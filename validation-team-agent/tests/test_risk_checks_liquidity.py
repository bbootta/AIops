import pytest

from tools.risk_checks import liquidity as lq


def test_lcr_ok():
    out = lq.check_lcr(120.0, 100.0)
    assert out["ratio"] == pytest.approx(1.2)
    assert out["status"] == "ok"


def test_lcr_warning():
    out = lq.check_lcr(105.0, 100.0)
    assert out["status"] == "warning"


def test_lcr_below_min():
    out = lq.check_lcr(90.0, 100.0)
    assert out["status"] == "below_min"


def test_lcr_rejects_invalid_outflow():
    with pytest.raises(ValueError):
        lq.check_lcr(100.0, 0.0)


def test_nsfr_ok_and_below_min():
    assert lq.check_nsfr(120.0, 100.0)["status"] == "ok"
    assert lq.check_nsfr(90.0, 100.0)["status"] == "below_min"


def test_nsfr_warning_boundary():
    out = lq.check_nsfr(104.0, 100.0)
    assert out["status"] == "warning"
