import numpy as np
import pandas as pd
import pytest

from tools import backtest_traffic_light as btl


def test_classify_zone_basic():
    assert btl.classify_zone(0.5) == "Green"
    assert btl.classify_zone(0.01) == "Yellow"
    assert btl.classify_zone(1e-6) == "Red"
    assert btl.classify_zone(float("nan")) == "Gray"


def test_classify_zone_rejects_inverted_alpha():
    with pytest.raises(ValueError):
        btl.classify_zone(0.5, alpha_green=0.0001, alpha_red=0.05)


def test_traffic_light_well_calibrated_is_green():
    # 1000 obs, predicted PD 0.02, observed 20 defaults. Right at the mean.
    df = pd.DataFrame({"n": [1000], "defaults": [20], "p": [0.02]})
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "p")
    assert out.iloc[0]["zone"] in {"Green", "Yellow"}
    assert 0.0 < out.iloc[0]["pvalue"] <= 1.0


def test_traffic_light_severe_under_prediction_is_red():
    # 1000 obs, predicted PD 0.02 but observed 200 defaults → severe under-prediction
    df = pd.DataFrame({"n": [1000], "defaults": [200], "p": [0.02]})
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "p")
    assert out.iloc[0]["zone"] == "Red"


def test_traffic_light_per_bucket_aggregates():
    df = pd.DataFrame({
        "grade": ["A", "B"],
        "n": [1000, 800],
        "defaults": [25, 200],  # B is severely under-predicted
        "p": [0.02, 0.05],
    })
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "p", bucket_col="grade")
    assert set(out["bucket"]) == {"A", "B"}
    assert btl.aggregate_zone(out) == "Red"


def test_traffic_light_handles_zero_predicted_pd():
    df = pd.DataFrame({"n": [100], "defaults": [0], "p": [0.0]})
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "p")
    # 0 defaults under p=0 is unconditionally consistent
    assert out.iloc[0]["zone"] == "Green"


def test_traffic_light_missing_columns():
    df = pd.DataFrame({"n": [1], "defaults": [0]})
    with pytest.raises(ValueError):
        btl.traffic_light_per_bucket(df, "n", "defaults", "no_such_col")
