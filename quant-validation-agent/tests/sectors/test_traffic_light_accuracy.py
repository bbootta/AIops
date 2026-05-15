"""Backtest traffic-light zoning accuracy on known binomial inputs."""
import pytest

from tests.sectors import fixtures as fx
from tools import backtest_traffic_light as btl


def test_calibrated_sample_is_green():
    df = fx.traffic_light_calibrated()
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "pred_pd")
    # observed default rate 100/5000 = 0.02 == predicted; p ≈ 0.5
    assert out.iloc[0]["zone"] == "Green"
    assert out.iloc[0]["pvalue"] > 0.4


def test_severe_under_prediction_is_red():
    df = fx.traffic_light_severe()
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "pred_pd")
    assert out.iloc[0]["zone"] == "Red"
    assert out.iloc[0]["pvalue"] < 1e-4


def test_borderline_under_prediction_is_yellow():
    # 30 defaults on 1000 obs at p=0.02 → expected 20, slight under-prediction.
    # P(X >= 30 | n=1000, p=0.02) lies between alpha_red=1e-4 and alpha_green=0.05.
    import pandas as pd
    df = pd.DataFrame({"n": [1000], "defaults": [30], "pred_pd": [0.02]})
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "pred_pd")
    assert out.iloc[0]["zone"] == "Yellow"


def test_aggregate_picks_worst_bucket():
    import pandas as pd
    df = pd.DataFrame({
        "grade": ["A", "B"],
        "n": [1000, 1000],
        "defaults": [20, 200],
        "pred_pd": [0.02, 0.02],
    })
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "pred_pd",
                                       bucket_col="grade")
    assert btl.aggregate_zone(out) == "Red"


def test_zero_defaults_with_zero_pred_is_green():
    import pandas as pd
    df = pd.DataFrame({"n": [100], "defaults": [0], "pred_pd": [0.0]})
    out = btl.traffic_light_per_bucket(df, "n", "defaults", "pred_pd")
    assert out.iloc[0]["zone"] == "Green"
