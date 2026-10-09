"""Frozen development-baseline comparison; not a production monitoring service."""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

MONITORED_FEATURES = (
    "recency_days",
    "frequency_orders",
    "monetary_total",
    "unique_products",
)
MIN_DEMO_SAMPLES = 100
QUANTILES = (0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0)


def _counts(values: np.ndarray, edges: list[float]) -> np.ndarray:
    return np.histogram(values, bins=np.array([-np.inf, *edges, np.inf]))[0]


def _reference_metric(values: pd.Series | np.ndarray) -> dict[str, Any]:
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna().to_numpy(dtype=float)
    if len(numeric) < MIN_DEMO_SAMPLES or not np.isfinite(numeric).all():
        raise ValueError("Development baseline requires at least 100 finite values")
    quantiles = np.quantile(numeric, QUANTILES)
    edges = np.unique(quantiles[1:-1]).astype(float).tolist()
    counts = _counts(numeric, edges)
    reference_proportions = (counts / len(numeric)).tolist()
    boundaries = [-np.inf, *edges, np.inf]
    representatives = []
    for lower, upper in pairwise(boundaries):
        in_bin = numeric[(numeric >= lower) & (numeric < upper)]
        representatives.append(float(np.median(in_bin)) if len(in_bin) else float(np.median(numeric)))
    return {
        "edges": edges,
        "reference_proportions": reference_proportions,
        "sample_values": representatives,
        "min": float(np.min(numeric)),
        "p25": float(np.quantile(numeric, 0.25)),
        "median": float(np.median(numeric)),
        "p75": float(np.quantile(numeric, 0.75)),
        "max": float(np.max(numeric)),
    }


def build_baseline(development: pd.DataFrame, probabilities: np.ndarray, model_version: str) -> dict[str, Any]:
    if set(development["snapshot_role"]) - {"train", "validation"}:
        raise ValueError("Protected or unknown snapshot roles cannot enter the drift baseline")
    if len(development) != len(probabilities):
        raise ValueError("Predictions must align with development snapshots")
    metrics = {name: _reference_metric(development[name]) for name in MONITORED_FEATURES}
    metrics["return_probability_90d"] = _reference_metric(probabilities)
    return {
        "purpose": "development_only_aggregate_drift_reference",
        "model_version": model_version,
        "development_rows": len(development),
        "snapshot_roles": sorted(set(development["snapshot_role"])),
        "min_demo_samples": MIN_DEMO_SAMPLES,
        "psi_watch": 0.10,
        "psi_high": 0.25,
        "thresholds_are_illustrative": True,
        "score_reference_is_in_sample_not_a_performance_estimate": True,
        "metrics": metrics,
    }


def analyze_batch(
    baseline: dict[str, Any], frame: pd.DataFrame, probabilities: np.ndarray
) -> dict[str, Any]:
    if len(frame) != len(probabilities):
        raise ValueError("Predictions must align with submitted profiles")
    results: list[dict[str, Any]] = []
    for name, reference in baseline["metrics"].items():
        values = probabilities if name == "return_probability_90d" else frame[name]
        numeric = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(numeric).all():
            raise ValueError(f"{name} must contain finite numeric values")
        observed = _counts(numeric, reference["edges"]) / len(numeric)
        expected = np.asarray(reference["reference_proportions"], dtype=float)
        epsilon = 1e-6
        psi = float(np.sum((observed - expected) * np.log((observed + epsilon) / (expected + epsilon))))
        out_of_range = float(np.mean((numeric < reference["min"]) | (numeric > reference["max"])))
        status = "high" if psi >= baseline["psi_high"] else "watch" if psi >= baseline["psi_watch"] else "stable"
        results.append({
            "name": name,
            "psi": round(psi, 4),
            "status": status,
            "out_of_range_rate": round(out_of_range, 4),
        })
    enough = len(frame) >= baseline["min_demo_samples"]
    input_results = [row for row in results if row["name"] != "return_probability_90d"]
    score_result = next(row for row in results if row["name"] == "return_probability_90d")
    return {
        "sample_count": len(frame),
        "minimum_samples": baseline["min_demo_samples"],
        "status": "insufficient" if not enough else (
            "high" if any(row["status"] == "high" for row in input_results) else
            "watch" if any(row["status"] == "watch" for row in input_results) else "stable"
        ),
        "score_status": "insufficient" if not enough else score_result["status"],
        "model_version": baseline["model_version"],
        "metrics": results,
        "synthetic_demo_only": True,
        "thresholds_are_illustrative": True,
    }
