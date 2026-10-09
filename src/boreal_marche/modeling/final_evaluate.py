"""One-time protected-test evaluation for the frozen Head A artifact."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd

from boreal_marche.data.ingest import sha256_file
from boreal_marche.modeling.segment_analysis import bootstrap_metrics, safe_metrics
from boreal_marche.modeling.tune import profit_curve


def evaluate_protected_test(root: Path, *, confirmed: bool) -> dict[str, object]:
    if not confirmed:
        raise ValueError("Protected-test evaluation requires --confirm-protected-test.")

    metadata_path = root / "artifacts" / "retention_model_meta.json"
    report_path = root / "reports" / "d3" / "final_test_report.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("protected_test_evaluated"):
        if report_path.exists():
            return json.loads(report_path.read_text(encoding="utf-8"))
        raise RuntimeError("Metadata says the protected test was evaluated, but its report is missing.")

    model_path = root / metadata["artifact_path"]
    if sha256_file(model_path) != metadata["artifact_sha256"]:
        raise RuntimeError("Model artifact hash differs from the frozen metadata.")
    if metadata["selected_calibrated_model"] != "random_forest_sigmoid":
        raise RuntimeError("Unexpected selected model; protected test remains closed.")
    threshold = float(metadata["selected_threshold"]["threshold"])
    if threshold != 0.4:
        raise RuntimeError("Unexpected campaign threshold; protected test remains closed.")

    balancing = json.loads(
        (root / "reports" / "d3" / "balancing_report.json").read_text(encoding="utf-8")
    )
    if balancing["selected_strategy"] != "balanced_class_weight":
        raise RuntimeError("Balancing strategy is not frozen; protected test remains closed.")

    snapshots = pd.read_parquet(
        root / "data" / "processed" / "customer_snapshots.parquet",
        filters=[("snapshot_role", "==", "test")],
    )
    if snapshots.empty or set(snapshots["snapshot_role"]) != {"test"}:
        raise RuntimeError("Protected-test role isolation failed.")

    model = joblib.load(model_path)
    feature_names = list(model.feature_names_in_)
    probability = model.predict_proba(snapshots[feature_names])[:, 1]
    actual = snapshots["target_return_90d"]
    overall = safe_metrics(actual, probability)
    uncertainty = bootstrap_metrics(actual, probability, iterations=1_000, seed=42)
    curve = profit_curve(probability, metadata["campaign_assumptions"])
    fixed = curve.iloc[(curve["threshold"] - threshold).abs().argmin()]
    selected = probability <= threshold
    generated = datetime.now(UTC).isoformat()
    report: dict[str, object] = {
        "generated_at_utc": generated,
        "evaluation_type": "one_time_protected_test",
        "model": metadata["selected_calibrated_model"],
        "balancing_strategy": balancing["selected_strategy"],
        "artifact_sha256": metadata["artifact_sha256"],
        "feature_source_sha256": metadata["feature_source_sha256"],
        "test_cutoff": str(pd.Timestamp(snapshots["snapshot_cutoff"].iloc[0]).date()),
        "test_rows": len(snapshots),
        "observed_positive_rate": float(actual.mean()),
        "metrics": overall,
        "bootstrap_iterations": 1_000,
        "bootstrap_95_intervals": uncertainty,
        "frozen_campaign_policy": {
            "threshold": threshold,
            "customers_contacted": int(selected.sum()),
            "selection_rate": float(selected.mean()),
            "scenario_estimated_incremental_profit": float(
                fixed["estimated_incremental_profit"]
            ),
            "causal_claim": False,
        },
        "customer_level_predictions_persisted": False,
        "no_post_test_model_selection": True,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    markdown = f"""# Head A — One-Time Protected-Test Evaluation

The frozen `{metadata['selected_calibrated_model']}` artifact with balanced class weights and the preselected 0.400 campaign threshold was evaluated once on the 10 September 2011 test snapshot. No customer-level predictions were persisted, and no model, calibration, balancing, or threshold choice may be changed because of this result.

## Aggregate result

- Test customers: {len(snapshots):,}
- Observed 90-day return rate: {actual.mean():.2%}
- PR-AUC: {overall['pr_auc']:.4f} (bootstrap 95% interval {uncertainty['pr_auc']['lower_95']:.4f}–{uncertainty['pr_auc']['upper_95']:.4f})
- ROC-AUC: {overall['roc_auc']:.4f} (bootstrap 95% interval {uncertainty['roc_auc']['lower_95']:.4f}–{uncertainty['roc_auc']['upper_95']:.4f})
- Brier score: {overall['brier_score']:.4f} (bootstrap 95% interval {uncertainty['brier_score']['lower_95']:.4f}–{uncertainty['brier_score']['upper_95']:.4f})
- Recall at top decile: {overall['recall_at_top_decile']:.4f}
- Mean predicted return: {overall['mean_predicted_return']:.2%}
- Calibration gap (mean predicted minus observed): {overall['calibration_gap']:.2%}

## Frozen campaign policy

- Contact rule: predicted return probability at or below 0.400
- Customers selected: {int(selected.sum()):,} ({selected.mean():.2%})
- Scenario-estimated incremental profit: {float(fixed['estimated_incremental_profit']):,.2f}

The profit figure is an assumption-driven planning scenario, not observed causal lift. Test results are final evaluation evidence and are not used for additional selection or tuning.
"""
    (root / "reports" / "d3" / "FINAL_TEST_REPORT.md").write_text(markdown, encoding="utf-8")

    metadata["protected_test_evaluated"] = True
    metadata["protected_test_evaluated_at_utc"] = generated
    metadata["protected_test_report"] = "reports/d3/final_test_report.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for path in (
        root / "reports" / "d3" / "tuning_calibration_report.json",
        root / "reports" / "d3" / "balancing_report.json",
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["protected_test_evaluated"] = True
        payload["protected_test_evaluated_at_utc"] = generated
        payload["protected_test_report"] = "reports/d3/final_test_report.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--confirm-protected-test", action="store_true")
    args = parser.parse_args()
    report = evaluate_protected_test(
        args.root.resolve(), confirmed=args.confirm_protected_test
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
