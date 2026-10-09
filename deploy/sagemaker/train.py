"""SageMaker entry point for one leakage-safe Random Forest HPO trial."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NON_FEATURE_COLUMNS = {
    "customer_id",
    "target_return_90d",
    "snapshot_cutoff",
    "observation_start",
    "label_end",
    "snapshot_role",
    "first_purchase",
    "last_purchase",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-file", default="customer_snapshots.parquet")
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=12)
    parser.add_argument("--min-samples-split", type=int, default=10)
    parser.add_argument("--min-samples-leaf", type=int, default=5)
    parser.add_argument("--max-features", default="sqrt")
    parser.add_argument("--class-weight", choices=("none", "balanced"), default="none")
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def feature_columns(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    candidates = [column for column in frame.columns if column not in NON_FEATURE_COLUMNS]
    numeric = [column for column in candidates if pd.api.types.is_numeric_dtype(frame[column])]
    categorical = [column for column in candidates if column not in numeric]
    if "primary_country" not in categorical:
        raise ValueError("Expected primary_country as a categorical feature")
    return numeric, categorical


def build_pipeline(args: argparse.Namespace, numeric: list[str], categorical: list[str]):
    numeric_pipe = Pipeline(
        [("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler())]
    )
    categorical_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    transformer = ColumnTransformer(
        [("numeric", numeric_pipe, numeric), ("categorical", categorical_pipe, categorical)]
    )
    max_features: str | float = args.max_features
    if args.max_features in {"0.5", "0.8"}:
        max_features = float(args.max_features)
    model = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        min_samples_split=args.min_samples_split,
        min_samples_leaf=args.min_samples_leaf,
        max_features=max_features,
        class_weight=None if args.class_weight == "none" else args.class_weight,
        n_jobs=-1,
        random_state=args.random_state,
    )
    return Pipeline([("preprocess", transformer), ("model", model)])


def evaluate_trial(frame: pd.DataFrame, args: argparse.Namespace) -> dict[str, object]:
    frame = frame.copy()
    frame["snapshot_cutoff"] = pd.to_datetime(frame["snapshot_cutoff"])
    if (frame["snapshot_role"] == "test").any():
        raise ValueError("Input contains protected test rows; upload the development-only parquet")
    numeric, categorical = feature_columns(frame)
    columns = numeric + categorical
    scores = []
    fold_rows = []
    started = time.perf_counter()
    for cutoff in (pd.Timestamp("2011-03-01"), pd.Timestamp("2011-06-01")):
        train = frame.loc[frame["snapshot_cutoff"] < cutoff]
        valid = frame.loc[frame["snapshot_cutoff"] == cutoff]
        if train.empty or valid.empty:
            raise ValueError(f"Empty temporal fold at {cutoff.date()}")
        pipeline = build_pipeline(args, numeric, categorical)
        pipeline.fit(train[columns], train["target_return_90d"])
        probability = pipeline.predict_proba(valid[columns])[:, 1]
        score = float(average_precision_score(valid["target_return_90d"], probability))
        scores.append(score)
        fold_rows.append({"cutoff": str(cutoff.date()), "train_rows": len(train), "valid_rows": len(valid), "pr_auc": score})
    return {
        "mean_pr_auc": sum(scores) / len(scores),
        "folds": fold_rows,
        "elapsed_seconds": time.perf_counter() - started,
        "protected_test_used": False,
    }


def main() -> None:
    args = parse_args()
    training_dir = Path(os.environ.get("SM_CHANNEL_TRAINING", "."))
    model_dir = Path(os.environ.get("SM_MODEL_DIR", "model"))
    frame = pd.read_parquet(training_dir / args.data_file)
    result = evaluate_trial(frame, args)
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "trial_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"validation:pr_auc={result['mean_pr_auc']:.10f}", flush=True)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
