"""Build aggregate D4 drift reference from train/validation snapshots only."""

from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import pandas as pd

from boreal_marche.monitoring.drift import MONITORED_FEATURES, build_baseline


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    model = joblib.load(root / "artifacts/retention_model.joblib")
    metadata = json.loads((root / "artifacts/retention_model_meta.json").read_text(encoding="utf-8"))
    feature_names = list(model.feature_names_in_)
    columns = list(dict.fromkeys([*feature_names, "snapshot_role"]))
    development = pd.read_parquet(
        root / "data/processed/customer_snapshots.parquet",
        columns=columns,
        filters=[("snapshot_role", "in", ["train", "validation"])],
    )
    if set(development["snapshot_role"]) != {"train", "validation"}:
        raise ValueError("Expected only training and validation snapshots")
    probabilities = model.predict_proba(development[feature_names])[:, 1]
    baseline = build_baseline(development, probabilities, metadata["artifact_sha256"][:12])
    output = Path(os.getenv(
        "BOREAL_DRIFT_BASELINE_OUTPUT",
        str(root / "src/boreal_marche/monitoring/development_baseline.json"),
    ))
    output.write_text(json.dumps(baseline, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Aggregate baseline: {len(development)} development rows; {len(MONITORED_FEATURES)} input features; zero test rows")


if __name__ == "__main__":
    main()
