import numpy as np
import pandas as pd
import pytest

from boreal_marche.modeling.screen import (
    business_rule_probability,
    metrics,
    recall_at_top_fraction,
    temporal_fold,
)


def test_recall_at_top_decile() -> None:
    y_true = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0])
    scores = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0])
    assert recall_at_top_fraction(y_true, scores, 0.1) == 0.5


def test_metrics_are_finite() -> None:
    result = metrics(pd.Series([0, 1, 0, 1]), np.array([0.1, 0.8, 0.2, 0.9]))
    assert set(result) == {"pr_auc", "roc_auc", "brier_score", "recall_at_top_decile"}
    assert all(np.isfinite(value) for value in result.values())


def test_business_rule_uses_configured_recency() -> None:
    frame = pd.DataFrame({"recency_days": [5, 30, 31, 100]})
    assert business_rule_probability(frame, 30).tolist() == [1.0, 1.0, 0.0, 0.0]


def test_temporal_fold_excludes_test_and_future_rows() -> None:
    frame = pd.DataFrame(
        {
            "snapshot_cutoff": pd.to_datetime(
                ["2020-01-01", "2020-02-01", "2020-03-01"]
            ),
            "snapshot_role": ["train", "validation", "test"],
        }
    )
    train, validation = temporal_fold(frame, pd.Timestamp("2020-02-01"))
    assert train["snapshot_cutoff"].max() < validation["snapshot_cutoff"].min()
    assert "test" not in set(train["snapshot_role"]) | set(validation["snapshot_role"])

    with pytest.raises(AssertionError, match="Protected test"):
        temporal_fold(frame, pd.Timestamp("2020-03-01"))

