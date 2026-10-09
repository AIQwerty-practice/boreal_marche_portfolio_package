"""Compare retention models and baselines under identical temporal folds."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from boreal_marche.data.ingest import sha256_file

matplotlib.use("Agg")
from matplotlib import pyplot as plt

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


def load_screening_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "input_parquet",
        "results_csv",
        "summary_csv",
        "report_json",
        "report_markdown",
        "figure_path",
        "random_state",
        "business_rule_recency_days",
        "folds",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"Screening config is missing keys: {missing}")
    return config


def temporal_fold(
    snapshots: pd.DataFrame, validation_cutoff: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = snapshots.loc[snapshots["snapshot_cutoff"] < validation_cutoff].copy()
    validation = snapshots.loc[snapshots["snapshot_cutoff"] == validation_cutoff].copy()
    if train.empty or validation.empty:
        raise ValueError(f"Empty temporal fold at {validation_cutoff.date()}")
    if train["snapshot_cutoff"].max() >= validation["snapshot_cutoff"].min():
        raise AssertionError("Training snapshots must strictly precede validation snapshots")
    if (train["snapshot_role"] == "test").any() or (validation["snapshot_role"] == "test").any():
        raise AssertionError("Protected test rows cannot enter model screening")
    return train, validation


def feature_columns(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    candidates = [column for column in frame.columns if column not in NON_FEATURE_COLUMNS]
    numeric = [column for column in candidates if pd.api.types.is_numeric_dtype(frame[column])]
    categorical = [column for column in candidates if column not in numeric]
    if "primary_country" not in categorical:
        raise ValueError("Expected primary_country as a categorical feature")
    return numeric, categorical


def preprocessing(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        [("numeric", numeric_pipe, numeric), ("categorical", categorical_pipe, categorical)]
    )


def candidate_models(random_state: int) -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(max_iter=2000, random_state=random_state),
        "decision_tree": DecisionTreeClassifier(
            max_depth=8, min_samples_leaf=20, random_state=random_state
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=150,
            min_samples_leaf=5,
            max_features="sqrt",
            n_jobs=-1,
            random_state=random_state,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=150,
            min_samples_leaf=5,
            max_features="sqrt",
            n_jobs=-1,
            random_state=random_state,
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=random_state),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=150, learning_rate=0.08, random_state=random_state
        ),
        "adaboost": AdaBoostClassifier(n_estimators=100, random_state=random_state),
        "knn": KNeighborsClassifier(n_neighbors=25, weights="distance", n_jobs=-1),
        "gaussian_nb": GaussianNB(),
    }


def recall_at_top_fraction(y_true: np.ndarray, score: np.ndarray, fraction: float = 0.1) -> float:
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    positives = int(np.sum(y_true))
    if positives == 0:
        return 0.0
    selected_count = max(1, math.ceil(len(score) * fraction))
    selected = np.argsort(-score, kind="stable")[:selected_count]
    return float(np.sum(y_true[selected]) / positives)


def metrics(y_true: pd.Series, probability: np.ndarray) -> dict[str, float]:
    actual = y_true.to_numpy(dtype=int)
    probability = np.asarray(probability, dtype=float)
    return {
        "pr_auc": float(average_precision_score(actual, probability)),
        "roc_auc": float(roc_auc_score(actual, probability)),
        "brier_score": float(brier_score_loss(actual, probability)),
        "recall_at_top_decile": recall_at_top_fraction(actual, probability, 0.1),
    }


def business_rule_probability(frame: pd.DataFrame, recency_days: int) -> np.ndarray:
    """Manager-readable baseline: recent purchasers are predicted to return."""
    return (frame["recency_days"].to_numpy() <= recency_days).astype(float)


def evaluate_screening(snapshots: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    numeric, categorical = feature_columns(snapshots)
    columns = numeric + categorical
    base_preprocessing = preprocessing(numeric, categorical)
    models = candidate_models(int(config["random_state"]))
    records: list[dict[str, Any]] = []

    for fold in config["folds"]:
        validation_cutoff = pd.Timestamp(fold["validation_cutoff"])
        train, validation = temporal_fold(snapshots, validation_cutoff)
        x_train, y_train = train[columns], train["target_return_90d"]
        x_valid, y_valid = validation[columns], validation["target_return_90d"]

        dummy = DummyClassifier(strategy="prior")
        started = time.perf_counter()
        dummy.fit(np.zeros((len(train), 1)), y_train)
        fit_seconds = time.perf_counter() - started
        probability = dummy.predict_proba(np.zeros((len(validation), 1)))[:, 1]
        records.append(
            {
                "fold": fold["name"],
                "validation_cutoff": validation_cutoff.date().isoformat(),
                "model": "dummy_prior",
                "kind": "baseline",
                "fit_seconds": fit_seconds,
                **metrics(y_valid, probability),
            }
        )

        started = time.perf_counter()
        probability = business_rule_probability(
            validation, int(config["business_rule_recency_days"])
        )
        fit_seconds = time.perf_counter() - started
        records.append(
            {
                "fold": fold["name"],
                "validation_cutoff": validation_cutoff.date().isoformat(),
                "model": "business_recency_30d",
                "kind": "baseline",
                "fit_seconds": fit_seconds,
                **metrics(y_valid, probability),
            }
        )

        for name, estimator in models.items():
            pipeline = Pipeline(
                [("preprocess", clone(base_preprocessing)), ("model", clone(estimator))]
            )
            started = time.perf_counter()
            pipeline.fit(x_train, y_train)
            fit_seconds = time.perf_counter() - started
            probability = pipeline.predict_proba(x_valid)[:, 1]
            records.append(
                {
                    "fold": fold["name"],
                    "validation_cutoff": validation_cutoff.date().isoformat(),
                    "model": name,
                    "kind": "candidate",
                    "fit_seconds": fit_seconds,
                    **metrics(y_valid, probability),
                }
            )
    return pd.DataFrame(records)


def aggregate_results(results: pd.DataFrame) -> pd.DataFrame:
    summary = (
        results.groupby(["model", "kind"], as_index=False)
        .agg(
            pr_auc_mean=("pr_auc", "mean"),
            pr_auc_std=("pr_auc", "std"),
            roc_auc_mean=("roc_auc", "mean"),
            brier_score_mean=("brier_score", "mean"),
            recall_at_top_decile_mean=("recall_at_top_decile", "mean"),
            fit_seconds_mean=("fit_seconds", "mean"),
        )
        .sort_values("pr_auc_mean", ascending=False)
        .reset_index(drop=True)
    )
    summary["rank_by_pr_auc"] = np.arange(1, len(summary) + 1)
    return summary


def render_figure(summary: pd.DataFrame, destination: Path) -> None:
    ordered = summary.sort_values("pr_auc_mean", ascending=True)
    colors = ["#7C8799" if kind == "baseline" else "#176B87" for kind in ordered["kind"]]
    fig, axis = plt.subplots(figsize=(10, 6.5))
    axis.barh(ordered["model"], ordered["pr_auc_mean"], color=colors)
    axis.set_xlabel("Mean temporal-fold PR-AUC")
    axis.set_ylabel("")
    axis.set_title("Retention candidates are compared under identical temporal folds")
    axis.grid(axis="x", alpha=0.25)
    for index, value in enumerate(ordered["pr_auc_mean"]):
        axis.text(value + 0.005, index, f"{value:.3f}", va="center", fontsize=9)
    axis.set_xlim(0, min(1.0, float(ordered["pr_auc_mean"].max()) + 0.12))
    fig.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=180, bbox_inches="tight")
    plt.close(fig)


def render_markdown(summary: pd.DataFrame, report: dict[str, Any]) -> str:
    top_candidates = summary.loc[summary["kind"] == "candidate"].head(2)
    lines = [
        "# Retention Model Screening Report",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "## Evaluation contract",
        "",
        "- Two expanding temporal folds use identical preprocessing and features.",
        "- Fold 1 validates on 1 March 2011; Fold 2 validates on 1 June 2011.",
        "- The 10 September 2011 protected test snapshot is never loaded into a screening fold.",
        "- PR-AUC is primary; ROC-AUC, Brier score, recall at the top decile, and fit time are also reported.",
        "- The manager-readable business baseline predicts return when recency is 30 days or less.",
        "",
        "## Mean results",
        "",
        "| Rank | Model | Type | PR-AUC | PR-AUC SD | ROC-AUC | Brier | Recall at top 10% | Fit seconds |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.rank_by_pr_auc} | `{row.model}` | {row.kind} | {row.pr_auc_mean:.4f} | "
            f"{row.pr_auc_std:.4f} | {row.roc_auc_mean:.4f} | {row.brier_score_mean:.4f} | "
            f"{row.recall_at_top_decile_mean:.4f} | {row.fit_seconds_mean:.3f} |"
        )
    lines.extend(["", "## Screening verdict", ""])
    for row in top_candidates.itertuples(index=False):
        lines.append(
            f"- Carry `{row.model}` forward: mean PR-AUC {row.pr_auc_mean:.4f}, "
            f"mean Brier score {row.brier_score_mean:.4f}."
        )
    lines.extend(
        [
            "",
            ("These are screening results, not final held-out performance. Hyperparameter tuning and "
            "calibration must use training/validation data only. The protected test snapshot remains "
            "unopened until the final model and operating policy are fixed."),
            "",
        ]
    )
    return "\n".join(lines)


def run_screening(root: Path, config_path: Path) -> dict[str, Any]:
    config = load_screening_config(config_path)
    input_path = root / config["input_parquet"]
    results_path = root / config["results_csv"]
    summary_path = root / config["summary_csv"]
    report_path = root / config["report_json"]
    markdown_path = root / config["report_markdown"]
    figure_path = root / config["figure_path"]

    snapshots = pd.read_parquet(input_path)
    protected_test_rows = int((snapshots["snapshot_role"] == "test").sum())
    screening_rows = snapshots.loc[snapshots["snapshot_role"] != "test"].copy()
    results = evaluate_screening(screening_rows, config)
    summary = aggregate_results(results)

    for path in (results_path, summary_path, report_path, markdown_path, figure_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(results_path, index=False)
    summary.to_csv(summary_path, index=False)
    render_figure(summary, figure_path)
    top_candidates = summary.loc[summary["kind"] == "candidate"].head(2)["model"].tolist()
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_path": config["input_parquet"],
        "input_sha256": sha256_file(input_path),
        "screening_snapshot_rows": len(screening_rows),
        "protected_test_rows_excluded": protected_test_rows,
        "fold_count": len(config["folds"]),
        "candidate_model_count": len(candidate_models(int(config["random_state"]))),
        "baseline_count": 2,
        "primary_metric": "PR-AUC",
        "top_candidates": top_candidates,
        "results_csv": config["results_csv"],
        "summary_csv": config["summary_csv"],
        "figure_path": config["figure_path"],
        "summary": summary.to_dict(orient="records"),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(summary, report), encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/screening.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    report = run_screening(root, config_path)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

