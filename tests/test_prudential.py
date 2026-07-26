"""건전성 감독 도메인 — 재무제표·국내 유동성·자산운용 한도·경영실태평가·적기시정조치.

핵심 명제:
  1) 재무제표는 자산 = 부채 + 자본이 성립한다.
  2) 비율은 방향(이상/이하)을 지켜 판정한다 — 뒤집히면 위반이 통과가 된다.
  3) 원장이 없어 배분치를 쓴 항목은 그 사실이 데이터에 남는다.
  4) 적기시정조치는 자본비율 축과 경영실태평가 축을 **각각** 보고 무거운 쪽을 택한다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from risk_lib.prudential import (
    FX_LIQUIDITY_MIN, KRW_LIQUIDITY_MIN, LOAN_DEPOSIT_MAX,
    assess_prompt_action, build_financials, compute_liquidity_ratios,
    compute_ownership_limits, evaluate_camel,
)
from risk_lib.prudential.camel import WEIGHTS
from risk_lib.prudential.pca import ACTION_ORDER, THRESHOLDS


@pytest.fixture(scope="module")
def tables(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio).tables


# ----- 재무제표 ---------------------------------------------------------------

def test_balance_sheet_balances(result, portfolio):
    fin = build_financials(result, portfolio)
    assert fin.passes(), (fin.total_assets, fin.total_liabilities,
                          fin.accounting_equity)


def test_allowance_is_shown_as_a_deduction(result, portfolio):
    """대손충당금을 총액에 묻으면 순자산이 과대계상된다."""
    fin = build_financials(result, portfolio)
    b = fin.balance.set_index("item")["amount"]
    assert b["대손충당금 (차감)"] < 0
    assert b["대출채권 (순액)"] == pytest.approx(
        b["대출채권 (총액)"] + b["대손충당금 (차감)"], abs=1.0)


def test_income_statement_rolls_to_net_income(result, portfolio):
    fin = build_financials(result, portfolio)
    m = fin.income.set_index("item")["amount"]
    pre = sum(m[k] for k in ("영업수익", "영업비용", "충당금 전입액", "운영손실"))
    assert m["법인세차감전순이익"] == pytest.approx(pre, abs=1.0)
    assert m["당기순이익"] == pytest.approx(
        m["법인세차감전순이익"] + m["법인세비용"], abs=1.0)
    assert fin.net_income == pytest.approx(m["당기순이익"], abs=1.0)


def test_tax_is_never_a_credit_on_a_loss(result, portfolio):
    """세전손실에 법인세 환급을 잡으면 손실이 축소되어 보인다."""
    fin = build_financials(result, portfolio)
    m = fin.income.set_index("item")["amount"]
    assert m["법인세비용"] <= 0.0


# ----- 국내 유동성 지표 -------------------------------------------------------

def test_liquidity_ratios_are_numerator_over_denominator(result):
    liq = compute_liquidity_ratios(result)
    for _, r in liq.detail.iterrows():
        assert r["value"] == pytest.approx(
            r["numerator"] / r["denominator"], rel=1e-12)


def test_liquidity_pass_flag_respects_direction(result):
    """min 지표는 이상, max 지표는 이하 — 방향을 잃으면 판정이 뒤집힌다."""
    liq = compute_liquidity_ratios(result)
    for _, r in liq.detail.iterrows():
        expected = (r["value"] >= r["threshold"] if r["direction"] == "min"
                    else r["value"] <= r["threshold"])
        assert bool(r["passes"]) == expected, r["metric"]


def test_liquidity_thresholds_match_the_regulation(result):
    liq = compute_liquidity_ratios(result)
    t = liq.detail.set_index("metric")["threshold"]
    assert t["원화유동성비율"] == KRW_LIQUIDITY_MIN == 1.00
    assert t["외화유동성비율"] == FX_LIQUIDITY_MIN == 0.85
    assert t["원화예대율"] == LOAN_DEPOSIT_MAX == 1.00


def test_currency_split_is_symmetric(result):
    """자산·부채에 다른 통화비중을 가정하면 없는 불일치가 비율에 섞인다."""
    from risk_lib.prudential.liquidity import (
        FX_SHARE_ASSETS, FX_SHARE_LIABILITIES,
    )
    assert FX_SHARE_ASSETS == FX_SHARE_LIABILITIES


# ----- 자산운용 한도 ----------------------------------------------------------

def test_limit_amount_is_capital_times_pct(result, portfolio):
    own = compute_ownership_limits(result, portfolio)
    for _, r in own.detail.iterrows():
        assert r["limit_amount"] == pytest.approx(
            own.own_capital * r["limit_pct"], rel=1e-12)


def test_limit_percentages_match_the_banking_act(result, portfolio):
    own = compute_ownership_limits(result, portfolio)
    p = own.detail.set_index("item")["limit_pct"]
    assert p["대주주 신용공여"] == 0.25
    assert p["대주주 발행주식 취득"] == 0.01
    assert p["자회사 출자"] == 0.20
    assert p["유가증권 투자"] == 1.00
    assert p["업무용부동산 소유"] == 0.60


def test_unidentified_major_shareholder_is_flagged_not_guessed(result, portfolio):
    """대주주 원장이 없으면 아무나 지정하지 않고 미식별 상태를 남긴다."""
    own = compute_ownership_limits(result, portfolio)
    r = own.detail.set_index("item").loc["대주주 신용공여"]
    assert r["used"] == 0.0
    assert "미보유" in str(r["basis"])


def test_securities_limit_excludes_government_bonds(result, portfolio):
    """국채를 한도 모집단에 넣으면 있지도 않은 초과가 만들어진다."""
    own = compute_ownership_limits(result, portfolio)
    used = float(own.detail.set_index("item").loc["유가증권 투자", "used"])
    hqla = result.alm["balance_sheet"].hqla
    assert used == pytest.approx(hqla["level_2a"] + hqla["level_2b"], rel=1e-12)
    assert used < sum(hqla.values())


def test_every_limit_row_states_its_basis(result, portfolio):
    own = compute_ownership_limits(result, portfolio)
    assert own.detail["basis"].str.len().min() > 0
    assert own.detail["citation"].str.contains("은행법").all()


# ----- 경영실태평가 -----------------------------------------------------------

def test_camel_covers_six_components_with_unit_weights(result, tables):
    c = evaluate_camel(result, tables)
    assert set(c.detail["component"]) == set(WEIGHTS)
    assert float(c.detail["weight"].sum()) == pytest.approx(1.0, abs=1e-12)
    assert c.detail["grade"].between(1, 5).all()


def test_camel_composite_is_the_weighted_average(result, tables):
    c = evaluate_camel(result, tables)
    assert c.composite == pytest.approx(
        float((c.detail["grade"] * c.detail["weight"]).sum()), rel=1e-12)


def test_camel_liquidity_reflects_domestic_ratio_breaches(result, tables):
    """LCR만 보면 예대율·원화유동성 위반이 평가 어디에도 남지 않는다."""
    dom = tables["pru_liquidity_ratio"]
    n_breach = int((~dom["passes"]).sum())
    base = evaluate_camel(result, {k: v for k, v in tables.items()
                                   if k != "pru_liquidity_ratio"})
    withdom = evaluate_camel(result, tables)
    g_base = int(base.detail.set_index("component").loc["유동성", "grade"])
    g_dom = int(withdom.detail.set_index("component").loc["유동성", "grade"])
    assert g_dom == min(5, g_base + n_breach)


def test_camel_management_component_declares_it_is_a_proxy(result, tables):
    c = evaluate_camel(result, tables)
    basis = str(c.detail.set_index("component").loc["경영관리", "basis"])
    assert "정성" in basis or "대용" in basis


# ----- 적기시정조치 -----------------------------------------------------------

def test_no_action_when_ratios_and_grades_are_sound(result, tables):
    pca = assess_prompt_action(result, camel=evaluate_camel(result, tables))
    assert pca.action in ACTION_ORDER
    if not pca.detail["triggered"].any():
        assert pca.action == "해당없음"


def test_capital_thresholds_match_the_regulation():
    order = [a for a, *_ in THRESHOLDS]
    assert order == ["경영개선명령", "경영개선요구", "경영개선권고"]
    by = {a: (t, ti, c) for a, t, ti, c in THRESHOLDS}
    assert by["경영개선권고"] == (0.080, 0.060, 0.045)
    assert by["경영개선요구"] == (0.060, 0.045, 0.035)
    assert by["경영개선명령"] == (0.020, 0.015, 0.012)


class _FakeBis:
    def __init__(self, cet1, tier1, total):
        self.cet1_ratio, self.tier1_ratio, self.total_ratio = cet1, tier1, total


class _FakeResult:
    def __init__(self, cet1, tier1, total):
        self.bis = _FakeBis(cet1, tier1, total)
        self.meta = {"asof": "2026-06-30"}


@pytest.mark.parametrize("ratios,expected", [
    ((0.115, 0.130, 0.155), "해당없음"),
    ((0.044, 0.070, 0.090), "경영개선권고"),
    ((0.034, 0.044, 0.059), "경영개선요구"),
    ((0.011, 0.014, 0.019), "경영개선명령"),
])
def test_capital_axis_escalates(ratios, expected):
    r = _FakeResult(*ratios)
    assert assess_prompt_action(r).action == expected


def test_camel_axis_can_trigger_on_its_own(result, tables):
    """자본비율이 멀쩡해도 경영실태평가로 조치 대상이 될 수 있다.

    두 축을 AND로 묶으면 취약한 은행이 조용히 빠져나간다.
    """
    camel = evaluate_camel(result, tables)
    forced = camel.__class__(
        asof=camel.asof,
        detail=camel.detail.assign(grade=4),
        composite=4.0, composite_grade=4)
    pca = assess_prompt_action(result, camel=forced)
    assert pca.action == "경영개선요구"
    assert pca.capital_trigger is None      # 자본비율은 정상
    assert pca.camel_trigger


def test_recommendation_requires_a_core_component_downgrade(result, tables):
    """권고 요건은 종합 3등급 + **자산건전성/자본적정성** 4등급 이하다."""
    camel = evaluate_camel(result, tables)
    only_liquidity = camel.detail.assign(
        grade=[1, 1, 3, 2, 4, 3])          # 유동성만 4등급
    weak = camel.__class__(asof=camel.asof, detail=only_liquidity,
                           composite=3.0, composite_grade=3)
    assert assess_prompt_action(result, camel=weak).action == "해당없음"

    core_weak = camel.detail.assign(grade=[4, 1, 3, 2, 1, 3])   # 자본적정성 4등급
    weak2 = camel.__class__(asof=camel.asof, detail=core_weak,
                            composite=3.0, composite_grade=3)
    assert assess_prompt_action(result, camel=weak2).action == "경영개선권고"
