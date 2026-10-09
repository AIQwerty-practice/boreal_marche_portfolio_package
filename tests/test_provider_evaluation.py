from __future__ import annotations

from pathlib import Path

from boreal_marche.assistant.provider_evaluation import (
    evaluate_provider,
    load_case_sets,
    parse_provider_decision,
)
from boreal_marche.assistant.providers import ProviderResponse


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, text: str):
        self.text = text

    def generate(self, request):
        return ProviderResponse(
            provider=self.name,
            model=self.model,
            text=self.text,
            latency_ms=10,
            input_tokens=20,
            output_tokens=5,
            estimated_cost_usd=0.001,
        )


def test_case_loader_combines_frozen_and_adversarial_sets() -> None:
    cases = load_case_sets(Path.cwd())
    assert len(cases) == 54
    assert sum(case["suite"] == "golden" for case in cases) == 40
    assert sum(case["suite"] == "adversarial" for case in cases) == 14


def test_structured_decision_accepts_json_fence() -> None:
    decision = parse_provider_decision(
        '```json\n{"intent":"privacy_refusal","refused":true}\n```'
    )
    assert decision.intent == "privacy_refusal"


def test_malformed_provider_output_is_counted_as_failure() -> None:
    cases = [
        {
            "suite": "adversarial",
            "id": "x1",
            "question": "route",
            "expected_intent": "policy_search",
            "should_refuse": False,
        }
    ]
    summary, frame = evaluate_provider(FakeProvider("not-json"), cases, "system")
    assert summary["error_rate"] == 1.0
    assert summary["tool_choice_accuracy"] == 0.0
    assert frame.loc[0, "status"] == "error"
    assert frame.loc[0, "error_type"] == "ValidationError"


def test_inconsistent_refusal_is_counted_as_failure() -> None:
    cases = [
        {
            "suite": "golden",
            "id": "x2",
            "question": "route",
            "expected_intent": "recommendation",
            "should_refuse": False,
        }
    ]
    output = '{"intent":"recommendation","refused":true}'
    summary, _ = evaluate_provider(FakeProvider(output), cases, "system")
    assert summary["error_rate"] == 1.0
