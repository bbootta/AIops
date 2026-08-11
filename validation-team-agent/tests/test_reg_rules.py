"""규제 규칙 카탈로그 — 규칙마다 위반 fixture 로 반증한다.

실패할 수 없는 검사는 통제가 아니다 (F-602 · F-E01). 특히 다음 셋은 요건
개요서의 샘플 케이스를 그대로 실행 가능한 검사로 옮긴 것이다.

  OVR-000  '정기적' 을 법정 연 1회로 오표기하면 verify 가 실패한다
  OVR-001  출력하한 65/70/72.5% 가 날짜에서 파생된다 (경계일 포함)
  OVR-009  RETIRED 규칙은 대체 규칙 없이 존재할 수 없다
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from tools.reg_rules import (
    calendar, effective_rules, load, output_floor_factor, verify,
)

# ------------------------------------------------------------- 합성 fixture


def _catalog() -> dict[str, Any]:
    return {
        "rules": [
            {"rule_id": "R-1", "title": "t", "authority_level": "DOMESTIC_BINDING",
             "source_locator": "세칙 별표 X", "status": "ACTIVE",
             "effective_from": "2026-01-01", "effective_to": None,
             "frequency_raw": "연 1회 이상", "frequency_basis": "LEGAL",
             "internal_frequency": "ANNUAL", "trigger": "정기",
             "params": {}, "required_evidence": ["보고서"]},
            {"rule_id": "F-26", "title": "floor 2026",
             "authority_level": "DOMESTIC_BINDING", "source_locator": "별표 3-2",
             "status": "ACTIVE", "group_id": "OUTPUT_FLOOR",
             "effective_from": "2026-01-01", "effective_to": "2026-12-31",
             "frequency_raw": "상시 적용", "frequency_basis": "LEGAL",
             "internal_frequency": "CONTINUOUS", "trigger": "상시",
             "params": {"floor_factor": 0.65}, "required_evidence": ["대사"]},
            {"rule_id": "F-27", "title": "floor 2027",
             "authority_level": "DOMESTIC_BINDING", "source_locator": "별표 3-2",
             "status": "ACTIVE", "group_id": "OUTPUT_FLOOR",
             "effective_from": "2027-01-01", "effective_to": None,
             "frequency_raw": "상시 적용", "frequency_basis": "LEGAL",
             "internal_frequency": "CONTINUOUS", "trigger": "상시",
             "params": {"floor_factor": 0.70}, "required_evidence": ["대사"]},
            {"rule_id": "OLD-1", "title": "폐기",
             "authority_level": "INTERNAL_POLICY", "source_locator": "구교재",
             "status": "RETIRED", "effective_from": "2016-01-01",
             "effective_to": "2025-12-31", "replaced_by": "R-1",
             "frequency_raw": "폐기", "frequency_basis": "INTERNAL_POLICY",
             "internal_frequency": "NONE", "trigger": "차단",
             "params": {}, "required_evidence": ["매핑"]},
        ],
        "opinion_map": {
            "note": "명칭은 내부정책 정의",
            "codes": {
                "SATISFACTORY": {"exchange_verdict": "적합"},
                "SATISFACTORY_WITH_CONDITIONS": {"exchange_verdict": "경부적합"},
                "NEEDS_IMPROVEMENT": {"exchange_verdict": "중부적합"},
                "UNSATISFACTORY": {"exchange_verdict": "중부적합"},
                "NO_OPINION": {"exchange_verdict": "없음"},
            },
        },
    }


def test_clean_fixture_passes():
    assert verify(_catalog()) == []


# ------------------------------------------------ OVR-000: 주기 오표기 방지

def test_periodic_raw_cannot_claim_legal_basis():
    """'정기적' 원문에 basis=LEGAL 을 달면 실패해야 한다 — 오표기의 원형."""
    c = _catalog()
    c["rules"][0]["frequency_raw"] = "정기적"
    assert any("오표기 금지" in p for p in verify(c))


def test_periodic_raw_with_internal_basis_is_fine():
    c = _catalog()
    c["rules"][0]["frequency_raw"] = "정기적"
    c["rules"][0]["frequency_basis"] = "INTERNAL_POLICY"
    assert verify(c) == []


def test_calendar_never_labels_unspecified_as_legal():
    """수용기준(OVR-004): 근거 없는 법정주기 생성 0건."""
    c = _catalog()
    c["rules"][0]["frequency_raw"] = "정기적"
    c["rules"][0]["frequency_basis"] = "INTERNAL_POLICY"
    rows = calendar(date(2026, 6, 30), c)
    row = next(r for r in rows if r["rule_id"] == "R-1")
    assert row["basis"] == "INTERNAL_POLICY"
    assert "법정 미명시" in row["label"] and "내부정책" in row["label"]


# ------------------------------------------------ OVR-001: 유효일자 경과조치

def test_floor_factor_follows_effective_dates():
    c = _catalog()
    assert output_floor_factor(date(2025, 12, 31), c) is None
    assert output_floor_factor(date(2026, 1, 1), c) == 0.65
    assert output_floor_factor(date(2026, 12, 31), c) == 0.65
    assert output_floor_factor(date(2027, 1, 1), c) == 0.70


def test_real_catalog_floor_matches_overview_document():
    """개요서 OVR-001 — 2026 65% · 2027 70% · 2028~ 72.5%."""
    assert output_floor_factor(date(2026, 6, 30)) == 0.65
    assert output_floor_factor(date(2027, 6, 30)) == 0.70
    assert output_floor_factor(date(2028, 1, 1)) == 0.725
    assert output_floor_factor(date(2030, 1, 1)) == 0.725


def test_run_20260630_floor_would_be_65_percent_and_still_nonbinding():
    """15회 교환의 실측 대입 — 경과조치 65% 를 적용해도 하한은 미구속이다.

    floor base 7,347,159,561,697.40 × 0.65 = 4,775,653,715,103.31 <
    내부모형 합계 9,399,913,501,716.785 이므로 rwa_final 불변. 즉 CO-010 은
    산출값 오류가 아니라 규칙 유효일자 규율의 문제다.
    """
    factor = output_floor_factor(date(2026, 6, 30))
    assert factor == 0.65
    floor_amt = 7_347_159_561_697.397 * factor
    internal = 9_399_913_501_716.785
    assert floor_amt < internal          # 미구속 — 산출값 영향 0
    # 기존 상수(72.5%)로도 미구속이었으므로 두 계수 모두 결과는 같다
    assert 7_347_159_561_697.397 * 0.725 < internal


def test_overlapping_group_windows_fail():
    c = _catalog()
    c["rules"][1]["effective_to"] = "2027-06-30"     # 2027 규칙과 겹침
    assert any("겹친다" in p for p in verify(c))


def test_open_ended_rule_before_another_fails():
    c = _catalog()
    c["rules"][1]["effective_to"] = None             # 무기한 + 뒤 규칙 존재
    assert any("무기한" in p for p in verify(c))


def test_gap_between_group_windows_fails():
    c = _catalog()
    c["rules"][2]["effective_from"] = "2027-03-01"   # 2027-01~02 빈틈
    assert any("빈틈" in p for p in verify(c))


# ------------------------------------------------ OVR-009: 폐기 수치 차단

def test_retired_requires_effective_to_and_replacement():
    c = _catalog()
    del c["rules"][3]["replaced_by"]
    assert any("replaced_by" in p for p in verify(c))
    c2 = _catalog()
    c2["rules"][3]["effective_to"] = None
    assert any("effective_to" in p for p in verify(c2))


def test_retired_replacement_must_exist():
    c = _catalog()
    c["rules"][3]["replaced_by"] = "NOPE-999"
    assert any("NOPE-999" in p for p in verify(c))


def test_retired_rules_never_appear_in_effective_set():
    c = _catalog()
    ids = {r["rule_id"] for r in effective_rules(date(2020, 1, 1), c)}
    assert "OLD-1" not in ids            # 과거 날짜여도 RETIRED 는 제외


# ---------------------------------------------------- 기본 무결성의 반증

def test_unknown_authority_level_fails():
    c = _catalog()
    c["rules"][0]["authority_level"] = "GLOBAL_MAYBE"
    assert any("authority_level" in p for p in verify(c))


def test_missing_source_locator_fails():
    c = _catalog()
    c["rules"][0]["source_locator"] = "  "
    assert any("근거 없는 규칙" in p for p in verify(c))


def test_missing_required_evidence_fails():
    c = _catalog()
    c["rules"][0]["required_evidence"] = []
    assert any("required_evidence" in p for p in verify(c))


def test_duplicate_rule_id_fails():
    c = _catalog()
    c["rules"][1]["rule_id"] = "R-1"
    assert any("중복" in p for p in verify(c))


# ---------------------------------------------------- 의견 코드 매핑 반증

def test_opinion_map_must_have_all_five_codes():
    c = _catalog()
    del c["opinion_map"]["codes"]["NO_OPINION"]
    assert any("NO_OPINION 누락" in p for p in verify(c))


def test_opinion_map_rejects_unknown_codes():
    c = _catalog()
    c["opinion_map"]["codes"]["VERY_GOOD"] = {"exchange_verdict": "적합"}
    assert any("VERY_GOOD" in p for p in verify(c))


def test_opinion_map_requires_internal_policy_caveat():
    """OVR-011 — 의견 명칭을 금감원 통일의견으로 오인하게 두면 실패."""
    c = _catalog()
    c["opinion_map"]["note"] = "표준 의견 체계"
    assert any("내부정책" in p for p in verify(c))


# --------------------------------------------------------- 실제 카탈로그

def test_real_catalog_is_consistent():
    assert verify() == []


def test_real_catalog_covers_the_overview_risk_matrix():
    """개요서 §4 의 리스크 영역이 전부 등재됐는지 — 참조는 실재해야 한다."""
    ids = {r["rule_id"] for r in load()["rules"]}
    for rid in ("REG-IRB-001", "REG-ECL-001", "REG-ICAAP-001", "REG-ST-001",
                "REG-IRR-001", "REG-MKT-001", "REG-CCR-001", "REG-OPR-001",
                "REG-LIQ-001", "REG-RDARR-001",
                "REG-FLOOR-2026", "REG-FLOOR-2027", "REG-FLOOR-2028"):
        assert rid in ids, f"{rid} 미등재"
    retired = [r for r in load()["rules"] if r["status"] == "RETIRED"]
    assert retired, "폐기 규칙(OVR-009 차단 대상)이 하나도 없다"


def test_real_calendar_has_no_unfounded_legal_frequency():
    """OVR-004 수용기준 — 원문이 미명시인데 LEGAL 로 표기된 항목 0건."""
    from tools.reg_rules import UNSPECIFIED_MARKERS
    for row in calendar(date(2026, 6, 30)):
        if row["basis"] == "LEGAL":
            rule = next(r for r in load()["rules"]
                        if r["rule_id"] == row["rule_id"])
            assert not any(m in rule["frequency_raw"]
                           for m in UNSPECIFIED_MARKERS)


def test_cli_exit_codes(tmp_path, monkeypatch):
    import json as _json

    from tools import reg_rules as rr
    assert rr.main(["verify"]) == 0
    broken = copy.deepcopy(_catalog())
    broken["rules"][0]["source_locator"] = ""
    p = tmp_path / "cat.json"
    p.write_text(_json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(rr, "CATALOG_PATH", p)
    assert rr.main(["verify"]) == 1


def test_valdoc_coverage_matrix_verifies_with_shared_rules():
    """두 문서 대비 매트릭스도 PRD-VAL 과 같은 규칙으로 검증된다 (근거 실재성)."""
    from tools.val_coverage import ROOT, load as vc_load, verify as vc_verify
    data = vc_load(ROOT / "harness" / "valdoc_coverage.json")
    assert vc_verify(data) == []
    assert len(data["requirements"]) == 19
