"""Tests for v0.6.0 credit modeling additions.

Discrimination metrics, LGD backtest, calibration curve, champion/challenger,
explainability and grade-level migration.  Deterministic (seed=42 throughout).
"""

import numpy as np
import pandas as pd
import pytest

from risk_lib.data_gen import generate_portfolio, split_train_test
from risk_lib.models.discrimination import (
    auc_roc, auprc, brier_score, kupiec_pof, christoffersen_independence,
    christoffersen_cc, calibration_curve, discrimination_summary,
)
from risk_lib.models.lgd_model import (
    fit_lgd_model, lgd_backtest, lgd_bucket_calibration,
)
from risk_lib.models.pd_model import fit_pd_model, gini
from risk_lib.models.explain import (
    coefficient_table, permutation_importance,
    grade_migration_psi, grade_transition_matrix, master_scale_calibration,
)
from risk_lib.models.rating import pd_to_rating


# -------------------------------------------------- discrimination metrics


def test_auc_perfect_and_inverted():
    y = np.array([0, 0, 1, 1])
    assert auc_roc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert auc_roc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)


def test_auc_matches_2_x_gini_plus_one_over_two():
    rng = np.random.default_rng(7)
    y = rng.integers(0, 2, 400)
    s = rng.random(400) + 0.6 * y     # positive signal
    auc = auc_roc(y, s)
    g = gini(y, s)
    assert auc == pytest.approx((g + 1) / 2, abs=1e-9)


def test_auprc_higher_for_signal_than_random():
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.3).astype(int)
    rand = rng.random(500)
    signal = rand + 0.8 * y
    assert auprc(y, signal) > auprc(y, rand)


def test_brier_score_zero_for_perfect():
    y = np.array([0, 1, 0, 1])
    p = y.astype(float)
    assert brier_score(y, p) == pytest.approx(0.0)


def test_kupiec_pof_ok_under_h0():
    # observed default rate = expected pd → should NOT reject
    res = kupiec_pof(observed_defaults=20, n=200, expected_pd=0.10)
    assert res["p_value"] > 0.5


def test_kupiec_pof_rejects_severe_miscalibration():
    # observed default rate 30% with expected 5% → should reject
    res = kupiec_pof(observed_defaults=60, n=200, expected_pd=0.05)
    assert res["p_value"] < 0.01


def test_christoffersen_independence_high_p_for_iid():
    rng = np.random.default_rng(1)
    e = (rng.random(500) < 0.1).astype(int)
    res = christoffersen_independence(e)
    assert res["p_value"] > 0.05


def test_christoffersen_cc_returns_dof2_consistent():
    rng = np.random.default_rng(2)
    e = (rng.random(400) < 0.1).astype(int)
    res = christoffersen_cc(e, expected_pd=0.10)
    assert 0.0 <= res["p_value"] <= 1.0
    assert res["lr"] == pytest.approx(res["lr_uc"] + res["lr_ind"], abs=1e-9)


def test_calibration_curve_monotonic_for_well_fit_model():
    rng = np.random.default_rng(3)
    pd_v = rng.random(1000) * 0.5
    y = (rng.random(1000) < pd_v).astype(int)
    cal = calibration_curve(pd_v, y, n_bins=10)
    # mean_pd should be monotonically increasing across buckets
    assert (cal["mean_pd"].diff().dropna() >= 0).all()
    assert (cal["n"] > 0).all()


def test_discrimination_summary_keys():
    rng = np.random.default_rng(0)
    y = (rng.random(300) < 0.2).astype(int)
    s = rng.random(300) + 0.5 * y
    d = discrimination_summary(y, s)
    for k in ("auc_roc", "gini", "auprc", "brier", "brier_skill", "base_rate"):
        assert k in d


# -------------------------------------------------- LGD backtest


def test_lgd_backtest_perfect():
    y = np.array([0.1, 0.4, 0.6, 0.9])
    res = lgd_backtest(y, y)
    assert res["mae"] == pytest.approx(0.0)
    assert res["rmse"] == pytest.approx(0.0)
    assert res["bias"] == pytest.approx(0.0)
    assert res["r2"] == pytest.approx(1.0)


def test_lgd_backtest_bias_sign():
    y = np.array([0.2, 0.3, 0.4])
    p = y + 0.1
    res = lgd_backtest(y, p)
    assert res["bias"] == pytest.approx(0.1)
    assert res["mae"] == pytest.approx(0.1)


def test_lgd_bucket_calibration_columns():
    df = generate_portfolio(n_corporate=300, n_retail=0, n_mortgage=0,
                            n_sovereign=0, n_bank=0)
    feats = ["leverage", "current_ratio", "log_assets", "interest_coverage"]
    model = fit_lgd_model(df, feats)
    p = model.predict_lgd(df)
    cal = lgd_bucket_calibration(df["lgd_realized"].values, p, n_bins=5)
    assert {"bucket", "n", "mean_pred", "mean_realised", "bias"} <= set(cal.columns)
    assert cal["n"].sum() == len(df)


# -------------------------------------------------- backtest report integration


def test_pd_backtest_report_new_keys():
    from risk_lib import run_pipeline
    r = run_pipeline(seed=42)
    bt = r.backtest
    for k in ("discrimination", "kupiec_pof", "christoffersen_cc",
              "calibration_curve"):
        assert k in bt, f"missing key {k}"
    assert 0 <= bt["discrimination"]["auc_roc"] <= 1


# -------------------------------------------------- explainability


def _fit_corp_model():
    df = generate_portfolio(n_corporate=600, n_retail=0, n_mortgage=0,
                            n_sovereign=0, n_bank=0)
    train, test = split_train_test(df, test_frac=0.3)
    feats = ["leverage", "current_ratio", "log_assets",
             "interest_coverage", "gdp_growth"]
    model = fit_pd_model(train, feats, target="default_12m")
    return model, train, test


def test_coefficient_table_signs_and_contributions():
    model, train, _ = _fit_corp_model()
    tab = coefficient_table(model)
    assert set(tab.columns) >= {"feature", "coef", "odds_ratio",
                                "abs_effect", "direction", "contribution_pct"}
    assert tab["contribution_pct"].sum() == pytest.approx(1.0, abs=1e-9)
    # leverage should increase risk (positive direction)
    row = tab[tab["feature"] == "leverage"].iloc[0]
    assert row["coef"] > 0


def test_permutation_importance_top_feature_dominant():
    model, _, test = _fit_corp_model()
    imp = permutation_importance(model, test, n_repeats=3, seed=42)
    # most important feature has the largest drop
    assert imp["gini_drop_mean"].iloc[0] == imp["gini_drop_mean"].max()
    # all features listed
    assert set(imp["feature"]) == set(model.features)


def test_grade_migration_psi_stable_when_same_pop():
    df = generate_portfolio(n_corporate=400, n_retail=0, n_mortgage=0,
                            n_sovereign=0, n_bank=0)
    df["grade"] = [pd_to_rating(p).grade for p in df["pd"]]
    res = grade_migration_psi(df["grade"], df["grade"])
    assert res["psi"] < 1e-6
    assert res["zone"] == "GREEN"


def test_grade_transition_matrix_diagonal_when_no_change():
    df = generate_portfolio(n_corporate=200, n_retail=0, n_mortgage=0,
                            n_sovereign=0, n_bank=0)
    grades = pd.Series([pd_to_rating(p).grade for p in df["pd"]])
    mat = grade_transition_matrix(grades, grades)
    # diagonal should be 1.0
    diag = mat[mat["from_grade"] == mat["to_grade"]]
    nonzero = diag[diag["n"] > 0]["pct"].tolist()
    assert nonzero == pytest.approx([1.0] * len(nonzero))


def test_master_scale_calibration_columns():
    from risk_lib import run_pipeline
    r = run_pipeline(seed=42)
    corp = r.backtest
    # use the pipeline portfolio_summary path: just call directly
    cal = r.calibration["corporate"]
    assert {"grade", "pd_midpoint", "mean_pd_predicted",
            "realised_dr", "n", "bias"} <= set(cal.columns)
    assert (cal["n"] > 0).all()
