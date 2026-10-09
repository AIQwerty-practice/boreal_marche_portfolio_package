"""Tune, calibrate, and select a scenario-based retention campaign threshold."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import mlflow
import numpy as np
import optuna
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline

from boreal_marche.data.ingest import sha256_file
from boreal_marche.modeling.screen import feature_columns, metrics, preprocessing, temporal_fold

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def model_for_trial(name: str, trial: optuna.Trial, seed: int) -> Any:
    common = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 400, step=50),
        "max_depth": trial.suggest_int("max_depth", 4, 24),
        "min_samples_split": trial.suggest_int("min_samples_split", 2, 30),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 20),
        "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", 0.5, 0.8]),
        "class_weight": trial.suggest_categorical("class_weight", [None, "balanced"]),
        "n_jobs": -1,
        "random_state": seed,
    }
    if name == "extra_trees":
        return ExtraTreesClassifier(**common)
    return RandomForestClassifier(**common, bootstrap=True)


def model_from_params(name: str, params: dict[str, Any], seed: int) -> Any:
    options = {**params, "n_jobs": -1, "random_state": seed}
    return ExtraTreesClassifier(**options) if name == "extra_trees" else RandomForestClassifier(**options)


def tuning_objective(
    trial: optuna.Trial,
    *,
    name: str,
    snapshots: pd.DataFrame,
    columns: list[str],
    transformer: Any,
    seed: int,
) -> float:
    scores = []
    estimator = model_for_trial(name, trial, seed)
    with mlflow.start_run(run_name=f"{name}-trial-{trial.number}", nested=True):
        mlflow.log_params({"model": name, **trial.params})
        for step, cutoff in enumerate(
            (pd.Timestamp("2011-03-01"), pd.Timestamp("2011-06-01"))
        ):
            train, valid = temporal_fold(snapshots, cutoff)
            pipe = Pipeline(
                [
                    ("preprocess", clone(transformer)),
                    ("model", clone(estimator)),
                ]
            )
            pipe.fit(train[columns], train["target_return_90d"])
            probability = pipe.predict_proba(valid[columns])[:, 1]
            score = average_precision_score(valid["target_return_90d"], probability)
            scores.append(score)
            mlflow.log_metric(f"fold_{step + 1}_pr_auc", score)
            trial.report(float(np.mean(scores)), step)
            if trial.should_prune():
                mlflow.set_tag("trial_status", "pruned")
                raise optuna.TrialPruned()
        value = float(np.mean(scores))
        mlflow.log_metric("mean_temporal_pr_auc", value)
        mlflow.set_tag("trial_status", "complete")
    return value


def tune_models(snapshots: pd.DataFrame, config: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    numeric, categorical = feature_columns(snapshots)
    columns = numeric + categorical
    transformer = preprocessing(numeric, categorical)
    tracking = (Path.cwd() / config["mlflow_tracking_uri"]).resolve()
    tracking.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking.as_posix()}")
    mlflow.set_experiment(config["mlflow_experiment"])
    best: dict[str, Any] = {}
    trials = []
    for name in ("extra_trees", "random_forest"):
        study = optuna.create_study(
            direction="maximize",
            study_name=f"{name}-temporal-pr-auc",
            sampler=optuna.samplers.TPESampler(seed=int(config["random_state"])),
            pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=0),
        )
        with mlflow.start_run(run_name=f"{name}-study"):
            study.optimize(
                lambda trial, name=name: tuning_objective(
                    trial,
                    name=name,
                    snapshots=snapshots,
                    columns=columns,
                    transformer=transformer,
                    seed=int(config["random_state"]),
                ),
                n_trials=int(config["n_trials_per_model"]),
            )
            mlflow.log_params({"model": name, "trial_count": len(study.trials)})
            mlflow.log_metric("best_mean_temporal_pr_auc", study.best_value)
        best[name] = {"value": study.best_value, "params": study.best_params}
        for trial in study.trials:
            trials.append({"model": name, "trial": trial.number, "pr_auc": trial.value, **trial.params})
    return best, pd.DataFrame(trials)


def fit_and_calibrate(
    snapshots: pd.DataFrame, best: dict[str, Any], config: dict[str, Any]
) -> tuple[Any, str, dict[str, Any], np.ndarray, np.ndarray, pd.Series]:
    numeric, categorical = feature_columns(snapshots)
    columns = numeric + categorical
    transformer = preprocessing(numeric, categorical)
    seed = int(config["random_state"])
    base_train = snapshots.loc[snapshots["snapshot_cutoff"] == pd.Timestamp("2010-12-01")]
    calibration = snapshots.loc[snapshots["snapshot_cutoff"] == pd.Timestamp("2011-03-01")]
    validation = snapshots.loc[snapshots["snapshot_cutoff"] == pd.Timestamp("2011-06-01")]
    evaluations: dict[str, Any] = {}
    candidates = []
    for name, result in best.items():
        base = Pipeline(
            [("preprocess", clone(transformer)), ("model", model_from_params(name, result["params"], seed))]
        )
        base.fit(base_train[columns], base_train["target_return_90d"])
        raw_probability = base.predict_proba(validation[columns])[:, 1]
        evaluations[f"{name}_uncalibrated"] = metrics(validation["target_return_90d"], raw_probability)
        for method in ("sigmoid", "isotonic"):
            calibrated = CalibratedClassifierCV(FrozenEstimator(base), method=method)
            calibrated.fit(calibration[columns], calibration["target_return_90d"])
            probability = calibrated.predict_proba(validation[columns])[:, 1]
            key = f"{name}_{method}"
            evaluations[key] = metrics(validation["target_return_90d"], probability)
            pr_auc_loss = evaluations[f"{name}_uncalibrated"]["pr_auc"] - evaluations[key]["pr_auc"]
            if pr_auc_loss <= 0.005:
                candidates.append(
                    (evaluations[key]["brier_score"], key, calibrated, raw_probability, probability)
                )
    _, selected_key, selected_model, selected_raw, selected_probability = min(
        candidates, key=lambda item: item[0]
    )
    return (
        selected_model,
        selected_key,
        evaluations,
        selected_raw,
        selected_probability,
        validation["target_return_90d"],
    )


def profit_curve(probability: np.ndarray, assumptions: dict[str, float]) -> pd.DataFrame:
    thresholds = np.linspace(0, 1, 201)
    margin = assumptions["gross_margin_per_incremental_purchase"]
    incentive = assumptions["incentive_cost_per_purchase"]
    contact = assumptions["contact_cost"]
    recovery = assumptions["recovery_fraction_of_non_returners"]
    rows = []
    for threshold in thresholds:
        selected = probability <= threshold
        uplift = recovery * (1 - probability[selected])
        incremental = uplift * margin - (probability[selected] + uplift) * incentive - contact
        rows.append(
            {
                "threshold": threshold,
                "customers_contacted": int(selected.sum()),
                "estimated_incremental_profit": float(incremental.sum()),
            }
        )
    return pd.DataFrame(rows)


def render_figures(y: pd.Series, raw: np.ndarray, calibrated: np.ndarray, curve: pd.DataFrame, config: dict[str, Any], root: Path) -> None:
    calibration_path = root / config["calibration_figure"]
    profit_path = root / config["profit_figure"]
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(8.0, 5.5))
    for label, probability in (("Uncalibrated", raw), ("Selected calibration", calibrated)):
        observed, predicted = calibration_curve(y, probability, n_bins=10, strategy="quantile")
        axis.plot(predicted, observed, marker="o", label=label)
    axis.plot([0, 1], [0, 1], linestyle="--", color="#666666", label="Perfect")
    axis.set(xlabel="Mean predicted probability", ylabel="Observed return rate", title="Calibration on the June 2011 validation snapshot")
    axis.legend()
    axis.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(calibration_path, dpi=180); plt.close(fig)
    fig, axis = plt.subplots(figsize=(8.0, 5.5))
    axis.plot(curve["threshold"], curve["estimated_incremental_profit"], color="#176B87")
    best_row = curve.loc[curve["estimated_incremental_profit"].idxmax()]
    axis.axvline(best_row["threshold"], linestyle="--", color="#C44E52")
    axis.set(
        xlabel="Maximum predicted return probability contacted",
        ylabel="Scenario-estimated incremental profit",
        title="Profit threshold under declared campaign assumptions",
    )
    axis.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(profit_path, dpi=180); plt.close(fig)


def run(root: Path, config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    snapshots = pd.read_parquet(root / config["input_parquet"])
    screening = snapshots.loc[snapshots["snapshot_role"] != "test"].copy()
    best, trials = tune_models(screening, config)
    selected_model, selected_key, evaluations, raw_probability, probability, y_valid = fit_and_calibrate(
        screening, best, config
    )
    curve = profit_curve(probability, config["campaign_assumptions"])
    best_profit = curve.loc[curve["estimated_incremental_profit"].idxmax()].to_dict()
    render_figures(y_valid, raw_probability, probability, curve, config, root)
    artifact = root / config["artifact_path"]
    metadata_path = root / config["metadata_path"]
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected_model, artifact)
    trials_path = root / config["trials_csv"]
    trials_path.parent.mkdir(parents=True, exist_ok=True)
    trials.to_csv(trials_path, index=False)
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "trial_count": len(trials),
        "best_tuning_results": best,
        "selected_calibrated_model": selected_key,
        "validation_metrics": evaluations[selected_key],
        "all_calibration_metrics": evaluations,
        "profit_policy": "Contact customers at or below the selected return-probability threshold.",
        "profit_assumptions_are_scenario_not_causal_estimates": True,
        "campaign_assumptions": config["campaign_assumptions"],
        "selected_threshold": best_profit,
        "protected_test_evaluated": False,
        "artifact_sha256": sha256_file(artifact),
    }
    metadata = {**report, "artifact_path": config["artifact_path"], "feature_source_sha256": sha256_file(root / config["input_parquet"])}
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report_path = root / config["output_report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Tuning, Calibration, and Campaign Threshold", "", f"Trials completed: {len(trials)}", "", f"Selected calibrated pipeline: `{selected_key}`", "", f"Validation PR-AUC: {evaluations[selected_key]['pr_auc']:.4f}", f"Validation Brier score: {evaluations[selected_key]['brier_score']:.4f}", "", "## Scenario threshold", "", f"Contact customers with predicted return probability at or below **{best_profit['threshold']:.3f}**.", f"Scenario-estimated incremental profit: **{best_profit['estimated_incremental_profit']:.2f}** across **{int(best_profit['customers_contacted'])}** validation customers.", "", "This is a decision scenario based on declared assumptions, not an observed causal treatment effect. The protected test set remains untouched.", ""]
    (root / config["output_markdown"]).write_text("\n".join(lines), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/tuning.json"))
    args = parser.parse_args(argv)
    root = args.root.resolve(); config_path = args.config if args.config.is_absolute() else root / args.config
    print(json.dumps(run(root, config_path), indent=2)); return 0


if __name__ == "__main__":
    sys.exit(main())
