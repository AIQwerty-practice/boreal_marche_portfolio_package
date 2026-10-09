import numpy as np

from boreal_marche.modeling.tune import profit_curve


def test_profit_curve_is_complete_and_scenario_based() -> None:
    curve = profit_curve(
        np.array([0.1, 0.5, 0.9]),
        {
            "gross_margin_per_incremental_purchase": 30.0,
            "incentive_cost_per_purchase": 5.0,
            "contact_cost": 1.0,
            "recovery_fraction_of_non_returners": 0.2,
        },
    )
    assert len(curve) == 201
    assert curve.iloc[0]["customers_contacted"] == 0
    assert curve.iloc[-1]["customers_contacted"] == 3
    assert np.isfinite(curve["estimated_incremental_profit"]).all()

