"""Create the development-only parquet used by the D3 SageMaker HPO job."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    frame = pd.read_parquet(args.source)
    if "snapshot_role" not in frame:
        raise ValueError("Missing snapshot_role column")
    source_counts = frame["snapshot_role"].value_counts().sort_index().to_dict()
    development = frame.loc[frame["snapshot_role"].isin(["train", "validation"])].copy()
    if development.empty or (development["snapshot_role"] == "test").any():
        raise AssertionError("Development export must contain train/validation rows and no test rows")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    development.to_parquet(args.output, index=False)
    exported = pd.read_parquet(args.output)
    if (exported["snapshot_role"] == "test").any():
        raise AssertionError("Protected test rows were found after export")

    manifest = {
        "source_file": args.source.as_posix(),
        "source_rows_by_role": source_counts,
        "export_file": args.output.name,
        "export_rows": len(exported),
        "export_rows_by_role": exported["snapshot_role"].value_counts().sort_index().to_dict(),
        "protected_test_rows_exported": 0,
        "sha256": sha256(args.output),
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
