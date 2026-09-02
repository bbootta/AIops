"""규제 미달 WARN 을 결재 차단 사유로 (2026-09 검수 4단계).

FAIL 0 이어도 완충자본 미달·위기상황 저점 미달·한도 위반·P2R 부재는 결재에
올릴 수 없는 상태다. 심각도는 WARN 으로 두되(합성 자본이라 계산 결함이 아님)
`blocks_approval` 표시가 붙고, `approval_blockers()` 가 그것을 FAIL 과 함께
돌려준다. 이 표시가 val_check 원장까지 실려야 결재선·요청서가 읽는다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.validation import consistency as C


def _rep():
    return C.ValidationReport()


class _Bis:
    def __init__(self, short, req):
        self.surplus_shortfall = short
        self.required = req
        self.cet1_ratio = 0.10; self.tier1_ratio = 0.11; self.total_ratio = 0.12
        self.rwa = 1.0


def test_buffer_shortfall_blocks_approval_but_stays_warn():
    rep = _rep()
    bis = _Bis({"cet1": 0.01, "tier1": -0.0034, "total": -0.0056},
               {"cet1": 0.07, "tier1": 0.095, "total": 0.115})
    C._check_bis_plausible(bis, rep)
    c = next(x for x in rep.checks if x.name == "bis_buffer_requirement")
    assert c.status == "WARN" and c.blocks_approval
    assert c in rep.approval_blockers()


def test_buffer_met_does_not_block():
    rep = _rep()
    bis = _Bis({"cet1": 0.01, "tier1": 0.01, "total": 0.02},
               {"cet1": 0.07, "tier1": 0.095, "total": 0.115})
    C._check_bis_plausible(bis, rep)
    c = next(x for x in rep.checks if x.name == "bis_buffer_requirement")
    assert c.status == "PASS" and not c.blocks_approval


def test_stress_trough_checks_all_three_tiers():
    """CET1 은 지키고 총자본만 깨지는 경로가 잡혀야 한다 (F-F02)."""
    rep = _rep()
    bis = _Bis({}, {"cet1": 0.045, "tier1": 0.06, "total": 0.08})
    path = pd.DataFrame({
        "scenario": ["adverse"] * 2, "quarter": ["2027Q1", "2027Q2"],
        "cet1_ratio": [0.09, 0.085],      # 요구 4.5% 위
        "tier1_ratio": [0.10, 0.095],
        "total_ratio": [0.081, 0.079],    # 요구 8.0% 아래로
        "binding": ["total", "total"],
    })
    C._check_stress_trough_requirement(path, bis, rep)
    c = next(x for x in rep.checks if x.name == "stress_trough_meets_requirement")
    assert c.status == "WARN" and c.blocks_approval
    assert "adverse/total" in c.detail and "cet1·tier1·total" in c.detail


def test_stress_trough_without_tier_columns_says_so():
    rep = _rep()
    bis = _Bis({}, {"cet1": 0.045, "tier1": 0.06, "total": 0.08})
    path = pd.DataFrame({"scenario": ["adverse"], "quarter": ["2027Q1"],
                         "cet1_ratio": [0.09]})
    C._check_stress_trough_requirement(path, bis, rep)
    c = next(x for x in rep.checks if x.name == "stress_trough_meets_requirement")
    assert c.status == "PASS" and "비교 계층 cet1" in c.detail


def test_pillar2_missing_blocks_approval():
    rep = _rep()
    C._check_pillar2_evidence({"pillar2": {"p2r": None, "p2g": None}}, rep)
    c = next(x for x in rep.checks if x.name == "pillar2_requirement_evidence")
    assert c.status == "WARN" and c.blocks_approval


def test_large_exposure_breaches_block_even_when_sources_agree():
    rep = _rep()
    pos = pd.DataFrame({"framework": ["은행법35조_동일차주"] * 3,
                        "breach": [True, True, False]})
    lim = pd.DataFrame({"limit": ["동일차주 한도"] * 2,
                        "severity": ["BREACH", "BREACH"]})
    C._check_large_exposure_sources(lim, {"lex_position": pos}, rep)
    c = next(x for x in rep.checks if x.name == "large_exposure_two_sources")
    assert c.status == "WARN" and c.blocks_approval


def test_large_exposure_clean_and_agreeing_is_pass():
    rep = _rep()
    pos = pd.DataFrame({"framework": ["은행법35조_동일차주"] * 2,
                        "breach": [False, False]})
    lim = pd.DataFrame({"limit": ["동일차주 한도"], "severity": ["OK"]})
    C._check_large_exposure_sources(lim, {"lex_position": pos}, rep)
    c = next(x for x in rep.checks if x.name == "large_exposure_two_sources")
    assert c.status == "PASS" and not c.blocks_approval


def test_missing_inputs_are_recorded_not_skipped():
    """조용히 return 하던 자리가 WARN 기록으로 바뀌었는지 (3단계)."""
    rep = _rep()
    C._check_leverage(None, rep)
    C._check_output_floor(None, rep)
    C._check_ecl(None, rep)
    names = {c.name for c in rep.checks}
    assert {"leverage_not_run", "output_floor_not_run", "ecl_not_run"} <= names
    assert all(c.status == "WARN" for c in rep.checks)


def test_sa_irb_overlap_without_ids_is_not_a_pass():
    rep = _rep()
    C._check_sa_irb_no_overlap(pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [1]}), rep)
    assert [c.name for c in rep.checks] == ["sa_irb_no_overlap_not_run"]


def test_identity_checks_are_excluded_from_controls_summary():
    rep = _rep()
    rep.add(C.ConsistencyCheck("x", "PASS", "", is_identity=True))
    rep.add(C.ConsistencyCheck("y", "PASS", ""))
    assert rep.summary() == {"PASS": 2}
    assert rep.controls_summary() == {"PASS": 1}
