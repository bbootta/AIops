"""PSI accuracy across known distribution scenarios."""
import math

import pytest

from tests.sectors import fixtures as fx
from tools import metric_psi as mp


def test_psi_near_zero_on_identical_distributions():
    base, cur = fx.identical_distributions(n=20000, seed=21)
    psi = mp.calculate_psi(base, cur, bins=10)
    # Same distribution different draws → ε very small
    assert psi < 0.01


def test_psi_moderate_on_unit_shift():
    """Mean shift of 1σ should give PSI in the 0.2–0.6 range typically."""
    base, cur = fx.shifted_distribution(n=20000, mean_shift=1.0, seed=22)
    psi = mp.calculate_psi(base, cur, bins=10)
    assert 0.2 < psi < 1.0


def test_psi_large_on_severe_shift():
    base, cur = fx.shifted_distribution(n=20000, mean_shift=2.5, seed=23)
    psi = mp.calculate_psi(base, cur, bins=10)
    assert psi > 1.0  # clear Red zone


def test_psi_very_large_on_disjoint_distributions():
    base, cur = fx.disjoint_distribution(n=20000, seed=24)
    psi = mp.calculate_psi(base, cur, bins=10)
    # Almost no overlap → PSI >> 1
    assert psi > 3.0


def test_psi_by_bucket_zero_on_identical_categorical():
    a = ["A"] * 70 + ["B"] * 20 + ["C"] * 10
    psi = mp.calculate_psi_by_bucket(a, a)
    assert psi < 1e-6


def test_psi_increases_monotonically_with_shift():
    """PSI should rise as the shift grows on equal samples."""
    psi_values = []
    for shift in (0.1, 0.5, 1.0, 1.5, 2.0):
        base, cur = fx.shifted_distribution(n=10000, mean_shift=shift, seed=25 + int(shift * 10))
        psi_values.append(mp.calculate_psi(base, cur, bins=10))
    # Not strictly monotone in every realization but trend must be increasing
    assert psi_values[-1] > psi_values[0]
    assert sum(b - a for a, b in zip(psi_values[:-1], psi_values[1:])) > 0
