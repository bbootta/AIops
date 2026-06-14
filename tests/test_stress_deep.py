"""v0.13.0 CRO-grade stress 부문 단위테스트.

검증 범위:
- 거시 narrative 표/요약
- factor-by-factor 분해 (PD / LGD / GDP 단독 + interaction)
- 자산군 sensitivity 단조성
- multi-target reverse stress (CET1/Tier1/LCR/NSFR)
- CCAR 3Y 분기 path + 연속 침범 + 자본 보충 액션
- NGFS 30Y 기후 자본 path
- 유동성 stress + 회복 우선순위
- 회복 plan 권고 (MDA / AT1 trigger / 신주 발행)
- scenario comparison

단조성:
  RWA(severe) >= RWA(adverse) >= RWA(baseline)
  CET1(severe) <= CET1(adverse) <= CET1(baseline)
이 위반 시 모형 오류 — 반드시 FAIL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.capital.bis import CapitalStack
from risk_lib.alm.balance_sheet import generate_balance_sheet
from risk_lib.alm.lcr import compute_lcr
from risk_lib.alm.nsfr import compute_nsfr
from risk_lib.data_gen import generate_portfolio
from risk_lib.stress import (
    BASELINE, ADVERSE, SEVERELY_ADVERSE, StressAxis,
    factor_decomposition, asset_class_sensitivity,
    run_multi_reverse, run_ccar, run_climate_capital,
    run_liquidity_stress, recovery_priority_ladder,
    build_recovery_plan, scenario_recovery_table,
    compare_scenarios, macro_table, narrative_summary,
    AT1_TRIGGER_CET1, DEFAULT_PATHS, DEFAULT_CCAR_PATHS,
    hump_severities, stress_lcr, stress_nsfr,
)


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def portfolio():
    return generate_portfolio(seed=42)


@pytest.fixture(scope="module")
def irb_book(portfolio):
    return portfolio[portfolio["asset_class"].isin(
        ["corporate", "retail_other", "residential_mortgage"])].copy()


@pytest.fixture(scope="module")
def capital(portfolio):
    total_ead = float(portfolio["ead"].sum())
    rwa = total_ead * 0.7
    return CapitalStack(cet1=rwa * 0.115, additional_t1=rwa * 0.015, tier2=rwa * 0.025)


@pytest.fixture(scope="module")
def rwa_other(portfolio):
    return float(portfolio["ead"].sum()) * 0.10


@pytest.fixture(scope="module")
def alm(portfolio, capital):
    bs = generate_balance_sheet(portfolio, capital.total, seed=42)
    return {"balance_sheet": bs, "lcr": compute_lcr(bs), "nsfr": compute_nsfr(bs)}


# ---------------------------------------------------------------- narrative


def test_macro_narrative_table_shape():
    tbl = macro_table()
    assert {"scenario", "year", "gdp_growth", "unemployment",
            "hpi_change", "policy_rate", "bbb_spread",
            "kospi_change", "fx_krw_usd"} <= set(tbl.columns)
    # 3 시나리오 × 3 horizon = 9 rows
    assert len(tbl) == 9


def test_narrative_summary_severity_ordering():
    summ = narrative_summary()
    severe = summ[summ["scenario"] == "severely_adverse"].iloc[0]
    adverse = summ[summ["scenario"] == "adverse"].iloc[0]
    base = summ[summ["scenario"] == "baseline"].iloc[0]
    # severity ordering: GDP shock 더 deep, 실업률 더 높음
    assert severe["peak_gdp"] < adverse["peak_gdp"] < base["peak_gdp"]
    assert severe["peak_unemployment"] >= adverse["peak_unemployment"]
    assert severe["peak_hpi"] < adverse["peak_hpi"]


# ---------------------------------------------------------------- decomposition


def test_factor_decomposition_columns(irb_book, capital, rwa_other):
    df = factor_decomposition(irb_book, capital, rwa_other, ADVERSE)
    assert set(df["factor"]) == {"base", "pd", "lgd", "gdp", "combined", "interaction"}
    assert {"cet1_ratio", "delta_cet1_pp", "ecl_uplift", "rwa_total"} <= set(df.columns)


def test_factor_decomposition_severity_monotone(irb_book, capital, rwa_other):
    """severe 결합 충격이 adverse 결합 충격보다 CET1 감소 더 큼."""
    fa = factor_decomposition(irb_book, capital, rwa_other, ADVERSE)
    fs = factor_decomposition(irb_book, capital, rwa_other, SEVERELY_ADVERSE)
    da = float(fa[fa["factor"] == "combined"]["delta_cet1_pp"].iloc[0])
    ds = float(fs[fs["factor"] == "combined"]["delta_cet1_pp"].iloc[0])
    assert ds < da  # severe is more negative


def test_factor_decomposition_each_factor_nonpositive(irb_book, capital, rwa_other):
    """단일 factor 적용은 CET1을 떨어뜨리거나 유지 — 절대 올리지 않음."""
    df = factor_decomposition(irb_book, capital, rwa_other, SEVERELY_ADVERSE)
    for f in ["pd", "lgd", "gdp"]:
        d = float(df[df["factor"] == f]["delta_cet1_pp"].iloc[0])
        assert d <= 1e-6, f"factor {f} delta {d} should be <= 0"


def test_asset_class_sensitivity(irb_book, capital, rwa_other):
    df = asset_class_sensitivity(irb_book, capital, rwa_other, SEVERELY_ADVERSE)
    assert {"asset_class", "ead", "cet1_ratio", "delta_cet1_pp",
            "ecl_uplift", "rwa_total", "share_of_total_drop_pp"} <= set(df.columns)
    # 자산군 단독 충격은 모두 CET1 떨어뜨림
    assert (df["delta_cet1_pp"] <= 1e-6).all()


# ---------------------------------------------------------------- multi-reverse


def test_multi_reverse_targets_shape(irb_book, capital, rwa_other, alm):
    mr = run_multi_reverse(
        irb_book, capital, rwa_other,
        base_lcr=alm["lcr"], base_nsfr=alm["nsfr"],
    )
    assert set(mr.targets["metric"]) == {
        "CET1 (4.5%)", "Tier1 (6.0%)", "LCR (100%)", "NSFR (100%)"
    }
    assert mr.binding_constraint in set(mr.targets["metric"])
    assert mr.binding_severity >= 0
    assert "narrative" in mr.critical_pathway


def test_multi_reverse_binding_is_minimum_severity(irb_book, capital, rwa_other, alm):
    mr = run_multi_reverse(
        irb_book, capital, rwa_other,
        base_lcr=alm["lcr"], base_nsfr=alm["nsfr"],
    )
    bindable = mr.targets[~mr.targets["resilient"] & ~mr.targets["already_breached"]]
    if not bindable.empty:
        min_sev = float(bindable["critical_severity"].min())
        assert abs(mr.binding_severity - min_sev) < 1e-6


def test_stress_lcr_monotone(alm):
    base = alm["lcr"].lcr
    s1 = stress_lcr(alm["lcr"], 1.0)
    s2 = stress_lcr(alm["lcr"], 2.0)
    assert s1 <= base + 1e-9
    assert s2 <= s1 + 1e-9


def test_stress_nsfr_monotone(alm):
    base = alm["nsfr"].nsfr
    s1 = stress_nsfr(alm["nsfr"], 1.0)
    s2 = stress_nsfr(alm["nsfr"], 2.0)
    assert s1 <= base + 1e-9
    assert s2 <= s1 + 1e-9


# ---------------------------------------------------------------- CCAR


def test_ccar_path_shape(irb_book, capital, rwa_other):
    ccar = run_ccar(irb_book, capital, rwa_other)
    # 3 scenarios × 12 quarters
    assert len(ccar.paths) == len(DEFAULT_CCAR_PATHS) * 12
    assert {"scenario", "quarter", "q_index", "severity",
            "rwa_total", "ecl", "cet1_ratio", "tier1_ratio",
            "total_ratio", "cbr_breach"} <= set(ccar.paths.columns)


def test_ccar_severity_monotone(irb_book, capital, rwa_other):
    """severely_adverse 시 CET1 최저값은 adverse보다 낮아야 한다."""
    ccar = run_ccar(irb_book, capital, rwa_other)
    consec = ccar.consecutive_breach
    min_sev = float(consec[consec["scenario"] == "severely_adverse"]["min_cet1"].iloc[0])
    min_adv = float(consec[consec["scenario"] == "adverse"]["min_cet1"].iloc[0])
    min_base = float(consec[consec["scenario"] == "baseline"]["min_cet1"].iloc[0])
    assert min_sev <= min_adv <= min_base + 1e-9


def test_ccar_recovery_action_ordering(irb_book, capital, rwa_other):
    """신주 발행은 다른 액션보다 trough CET1을 더 올려야 한다."""
    ccar = run_ccar(irb_book, capital, rwa_other)
    rec = ccar.recovery_summary
    if rec.empty:
        return
    passive = float(rec[rec["action"] == "passive"]["trough_cet1"].iloc[0])
    rights = float(rec[rec["action"] == "rights_issue"]["trough_cet1"].iloc[0])
    assert rights >= passive - 1e-9


def test_hump_severities_shape():
    s = hump_severities(2.5, peak_q=3, n=12, decay=0.85)
    assert len(s) == 12
    # peak at index 3
    assert s[3] == pytest.approx(2.5)
    assert s[0] <= s[3] and s[11] <= s[3]


# ---------------------------------------------------------------- climate capital


def test_climate_capital_path_shape(irb_book, capital, rwa_other):
    cc = run_climate_capital(irb_book, capital, rwa_other)
    assert len(cc.path) == 3 * 7   # 3 시나리오 × 7 horizon
    assert {"scenario", "year", "co2_price", "hazard_intensity",
            "rwa_total", "ecl", "cet1_ratio"} <= set(cc.path.columns)
    assert cc.worst_point["cet1_ratio"] <= cc.path["cet1_ratio"].max()


def test_climate_capital_scenarios_ordering(irb_book, capital, rwa_other):
    """모든 climate 시나리오는 base 대비 CET1 하락 (delta_cet1_pp <= 0)."""
    cc = run_climate_capital(irb_book, capital, rwa_other)
    # 최종 horizon에서 delta_cet1 음수
    last_year = cc.path["year"].max()
    last_pts = cc.path[cc.path["year"] == last_year]
    assert (last_pts["delta_cet1_pp"] <= 1e-6).all()


def test_climate_capital_binding_year(irb_book, capital, rwa_other):
    cc = run_climate_capital(irb_book, capital, rwa_other)
    assert set(cc.binding_year.keys()) == {"orderly", "disorderly", "hot_house"}


# ---------------------------------------------------------------- liquidity


def test_liquidity_stress_scenarios(alm):
    df = run_liquidity_stress(alm["lcr"], alm["nsfr"])
    assert "baseline" in df["scenario"].values
    base_lcr = float(df[df["scenario"] == "baseline"]["lcr"].iloc[0])
    severe_lcr = float(df[df["scenario"] == "combined_severe"]["lcr"].iloc[0])
    assert severe_lcr <= base_lcr + 1e-9


def test_recovery_priority_ladder_monotone(alm):
    # arbitrary shortfall
    shortfall = float(alm["lcr"].net_outflow) * 0.20
    df = recovery_priority_ladder(shortfall, alm["lcr"])
    # cumulative is monotone non-decreasing
    cum = df["cumulative_lcr_relief"].values
    for i in range(1, len(cum)):
        assert cum[i] >= cum[i - 1] - 1e-9
    # final cumulative covers shortfall
    assert df.iloc[-1]["covers_shortfall"]


# ---------------------------------------------------------------- recovery plan


def test_recovery_plan_normal():
    """CET1 11.5% → 정상, MDA 100% distributable, no actions."""
    rec = build_recovery_plan(0.115, 1e12 * 0.115, 1e12)
    assert rec.severity_level == "정상"
    assert rec.mda_distributable_pct == 1.0
    assert not rec.at1_trigger_active
    assert rec.capital_raise_required == 0.0


def test_recovery_plan_at1_trigger():
    """CET1 5.0% < 5.125% → AT1 trigger 활성화."""
    rec = build_recovery_plan(0.050, 1e12 * 0.050, 1e12)
    assert rec.at1_trigger_active
    assert rec.severity_level.startswith("경고")
    assert rec.capital_raise_required > 0
    assert any("신주" in a for a in rec.actions)


def test_recovery_plan_pillar1_breach():
    """CET1 3.5% < 4.5% → 위기 단계, 100% retention."""
    rec = build_recovery_plan(0.035, 1e12 * 0.035, 1e12)
    assert rec.severity_level.startswith("위기")
    assert rec.mda_distributable_pct == 0.0
    assert any("배당 완전 중단" in a for a in rec.actions)


def test_recovery_plan_at1_trigger_constant():
    assert AT1_TRIGGER_CET1 == 0.05125


def test_scenario_recovery_table_shape(irb_book, capital, rwa_other):
    from risk_lib.stress import run_stress
    stress = run_stress(irb_book, capital, rwa_other,
                        scenarios=[BASELINE, ADVERSE, SEVERELY_ADVERSE])
    tbl = scenario_recovery_table(stress)
    assert {"scenario", "cet1_ratio", "severity_level",
            "mda_distributable_pct", "at1_trigger",
            "capital_raise_required"} <= set(tbl.columns)
    assert len(tbl) == 3


# ---------------------------------------------------------------- comparison


def test_compare_scenarios_columns(irb_book, capital, rwa_other, alm):
    from risk_lib.stress import run_stress
    stress = run_stress(irb_book, capital, rwa_other,
                        scenarios=[BASELINE, ADVERSE, SEVERELY_ADVERSE])
    cmp = compare_scenarios(stress, base_lcr=alm["lcr"], base_nsfr=alm["nsfr"])
    expected = {"scenario", "cet1_ratio", "total_ratio", "cet1_surplus_pp",
                "mda_distributable_pct", "capital_raise_required",
                "lcr", "nsfr", "lcr_passes", "nsfr_passes",
                "ecl_uplift", "rwa_growth_pct", "roa_impact_pp", "passes_all"}
    assert expected <= set(cmp.columns)


def test_compare_scenarios_monotone(irb_book, capital, rwa_other, alm):
    """CET1 비율 단조 감소 + LCR 단조 감소."""
    from risk_lib.stress import run_stress
    stress = run_stress(irb_book, capital, rwa_other,
                        scenarios=[BASELINE, ADVERSE, SEVERELY_ADVERSE])
    cmp = compare_scenarios(stress, base_lcr=alm["lcr"], base_nsfr=alm["nsfr"])
    base = cmp[cmp["scenario"] == "baseline"].iloc[0]
    adv = cmp[cmp["scenario"] == "adverse"].iloc[0]
    sev = cmp[cmp["scenario"] == "severely_adverse"].iloc[0]
    assert sev["cet1_ratio"] <= adv["cet1_ratio"] <= base["cet1_ratio"] + 1e-9
    assert sev["lcr"] <= adv["lcr"] <= base["lcr"] + 1e-9


# ---------------------------------------------------------------- pipeline wiring


def test_pipeline_exposes_stress_deep():
    from risk_lib.pipeline import run_pipeline
    r = run_pipeline()
    sd = r.stress_deep
    expected_keys = {"narrative_table", "narrative_summary",
                     "factor_decomp_adverse", "factor_decomp_severe",
                     "asset_class_sens_adverse", "asset_class_sens_severe",
                     "multi_reverse", "ccar", "climate_capital",
                     "liquidity_stress", "liquidity_recovery_ladder",
                     "recovery_table", "comparison"}
    assert expected_keys <= set(sd.keys())


def test_pipeline_stress_deep_monotone():
    """파이프라인 전체에서 시나리오 단조성 유지 — 검증 핵심."""
    from risk_lib.pipeline import run_pipeline
    r = run_pipeline()
    s = r.stress
    base = s[s["scenario"] == "baseline"].iloc[0]
    adv = s[s["scenario"] == "adverse"].iloc[0]
    sev = s[s["scenario"] == "severely_adverse"].iloc[0]
    # RWA 비감소
    assert base["rwa_total"] <= adv["rwa_total"] <= sev["rwa_total"] + 1e-6
    # CET1 비증가
    assert sev["cet1_ratio"] <= adv["cet1_ratio"] <= base["cet1_ratio"] + 1e-9
