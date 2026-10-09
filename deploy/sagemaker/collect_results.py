"""Collect reproducible SageMaker HPO metrics and timing evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd


def iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--region", default="ca-central-1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.region != "ca-central-1":
        raise SystemExit("D3 evidence must be collected from ca-central-1")
    client = boto3.client("sagemaker", region_name=args.region)
    tuning = client.describe_hyper_parameter_tuning_job(HyperParameterTuningJobName=args.job_name)
    rows = []
    token = None
    while True:
        request = {"HyperParameterTuningJobName": args.job_name, "MaxResults": 100}
        if token:
            request["NextToken"] = token
        response = client.list_training_jobs_for_hyper_parameter_tuning_job(**request)
        for summary in response["TrainingJobSummaries"]:
            detail = client.describe_training_job(TrainingJobName=summary["TrainingJobName"])
            objective = detail.get("FinalMetricDataList", [])
            objective_value = next((x["Value"] for x in objective if x["MetricName"] == "validation:pr_auc"), None)
            rows.append(
                {
                    "training_job_name": detail["TrainingJobName"],
                    "status": detail["TrainingJobStatus"],
                    "objective_pr_auc": objective_value,
                    "training_time_seconds": detail.get("TrainingTimeInSeconds"),
                    "billable_time_seconds": detail.get("BillableTimeInSeconds"),
                    "instance_type": detail["ResourceConfig"]["InstanceType"],
                    "training_start": iso(detail.get("TrainingStartTime")),
                    "training_end": iso(detail.get("TrainingEndTime")),
                    **{f"hp_{key}": value for key, value in detail.get("HyperParameters", {}).items()},
                }
            )
        token = response.get("NextToken")
        if not token:
            break
    args.output.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows).sort_values("objective_pr_auc", ascending=False)
    frame.to_csv(args.output / "hpo_trials.csv", index=False)
    summary = {
        "job_name": args.job_name,
        "region": args.region,
        "status": tuning["HyperParameterTuningJobStatus"],
        "strategy": tuning["HyperParameterTuningJobConfig"]["Strategy"],
        "trial_count": len(frame),
        "best_training_job": tuning.get("BestTrainingJob"),
        "total_training_seconds": float(frame["training_time_seconds"].fillna(0).sum()),
        "total_billable_seconds": float(frame["billable_time_seconds"].fillna(0).sum()),
        "actual_cost_usd": None,
        "actual_cost_source": "Populate from AWS Billing/Cost Explorer when available; do not infer.",
    }
    (args.output / "hpo_job_summary.json").write_text(json.dumps(summary, indent=2, default=iso), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=iso))


if __name__ == "__main__":
    main()
