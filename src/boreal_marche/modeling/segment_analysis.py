"""Validation-only uncertainty and segment diagnostics for the retention model."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from boreal_marche.modeling.screen import feature_columns, recall_at_top_fraction

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def safe_metrics(y_true: pd.Series, probability: np.ndarray) -> dict[str, float | None]:
    actual = y_true.to_numpy(dtype=int)
    probability = np.asarray(probability, dtype=float)
    has_two_classes = np.unique(actual).size == 2
    return {
        "pr_auc": float(average_precision_score(actual, probability)) if has_two_classes else None,
        "roc_auc": float(roc_auc_score(actual, probability)) if has_two_classes else None,
        "brier_score": float(brier_score_loss(actual, probability)),
        "recall_at_top_decile": recall_at_top_fraction(actual, probability, 0.1),
        "mean_predicted_return": float(probability.mean()),
        "observed_return_rate": float(actual.mean()),
        "calibration_gap": float(probability.mean() - actual.mean()),
    }


def bootstrap_metrics(
    y_true: pd.Series, probability: np.ndarray, iterations: int, seed: int
) -> dict[str, dict[str, float]]:
    actual = y_true.to_numpy(dtype=int)
    probability = np.asarray(probability, dtype=float)
    rng = np.random.default_rng(seed)
    estimates: dict[str, list[float]] = {"pr_auc": [], "roc_auc": [], "brier_score": []}
    for _ in range(iterations):
        sample = rng.integers(0, len(actual), len(actual))
        sampled_y = actual[sample]
        if np.unique(sampled_y).size < 2:
            continue
        sampled_p = probability[sample]
        estimates["pr_auc"].append(float(average_precision_score(sampled_y, sampled_p)))
        estimates["roc_auc"].append(float(roc_auc_score(sampled_y, sampled_p)))
        estimates["brier_score"].append(float(brier_score_loss(sampled_y, sampled_p)))
    return {
        name: {
            "lower_95": float(np.quantile(values, 0.025)),
            "median": float(np.quantile(values, 0.5)),
            "upper_95": float(np.quantile(values, 0.975)),
        }
        for name, values in estimates.items()
    }


def add_segments(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["country_group"] = np.where(
        result["primary_country"].eq("UNITED KINGDOM"), "United Kingdom", "Other countries"
    )
    result["value_segment"] = pd.qcut(
        result["monetary_total"], 3, labels=["Lower value", "Middle value", "Higher value"]
    ).astype(str)
    result["activity_segment"] = pd.qcut(
        result["frequency_orders"].rank(method="first"),
        3,
        labels=["Lower activity", "Middle activity", "Higher activity"],
    ).astype(str)
    return result


def segment_table(
    frame: pd.DataFrame, segment_column: str, threshold: float, minimum_size: int
) -> pd.DataFrame:
    rows = []
    for segment, group in frame.groupby(segment_column, observed=True):
        if len(group) < minimum_size:
            continue
        scores = group["predicted_return_probability"].to_numpy()
        selected = scores <= threshold
        values = safe_metrics(group["target_return_90d"], scores)
        rows.append(
            {
                "segment_dimension": segment_column,
                "segment": str(segment),
                "customers": len(group),
                **values,
                "campaign_selection_rate": float(selected.mean()),
                "observed_nonreturn_rate_selected": (
                    float(1 - group.loc[selected, "target_return_90d"].mean())
                    if selected.any()
                    else None
                ),
            }
        )
    return pd.DataFrame(rows)


def run(root: Path, config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    snapshots = pd.read_parquet(root / config["input_parquet"])
    validation = snapshots.loc[snapshots["snapshot_role"] == "validation"].copy()
    if validation.empty or (validation["snapshot_role"] == "test").any():
        raise AssertionError("Analysis must use validation rows only")
    numeric, categorical = feature_columns(validation)
    model = joblib.load(root / config["artifact_path"])
    validation["predicted_return_probability"] = model.predict_proba(
        validation[numeric + categorical]
    )[:, 1]
    validation = add_segments(validation)
    threshold = float(config["operating_threshold"])
    tables = [
        segment_table(validation, dimension, threshold, int(config["minimum_segment_size"]))
        for dimension in ("country_group", "value_segment", "activity_segment")
    ]
    segments = pd.concat(tables, ignore_index=True)
    uncertainty = bootstrap_metrics(
        validation["target_return_90d"],
        validation["predicted_return_probability"].to_numpy(),
        int(config["bootstrap_iterations"]),
        int(config["random_state"]),
    )
    overall = safe_metrics(
        validation["target_return_90d"], validation["predicted_return_probability"].to_numpy()
    )
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "evaluation_split": "validation",
        "validation_customers": len(validation),
        "protected_test_evaluated": False,
        "overall_metrics": overall,
        "bootstrap_iterations": int(config["bootstrap_iterations"]),
        "bootstrap_95_intervals": uncertainty,
        "operating_threshold": threshold,
        "segment_dimensions": ["country_group", "value_segment", "activity_segment"],
        "fairness_scope": (
            "Performance and allocation diagnostics only. The dataset has no protected "
            "demographic attributes, so demographic fairness cannot be assessed."
        ),
        "country_imbalance": validation["country_group"].value_counts().to_dict(),
    }
    csv_path = root / config["segments_csv"]
    json_path = root / config["report_json"]
    markdown_path = root / config["report_markdown"]
    figure_path = root / config["figure_path"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    segments.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    plot = segments.sort_values(["segment_dimension", "pr_auc"])
    labels = plot["segment_dimension"].str.replace("_", " ") + ": " + plot["segment"]
    colors = plot["segment_dimension"].map(
        {"country_group": "#176B87", "value_segment": "#64CCC5", "activity_segment": "#DAA520"}
    )
    fig, axis = plt.subplots(figsize=(9, 6))
    axis.barh(labels, plot["pr_auc"], color=colors)
    axis.axvline(float(overall["pr_auc"]), color="#C44E52", linestyle="--", label="Overall")
    axis.set(
        xlabel="Validation PR-AUC",
        ylabel="",
        title="Retention ranking performance varies across operational segments",
        xlim=(0, 1),
    )
    axis.grid(axis="x", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(figure_path, dpi=180)
    plt.close(fig)

    pr = uncertainty["pr_auc"]
    brier = uncertainty["brier_score"]
    markdown = f"""# Validation Uncertainty and Segment Diagnostics

Evaluation split: **validation only** ({len(validation):,} customers). The protected test set remains untouched.

## Overall uncertainty

- PR-AUC: {overall['pr_auc']:.4f} (bootstrap 95% interval {pr['lower_95']:.4f}–{pr['upper_95']:.4f})
- ROC-AUC: {overall['roc_auc']:.4f}
- Brier score: {overall['brier_score']:.4f} (bootstrap 95% interval {brier['lower_95']:.4f}–{brier['upper_95']:.4f})
- Bootstrap resamples: {config['bootstrap_iterations']:,}, seeded for reproducibility

## Segment scope and fairness limitation

The audit compares UK versus other-country customers, monetary-value thirds, and activity thirds. These are operational diagnostics. Online Retail II contains no protected demographic attributes, so this work cannot establish demographic fairness. Country is also highly imbalanced; results for the pooled non-UK group can hide country-specific variation.

At the 0.400 operating threshold, the segment table reports campaign selection rates and observed non-return rates among selected customers. These are allocation diagnostics, not treatment-effect or causal-fairness estimates.

See `segment_metrics.csv` for all segment results and `figures/segment_pr_auc.png` for the presentation-ready comparison.
"""
    markdown_path.write_text(markdown, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/segment_analysis.json"))
    args = parser.parse_args()
    report = run(args.root.resolve(), (args.root / args.config).resolve())
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
