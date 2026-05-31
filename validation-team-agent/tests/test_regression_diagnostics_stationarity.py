import numpy as np
import pytest

from tools import regression_diagnostics as rd


def test_adf_detects_stationary_white_noise():
    rng = np.random.default_rng(0)
    x = rng.normal(size=300)
    out = rd.adf_test(x)
    assert out["test"] == "ADF"
    assert out["stationary"] is True
    assert "1%" in out["critical_values"]


def test_adf_detects_random_walk_as_nonstationary():
    rng = np.random.default_rng(1)
    rw = np.cumsum(rng.normal(size=300))
    out = rd.adf_test(rw)
    assert out["stationary"] is False


def test_kpss_consistent_with_adf_on_stationary():
    rng = np.random.default_rng(2)
    x = rng.normal(size=300)
    out = rd.kpss_test(x)
    assert out["test"] == "KPSS"
    assert out["stationary"] is True


def test_stationarity_summary_label_for_random_walk():
    rng = np.random.default_rng(3)
    rw = np.cumsum(rng.normal(size=300))
    summary = rd.stationarity_summary(rw)
    assert summary["label"] in {
        "non_stationary",
        "inconclusive_likely_non_stationary",
    }


def test_adf_rejects_short_series():
    with pytest.raises(ValueError):
        rd.adf_test([1.0, 2.0, 3.0])


def test_kpss_rejects_nan():
    with pytest.raises(ValueError):
        rd.kpss_test([1.0, float("nan"), 3.0] * 5)
