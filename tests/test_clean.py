import pandas as pd

from boreal_marche.data.clean import (
    apply_exclusion_rules,
    canonicalize_clean_rows,
    canonicalize_text,
    flag_outliers,
)


def sample_frame() -> pd.DataFrame:
    rows = [
        ["1", "A", "  Blue   Mug ", 2, "2020-01-01", 3.0, "10", "UK", "S1"],
        ["1", "A", "  Blue   Mug ", 2, "2020-01-01", 3.0, "10", "UK", "S1"],
        ["2", "A", "Mug", 1, "2020-01-02", 3.0, None, "UK", "S1"],
        ["3", "A", None, 1, "2020-01-03", 3.0, "10", "UK", "S1"],
        ["C4", "A", "Mug", -1, "2020-01-04", 3.0, "10", "UK", "S1"],
        ["5", "A", "Mug", 0, "2020-01-05", 3.0, "10", "UK", "S1"],
        ["6", "A", "Mug", 1, "2020-01-06", 0.0, "10", "UK", "S1"],
        ["7", "POST", "Postage", 1, "2020-01-07", 4.0, "10", "UK", "S1"],
        ["8", "B", "Plate", 100, "2020-01-08", 5.0, "11", "UK", "S1"],
    ]
    return pd.DataFrame(
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
        ],
    ).astype({"invoice_no": "string", "stock_code": "string", "description": "string"})


def test_canonicalize_text() -> None:
    assert canonicalize_text("  blue\t mug ") == "BLUE MUG"
    assert pd.isna(canonicalize_text(None))


def test_rules_are_ordered_and_do_not_double_count() -> None:
    clean, rejected, audit = apply_exclusion_rules(sample_frame(), ["POST"])

    assert len(clean) == 2
    assert len(rejected) == 7
    assert rejected["rejection_reason"].value_counts().to_dict() == {
        "exact_duplicate": 1,
        "missing_customer_id": 1,
        "missing_description": 1,
        "cancellation_invoice": 1,
        "non_positive_quantity": 1,
        "non_positive_unit_price": 1,
        "service_stock_code": 1,
    }
    assert sum(rule["rows_newly_excluded"] for rule in audit) == len(rejected)


def test_canonicalization_and_outlier_flags_preserve_rows() -> None:
    clean, _, _ = apply_exclusion_rules(sample_frame(), ["POST"])
    canonical = canonicalize_clean_rows(clean)
    flagged, summary = flag_outliers(canonical, 0.75)

    assert len(flagged) == len(canonical)
    assert flagged.iloc[0]["description"] == "BLUE MUG"
    assert flagged.iloc[0]["line_total"] == 6.0
    assert summary["rows_removed_as_outliers"] == 0
    assert flagged["is_any_outlier"].any()

