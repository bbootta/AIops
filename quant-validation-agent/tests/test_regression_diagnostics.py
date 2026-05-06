import numpy as np
import pandas as pd
import pytest

from tools import regression_diagnostics as rd


def _toy_data(seed=7):
    rng = np.random.default_rng(seed)
    n = 200
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    x3 = x1 * 0.9 + rng.normal(0, 0.1, n)  # collinear with x1
    y = 1.0 + 0.5 * x1 - 0.3 * x2 + rng.normal(0, 0.5, n)
    X = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
    return y, X


def test_vif_detects_multicollinearity():
    _, X = _toy_data()
    vif = rd.calculate_vif(X)
    # x1 and x3 are collinear, both should have high VIF
    by_var = vif.set_index("variable")["vif"]
    assert by_var["x1"] > 5
    assert by_var["x3"] > 5
    # x2 should be near 1
    assert by_var["x2"] < 3


def test_fit_ols_and_summary():
    y, X = _toy_data()
    res = rd.fit_ols(y, X)
    summary = rd.extract_regression_summary(res)
    assert summary["n"] == 200
    assert 0.0 <= summary["r_squared"] <= 1.0


def test_check_pvalues_returns_dataframe():
    y, X = _toy_data()
    res = rd.fit_ols(y, X)
    out = rd.check_pvalues(res, threshold=0.05)
    assert "significant_at_threshold" in out.columns


def test_check_coefficient_signs():
    y, X = _toy_data()
    res = rd.fit_ols(y, X)
    out = rd.check_coefficient_signs(res, {"x1": "+", "x2": "-"})
    assert "match" in out.columns


def test_condition_index_is_finite_positive():
    _, X = _toy_data()
    out = rd.check_condition_index(X)
    assert out["max_condition_index"] > 0
    assert np.isfinite(out["max_condition_index"])


def test_residual_basic():
    y, X = _toy_data()
    res = rd.fit_ols(y, X)
    r = rd.check_residual_basic(res)
    assert r["n"] == 200
    assert abs(r["mean"]) < 1e-6


def _autocorrelated_data(seed=11):
    rng = np.random.default_rng(seed)
    n = 200
    x = rng.normal(0, 1, n)
    eps = np.zeros(n)
    eps[0] = rng.normal()
    for i in range(1, n):
        eps[i] = 0.85 * eps[i - 1] + rng.normal(0, 0.5)
    y = 1.0 + 0.5 * x + eps
    X = pd.DataFrame({"x": x})
    return y, X


def test_durbin_watson_iid_near_two():
    y, X = _toy_data()
    res = rd.fit_ols(y, X)
    dw = rd.calculate_durbin_watson(res)
    assert 1.5 < dw < 2.5


def test_durbin_watson_autocorrelated_below_two():
    y, X = _autocorrelated_data()
    res = rd.fit_ols(y, X)
    dw = rd.calculate_durbin_watson(res)
    assert dw < 1.5


def test_breusch_godfrey_detects_autocorrelation():
    y, X = _autocorrelated_data()
    res = rd.fit_ols(y, X)
    out = rd.calculate_breusch_godfrey(res, lags=2)
    assert "lm_pvalue" in out
    assert out["lm_pvalue"] < 0.05


def test_breusch_godfrey_invalid_lags():
    y, X = _toy_data()
    res = rd.fit_ols(y, X)
    with pytest.raises(ValueError):
        rd.calculate_breusch_godfrey(res, lags=0)


def test_arch_test_returns_keys():
    y, X = _toy_data()
    res = rd.fit_ols(y, X)
    out = rd.calculate_arch_test(res, lags=1)
    assert {"lm_stat", "lm_pvalue", "f_stat", "f_pvalue"}.issubset(out.keys())
