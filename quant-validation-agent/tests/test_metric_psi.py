import numpy as np
import pytest

from tools import metric_psi as m


def test_psi_zero_for_identical_distributions():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=2000)
    psi = m.calculate_psi(x, x, bins=10)
    assert psi < 1e-6


def test_psi_increases_with_shift():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=2000)
    y = rng.normal(1.0, 1, size=2000)
    psi = m.calculate_psi(x, y, bins=10)
    assert psi > 0.05


def test_psi_no_division_by_zero_when_bucket_empty():
    rng = np.random.default_rng(1)
    expected = rng.normal(0, 1, size=1000)
    actual = rng.normal(5, 0.1, size=1000)  # forces some empty buckets in expected edges
    psi = m.calculate_psi(expected, actual, bins=10, epsilon=1e-6)
    assert psi >= 0.0
    assert np.isfinite(psi)


def test_psi_by_bucket():
    base = ["A"] * 70 + ["B"] * 20 + ["C"] * 10
    cur = ["A"] * 50 + ["B"] * 30 + ["C"] * 20
    psi = m.calculate_psi_by_bucket(base, cur)
    assert psi > 0


def test_psi_zero_epsilon_rejected():
    with pytest.raises(ValueError):
        m.calculate_psi([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], bins=2, epsilon=0)


def test_psi_inf_result_raises():
    """Constant-value distributions with bins=2 collapse to a single edge → ValueError."""
    with pytest.raises(ValueError):
        m.calculate_psi([1.0] * 100, [1.0] * 100, bins=2)


def test_distribution_table_columns():
    rng = np.random.default_rng(2)
    e = rng.normal(0, 1, size=500)
    a = rng.normal(0.2, 1, size=500)
    tbl = m.build_distribution_table(e, a, bins=5)
    assert {"expected_ratio", "actual_ratio", "psi_contribution"}.issubset(tbl.columns)
    assert (tbl["expected_ratio"].sum() <= 1.0 + 1e-9) and (tbl["expected_ratio"].sum() > 0)
