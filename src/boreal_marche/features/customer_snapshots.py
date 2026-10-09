"""Build point-in-time customer features and 90-day retention labels."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from boreal_marche.data.ingest import sha256_file


def load_modeling_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "observation_days",
        "label_days",
        "cutoffs",
        "input_parquet",
        "output_parquet",
        "report_json",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"Modeling config is missing keys: {missing}")
    if int(config["observation_days"]) <= 0 or int(config["label_days"]) <= 0:
        raise ValueError("Window lengths must be positive")
    if not config["cutoffs"]:
        raise ValueError("At least one cutoff is required")
    return config


def _safe_cv(mean: pd.Series, std: pd.Series) -> pd.Series:
    return std.div(mean.replace(0, np.nan))


def build_customer_snapshot(
    transactions: pd.DataFrame,
    *,
    cutoff: pd.Timestamp,
    role: str,
    observation_days: int,
    label_days: int,
) -> pd.DataFrame:
    observation_start = cutoff - pd.Timedelta(days=observation_days)
    label_end = cutoff + pd.Timedelta(days=label_days)
    observation = transactions.loc[
        (transactions["invoice_date"] >= observation_start)
        & (transactions["invoice_date"] < cutoff)
    ].copy()
    label = transactions.loc[
        (transactions["invoice_date"] >= cutoff)
        & (transactions["invoice_date"] < label_end)
    ]
    if observation.empty:
        raise ValueError(f"No observation data for cutoff {cutoff.date()}")

    observation["order_date"] = observation["invoice_date"].dt.normalize()
    observation["is_weekend"] = observation["invoice_date"].dt.dayofweek >= 5
    observation["is_morning"] = observation["invoice_date"].dt.hour < 12
    observation["is_evening"] = observation["invoice_date"].dt.hour >= 18
    observation["is_recent_30d"] = observation["invoice_date"] >= cutoff - pd.Timedelta(days=30)
    observation["is_recent_60d"] = observation["invoice_date"] >= cutoff - pd.Timedelta(days=60)
    observation["is_recent_90d"] = observation["invoice_date"] >= cutoff - pd.Timedelta(days=90)

    invoice = (
        observation.groupby(["customer_id", "invoice_no"], observed=True)
        .agg(
            order_time=("invoice_date", "min"),
            order_value=("line_total", "sum"),
            basket_lines=("stock_code", "size"),
            basket_unique_products=("stock_code", "nunique"),
            basket_quantity=("quantity", "sum"),
        )
        .reset_index()
    )
    invoice = invoice.sort_values(["customer_id", "order_time"])
    invoice["cadence_days"] = invoice.groupby("customer_id", observed=True)["order_time"].diff().dt.total_seconds().div(86400)

    customer = observation.groupby("customer_id", observed=True)
    invoice_customer = invoice.groupby("customer_id", observed=True)
    features = customer.agg(
        first_purchase=("invoice_date", "min"),
        last_purchase=("invoice_date", "max"),
        quantity_total=("quantity", "sum"),
        unique_products=("stock_code", "nunique"),
        line_count=("stock_code", "size"),
        unit_price_mean=("unit_price", "mean"),
        unit_price_median=("unit_price", "median"),
        unit_price_max=("unit_price", "max"),
        country_count=("country", "nunique"),
        weekend_line_ratio=("is_weekend", "mean"),
        morning_line_ratio=("is_morning", "mean"),
        evening_line_ratio=("is_evening", "mean"),
        outlier_line_ratio=("is_any_outlier", "mean"),
        recent_30d_lines=("is_recent_30d", "sum"),
        recent_60d_lines=("is_recent_60d", "sum"),
        recent_90d_lines=("is_recent_90d", "sum"),
    )
    order_features = invoice_customer.agg(
        frequency_orders=("invoice_no", "nunique"),
        monetary_total=("order_value", "sum"),
        order_value_mean=("order_value", "mean"),
        order_value_median=("order_value", "median"),
        order_value_std=("order_value", "std"),
        order_value_max=("order_value", "max"),
        basket_lines_mean=("basket_lines", "mean"),
        basket_lines_median=("basket_lines", "median"),
        basket_lines_max=("basket_lines", "max"),
        basket_unique_products_mean=("basket_unique_products", "mean"),
        basket_quantity_mean=("basket_quantity", "mean"),
        cadence_days_mean=("cadence_days", "mean"),
        cadence_days_std=("cadence_days", "std"),
    )
    features = features.join(order_features)

    primary_country = (
        observation.groupby(["customer_id", "country"], observed=True)
        .size()
        .rename("lines")
        .reset_index()
        .sort_values(["customer_id", "lines", "country"], ascending=[True, False, True])
        .drop_duplicates("customer_id")
        .set_index("customer_id")["country"]
        .rename("primary_country")
    )
    features = features.join(primary_country)

    recent = observation.groupby("customer_id", observed=True).agg(
        recent_30d_orders=("invoice_no", lambda x: x[observation.loc[x.index, "is_recent_30d"]].nunique()),
        recent_60d_orders=("invoice_no", lambda x: x[observation.loc[x.index, "is_recent_60d"]].nunique()),
        recent_90d_orders=("invoice_no", lambda x: x[observation.loc[x.index, "is_recent_90d"]].nunique()),
        recent_90d_spend=("line_total", lambda x: x[observation.loc[x.index, "is_recent_90d"]].sum()),
    )
    features = features.join(recent)

    features["recency_days"] = (cutoff - features["last_purchase"]).dt.total_seconds() / 86400
    features["tenure_days"] = (cutoff - features["first_purchase"]).dt.total_seconds() / 86400
    features["active_span_days"] = (
        features["last_purchase"] - features["first_purchase"]
    ).dt.total_seconds() / 86400
    features["monthly_order_frequency"] = features["frequency_orders"] / (observation_days / 30.4375)
    features["quantity_per_order"] = features["quantity_total"] / features["frequency_orders"]
    features["product_diversity_ratio"] = features["unique_products"] / features["line_count"]
    features["order_value_cv"] = _safe_cv(
        features["order_value_mean"], features["order_value_std"]
    )
    features["recency_to_cadence"] = features["recency_days"] / features[
        "cadence_days_mean"
    ].replace(0, np.nan)
    features["repeat_product_ratio"] = 1 - (
        features["unique_products"] / features["quantity_total"].clip(lower=1)
    )

    positive_customers = set(label["customer_id"].dropna().unique())
    features["target_return_90d"] = features.index.isin(positive_customers).astype("int8")
    features["snapshot_cutoff"] = cutoff
    features["observation_start"] = observation_start
    features["label_end"] = label_end
    features["snapshot_role"] = role
    return features.reset_index()


def build_all_snapshots(transactions: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    maximum_date = transactions["invoice_date"].max()
    snapshots: list[pd.DataFrame] = []
    for item in config["cutoffs"]:
        cutoff = pd.Timestamp(item["date"])
        label_end = cutoff + pd.Timedelta(days=int(config["label_days"]))
        if label_end > maximum_date:
            raise ValueError(
                f"Label window for {cutoff.date()} ends after available data ({maximum_date})"
            )
        snapshots.append(
            build_customer_snapshot(
                transactions,
                cutoff=cutoff,
                role=str(item["role"]),
                observation_days=int(config["observation_days"]),
                label_days=int(config["label_days"]),
            )
        )
    return pd.concat(snapshots, ignore_index=True)


def run_feature_generation(root: Path, config_path: Path) -> dict[str, Any]:
    config = load_modeling_config(config_path)
    input_path = root / config["input_parquet"]
    output_path = root / config["output_parquet"]
    report_path = root / config["report_json"]
    transactions = pd.read_parquet(input_path)
    snapshots = build_all_snapshots(transactions, config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    snapshots.to_parquet(output_path, index=False, compression="snappy")

    metadata_columns = {
        "customer_id",
        "target_return_90d",
        "snapshot_cutoff",
        "observation_start",
        "label_end",
        "snapshot_role",
        "primary_country",
        "first_purchase",
        "last_purchase",
    }
    feature_columns = [column for column in snapshots.columns if column not in metadata_columns]
    by_snapshot = []
    for (cutoff, role), group in snapshots.groupby(
        ["snapshot_cutoff", "snapshot_role"], observed=True
    ):
        by_snapshot.append(
            {
                "cutoff": cutoff.isoformat(),
                "role": role,
                "customers": len(group),
                "positive_rate": float(group["target_return_90d"].mean()),
                "observation_start": group["observation_start"].iloc[0].isoformat(),
                "label_end": group["label_end"].iloc[0].isoformat(),
            }
        )
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_path": config["input_parquet"],
        "input_sha256": sha256_file(input_path),
        "output_path": config["output_parquet"],
        "output_sha256": sha256_file(output_path),
        "observation_days": int(config["observation_days"]),
        "label_days": int(config["label_days"]),
        "snapshot_rows": len(snapshots),
        "numeric_feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "snapshots": by_snapshot,
        "leakage_contract": (
            "Features use timestamps in [cutoff-observation_days, cutoff); labels use "
            "timestamps in [cutoff, cutoff+label_days)."
        ),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/modeling.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    report = run_feature_generation(root, config_path)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

