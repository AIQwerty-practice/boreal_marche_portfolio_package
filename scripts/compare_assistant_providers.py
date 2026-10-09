"""Compare configured Head C providers on golden and adversarial routing cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from boreal_marche.assistant.provider_evaluation import evaluate_provider, load_case_sets
from boreal_marche.assistant.providers import configured_providers
from boreal_marche.assistant.routing_prompt import SYSTEM_PROMPT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--provider", choices=("openai", "hosted", "ollama", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    providers = configured_providers()
    selected = (
        providers
        if args.provider == "all"
        else {name: provider for name, provider in providers.items() if name == args.provider}
    )
    cases = load_case_sets(root)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "configured": sorted(providers),
                    "selected": sorted(selected),
                    "case_count": len(cases),
                    "suites": {name: sum(c["suite"] == name for c in cases) for name in ("golden", "adversarial")},
                    "external_calls_made": False,
                },
                indent=2,
            )
        )
        return 0
    if not selected:
        raise SystemExit("No requested provider is configured; no external call was made.")

    output_directory = (
        args.output.resolve()
        if args.output
        else root / "reports" / "d3" / "provider_comparison"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    for name, provider in selected.items():
        summary, frame = evaluate_provider(provider, cases, SYSTEM_PROMPT)
        frame.to_csv(output_directory / f"{name}.csv", index=False)
        (output_directory / f"{name}.json").write_text(
            json.dumps({"summary": summary, "cases": frame.to_dict(orient="records")}, indent=2),
            encoding="utf-8",
        )
        summaries.append(summary)
    (output_directory / "summary.json").write_text(
        json.dumps(summaries, indent=2), encoding="utf-8"
    )
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
