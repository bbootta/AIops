"""Decile lift accuracy."""
import pytest

from tests.sectors import fixtures as fx
from tools import decile_lift as dl
from tools.metric_ks_auc_ar import calculate_ks


def test_top_decile_lift_high_on_separable_data():
    """Standard cumulative lift = cum_default_share / cum_pop_share.
    Cumulative lift at the bottom of the table equals 1.0 exactly."""
    y, score, _ = fx.two_normal_mixture(n=10000, shift=2.0, seed=70)
    lift = dl.build_lift_table(y, score, n_bins=10, higher_is_worse=True)
    assert lift.iloc[0]["lift"] > 2.0
    assert lift.iloc[-1]["lift"] == pytest.approx(1.0, abs=1e-9)


def test_random_score_lift_near_one():
    """Random scoring → cumulative lift near 1.0 across all deciles."""
    y, score = fx.random_score(n=20000, bad_rate=0.3, seed=71)
    lift = dl.build_lift_table(y, score, n_bins=10, higher_is_worse=True)
    assert abs(lift["lift"].mean() - 1.0) < 0.1
    assert lift.iloc[0]["lift"] < 1.3


def test_perfect_separator_top_decile_lift_matches_formula():
    """With perfect separation and base rate p, top decile lift =
    min(1/p, 10) — the maximum possible cumulative lift in the top 10%."""
    y, score = fx.perfect_separator(n=1000, seed=72)
    base_rate = float(y.sum()) / y.shape[0]
    lift = dl.build_lift_table(y, score, n_bins=10, higher_is_worse=True)
    expected_top = min(1.0 / base_rate, 10.0)
    assert lift.iloc[0]["lift"] == pytest.approx(expected_top, abs=0.5)
    assert lift.iloc[0]["lift"] > 1.5


def test_ks_plot_max_equals_calculate_ks():
    y, score, _ = fx.two_normal_mixture(n=5000, shift=1.5, seed=73)
    coords = dl.ks_plot_coordinates(y, score, higher_is_worse=True)
    ks_plot = float(coords["ks_distance"].max())
    ks_metric = calculate_ks(y, score, higher_is_worse=True)
    assert abs(ks_plot - ks_metric) < 1e-9
