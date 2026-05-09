import numpy as np
import pandas as pd
import pytest

from tools import scenario_regression_pipeline as srp


def _hist_df(seed=0, n=80):
    rng = np.random.default_rng(seed)
    gdp = rng.normal(0.02, 0.01, n)
    unemp = rng.normal(0.04, 0.005, n)
    spread = rng.normal(0.015, 0.003, n)
    target = 1.0 - 5.0 * gdp + 8.0 * unemp + 6.0 * spread + rng.normal(0, 0.05, n)
    return pd.DataFrame(
        {
            "period": [f"2020Q{(i % 4) + 1}" for i in range(n)],
            "pd_multiplier": target,
            "gdp_growth": gdp,
            "unemployment": unemp,
            "bond_spread": spread,
        }
    )


def _scenario_df():
    return pd.DataFrame(
        {
            "period": ["2026Q1", "2026Q1", "2026Q1"],
            "scenario": ["base", "adverse", "severe"],
            "gdp_growth": [0.025, 0.005, -0.025],
            "unemployment": [0.035, 0.060, 0.090],
            "bond_spread": [0.012, 0.025, 0.050],
        }
    )


def test_fit_scenario_regression_basic():
    hist = _hist_df()
    fit = srp.fit_scenario_regression(
        hist,
        "pd_multiplier",
        ["gdp_growth", "unemployment", "bond_spread"],
        expected_signs={"gdp_growth": "-", "unemployment": "+", "bond_spread": "+"},
    )
    assert fit["n"] == 80
    assert fit["k"] == 3
    assert fit["summary"]["r_squared"] > 0.5
    assert "vif" in fit and len(fit["vif"]) == 3
    assert "durbin_watson" in fit


def test_fit_rejects_missing_columns():
    hist = _hist_df()
    with pytest.raises(ValueError):
        srp.fit_scenario_regression(hist, "pd_multiplier", ["nonexistent"])


def test_predict_scenarios_returns_pred_column():
    hist = _hist_df()
    fit = srp.fit_scenario_regression(
        hist, "pd_multiplier", ["gdp_growth", "unemployment", "bond_spread"]
    )
    pred = srp.predict_scenarios(fit, _scenario_df(), "scenario", period_col="period")
    assert "pred" in pred.columns
    assert pred.shape[0] == 3


def test_check_scenario_severity_holds():
    hist = _hist_df()
    fit = srp.fit_scenario_regression(
        hist, "pd_multiplier", ["gdp_growth", "unemployment", "bond_spread"]
    )
    pred = srp.predict_scenarios(fit, _scenario_df(), "scenario", period_col="period")
    sev = srp.check_scenario_severity(pred, "scenario", "pred", period_col="period")
    assert sev["order"]["n_violation_total"] == 0


def test_check_scenario_severity_missing_scenarios():
    bad = pd.DataFrame(
        {"scenario": ["base", "adverse"], "pred": [1.0, 1.5]}
    )
    with pytest.raises(ValueError):
        srp.check_scenario_severity(bad, "scenario", "pred")


def test_check_multiplier_floors_detects_violation():
    pred = pd.DataFrame(
        {
            "scenario": ["base", "base", "adverse", "severe"],
            "pred": [0.95, 1.05, 1.4, 2.0],
        }
    )
    out = srp.check_multiplier_floors(
        pred, "scenario", "pred", {"base": 1.0, "adverse": 1.0, "severe": 1.0}
    )
    base = next(r for r in out if r["scenario_type"] == "base")
    assert base["violation"] is True
    assert base["n_below_floor"] == 1


def test_adf_stationarity_check_iid_rejects_unit_root():
    rng = np.random.default_rng(0)
    s = pd.Series(rng.normal(0, 1, size=200))
    out = srp.adf_stationarity_check(s, alpha=0.05)
    assert out["stationary_at_alpha"] is True


def test_adf_stationarity_check_random_walk_does_not_reject():
    rng = np.random.default_rng(1)
    rw = np.cumsum(rng.normal(0, 1, size=200))
    out = srp.adf_stationarity_check(pd.Series(rw), alpha=0.05)
    assert out["stationary_at_alpha"] is False


def test_adf_too_short_raises():
    with pytest.raises(ValueError):
        srp.adf_stationarity_check(pd.Series([1.0, 2.0, 3.0]))


def test_check_feature_stationarity_returns_dataframe():
    hist = _hist_df()
    out = srp.check_feature_stationarity(hist, ["pd_multiplier", "gdp_growth"], alpha=0.05)
    assert {"variable", "adf_stat", "pvalue", "stationary_at_alpha"}.issubset(out.columns)


def test_fit_includes_stationarity_when_requested():
    hist = _hist_df()
    fit = srp.fit_scenario_regression(
        hist,
        "pd_multiplier",
        ["gdp_growth", "unemployment", "bond_spread"],
        autocorr_lags=2,
        run_stationarity_check=True,
    )
    assert fit["stationarity"] is not None
    assert fit["autocorr_lags"] == 2


def test_fit_skips_stationarity_when_disabled():
    hist = _hist_df()
    fit = srp.fit_scenario_regression(
        hist,
        "pd_multiplier",
        ["gdp_growth", "unemployment", "bond_spread"],
        run_stationarity_check=False,
    )
    assert fit["stationarity"] is None


def test_run_pipeline_end_to_end_with_supplied_multipliers():
    hist = _hist_df()
    sc = _scenario_df()
    sc["pd_multiplier"] = [1.05, 1.45, 2.40]
    out = srp.run_pipeline(
        hist,
        "pd_multiplier",
        ["gdp_growth", "unemployment", "bond_spread"],
        sc,
        scenario_col="scenario",
        period_col="period",
        pred_col_in_scenario="pd_multiplier",
        multiplier_floor_by_scenario={"base": 1.0, "adverse": 1.0, "severe": 1.0},
    )
    assert "fit" in out and "severity" in out
    assert out["severity"]["order"]["n_violation_total"] == 0
    assert out["multiplier_floors"]
    # No 'model' object should leak into the serializable bundle.
    assert "model" not in out["fit"]
