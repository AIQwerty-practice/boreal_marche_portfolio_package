import numpy as np
import pandas as pd

from boreal_marche.modeling.segment_analysis import (
    add_segments,
    bootstrap_metrics,
    safe_metrics,
    segment_table,
)


def test_safe_metrics_reports_calibration_gap() -> None:
    result = safe_metrics(pd.Series([0, 0, 1, 1]), np.array([0.1, 0.2, 0.7, 0.9]))
    assert result["pr_auc"] == 1.0
    assert abs(result["calibration_gap"] - (-0.025)) < 1e-12


def test_bootstrap_metrics_are_seeded_and_ordered() -> None:
    y = pd.Series([0, 1] * 50)
    probability = np.linspace(0.01, 0.99, 100)
    first = bootstrap_metrics(y, probability, 50, 42)
    second = bootstrap_metrics(y, probability, 50, 42)
    assert first == second
    assert first["pr_auc"]["lower_95"] <= first["pr_auc"]["upper_95"]


def test_segment_table_respects_minimum_size_and_threshold() -> None:
    frame = pd.DataFrame(
        {
            "group": ["large"] * 10 + ["small"] * 2,
            "target_return_90d": [0, 1] * 6,
            "predicted_return_probability": np.linspace(0.05, 0.95, 12),
        }
    )
    result = segment_table(frame, "group", threshold=0.4, minimum_size=5)
    assert result["segment"].tolist() == ["large"]
    assert 0 < result.loc[0, "campaign_selection_rate"] < 1


def test_add_segments_keeps_country_scope_explicit() -> None:
    frame = pd.DataFrame(
        {
            "primary_country": ["UNITED KINGDOM", "FRANCE", "GERMANY"],
            "monetary_total": [10.0, 20.0, 30.0],
            "frequency_orders": [1, 2, 3],
        }
    )
    result = add_segments(frame)
    assert result["country_group"].tolist() == [
        "United Kingdom",
        "Other countries",
        "Other countries",
    ]
