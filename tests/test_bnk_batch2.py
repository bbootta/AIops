"""은행 부문 미구현 요건 (BNK-ST-005 경영조치 · BNK-CRE-006 PMA·GL 대사).

두 요건의 공통 검사는 하나다. **근거가 없으면 판정하지 않는다.** 조치의
자본효과 가정이 없으면 자본경로를 고치지 않고, 총계정원장 잔액이 없으면
대사를 통과시키지 않는다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from risk_lib.datamodel.spec import TableSpec, check_refs, validate
from risk_lib.provisioning import pma
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.stress import management_action as ma

ASOF = "2026-06-11"

_MODULES = (ma, pma)


def _specs(module) -> dict[str, TableSpec]:
    return {s.name: s for s in module.SPECS}


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__)
def test_every_spec_declares_grain_key_and_units(module):
    for spec in module.SPECS:
        assert spec.grain.strip(), f"{spec.name}: 입도 미기재"
        assert spec.primary_key, f"{spec.name}: 기본키 미지정"
        for col in spec.columns:
            if col.dtype == "float":
                assert col.unit, f"{spec.name}.{col.name}: float 컬럼에 단위 없음"


# ----- BNK-ST-005 경영조치 -----------------------------------------------------

@pytest.fixture(scope="module")
def capital_path():
    return pd.DataFrame({
        "scenario": ["기준", "악화", "심각"] * 2,
        "quarter": ["2026Q3"] * 3 + ["2026Q4"] * 3,
        "cet1_ratio": [0.130, 0.100, 0.060, 0.128, 0.095, 0.055],
        "tier1_ratio": [0.140, 0.110, 0.070, 0.138, 0.105, 0.065],
        "total_ratio": [0.160, 0.130, 0.090, 0.158, 0.125, 0.085],
    })


@pytest.fixture(scope="module")
def required():
    return {"cet1": 0.08, "tier1": 0.095, "total": 0.115}


@pytest.fixture(scope="module")
def action_tables(capital_path, required):
    return ma.build_management_actions(capital_path, required)


def test_action_ledgers_match_specs_and_references(action_tables):
    tables, _ = action_tables
    specs = _specs(ma)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(tables, specs)


def test_trigger_levels_come_from_the_caller_not_from_the_module(required):
    """규제 임계는 인자로 받은 요구비율 그대로여야 한다. 별사본을 두지 않는다."""
    book = ma.build_action_playbook(required)
    regulated = book[book["trigger_level"].notna()]
    for _, r in regulated.iterrows():
        metric = str(r["trigger_metric"]).replace("_ratio", "")
        assert float(r["trigger_level"]) == required[metric]


def test_actions_fire_only_where_the_path_breaches(action_tables, capital_path):
    tables, _ = action_tables
    fired = tables["st_management_action"]
    fired = fired[fired["status"] == "발동"]
    assert set(fired["scenario"]) == {"심각"}
    for _, r in fired.iterrows():
        row = capital_path[(capital_path["scenario"] == r["scenario"])
                           & (capital_path["quarter"] == r["quarter"])].iloc[0]
        assert float(row[r["trigger_metric"]]) < float(r["trigger_level"])


def test_playbook_carries_the_source_clause(required):
    """발동표가 존재해야 하는 근거를 원장에 남긴다."""
    book = ma.build_action_playbook(required)
    assert (book["citation"].str.contains("별표 19")).all()
    regulated = book[book["trigger_level"].notna()]
    assert (regulated["evidence_status"] == "원문확인").all()
    assert "제26항 라" in ma.MITIGATION_CITATION


def test_capital_effect_is_never_invented(action_tables):
    tables, skipped = action_tables
    assert tables["st_action_playbook"]["capital_effect_bp"].isna().all()
    assert tables["st_management_action"]["capital_effect_bp"].isna().all()
    assert any("자본 개선폭" in s for s in skipped)


def test_internal_thresholds_without_approval_stay_unjudged(action_tables):
    tables, skipped = action_tables
    actions = tables["st_management_action"]
    unjudged = actions[actions["status"] == "판정불가"]
    assert set(unjudged["action_id"]) == {"MA-02", "MA-05", "MA-06"}
    assert unjudged["trigger_level"].isna().all()
    assert sum("임계 NULL" in s for s in skipped) == 3


def test_no_breach_still_leaves_a_row(required):
    """저촉이 없어도 행을 남긴다. 행이 없으면 판정하지 않은 것과 구분되지 않는다."""
    healthy = pd.DataFrame({
        "scenario": ["기준"], "quarter": ["2026Q3"], "cet1_ratio": [0.15],
        "tier1_ratio": [0.16], "total_ratio": [0.18]})
    tables, _ = ma.build_management_actions(healthy, required)
    actions = tables["st_management_action"]
    assert "발동" not in set(actions["status"])
    assert "미발동" in set(actions["status"])


# ----- BNK-CRE-006 PMA·GL 대사 -------------------------------------------------

@pytest.fixture(scope="module")
def segment_ecl(portfolio):
    return pma.segment_ecl_from_result(compute_ecl(portfolio))


@pytest.fixture(scope="module")
def pma_tables(segment_ecl):
    return pma.build_pma_and_recon(segment_ecl, asof=ASOF)


def test_pma_ledgers_match_specs(pma_tables):
    tables, _ = pma_tables
    specs = _specs(pma)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"


def test_adjustment_without_segregation_of_duties_is_not_applied(pma_tables):
    tables, blocked = pma_tables
    p = tables["ecl_pma"].set_index("pma_id")
    assert p.loc["PMA-004", "status"] == "미적용"
    assert "직무분리 위반" in p.loc["PMA-004", "control_note"]
    assert any("PMA-004" in b for b in blocked)


def test_adjustment_without_evidence_reference_is_not_applied(pma_tables):
    tables, _ = pma_tables
    p = tables["ecl_pma"].set_index("pma_id")
    assert p.loc["PMA-005", "status"] == "미적용"
    assert "증빙 참조 미기재" in p.loc["PMA-005", "control_note"]


def test_blocked_adjustments_do_not_move_the_reported_number(segment_ecl):
    """미적용 조정은 보고 충당금에 들어가지 않는다."""
    p = pma.build_pma(segment_ecl, asof=ASOF)
    recon, _ = pma.reconcile_gl(segment_ecl, p)
    blocked_segments = set(p[p["status"] == "미적용"]["segment"])
    for seg in blocked_segments:
        row = recon[recon["segment"] == seg].iloc[0]
        applied = p[(p["segment"] == seg) & (p["status"] == "적용")]["pma_amount"].sum()
        assert row["pma_applied"] == pytest.approx(applied)


def test_expired_adjustment_is_blocked(segment_ecl):
    """유효기간이 지난 조정은 자동으로 무효다."""
    p = pma.build_pma(segment_ecl, asof=ASOF)
    row = p.iloc[0].to_dict()
    row["expires_on"] = "2020-01-01"
    assert any("유효기간 만료" in v for v in pma.control_violations(row, asof=ASOF))


def test_reconciliation_without_a_gl_feed_is_not_marked_as_passing(pma_tables):
    tables, problems = pma_tables
    recon = tables["ecl_gl_reconciliation"]
    assert set(recon["status"]) == {"미대사"}
    assert recon["gl_balance"].isna().all()
    assert any("대사를 수행하지 않았다" in p for p in problems)


def test_reconciliation_detects_an_unrecorded_adjustment(segment_ecl):
    """원장에 없는 조정이 개입하면 대사에서 차이로 드러난다."""
    p = pma.build_pma(segment_ecl, asof=ASOF)
    applied = p[p["status"] == "적용"].groupby("segment")["pma_amount"].sum()
    gl = {str(r["segment"]): float(r["ecl"]) + float(applied.get(r["segment"], 0.0))
          for _, r in segment_ecl.iterrows()}
    recon, problems = pma.reconcile_gl(segment_ecl, p, gl_balances=gl)
    assert set(recon["status"]) <= {"일치"}
    assert not problems

    biggest = str(segment_ecl.loc[segment_ecl["ecl"].idxmax(), "segment"])
    gl[biggest] += 1_000_000_000.0
    recon, problems = pma.reconcile_gl(segment_ecl, p, gl_balances=gl)
    assert recon[recon["segment"] == biggest].iloc[0]["status"] == "차이"
    assert problems


def test_adjustment_for_a_missing_segment_is_not_created():
    small = pd.DataFrame({"segment": ["corporate"], "ecl": [1.0e10]})
    p = pma.build_pma(small, asof=ASOF)
    assert set(p["segment"]) == {"corporate"}
