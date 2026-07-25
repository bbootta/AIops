"""순자본비율(NCR) 산출 테스트 — 금융투자업규정 제3-6조·제3-26조."""

from __future__ import annotations

from pathlib import Path

import pytest

from risk_lib.ncr import (
    compute_ncr, compute_net_operating_capital, compute_total_risk,
    required_capital, prompt_action_grade, reconcile_prior_period,
    compute_ncr_from_result, LICENSE_CAPITAL_REQUIREMENT,
)
from risk_lib.references import NCR_MIN, NCR_PROMPT_ACTION, NCR_EARLY_WARNING

AGENTS = Path(__file__).resolve().parent.parent / ".claude" / "agents"


# ----- 영업용순자본 ---------------------------------------------------------

def test_noc_identity():
    """영업용순자본 = 자산 − 부채 − 차감 + 가산."""
    noc = compute_net_operating_capital(
        1_000.0, 600.0,
        deductions={"고정자산": 50.0, "임차보증금": 20.0},
        additions={"후순위차입금": 30.0})
    assert noc.net_worth == pytest.approx(400.0)
    assert noc.total_deduction == pytest.approx(70.0)
    assert noc.total_addition == pytest.approx(30.0)
    assert noc.net_operating_capital == pytest.approx(400.0 - 70.0 + 30.0)


def test_noc_lists_all_regulatory_items_even_when_zero():
    """미기재 항목도 표에 남겨 누락과 0원을 구분할 수 있어야 한다."""
    from risk_lib.references import NCR_DEDUCTION_ITEMS, NCR_ADDITION_ITEMS
    noc = compute_net_operating_capital(100.0, 50.0, deductions={"고정자산": 1.0})
    assert list(noc.deductions["item"]) == list(NCR_DEDUCTION_ITEMS)
    assert list(noc.additions["item"]) == list(NCR_ADDITION_ITEMS)


def test_noc_rejects_unknown_and_negative_items():
    with pytest.raises(ValueError, match="규정 외"):
        compute_net_operating_capital(100.0, 50.0, deductions={"임의항목": 1.0})
    with pytest.raises(ValueError, match="음수"):
        compute_net_operating_capital(100.0, 50.0, deductions={"고정자산": -1.0})
    with pytest.raises(ValueError, match="음수"):
        compute_net_operating_capital(-1.0, 50.0)


# ----- 총위험액 -------------------------------------------------------------

def test_total_risk_is_a_simple_sum_no_diversification():
    """분산효과를 인정하지 않는 단순합이어야 한다 (BIS 경제자본과 다른 점)."""
    r = compute_total_risk(100.0, 200.0, 50.0)
    assert r.total == pytest.approx(350.0)
    assert r.total == pytest.approx(r.market_risk + r.credit_risk
                                    + r.operational_risk)
    assert len(r.by_component) == 3


def test_total_risk_rejects_negative():
    with pytest.raises(ValueError, match="음수"):
        compute_total_risk(-1.0, 0.0, 0.0)


# ----- 필요유지자기자본 -----------------------------------------------------

def test_required_capital_sums_licenses():
    total, df = required_capital(["투자중개업", "신탁업"])
    assert total == pytest.approx(
        LICENSE_CAPITAL_REQUIREMENT["투자중개업"]
        + LICENSE_CAPITAL_REQUIREMENT["신탁업"])
    assert len(df) == 2


def test_required_capital_rejects_empty_and_unknown():
    with pytest.raises(ValueError, match="인가업무 단위가 없다"):
        required_capital([])
    with pytest.raises(ValueError, match="미등록"):
        required_capital(["존재하지않는업무"])


# ----- 순자본비율 · 적기시정조치 --------------------------------------------

def test_ncr_identity():
    """NCR = (영업용순자본 − 총위험액) / 필요유지자기자본."""
    n = compute_ncr(
        1_000.0, 400.0,
        market_risk=100.0, credit_risk=80.0, operational_risk=20.0,
        licenses={"단위A": 200.0},
        deductions={"고정자산": 100.0}, additions={"후순위차입금": 50.0})
    noc = 1_000 - 400 - 100 + 50            # 550
    assert n.noc.net_operating_capital == pytest.approx(noc)
    assert n.risk.total == pytest.approx(200.0)
    assert n.surplus == pytest.approx(noc - 200.0)
    assert n.ncr == pytest.approx((noc - 200.0) / 200.0)


def test_prompt_action_thresholds_at_the_boundary():
    """100%/50%/0% 경계 — 미만일 때만 조치가 발동한다."""
    assert prompt_action_grade(1.00) == "해당없음"     # 기준선 충족
    assert prompt_action_grade(0.999) == "경영개선권고"
    assert prompt_action_grade(0.50) == "경영개선권고"
    assert prompt_action_grade(0.499) == "경영개선요구"
    assert prompt_action_grade(0.0) == "경영개선요구"
    assert prompt_action_grade(-0.001) == "경영개선명령"


def test_strongest_action_wins():
    """중첩 시 가장 강한 조치를 반환한다."""
    for v, expected in ((-5.0, "경영개선명령"), (0.2, "경영개선요구"),
                        (0.8, "경영개선권고")):
        assert prompt_action_grade(v) == expected


def test_passes_matches_min_and_early_warning_is_internal_only():
    n = compute_ncr(
        1_000.0, 400.0, market_risk=100.0, credit_risk=100.0,
        operational_risk=0.0, licenses={"단위A": 400.0})
    assert n.passes() == (n.ncr >= NCR_MIN)
    assert n.early_warning == (n.ncr < NCR_EARLY_WARNING)
    # 조기경보 임계는 감독 기준(100%)보다 높은 내부 관리값
    assert NCR_EARLY_WARNING > NCR_PROMPT_ACTION["경영개선권고"]


def test_legacy_ncr_is_reported_separately():
    """舊 NCR(영업용순자본/총위험액)은 별도 값이며 신 NCR과 혼용 불가."""
    n = compute_ncr(1_000.0, 400.0, market_risk=100.0, credit_risk=100.0,
                    operational_risk=0.0, licenses={"단위A": 200.0})
    assert n.legacy_ncr == pytest.approx(n.noc.net_operating_capital
                                         / n.risk.total)
    assert n.legacy_ncr != pytest.approx(n.ncr)


# ----- 전월 대사 (SEC-NCR-004) ----------------------------------------------

def test_prior_period_reconciliation(result):
    cur = compute_ncr_from_result(result, seed=42)
    prior = compute_ncr(
        cur.noc.total_assets * 0.97, cur.noc.total_liabilities * 0.975,
        market_risk=cur.risk.market_risk * 1.06,
        credit_risk=cur.risk.credit_risk,
        operational_risk=cur.risk.operational_risk,
        licenses={"단위A": cur.required_capital})
    recon = reconcile_prior_period(cur, prior)
    assert {"항목", "전월", "당월", "증감"} <= set(recon.columns)
    # 증감 = 당월 − 전월
    assert (recon["증감"] == recon["당월"] - recon["전월"]).all()
    # 최상위 두 항목은 NCR 기여도를 갖는다
    contrib = recon.set_index("항목")["NCR 기여(%p, 분모불변 가정)"]
    assert not contrib.loc["영업용순자본"] != contrib.loc["영업용순자본"]  # not NaN
    assert not contrib.loc["총위험액"] != contrib.loc["총위험액"]


# ----- 파이프라인 연계 · 보고서 ---------------------------------------------

def test_ncr_from_result_is_deterministic(result):
    a = compute_ncr_from_result(result, seed=42)
    b = compute_ncr_from_result(result, seed=42)
    assert a.ncr == pytest.approx(b.ncr, rel=1e-12)
    assert a.noc.net_operating_capital == pytest.approx(
        b.noc.net_operating_capital, rel=1e-12)


def test_ncr_page_renders_and_flags_demo_status(result):
    from risk_lib.ops_pages.market_trading import page_ncr
    html = page_ncr(result)
    assert "순자본비율" in html
    assert "적기시정조치" in html
    assert "전월 대비 대사" in html
    # 규제 제출용이 아님을 반드시 표기
    assert "규제 제출용이 아닙니다" in html
    # 舊 NCR과의 체계 차이 경고
    assert "舊 NCR" in html


def test_ncr_page_registered():
    from risk_lib.page_registry import PAGES
    specs = [p for p in PAGES if p.filename == "64_ncr.html"]
    assert len(specs) == 1
    assert callable(specs[0].resolve())


# ----- 담당 에이전트 --------------------------------------------------------

def test_prudential_agent_exists_and_owns_ncr_requirements():
    from risk_lib import rynta
    txt = (AGENTS / "prudential-capital-analyst.md").read_text(encoding="utf-8")
    assert "PRD-NCR" in txt and "SEC-NCR-001~004" in txt
    # BIS와의 혼용 금지가 명시돼야 한다 (분자·분모가 다른 체계)
    assert "BIS 자본비율과 혼용 금지" in txt
    df = rynta.coverage_frame()
    ncr_reqs = df[df["product"] == "PRD-NCR"]
    assert (ncr_reqs["owner"] == "prudential-capital-analyst").all()


def test_no_scoped_requirement_is_unowned():
    """NCR 담당 신설로 미배정 요건이 0이어야 한다."""
    from risk_lib import rynta
    df = rynta.coverage_frame()
    scoped = df[df["status"] != "platform"]
    orphans = list(scoped[scoped["owner"] == ""]["id"])
    assert not orphans, f"미배정 요건: {orphans}"
