import pandas as pd

from boreal_marche.features.customer_snapshots import build_customer_snapshot


def synthetic_transactions() -> pd.DataFrame:
    rows = [
        ["1", "A", "A", 1, "2020-01-10", 10.0, "C1", "UK", "S", 10.0],
        ["2", "B", "B", 2, "2020-01-20", 5.0, "C1", "UK", "S", 10.0],
        ["3", "C", "C", 1, "2020-02-10", 7.0, "C2", "FR", "S", 7.0],
        ["4", "D", "D", 1, "2020-03-05", 9.0, "C1", "UK", "S", 9.0],
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "invoice_no",
            "stock_code",
            "description",
            "quantity",
            "invoice_date",
            "unit_price",
            "customer_id",
            "country",
            "source_sheet",
            "line_total",
        ],
    )
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"])
    frame["is_any_outlier"] = False
    return frame


def test_snapshot_separates_observation_and_label_windows() -> None:
    result = build_customer_snapshot(
        synthetic_transactions(),
        cutoff=pd.Timestamp("2020-03-01"),
        role="test",
        observation_days=60,
        label_days=30,
    ).set_index("customer_id")

    assert set(result.index) == {"C1", "C2"}
    assert result.loc["C1", "frequency_orders"] == 2
    assert result.loc["C1", "monetary_total"] == 20.0
    assert result.loc["C1", "target_return_90d"] == 1
    assert result.loc["C2", "target_return_90d"] == 0


def test_future_transaction_never_changes_features() -> None:
    frame = synthetic_transactions()
    without_future = frame.iloc[:3].copy()
    kwargs = {
        "cutoff": pd.Timestamp("2020-03-01"),
        "role": "test",
        "observation_days": 60,
        "label_days": 30,
    }
    with_label = build_customer_snapshot(frame, **kwargs).set_index("customer_id")
    without_label = build_customer_snapshot(without_future, **kwargs).set_index("customer_id")

    feature_columns = [
        "frequency_orders",
        "monetary_total",
        "recency_days",
        "quantity_total",
        "unique_products",
    ]
    pd.testing.assert_series_equal(
        with_label.loc["C1", feature_columns], without_label.loc["C1", feature_columns]
    )
    assert with_label.loc["C1", "target_return_90d"] == 1
    assert without_label.loc["C1", "target_return_90d"] == 0

