import numpy as np
import pandas as pd
import pytest

from tools import calibration_test as ct


def _well_calibrated(seed=0, n=2000):
    rng = np.random.default_rng(seed)
    p = np.clip(rng.beta(2, 8, size=n), 1e-3, 1 - 1e-3)
    y = (rng.uniform(size=n) < p).astype(int)
    return y, p


def _miscalibrated(seed=1, n=2000):
    """Predicted PDs are systematically too low compared to realized."""
    rng = np.random.default_rng(seed)
    p_true = np.clip(rng.beta(2, 8, size=n), 1e-3, 1 - 1e-3)
    y = (rng.uniform(size=n) < p_true).astype(int)
    p_pred = np.clip(p_true * 0.4, 1e-4, 1 - 1e-4)
    return y, p_pred


def test_hosmer_lemeshow_well_calibrated_high_pvalue():
    y, p = _well_calibrated()
    out = ct.hosmer_lemeshow_test(y, p, n_bins=10)
    assert out["pvalue"] > 0.05
    assert out["df"] >= 1


def test_hosmer_lemeshow_miscalibrated_rejects():
    y, p = _miscalibrated()
    out = ct.hosmer_lemeshow_test(y, p, n_bins=10)
    assert out["pvalue"] < 0.05


def test_hosmer_lemeshow_invalid_bins():
    with pytest.raises(ValueError):
        ct.hosmer_lemeshow_test([0, 1], [0.1, 0.2], n_bins=1)


def test_spiegelhalter_well_calibrated_high_pvalue():
    y, p = _well_calibrated()
    out = ct.spiegelhalter_z_test(y, p)
    assert abs(out["z"]) < 2.5
    assert out["pvalue"] > 0.01


def test_spiegelhalter_miscalibrated_rejects():
    y, p = _miscalibrated()
    out = ct.spiegelhalter_z_test(y, p)
    assert out["pvalue"] < 0.05


def test_binomial_calibration_test_per_bucket():
    rng = np.random.default_rng(2)
    n = 600
    p = np.clip(rng.beta(2, 8, size=n), 1e-3, 1 - 1e-3)
    y = (rng.uniform(size=n) < p).astype(int)
    df = pd.DataFrame({"pred": p, "y": y})
    df["bucket"] = pd.qcut(df["pred"], 5, labels=["q1", "q2", "q3", "q4", "q5"])
    out = ct.binomial_calibration_test(df, "pred", "y", "bucket")
    assert {"bucket", "n", "expected_pd", "pvalue", "reject_h0"}.issubset(out.columns)
    assert out.shape[0] == 5
    # Most buckets should NOT reject H0 under well-calibrated data.
    assert int(out["reject_h0"].sum()) <= 2


def test_binomial_calibration_invalid_alpha():
    df = pd.DataFrame({"p": [0.1], "y": [0], "b": ["a"]})
    with pytest.raises(ValueError):
        ct.binomial_calibration_test(df, "p", "y", "b", alpha=0.0)
