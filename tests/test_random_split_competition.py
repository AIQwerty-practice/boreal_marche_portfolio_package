from __future__ import annotations

import pandas as pd

from boreal_marche.modeling.random_split_competition import _partition


def test_customer_group_split_is_seeded_and_disjoint() -> None:
    frame = pd.DataFrame(
        {
            "customer_id": [f"C{customer}" for customer in range(30) for _ in range(3)],
            "target_return_90d": [customer % 2 for customer in range(30) for _ in range(3)],
        }
    )
    left, right = _partition(frame, 0.20, 42)
    again_left, again_right = _partition(frame, 0.20, 42)
    assert set(left.customer_id).isdisjoint(right.customer_id)
    assert set(left.customer_id) == set(again_left.customer_id)
    assert set(right.customer_id) == set(again_right.customer_id)
    assert len(right.customer_id.unique()) == 6
