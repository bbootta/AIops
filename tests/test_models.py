import numpy as np
import pandas as pd
import pytest

from risk_lib.data_gen import generate_portfolio, split_train_test
from risk_lib.models.pd_model import fit_pd_model, gini, ks_statistic, psi
from risk_lib.models.lgd_model import workout_lgd, fit_lgd_model
from risk_lib.models.rating import (
    DEFAULT_MASTER_SCALE, pd_to_rating, rating_to_pd_midpoint,
)


def test_pd_model_learns_signal():
    df = generate_portfolio(n_corporate=1000, n_retail=0, n_mortgage=0,
                            n_sovereign=0, n_bank=0)
    train, test = split_train_test(df, test_frac=0.3)
    feats = ["leverage", "current_ratio", "log_assets",
             "interest_coverage", "gdp_growth"]
    model = fit_pd_model(train, feats, target="default_12m")
    p_test = model.predict_pd(test)
    g = gini(test["default_12m"].values, p_test)
    assert g > 0.35, f"Gini={g} too low"


def test_pd_recalibration_centres_mean():
    df = generate_portfolio(n_corporate=600, n_retail=0, n_mortgage=0,
                            n_sovereign=0, n_bank=0)
    feats = ["leverage", "current_ratio", "log_assets",
             "interest_coverage", "gdp_growth"]
    model = fit_pd_model(df, feats, target="default_12m", central_tendency=0.15)
    p = model.predict_pd(df)
    p_cal = model.recalibrate(p)
    assert abs(p_cal.mean() - 0.15) < 0.005


def test_gini_perfect_and_random():
    y = np.array([0, 0, 1, 1])
    assert gini(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 1000)
    g = gini(y, rng.random(1000))
    assert abs(g) < 0.1  # near zero for random


def test_ks_in_range():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 500)
    s = rng.random(500)
    k = ks_statistic(y, s)
    assert 0 <= k <= 1


def test_psi_stable_vs_shifted():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 5000)
    b = rng.normal(0, 1, 5000)
    p_stable = psi(a, b)
    c = rng.normal(2, 1, 5000)
    p_shift = psi(a, c)
    assert p_shift > p_stable
    assert p_stable < 0.10  # commonly used "stable" threshold


def test_workout_lgd_full_recovery():
    lgd = workout_lgd(100.0, [(0.0, 100.0)], discount_rate=0.05)
    assert lgd == pytest.approx(0.0)


def test_workout_lgd_partial_with_discount():
    lgd = workout_lgd(100.0, [(1.0, 50.0)], workout_costs=5.0,
                      discount_rate=0.05)
    # PV recoveries = 50/1.05 - 5 = 42.619
    assert lgd == pytest.approx(1 - (50 / 1.05 - 5) / 100, abs=1e-6)


def test_lgd_model_outputs_within_bounds():
    df = generate_portfolio(n_corporate=400, n_retail=0, n_mortgage=0,
                            n_sovereign=0, n_bank=0)
    feats = ["leverage", "current_ratio", "log_assets", "interest_coverage"]
    model = fit_lgd_model(df, feats, target="lgd_realized")
    out = model.predict_lgd(df)
    assert (out >= model.floor - 1e-9).all()
    assert (out <= 1.0 + 1e-9).all()


def test_rating_scale_monotone_and_complete():
    uppers = [g.pd_upper for g in DEFAULT_MASTER_SCALE]
    assert uppers == sorted(uppers)
    assert DEFAULT_MASTER_SCALE[0].pd_lower == 0.0
    assert DEFAULT_MASTER_SCALE[-1].pd_upper > 1.0


def test_rating_round_trip_in_bucket():
    g = pd_to_rating(0.014)
    assert g.grade == "BBB"
    assert g.pd_midpoint == rating_to_pd_midpoint("BBB")
