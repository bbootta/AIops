import pandas as pd
import pytest

from tools import scenario_order_check as soc


def test_order_holds():
    out = soc.check_scenario_order([0.01, 0.02], [0.02, 0.03], [0.05, 0.07])
    assert out["n_violation_total"] == 0


def test_order_violation_base_above_adverse():
    out = soc.check_scenario_order([0.05, 0.02], [0.02, 0.03], [0.06, 0.07])
    assert out["n_violation_base_vs_adverse"] == 1
    assert 0 in out["violation_positions"]


def test_order_violation_adverse_above_severe():
    out = soc.check_scenario_order([0.01, 0.02], [0.05, 0.03], [0.04, 0.07])
    assert out["n_violation_adverse_vs_severe"] == 1


def test_pd_multiplier_floor_violation():
    out = soc.check_pd_multiplier_floor([0.9, 1.0, 1.2], scenario_type="base", floor=1.0)
    assert out["n_below_floor"] == 1
    assert out["violation"] is True


def test_summarize_scenario_violations():
    df = pd.DataFrame(
        {
            "base": [0.01, 0.02, 0.03],
            "adverse": [0.02, 0.01, 0.04],
            "severe": [0.05, 0.06, 0.02],
        }
    )
    out = soc.summarize_scenario_violations(df, "base", "adverse", "severe")
    assert out["any_violation"].sum() >= 2


def test_invalid_direction():
    with pytest.raises(ValueError):
        soc.check_scenario_order([0.01], [0.02], [0.03], direction="not_a_direction")
