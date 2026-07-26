"""Round 86 — 중요도 등급 (VAL-004) + 조건부 승인·제한 배포 (VAL-017)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from tools.conditional_approval import (
    ApprovalError,
    check_scope,
    compliance,
    derive,
    escalations,
    fulfil,
    grant,
    parse_condition,
    render_compliance,
)
from tools.validation_scope import (
    MATERIALITY_PATH,
    ScopeError,
    check_plan,
    load_policy,
    render_check,
    render_score,
    score_model,
)

AS = date(2026, 7, 25)

HIGH = {"model_id": "CSS-RETAIL-01", "exposure_share": 0.35,
        "regulatory_use": "direct", "decision_impact": "automated",
        "complexity": "statistical"}
LOW = {"model_id": "AUX-01", "exposure_share": 0.001,
       "regulatory_use": "internal_only", "decision_impact": "monitoring",
       "complexity": "rule_based"}


def _cond(desc="원천 대사 완료", owner="alm_owner", due="2026-08-15"):
    return parse_condition(f"{desc}|{owner}|{due}")


# =========================== VAL-004 중요도 등급 ===========================

def test_policy_is_valid_json():
    json.loads(MATERIALITY_PATH.read_text(encoding="utf-8"))


def test_high_materiality_model_is_tier1():
    s = score_model(HIGH)
    assert s["tier"] == "tier1"
    assert s["score"] == 11 and s["max_score"] == 12
    assert s["requirements"]["min_depth"] == "full"


def test_low_materiality_model_is_tier3():
    s = score_model(LOW)
    assert s["tier"] == "tier3"
    assert s["requirements"]["independent_validation_required"] is False


def test_score_breakdown_explains_every_factor():
    """왜 그 등급인지 설명 가능해야 한다."""
    s = score_model(HIGH)
    keys = {b["key"] for b in s["breakdown"]}
    assert keys == {"exposure_share", "regulatory_use", "decision_impact",
                    "complexity"}
    for b in s["breakdown"]:
        assert b["rationale"].strip() and b["value_label"].strip()


def test_missing_attribute_rejected():
    with pytest.raises(ScopeError, match="입력 누락"):
        score_model({k: v for k, v in HIGH.items() if k != "complexity"})


def test_unknown_category_rejected():
    with pytest.raises(ScopeError, match="알 수 없는 값"):
        score_model({**HIGH, "regulatory_use": "maybe"})


def test_non_numeric_exposure_rejected():
    with pytest.raises(ScopeError, match="수치가 필요"):
        score_model({**HIGH, "exposure_share": "높음"})
    with pytest.raises(ScopeError, match="수치가 필요"):
        score_model({**HIGH, "exposure_share": True})


def test_negative_exposure_rejected():
    with pytest.raises(ScopeError, match="음수"):
        score_model({**HIGH, "exposure_share": -0.1})


def test_plan_below_minimum_depth_is_violation():
    r = check_plan(HIGH, {"depth": "light", "revalidation_cycle_months": 36,
                          "independent_validation": False}, as_of=AS)
    assert not r["passed"]
    types = {v["type"] for v in r["violations"]}
    assert {"depth_below_minimum", "cycle_exceeds_maximum",
            "independence_missing"} <= types


def test_compliant_plan_passes():
    r = check_plan(HIGH, {"depth": "full", "revalidation_cycle_months": 12,
                          "independent_validation": True}, as_of=AS)
    assert r["passed"], r["violations"]


def test_stricter_plan_passes():
    """최소 기준보다 엄격한 계획은 당연히 통과."""
    r = check_plan(LOW, {"depth": "full", "revalidation_cycle_months": 6,
                         "independent_validation": True}, as_of=AS)
    assert r["passed"]


def test_valid_exception_permits_lower_depth():
    plan = {"depth": "standard", "revalidation_cycle_months": 12,
            "independent_validation": True,
            "exception": {"rationale": "신규 도입 유예", "approver": "APR-301",
                          "expires_at": "2026-12-31"}}
    r = check_plan(HIGH, plan, as_of=AS)
    assert r["passed"]
    assert any("예외 유효" in n for n in r["notes"])


def test_expired_exception_has_no_effect():
    plan = {"depth": "standard", "revalidation_cycle_months": 12,
            "independent_validation": True,
            "exception": {"rationale": "유예", "approver": "APR-301",
                          "expires_at": "2026-12-31"}}
    r = check_plan(HIGH, plan, as_of=date(2027, 1, 15))
    assert not r["passed"]
    assert any("만료" in n for n in r["notes"])


@pytest.mark.parametrize("missing", ["rationale", "approver", "expires_at"])
def test_incomplete_exception_has_no_effect(missing):
    exc = {"rationale": "유예", "approver": "APR-301",
           "expires_at": "2026-12-31"}
    exc.pop(missing)
    r = check_plan(HIGH, {"depth": "standard", "revalidation_cycle_months": 12,
                          "independent_validation": True, "exception": exc},
                   as_of=AS)
    assert not r["passed"]
    assert any("필수 항목 누락" in n for n in r["notes"])


def test_independence_cannot_be_waived_by_exception():
    """독립검증 면제는 등급 자체를 바꾸는 것과 같으므로 예외로 불가."""
    plan = {"depth": "full", "revalidation_cycle_months": 12,
            "independent_validation": False,
            "exception": {"rationale": "인력 부족", "approver": "APR-301",
                          "expires_at": "2026-12-31"}}
    r = check_plan(HIGH, plan, as_of=AS)
    assert not r["passed"]
    assert any(v["type"] == "independence_missing" for v in r["violations"])


def test_unknown_depth_rejected():
    r = check_plan(HIGH, {"depth": "적당히", "revalidation_cycle_months": 12,
                          "independent_validation": True}, as_of=AS)
    assert any(v["type"] == "unknown_depth" for v in r["violations"])


def test_missing_cycle_is_violation():
    r = check_plan(HIGH, {"depth": "full", "independent_validation": True},
                   as_of=AS)
    assert any(v["type"] == "missing_cycle" for v in r["violations"])


def test_renderers():
    assert "중요도 산정" in render_score(score_model(HIGH))
    text = render_check(check_plan(HIGH, {"depth": "light",
                                          "revalidation_cycle_months": 36,
                                          "independent_validation": False},
                                   as_of=AS))
    assert "[위반]" in text and "부적정" in text


def test_scope_cli(tmp_path):
    from tools.validation_scope import main

    attrs = tmp_path / "m.json"
    attrs.write_text(json.dumps(HIGH), encoding="utf-8")
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"depth": "full",
                                "revalidation_cycle_months": 12,
                                "independent_validation": True}),
                    encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"depth": "light",
                               "revalidation_cycle_months": 36,
                               "independent_validation": False}),
                   encoding="utf-8")
    assert main(["tiers"]) == 0
    assert main(["score", "--attributes", str(attrs)]) == 0
    assert main(["check", "--attributes", str(attrs), "--plan", str(good),
                 "--as-of", "2026-07-25"]) == 0
    assert main(["check", "--attributes", str(attrs), "--plan", str(bad),
                 "--as-of", "2026-07-25"]) == 1


# ======================= VAL-017 조건부 승인·제한 배포 =======================

def _granted(**over):
    kw = dict(change_id="CHG-0150", approver="APR-301",
              residual_risk="LCR 재계산 차이 미해소",
              deployment_scope="리테일 포트폴리오 한정",
              conditions=[_cond()], as_of=AS)
    kw.update(over)
    return grant(**kw)


def test_conditional_approval_requires_conditions():
    with pytest.raises(ApprovalError, match="후속조건 없는"):
        _granted(conditions=[])


def test_requires_residual_risk_and_scope():
    with pytest.raises(ApprovalError, match="잔여위험"):
        _granted(residual_risk="   ")
    with pytest.raises(ApprovalError, match="배포 범위"):
        _granted(deployment_scope=" ")


def test_only_approver_role_may_grant():
    with pytest.raises(ApprovalError, match="승인 권한이 없다"):
        _granted(approver="DEV-101")
    with pytest.raises(ApprovalError, match="승인 권한이 없다"):
        _granted(approver="REV-201")


def test_sod_can_be_disabled_explicitly():
    row = _granted(approver="DEV-101", enforce_sod=False)
    assert row["approver"] == "DEV-101"


def test_duplicate_grant_rejected():
    first = _granted()
    with pytest.raises(ApprovalError, match="이미 조건부 승인"):
        _granted(existing=[first])


def test_condition_format_validation():
    with pytest.raises(ApprovalError, match="조건 형식"):
        parse_condition("설명만 있음")
    with pytest.raises(ApprovalError, match="기한 형식"):
        parse_condition("설명|owner|2026-13-45")


def test_condition_missing_field_rejected():
    with pytest.raises(ApprovalError, match="조건 필수 항목 누락"):
        _granted(conditions=[{"description": "d", "owner_role": "",
                              "due_at": "2026-08-15"}])


def test_overdue_condition_escalates():
    rows = [_granted(conditions=[_cond(due="2026-08-15")])]
    st = derive(rows)
    assert escalations(st, as_of=AS) == []
    esc = escalations(st, as_of=date(2026, 9, 1))
    assert [e["change_id"] for e in esc] == ["CHG-0150"]


def test_fulfilment_clears_escalation():
    rows = [_granted(conditions=[_cond(due="2026-08-15")])]
    rows.append(fulfil("CHG-0150", condition_index=0, evidence="대사표 첨부",
                       as_of=date(2026, 8, 10), approvals=rows))
    st = derive(rows)
    assert escalations(st, as_of=date(2026, 9, 1)) == []
    assert compliance(st, as_of=date(2026, 9, 1))[0]["fully_fulfilled"]


def test_fulfilment_requires_evidence():
    rows = [_granted()]
    with pytest.raises(ApprovalError, match="증빙 없이"):
        fulfil("CHG-0150", condition_index=0, evidence="  ", as_of=AS,
               approvals=rows)


def test_double_fulfilment_rejected():
    rows = [_granted()]
    rows.append(fulfil("CHG-0150", condition_index=0, evidence="e",
                       as_of=AS, approvals=rows))
    with pytest.raises(ApprovalError, match="이미 이행"):
        fulfil("CHG-0150", condition_index=0, evidence="e", as_of=AS,
               approvals=rows)


def test_fulfilment_index_out_of_range():
    rows = [_granted()]
    with pytest.raises(ApprovalError, match="범위 밖"):
        fulfil("CHG-0150", condition_index=9, evidence="e", as_of=AS,
               approvals=rows)


def test_fulfilment_without_grant_rejected():
    with pytest.raises(ApprovalError, match="조건부 승인이 없다"):
        fulfil("CHG-X", condition_index=0, evidence="e", as_of=AS,
               approvals=[])


def test_orphan_event_rejected():
    with pytest.raises(ApprovalError, match="granted 없이"):
        derive([{"event": "condition_fulfilled", "change_id": "CHG-Z",
                 "condition_index": 0, "at": "2026-07-25", "evidence": "e"}])


def test_scope_check_allows_declared_usage():
    st = derive([_granted()])
    r = check_scope("CHG-0150", "리테일 포트폴리오", states=st)
    assert r["allowed"]


def test_scope_check_blocks_out_of_scope_usage():
    st = derive([_granted()])
    r = check_scope("CHG-0150", "기업 포트폴리오", states=st)
    assert not r["allowed"]
    assert "승인 재요청" in r["reason"]


def test_scope_check_without_approval_is_blocked():
    r = check_scope("CHG-NONE", "무엇이든", states={})
    assert not r["allowed"]
    assert "근거 없음" in r["reason"]


def test_render_compliance_marks_escalation():
    rows = [_granted(conditions=[_cond(due="2026-08-15")])]
    text = render_compliance(compliance(derive(rows), as_of=date(2026, 9, 1)))
    assert "[에스컬레이션]" in text and "[기한초과]" in text


def test_render_compliance_empty():
    assert "없음" in render_compliance([])


def test_approval_cli(tmp_path, monkeypatch):
    from tools import conditional_approval as ca

    ledger = tmp_path / "ca.jsonl"
    monkeypatch.setattr(ca, "APPROVALS_PATH", ledger)
    assert ca.main(["grant", "--change-id", "CHG-1", "--approver", "APR-301",
                    "--residual-risk", "잔여위험", "--scope", "리테일 한정",
                    "--condition", "대사 완료|alm_owner|2026-08-15",
                    "--as-of", "2026-07-25"]) == 0
    assert ca.main(["status", "--as-of", "2026-07-25"]) == 0
    assert ca.main(["status", "--as-of", "2026-09-01"]) == 1   # 기한초과
    assert ca.main(["check-scope", "--change-id", "CHG-1",
                    "--usage", "리테일"]) == 0
    assert ca.main(["check-scope", "--change-id", "CHG-1",
                    "--usage", "기업"]) == 1
    assert ca.main(["grant", "--change-id", "CHG-2", "--approver", "DEV-101",
                    "--residual-risk", "r", "--scope", "s",
                    "--condition", "c|o|2026-08-15"]) == 2   # 권한 없음


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    names = {m for m, _ in CLI_MODULES}
    assert {"tools.validation_scope", "tools.conditional_approval"} <= names
    assert ("scope",) in _DISPATCH and ("approval",) in _DISPATCH


def test_policy_tier_requirements_reference_defined_depths():
    pol = load_policy()
    depths = set(pol["depth_levels"])
    for tier, req in pol["tier_requirements"].items():
        assert req["min_depth"] in depths, tier
