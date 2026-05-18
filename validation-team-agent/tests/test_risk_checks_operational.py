import pytest

from tools.risk_checks import operational as op


def test_bi_average_simple():
    out = op.business_indicator_average([1.0, 2.0, 3.0])
    assert out["years"] == 3
    assert out["average_bi"] == pytest.approx(2.0)


def test_bi_average_rejects_empty():
    with pytest.raises(ValueError):
        op.business_indicator_average([])


def test_bi_average_rejects_more_than_three_years():
    with pytest.raises(ValueError):
        op.business_indicator_average([1, 2, 3, 4])


def test_bic_bucket1_only():
    out = op.compute_bic(0.5)
    # 0.5bn × 12% = 0.06
    assert out["bic_eur_bn"] == pytest.approx(0.06)


def test_bic_progressive_through_bucket2():
    out = op.compute_bic(5.0)
    # bucket1: 1 × 12% = 0.12; bucket2: 4 × 15% = 0.60; total 0.72
    assert out["bic_eur_bn"] == pytest.approx(0.72)


def test_bic_progressive_into_bucket3():
    out = op.compute_bic(40.0)
    # bucket1 1×0.12=0.12, bucket2 29×0.15=4.35, bucket3 10×0.18=1.80 → 6.27
    assert out["bic_eur_bn"] == pytest.approx(6.27, rel=1e-6)


def test_orc_blocks_ilm_below_floor():
    with pytest.raises(ValueError):
        op.compute_orc(bic=1.0, ilm=0.5)


def test_orc_simple_product():
    out = op.compute_orc(bic=2.0, ilm=1.2)
    assert out["orc"] == pytest.approx(2.4)


def test_loss_history_check():
    assert op.check_loss_history_years(10)["passed"] is True
    assert op.check_loss_history_years(7)["passed"] is False
