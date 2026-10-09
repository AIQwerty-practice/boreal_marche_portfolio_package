"""Auditable silver-layer cleaning for Online Retail II transactions."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from boreal_marche.data.ingest import sha256_file

RuleMask = Callable[[pd.DataFrame], pd.Series]


def load_cleaning_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "service_stock_codes",
        "outlier_quantile",
        "input_parquet",
        "clean_parquet",
        "rejected_parquet",
        "report_json",
        "report_markdown",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"Cleaning config is missing keys: {missing}")
    quantile = float(config["outlier_quantile"])
    if not 0.5 < quantile < 1:
        raise ValueError("outlier_quantile must be between 0.5 and 1")
    return config


def canonicalize_text(value: Any) -> Any:
    """Normalize Unicode and whitespace while preserving missing values."""
    if pd.isna(value):
        return pd.NA
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text.upper() if text else pd.NA


def _rule_definitions(service_codes: set[str]) -> list[tuple[str, str, RuleMask]]:
    return [
        (
            "exact_duplicate",
            "Remove repeated rows after the first occurrence to avoid double-counting.",
            lambda frame: frame.duplicated(keep="first"),
        ),
        (
            "missing_customer_id",
            "Exclude rows that cannot be assigned to a customer history.",
            lambda frame: frame["customer_id"].isna(),
        ),
        (
            "missing_description",
            "Exclude rows without product text needed for catalogue mapping and explanation.",
            lambda frame: frame["description"].isna(),
        ),
        (
            "cancellation_invoice",
            "Exclude cancellation invoices from positive-purchase modelling.",
            lambda frame: frame["invoice_no"].str.upper().str.startswith("C", na=False),
        ),
        (
            "non_positive_quantity",
            "Exclude returns, reversals, and invalid purchase quantities.",
            lambda frame: frame["quantity"] <= 0,
        ),
        (
            "non_positive_unit_price",
            "Exclude free, corrective, and invalid price lines from monetary features.",
            lambda frame: frame["unit_price"] <= 0,
        ),
        (
            "service_stock_code",
            "Exclude postage, fees, adjustments, discounts, tests, and other non-product codes.",
            lambda frame: frame["stock_code"].str.upper().isin(service_codes),
        ),
    ]


def apply_exclusion_rules(
    frame: pd.DataFrame, service_stock_codes: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Apply ordered rules and assign one primary rejection reason to every excluded row."""
    required = {
        "invoice_no",
        "stock_code",
        "description",
        "quantity",
        "invoice_date",
        "unit_price",
        "customer_id",
        "country",
        "source_sheet",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Bronze data is missing required columns: {missing}")

    service_codes = {canonicalize_text(code) for code in service_stock_codes}
    rejected_reason = pd.Series(pd.NA, index=frame.index, dtype="string")
    audit: list[dict[str, Any]] = []

    for name, rationale, mask_function in _rule_definitions(service_codes):
        raw_mask = mask_function(frame).fillna(False)
        newly_excluded = raw_mask & rejected_reason.isna()
        rejected_reason.loc[newly_excluded] = name
        audit.append(
            {
                "rule": name,
                "rationale": rationale,
                "rows_matching_raw_condition": int(raw_mask.sum()),
                "rows_newly_excluded": int(newly_excluded.sum()),
            }
        )

    rejected = frame.loc[rejected_reason.notna()].copy()
    rejected["rejection_reason"] = rejected_reason.loc[rejected.index]
    clean = frame.loc[rejected_reason.isna()].copy()
    return clean, rejected, audit


def canonicalize_clean_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Canonicalize identifiers and descriptions after invalid rows are isolated."""
    clean = frame.copy()
    for column in ("invoice_no", "stock_code", "description", "country"):
        clean[column] = clean[column].map(canonicalize_text).astype("string")
    clean["customer_id"] = clean["customer_id"].astype("string").str.strip()
    clean["line_total"] = clean["quantity"] * clean["unit_price"]
    return clean


def flag_outliers(frame: pd.DataFrame, quantile: float) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Flag extreme valid purchases without deleting wholesale behavior."""
    clean = frame.copy()
    thresholds = {
        "quantity": float(clean["quantity"].quantile(quantile)),
        "unit_price": float(clean["unit_price"].quantile(quantile)),
        "line_total": float(clean["line_total"].quantile(quantile)),
    }
    clean["is_quantity_outlier"] = clean["quantity"] > thresholds["quantity"]
    clean["is_unit_price_outlier"] = clean["unit_price"] > thresholds["unit_price"]
    clean["is_line_total_outlier"] = clean["line_total"] > thresholds["line_total"]
    clean["is_any_outlier"] = clean[
        ["is_quantity_outlier", "is_unit_price_outlier", "is_line_total_outlier"]
    ].any(axis=1)
    summary = {
        "policy": (
            "Retain valid extreme purchases and flag values above the configured quantile. "
            "Downstream models must evaluate robust transforms or caps using training data only."
        ),
        "quantile": quantile,
        "thresholds": thresholds,
        "flag_counts": {
            "quantity": int(clean["is_quantity_outlier"].sum()),
            "unit_price": int(clean["is_unit_price_outlier"].sum()),
            "line_total": int(clean["is_line_total_outlier"].sum()),
            "any": int(clean["is_any_outlier"].sum()),
        },
        "rows_removed_as_outliers": 0,
    }
    return clean, summary


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Cleaning Report",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "## Before and after",
        "",
        "| Measure | Rows |",
        "|---|---:|",
        f"| Bronze input | {report['before_rows']:,} |",
        f"| Rejected with one primary reason | {report['rejected_rows']:,} |",
        f"| Silver output | {report['after_rows']:,} |",
        f"| Retained | {report['retention_rate']:.2%} |",
        "",
        "## Ordered exclusion rules",
        "",
        ("A row can match multiple raw conditions. `Rows newly excluded` assigns each rejected row "
        "to the first applicable rule, preventing double-counting."),
        "",
        "| Order | Rule | Raw matches | Rows newly excluded | Rationale |",
        "|---:|---|---:|---:|---|",
    ]
    for order, rule in enumerate(report["rules"], start=1):
        lines.append(
            f"| {order} | `{rule['rule']}` | {rule['rows_matching_raw_condition']:,} | "
            f"{rule['rows_newly_excluded']:,} | {rule['rationale']} |"
        )
    outliers = report["outliers"]
    lines.extend(
        [
            "",
            "## Description and identifier canonicalization",
            "",
            ("Invoice numbers, stock codes, descriptions, and countries are Unicode-normalized, "
            "trimmed, internal whitespace is collapsed, and values are uppercased. Customer IDs "
            "remain strings. The original bronze artifact remains unchanged."),
            "",
            "## Outlier policy",
            "",
            outliers["policy"],
            "",
            f"Configured quantile: {outliers['quantile']:.3%}",
            "",
            "| Signal | Threshold | Flagged rows |",
            "|---|---:|---:|",
            (f"| Quantity | {outliers['thresholds']['quantity']:,.4f} | "
            f"{outliers['flag_counts']['quantity']:,} |"),
            (f"| Unit price | {outliers['thresholds']['unit_price']:,.4f} | "
            f"{outliers['flag_counts']['unit_price']:,} |"),
            (f"| Line total | {outliers['thresholds']['line_total']:,.4f} | "
            f"{outliers['flag_counts']['line_total']:,} |"),
            f"| Any outlier signal | - | {outliers['flag_counts']['any']:,} |",
            "",
            "## Artifacts",
            "",
            f"- Bronze SHA-256: `{report['input_sha256']}`",
            f"- Silver SHA-256: `{report['clean_sha256']}`",
            f"- Rejected-record SHA-256: `{report['rejected_sha256']}`",
            "",
            "## Interpretation",
            "",
            ("These rules define the modelling population; they do not claim that excluded records "
            "are errors in the source system. Cancellation and reversal records remain available in "
            "the rejected artifact for audit and possible future return-behavior analysis."),
            "",
        ]
    )
    return "\n".join(lines)


def run_cleaning(root: Path, config_path: Path) -> dict[str, Any]:
    config = load_cleaning_config(config_path)
    source_path = root / config["input_parquet"]
    clean_path = root / config["clean_parquet"]
    rejected_path = root / config["rejected_parquet"]
    report_json_path = root / config["report_json"]
    report_markdown_path = root / config["report_markdown"]

    source = pd.read_parquet(source_path)
    clean, rejected, rules = apply_exclusion_rules(source, config["service_stock_codes"])
    clean = canonicalize_clean_rows(clean)
    clean, outliers = flag_outliers(clean, float(config["outlier_quantile"]))

    clean_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(clean_path, index=False, compression="snappy")
    rejected.to_parquet(rejected_path, index=False, compression="snappy")

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_path": config["input_parquet"],
        "input_sha256": sha256_file(source_path),
        "before_rows": len(source),
        "rejected_rows": len(rejected),
        "after_rows": len(clean),
        "retention_rate": len(clean) / len(source),
        "rules": rules,
        "outliers": outliers,
        "clean_path": config["clean_parquet"],
        "clean_sha256": sha256_file(clean_path),
        "rejected_path": config["rejected_parquet"],
        "rejected_sha256": sha256_file(rejected_path),
        "clean_schema": {column: str(dtype) for column, dtype in clean.dtypes.items()},
        "clean_null_counts": {
            column: int(value) for column, value in clean.isna().sum().items()
        },
        "rejection_reason_counts": {
            str(reason): int(count)
            for reason, count in rejected["rejection_reason"].value_counts().items()
        },
    }
    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/cleaning.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    report = run_cleaning(root, config_path)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

