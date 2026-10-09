import pandas as pd
import pytest

from boreal_marche.modeling.balancing import (
    assert_training_only,
    resample_training,
    select_strategy,
)


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "target_return_90d": [0] * 8 + [1] * 2,
            "snapshot_cutoff": pd.to_datetime(["2020-01-01"] * 10),
            "snapshot_role": ["train"] * 10,
            "value": range(10),
        }
    )


def test_random_undersampling_balances_training_rows() -> None:
    result = resample_training(sample_frame(), "random_undersampling", "target_return_90d", 42)
    assert result["target_return_90d"].value_counts().to_dict() == {0: 2, 1: 2}


def test_random_oversampling_balances_training_rows() -> None:
    result = resample_training(sample_frame(), "random_oversampling", "target_return_90d", 42)
    assert result["target_return_90d"].value_counts().to_dict() == {0: 8, 1: 8}


def test_no_sampling_preserves_rows() -> None:
    result = resample_training(sample_frame(), "none", "target_return_90d", 42)
    assert result.equals(sample_frame())


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown balancing strategy"):
        resample_training(sample_frame(), "smote", "target_return_90d", 42)


def test_protected_test_rows_are_rejected() -> None:
    training = sample_frame()
    validation = sample_frame().assign(
        snapshot_cutoff=pd.Timestamp("2020-02-01"), snapshot_role="test"
    )
    with pytest.raises(AssertionError, match="Protected test"):
        assert_training_only(training, validation)


def test_non_temporal_split_is_rejected() -> None:
    training = sample_frame().assign(snapshot_cutoff=pd.Timestamp("2020-03-01"))
    validation = sample_frame().assign(snapshot_cutoff=pd.Timestamp("2020-02-01"))
    with pytest.raises(AssertionError, match="precede"):
        assert_training_only(training, validation)


def test_selection_guard_rejects_marginal_pr_gain_with_bad_calibration() -> None:
    summary = pd.DataFrame(
        {
            "strategy": ["none", "balanced_class_weight", "random_undersampling"],
            "mean_pr_auc": [0.7350, 0.7357, 0.7362],
            "mean_brier_score": [0.1729, 0.1727, 0.1742],
            "mean_estimated_incremental_profit": [6692.0, 6767.0, 3907.0],
            "mean_recall_at_top_decile": [0.2494, 0.2494, 0.2475],
        }
    )
    assert select_strategy(summary, 0.002, 0.001) == "balanced_class_weight"
