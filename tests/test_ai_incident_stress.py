"""AI 사고 시나리오 스트레스 (risk_lib.stress.ai_incident) 회귀·불변식.

수치 골든은 conftest 의 고정 기준일(2026-06-11) 표본에서 나온다. 모수 대부분이
재량 관리값이므로 골든은 "맞는 값"이 아니라 "바뀌면 알아채야 하는 값"이다.
모수를 고치면 이 표와 GOLDEN_VALIDATION 을 함께 고치고 사유를 남긴다.
"""

from __future__ import annotations

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.stress import ai_incident as ai

# 심각 심도 단독 시나리오의 최대 CET1비율 하락 (bp). 결합은 AI 사고 증분.
GOLDEN_SEVERE_BP = {
    "AI-01": -16.425354, "AI-02": -61.530503, "AI-03": -21.332873,
    "AI-04": -14.857236, "AI-05": -17.313897, "AI-06": -10.452455,
    "AI-07": -17.788889,
}
GOLDEN_COMBINED_TROUGH = {"AI-C1": 0.035868, "AI-C2": 0.036834}
GOLDEN_LOSS_STAR_BI = 0.042594


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
    assert rev.loc["loss_star_bi", "value"] == pytest.approx(GOLDEN_LOSS_STAR_BI, abs=1e-6)
    # ILM 경로를 끈 닫힌 해는 ILM 이 손실을 키우므로 항상 더 크다.
    assert rev.loc["loss_star_bi_no_ilm", "value"] > rev.loc["loss_star_bi", "value"]


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
        "stress_ai_trough_meets_requirement": "WARN",
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
    assert h["ai_reverse_critical_loss_bi"] == pytest.approx(GOLDEN_LOSS_STAR_BI, abs=1e-6)
