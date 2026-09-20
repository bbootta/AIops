"""산정 시점 기준(세칙 제17조제2항)과 규정 원화예대율(제26조 · 별표 3의7).

LCR·원화예대율은 매월 평잔이다. 비율이 충분해도 시점값을 평잔으로 보고하면
기준 위반이며, 기준을 밝히지 않으면 판단하지 않는다.
"""

from __future__ import annotations

import pytest

from vta.domains import alm, liquidity


# ---- LCR 산정 기준

def test_lcr_without_basis_leaves_the_judgement_open():
    out = liquidity.check_lcr(120.0, 100.0)
    assert out["status"] == "ok"
    assert out["basis_ok"] is None
    assert out["required_basis"] == "monthly_average"


def test_lcr_spot_value_fails_the_basis_even_when_the_ratio_is_fine():
    out = liquidity.check_lcr(120.0, 100.0, basis="spot")
    assert out["status"] == "ok"
    assert out["basis_ok"] is False


def test_lcr_monthly_average_passes_the_basis():
    assert liquidity.check_lcr(120.0, 100.0, basis="monthly_average")["basis_ok"] is True


def test_lcr_rejects_an_unknown_basis():
    with pytest.raises(ValueError):
        liquidity.check_lcr(120.0, 100.0, basis="quarterly")


def test_liquidity_handler_fails_a_spot_lcr():
    from vta.handlers.registry import liquidity_handler
    from tools.workflow import WorkflowContext

    ctx = WorkflowContext(request={})
    ok = liquidity_handler({"liquidity_hqla": 120.0, "liquidity_outflow": 100.0,
                            "liquidity_basis": "monthly_average"}, ctx)
    spot = liquidity_handler({"liquidity_hqla": 120.0, "liquidity_outflow": 100.0,
                              "liquidity_basis": "spot"}, ctx)
    unknown = liquidity_handler({"liquidity_hqla": 120.0, "liquidity_outflow": 100.0}, ctx)
    assert ok.status == "ok"
    assert spot.status == "fail"
    assert "산정기준 spot" in spot.detail
    assert unknown.status == "ok" and "산정기준 미확인" in unknown.detail


# ---- 원화예대율

BASE = dict(won_loans=95.0, won_deposits=100.0, basis="monthly_average")


def test_won_ltd_plain_case_matches_the_formula():
    out = alm.check_won_loan_to_deposit(**BASE)
    assert out["ratio"] == pytest.approx(0.95)
    assert out["level"] == "ok"
    assert out["basis_ok"] is True
    assert any("가감 미적용" in n for n in out["notes"])


def test_won_ltd_policy_loans_leave_the_numerator():
    out = alm.check_won_loan_to_deposit(**BASE, policy_loans_excluded=15.0)
    assert out["ratio"] == pytest.approx(0.80)


def test_won_ltd_caps_covered_bonds_at_1_and_2_percent_of_deposits():
    # 5~10년 3.0 → 1.0 인정, 10년 이상 5.0 과 합산 6.0 → 2.0 인정
    out = alm.check_won_loan_to_deposit(**BASE, covered_bond_5_10y=3.0,
                                        covered_bond_10y_plus=5.0)
    assert out["components"]["covered_bond_counted"] == pytest.approx(2.0)
    assert out["denominator"] == pytest.approx(102.0)


def test_won_ltd_caps_cd_at_1_percent_after_the_benchmark_adjustment():
    # 지표물 0.4 × 1.5 = 0.6, 그 외 0.4 × 0.5 = 0.2 → 0.8 (한도 1.0 이내)
    out = alm.check_won_loan_to_deposit(**BASE, benchmark_cd=0.4, other_cd=0.4)
    assert out["components"]["cd_counted"] == pytest.approx(0.8)
    # 지표물 5.0 × 1.5 = 7.5 → 한도 1.0
    out = alm.check_won_loan_to_deposit(**BASE, benchmark_cd=5.0)
    assert out["components"]["cd_counted"] == pytest.approx(1.0)


def test_won_ltd_applies_regional_adjustments_and_household_addon():
    breakdown = {"corporate_metro": 20.0, "corporate_nonmetro": 10.0,
                 "sole_proprietor_nonmetro": 10.0, "household": 40.0}
    out = alm.check_won_loan_to_deposit(**BASE, loan_breakdown=breakdown)
    # −3.0 −2.0 −0.5 +6.0 = +0.5
    assert out["components"]["loan_adjustment"] == pytest.approx(0.5)
    assert out["ratio"] == pytest.approx(0.955)
    assert not any("가감 미적용" in n for n in out["notes"])


def test_won_ltd_rejects_an_unknown_breakdown_key():
    with pytest.raises(ValueError):
        alm.check_won_loan_to_deposit(**BASE, loan_breakdown={"sme": 1.0})


def test_won_ltd_breach_is_detected_and_household_addon_can_cause_it():
    """가계대출 15% 가산 없이는 통과하는 은행이 가산 후 100% 를 넘는다."""
    out = alm.check_won_loan_to_deposit(won_loans=98.0, won_deposits=100.0,
                                        loan_breakdown={"household": 98.0})
    assert out["ratio"] == pytest.approx(1.127)
    assert out["level"] == "below_min" and not out["passed"]


def test_won_ltd_exemption_below_4_trillion():
    small = alm.check_won_loan_to_deposit(won_loans=120.0, won_deposits=100.0,
                                          prior_quarter_end_won_loans=3.9e12)
    assert small["applicable"] is False
    assert small["level"] == "not_applicable" and small["passed"]
    large = alm.check_won_loan_to_deposit(won_loans=120.0, won_deposits=100.0,
                                          prior_quarter_end_won_loans=4.0e12)
    assert large["applicable"] is True and large["level"] == "below_min"


def test_won_ltd_spot_basis_is_flagged():
    out = alm.check_won_loan_to_deposit(won_loans=95.0, won_deposits=100.0, basis="spot")
    assert out["basis_ok"] is False


def test_alm_handler_wires_won_ltd_and_fails_on_spot_basis():
    from vta.handlers.registry import alm_handler
    from tools.workflow import WorkflowContext

    ctx = WorkflowContext(request={})
    res = alm_handler({"alm_won_ltd": {"won_loans": 95.0, "won_deposits": 100.0,
                                       "basis": "monthly_average"}}, ctx)
    assert res.status == "ok" and "원화예대율 95.0%" in res.detail
    res = alm_handler({"alm_won_ltd": {"won_loans": 95.0, "won_deposits": 100.0,
                                       "basis": "spot"}}, ctx)
    assert res.status == "fail"
    res = alm_handler({"alm_won_ltd": {"won_loans": 95.0}}, ctx)
    assert res.status == "skipped"


# ---- 임계 원장 대조

def test_won_ltd_thresholds_are_cross_checked_against_the_regulation():
    from tools import regulatory_criteria as rc

    cat = rc.load()
    by_key = {t["key"]: t for t in cat["thresholds"]}
    for key in ("won_ltd_max", "won_ltd_exemption_loans"):
        assert key in by_key, key
        assert by_key[key]["source_key"] == "규정"
        assert by_key[key]["harness_file"] == "harness/alm_thresholds.json"
        assert by_key[key]["status"] == "ok"
