"""Accuracy checks for PD calibration metrics."""
import numpy as np
import pandas as pd
import pytest

from tests.sectors import fixtures as fx
from tools import calibration_test as ct
from tools import metric_calibration as mc


def test_brier_matches_expected_for_well_calibrated():
    """For perfectly calibrated PDs, E[Brier] = E[p*(1-p)]."""
    y, p = fx.well_calibrated_pd(n=20000, seed=11)
    brier = mc.calculate_brier_score(y, p)
    expected = float(np.mean(p * (1 - p)))
    # Sampling noise → 0.005 tolerance on N=20k
    assert brier == pytest.approx(expected, abs=0.005)


def test_pd_bias_close_to_zero_on_well_calibrated():
    y, p = fx.well_calibrated_pd(n=20000, seed=12)
    df = pd.DataFrame({"pred_pd": p, "default": y})
    out = mc.calculate_pd_bias(df, "pred_pd", "default")
    assert abs(out["abs_bias"]) < 0.005


def test_pd_bias_negative_when_predictions_too_low():
    """factor=0.5 → predicted is half of true PD → bias negative."""
    y, p = fx.miscalibrated_pd(n=20000, factor=0.5, seed=13)
    df = pd.DataFrame({"pred_pd": p, "default": y})
    out = mc.calculate_pd_bias(df, "pred_pd", "default")
    assert out["abs_bias"] < -0.02


def test_hl_does_not_reject_on_well_calibrated():
    y, p = fx.well_calibrated_pd(n=20000, seed=14)
    out = ct.hosmer_lemeshow_test(y, p, n_bins=10)
    assert out["pvalue"] > 0.05


def test_hl_rejects_strong_miscalibration():
    y, p = fx.miscalibrated_pd(n=20000, factor=0.5, seed=15)
    out = ct.hosmer_lemeshow_test(y, p, n_bins=10)
    assert out["pvalue"] < 0.01


def test_spiegelhalter_does_not_reject_on_well_calibrated():
    y, p = fx.well_calibrated_pd(n=20000, seed=16)
    out = ct.spiegelhalter_z_test(y, p)
    assert abs(out["z"]) < 2.5


def test_spiegelhalter_rejects_strong_miscalibration():
    y, p = fx.miscalibrated_pd(n=20000, factor=0.5, seed=17)
    out = ct.spiegelhalter_z_test(y, p)
    assert out["pvalue"] < 0.01


def test_calibration_table_quantile_means_in_range():
    y, p = fx.well_calibrated_pd(n=10000, seed=18)
    df = pd.DataFrame({"pred_pd": p, "default": y})
    tbl = mc.build_calibration_table(df, "pred_pd", "default", n_bins=10)
    # mean_actual within ~0.05 of mean_pred per quintile-or-so bin
    diffs = (tbl["mean_pred"] - tbl["mean_actual"]).abs()
    assert diffs.max() < 0.05, f"max bin diff {diffs.max()}"


def test_binomial_calibration_rarely_rejects_when_calibrated():
    y, p = fx.well_calibrated_pd(n=10000, seed=19)
    df = pd.DataFrame({"pred_pd": p, "default": y})
    df["bucket"] = pd.qcut(df["pred_pd"], 5, labels=["q1", "q2", "q3", "q4", "q5"])
    out = ct.binomial_calibration_test(df, "pred_pd", "default", "bucket", alpha=0.05)
    # 5 buckets, alpha=0.05 → expected false-positive ≤ 1; allow ≤ 2 for noise
    assert int(out["reject_h0"].sum()) <= 2
