"""FastAPI application that integrates the three model heads behind typed contracts."""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
import joblib
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from boreal_marche.assistant.api_tools import ApiToolConfig, AuthenticatedApiTools
from boreal_marche.assistant.core import (
    AssistantRequest,
    AssistantResponse,
    AssistantTools,
    PolicyRetriever,
    ProductLookupResult,
    RuleBasedAssistant,
    route_intent,
)
from boreal_marche.assistant.provider_evaluation import parse_provider_decision
from boreal_marche.assistant.providers import (
    AssistantProvider,
    ProviderRequest,
    configured_providers,
)
from boreal_marche.assistant.routing_prompt import SYSTEM_PROMPT
from boreal_marche.data.ingest import sha256_file
from boreal_marche.monitoring.drift import analyze_batch
from boreal_marche.recommendation.recommend import recommend


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoStaffLogin(StrictModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


FeatureValue = float | int | str | None


CATALOG_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("kitchen_dining", ("mug", "cup", "plate", "bowl", "cake", "tea", "coffee", "glass", "spoon", "fork", "napkin", "kitchen", "bottle", "coaster")),
    ("bags_storage", ("bag", "box", "basket", "case", "storage", "lunch", "tin")),
    ("stationery_crafts", ("pencil", "pen", "notebook", "card", "paper", "ribbon", "sticker", "craft", "felt", "tape")),
    ("home_decor", ("candle", "holder", "heart", "sign", "ornament", "frame", "mirror", "clock", "light", "lantern", "drawer", "cabinet")),
    ("gifts_seasonal", ("christmas", "xmas", "easter", "birthday", "gift", "decoration", "toy", "doll", "stocking")),
    ("accessories", ("necklace", "bracelet", "ring", "parasol", "fan", "umbrella", "scarf", "purse")),
)


def _catalog_category(description: str) -> str:
    normalized = description.casefold()
    for category, keywords in CATALOG_CATEGORY_KEYWORDS:
        if any(re.search(rf"\b{re.escape(keyword)}(?:s|es)?\b", normalized) for keyword in keywords):
            return category
    return "other"


class PredictionRequest(StrictModel):
    features: dict[str, FeatureValue] = Field(min_length=1, max_length=60)
    model_variant: Literal["temporal", "random_80_20"] = "temporal"


class BatchPredictionRequest(StrictModel):
    records: list[PredictionRequest] = Field(min_length=1, max_length=100)


class PredictionResponse(StrictModel):
    return_probability_90d: float = Field(ge=0, le=1)
    campaign_eligible: bool
    threshold: float = Field(ge=0, le=1)
    model_version: str
    model_variant: Literal["temporal", "random_80_20"] = "temporal"


class BatchPredictionResponse(StrictModel):
    predictions: list[PredictionResponse]


class RecommendationApiRequest(StrictModel):
    basket: list[str] = Field(default_factory=list, max_length=50)
    k: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def normalize_codes(self) -> RecommendationApiRequest:
        self.basket = [code.strip().upper() for code in self.basket if code.strip()]
        return self


class RecommendationItem(StrictModel):
    item: str
    support: float | None
    confidence: float | None
    lift: float | None
    firing_rule: str | None


class RecommendationResponse(StrictModel):
    source: str
    recommendations: list[RecommendationItem]


class CatalogItem(StrictModel):
    stock_code: str
    description: str
    category: str


class CatalogResponse(StrictModel):
    items: list[CatalogItem]
    total: int
    offset: int
    categories: dict[str, int]


class HealthResponse(StrictModel):
    status: str


class ReadyResponse(StrictModel):
    ready: bool
    components: dict[str, bool]


class VersionResponse(StrictModel):
    service_version: str
    model_version: str
    protected_test_evaluated: bool


class MetricsResponse(StrictModel):
    requests_total: int
    errors_total: int
    average_latency_ms: float
    error_rate: float = Field(ge=0, le=1)
    alert_threshold: float = Field(ge=0, le=1)
    alert_active: bool


class DriftDemoRequest(StrictModel):
    records: list[PredictionRequest] = Field(min_length=1, max_length=150)


class ContractResponse(StrictModel):
    feature_names: list[str]
    threshold: float = Field(ge=0, le=1)
    model_version: str
    synthetic_example: dict[str, FeatureValue]
    model_variants: list[str] = Field(default_factory=lambda: ["temporal"])
    random_split_winner: str | None = None


@dataclass
class Services:
    model: Any
    feature_names: list[str]
    threshold: float
    model_version: str
    protected_test_evaluated: bool
    rules_index: dict[str, list[dict[str, Any]]]
    popularity: list[str]
    catalog: dict[str, str]
    assistant: RuleBasedAssistant
    staff_assistant: RuleBasedAssistant | None = None
    assistant_providers: dict[str, AssistantProvider] = field(default_factory=dict)
    recommendation_catalog: list[str] | None = None
    random_split_model: Any | None = None
    random_split_model_version: str | None = None
    random_split_winner: str | None = None
    drift_baseline: dict[str, Any] | None = None


def _synthetic_reference(model: Any, feature_names: list[str]) -> dict[str, FeatureValue]:
    """Build a plausible UI reference row from the fitted preprocessing statistics.

    The production artifact stores the numeric training medians inside its imputer.
    Reusing them keeps demonstration profiles in distribution without loading source
    customer data into the service.
    """
    example: dict[str, FeatureValue] = {name: 0.0 for name in feature_names}
    if "primary_country" in example:
        example["primary_country"] = "UNITED KINGDOM"
    try:
        calibrated = model.calibrated_classifiers_[0]
        frozen = calibrated.estimator
        pipeline = getattr(frozen, "estimator", frozen)
        transformer = pipeline.named_steps["preprocess"]
        numeric_pipeline = transformer.named_transformers_["numeric"]
        numeric_columns = list(transformer.transformers_[0][2])
        statistics = numeric_pipeline.named_steps["impute"].statistics_
        for name, value in zip(numeric_columns, statistics, strict=True):
            if pd.notna(value):
                example[name] = float(value)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        # Test doubles and future model families may not expose sklearn internals.
        # The exact feature contract is still returned in that case.
        pass
    return example


def _normalize_prediction_features(features: dict[str, FeatureValue]) -> dict[str, FeatureValue]:
    normalized = dict(features)
    country = normalized.get("primary_country")
    if isinstance(country, str):
        normalized["primary_country"] = country.strip().upper()
    return normalized


def load_services(root: Path) -> Services:
    model_path = root / "artifacts" / "retention_model.joblib"
    metadata = json.loads((root / "artifacts" / "retention_model_meta.json").read_text())
    rules = json.loads((root / "artifacts" / "recommendation_rules.json").read_text())
    model = joblib.load(model_path)
    drift_path = root / "src/boreal_marche/monitoring/development_baseline.json"
    drift_baseline = json.loads(drift_path.read_text(encoding="utf-8")) if drift_path.is_file() else None
    if drift_baseline is not None and drift_baseline["model_version"] != metadata["artifact_sha256"][:12]:
        raise RuntimeError("Drift baseline does not match the official temporal model")
    random_path = root / "artifacts/retention_model_random_80_20.joblib"
    random_report_path = root / "artifacts/retention_model_random_80_20_meta.json"
    random_model = None
    random_version = None
    random_winner = None
    if random_path.exists() and random_report_path.exists():
        random_report = json.loads(random_report_path.read_text(encoding="utf-8"))
        if sha256_file(random_path) != random_report["artifact_sha256"]:
            raise RuntimeError("80/20 comparison artifact differs from its report hash")
        random_model = joblib.load(random_path)
        if list(random_model.feature_names_in_) != list(model.feature_names_in_):
            raise RuntimeError("80/20 comparison feature schema differs from the temporal model")
        random_version = random_report["artifact_sha256"][:12]
        random_winner = random_report.get("selected_model")
    retriever = PolicyRetriever(
        root / "docs" / "corpus",
        allowed_document_ids={"policy_returns", "policy_shipping", "policy_privacy"},
    )
    direct_tools = AssistantTools(root, retriever)
    tool_api_base_url = os.getenv("BOREAL_TOOL_API_BASE_URL")
    tool_api_token = os.getenv("BOREAL_API_TOKEN")
    assistant_tools = (
        AuthenticatedApiTools(
            ApiToolConfig(
                base_url=tool_api_base_url,
                bearer_token=SecretStr(tool_api_token),
            ),
            retriever,
        )
        if tool_api_base_url and tool_api_token
        else direct_tools
    )
    assistant = RuleBasedAssistant(assistant_tools)
    staff_retriever = PolicyRetriever(
        root / "docs" / "corpus", allowed_document_ids={"policy_loyalty"}
    )
    staff_assistant = RuleBasedAssistant(AssistantTools(root, staff_retriever))
    return Services(
        model=model,
        feature_names=list(model.feature_names_in_),
        threshold=float(metadata["selected_threshold"]["threshold"]),
        model_version=str(metadata["artifact_sha256"][:12]),
        protected_test_evaluated=bool(metadata["protected_test_evaluated"]),
        rules_index=rules["rules_index"],
        popularity=rules["popularity"],
        catalog=direct_tools.catalog,
        assistant=assistant,
        staff_assistant=staff_assistant,
        assistant_providers={
            name: provider
            for name, provider in configured_providers().items()
            if name in {"openai", "huggingface", "ollama"}
        },
        recommendation_catalog=rules["catalog"],
        random_split_model=random_model,
        random_split_model_version=random_version,
        random_split_winner=random_winner,
        drift_baseline=drift_baseline,
    )


def _require_internal_token(authorization: str | None, expected_token: str | None) -> None:
    if not expected_token:
        raise HTTPException(status_code=503, detail="Internal tool authentication is not configured.")
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not hmac.compare_digest(supplied, expected_token):
        raise HTTPException(status_code=401, detail="Valid internal bearer token required.")


def _predict(payload: PredictionRequest, services: Services) -> PredictionResponse:
    supplied = set(payload.features)
    expected = set(services.feature_names)
    if supplied != expected:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Feature keys must exactly match the model contract.",
                "missing": sorted(expected - supplied),
                "unexpected": sorted(supplied - expected),
            },
        )
    normalized = _normalize_prediction_features(payload.features)
    frame = pd.DataFrame([normalized], columns=services.feature_names)
    if payload.model_variant == "random_80_20":
        if services.random_split_model is None or services.random_split_model_version is None:
            raise HTTPException(status_code=503, detail="80/20 comparison model is unavailable")
        model = services.random_split_model
        version = services.random_split_model_version
    else:
        model = services.model
        version = services.model_version
    probability = float(model.predict_proba(frame)[0, 1])
    return PredictionResponse(
        return_probability_90d=probability,
        campaign_eligible=probability <= services.threshold,
        threshold=services.threshold,
        model_version=version,
        model_variant=payload.model_variant,
    )


def create_app(
    root: Path | None = None,
    services: Services | None = None,
    internal_api_token: str | None = None,
) -> FastAPI:
    project_root = (root or Path.cwd()).resolve()
    expected_internal_token = internal_api_token or os.getenv("BOREAL_API_TOKEN")
    expected_provider_access_token = os.getenv("BOREAL_LLM_ACCESS_TOKEN")
    drift_demo_enabled = os.getenv("BOREAL_ENABLE_DRIFT_DEMO", "0") == "1"
    demo_staff_username = os.getenv("BOREAL_DEMO_STAFF_USERNAME")
    demo_staff_password = os.getenv("BOREAL_DEMO_STAFF_PASSWORD")
    staff_sessions: dict[str, float] = {}
    login_failures: dict[str, list[float]] = {}
    staff_cookie = "boreal_staff_demo"
    staff_session_seconds = 30 * 60

    def require_staff_session(request: Request) -> None:
        session_id = request.cookies.get(staff_cookie, "")
        expires_at = staff_sessions.get(session_id, 0.0)
        if not session_id or expires_at <= time.monotonic():
            staff_sessions.pop(session_id, None)
            raise HTTPException(status_code=401, detail="Staff sign-in required.")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = services or load_services(project_root)
        app.state.requests_total = 0
        app.state.errors_total = 0
        app.state.total_latency_ms = 0.0
        yield

    app = FastAPI(
        title="Boreal Marche Customer Intelligence API",
        version="0.4.0",
        description="Typed service for retention, recommendation, assistant, and D4 monitoring workflows.",
        lifespan=lifespan,
    )
    frontend_dir = project_root / "frontend"
    if frontend_dir.is_dir():
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.middleware("http")
    async def record_metrics(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
            if response.status_code >= 400:
                request.app.state.errors_total += 1
            return response
        except Exception:
            request.app.state.errors_total += 1
            raise
        finally:
            request.app.state.requests_total += 1
            request.app.state.total_latency_ms += (time.perf_counter() - started) * 1000

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/ready", response_model=ReadyResponse, tags=["operations"])
    def ready(request: Request) -> ReadyResponse:
        loaded = hasattr(request.app.state, "services")
        return ReadyResponse(
            ready=loaded,
            components={"head_a": loaded, "head_b": loaded, "head_c": loaded},
        )

    @app.get("/version", response_model=VersionResponse, tags=["operations"])
    def version(request: Request) -> VersionResponse:
        service: Services = request.app.state.services
        return VersionResponse(
            service_version=app.version,
            model_version=service.model_version,
            protected_test_evaluated=service.protected_test_evaluated,
        )

    @app.get("/contract", response_model=ContractResponse, tags=["operations"])
    def contract(request: Request) -> ContractResponse:
        service: Services = request.app.state.services
        example = _synthetic_reference(service.model, service.feature_names)
        return ContractResponse(
            feature_names=service.feature_names,
            threshold=service.threshold,
            model_version=service.model_version,
            synthetic_example=example,
            model_variants=["temporal", "random_80_20"] if service.random_split_model else ["temporal"],
            random_split_winner=service.random_split_winner,
        )

    @app.post("/predict", response_model=PredictionResponse, tags=["head-a"])
    def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
        return _predict(payload, request.app.state.services)

    @app.post("/predict/batch", response_model=BatchPredictionResponse, tags=["head-a"])
    def predict_batch(payload: BatchPredictionRequest, request: Request) -> BatchPredictionResponse:
        service: Services = request.app.state.services
        return BatchPredictionResponse(predictions=[_predict(row, service) for row in payload.records])

    @app.post("/recommend", response_model=RecommendationResponse, tags=["head-b"])
    def recommendation(payload: RecommendationApiRequest, request: Request) -> dict[str, Any]:
        service: Services = request.app.state.services
        return recommend(payload.basket, service.rules_index, service.popularity, payload.k)

    @app.get("/catalog", response_model=CatalogResponse, tags=["head-b"])
    def catalog(
        request: Request,
        q: str = "",
        category: str = "all",
        offset: int = 0,
        limit: int = 30,
    ) -> CatalogResponse:
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        if offset < 0:
            raise HTTPException(status_code=422, detail="offset must be zero or greater")
        service: Services = request.app.state.services
        eligible = service.recommendation_catalog or list(service.catalog)
        needle = q.strip().casefold()
        category_counts: dict[str, int] = {}
        for code in eligible:
            if code in service.catalog:
                item_category = _catalog_category(service.catalog[code])
                category_counts[item_category] = category_counts.get(item_category, 0) + 1
        matches = [
            CatalogItem(
                stock_code=code,
                description=service.catalog[code],
                category=_catalog_category(service.catalog[code]),
            )
            for code in eligible
            if code in service.catalog
            and (needle in code.casefold() or needle in service.catalog[code].casefold())
            and (category == "all" or _catalog_category(service.catalog[code]) == category)
        ]
        matches.sort(key=lambda item: (item.description.casefold(), item.stock_code))
        return CatalogResponse(
            items=matches[offset : offset + limit],
            total=len(matches),
            offset=offset,
            categories=dict(sorted(category_counts.items())),
        )

    @app.post(
        "/internal/tools/recommendation",
        response_model=RecommendationResponse,
        tags=["internal-tools"],
    )
    def internal_recommendation(
        payload: RecommendationApiRequest,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _require_internal_token(authorization, expected_internal_token)
        service: Services = request.app.state.services
        return recommend(payload.basket, service.rules_index, service.popularity, payload.k)

    @app.get(
        "/internal/tools/product/{stock_code}",
        response_model=ProductLookupResult,
        tags=["internal-tools"],
    )
    def internal_product_lookup(
        stock_code: str,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ProductLookupResult:
        _require_internal_token(authorization, expected_internal_token)
        normalized = stock_code.strip().upper()
        description = request.app.state.services.catalog.get(normalized)
        return ProductLookupResult(
            found=description is not None,
            stock_code=normalized,
            description=description,
        )

    @app.post("/chat", response_model=AssistantResponse, tags=["head-c"])
    def chat(
        payload: AssistantRequest,
        request: Request,
        provider_access: Annotated[str | None, Header(alias="X-Provider-Access")] = None,
    ) -> AssistantResponse:
        service: Services = request.app.state.services
        if payload.provider == "baseline":
            return service.assistant.answer(payload)
        if not expected_provider_access_token:
            raise HTTPException(status_code=503, detail="LLM access control is not configured.")
        if not hmac.compare_digest(provider_access or "", expected_provider_access_token):
            raise HTTPException(status_code=401, detail="Valid LLM access token required.")
        if payload.intent_hint != "auto":
            raise HTTPException(status_code=422, detail="LLM routing requires automatic question category.")
        provider = service.assistant_providers.get(payload.provider)
        if provider is None:
            raise HTTPException(status_code=503, detail=f"{payload.provider} provider is not configured.")
        if payload.provider in {"openai", "huggingface"}:
            if not payload.hosted_data_consent:
                raise HTTPException(status_code=422, detail="Confirm that the question contains no personal or customer data before using a hosted provider.")
            if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b(?:\+?\d[\d\s().-]{7,}\d)\b|\b(?:customer|client|order|invoice)\s*#?\s*\d{3,}\b", payload.question, re.IGNORECASE):
                raise HTTPException(status_code=422, detail="This question may contain personal or transaction data. Use the local baseline instead.")
        safety_intent = route_intent(payload.question)
        if safety_intent in {"privacy_refusal", "out_of_scope", "retention_score"}:
            return service.assistant.answer(payload)
        try:
            generated = provider.generate(
                ProviderRequest(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=payload.question,
                    max_tokens=120,
                )
            )
            decision = parse_provider_decision(generated.text)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=502, detail=f"{payload.provider} routing failed ({type(error).__name__}).") from error
        grounded = service.assistant.answer(
            payload.model_copy(update={"intent_hint": decision.intent})
        )
        return grounded.model_copy(update={"provider": payload.provider, "model": generated.model})

    @app.get("/assistant/providers", tags=["head-c"])
    def assistant_providers(request: Request) -> dict[str, Any]:
        available = request.app.state.services.assistant_providers
        return {
            "providers": [
                {"id": "baseline", "available": True, "model": "keyword router + grounded tools"},
                *[
                    {"id": name, "available": name in available and bool(expected_provider_access_token), "model": available[name].model if name in available else None}
                    for name in ("openai", "huggingface", "ollama")
                ],
            ]
        }

    @app.post("/internal/staff/login", tags=["head-c-internal"])
    def staff_login(payload: DemoStaffLogin, request: Request, response: Response) -> dict[str, bool]:
        if not demo_staff_username or not demo_staff_password:
            raise HTTPException(status_code=503, detail="Demo staff sign-in is not configured.")
        client_id = request.client.host if request.client else "unknown"
        now = time.monotonic()
        failures = [attempt for attempt in login_failures.get(client_id, []) if now - attempt < 60]
        login_failures[client_id] = failures
        if len(failures) >= 5:
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again later.")
        valid_username = hmac.compare_digest(payload.username, demo_staff_username)
        valid_password = hmac.compare_digest(payload.password, demo_staff_password)
        if not (valid_username and valid_password):
            failures.append(now)
            raise HTTPException(status_code=401, detail="Invalid staff sign-in.")
        login_failures.pop(client_id, None)
        session_id = secrets.token_urlsafe(32)
        staff_sessions[session_id] = time.monotonic() + staff_session_seconds
        response.set_cookie(
            key=staff_cookie,
            value=session_id,
            max_age=staff_session_seconds,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            path="/internal/staff",
        )
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": True}

    @app.get("/internal/staff/session", tags=["head-c-internal"])
    def staff_session(request: Request, response: Response) -> dict[str, bool]:
        require_staff_session(request)
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": True}

    @app.post("/internal/staff/logout", tags=["head-c-internal"])
    def staff_logout(request: Request, response: Response) -> dict[str, bool]:
        staff_sessions.pop(request.cookies.get(staff_cookie, ""), None)
        response.delete_cookie(staff_cookie, path="/internal/staff", samesite="strict")
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": False}

    @app.post("/internal/staff/chat", response_model=AssistantResponse, tags=["head-c-internal"])
    def staff_chat(
        payload: AssistantRequest,
        request: Request,
    ) -> AssistantResponse:
        require_staff_session(request)
        assistant = request.app.state.services.staff_assistant
        if assistant is None:
            raise HTTPException(status_code=503, detail="Staff assistant is unavailable.")
        intent = route_intent(payload.question)
        if intent in {"privacy_refusal", "out_of_scope"}:
            return assistant.answer(payload)
        return assistant.answer(
            AssistantRequest(question=payload.question, intent_hint="policy_search")
        )

    @app.get("/metrics", response_model=MetricsResponse, tags=["operations"])
    def metrics(request: Request) -> MetricsResponse:
        count = request.app.state.requests_total
        errors = request.app.state.errors_total
        error_rate = errors / count if count else 0.0
        alert_threshold = float(os.getenv("BOREAL_ERROR_RATE_ALERT_THRESHOLD", "0.20"))
        return MetricsResponse(
            requests_total=count,
            errors_total=errors,
            average_latency_ms=request.app.state.total_latency_ms / count if count else 0.0,
            error_rate=error_rate,
            alert_threshold=alert_threshold,
            alert_active=count >= 5 and error_rate >= alert_threshold,
        )

    @app.get("/monitoring/drift/reference", tags=["operations"])
    def drift_reference(request: Request) -> dict[str, Any]:
        baseline = request.app.state.services.drift_baseline
        if not drift_demo_enabled or baseline is None:
            return {"enabled": False, "reason": "Synthetic drift demonstration is not enabled."}
        return {
            "enabled": True,
            "model_version": baseline["model_version"],
            "development_rows": baseline["development_rows"],
            "snapshot_roles": baseline["snapshot_roles"],
            "min_demo_samples": baseline["min_demo_samples"],
            "features": {
                name: {
                    "sample_values": baseline["metrics"][name]["sample_values"],
                    "reference_proportions": baseline["metrics"][name]["reference_proportions"],
                }
                for name in ("recency_days", "frequency_orders", "monetary_total", "unique_products")
            },
            "synthetic_demo_only": True,
        }

    @app.post("/monitoring/drift/demo", tags=["operations"])
    def drift_demo(payload: DriftDemoRequest, request: Request) -> dict[str, Any]:
        service: Services = request.app.state.services
        if not drift_demo_enabled or service.drift_baseline is None:
            raise HTTPException(status_code=503, detail="Synthetic drift demonstration is disabled.")
        if any(row.model_variant != "temporal" for row in payload.records):
            raise HTTPException(status_code=422, detail="Only the official temporal model is monitored.")
        expected = set(service.feature_names)
        if any(set(row.features) != expected for row in payload.records):
            raise HTTPException(status_code=422, detail="Every synthetic profile must match the model feature contract.")
        frame = pd.DataFrame(
            [_normalize_prediction_features(row.features) for row in payload.records],
            columns=service.feature_names,
        )
        try:
            probabilities = service.model.predict_proba(frame)[:, 1]
            return analyze_batch(service.drift_baseline, frame, probabilities)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    if frontend_dir.is_dir():

        @app.get("/about/{document}", include_in_schema=False)
        def about_document(document: str) -> FileResponse:
            documents = {
                "data-card": project_root / "DATA_CARD.md",
                "model-card": project_root / "MODEL_CARD.md",
                "privacy": project_root / "docs/corpus/privacy_policy.md",
                "architecture": project_root / "docs/assets/system_architecture.png",
            }
            path = documents.get(document)
            if path is None or not path.is_file():
                raise HTTPException(status_code=404, detail="Document not found")
            return FileResponse(path)

        @app.get("/", include_in_schema=False)
        def frontend() -> FileResponse:
            return FileResponse(frontend_dir / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
