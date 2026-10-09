"""Authenticated HTTP tool client for deployed Head C orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr

from boreal_marche.assistant.core import (
    PolicyRetriever,
    PolicySearchRequest,
    PolicySearchResult,
    ProductLookupRequest,
    ProductLookupResult,
    RecommendationRequest,
    RetentionScoreRequest,
)


@dataclass(frozen=True)
class ApiToolConfig:
    base_url: str
    bearer_token: SecretStr
    timeout_seconds: float = 15.0


class AuthenticatedApiTools:
    """Uses authenticated HTTP for online tools and local retrieval for the policy corpus."""

    def __init__(
        self,
        config: ApiToolConfig,
        retriever: PolicyRetriever,
        transport: httpx.BaseTransport | None = None,
    ):
        self.retriever = retriever
        self.client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            transport=transport,
            headers={"Authorization": f"Bearer {config.bearer_token.get_secret_value()}"},
        )

    def policy_search(self, request: PolicySearchRequest) -> list[PolicySearchResult]:
        return self.retriever.search(request)

    def recommendation(self, request: RecommendationRequest) -> dict[str, Any]:
        response = self.client.post(
            "/internal/tools/recommendation",
            json={"basket": request.basket, "k": request.k},
        )
        response.raise_for_status()
        return response.json()

    def product_lookup(self, request: ProductLookupRequest) -> ProductLookupResult:
        response = self.client.get(f"/internal/tools/product/{request.stock_code}")
        response.raise_for_status()
        return ProductLookupResult.model_validate(response.json())

    def search_products(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        from boreal_marche.assistant.core import product_search_terms

        terms = product_search_terms(query)
        if not terms:
            return []
        response = self.client.get("/catalog", params={"q": terms[-1], "limit": limit})
        response.raise_for_status()
        return [
            {"stock_code": item["stock_code"], "description": item["description"]}
            for item in response.json()["items"]
        ]

    def retention_score(self, request: RetentionScoreRequest) -> dict[str, Any]:
        return {
            "status": "requires_verified_customer_feature_context",
            "customer_id": request.customer_id,
            "message": "Authenticated customer-to-feature lookup is not implemented.",
        }
