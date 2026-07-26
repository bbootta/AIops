"""Round 83 — 직무분리(SoD) 통제 (VAL-006)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from middleware.sod_guard import (
    SOD_POLICY_PATH,
    STATUS_FAIL,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    SoDViolation,
    actor_roles,
    check_sod,
    load_policy,
    require_sod,
)
from tools.validation_finding import (
    close_finding,
    derive,
    open_finding,
    record_remediation,
    record_reverification,
)

AS = date(2026, 7, 25)
SLA = {"critical": 5, "high": 10, "medium": 20}


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def _lifecycle(rem_actor, rev_actor):
    ev = open_finding(title="t", domain="credit", severity="medium",
                      owner_role="credit_model_owner", as_of=AS, events=[],
                      sla_days=SLA)
    fid = ev[0]["finding_id"]
    ev.append(record_remediation(fid, action="a", root_cause="model",
                                 as_of=AS, events=ev, actor=rem_actor))
    ev.append(record_reverification(fid, result="pass", evidence="e",
                                    as_of=AS, events=ev, actor=rev_actor))
    return ev, fid


# ---------- 정책 SSoT ----------

def test_policy_shape(policy):
    assert policy["roles"] and policy["activity_required_roles"]
    assert policy["conflicts"]
    for c in policy["conflicts"]:
        assert len(c["activities"]) == 2
        assert c["rule"] == "different_actor"
        assert c["rationale"].strip()


def test_every_required_role_is_defined(policy):
    """활동에 요구되는 역할이 roles 에 실제로 정의돼 있어야 한다."""
    for activity, roles in policy["activity_required_roles"].items():
        for r in roles:
            assert r in policy["roles"], f"{activity}: 미정의 역할 {r}"


def test_every_actor_role_is_defined(policy):
    for a in policy["actors"]:
        for r in a["roles"]:
            assert r in policy["roles"], f"{a['actor_id']}: 미정의 역할 {r}"


def test_conflict_activities_are_known(policy):
    known = set(policy["activity_required_roles"])
    for c in policy["conflicts"]:
        assert set(c["activities"]) <= known, c["conflict_id"]


def test_developer_and_validator_separation_is_policy(policy):
    """개발↔독립검증 분리는 모형리스크관리의 기본 통제 — 정책에 존재해야 한다."""
    pairs = [set(c["activities"]) for c in policy["conflicts"]]
    assert {"remediation", "reverification"} in pairs


def test_actor_roles_lookup(policy):
    assert actor_roles("DEV-101", policy) == ["model_developer"]
    assert actor_roles("REV-201", policy) == ["independent_validator"]
    assert actor_roles("NO-SUCH", policy) == []


def test_policy_file_is_valid_json():
    json.loads(SOD_POLICY_PATH.read_text(encoding="utf-8"))


# ---------- check_sod ----------

def test_clean_separation_passes():
    r = check_sod({"remediation": "DEV-101", "reverification": "REV-201",
                   "closure_approval": "APR-301"})
    assert r["status"] == STATUS_PASS and r["passed"]
    assert r["violations"] == []


def test_same_actor_remediation_and_reverification_conflicts():
    """SOD-001 — DUAL-901 은 두 역할을 다 갖지만 겸직 수행은 금지."""
    r = check_sod({"remediation": "DUAL-901", "reverification": "DUAL-901",
                   "closure_approval": "APR-301"})
    assert r["status"] == STATUS_FAIL
    kinds = {v["type"] for v in r["violations"]}
    assert "conflict" in kinds
    assert any(v.get("conflict_id") == "SOD-001" for v in r["violations"])


def test_reverifier_cannot_be_approver():
    r = check_sod({"remediation": "DEV-101", "reverification": "REV-201",
                   "closure_approval": "REV-201"})
    assert r["status"] == STATUS_FAIL


def test_role_not_permitted_is_violation():
    r = check_sod({"remediation": "DEV-101", "reverification": "DEV-102",
                   "closure_approval": "APR-301"})
    assert r["status"] == STATUS_FAIL
    assert any(v["type"] == "role_not_permitted" for v in r["violations"])


def test_unregistered_actor_is_violation():
    r = check_sod({"remediation": "GHOST-999", "reverification": "REV-201",
                   "closure_approval": "APR-301"})
    assert any(v["type"] == "unregistered_actor" for v in r["violations"])


def test_unknown_activity_is_violation():
    r = check_sod({"deploy_to_prod": "DEV-101"})
    assert any(v["type"] == "unknown_activity" for v in r["violations"])


def test_missing_actor_is_not_evaluated_not_pass():
    """수행자를 모르면 분리 여부를 알 수 없다 — 통과로 처리하지 않는다."""
    r = check_sod({"remediation": None, "reverification": "REV-201",
                   "closure_approval": "APR-301"})
    assert r["status"] == STATUS_NOT_EVALUATED
    assert not r["passed"]
    assert r["unrecorded_activities"] == ["remediation"]


def test_business_owner_may_remediate():
    r = check_sod({"remediation": "BIZ-151", "reverification": "REV-201",
                   "closure_approval": "APR-301"})
    assert r["status"] == STATUS_PASS


def test_require_sod_raises_on_violation_and_on_unknown():
    with pytest.raises(SoDViolation, match="위반"):
        require_sod({"remediation": "DEV-101", "reverification": "DEV-101",
                     "closure_approval": "APR-301"})
    with pytest.raises(SoDViolation, match="판정 불가"):
        require_sod({"remediation": None, "reverification": "REV-201",
                     "closure_approval": "APR-301"})


# ---------- Finding 종결 연동 ----------

def test_close_records_actors_and_sod_status():
    ev, fid = _lifecycle("DEV-101", "REV-201")
    closed = close_finding(fid, as_of=AS, events=ev, actor="APR-301")
    assert closed["sod_status"] == STATUS_PASS
    ev.append(closed)
    st = derive(ev)[fid]
    assert st["remediation_actor"] == "DEV-101"
    assert st["reverification_actor"] == "REV-201"
    assert st["closure_actor"] == "APR-301"
    assert st["sod_status"] == STATUS_PASS


def test_close_blocked_when_developer_self_reverifies():
    ev, fid = _lifecycle("DEV-101", "DEV-101")
    with pytest.raises(SoDViolation):
        close_finding(fid, as_of=AS, events=ev, actor="APR-301")


def test_close_blocked_when_reverifier_approves():
    ev, fid = _lifecycle("DEV-101", "REV-201")
    with pytest.raises(SoDViolation):
        close_finding(fid, as_of=AS, events=ev, actor="REV-201")


def test_close_without_actors_is_not_evaluated_but_allowed():
    """수행자 미기록 이력(R82 이전 데이터)은 차단하지 않되 판정 불가로 남긴다."""
    ev, fid = _lifecycle(None, None)
    closed = close_finding(fid, as_of=AS, events=ev)
    assert closed["sod_status"] == STATUS_NOT_EVALUATED


def test_enforce_sod_can_be_disabled_explicitly():
    ev, fid = _lifecycle("DEV-101", "DEV-101")
    closed = close_finding(fid, as_of=AS, events=ev, actor="APR-301",
                           enforce_sod=False)
    assert closed["sod_status"] == STATUS_FAIL   # 기록은 남는다


def test_sod_failure_does_not_close_the_finding():
    """차단된 종결은 상태를 바꾸지 않아야 한다."""
    ev, fid = _lifecycle("DEV-101", "DEV-101")
    with pytest.raises(SoDViolation):
        close_finding(fid, as_of=AS, events=ev, actor="APR-301")
    assert derive(ev)[fid]["status"] != "closed"
