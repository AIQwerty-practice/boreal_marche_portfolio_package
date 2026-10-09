"""Build and evaluate the offline association-rule recommendation head."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse


def build_baskets(
    transactions: pd.DataFrame, maximum_items: int
) -> tuple[pd.DataFrame, list[str], dict[str, int]]:
    counts = transactions.groupby("stock_code")["invoice_no"].nunique().sort_values(ascending=False)
    items = counts.head(maximum_items).index.astype(str).tolist()
    filtered = transactions.loc[transactions["stock_code"].isin(items), ["invoice_no", "stock_code"]]
    invoices = sorted(filtered["invoice_no"].astype(str).unique())
    invoice_index = {invoice: index for index, invoice in enumerate(invoices)}
    item_index = {item: index for index, item in enumerate(items)}
    unique_pairs = filtered.drop_duplicates().astype(str)
    rows = unique_pairs["invoice_no"].map(invoice_index).to_numpy()
    columns = unique_pairs["stock_code"].map(item_index).to_numpy()
    matrix = sparse.csr_matrix(
        (np.ones(len(unique_pairs), dtype=np.uint8), (rows, columns)),
        shape=(len(invoices), len(items)),
        dtype=np.uint8,
    )
    baskets = pd.DataFrame.sparse.from_spmatrix(
        matrix, index=invoices, columns=items
    ).astype(pd.SparseDtype(bool, False))
    memory = {
        "dense_bytes": int(matrix.shape[0] * matrix.shape[1] * np.dtype(bool).itemsize),
        "sparse_bytes": int(matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes),
    }
    return baskets, items, memory


def mine_rules(
    baskets: pd.DataFrame,
    min_support: float,
    min_confidence: float,
    min_lift: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    from mlxtend.frequent_patterns import association_rules, fpgrowth

    start = time.perf_counter()
    itemsets = fpgrowth(baskets, min_support=min_support, use_colnames=True, max_len=2)
    fp_seconds = time.perf_counter() - start
    rules = association_rules(
        itemsets,
        num_itemsets=len(baskets),
        metric="confidence",
        min_threshold=min_confidence,
    )
    rules = rules.loc[
        (rules["antecedents"].map(len) == 1) & (rules["consequents"].map(len) == 1)
    ].copy()
    rules_before_lift_filter = len(rules)
    rules = rules.loc[rules["lift"] >= min_lift].copy()
    rules["antecedent"] = rules["antecedents"].map(lambda value: next(iter(value)))
    rules["consequent"] = rules["consequents"].map(lambda value: next(iter(value)))
    rules = rules.sort_values(
        ["antecedent", "lift", "confidence", "support"], ascending=[True, False, False, False]
    )
    rules = rules.drop_duplicates(["antecedent", "consequent"], keep="first")
    return rules, {
        "fpgrowth_seconds": fp_seconds,
        "frequent_itemsets": len(itemsets),
        "min_lift": min_lift,
        "rules_before_lift_filter": rules_before_lift_filter,
        "rules_removed_by_lift_filter": rules_before_lift_filter - len(rules),
    }


def demonstrate_apriori(baskets: pd.DataFrame, min_support: float, item_limit: int) -> dict[str, float]:
    from mlxtend.frequent_patterns import apriori

    sample = baskets.iloc[:, : min(item_limit, baskets.shape[1])]
    start = time.perf_counter()
    itemsets = apriori(sample, min_support=min_support, use_colnames=True, max_len=2)
    return {
        "columns": int(sample.shape[1]),
        "seconds": time.perf_counter() - start,
        "frequent_itemsets": len(itemsets),
    }


def index_rules(rules: pd.DataFrame) -> dict[str, list[dict[str, float | str]]]:
    index: dict[str, list[dict[str, float | str]]] = defaultdict(list)
    for row in rules.itertuples():
        index[str(row.antecedent)].append(
            {
                "item": str(row.consequent),
                "support": float(row.support),
                "confidence": float(row.confidence),
                "lift": float(row.lift),
                "firing_rule": f"{row.antecedent} -> {row.consequent}",
            }
        )
    return dict(index)


def recommend(
    basket: list[str],
    rules_index: dict[str, list[dict[str, Any]]],
    popularity: list[str],
    k: int = 5,
) -> dict[str, Any]:
    basket_set = set(basket)
    candidates: dict[str, dict[str, Any]] = {}
    for antecedent in basket:
        for rule in rules_index.get(antecedent, []):
            item = str(rule["item"])
            if item not in basket_set and (
                item not in candidates or float(rule["lift"]) > float(candidates[item]["lift"])
            ):
                candidates[item] = rule
    ranked = sorted(
        candidates.values(),
        key=lambda rule: (float(rule["lift"]), float(rule["confidence"]), float(rule["support"])),
        reverse=True,
    )
    source = "association_rules" if ranked else ("empty_basket_popularity" if not basket else "no_match_popularity")
    selected = ranked[:k]
    used = {str(rule["item"]) for rule in selected}
    for item in popularity:
        if len(selected) >= k:
            break
        if item not in basket_set and item not in used:
            selected.append(
                {"item": item, "support": None, "confidence": None, "lift": None, "firing_rule": None}
            )
            used.add(item)
    return {"source": source, "recommendations": selected}


def holdout_cases(transactions: pd.DataFrame) -> list[tuple[list[str], set[str]]]:
    cases = []
    for _, group in transactions.sort_values("invoice_date").groupby("invoice_no", sort=False):
        items = list(dict.fromkeys(group["stock_code"].astype(str)))
        if len(items) < 2:
            continue
        split = max(1, len(items) // 2)
        context, targets = items[:split], set(items[split:])
        if targets:
            cases.append((context, targets))
    return cases


def evaluate(
    cases: list[tuple[list[str], set[str]]],
    rules_index: dict[str, list[dict[str, Any]]],
    popularity: list[str],
    catalog: set[str],
    k: int,
) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    for name in ("rules", "popularity"):
        hits = 0
        recommended: set[str] = set()
        rule_fires = 0
        for context, targets in cases:
            if name == "rules":
                response = recommend(context, rules_index, popularity, k)
                ranked = [str(item["item"]) for item in response["recommendations"]]
                rule_fires += response["source"] == "association_rules"
            else:
                ranked = [item for item in popularity if item not in set(context)][:k]
            hits += bool(set(ranked) & targets)
            recommended.update(ranked)
        results[name] = {
            "hit_rate_at_5": hits / len(cases),
            "catalog_coverage": len(recommended & catalog) / len(catalog),
            "unique_items_recommended": len(recommended),
            "rule_fire_rate": rule_fires / len(cases) if name == "rules" else 0.0,
        }
    return results


def run(root: Path, config_path: Path) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    config = json.loads(config_path.read_text(encoding="utf-8"))
    transactions = pd.read_parquet(root / config["input_parquet"])
    cutoff = pd.Timestamp(config["holdout_start"])
    training = transactions.loc[transactions["invoice_date"] < cutoff].copy()
    holdout = transactions.loc[transactions["invoice_date"] >= cutoff].copy()
    if training.empty or holdout.empty or training["invoice_date"].max() >= holdout["invoice_date"].min():
        raise AssertionError("Recommendation evaluation requires a strict temporal split")
    baskets, catalog_list, memory = build_baskets(training, int(config["maximum_items"]))
    popularity = (
        training.loc[training["stock_code"].isin(catalog_list)]
        .groupby("stock_code")["invoice_no"]
        .nunique()
        .sort_values(ascending=False)
        .index.astype(str)
        .tolist()
    )
    apriori_result = demonstrate_apriori(
        baskets, float(config["apriori_min_support"]), int(config["apriori_item_limit"])
    )
    rules, mining = mine_rules(
        baskets,
        float(config["min_support"]),
        float(config["min_confidence"]),
        float(config["min_lift"]),
    )
    rules_index = index_rules(rules)
    cases = holdout_cases(holdout.loc[holdout["stock_code"].isin(catalog_list)])
    evaluation = evaluate(cases, rules_index, popularity, set(catalog_list), int(config["k"]))

    sweep_rows = []
    for support in config["support_sweep"]:
        for confidence in config["confidence_sweep"]:
            swept, _ = mine_rules(
                baskets,
                float(support),
                float(confidence),
                float(config["min_lift"]),
            )
            sweep_rows.append(
                {
                    "min_support": support,
                    "min_confidence": confidence,
                    "min_lift": config["min_lift"],
                    "rules": len(swept),
                }
            )
    sweep = pd.DataFrame(sweep_rows)
    output_rules = rules[["antecedent", "consequent", "support", "confidence", "lift"]].copy()
    paths = {name: root / config[name] for name in ("rules_csv", "sweep_csv", "artifact_json", "report_json", "report_markdown", "figure_path")}
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    output_rules.to_csv(paths["rules_csv"], index=False)
    sweep.to_csv(paths["sweep_csv"], index=False)
    artifact = {"rules_index": rules_index, "popularity": popularity, "catalog": catalog_list, "k": int(config["k"])}
    paths["artifact_json"].write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "head": "B - Recommendation",
        "temporal_split": {"training_end_exclusive": config["holdout_start"], "holdout_start": config["holdout_start"]},
        "training_invoices": int(training["invoice_no"].nunique()),
        "holdout_invoices": int(holdout["invoice_no"].nunique()),
        "evaluation_cases": len(cases),
        "catalog_items": len(catalog_list),
        "basket_shape": list(baskets.shape),
        "basket_density": float(baskets.sparse.density),
        "memory": {**memory, "dense_to_sparse_ratio": memory["dense_bytes"] / memory["sparse_bytes"]},
        "apriori_demonstration": apriori_result,
        "fpgrowth": mining,
        "minimum_lift": float(config["min_lift"]),
        "rules": len(rules),
        "evaluation": evaluation,
        "fallbacks": ["empty_basket_popularity", "no_match_popularity"],
    }
    paths["report_json"].write_text(json.dumps(report, indent=2), encoding="utf-8")
    names = ["Association rules", "Popularity baseline"]
    hit_rates = [evaluation["rules"]["hit_rate_at_5"], evaluation["popularity"]["hit_rate_at_5"]]
    coverage = [evaluation["rules"]["catalog_coverage"], evaluation["popularity"]["catalog_coverage"]]
    x = np.arange(2)
    fig, axis = plt.subplots(figsize=(8, 5.5))
    width = 0.34
    axis.bar(x - width / 2, hit_rates, width, label="Hit-rate@5", color="#176B87")
    axis.bar(x + width / 2, coverage, width, label="Catalog coverage", color="#64CCC5")
    axis.set_xticks(x, names)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Share")
    axis.set_title("Association rules improve hit rate and catalog coverage")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(paths["figure_path"], dpi=180)
    plt.close(fig)
    rule_eval = evaluation["rules"]
    pop_eval = evaluation["popularity"]
    markdown = f"""# Head B — Product Recommendation Evaluation

Training uses invoices before **{config['holdout_start']}**; evaluation uses later invoices only.

## Basket and mining evidence

- Sparse basket shape: {baskets.shape[0]:,} invoices × {baskets.shape[1]:,} items; density {baskets.sparse.density:.4%}.
- Dense footprint estimate: {memory['dense_bytes'] / 1_048_576:.2f} MiB; sparse CSR footprint: {memory['sparse_bytes'] / 1_048_576:.2f} MiB ({memory['dense_bytes'] / memory['sparse_bytes']:.1f}× smaller).
- Apriori demonstration: {apriori_result['frequent_itemsets']:,} itemsets across {apriori_result['columns']} items in {apriori_result['seconds']:.3f} seconds.
- FP-Growth production run: {mining['frequent_itemsets']:,} itemsets and {mining['rules_before_lift_filter']:,} singleton-to-singleton candidates in {mining['fpgrowth_seconds']:.3f} seconds.
- Explicit minimum-lift floor: {config['min_lift']:.2f}; {mining['rules_removed_by_lift_filter']:,} weak rules removed and {len(rules):,} production rules retained.

## Temporal holdout results ({len(cases):,} partial-basket cases)

| Method | Hit-rate@5 | Catalog coverage | Rule fire rate |
|---|---:|---:|---:|
| Association rules with popularity fallback | {rule_eval['hit_rate_at_5']:.4f} | {rule_eval['catalog_coverage']:.4f} | {rule_eval['rule_fire_rate']:.4f} |
| Global popularity | {pop_eval['hit_rate_at_5']:.4f} | {pop_eval['catalog_coverage']:.4f} | — |

The rules artifact applies the configured lift floor before indexing, is indexed by antecedent, excludes items already in the basket, deduplicates consequents by highest lift, and returns the firing rule. Empty baskets and unmatched baskets are explicitly identified and use the popularity fallback.

This is an offline next-item proxy based on historical co-purchase. It does not measure revenue lift, causal impact, novelty, or long-term customer value.
"""
    paths["report_markdown"].write_text(markdown, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/recommendation.json"))
    args = parser.parse_args()
    print(json.dumps(run(args.root.resolve(), (args.root / args.config).resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
