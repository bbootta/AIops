import pytest

from tools.risk_checks import irrbb


def test_all_scenarios_present():
    out = irrbb.check_scenarios_present({
        "parallel_up": 0.0,
        "parallel_down": 0.0,
        "steepener": 0.0,
        "flattener": 0.0,
        "short_rate_up": 0.0,
        "short_rate_down": 0.0,
    })
    assert out["passed"] is True
    assert out["missing"] == []


def test_missing_scenarios_reported():
    out = irrbb.check_scenarios_present({"parallel_up": 0.0})
    assert out["passed"] is False
    assert "steepener" in out["missing"]


def test_eve_outlier_detected_above_15_pct():
    out = irrbb.check_eve_outlier(
        {"parallel_up": -2_000_000, "parallel_down": 100_000},
        tier1_capital=10_000_000,
    )
    assert out["worst_scenario"] == "parallel_up"
    assert out["ratio"] == pytest.approx(0.2)
    assert out["outlier"] is True


def test_eve_within_limit_not_outlier():
    out = irrbb.check_eve_outlier(
        {"parallel_up": -500_000, "parallel_down": 100_000},
        tier1_capital=10_000_000,
    )
    assert out["outlier"] is False


def test_eve_rejects_invalid_tier1():
    with pytest.raises(ValueError):
        irrbb.check_eve_outlier({"parallel_up": -1.0}, tier1_capital=0)


def test_nii_warning_triggered_above_20_pct():
    out = irrbb.check_nii_warning(-30, 100)
    assert out["ratio"] == pytest.approx(0.3)
    assert out["warning"] is True


def test_nii_warning_not_triggered():
    out = irrbb.check_nii_warning(-10, 100)
    assert out["warning"] is False
