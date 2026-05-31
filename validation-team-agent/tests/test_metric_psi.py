import numpy as np
import pytest

from tools import metric_psi as psi


def test_psi_zero_for_same_distribution():
    rng = np.random.default_rng(1)
    x = rng.normal(size=2000)
    out = psi.calculate_psi(x, x, bins=10)
    assert out["psi"] < 1e-6
    assert out["n_expected"] == 2000
    assert out["n_actual"] == 2000


def test_psi_increases_with_drift():
    rng = np.random.default_rng(2)
    expected = rng.normal(loc=0, scale=1, size=2000)
    drifted = rng.normal(loc=1.5, scale=1, size=2000)
    out = psi.calculate_psi(expected, drifted, bins=10)
    assert out["psi"] > 0.25


def test_psi_no_zero_division_with_empty_bin():
    rng = np.random.default_rng(3)
    expected = rng.uniform(0, 1, size=1000)
    actual = rng.uniform(2, 3, size=1000)
    out = psi.calculate_psi(expected, actual, bins=10)
    assert np.isfinite(out["psi"])


def test_psi_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        psi.calculate_psi([], [1.0, 2.0])
    with pytest.raises(ValueError):
        psi.calculate_psi([1.0, 2.0], [1.0, 2.0], bins=1)
    with pytest.raises(ValueError):
        psi.calculate_psi([1.0, np.nan], [1.0, 2.0])


def test_psi_by_bucket_basic():
    expected = ["A", "A", "B", "B", "C"]
    actual = ["A", "B", "B", "C", "C"]
    out = psi.calculate_psi_by_bucket(expected, actual)
    assert out["categories"] == ["A", "B", "C"]
    assert out["n_expected"] == 5
    assert out["n_actual"] == 5
    assert np.isfinite(out["psi"])
