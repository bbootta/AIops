"""ADF stationarity test accuracy on canonical processes."""
import pytest

from tests.sectors import fixtures as fx
from tools import scenario_regression_pipeline as srp


def test_white_noise_is_rejected_as_non_stationary():
    s = fx.white_noise_series(n=500, seed=51)
    out = srp.adf_stationarity_check(s, alpha=0.05)
    assert out["stationary_at_alpha"] is True
    assert out["pvalue"] < 0.05


def test_random_walk_not_classified_stationary():
    s = fx.random_walk_series(n=500, seed=52)
    out = srp.adf_stationarity_check(s, alpha=0.05)
    assert out["stationary_at_alpha"] is False


def test_too_short_raises():
    s = fx.white_noise_series(n=5)
    with pytest.raises(ValueError):
        srp.adf_stationarity_check(s)
