import pytest

from tools.risk_checks import capital as cap


def test_passes_with_buffers_satisfied():
    out = cap.check_ratios(
        cet1_ratio=0.085, tier1_ratio=0.100, total_ratio=0.130,
        conservation_buffer_applied=True,
        countercyclical_buffer=0.0,
        dsib_surcharge=0.010,
    )
    # required = 4.5% + 2.5% + 0% + 1.0% = 8.0%; CET1=8.5%, T1=10%, total=13% → pass
    assert out["passed"] is True
    assert out["add_buffer"] == pytest.approx(0.035)


def test_violation_when_cet1_below_buffer_floor():
    out = cap.check_ratios(
        cet1_ratio=0.060, tier1_ratio=0.080, total_ratio=0.105,
        conservation_buffer_applied=True,
        dsib_surcharge=0.010,
    )
    # cet1_required = 4.5+2.5+1.0 = 8.0%, actual 6.0% → violation
    assert out["passed"] is False
    assert any(v["metric"] == "cet1" for v in out["violations"])


def test_rejects_negative_ratio():
    with pytest.raises(ValueError):
        cap.check_ratios(-0.01, 0.10, 0.13)


def test_leverage_floor():
    assert cap.check_leverage(0.030)["passed"] is True
    assert cap.check_leverage(0.025)["passed"] is False


def test_dividend_eligibility_with_buffers():
    out = cap.check_dividend_eligibility(
        cet1_ratio=0.085,
        countercyclical_buffer=0.0,
        dsib_surcharge=0.010,
    )
    # floor = 4.5 + 2.5 + 1.0 = 8.0%
    assert out["floor_for_unrestricted_dividend"] == pytest.approx(0.080)
    assert out["dividend_unrestricted"] is True


def test_dividend_blocked_when_buffer_breached():
    out = cap.check_dividend_eligibility(cet1_ratio=0.060)
    # floor = 4.5 + 2.5 = 7.0%; 6% < 7% → restricted
    assert out["dividend_unrestricted"] is False
