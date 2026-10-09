from __future__ import annotations

import json
from pathlib import Path

import pytest

from boreal_marche.assistant.core import (
    AssistantRequest,
    AssistantTools,
    PolicyRetriever,
    RuleBasedAssistant,
    evaluate_golden,
)

ROOT = Path.cwd().resolve()
CASES = json.loads(Path(__file__).with_name("assistant_adversarial_set.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def assistant() -> RuleBasedAssistant:
    retriever = PolicyRetriever(ROOT / "docs" / "corpus")
    return RuleBasedAssistant(AssistantTools(ROOT, retriever))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_adversarial_case(case: dict[str, object], assistant: RuleBasedAssistant) -> None:
    response = assistant.answer(AssistantRequest(question=str(case["question"])))
    assert response.intent == case["expected_intent"]
    assert response.refused is case["should_refuse"]


def test_frozen_golden_set_remains_unchanged() -> None:
    golden = json.loads((ROOT / "tests" / "assistant_golden_set.json").read_text(encoding="utf-8"))
    assert len(golden) == 40


def test_frozen_golden_evaluation_meets_gate(tmp_path: Path) -> None:
    summary = evaluate_golden(ROOT, tmp_path / "assistant_evaluation.json")
    assert summary["questions"] == 40
    assert summary["tool_choice_accuracy"] >= 0.95
    assert summary["refusal_accuracy"] == 1.0
    assert summary["citation_accuracy_when_expected"] == 1.0
    assert summary["groundedness_rate"] == 1.0
    assert summary["french_pass_rate"] == 1.0
