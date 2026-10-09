"""Validate or explicitly launch the bounded D3 SageMaker HPO job."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_REGION = "ca-central-1"
MAX_JOBS_CAP = 12
MAX_PARALLEL_CAP = 2
MAX_RUN_CAP = 1200
MAX_WAIT_CAP = 1800


def load_and_validate(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "region", "bucket", "role_arn", "input_key", "output_prefix", "code_prefix",
        "instance_type", "framework_version", "python_version", "max_jobs",
        "max_parallel_jobs", "max_run_seconds", "max_wait_seconds", "random_seed",
        "base_job_name", "managed_spot",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"Missing configuration keys: {missing}")
    if config["region"] != ALLOWED_REGION:
        raise ValueError("D3 SageMaker region must be ca-central-1")
    if not str(config["input_key"]).startswith("d3/input/"):
        raise ValueError("Input must remain under d3/input/")
    for key in ("output_prefix", "code_prefix"):
        if not str(config[key]).startswith("d3/"):
            raise ValueError(f"{key} must remain under d3/")
    if int(config["max_jobs"]) > MAX_JOBS_CAP:
        raise ValueError(f"max_jobs exceeds safety cap {MAX_JOBS_CAP}")
    if int(config["max_parallel_jobs"]) > MAX_PARALLEL_CAP:
        raise ValueError(f"max_parallel_jobs exceeds safety cap {MAX_PARALLEL_CAP}")
    if int(config["max_run_seconds"]) > MAX_RUN_CAP:
        raise ValueError(f"max_run_seconds exceeds safety cap {MAX_RUN_CAP}")
    if int(config["max_wait_seconds"]) > MAX_WAIT_CAP:
        raise ValueError(f"max_wait_seconds exceeds safety cap {MAX_WAIT_CAP}")
    if bool(config["managed_spot"]) and int(config["max_wait_seconds"]) <= int(config["max_run_seconds"]):
        raise ValueError("Spot max_wait_seconds must exceed max_run_seconds")
    return config


def plan(config: dict[str, Any]) -> dict[str, Any]:
    bucket = config["bucket"]
    return {
        "region": config["region"],
        "role_arn": config["role_arn"],
        "input_uri": f"s3://{bucket}/{config['input_key']}",
        "output_uri": f"s3://{bucket}/{config['output_prefix']}",
        "max_jobs": int(config["max_jobs"]),
        "max_parallel_jobs": int(config["max_parallel_jobs"]),
        "instance_type": config["instance_type"],
        "managed_spot": bool(config["managed_spot"]),
        "max_run_seconds_per_job": int(config["max_run_seconds"]),
        "max_wait_seconds_per_job": int(config["max_wait_seconds"]),
        "objective": "maximize validation:pr_auc",
        "protected_test_uploaded_or_used": False,
    }


def launch(config: dict[str, Any]) -> str:
    from sagemaker.inputs import TrainingInput
    from sagemaker.parameter import CategoricalParameter, IntegerParameter
    from sagemaker.sklearn.estimator import SKLearn
    from sagemaker.tuner import HyperparameterTuner

    here = Path(__file__).resolve().parent
    bucket = config["bucket"]
    estimator = SKLearn(
        entry_point="train.py",
        source_dir=str(here),
        role=config["role_arn"],
        instance_count=1,
        instance_type=config["instance_type"],
        framework_version=config["framework_version"],
        py_version=config["python_version"],
        output_path=f"s3://{bucket}/{config['output_prefix']}",
        code_location=f"s3://{bucket}/{config['code_prefix']}",
        hyperparameters={"data-file": Path(config["input_key"]).name, "random-state": config["random_seed"]},
        use_spot_instances=bool(config["managed_spot"]),
        max_run=int(config["max_run_seconds"]),
        max_wait=int(config["max_wait_seconds"]),
        base_job_name=config["base_job_name"],
    )
    tuner = HyperparameterTuner(
        estimator,
        objective_metric_name="validation:pr_auc",
        hyperparameter_ranges={
            "n-estimators": IntegerParameter(100, 400),
            "max-depth": IntegerParameter(4, 24),
            "min-samples-split": IntegerParameter(2, 30),
            "min-samples-leaf": IntegerParameter(1, 20),
            "max-features": CategoricalParameter(["sqrt", "log2", "0.5", "0.8"]),
            "class-weight": CategoricalParameter(["none", "balanced"]),
        },
        metric_definitions=[{"Name": "validation:pr_auc", "Regex": r"validation:pr_auc=([0-9.]+)"}],
        objective_type="Maximize",
        max_jobs=int(config["max_jobs"]),
        max_parallel_jobs=int(config["max_parallel_jobs"]),
        strategy="Bayesian",
        early_stopping_type="Auto",
        base_tuning_job_name=config["base_job_name"],
    )
    tuner.fit(
        {"training": TrainingInput(f"s3://{bucket}/{config['input_key']}", content_type="application/x-parquet")},
        wait=False,
        logs=False,
    )
    return tuner.latest_tuning_job.job_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args()
    config = load_and_validate(args.config)
    output = plan(config)
    output["external_calls_made"] = bool(args.launch)
    if args.launch:
        output["tuning_job_name"] = launch(config)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
