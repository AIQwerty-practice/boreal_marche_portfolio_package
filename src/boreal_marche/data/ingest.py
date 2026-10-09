"""Reproducible acquisition and bronze conversion for UCI Online Retail II."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

CANONICAL_COLUMNS = {
    "Invoice": "invoice_no",
    "InvoiceNo": "invoice_no",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "unit_price",
    "UnitPrice": "unit_price",
    "Customer ID": "customer_id",
    "CustomerID": "customer_id",
    "Country": "country",
}

REQUIRED_COLUMNS = (
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
)

PARQUET_DTYPES = {
    "invoice_no": "string",
    "stock_code": "string",
    "description": "string",
    "quantity": "int64",
    "unit_price": "float64",
    "customer_id": "string",
    "country": "string",
    "source_sheet": "string",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of a file without loading it fully into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    """Load and minimally validate the dataset configuration."""
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "dataset_name",
        "source_url",
        "source_page",
        "doi",
        "license",
        "citation",
        "archive_filename",
        "workbook_filename",
        "parquet_filename",
        "manifest_filename",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"Dataset config is missing keys: {missing}")
    return config


def download_file(url: str, destination: Path, force: bool = False) -> None:
    """Download to a temporary file and atomically move it into place."""
    if destination.exists() and not force:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "boreal-marche-capstone/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def verify_checksum(path: Path, expected_sha256: str | None) -> str:
    """Calculate a checksum and fail when it differs from a recorded expectation."""
    actual = sha256_file(path)
    if expected_sha256 and actual.lower() != expected_sha256.lower():
        raise ValueError(
            f"Checksum mismatch for {path.name}: expected {expected_sha256}, got {actual}"
        )
    return actual


def extract_workbook(archive: Path, destination: Path, force: bool = False) -> None:
    """Extract the configured workbook from the official archive."""
    if destination.exists() and not force:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        candidates = [name for name in bundle.namelist() if Path(name).name == destination.name]
        if len(candidates) != 1:
            raise ValueError(
                f"Expected exactly one {destination.name!r} in archive; found {candidates}"
            )
        member = candidates[0]
        with bundle.open(member) as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)


def _normalize_customer_id(value: Any) -> Any:
    if pd.isna(value):
        return pd.NA
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or pd.NA


def normalize_sheet(frame: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """Rename source columns and enforce the bronze-layer schema."""
    frame = frame.rename(columns=CANONICAL_COLUMNS)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Sheet {sheet_name!r} is missing required columns: {missing}")

    frame = frame.loc[:, REQUIRED_COLUMNS].copy()
    frame["customer_id"] = frame["customer_id"].map(_normalize_customer_id)
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="raise")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="raise").astype("int64")
    frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="raise").astype("float64")
    frame["source_sheet"] = sheet_name

    for column, dtype in PARQUET_DTYPES.items():
        frame[column] = frame[column].astype(dtype)
    return frame


def workbook_to_parquet(workbook: Path, parquet_path: Path) -> tuple[pd.DataFrame, list[str]]:
    """Read all workbook sheets, normalize them, and write one Parquet artifact."""
    sheets = pd.read_excel(workbook, sheet_name=None, engine="openpyxl")
    if not sheets:
        raise ValueError("Workbook contains no sheets")
    normalized = [normalize_sheet(frame, name) for name, frame in sheets.items()]
    combined = pd.concat(normalized, ignore_index=True)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(parquet_path, index=False, engine="pyarrow", compression="snappy")
    return combined, list(sheets)


def build_manifest(
    *,
    root: Path,
    config: dict[str, Any],
    archive: Path,
    workbook: Path,
    parquet_path: Path,
    frame: pd.DataFrame,
    sheets: list[str],
) -> dict[str, Any]:
    """Create machine-readable provenance and schema metadata."""
    return {
        "dataset": config["dataset_name"],
        "source_url": config["source_url"],
        "source_page": config["source_page"],
        "doi": config["doi"],
        "license": config["license"],
        "citation": config["citation"],
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "archive": {
            "path": archive.relative_to(root).as_posix(),
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
        "workbook": {
            "path": workbook.relative_to(root).as_posix(),
            "bytes": workbook.stat().st_size,
            "sha256": sha256_file(workbook),
            "sheets": sheets,
        },
        "parquet": {
            "path": parquet_path.relative_to(root).as_posix(),
            "bytes": parquet_path.stat().st_size,
            "sha256": sha256_file(parquet_path),
            "row_count": len(frame),
            "column_count": len(frame.columns),
            "schema": {column: str(dtype) for column, dtype in frame.dtypes.items()},
            "null_counts": {column: int(count) for column, count in frame.isna().sum().items()},
        },
        "provenance_note": (
            "Public UCI data re-skinned as Boreal Marche for a pedagogical scenario; "
            "it is not proprietary client data."
        ),
    }


def run_ingestion(
    root: Path,
    config_path: Path,
    *,
    force_download: bool = False,
    force_extract: bool = False,
) -> dict[str, Any]:
    """Run acquisition, verification, schema normalization, and Parquet conversion."""
    config = load_config(config_path)
    raw_dir = root / "data" / "raw"
    processed_dir = root / "data" / "processed"
    archive = raw_dir / config["archive_filename"]
    workbook = raw_dir / config["workbook_filename"]
    parquet_path = processed_dir / config["parquet_filename"]
    manifest_path = processed_dir / config["manifest_filename"]

    download_file(config["source_url"], archive, force=force_download)
    verify_checksum(archive, config.get("expected_archive_sha256"))
    extract_workbook(archive, workbook, force=force_extract)
    frame, sheets = workbook_to_parquet(workbook, parquet_path)
    manifest = build_manifest(
        root=root,
        config=config,
        archive=archive,
        workbook=workbook,
        parquet_path=parquet_path,
        frame=frame,
        sheets=sheets,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/data.json"))
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--force-extract", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    manifest = run_ingestion(
        root,
        config_path,
        force_download=args.force_download,
        force_extract=args.force_extract,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
