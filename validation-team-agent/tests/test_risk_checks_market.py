import pytest

from tools.risk_checks import market as m


def test_traffic_light_green():
    out = m.var_backtest_traffic_light(3)
    assert out["zone"] == "green"


def test_traffic_light_yellow():
    out = m.var_backtest_traffic_light(7)
    assert out["zone"] == "yellow"


def test_traffic_light_red():
    out = m.var_backtest_traffic_light(15)
    assert out["zone"] == "red"


def test_traffic_light_boundary():
    assert m.var_backtest_traffic_light(4)["zone"] == "green"
    assert m.var_backtest_traffic_light(5)["zone"] == "yellow"
    assert m.var_backtest_traffic_light(9)["zone"] == "yellow"
    assert m.var_backtest_traffic_light(10)["zone"] == "red"


def test_traffic_light_rejects_negative():
    with pytest.raises(ValueError):
        m.var_backtest_traffic_light(-1)


def test_var_multiplier_passes_at_floor():
    assert m.check_var_multiplier(3.0)["passed"] is True
    assert m.check_var_multiplier(2.9)["passed"] is False


def test_es_consistency_detects_short_horizon():
    out = m.check_es_consistency({"eq": 10, "fx": 5})
    assert out["passed"] is False
    assert any(v["factor"] == "fx" for v in out["violations"])


def test_nmrf_ratio_within_unit_interval():
    out = m.summarize_nmrf(20, 200)
    assert 0 <= out["ratio"] <= 1
    assert out["ratio"] == pytest.approx(0.10)
