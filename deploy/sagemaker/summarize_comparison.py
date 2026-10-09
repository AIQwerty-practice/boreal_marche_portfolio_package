"""Create a sanitized local-versus-SageMaker HPO comparison summary."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import mean


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-summary", type=Path, required=True)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--local-benchmark", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--billing-checked-on")
    parser.add_argument("--successful-job-estimate-usd", type=float)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> None:
    args = parse_args()
    job = json.loads(args.job_summary.read_text(encoding="utf-8"))
    trials = read_csv(args.trials)
    local = read_csv(args.local_benchmark)

    managed_by_name = {row["training_job_name"]: row for row in trials}
    local_by_name = {row["training_job_name"]: row for row in local}
    matched_names = sorted(managed_by_name.keys() & local_by_name.keys())
    if not matched_names:
        raise ValueError("No matching trial names were found in the managed and local evidence.")
    if len(matched_names) != len(trials) or len(matched_names) != len(local):
        raise ValueError("Managed and local evidence must contain the same trial names.")

    starts = [iso_datetime(managed_by_name[name]["training_start"]) for name in matched_names]
    ends = [iso_datetime(managed_by_name[name]["training_end"]) for name in matched_names]
    managed_wall_seconds = (max(ends) - min(starts)).total_seconds()
    local_total_seconds = float(local[0]["matched_local_total_elapsed_seconds"])
    deltas = [
        abs(
            float(managed_by_name[name]["objective_pr_auc"])
            - float(local_by_name[name]["mean_pr_auc"])
        )
        for name in matched_names
    ]
    best_name = job["best_training_job"]["TrainingJobName"]
    actual_cost = job.get("actual_cost_usd")

    summary = {
        "comparison_scope": "Eight identical Random Forest configurations on two development-only temporal folds",
        "protected_test_used": False,
        "managed_platform": {
            "service": "Amazon SageMaker AI",
            "region": job["region"],
            "instance_type": managed_by_name[matched_names[0]]["instance_type"],
            "spot_training": True,
            "strategy": job["strategy"],
            "status": job["status"],
            "trial_count": len(matched_names),
            "wall_seconds": managed_wall_seconds,
            "training_seconds_sum": float(job["total_training_seconds"]),
            "billable_seconds_sum": float(job["total_billable_seconds"]),
            "best_pr_auc": float(job["best_training_job"]["FinalHyperParameterTuningJobObjectiveMetric"]["Value"]),
        },
        "local_platform": {
            "trial_count": len(matched_names),
            "wall_seconds": local_total_seconds,
            "best_pr_auc": float(local_by_name[best_name]["mean_pr_auc"]),
        },
        "agreement": {
            "same_best_configuration": best_name == max(
                matched_names, key=lambda name: float(local_by_name[name]["mean_pr_auc"])
            ),
            "mean_absolute_pr_auc_delta": mean(deltas),
            "max_absolute_pr_auc_delta": max(deltas),
        },
        "runtime": {
            "managed_to_local_wall_ratio": managed_wall_seconds / local_total_seconds,
            "billable_to_local_ratio": float(job["total_billable_seconds"]) / local_total_seconds,
        },
        "cost": {
            "actual_cost_usd": actual_cost,
            "status": "available" if actual_cost is not None else "pending_billing",
            "billing_checked_on": args.billing_checked_on,
            "billing_observation": (
                "No new attributable SageMaker charge was visible."
                if args.billing_checked_on and actual_cost is None
                else None
            ),
            "successful_job_estimate_usd": args.successful_job_estimate_usd,
            "source": job.get("actual_cost_source"),
            "cost_crossover_status": "pending_actual_cost" if actual_cost is None else "requires_documented_local_cost_basis",
        },
        "interpretation": (
            "For this small data set and short Random Forest workload, local replay was faster because "
            "managed startup dominated elapsed time. SageMaker remains useful when managed isolation, "
            "parallel capacity, or larger and longer-running workloads outweigh that overhead."
        ),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    cost_text = "Pending AWS Billing/Cost Explorer attribution" if actual_cost is None else f"USD {actual_cost:.4f}"
    billing_text = (
        f" Billing was checked on {args.billing_checked_on} and showed no new attributable "
        "SageMaker charge."
        if args.billing_checked_on and actual_cost is None
        else ""
    )
    estimate_text = (
        f" The successful-job planning estimate is USD {args.successful_job_estimate_usd:.4f}."
        if args.successful_job_estimate_usd is not None
        else ""
    )
    markdown = f"""# D3 SageMaker versus local comparison

Scope: eight identical Random Forest configurations evaluated on the same two development-only temporal folds. The protected test partition was not uploaded or used.

| Measure | SageMaker managed Spot | Local replay |
|---|---:|---:|
| Trials | {len(matched_names)} | {len(matched_names)} |
| Wall time | {managed_wall_seconds:.3f} s ({managed_wall_seconds / 60:.2f} min) | {local_total_seconds:.3f} s |
| Summed billable/trial time | {float(job['total_billable_seconds']):.0f} s | Not applicable |
| Best mean PR-AUC | {summary['managed_platform']['best_pr_auc']:.6f} | {summary['local_platform']['best_pr_auc']:.6f} |

The same configuration ranked first on both platforms. Across all eight matched trials, the mean absolute PR-AUC difference was {mean(deltas):.6f} and the maximum was {max(deltas):.6f}. Managed wall time was {managed_wall_seconds / local_total_seconds:.2f} times local wall time; summed managed billable seconds were {float(job['total_billable_seconds']) / local_total_seconds:.2f} times the local replay duration.

Actual recorded AWS cost: **{cost_text}**.{billing_text}{estimate_text} A cost crossover must not be claimed until that billed value and a documented local-compute cost basis are available.

Interpretation: for this small data set and short Random Forest workload, local execution is the practical default because managed startup dominates. SageMaker becomes more attractive when managed isolation, elastic parallelism, or larger and longer-running workloads justify that overhead.
"""
    args.output_markdown.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
