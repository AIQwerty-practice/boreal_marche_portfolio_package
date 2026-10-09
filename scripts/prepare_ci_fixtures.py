"""Create synthetic tool fixtures for clean-checkout assistant contract tests."""

import json
from pathlib import Path

import pandas as pd


def main():
    root = Path.cwd()
    rules = root / "artifacts/recommendation_rules.json"
    data = root / "data/processed/transactions_clean.parquet"
    if rules.exists() or data.exists():
        raise SystemExit("Refusing to overwrite existing project artifacts or data.")
    rules.parent.mkdir(parents=True, exist_ok=True)
    data.parent.mkdir(parents=True, exist_ok=True)
    rules.write_text(
        json.dumps(
            {
                "rules_index": {
                    "15056BL": [
                        {
                            "item": "22630",
                            "support": 0.02,
                            "confidence": 0.2,
                            "lift": 1.2,
                            "firing_rule": "15056BL -> 22630",
                        }
                    ]
                },
                "popularity": ["85048", "79323P"],
                "catalog": ["15056BL", "22630", "85048", "79323P"],
            }
        )
    )
    pd.DataFrame(
        {
            "stock_code": ["15056BL", "22630", "85048", "79323P"],
            "description": [
                "Synthetic demo item A",
                "Synthetic demo item B",
                "Synthetic demo item C",
                "Synthetic demo item D",
            ],
        }
    ).to_parquet(data, index=False)
    print("Synthetic CI fixtures created; these are not trained-model or provider evidence.")


if __name__ == "__main__":
    main()
