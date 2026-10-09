"""Compare class-imbalance strategies without touching protected test data."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib
import mlflow
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from boreal_marche.data.ingest import sha256_file
from boreal_marche.modeling.screen import feature_columns, metrics, preprocessing, temporal_fold
from boreal_marche.modeling.tune import profit_curve

matplotlib.use("Agg")
from matplotlib import pyplot as plt

STRATEGIES = ("none", "balanced_class_weight", "random_undersampling", "random_oversampling")


def resample_training(
    frame: pd.DataFrame, strategy: str, target: str, seed: int
) -> pd.DataFrame:
    """Resample a training frame only; callers must enforce split membership."""
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown balancing strategy: {strategy}")
    if strategy in {"none", "balanced_class_weight"}:
        return frame.copy()
    counts = frame[target].value_counts()
    if len(counts) != 2:
        raise ValueError("Balancing requires a binary target with both classes")
    majority_label = counts.idxmax()
    minority_label = counts.idxmin()
    majority = frame.loc[frame[target] == majority_label]
    minority = frame.loc[frame[target] == minority_label]
    if strategy == "random_undersampling":
        sampled_majority = majority.sample(n=len(minority), replace=False, random_state=seed)
        result = pd.concat([sampled_majority, minority], ignore_index=True)
    else:
        sampled_minority = minority.sample(n=len(majority), replace=True, random_state=seed)
        result = pd.concat([majority, sampled_minority], ignore_index=True)
    return result.sample(frac=1, random_state=seed).reset_index(drop=True)


def assert_training_only(train: pd.DataFrame, validation: pd.DataFrame) -> None:
    if (train["snapshot_role"] == "test").any() or (validation["snapshot_role"] == "test").any():
        raise AssertionError("Protected test rows cannot enter balancing experiments")
    if train["snapshot_cutoff"].max() >= validation["snapshot_cutoff"].min():
        raise AssertionError("All resampled rows must precede the validation cutoff")


def estimator(config: dict[str, Any], strategy: str) -> RandomForestClassifier:
    params = dict(config["model_params"])
    params["class_weight"] = "balanced" if strategy == "balanced_class_weight" else None
    params["random_state"] = int(config["random_state"])
    params["n_jobs"] = -1
    return RandomForestClassifier(**params)


def evaluate_strategy(
    snapshots: pd.DataFrame, strategy: str, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    numeric, categorical = feature_columns(snapshots)
    columns = numeric + categorical
    rows = []
    curves = []
    for fold_number, fold in enumerate(config["folds"], start=1):
        cutoff = pd.Timestamp(fold["validation_cutoff"])
        train, validation = temporal_fold(snapshots, cutoff)
        assert_training_only(train, validation)
        sampled = resample_training(
            train, strategy, "target_return_90d", int(config["random_state"]) + fold_number
        )
        assert_training_only(sampled, validation)
        pipeline = Pipeline(
            [
                ("preprocess", preprocessing(numeric, categorical)),
                ("model", estimator(config, strategy)),
            ]
        )
        calibrated = CalibratedClassifierCV(
            pipeline,
            method="sigmoid",
            cv=int(config["calibration_cv"]),
            ensemble=False,
        )
        started = time.perf_counter()
        calibrated.fit(sampled[columns], sampled["target_return_90d"])
        fit_seconds = time.perf_counter() - started
        probability = calibrated.predict_proba(validation[columns])[:, 1]
        fold_metrics = metrics(validation["target_return_90d"], probability)
        curve = profit_curve(probability, config["campaign_assumptions"])
        best_profit = curve.loc[curve["estimated_incremental_profit"].idxmax()]
        record = {
            "strategy": strategy,
            "fold": fold["name"],
            "validation_cutoff": fold["validation_cutoff"],
            "original_training_rows": len(train),
            "sampled_training_rows": len(sampled),
            "sampled_positive_rate": float(sampled["target_return_90d"].mean()),
            "validation_rows": len(validation),
            "fit_seconds": fit_seconds,
            **fold_metrics,
            "profit_threshold": float(best_profit["threshold"]),
            "estimated_incremental_profit": float(best_profit["estimated_incremental_profit"]),
        }
        rows.append(record)
        curve = curve.copy()
        curve["strategy"] = strategy
        curve["fold"] = fold["name"]
        curves.append(curve)
        for name, value in record.items():
            if isinstance(value, (int, float)):
                mlflow.log_metric(f"{fold['name']}_{name}", float(value))
    return rows, pd.concat(curves, ignore_index=True)


def aggregate(folds: pd.DataFrame) -> pd.DataFrame:
    measures = [
        "pr_auc",
        "roc_auc",
        "brier_score",
        "recall_at_top_decile",
        "estimated_incremental_profit",
        "fit_seconds",
        "sampled_training_rows",
    ]
    summary = folds.groupby("strategy", as_index=False)[measures].mean()
    summary = summary.rename(columns={name: f"mean_{name}" for name in measures})
    summary["pr_auc_fold_std"] = folds.groupby("strategy")["pr_auc"].std().to_numpy()
    return summary.sort_values(
        ["mean_pr_auc", "mean_brier_score", "mean_estimated_incremental_profit"],
        ascending=[False, True, False],
    ).reset_index(drop=True)


def select_strategy(summary: pd.DataFrame, pr_tolerance: float, brier_tolerance: float) -> str:
    """Apply discrimination and calibration guards, then maximize scenario profit."""
    best_pr_auc = float(summary["mean_pr_auc"].max())
    baseline_brier = float(
        summary.loc[summary["strategy"] == "none", "mean_brier_score"].iloc[0]
    )
    eligible = summary.loc[
        (summary["mean_pr_auc"] >= best_pr_auc - pr_tolerance)
        & (summary["mean_brier_score"] <= baseline_brier + brier_tolerance)
    ]
    if eligible.empty:
        raise ValueError("No balancing strategy passed the PR-AUC and Brier guards")
    return str(
        eligible.sort_values(
            ["mean_estimated_incremental_profit", "mean_recall_at_top_decile"],
            ascending=[False, False],
        ).iloc[0]["strategy"]
    )


def render_figure(summary: pd.DataFrame, path: Path) -> None:
    ordered = summary.sort_values("mean_pr_auc")
    labels = ordered["strategy"].str.replace("_", " ")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5))
    axes[0].barh(labels, ordered["mean_pr_auc"], color="#176B87")
    axes[0].set(xlabel="Mean temporal-fold PR-AUC", xlim=(0.65, 0.77), title="Ranking quality")
    axes[0].grid(axis="x", alpha=0.25)
    axes[1].barh(labels, ordered["mean_brier_score"], color="#64CCC5")
    axes[1].set(xlabel="Mean Brier score (lower is better)", title="Probability quality")
    axes[1].grid(axis="x", alpha=0.25)
    fig.suptitle("Head A balancing strategies use identical temporal validation")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run(root: Path, config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = root / config["input_parquet"]
    snapshots = pd.read_parquet(source)
    protected_rows = int((snapshots["snapshot_role"] == "test").sum())
    development = snapshots.loc[snapshots["snapshot_role"] != "test"].copy()
    if protected_rows == 0 or (development["snapshot_role"] == "test").any():
        raise AssertionError("Protected test split was not isolated")
    tracking = (root / config["mlflow_tracking_uri"]).resolve()
    mlflow.set_tracking_uri(f"sqlite:///{tracking.as_posix()}")
    mlflow.set_experiment(config["mlflow_experiment"])
    fold_rows = []
    all_curves = []
    run_ids = {}
    for strategy in STRATEGIES:
        with mlflow.start_run(run_name=f"balancing-{strategy}") as active_run:
            run_ids[strategy] = active_run.info.run_id
            mlflow.log_params(
                {
                    "strategy": strategy,
                    "calibration": "sigmoid",
                    "calibration_cv": config["calibration_cv"],
                    "random_state": config["random_state"],
                    **{f"model_{key}": value for key, value in config["model_params"].items()},
                }
            )
            mlflow.set_tags(
                {
                    "head": "A-prediction",
                    "evaluation": "development-temporal-folds-only",
                    "protected_test_evaluated": "false",
                    "feature_source_sha256": sha256_file(source),
                }
            )
            rows, curves = evaluate_strategy(development, strategy, config)
            fold_rows.extend(rows)
            all_curves.append(curves)
            strategy_frame = pd.DataFrame(rows)
            for metric in (
                "pr_auc",
                "roc_auc",
                "brier_score",
                "recall_at_top_decile",
                "estimated_incremental_profit",
                "fit_seconds",
            ):
                mlflow.log_metric(f"mean_{metric}", float(strategy_frame[metric].mean()))
    folds = pd.DataFrame(fold_rows)
    summary = aggregate(folds)
    selected = select_strategy(
        summary,
        float(config["pr_auc_tolerance"]),
        float(config["brier_tolerance_vs_none"]),
    )
    client = mlflow.MlflowClient()
    for strategy, run_id in run_ids.items():
        client.set_tag(run_id, "selection_status", "selected" if strategy == selected else "rejected")
    fold_path = root / config["fold_results_csv"]
    summary_path = root / config["summary_csv"]
    curves_path = root / config["profit_curves_csv"]
    report_path = root / config["report_json"]
    markdown_path = root / config["report_markdown"]
    figure_path = root / config["figure_path"]
    fold_path.parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(fold_path, index=False)
    summary.to_csv(summary_path, index=False)
    pd.concat(all_curves, ignore_index=True).to_csv(curves_path, index=False)
    render_figure(summary, figure_path)
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "strategies": list(STRATEGIES),
        "selection_rule": (
            "Require PR-AUC within configured tolerance of the best and Brier no worse than "
            "the unbalanced baseline plus tolerance; then maximize scenario profit."
        ),
        "pr_auc_tolerance": config["pr_auc_tolerance"],
        "brier_tolerance_vs_none": config["brier_tolerance_vs_none"],
        "selected_strategy": selected,
        "summary": summary.to_dict(orient="records"),
        "protected_test_rows_isolated": protected_rows,
        "protected_test_evaluated": False,
        "resampling_scope": "training folds only",
        "campaign_assumptions_are_scenario_not_causal": True,
        "feature_source_sha256": sha256_file(source),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    best = summary.loc[summary["strategy"] == selected].iloc[0]
    markdown = f"""# Head A Class-Balancing Comparison

Four strategies were compared using identical expanding temporal folds and the tuned Random Forest configuration. Sampling occurred inside training folds only. Validation rows were never resampled, and all {protected_rows:,} protected-test rows remained isolated.

## Selection

Selected development strategy: **{selected.replace('_', ' ')}**.

- Mean PR-AUC: {best['mean_pr_auc']:.4f}
- Mean Brier score: {best['mean_brier_score']:.4f}
- Mean recall at top decile: {best['mean_recall_at_top_decile']:.4f}
- Mean scenario-estimated profit: {best['mean_estimated_incremental_profit']:.2f}

The selection guard requires PR-AUC within {config['pr_auc_tolerance']:.3f} of the best result and Brier score no more than {config['brier_tolerance_vs_none']:.3f} worse than no balancing; eligible strategies are then ranked by scenario profit. This prevents a negligible ranking gain from overriding calibration and business consequences. Profit is based on declared assumptions and is not a causal estimate. This experiment does not authorize final protected-test evaluation or replacement of the promoted artifact.

See `balancing_summary.csv`, `balancing_fold_results.csv`, and `figures/balancing_comparison.png` for complete evidence.
"""
    markdown_path.write_text(markdown, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/balancing.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    print(json.dumps(run(root, config_path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
