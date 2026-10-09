"""Render validation-versus-protected-test evidence from aggregate reports."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
validation = json.loads(
    (ROOT / "reports" / "d3" / "tuning_calibration_report.json").read_text(encoding="utf-8")
)["validation_metrics"]
test = json.loads(
    (ROOT / "reports" / "d3" / "final_test_report.json").read_text(encoding="utf-8")
)["metrics"]

labels = ["PR-AUC", "ROC-AUC", "Brier", "Top-decile recall"]
validation_values = [
    validation["pr_auc"],
    validation["roc_auc"],
    validation["brier_score"],
    validation["recall_at_top_decile"],
]
test_values = [
    test["pr_auc"],
    test["roc_auc"],
    test["brier_score"],
    test["recall_at_top_decile"],
]
x = range(len(labels))
fig, axis = plt.subplots(figsize=(9, 5.5))
axis.bar([value - 0.18 for value in x], validation_values, width=0.36, label="Validation")
axis.bar([value + 0.18 for value in x], test_values, width=0.36, label="Protected test")
axis.set_xticks(list(x), labels)
axis.set_ylim(0, 0.9)
axis.set_ylabel("Metric value")
axis.set_title("Frozen Head A: validation versus one-time protected test")
axis.legend()
axis.grid(axis="y", alpha=0.25)
fig.tight_layout()
output = ROOT / "reports" / "d3" / "figures" / "final_test_comparison.png"
fig.savefig(output, dpi=180)
plt.close(fig)
print(output)
