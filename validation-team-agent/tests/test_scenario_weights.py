import math

import pandas as pd
import pytest

from tools import scenario_weights as sw


def test_weight_sum_passes_for_valid_set():
    out = sw.check_weight_sum({"base": 0.5, "adverse": 0.3, "severe": 0.2})
    assert out["passed"] is True
    assert math.isclose(out["sum"], 1.0)
    assert out["violations"] == []


def test_weight_sum_detects_violation_of_one():
    out = sw.check_weight_sum({"base": 0.4, "adverse": 0.3, "severe": 0.2})
    assert out["passed"] is False
    types = {v["type"] for v in out["violations"]}
    assert "sum" in types


def test_weight_sum_detects_negative_weight():
    out = sw.check_weight_sum({"base": 1.1, "adverse": -0.05, "severe": -0.05})
    types = {v["type"] for v in out["violations"]}
    assert "negative" in types
    assert out["passed"] is False


def test_weight_sum_detects_unknown_scenario_and_missing():
    out = sw.check_weight_sum({"base": 0.5, "boom": 0.5})
    types = {v["type"] for v in out["violations"]}
    assert "unknown_scenario" in types
    assert "missing_scenarios" in types


def test_weight_panel_groups_by_period():
    df = pd.DataFrame(
        {
            "period": ["2024-Q1", "2024-Q1", "2024-Q1", "2024-Q2", "2024-Q2", "2024-Q2"],
            "scenario": ["base", "adverse", "severe"] * 2,
            "weight": [0.5, 0.3, 0.2, 0.4, 0.4, 0.3],
        }
    )
    out = sw.check_weight_panel(
        df, period_col="period", scenario_col="scenario", weight_col="weight"
    )
    assert set(out["period"]) == {"2024-Q1", "2024-Q2"}
    q1 = out.set_index("period").loc["2024-Q1"]
    q2 = out.set_index("period").loc["2024-Q2"]
    assert bool(q1["passed"]) is True
    assert bool(q2["passed"]) is False
    assert "sum" in q2["violation_types"]


def test_weight_panel_rejects_missing_columns():
    df = pd.DataFrame({"x": [1]})
    with pytest.raises(KeyError):
        sw.check_weight_panel(df, period_col="period", scenario_col="s", weight_col="w")
