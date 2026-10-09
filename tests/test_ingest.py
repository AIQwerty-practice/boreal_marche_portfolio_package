from pathlib import Path

import pandas as pd
import pytest

from boreal_marche.data.ingest import normalize_sheet, sha256_file, verify_checksum


def test_sha256_and_verification(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"boreal-marche")
    digest = sha256_file(sample)

    assert digest == "c974bae400ae90360ad4fbc72a6c755df365d4cc86aa01072966748993cf4577"
    assert verify_checksum(sample, digest.upper()) == digest

    with pytest.raises(ValueError, match="Checksum mismatch"):
        verify_checksum(sample, "0" * 64)


def test_normalize_sheet_maps_both_year_schema() -> None:
    source = pd.DataFrame(
        {
            "Invoice": ["489434", "C489435"],
            "StockCode": ["85048", "79323P"],
            "Description": ["15CM CHRISTMAS GLASS BALL", None],
            "Quantity": [12, -1],
            "InvoiceDate": ["2009-12-01 07:45:00", "2009-12-01 07:46:00"],
            "Price": [6.95, 6.95],
            "Customer ID": [13085.0, None],
            "Country": ["United Kingdom", "United Kingdom"],
        }
    )

    result = normalize_sheet(source, "Year 2009-2010")

    assert list(result.columns) == [
        "invoice_no",
        "stock_code",
        "description",
        "quantity",
        "invoice_date",
        "unit_price",
        "customer_id",
        "country",
        "source_sheet",
    ]
    assert result.loc[0, "customer_id"] == "13085"
    assert pd.isna(result.loc[1, "customer_id"])
    assert str(result["invoice_date"].dtype) == "datetime64[ns]"


def test_normalize_sheet_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        normalize_sheet(pd.DataFrame({"Invoice": ["1"]}), "broken")
