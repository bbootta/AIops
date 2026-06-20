"""Tests for the explainability layer."""

from __future__ import annotations

import numpy as np
import pytest

from risk_lib import generate_portfolio, run_pipeline
from risk_lib.explainability import (
    Driver, driver_decomposition,
    shapley_attribution, find_counterfactual,
    what_if_grid, narrate_capital_change,
    recommend_actions,
)


# ----- driver decomposition -----------------------------------------------

def test_driver_decomposition_sums_to_total():
    drivers = driver_decomposition(0.115, 0.110, {"a": -0.003, "b": -0.002})
    # all named driven; no "other"
    assert sum(d.contribution for d in drivers) == pytest.approx(-0.005, rel=1e-9)
    assert all(d.contribution_pct >= 0 for d in drivers)


def test_driver_decomposition_residual_captured():
    """When named drivers don't sum to the total delta, residual is captured."""
    drivers = driver_decomposition(0.115, 0.100, {"a": -0.005})  # delta = -0.015
    names = [d.name for d in drivers]
    assert "other" in names
    assert sum(d.contribution for d in drivers) == pytest.approx(-0.015, rel=1e-9)


def test_driver_decomposition_top_n():
    drivers = driver_decomposition(
        0, 10, {"a": 1, "b": 2, "c": 3, "d": 4}, top_n=2)
    assert len(drivers) == 2
    # sorted by absolute contribution
    assert abs(drivers[0].contribution) >= abs(drivers[1].contribution)


def test_driver_direction():
    drivers = driver_decomposition(0, 1, {"up": 2, "down": -1})
    by_name = {d.name: d for d in drivers}
    assert by_name["up"].direction == "+"
    assert by_name["down"].direction == "-"


# ----- Shapley attribution ------------------------------------------------

def test_shapley_sum_equals_delta_metric():
    """For an additive metric, Shapley values sum to the total change."""
    def m(x): return 2 * x["a"] + 3 * x["b"]
    base = {"a": 1, "b": 1}; scen = {"a": 2, "b": 4}
    shap = shapley_attribution(m, base, scen, n_samples=500)
    expected_delta = m(scen) - m(base)
    actual_sum = sum(shap.values())
    assert actual_sum == pytest.approx(expected_delta, rel=1e-3)


def test_shapley_isolates_no_op_feature():
    """A feature held constant should have zero SHAP value."""
    def m(x): return x["a"] * 2
    base = {"a": 1, "b": 5}; scen = {"a": 2, "b": 5}
    shap = shapley_attribution(m, base, scen, n_samples=300)
    assert shap["b"] == pytest.approx(0, abs=1e-9)
    assert shap["a"] == pytest.approx(2, rel=1e-9)


# ----- counterfactual -----------------------------------------------------

def test_counterfactual_binary_search_converges():
    """Find the RWA level that drives CET1 = 0.10 given capital = 1.0e12."""
    def cet1(x): return x["capital"] / x["rwa"]
    res = find_counterfactual(
        cet1,
        {"capital": 1.0e12, "rwa": 1.0e13},
        target_value=0.10,
        search_feature="rwa", direction="down",
        bounds=(5e12, 1.5e13),
    )
    assert res.target_metric == pytest.approx(0.10, abs=1e-4)
    assert res.target_value == pytest.approx(1.0e13, rel=0.001)


def test_counterfactual_direction_up_works():
    def f(x): return x["x"] * 2
    res = find_counterfactual(
        f, {"x": 5.0}, target_value=20.0,
        search_feature="x", direction="up",
        bounds=(0, 20),
    )
    assert res.target_metric == pytest.approx(20.0, abs=1e-4)


# ----- what-if grid --------------------------------------------------------

def test_what_if_grid_shape():
    metrics = {"CET1": 0.115, "ECL": 100e9}
    shocks = {
        "RWA +10%":   {"CET1": 0.105, "ECL": 100e9},
        "PD +50%":    {"CET1": 0.110, "ECL": 150e9},
    }
    rows = what_if_grid(metrics, shocks)
    assert len(rows) == 4   # 2 factors × 2 metrics


# ----- narrative ----------------------------------------------------------

def test_narrative_capital_increase_narrative():
    nar = narrate_capital_change(
        base_cet1=0.110, current_cet1=0.115,
        rwa_change_pct=-0.02, capital_change_pct=0.025,
    )
    assert "상승" in nar.headline
    assert len(nar.drivers) >= 2


def test_narrative_low_cet1_triggers_action():
    nar = narrate_capital_change(
        base_cet1=0.090, current_cet1=0.085,
        rwa_change_pct=0.04, capital_change_pct=-0.01,
    )
    # Below 10% → AT1/T2 issuance action should appear
    assert any("AT1" in a for a in nar.actions)


# ----- action recommender -------------------------------------------------

def test_recommend_actions_returns_sorted(monkeypatch):
    res = run_pipeline(generate_portfolio(seed=42), seed=42)
    actions = recommend_actions(res)
    priorities = [a.priority for a in actions]
    assert priorities == sorted(priorities)


def test_recommend_actions_includes_validation_failures():
    res = run_pipeline(generate_portfolio(seed=42), seed=42)
    actions = recommend_actions(res)
    # At least one action should reference a check
    assert any(a.category in ("자본/유동성", "검증", "스트레스") for a in actions)


def test_recommend_actions_red_kri_is_priority_1():
    res = run_pipeline(generate_portfolio(seed=42), seed=42)
    actions = recommend_actions(res)
    # If there's a RED KRI, at least one action must be P1
    if res.raf and any(k.grade == "RED" for k in res.raf.kris):
        assert any(a.priority == 1 for a in actions)


# ----- HTML page registration ---------------------------------------------

def test_explainability_page_in_report_set(tmp_path):
    from risk_lib.html_report import build_full_report_package
    p = generate_portfolio(seed=42)
    res = run_pipeline(p, seed=42)
    written = build_full_report_package(res, tmp_path, portfolio=p)
    assert "ops/58_explainability.html" in written
    import os
    assert os.path.getsize(written["ops/58_explainability.html"]) > 5000
