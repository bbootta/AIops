"""AI 사고 시나리오 스트레스 (risk_lib.stress.ai_incident) 회귀·불변식.

수치 골든은 conftest 의 고정 기준일(2026-06-11) 표본에서 나온다. 모수 대부분이
재량 관리값이므로 골든은 "맞는 값"이 아니라 "바뀌면 알아채야 하는 값"이다.
모수를 고치면 이 표와 GOLDEN_VALIDATION 을 함께 고치고 사유를 남긴다.
"""

from __future__ import annotations

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.stress import ai_incident as ai

# 심각 심도 단독 시나리오의 최저 CET1비율 변화 (bp). 결합은 AI 사고 증분.
# AI-01 은 SEC 2013-222 원문의 45분, AI-07 은 감독 보수성 배수를 자본 산출에만
# 넣은 값이다 (적대적 검토 반영).
GOLDEN_SEVERE_BP = {
    "AI-01": -24.402409, "AI-02": -61.530503, "AI-03": -21.332873,
    "AI-04": -14.857236, "AI-05": -17.313897, "AI-06": -10.452455,
    "AI-07": -15.134452,
}
GOLDEN_COMBINED_TROUGH = {"AI-C1": 0.035868, "AI-C2": 0.036834}
# 이 표본은 AI 사고 전에 이미 Tier1·총자본 요구치 미달이다. 3계층 기준 임계는 0 이고
# CET1 계층 임계만 값이 있다.
GOLDEN_LOSS_STAR_BI_CET1 = 0.042594


def _t(result, name):
    return result.ledger_tables[name]


def test_ledgers_are_in_the_catalog_and_materialised(result):
    names = {sp.name for sp in cat.ALL_TABLES}
    for sp in ai.SPECS:
        assert sp.name in names, f"{sp.name} 이 카탈로그에 없다"
        df = _t(result, sp.name)
        assert len(df), f"{sp.name} 이 비었다"
        assert list(df.columns) == [c.name for c in sp.columns], sp.name


def test_basel_event_types_are_catalogue_codes():
    used = {s.basel_event_type for s in ai.SCENARIOS if s.basel_event_type}
    assert used <= set(cat.OP_EVENT_TYPES), used - set(cat.OP_EVENT_TYPES)


def test_every_parameter_carries_a_citation_and_a_known_status():
    from risk_lib.alm.params import EVIDENCE_STATUS
    for p in ai.PARAMS:
        assert p.citation.strip(), (p.scenario_id, p.channel)
        assert p.evidence_status in EVIDENCE_STATUS, (p.scenario_id, p.channel)


@pytest.mark.parametrize("sid,golden", sorted(GOLDEN_SEVERE_BP.items()))
def test_severe_delta_cet1_bp_regression(result, sid, golden):
    imp = _t(result, "st_ai_impact")
    row = imp[(imp["scenario_id"] == sid) & (imp["severity_key"] == "severely_adverse")]
    assert len(row) == 1
    assert row["delta_cet1_bp"].iloc[0] == pytest.approx(golden, abs=1e-5)


@pytest.mark.parametrize("sid,golden", sorted(GOLDEN_COMBINED_TROUGH.items()))
def test_combined_trough_regression(result, sid, golden):
    imp = _t(result, "st_ai_impact")
    row = imp[imp["scenario_id"] == sid]
    assert row["cet1_ratio_trough"].iloc[0] == pytest.approx(golden, abs=1e-6)


def test_reverse_critical_loss_regression(result):
    rev = _t(result, "st_ai_reverse").set_index("metric_id")
    assert rev.loc["loss_star_bi", "value"] == 0.0
    assert bool(rev.loc["loss_star_bi", "already_breached"])
    assert rev.loc["loss_star_bi_cet1", "value"] == pytest.approx(
        GOLDEN_LOSS_STAR_BI_CET1, abs=1e-6)
    # ILM 경로를 끈 닫힌 해는 ILM 이 손실을 키우므로 항상 더 크다.
    assert rev.loc["loss_star_bi_no_ilm_cet1", "value"] > rev.loc["loss_star_bi_cet1", "value"]


def test_requirement_test_uses_all_three_tiers(result):
    """엔진 판정과 같이 CET1·Tier1·총자본(완충 포함)의 구속 계층으로 본다 (F-F02)."""
    base = result.ai_incident.base
    assert base["binding_surplus"] < 0 <= base["cet1_surplus"]
    imp = _t(result, "st_ai_impact")
    assert imp["breach"].all()
    assert not imp["cet1_breach"].all()
    path = _t(result, "st_ai_path")
    assert not path["passes"].any()
    assert (path["capital_surplus"] <= path["cet1_surplus"] + 1e-6).all()


def test_lcr_reverse_flag_follows_lcr_not_capital(result):
    rev = _t(result, "st_ai_reverse").set_index("metric_id")
    assert result.ai_incident.base["lcr"] >= 1.0
    assert not bool(rev.loc["lcr_retail_runoff_star", "already_breached"])
    assert rev.loc["lcr_retail_runoff_star", "value"] > 0


def test_capital_only_pd_multiplier_leaves_ecl_alone(result):
    """AI-07 감독 보수성 배수는 RWA 에만 들어간다. ECL 은 편의 없는 추정이다."""
    path = _t(result, "st_ai_path")
    a7 = path[(path["scenario_id"] == "AI-07") & (path["pd_multiplier"] > 1.0)]
    assert len(a7)
    assert a7["delta_ecl"].abs().max() == 0.0
    assert (a7["delta_rwa_total"] > 0).all()


def test_out_of_horizon_losses_are_kept_not_compressed():
    """짧은 시계에서 영업정지·이탈 손실을 버리거나 앞당기지 않고 시계 밖 몫으로 남긴다."""
    tl = ai.timeline(["2026Q4", "2027Q1", "2027Q2", "2027Q3"])
    sc = ai.Scale(REV=1e12, BI=1e12, OPEX=5e11, FEE=2e11, NII=8e11, NP_EAD=1e13,
                  NP_SHARE=0.4)
    plan = ai.plan_ai03(sc, "severely_adverse", tl)
    total = sum(a for a, _ in plan.nonop)
    kept = ai._cum(plan.nonop, tl.n - 1) + ai._oob(plan.nonop, tl.n)
    assert kept == pytest.approx(total)
    assert ai._oob(plan.nonop, tl.n) > 0
    for _, ws in plan.nonop:
        assert sum(ws.values()) == pytest.approx(1.0)


def test_english_build_leaves_no_korean_in_ai_ledgers(result):
    from risk_lib.ui_studio.export_en import HANGUL, Translator
    tr = Translator()
    left = set()
    for sp in ai.SPECS:
        df = _t(result, sp.name)
        for c in df.columns:
            for v in df[c].dropna().unique():
                if isinstance(v, str) and HANGUL.search(tr.text(v)):
                    left.add(v)
    assert not left, sorted(left)[:5]


def test_severity_is_monotone_for_every_standalone_scenario(result):
    imp = _t(result, "st_ai_impact").set_index(["scenario_id", "severity_key"])
    for sid in ai.STANDALONE_IDS:
        b, a, s = (imp.loc[(sid, k), "delta_cet1_bp"] for k in ai.SEVERITIES)
        assert b >= a >= s, (sid, b, a, s)


def test_cumulative_losses_never_fall(result):
    path = _t(result, "st_ai_path").sort_values("q_index")
    for (_sid, _sev), g in path.groupby(["scenario_id", "severity_key"]):
        for col in ("loss_op_cum", "loss_nonop_cum", "fine_cum"):
            assert g[col].is_monotonic_increasing, (_sid, _sev, col)


def test_combined_decomposition_residual_is_small(result):
    from risk_lib.validation.consistency import AI_INTERACTION_TOL_BP
    path = _t(result, "st_ai_path")
    assert path["interaction_bp"].abs().max() <= AI_INTERACTION_TOL_BP


def test_second_line_checks_ran_with_expected_statuses(result):
    got = {c.name: c.status for c in result.validation.checks
           if c.name.startswith("stress_ai_")}
    assert got == {
        "stress_ai_base_reconciles": "PASS",
        "stress_ai_severity_monotone": "PASS",
        "stress_ai_losses_cumulative": "PASS",
        "stress_ai_channel_separation": "PASS",
        "stress_ai_statutory_caps": "PASS",
        "stress_ai_evidence_registered": "PASS",
        # 기준점이 이미 Tier1·총자본 요구치 미달이다
        "stress_ai_trough_meets_requirement": "FAIL",
        "stress_ai_lcr_floor": "WARN",
        "stress_ai_combined_decomposition": "PASS",
    }
    breach = next(c for c in result.validation.checks
                  if c.name == "stress_ai_trough_meets_requirement")
    assert breach.blocks_approval


def test_missing_ledger_fails_closed(result):
    from risk_lib.validation.consistency import ValidationReport, _check_ai_incident
    tables = {k: v for k, v in result.ledger_tables.items() if k != "st_ai_path"}
    rep = ValidationReport()
    _check_ai_incident(tables, result.ai_incident, result.bis, rep)
    assert [(c.name, c.status) for c in rep.checks] == [("stress_ai_ledgers_present", "FAIL")]


def test_headlines_are_in_the_recalc_scope_and_read_from_the_ledgers(result):
    from risk_lib.validation.independent import RECALC_SCOPE, _headline
    keys = ("ai_stress_worst_delta_cet1_bp", "ai_stress_trough_cet1",
            "ai_combined_trough_cet1", "ai_reverse_critical_loss_bi", "ai_stress_lcr_min")
    scope = {row[0] for row in RECALC_SCOPE}
    for k in keys:
        assert k in scope, k
    h = _headline(result, result.ledger_tables)
    assert h["ai_stress_worst_delta_cet1_bp"] == pytest.approx(min(GOLDEN_SEVERE_BP.values()), abs=1e-5)
    assert h["ai_combined_trough_cet1"] == pytest.approx(min(GOLDEN_COMBINED_TROUGH.values()), abs=1e-6)
    assert h["ai_reverse_critical_loss_bi"] == 0.0
