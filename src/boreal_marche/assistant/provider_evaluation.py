"""Robust, auditable evaluation of Head C routing providers."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Literal

import httpx
import pandas as pd
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from boreal_marche.assistant.providers import AssistantProvider, ProviderRequest

Intent = Literal[
    "policy_search",
    "recommendation",
    "product_lookup",
    "retention_score",
    "privacy_refusal",
    "out_of_scope",
]


class ProviderDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    refused: bool

    @model_validator(mode="after")
    def refusal_matches_intent(self) -> ProviderDecision:
        expected = self.intent in {"privacy_refusal", "out_of_scope"}
        if self.refused is not expected:
            raise ValueError("refused must be true exactly for refusal intents")
        return self


def parse_provider_decision(text: str) -> ProviderDecision:
    candidate = text.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    elif candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
    return ProviderDecision.model_validate_json(candidate)


def load_case_sets(root: Path) -> list[dict[str, Any]]:
    paths = {
        "golden": root / "tests" / "assistant_golden_set.json",
        "adversarial": root / "tests" / "assistant_adversarial_set.json",
    }
    cases: list[dict[str, Any]] = []
    for suite, path in paths.items():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        for case in loaded:
            cases.append({"suite": suite, **case})
    return cases


def evaluate_provider(
    provider: AssistantProvider,
    cases: list[dict[str, Any]],
    system_prompt: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    records: list[dict[str, Any]] = []
    for case in cases:
        base = {
            "suite": case["suite"],
            "id": case["id"],
            "expected_intent": case["expected_intent"],
            "expected_refusal": case["should_refuse"],
        }
        try:
            result = provider.generate(
                ProviderRequest(system_prompt=system_prompt, user_prompt=case["question"])
            )
            decision = parse_provider_decision(result.text)
            records.append(
                {
                    **base,
                    "status": "success",
                    "error_type": None,
                    "predicted_intent": decision.intent,
                    "predicted_refusal": decision.refused,
                    "intent_correct": decision.intent == case["expected_intent"],
                    "refusal_correct": decision.refused == case["should_refuse"],
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": result.estimated_cost_usd,
                }
            )
        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValidationError,
            ValueError,
        ) as error:
            records.append(
                {
                    **base,
                    "status": "error",
                    "error_type": type(error).__name__,
                    "predicted_intent": None,
                    "predicted_refusal": None,
                    "intent_correct": False,
                    "refusal_correct": False,
                    "latency_ms": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "estimated_cost_usd": None,
                }
            )
    frame = pd.DataFrame(records)
    successful_latency = frame.loc[frame["status"] == "success", "latency_ms"].tolist()
    summary: dict[str, Any] = {
        "provider": provider.name,
        "model": provider.model,
        "questions": len(frame),
        "successful_responses": int(frame["status"].eq("success").sum()),
        "error_rate": float(frame["status"].eq("error").mean()),
        "tool_choice_accuracy": float(frame["intent_correct"].mean()),
        "refusal_accuracy": float(frame["refusal_correct"].mean()),
        "latency_ms_median": (
            float(statistics.median(successful_latency)) if successful_latency else None
        ),
        "latency_ms_p95": (
            float(pd.Series(successful_latency).quantile(0.95)) if successful_latency else None
        ),
        "input_tokens": int(pd.to_numeric(frame["input_tokens"], errors="coerce").sum()),
        "output_tokens": int(pd.to_numeric(frame["output_tokens"], errors="coerce").sum()),
        "estimated_cost_usd": float(
            pd.to_numeric(frame["estimated_cost_usd"], errors="coerce").sum()
        ),
        "suite_metrics": {
            suite: {
                "questions": len(group),
                "tool_choice_accuracy": float(group["intent_correct"].mean()),
                "refusal_accuracy": float(group["refusal_correct"].mean()),
                "error_rate": float(group["status"].eq("error").mean()),
            }
            for suite, group in frame.groupby("suite", sort=True)
        },
    }
    return summary, frame
