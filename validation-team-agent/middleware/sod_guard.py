"""직무분리(SoD) 통제 — 검증 활동의 역할 적격성과 겸직 금지 (PRD-VAL VAL-006).

두 가지를 판정한다.

1. **역할 적격성**: 활동을 수행한 actor 가 그 활동에 허용된 역할을 보유하는가.
   미등록 actor 나 역할 미보유자의 수행은 위반이다.
2. **겸직 금지**: 정책이 분리하도록 정한 활동 쌍을 동일인이 수행했는가.
   (예: 보완을 수행한 사람이 그 보완을 스스로 재검증)

``permission_matrix`` 가 "이 명령을 실행해도 되는가"(시스템 접근)를 본다면,
본 가드는 "이 검증 활동을 이 사람이 수행해도 되는가"(직무 분리)를 본다.
두 통제는 축이 다르므로 분리한다.

판정 결과는 ``passed`` 와 ``violations`` 로 반환하며, 평가에 필요한 actor 가
기록되지 않은 경우 조용히 통과시키지 않고 ``not_evaluated`` 로 남긴다 —
직무분리는 수행자를 모르면 판정할 수 없고, 모른다는 것은 통과가 아니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
SOD_POLICY_PATH = ROOT / "harness" / "sod_policy.json"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NOT_EVALUATED = "NOT_EVALUATED"


class SoDViolation(RuntimeError):
    """직무분리 위반."""


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or SOD_POLICY_PATH).read_text(encoding="utf-8"))


def actor_roles(actor_id: str,
                policy: Mapping[str, Any] | None = None) -> list[str]:
    """actor 의 역할 목록. 미등록이면 빈 리스트."""
    pol = policy if policy is not None else load_policy()
    for a in pol["actors"]:
        if a["actor_id"] == actor_id:
            return list(a["roles"])
    return []


def check_sod(activity_actors: Mapping[str, str | None], *,
              policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """활동→수행자 매핑을 받아 SoD 를 판정한다.

    Args:
        activity_actors: 예 ``{"remediation": "DEV-101",
            "reverification": "REV-201", "closure_approval": "APR-301"}``.
            값이 None 이면 해당 활동은 미기록으로 본다.

    Returns:
        ``{"status", "passed", "violations", "evaluated_activities",
        "unrecorded_activities"}``
    """
    pol = policy if policy is not None else load_policy()
    required = pol["activity_required_roles"]
    violations: list[dict[str, str]] = []

    recorded = {act: who for act, who in activity_actors.items() if who}
    unrecorded = sorted(act for act, who in activity_actors.items() if not who)

    # 1) 역할 적격성
    for activity, who in sorted(recorded.items()):
        allowed = required.get(activity)
        if allowed is None:
            violations.append({
                "type": "unknown_activity", "activity": activity,
                "actor_id": who,
                "detail": f"정책에 정의되지 않은 활동: {activity}"})
            continue
        roles = actor_roles(who, pol)
        if not roles:
            violations.append({
                "type": "unregistered_actor", "activity": activity,
                "actor_id": who,
                "detail": f"{who} 는 SoD 정책에 등록되지 않은 수행자"})
        elif not set(roles) & set(allowed):
            violations.append({
                "type": "role_not_permitted", "activity": activity,
                "actor_id": who,
                "detail": f"{who}(역할 {roles}) 는 {activity} 수행 역할"
                          f" {allowed} 가 아니다"})

    # 2) 겸직 금지
    for conflict in pol["conflicts"]:
        a, b = conflict["activities"]
        if a in recorded and b in recorded and recorded[a] == recorded[b]:
            violations.append({
                "type": "conflict", "conflict_id": conflict["conflict_id"],
                "activity": f"{a}+{b}", "actor_id": recorded[a],
                "detail": f"{conflict['conflict_id']}: 동일인({recorded[a]})이 "
                          f"{a} 와 {b} 를 함께 수행 — {conflict['rationale']}"})

    if violations:
        status = STATUS_FAIL
    elif unrecorded:
        status = STATUS_NOT_EVALUATED
    else:
        status = STATUS_PASS
    return {
        "status": status,
        "passed": status == STATUS_PASS,
        "violations": violations,
        "evaluated_activities": sorted(recorded),
        "unrecorded_activities": unrecorded,
    }


def require_sod(activity_actors: Mapping[str, str | None], *,
                policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """SoD 를 강제한다. 위반이거나 판정 불가면 SoDViolation."""
    result = check_sod(activity_actors, policy=policy)
    if result["status"] == STATUS_FAIL:
        detail = " / ".join(v["detail"] for v in result["violations"])
        raise SoDViolation(f"직무분리 위반: {detail}")
    if result["status"] == STATUS_NOT_EVALUATED:
        raise SoDViolation(
            "직무분리 판정 불가 — 수행자 미기록: "
            f"{result['unrecorded_activities']}. 수행자를 모르면 분리 여부를 "
            "판단할 수 없으므로 통과로 처리하지 않는다.")
    return result


__all__ = [
    "SoDViolation", "SOD_POLICY_PATH", "STATUS_PASS", "STATUS_FAIL",
    "STATUS_NOT_EVALUATED", "load_policy", "actor_roles", "check_sod",
    "require_sod",
]
