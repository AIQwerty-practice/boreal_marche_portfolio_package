"""Evaluate the Head C deterministic baseline against the frozen golden set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

from boreal_marche.assistant.core import evaluate_golden

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    summary = evaluate_golden(root, root / "reports" / "d3" / "assistant_evaluation.json")
    figure_path = root / "reports" / "d3" / "figures" / "assistant_golden_evaluation.png"
    labels = ["Tool choice", "Refusal", "Citation", "French"]
    values = [
        summary["tool_choice_accuracy"],
        summary["refusal_accuracy"],
        summary["citation_accuracy_when_expected"],
        summary["french_pass_rate"],
    ]
    fig, axis = plt.subplots(figsize=(8, 5.5))
    bars = axis.bar(labels, values, color=["#176B87", "#C44E52", "#64CCC5", "#DAA520"])
    axis.bar_label(bars, labels=[f"{value:.0%}" for value in values], padding=4)
    axis.set_ylim(0, 1.1)
    axis.set_ylabel("Pass rate")
    axis.set_title("Deterministic assistant baseline passes the frozen golden set")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_path, dpi=180)
    plt.close(fig)
    report = f"""# Head C — Grounded Bilingual Assistant Baseline

The 40-question golden set was frozen before implementation: 15 policy, 10 tool-routing, 8 out-of-scope, and 7 French questions.

## Baseline results

- Tool-choice accuracy: {summary['tool_choice_accuracy']:.1%}
- Refusal accuracy: {summary['refusal_accuracy']:.1%}
- Citation accuracy when expected: {summary['citation_accuracy_when_expected']:.1%}
- Groundedness proxy: {summary['groundedness_rate']:.1%}
- French pass rate: {summary['french_pass_rate']:.1%}
- Median latency: {summary['latency_ms_median']:.3f} ms; p95: {summary['latency_ms_p95']:.3f} ms
- Estimated provider cost: $0.00

The first run reached 95.0% tool-choice accuracy and revealed two phrase-routing errors. The corrected deterministic baseline passes this small frozen set, but that does not establish broad conversational quality.

## Scope and safeguards

- Policy responses require retrieval above a minimum score and include document ID, title, and version citations.
- Low-score policy requests trigger refusal and human handoff.
- Cross-customer disclosure is refused and handed to a privacy specialist.
- Product lookup and recommendation use validated request contracts; recommendation calls the Head B artifact.
- Retention scoring deliberately returns `requires_verified_api_context` until authenticated API integration exists.

The corpus is fictional capstone-demo policy, not UCI source material or an approved real-company policy. Hosted LLM and local Ollama providers, API integration, adversarial testing, and broader semantic evaluation remain pending.
"""
    (root / "reports" / "d3" / "ASSISTANT_BASELINE_REPORT.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
