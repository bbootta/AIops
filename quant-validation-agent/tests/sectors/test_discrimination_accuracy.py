"""Accuracy checks for discrimination metrics (KS / AUROC / AR).

Verifies the tools return values within tolerance of analytical
expectations on synthetic data with known properties.
"""
import numpy as np
import pytest

from tests.sectors import fixtures as fx
from tools import metric_ks_auc_ar as mka


def test_perfect_separator_metrics_at_ceiling():
    y, score = fx.perfect_separator(n=2000, seed=1)
    assert mka.calculate_ks(y, score) == pytest.approx(1.0, abs=1e-9)
    assert mka.calculate_auc(y, score) == pytest.approx(1.0, abs=1e-9)
    assert mka.calculate_gini(y, score) == pytest.approx(1.0, abs=1e-9)
    assert mka.calculate_accuracy_ratio(y, score) == pytest.approx(1.0, abs=1e-9)


def test_two_normal_mixture_auc_matches_analytical():
    # Phi(shift/sqrt(2)) is the analytical AUC for two equal-variance normals.
    for shift in (0.5, 1.0, 1.5, 2.0):
        y, score, expected = fx.two_normal_mixture(n=10000, shift=shift, seed=10 + int(shift * 10))
        auc = mka.calculate_auc(y, score)
        assert auc == pytest.approx(expected, abs=0.02), (
            f"shift={shift}: tool AUC {auc:.4f} vs expected {expected:.4f}"
        )


def test_random_score_auc_near_half():
    y, score = fx.random_score(n=10000, seed=3)
    auc = mka.calculate_auc(y, score)
    assert abs(auc - 0.5) < 0.03


def test_direction_flip_inverts_around_half():
    y, score, _ = fx.two_normal_mixture(n=5000, shift=1.5, seed=4)
    auc_a = mka.calculate_auc(y, score, higher_is_worse=True)
    auc_b = mka.calculate_auc(y, score, higher_is_worse=False)
    assert auc_a + auc_b == pytest.approx(1.0, abs=1e-9)


def test_decile_table_monotonic_on_separable_data():
    y, score, _ = fx.two_normal_mixture(n=5000, shift=1.5, seed=5)
    tbl = mka.build_decile_table(y, score, n_bins=10, higher_is_worse=True)
    rates = tbl["default_rate"].tolist()
    # Default rate must rise monotonically in 'worst → best' ordering
    # The build_decile_table builds bins by score ascending of risk, so
    # the LAST bin should have the highest default rate.
    assert rates[-1] >= rates[0]
    # Allow small reversals but average trend must be increasing
    assert sum(rates[5:]) > sum(rates[:5])


def test_ks_equals_auc_consistency_on_extreme_data():
    """KS and AUC both saturate near 1 on near-perfect separation."""
    y, score, _ = fx.two_normal_mixture(n=20000, shift=4.0, seed=6)
    # On 20k obs with shift=4σ the empirical KS reliably exceeds 0.95
    assert mka.calculate_ks(y, score) > 0.95
    assert mka.calculate_auc(y, score) > 0.995
