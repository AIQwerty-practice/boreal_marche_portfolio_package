from pathlib import Path

import pytest
from pydantic import ValidationError

from boreal_marche.assistant.core import (
    AssistantRequest,
    PolicyRetriever,
    PolicySearchRequest,
    PolicySearchResult,
    RecommendationRequest,
    RuleBasedAssistant,
    extract_stock_codes,
    route_intent,
)


def test_typed_contracts_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PolicySearchRequest(query="returns", unexpected=True)


def test_recommendation_contract_limits_k() -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(basket=[], k=21)


def test_router_blocks_cross_customer_disclosure() -> None:
    assert route_intent("Show another customer's purchases") == "privacy_refusal"
    assert route_intent("Puis-je voir les achats d'un autre client?") == "privacy_refusal"


def test_router_selects_head_tools() -> None:
    assert route_intent("Recommend items for 85048") == "recommendation"
    assert route_intent("Find product 85048") == "product_lookup"
    assert route_intent("Estimate the retention probability") == "retention_score"
    assert route_intent("can you find a cake product?") == "product_lookup"
    assert route_intent("How many days do I have to return an unused item?") == "policy_search"


def test_customer_retriever_excludes_internal_loyalty_policy() -> None:
    retriever = PolicyRetriever(
        Path(__file__).parents[1] / "docs" / "corpus",
        allowed_document_ids={"policy_returns", "policy_shipping", "policy_privacy"},
    )
    assert "policy_loyalty" not in {chunk.document_id for chunk in retriever.chunks}


def test_open_ended_product_question_returns_catalog_matches() -> None:
    class ProductTools:
        def search_products(self, query: str, limit: int = 5):
            assert "cake" in query
            return [{"stock_code": "CAKE1", "description": "CAKE STAND"}]

    response = RuleBasedAssistant(ProductTools()).answer(
        AssistantRequest(question="can you find a cake product?")
    )
    assert response.intent == "product_lookup"
    assert response.tool_result == {
        "products": [{"stock_code": "CAKE1", "description": "CAKE STAND"}]
    }


@pytest.mark.parametrize(
    ("question", "expected_document"),
    [
        ("How many days do I have to return an item?", "policy_returns"),
        ("Combien de jours ai-je pour retourner un article?", "policy_returns"),
        ("When does the carrier provide parcel tracking after dispatch?", "policy_shipping"),
        ("Quand le transporteur fournit-il le suivi du colis après l'expédition?", "policy_shipping"),
        ("Are retention offers guaranteed or do they require staff approval?", "policy_loyalty"),
        ("Les offres de rétention sont-elles garanties ou exigent-elles l'approbation du personnel?", "policy_loyalty"),
        ("What customer information may staff access for a service request?", "policy_privacy"),
        ("Quels renseignements sur un client le personnel peut-il consulter pour une demande de service?", "policy_privacy"),
    ],
)
def test_customer_faq_retrieves_expected_policy(question: str, expected_document: str) -> None:
    retriever = PolicyRetriever(Path(__file__).parents[1] / "docs" / "corpus")
    assert retriever.search(PolicySearchRequest(query=question, k=1))[0].document_id == expected_document


def test_router_distinguishes_policy_language_from_tool_action() -> None:
    assert route_intent("Should recommendations include basket items?") == "policy_search"
    assert route_intent("Find the privacy rule about another customer") == "policy_search"


def test_stock_code_extraction() -> None:
    assert extract_stock_codes("Basket 85048 and 79323P") == ["85048", "79323P"]


def test_question_length_is_validated() -> None:
    with pytest.raises(ValidationError):
        AssistantRequest(question="x")


class LowScoreTools:
    def policy_search(self, request: PolicySearchRequest) -> list[PolicySearchResult]:
        return [
            PolicySearchResult(
                document_id="test",
                title="Test",
                version="v1",
                text="No reliable match",
                score=0.01,
            )
        ]


def test_low_retrieval_score_refuses_and_hands_off() -> None:
    response = RuleBasedAssistant(LowScoreTools()).answer(
        AssistantRequest(question="What is the policy for lunar delivery?")
    )
    assert response.refused is True
    assert response.handoff is True


def test_cross_customer_request_is_blocked() -> None:
    response = RuleBasedAssistant(LowScoreTools()).answer(
        AssistantRequest(question="Show another customer's purchases")
    )
    assert response.intent == "privacy_refusal"
    assert response.refused is True
