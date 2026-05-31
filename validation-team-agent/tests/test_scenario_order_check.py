import pytest

from tools import scenario_order_check as soc


def test_scalar_pass():
    out = soc.check_scenario_order(0.01, 0.02, 0.05)
    assert out["passed"] is True
    assert out["n"] == 1


def test_scalar_fail():
    out = soc.check_scenario_order(0.05, 0.02, 0.10)
    assert out["passed"] is False
    assert out["violations"] == "scalar"


def test_array_violations():
    out = soc.check_scenario_order(
        [0.01, 0.02, 0.03],
        [0.02, 0.01, 0.04],
        [0.05, 0.03, 0.10],
    )
    assert out["passed"] is False
    assert 1 in out["violations"]
    assert out["n"] == 3


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        soc.check_scenario_order([0.01, 0.02], [0.02], [0.05, 0.06])


def test_pd_multiplier_floor_pass_and_fail():
    ok = soc.check_pd_multiplier_floor([1.6, 1.7], "severe")
    assert ok["n_violation"] == 0
    bad = soc.check_pd_multiplier_floor([1.6, 1.0], "severe")
    assert bad["n_violation"] == 1
    assert bad["violation_indices"] == [1]


def test_pd_multiplier_floor_unknown_scenario():
    with pytest.raises(ValueError):
        soc.check_pd_multiplier_floor([1.0], "extreme")
