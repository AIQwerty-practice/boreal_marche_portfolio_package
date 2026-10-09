"""Grounded bilingual assistant baseline and typed Head A/Head B tool contracts."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from boreal_marche.recommendation.recommend import recommend


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicySearchRequest(StrictModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=2, ge=1, le=5)


class RecommendationRequest(StrictModel):
    basket: list[str] = Field(default_factory=list, max_length=50)
    k: int = Field(default=5, ge=1, le=20)


class ProductLookupRequest(StrictModel):
    stock_code: str = Field(min_length=1, max_length=30)


class RetentionScoreRequest(StrictModel):
    customer_id: str = Field(min_length=1, max_length=50)


class AssistantRequest(StrictModel):
    question: str = Field(min_length=2, max_length=1000)
    customer_verified: bool = False
    intent_hint: Literal["auto", "policy_search", "product_lookup", "recommendation", "retention_score", "privacy_refusal", "out_of_scope"] = "auto"
    basket: list[str] = Field(default_factory=list, max_length=50)
    provider: Literal["baseline", "openai", "huggingface", "ollama"] = "baseline"
    hosted_data_consent: bool = False


class Citation(StrictModel):
    document_id: str
    title: str
    version: str


class PolicySearchResult(StrictModel):
    document_id: str
    title: str
    version: str
    text: str
    score: float = Field(ge=0, le=1)


class ProductLookupResult(StrictModel):
    found: bool
    stock_code: str
    description: str | None


class AssistantResponse(StrictModel):
    intent: str
    answer: str
    refused: bool
    handoff: bool
    provider: str = "baseline"
    model: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    tool_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class Chunk:
    document_id: str
    title: str
    version: str
    text: str


def parse_policy(path: Path) -> Chunk:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"Missing front matter in {path.name}")
    metadata = {}
    for line in parts[1].strip().splitlines():
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return Chunk(
        document_id=metadata["document_id"],
        title=metadata["title"],
        version=metadata["version"],
        text=parts[2].strip(),
    )


class PolicyRetriever:
    """Character n-gram retrieval supports English/French spelling variation."""

    def __init__(self, corpus_directory: Path, allowed_document_ids: set[str] | None = None):
        self.chunks = [parse_policy(path) for path in sorted(corpus_directory.glob("*.md"))]
        if allowed_document_ids is not None:
            self.chunks = [chunk for chunk in self.chunks if chunk.document_id in allowed_document_ids]
        if not self.chunks:
            raise ValueError("Policy corpus is empty")
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(chunk.text for chunk in self.chunks)

    def search(self, request: PolicySearchRequest) -> list[PolicySearchResult]:
        query = self.vectorizer.transform([request.query])
        scores = cosine_similarity(query, self.matrix)[0]
        ranked = scores.argsort()[::-1][: request.k]
        return [
            PolicySearchResult(
                document_id=self.chunks[index].document_id,
                title=self.chunks[index].title,
                version=self.chunks[index].version,
                text=self.chunks[index].text,
                score=float(scores[index]),
            )
            for index in ranked
        ]


def route_intent(question: str) -> str:
    normalized = question.casefold()
    if "privacy rule" in normalized or "règle de confidentialité" in normalized:
        return "policy_search"
    if normalized.startswith("should recommendations"):
        return "policy_search"
    privacy_patterns = (
        "another customer",
        "another shopper",
        "autre client",
        "autre cliente",
        "quelqu'un d'autre",
        "someone else's",
        "other customer's",
    )
    unverified_customer_reference = re.search(
        r"\b(?:customer|client|cliente)\s*#?\s*\d{3,}\b", normalized
    )
    sensitive_disclosure = any(
        term in normalized
        for term in (
            "purchase history",
            "purchase data",
            "email address",
            "retention score",
            "historique d'achat",
            "adresse courriel",
            "score de rétention",
        )
    )
    if any(pattern in normalized for pattern in privacy_patterns) or (
        unverified_customer_reference and sensitive_disclosure
    ):
        return "privacy_refusal"
    out_of_scope = (
        "malware",
        "medical advice",
        "conseil médical",
        "mot de passe",
        "password",
        "stock market",
        "marché boursier",
        "guarantee that",
        "garantis que",
        "approve a retention",
        "approuve une remise",
    )
    if any(pattern in normalized for pattern in out_of_scope):
        return "out_of_scope"
    if any(pattern in normalized for pattern in ("recommend", "suggest", "goes with", "recommande")):
        return "recommendation"
    if re.search(r"\b(?:find|search|looking for|carry|do you have|have you got|trouve|cherche|recherche|avez-vous|vendez)\b.{0,60}\b(?:product|item|article|produit)\b", normalized):
        return "product_lookup"
    if any(
        pattern in normalized
        for pattern in (
            "find product",
            "look up",
            "stock code",
            "trouve le produit",
            "trouver le produit",
            "recherche le produit",
            "rechercher le produit",
        )
    ):
        return "product_lookup"
    if any(
        pattern in normalized
        for pattern in (
            "retention probability",
            "return score",
            "retention score",
            "probabilité de rétention",
            "probabilité de retour",
            "score de rétention",
        )
    ):
        return "retention_score"
    return "policy_search"


def extract_stock_codes(question: str) -> list[str]:
    return re.findall(r"\b(?=[A-Z0-9]*\d)[A-Z0-9]{5,6}\b", question.upper())


def product_search_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[\w]+", query.casefold()) if term not in {
        "can", "you", "find", "a", "an", "the", "product", "products", "item", "items", "for", "me",
        "do", "have", "any", "please", "search", "look", "up", "i", "want", "with", "what",
        "un", "une", "des", "de", "du", "le", "la", "les", "produit", "article",
        "pouvez", "vous", "trouver", "cherche", "recherche", "avez", "est", "ce", "que",
        "rechercher", "recommend", "recommendation", "recommendations", "suggest", "goes",
        "recommande", "recommandations", "would", "buy", "together", "pour", "avec", "quels", "quelles",
    }]


class AssistantTools:
    def __init__(self, root: Path, retriever: PolicyRetriever):
        self.root = root
        self.retriever = retriever
        rules = json.loads((root / "artifacts" / "recommendation_rules.json").read_text())
        self.rules_index = rules["rules_index"]
        self.popularity = rules["popularity"]
        transactions = pd.read_parquet(
            root / "data" / "processed" / "transactions_clean.parquet",
            columns=["stock_code", "description"],
        )
        self.catalog = (
            transactions.drop_duplicates(["stock_code"], keep="last")
            .set_index("stock_code")["description"]
            .astype(str)
            .to_dict()
        )
        self.eligible_catalog = {code: self.catalog[code] for code in rules["catalog"] if code in self.catalog}

    def policy_search(self, request: PolicySearchRequest) -> list[PolicySearchResult]:
        return self.retriever.search(request)

    def recommendation(self, request: RecommendationRequest) -> dict[str, Any]:
        return recommend(request.basket, self.rules_index, self.popularity, request.k)

    def product_lookup(self, request: ProductLookupRequest) -> ProductLookupResult:
        description = self.catalog.get(request.stock_code)
        return ProductLookupResult(
            found=description is not None,
            stock_code=request.stock_code,
            description=description,
        )

    def search_products(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        needle = query.strip().casefold()
        if not needle:
            return []
        terms = product_search_terms(needle)
        if not terms:
            return []
        matches = [
            {"stock_code": code, "description": description}
            for code, description in self.eligible_catalog.items()
            if all(term in f"{code} {description}".casefold() for term in terms)
        ]
        return sorted(matches, key=lambda item: (item["description"].casefold(), item["stock_code"]))[:limit]

    def retention_score(self, request: RetentionScoreRequest) -> dict[str, Any]:
        return {
            "status": "requires_verified_api_context",
            "customer_id": request.customer_id,
            "message": "Retention scoring will be enabled through the authenticated project API.",
        }


class RuleBasedAssistant:
    def __init__(self, tools: AssistantTools, minimum_retrieval_score: float = 0.08):
        self.tools = tools
        self.minimum_retrieval_score = minimum_retrieval_score

    def answer(self, request: AssistantRequest) -> AssistantResponse:
        intent = route_intent(request.question)
        if request.intent_hint != "auto" and intent not in {"privacy_refusal", "out_of_scope", "retention_score"}:
            intent = request.intent_hint
        french = bool(re.search(r"\b(quel|quand|combien|puis|recommande|trouve|les|des)\b", request.question.casefold()))
        if intent == "privacy_refusal":
            answer = (
                "Je ne peux pas divulguer les données d'un autre client. Je transmets la demande à un responsable."
                if french
                else "I cannot disclose another customer's data. I will hand this request to a privacy specialist."
            )
            return AssistantResponse(intent=intent, answer=answer, refused=True, handoff=True)
        if intent == "out_of_scope":
            answer = (
                "Je ne peux pas effectuer cette demande. Un membre du personnel peut vous aider."
                if french
                else "I cannot complete that request. A staff member can help with an appropriate next step."
            )
            return AssistantResponse(intent=intent, answer=answer, refused=True, handoff=True)
        if intent == "recommendation":
            codes = extract_stock_codes(request.question)
            matching_products = self.tools.search_products(request.question, limit=1)
            if matching_products:
                codes = codes or [matching_products[0]["stock_code"]]
            codes = codes or [code.strip().upper() for code in request.basket if code.strip()]
            result = self.tools.recommendation(RecommendationRequest(basket=codes))
            result["matched_product"] = matching_products[0] if matching_products else None
            result["used_basket"] = codes
            return AssistantResponse(
                intent=intent,
                answer=("Voici les recommandations disponibles." if french else "Here are the available recommendations."),
                refused=False,
                handoff=False,
                tool_result=result,
            )
        if intent == "product_lookup":
            codes = extract_stock_codes(request.question)
            matches = self.tools.search_products(request.question)
            if codes and not matches:
                result = self.tools.product_lookup(ProductLookupRequest(stock_code=codes[0]))
                matches = [result.model_dump()] if result.found else []
            return AssistantResponse(
                intent=intent,
                answer=("Voici les produits correspondants du catalogue de démonstration." if french else "Here are matching products in the demonstration catalog.") if matches else ("Aucun produit correspondant dans le catalogue de démonstration." if french else "No matching product in the demonstration catalog."),
                refused=False,
                handoff=False,
                tool_result={"products": matches},
            )
        if intent == "retention_score":
            result = self.tools.retention_score(RetentionScoreRequest(customer_id="verified-context-required"))
            return AssistantResponse(
                intent=intent,
                answer="Retention scoring requires a verified customer context and the project API.",
                refused=False,
                handoff=True,
                tool_result=result,
            )
        results = self.tools.policy_search(PolicySearchRequest(query=request.question, k=1))
        top = results[0]
        if top.score < self.minimum_retrieval_score:
            return AssistantResponse(
                intent=intent,
                answer=(
                    "Je n'ai pas trouvé une source suffisamment fiable. Je transmets la demande au soutien."
                    if french
                    else "I could not find a sufficiently reliable source. I will hand this to support."
                ),
                refused=True,
                handoff=True,
            )
        return AssistantResponse(
            intent=intent,
            answer=top.text,
            refused=False,
            handoff=False,
            citations=[
                Citation(
                    document_id=top.document_id, title=top.title, version=top.version
                )
            ],
            tool_result={"retrieval_score": top.score},
        )


def evaluate_golden(root: Path, output_path: Path) -> dict[str, Any]:
    golden = json.loads((root / "tests" / "assistant_golden_set.json").read_text(encoding="utf-8"))
    retriever = PolicyRetriever(root / "docs" / "corpus")
    assistant = RuleBasedAssistant(AssistantTools(root, retriever))
    records = []
    for case in golden:
        start = time.perf_counter()
        response = assistant.answer(AssistantRequest(question=case["question"]))
        latency_ms = (time.perf_counter() - start) * 1000
        cited_documents = [citation.document_id for citation in response.citations]
        records.append(
            {
                "id": case["id"],
                "category": case["category"],
                "language": case["language"],
                "intent_correct": response.intent == case["expected_intent"],
                "refusal_correct": response.refused == case["should_refuse"],
                "citation_correct": (
                    case.get("expected_document") in cited_documents
                    if case.get("expected_document")
                    else True
                ),
                "grounded": bool(response.citations or response.tool_result or response.refused),
                "latency_ms": latency_ms,
                "estimated_cost_usd": 0.0,
            }
        )
    frame = pd.DataFrame(records)
    summary = {
        "provider": "keyword_router_and_char_ngram_retrieval_baseline",
        "questions": len(frame),
        "tool_choice_accuracy": float(frame["intent_correct"].mean()),
        "refusal_accuracy": float(frame["refusal_correct"].mean()),
        "citation_accuracy_when_expected": float(
            frame.loc[frame["category"].isin(["policy", "french"]), "citation_correct"].mean()
        ),
        "groundedness_rate": float(frame["grounded"].mean()),
        "french_pass_rate": float(
            frame.loc[frame["language"] == "fr", ["intent_correct", "refusal_correct", "citation_correct"]]
            .all(axis=1)
            .mean()
        ),
        "latency_ms_median": float(frame["latency_ms"].median()),
        "latency_ms_p95": float(frame["latency_ms"].quantile(0.95)),
        "estimated_cost_usd": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path.with_suffix(".csv"), index=False)
    output_path.write_text(json.dumps({"summary": summary, "cases": records}, indent=2), encoding="utf-8")
    return summary
