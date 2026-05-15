"""Regression diagnostics accuracy on collinear / orthogonal samples."""
import numpy as np
import pytest

from tests.sectors import fixtures as fx
from tools import regression_diagnostics as rd


def test_vif_high_on_collinear_pair():
    _, X = fx.collinear_features(n=300, seed=41)
    vif = rd.calculate_vif(X).set_index("variable")["vif"]
    # x1 and x3 share 90% of variance → VIF >> 5
    assert vif["x1"] > 5
    assert vif["x3"] > 5
    # x2 is independent → VIF near 1
    assert vif["x2"] < 2


def test_vif_near_one_on_orthogonal_features():
    _, X = fx.orthogonal_features(n=1000, seed=42)
    vif = rd.calculate_vif(X).set_index("variable")["vif"]
    for v in ("x1", "x2", "x3"):
        # All near 1; large sample keeps deviation small
        assert vif[v] < 1.15, f"VIF for {v} = {vif[v]}"


def test_condition_index_low_on_orthogonal():
    _, X = fx.orthogonal_features(n=1000, seed=43)
    out = rd.check_condition_index(X)
    assert out["max_condition_index"] < 1.3


def test_condition_index_elevated_on_collinear():
    _, X = fx.collinear_features(n=300, seed=44)
    out = rd.check_condition_index(X)
    # Strong collinearity → CI rises noticeably
    assert out["max_condition_index"] > 3


def test_r_squared_high_on_well_specified_model():
    y, X = fx.orthogonal_features(n=1000, seed=45)
    fit = rd.fit_ols(y, X)
    summ = rd.extract_regression_summary(fit)
    assert summ["r_squared"] > 0.15  # signal dominates noise σ=0.5


def test_p_values_significant_for_strong_predictors():
    y, X = fx.orthogonal_features(n=2000, seed=46)
    fit = rd.fit_ols(y, X)
    df = rd.check_pvalues(fit, threshold=0.05).set_index("variable")
    assert df.loc["x1", "significant_at_threshold"] is True or df.loc["x1", "pvalue"] < 0.05
