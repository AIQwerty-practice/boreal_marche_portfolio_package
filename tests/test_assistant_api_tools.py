from __future__ import annotations

import json

import httpx
from pydantic import SecretStr

from boreal_marche.assistant.api_tools import ApiToolConfig, AuthenticatedApiTools
from boreal_marche.assistant.core import (
    ProductLookupRequest,
    RecommendationRequest,
    RetentionScoreRequest,
)


class FakeRetriever:
    def search(self, request):
        return []


def test_authenticated_api_tools_send_bearer_token_and_validate_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tool-secret"
        if request.url.path.endswith("/recommendation"):
            assert json.loads(request.content) == {"basket": ["85048"], "k": 2}
            return httpx.Response(200, json={"source": "rule", "recommendations": []})
        return httpx.Response(
            200,
            json={"found": True, "stock_code": "85048", "description": "TEST PRODUCT"},
        )

    tools = AuthenticatedApiTools(
        ApiToolConfig(
            base_url="https://api.internal",
            bearer_token=SecretStr("tool-secret"),
        ),
        FakeRetriever(),
        transport=httpx.MockTransport(handler),
    )
    assert tools.recommendation(RecommendationRequest(basket=["85048"], k=2))["source"] == "rule"
    product = tools.product_lookup(ProductLookupRequest(stock_code="85048"))
    assert product.found is True


def test_retention_tool_remains_fail_closed_without_customer_feature_store() -> None:
    tools = AuthenticatedApiTools(
        ApiToolConfig(base_url="https://api.internal", bearer_token=SecretStr("tool-secret")),
        FakeRetriever(),
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    result = tools.retention_score(RetentionScoreRequest(customer_id="verified-context-required"))
    assert result["status"] == "requires_verified_customer_feature_context"
