from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from test_api import services

from boreal_marche.api.app import create_app
from boreal_marche.monitoring.drift import analyze_batch, build_baseline


def reference_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "snapshot_role": ["train"] * 50 + ["validation"] * 50,
        "recency_days": np.arange(100, dtype=float),
        "frequency_orders": np.arange(100, dtype=float) % 15 + 1,
        "monetary_total": np.arange(100, dtype=float) * 20 + 50,
        "unique_products": np.arange(100, dtype=float) % 30 + 1,
    })


def test_reference_rejects_protected_test_and_contains_only_aggregates() -> None:
    frame = reference_frame()
    baseline = build_baseline(frame, np.linspace(0.1, 0.9, 100), "official")
    assert baseline["snapshot_roles"] == ["train", "validation"]
    assert baseline["development_rows"] == 100
    assert "customer_id" not in str(baseline)
    frame.loc[0, "snapshot_role"] = "test"
    with pytest.raises(ValueError, match="Protected"):
        build_baseline(frame, np.linspace(0.1, 0.9, 100), "official")


def test_shifted_valid_batch_has_more_feature_drift() -> None:
    frame = reference_frame()
    scores = np.linspace(0.1, 0.9, 100)
    baseline = build_baseline(frame, scores, "official")
    normal = analyze_batch(baseline, frame, scores)
    shifted_frame = frame.copy()
    shifted_frame["recency_days"] = 350.0
    shifted = analyze_batch(baseline, shifted_frame, scores)
    assert normal["status"] == "stable"
    assert normal["score_status"] == "stable"
    assert shifted["status"] == "high"
    assert shifted["metrics"][0]["psi"] > normal["metrics"][0]["psi"]
    assert shifted["metrics"][0]["out_of_range_rate"] == 1.0
    assert analyze_batch(baseline, frame.head(20), scores[:20])["status"] == "insufficient"
    score_only_shift = analyze_batch(baseline, frame, np.full(100, 0.9))
    assert score_only_shift["status"] == "stable"
    assert score_only_shift["score_status"] == "high"


def test_drift_demo_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOREAL_ENABLE_DRIFT_DEMO", raising=False)
    with TestClient(create_app(services=services())) as client:
        assert client.get("/monitoring/drift/reference").json()["enabled"] is False
        assert client.post("/monitoring/drift/demo", json={"records": [{"features": {"recency_days": 1}}]}).status_code == 503


def test_enabled_drift_endpoint_uses_official_model_only(monkeypatch: pytest.MonkeyPatch) -> None:
    class Model:
        def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
            return np.tile([0.7, 0.3], (len(frame), 1))

    monkeypatch.setenv("BOREAL_ENABLE_DRIFT_DEMO", "1")
    configured = services()
    configured.model = Model()
    configured.feature_names = [
        "recency_days", "frequency_orders", "monetary_total", "unique_products", "primary_country"
    ]
    configured.drift_baseline = build_baseline(reference_frame(), np.full(100, 0.3), "test-model")
    record = {"features": {
        "recency_days": 35, "frequency_orders": 3, "monetary_total": 500,
        "unique_products": 20, "primary_country": "United Kingdom",
    }}
    with TestClient(create_app(services=configured)) as client:
        reference = client.get("/monitoring/drift/reference").json()
        assert reference["snapshot_roles"] == ["train", "validation"]
        assert "recency_days" in reference["features"]
        response = client.post("/monitoring/drift/demo", json={"records": [record] * 100})
        assert response.status_code == 200
        assert response.json()["sample_count"] == 100
        assert response.json()["synthetic_demo_only"] is True
        wrong_model = {**record, "model_variant": "random_80_20"}
        assert client.post("/monitoring/drift/demo", json={"records": [wrong_model]}).status_code == 422
