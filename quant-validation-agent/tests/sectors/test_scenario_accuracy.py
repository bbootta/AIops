"""Scenario severity and floor accuracy on monotonic / violation cases."""
import pandas as pd
import pytest

from tests.sectors import fixtures as fx
from tools import scenario_order_check as soc


def _pivot(df):
    return df.pivot_table(index="period", columns="scenario",
                          values="pd_multiplier", aggfunc="mean")


def test_monotonic_case_yields_zero_violations():
    pivot = _pivot(fx.scenario_monotonic_severity())
    out = soc.check_scenario_order(pivot["base"].values,
                                   pivot["adverse"].values,
                                   pivot["severe"].values)
    assert out["n_violation_total"] == 0


def test_engineered_violation_is_detected():
    pivot = _pivot(fx.scenario_with_violation())
    out = soc.check_scenario_order(pivot["base"].values,
                                   pivot["adverse"].values,
                                   pivot["severe"].values)
    assert out["n_violation_adverse_vs_severe"] >= 1
    assert out["n_violation_total"] >= 1


def test_floor_violation_detected():
    out = soc.check_pd_multiplier_floor([0.9, 1.0, 1.2], scenario_type="base",
                                        floor=1.0)
    assert out["violation"] is True
    assert out["n_below_floor"] == 1


def test_floor_no_violation_when_all_above():
    out = soc.check_pd_multiplier_floor([1.05, 1.10, 1.20], scenario_type="base",
                                        floor=1.0)
    assert out["violation"] is False
    assert out["n_below_floor"] == 0


def test_summarize_scenario_violations_per_row():
    df = pd.DataFrame({
        "base": [1.0, 1.0, 1.0],
        "adverse": [0.9, 1.5, 1.5],  # row 0 violates base>adverse
        "severe": [1.5, 1.4, 2.5],   # row 1 violates adverse>severe
    })
    out = soc.summarize_scenario_violations(df, "base", "adverse", "severe")
    assert out["viol_base_vs_adverse"].sum() == 1
    assert out["viol_adverse_vs_severe"].sum() == 1
    assert out["any_violation"].sum() == 2


def test_direction_lower_is_worse_reverses_expectations():
    """For 'capital ratio' style metrics where lower=worse, base should be the
    largest value and severe the smallest. Violation when base < adverse."""
    out = soc.check_scenario_order([10.0, 9.5, 9.0], [8.0, 7.5, 7.0],
                                   [6.0, 5.5, 5.0], direction="lower_is_worse")
    assert out["n_violation_total"] == 0
    # Now break it: base[0] < adverse[0]
    out2 = soc.check_scenario_order([6.0, 9.5, 9.0], [8.0, 7.5, 7.0],
                                    [6.0, 5.5, 5.0], direction="lower_is_worse")
    assert out2["n_violation_base_vs_adverse"] == 1
