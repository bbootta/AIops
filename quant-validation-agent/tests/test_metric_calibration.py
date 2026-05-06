import numpy as np
import pandas as pd
import pytest

from tools import metric_calibration as m


def _make_pd_df(seed=0):
    rng = np.random.default_rng(seed)
    n = 500
    pred_pd = np.clip(rng.beta(2, 8, size=n), 1e-4, 1 - 1e-4)
    realized = (rng.uniform(0, 1, size=n) < pred_pd).astype(int)
    return pd.DataFrame({"pred_pd": pred_pd, "default": realized})


def test_build_calibration_table_quantile_bins():
    df = _make_pd_df()
    tbl = m.build_calibration_table(df, "pred_pd", "default", n_bins=5)
    assert {"count", "mean_pred", "mean_actual", "diff"}.issubset(tbl.columns)
    assert tbl.shape[0] <= 5


def test_build_calibration_table_with_bucket():
    df = _make_pd_df()
    df["bucket"] = pd.qcut(df["pred_pd"], 4, labels=["q1", "q2", "q3", "q4"])
    tbl = m.build_calibration_table(df, "pred_pd", "default", bucket_col="bucket")
    assert tbl.shape[0] == 4


def test_brier_score_range():
    df = _make_pd_df()
    bs = m.calculate_brier_score(df["default"].tolist(), df["pred_pd"].tolist())
    assert 0.0 <= bs <= 1.0


def test_brier_score_rejects_out_of_range_pd():
    with pytest.raises(ValueError):
        m.calculate_brier_score([0, 1, 0], [0.1, 1.5, 0.4])


def test_pd_bias_returns_zero_division_friendly():
    df = pd.DataFrame({"pred_pd": [0.1, 0.2], "default": [0, 0]})
    out = m.calculate_pd_bias(df, "pred_pd", "default")
    assert abs(out["mean_predicted_pd"] - 0.15) < 1e-9
    assert out["observed_default_rate"] == 0.0
    # rel_bias should be NaN
    assert np.isnan(out["rel_bias"])


def test_summarize_observed_vs_predicted():
    df = _make_pd_df()
    df["grp"] = (df["pred_pd"] > df["pred_pd"].median()).astype(int)
    out = m.summarize_observed_vs_predicted(df, "pred_pd", "default", "grp")
    assert out.shape[0] == 2
    assert {"mean_pred", "mean_actual", "diff"}.issubset(out.columns)
