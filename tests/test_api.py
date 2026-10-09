from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from boreal_marche.api.app import Services, create_app
from boreal_marche.assistant.core import AssistantResponse
from boreal_marche.assistant.providers import ProviderResponse

FEATURES = ["recency_days", "primary_country"]


class FakeModel:
    def predict_proba(self, frame):
        assert list(frame.columns) == FEATURES
        return np.array([[0.7, 0.3]] * len(frame))


class FakeComparisonModel:
    def predict_proba(self, frame):
        assert list(frame.columns) == FEATURES
        return np.array([[0.2, 0.8]] * len(frame))


class FakeAssistant:
    def answer(self, request):
        return AssistantResponse(
            intent="policy_search",
            answer="Grounded test answer",
            refused=False,
            handoff=False,
        )


def services() -> Services:
    return Services(
        model=FakeModel(),
        feature_names=FEATURES,
        threshold=0.4,
        model_version="test-model",
        protected_test_evaluated=False,
        rules_index={},
        popularity=["85048", "79323P"],
        catalog={"85048": "TEST PRODUCT"},
        assistant=FakeAssistant(),
        staff_assistant=FakeAssistant(),
    )


def test_operations_contracts() -> None:
    with TestClient(create_app(services=services())) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json()["components"] == {
            "head_a": True,
            "head_b": True,
            "head_c": True,
        }
        assert client.get("/version").json()["protected_test_evaluated"] is False
        contract = client.get("/contract").json()
        assert contract["feature_names"] == FEATURES
        assert contract["synthetic_example"] == {
            "recency_days": 0.0,
            "primary_country": "UNITED KINGDOM",
        }


def test_frontend_is_served_from_same_origin() -> None:
    with TestClient(create_app(services=services())) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
        assert "Boreal Marche Intelligence" in response.text
        assert client.get("/static/app.js").status_code == 200


def test_catalog_search_exposes_descriptions_not_customer_data() -> None:
    with TestClient(create_app(services=services())) as client:
        response = client.get("/catalog", params={"q": "test", "limit": 5})
        assert response.status_code == 200
        assert response.json() == {
            "items": [{"stock_code": "85048", "description": "TEST PRODUCT", "category": "other"}],
            "total": 1,
            "offset": 0,
            "categories": {"other": 1},
        }
        code_response = client.get("/catalog", params={"q": "85048", "limit": 5})
        assert code_response.status_code == 200
        assert code_response.json() == response.json()
        assert client.get("/catalog", params={"limit": 101}).status_code == 422
        assert client.get("/catalog", params={"offset": -1}).status_code == 422


def test_about_documents_use_explicit_allowlist() -> None:
    with TestClient(create_app(services=services())) as client:
        assert client.get("/about/data-card").status_code == 200
        assert client.get("/about/model-card").status_code == 200
        assert client.get("/about/privacy").status_code == 200
        assert client.get("/about/architecture").status_code == 200
        assert client.get("/about/not-approved").status_code == 404


def test_prediction_and_exact_feature_contract() -> None:
    with TestClient(create_app(services=services())) as client:
        response = client.post(
            "/predict",
            json={"features": {"recency_days": 15.0, "primary_country": "United Kingdom"}},
        )
        assert response.status_code == 200
        assert response.json()["return_probability_90d"] == 0.3
        assert response.json()["campaign_eligible"] is True
        invalid = client.post("/predict", json={"features": {"recency_days": 15.0}})
        assert invalid.status_code == 422
        assert invalid.json()["detail"]["missing"] == ["primary_country"]


def test_batch_prediction_limit_and_result() -> None:
    payload = {"features": {"recency_days": 15.0, "primary_country": "France"}}
    with TestClient(create_app(services=services())) as client:
        response = client.post("/predict/batch", json={"records": [payload, payload]})
        assert response.status_code == 200
        assert len(response.json()["predictions"]) == 2


def test_random_split_model_is_selected_explicitly() -> None:
    configured = services()
    configured.random_split_model = FakeComparisonModel()
    configured.random_split_model_version = "comparison-hash"
    configured.random_split_winner = "lightgbm"
    with TestClient(create_app(services=configured)) as client:
        contract = client.get("/contract").json()
        assert contract["model_variants"] == ["temporal", "random_80_20"]
        assert contract["random_split_winner"] == "lightgbm"
        payload = {"features": {"recency_days": 15.0, "primary_country": "United Kingdom"}}
        temporal = client.post("/predict", json=payload).json()
        comparison = client.post(
            "/predict", json={**payload, "model_variant": "random_80_20"}
        ).json()
        assert temporal["return_probability_90d"] == 0.3
        assert temporal["campaign_eligible"] is True
        assert comparison["return_probability_90d"] == 0.8
        assert comparison["campaign_eligible"] is False
        assert comparison["model_version"] == "comparison-hash"
        assert comparison["model_variant"] == "random_80_20"


def test_random_split_model_unavailable_is_explicit() -> None:
    with TestClient(create_app(services=services())) as client:
        response = client.post(
            "/predict",
            json={
                "features": {"recency_days": 15.0, "primary_country": "United Kingdom"},
                "model_variant": "random_80_20",
            },
        )
        assert response.status_code == 503


def test_recommendation_fallback_and_chat() -> None:
    with TestClient(create_app(services=services())) as client:
        recommendation = client.post("/recommend", json={"basket": [], "k": 2})
        assert recommendation.status_code == 200
        assert recommendation.json()["source"] == "empty_basket_popularity"
        no_match = client.post("/recommend", json={"basket": ["UNKNOWN"], "k": 2})
        assert no_match.status_code == 200
        assert no_match.json()["source"] == "no_match_popularity"
        assert len(no_match.json()["recommendations"]) == 2
        chat = client.post("/chat", json={"question": "What is the return policy?"})
        assert chat.status_code == 200
        assert chat.json()["answer"] == "Grounded test answer"


def test_contract_rejects_extra_fields_and_metrics_increment() -> None:
    with TestClient(create_app(services=services())) as client:
        response = client.post("/recommend", json={"basket": [], "k": 2, "unknown": True})
        assert response.status_code == 422
        metrics = client.get("/metrics").json()
        assert metrics["requests_total"] >= 1
        assert metrics["errors_total"] >= 1
        assert metrics["error_rate"] > 0
        assert metrics["alert_threshold"] == 0.2


def test_error_rate_alert_activates_after_repeated_invalid_requests() -> None:
    with TestClient(create_app(services=services())) as client:
        for _ in range(5):
            assert client.post("/predict", json={"features": {}}).status_code == 422
        metrics = client.get("/metrics").json()
        assert metrics["alert_active"] is True


def test_internal_tool_endpoints_require_valid_bearer_token() -> None:
    with TestClient(create_app(services=services(), internal_api_token="tool-secret")) as client:
        unauthenticated = client.post(
            "/internal/tools/recommendation", json={"basket": [], "k": 1}
        )
        assert unauthenticated.status_code == 401

        headers = {"Authorization": "Bearer tool-secret"}
        recommendation = client.post(
            "/internal/tools/recommendation",
            json={"basket": [], "k": 1},
            headers=headers,
        )
        assert recommendation.status_code == 200
        assert len(recommendation.json()["recommendations"]) == 1

        product = client.get("/internal/tools/product/85048", headers=headers)
        assert product.status_code == 200
        assert product.json() == {
            "found": True,
            "stock_code": "85048",
            "description": "TEST PRODUCT",
        }


def test_internal_tools_fail_closed_when_token_is_not_configured() -> None:
    with TestClient(create_app(services=services(), internal_api_token=None)) as client:
        response = client.get("/internal/tools/product/85048")
        assert response.status_code == 503


def test_staff_assistant_uses_demo_sign_in_not_internal_api_token(monkeypatch) -> None:
    monkeypatch.setenv("BOREAL_DEMO_STAFF_USERNAME", "staff-demo")
    monkeypatch.setenv("BOREAL_DEMO_STAFF_PASSWORD", "test-only-password")
    with TestClient(create_app(services=services(), internal_api_token="tool-secret")) as client:
        payload = {"question": "Are retention offers guaranteed?"}
        assert client.post("/internal/staff/chat", json=payload).status_code == 401
        assert client.post(
            "/internal/staff/chat",
            json=payload,
            headers={"Authorization": "Bearer tool-secret"},
        ).status_code == 401
        assert client.post("/internal/staff/login", json={"username": "staff-demo", "password": "wrong"}).status_code == 401
        login = client.post("/internal/staff/login", json={"username": "staff-demo", "password": "test-only-password"})
        assert login.status_code == 200
        assert login.json() == {"authenticated": True}
        assert "httponly" in login.headers["set-cookie"].lower()
        assert "samesite=strict" in login.headers["set-cookie"].lower()
        assert client.get("/internal/staff/session").json() == {"authenticated": True}
        allowed = client.post("/internal/staff/chat", json=payload)
        assert allowed.status_code == 200
        assert allowed.json()["intent"] == "policy_search"
        assert client.post("/internal/staff/logout").json() == {"authenticated": False}
        assert client.post("/internal/staff/chat", json=payload).status_code == 401


def test_demo_staff_login_fails_closed_without_private_credentials(monkeypatch) -> None:
    monkeypatch.delenv("BOREAL_DEMO_STAFF_USERNAME", raising=False)
    monkeypatch.delenv("BOREAL_DEMO_STAFF_PASSWORD", raising=False)
    with TestClient(create_app(services=services())) as client:
        response = client.post("/internal/staff/login", json={"username": "staff-demo", "password": "anything"})
        assert response.status_code == 503


def test_demo_staff_login_limits_repeated_failures(monkeypatch) -> None:
    monkeypatch.setenv("BOREAL_DEMO_STAFF_USERNAME", "staff-demo")
    monkeypatch.setenv("BOREAL_DEMO_STAFF_PASSWORD", "test-only-password")
    with TestClient(create_app(services=services())) as client:
        for _ in range(5):
            assert client.post("/internal/staff/login", json={"username": "staff-demo", "password": "wrong"}).status_code == 401
        assert client.post("/internal/staff/login", json={"username": "staff-demo", "password": "test-only-password"}).status_code == 429


def test_head_c_provider_selection_and_hosted_guardrails(monkeypatch) -> None:
    class FakeProvider:
        name = "openai"
        model = "test-hosted-model"

        def generate(self, request):
            assert "cake product" in request.user_prompt
            return ProviderResponse(
                provider=self.name,
                model=self.model,
                text='{"intent":"product_lookup","refused":false}',
                latency_ms=1,
            )

    monkeypatch.setenv("BOREAL_LLM_ACCESS_TOKEN", "demo-token")
    service = services()
    class CapturingAssistant(FakeAssistant):
        def answer(self, request):
            assert request.intent_hint == "product_lookup"
            return super().answer(request)

    service.assistant = CapturingAssistant()
    service.assistant_providers = {"openai": FakeProvider()}
    with TestClient(create_app(services=service)) as client:
        catalog = client.get("/assistant/providers").json()["providers"]
        assert [(item["id"], item["available"]) for item in catalog] == [
            ("baseline", True), ("openai", True), ("huggingface", False), ("ollama", False)
        ]
        payload = {"question": "can you find a cake product?", "provider": "openai"}
        assert client.post("/chat", json=payload).status_code == 401
        headers = {"X-Provider-Access": "demo-token"}
        assert client.post("/chat", json=payload, headers=headers).status_code == 422
        assert client.post("/chat", json={**payload, "hosted_data_consent": True, "intent_hint": "product_lookup"}, headers=headers).status_code == 422
        assert client.post("/chat", json={**payload, "hosted_data_consent": True, "question": "Find customer 12345's cake product"}, headers=headers).status_code == 422
        answer = client.post("/chat", json={**payload, "hosted_data_consent": True}, headers=headers)
        assert answer.status_code == 200
        assert answer.json()["provider"] == "openai"
        assert answer.json()["model"] == "test-hosted-model"


def test_unconfigured_llm_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("BOREAL_LLM_ACCESS_TOKEN", raising=False)
    with TestClient(create_app(services=services())) as client:
        response = client.post("/chat", json={"question": "What is shipping?", "provider": "ollama"})
        assert response.status_code == 503


def test_huggingface_selection_requires_access_and_hosted_consent(monkeypatch) -> None:
    class FakeHuggingFace:
        model = "test-hf-model"

        def generate(self, request):
            return ProviderResponse(
                provider="huggingface",
                model=self.model,
                text='{"intent":"policy_search","refused":false}',
                latency_ms=1,
            )

    monkeypatch.setenv("BOREAL_LLM_ACCESS_TOKEN", "demo-token")
    service = services()
    service.assistant_providers = {"huggingface": FakeHuggingFace()}
    payload = {"question": "What is the return policy?", "provider": "huggingface"}
    with TestClient(create_app(services=service)) as client:
        catalog = client.get("/assistant/providers").json()["providers"]
        assert [(item["id"], item["available"]) for item in catalog] == [
            ("baseline", True), ("openai", False), ("huggingface", True), ("ollama", False)
        ]
        assert client.post("/chat", json=payload).status_code == 401
        headers = {"X-Provider-Access": "demo-token"}
        assert client.post("/chat", json=payload, headers=headers).status_code == 422
        assert client.post("/chat", json={**payload, "hosted_data_consent": True, "question": "Find customer 12345"}, headers=headers).status_code == 422
        response = client.post("/chat", json={**payload, "hosted_data_consent": True}, headers=headers)
        assert response.status_code == 200
        assert response.json()["provider"] == "huggingface"


def test_ollama_selection_uses_local_provider_without_hosted_consent(monkeypatch) -> None:
    class FakeOllama:
        name = "ollama"
        model = "local-test-model"

        def generate(self, request):
            return ProviderResponse(
                provider=self.name,
                model=self.model,
                text='{"intent":"policy_search","refused":false}',
                latency_ms=1,
            )

    monkeypatch.setenv("BOREAL_LLM_ACCESS_TOKEN", "demo-token")
    service = services()
    service.assistant_providers = {"ollama": FakeOllama()}
    with TestClient(create_app(services=service)) as client:
        response = client.post(
            "/chat",
            json={"question": "What is the shipping policy?", "provider": "ollama"},
            headers={"X-Provider-Access": "demo-token"},
        )
        assert response.status_code == 200
        assert response.json()["provider"] == "ollama"
        assert response.json()["model"] == "local-test-model"
