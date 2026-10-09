"""Replay SageMaker trial configurations locally for a matched time comparison."""

from __future__ import annotations

import argparse
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


def load_train_module():
    path = Path(__file__).with_name("train.py")
    spec = importlib.util.spec_from_file_location("boreal_sagemaker_train", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def value(row, name, default):
    key = f"hp_{name}"
    return row[key] if key in row and pd.notna(row[key]) else default


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    module = load_train_module()
    frame = pd.read_parquet(args.data)
    trials = pd.read_csv(args.trials)
    results = []
    overall = time.perf_counter()
    for _, row in trials.iterrows():
        settings = SimpleNamespace(
            n_estimators=int(float(value(row, "n-estimators", 200))),
            max_depth=int(float(value(row, "max-depth", 12))),
            min_samples_split=int(float(value(row, "min-samples-split", 10))),
            min_samples_leaf=int(float(value(row, "min-samples-leaf", 5))),
            max_features=str(value(row, "max-features", "sqrt")).strip('"'),
            class_weight=str(value(row, "class-weight", "none")).strip('"'),
            random_state=int(float(value(row, "random-state", 42))),
        )
        result = module.evaluate_trial(frame, settings)
        results.append({"training_job_name": row["training_job_name"], **result})
    output = pd.DataFrame(results)
    output["matched_local_total_elapsed_seconds"] = time.perf_counter() - overall
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(output.to_string(index=False))


if __name__ == "__main__":
    main()
