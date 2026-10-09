import pandas as pd

from boreal_marche.recommendation.recommend import (
    holdout_cases,
    index_rules,
    mine_rules,
    recommend,
)


def test_recommend_excludes_basket_and_uses_highest_lift() -> None:
    rules = pd.DataFrame(
        {
            "antecedent": ["A", "B"],
            "consequent": ["C", "C"],
            "support": [0.1, 0.1],
            "confidence": [0.5, 0.4],
            "lift": [2.0, 3.0],
        }
    )
    response = recommend(["A", "B"], index_rules(rules), ["A", "D"], k=2)
    assert response["source"] == "association_rules"
    assert response["recommendations"][0]["firing_rule"] == "B -> C"
    assert [item["item"] for item in response["recommendations"]] == ["C", "D"]


def test_fallbacks_are_explicit() -> None:
    assert recommend([], {}, ["A", "B"], k=1)["source"] == "empty_basket_popularity"
    assert recommend(["X"], {}, ["A", "B"], k=1)["source"] == "no_match_popularity"


def test_holdout_cases_constructs_context_before_target() -> None:
    frame = pd.DataFrame(
        {
            "invoice_no": ["1", "1", "1", "2"],
            "stock_code": ["A", "B", "C", "D"],
            "invoice_date": pd.to_datetime(["2020-01-01"] * 4),
        }
    )
    assert holdout_cases(frame) == [(["A"], {"B", "C"})]


def test_mine_rules_enforces_minimum_lift_floor() -> None:
    baskets = pd.DataFrame(
        {
            "A": [True, True, True, False, False, False],
            "B": [True, True, False, True, False, False],
            "C": [True, False, True, True, True, False],
        }
    )
    rules, metadata = mine_rules(
        baskets,
        min_support=0.15,
        min_confidence=0.1,
        min_lift=1.1,
    )
    assert not rules.empty
    assert (rules["lift"] >= 1.1).all()
    assert metadata["min_lift"] == 1.1
    assert metadata["rules_removed_by_lift_filter"] > 0
