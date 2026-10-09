"""Compare retention models using an 80/20 customer split of cleaned transactions.

The cleaned transaction rows are converted to point-in-time customer snapshots before
splitting. A customer can appear in only one partition. This supplementary study
includes all configured snapshot dates, including the date previously reserved for
the D3 temporal test; it does not alter the frozen D3 model or its original result.

Run: python -m boreal_marche.modeling.random_split_competition --root . --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from boreal_marche.data.ingest import sha256_file
from boreal_marche.features.customer_snapshots import build_all_snapshots
from boreal_marche.modeling.screen import feature_columns, metrics, preprocessing


def _partition(frame: pd.DataFrame, test_fraction: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=seed)
    left, right = next(splitter.split(frame, frame["target_return_90d"], frame["customer_id"]))
    training, testing = frame.iloc[left], frame.iloc[right]
    if set(training["customer_id"]) & set(testing["customer_id"]):
        raise AssertionError("A customer appeared in both partitions")
    return training, testing


def _candidates(seed: int, positive_weight: float) -> dict[str, Any]:
    # These are training-only extras. Keep partition helpers importable in the
    # lightweight runtime and CI environments that do not install them.
    from catboost import CatBoostClassifier
    from lightgbm import LGBMClassifier
    from xgboost import XGBClassifier

    return {
        "logistic_regression": LogisticRegression(
            class_weight="balanced", max_iter=2000, random_state=seed
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=250, min_samples_leaf=10, class_weight="balanced",
            n_jobs=4, random_state=seed,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=250, min_samples_leaf=10, class_weight="balanced",
            n_jobs=4, random_state=seed,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=250, learning_rate=0.05, class_weight="balanced", random_state=seed
        ),
        "xgboost": XGBClassifier(
            n_estimators=250, max_depth=5, learning_rate=0.05, subsample=0.8,
            colsample_bytree=0.8, scale_pos_weight=positive_weight, tree_method="hist",
            eval_metric="logloss", n_jobs=4, random_state=seed,
        ),
        "catboost": CatBoostClassifier(
            iterations=250, depth=6, learning_rate=0.05, loss_function="Logloss",
            auto_class_weights="Balanced", random_seed=seed, thread_count=4,
            verbose=False, allow_writing_files=False,
        ),
        "lightgbm": LGBMClassifier(
            n_estimators=250, learning_rate=0.05, num_leaves=31,
            min_child_samples=30, class_weight="balanced", n_jobs=4,
            verbosity=-1, random_state=seed,
        ),
    }


def run_competition(root: Path, *, seed: int = 42) -> dict[str, Any]:
    config = json.loads((root / "configs/modeling.json").read_text(encoding="utf-8"))
    source = root / "data/processed/transactions_clean.parquet"
    transactions = pd.read_parquet(source)
    snapshots = build_all_snapshots(transactions, config)
    numeric, categorical = feature_columns(snapshots)
    columns = numeric + categorical

    development, holdout = _partition(snapshots, 0.20, seed)
    fitting, validation = _partition(development, 0.20, seed + 1)
    if set(holdout["customer_id"]) & (
        set(fitting["customer_id"]) | set(validation["customer_id"])
    ):
        raise AssertionError("The 20% test partition was reused during model selection")
    positive_weight = float(
        (fitting["target_return_90d"] == 0).sum()
        / (fitting["target_return_90d"] == 1).sum()
    )

    validation_results: list[dict[str, Any]] = []
    winner_name = ""
    winner_score = -1.0
    winner_pipeline: Pipeline | None = None
    for name, estimator in _candidates(seed, positive_weight).items():
        started = perf_counter()
        pipeline = Pipeline(
            [("preprocess", preprocessing(numeric, categorical)), ("model", estimator)]
        )
        pipeline.fit(fitting[columns], fitting["target_return_90d"])
        probability = pipeline.predict_proba(validation[columns])[:, 1]
        result = {
            "model": name,
            "validation_metrics": metrics(validation["target_return_90d"], probability),
            "fit_and_validation_seconds": perf_counter() - started,
            "estimator_parameters": {
                key: None if isinstance(value, float) and not math.isfinite(value) else value
                for key, value in estimator.get_params().items()
            },
        }
        validation_results.append(result)
        score = result["validation_metrics"]["pr_auc"]
        if score > winner_score:
            winner_name, winner_score, winner_pipeline = name, score, pipeline

    assert winner_pipeline is not None
    # The validation partition is disjoint from fitting and calibrates the selected
    # fitted model. Model choice used this partition too; the outer test stays untouched.
    selected = CalibratedClassifierCV(FrozenEstimator(winner_pipeline), method="sigmoid")
    selected.fit(validation[columns], validation["target_return_90d"])
    test_probability = selected.predict_proba(holdout[columns])[:, 1]
    temporal_meta = json.loads(
        (root / "artifacts/retention_model_meta.json").read_text(encoding="utf-8")
    )
    threshold = float(temporal_meta["selected_threshold"]["threshold"])

    artifact = root / "artifacts/retention_model_random_80_20.joblib"
    report_path = root / "reports/d4/retention_random_80_20.json"
    metadata_path = root / "artifacts/retention_model_random_80_20_meta.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected, artifact)
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "purpose": "supplementary_full_cleaned_data_80_20_model_competition",
        "source_path": str(source.relative_to(root)).replace("\\", "/"),
        "source_sha256": sha256_file(source),
        "cleaned_transaction_rows": len(transactions),
        "snapshot_rows": len(snapshots),
        "snapshot_cutoffs": [str(item["date"]) for item in config["cutoffs"]],
        "observation_days": int(config["observation_days"]),
        "label_days": int(config["label_days"]),
        "prior_d3_temporal_test_date_included": True,
        "prior_d3_result_unchanged": True,
        "split_method": "customer-grouped random 80/20; no customer appears on both sides",
        "random_state": seed,
        "internal_validation_random_state": seed + 1,
        "development_rows": len(development),
        "test_rows": len(holdout),
        "test_row_fraction": len(holdout) / len(snapshots),
        "development_customers": development["customer_id"].nunique(),
        "test_customers": holdout["customer_id"].nunique(),
        "fit_rows": len(fitting),
        "validation_rows": len(validation),
        "customer_overlap": 0,
        "test_positive_rate": float(holdout["target_return_90d"].mean()),
        "selection_metric": "validation_pr_auc",
        "candidate_results": sorted(
            validation_results, key=lambda row: row["validation_metrics"]["pr_auc"], reverse=True
        ),
        "selected_model": winner_name,
        "calibration": "sigmoid on internal validation partition",
        "test_metrics": metrics(holdout["target_return_90d"], test_probability),
        "comparison_threshold": threshold,
        "comparison_threshold_source": "temporal model; illustrative only",
        "comparison_selection_rate": float((test_probability <= threshold).mean()),
        "features": columns,
        "artifact_path": str(artifact.relative_to(root)).replace("\\", "/"),
        "artifact_sha256": sha256_file(artifact),
        "limitations": [
            "The 790,960 transaction lines become customer snapshot examples before the split.",
            "Randomly mixing dates does not estimate forward-time performance.",
            (
                "The former D3 temporal test date participates in this separate experiment; "
                "its result cannot be treated as an untouched holdout for this new comparison."
            ),
            (
                "Model selection and calibration use the same internal validation partition; "
                "the outer 20% test is evaluated once after selection."
            ),
        ],
    }
    serialized = json.dumps(report, indent=2, default=str, allow_nan=False)
    report_path.write_text(serialized, encoding="utf-8")
    metadata_path.write_text(serialized, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(run_competition(args.root.resolve(), seed=args.seed), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
