"""조건부 승인·제한 배포 (PRD-VAL VAL-017).

미종결 위험이 남았지만 업무상 배포가 불가피할 때, 무조건 승인과 무조건 차단
사이의 **기록된 중간 경로**를 제공한다. VAL-016 의 차단을 우회하는 유일한
정규 경로이며, 우회의 대가로 다음을 반드시 남긴다.

- **잔여위험**: 무엇을 감수하는가
- **후속조건**: 무엇을 언제까지 이행하는가 (담당·기한 필수)
- **강화 모니터링**: 그동안 무엇을 더 본다
- **제한 배포 범위**: 어디까지만 쓰는가
- **승인자**: 누가 책임지는가 (SoD 상 approver 역할만)

조건 기한이 지나면 자동으로 에스컬레이션 대상이 되고, 선언한 범위를 벗어난
사용은 차단된다. 조건 없는 조건부 승인은 성립하지 않는다 — 그것은 그냥
승인이며, 이 모듈이 거부한다.

CLAUDE.md §7: 조건부 승인 여부와 잔여위험 수용은 인간 검증 책임자의 판단이다.
본 모듈은 그 판단을 기록·강제할 뿐 대신 내리지 않는다.

사용:
    python -m tools.conditional_approval grant --change-id CHG-0150 \\
        --approver APR-301 --residual-risk "LCR 재계산 차이 미해소" \\
        --condition "원천 대사 완료|alm_owner|2026-08-15" \\
        --scope "리테일 포트폴리오 한정"
    python -m tools.conditional_approval status
    python -m tools.conditional_approval check-scope --change-id CHG-0150 \\
        --usage "기업 포트폴리오"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
APPROVALS_PATH = ROOT / "logs" / "conditional_approvals.jsonl"


class ApprovalError(RuntimeError):
    """조건부 승인 규칙 위반."""


def load_approvals(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path or APPROVALS_PATH)
    if not p.exists():
        return []
    return [json.loads(line)
            for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def append_approvals(rows: Iterable[Mapping[str, Any]],
                     path: str | Path | None = None) -> Path:
    p = Path(path or APPROVALS_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def parse_condition(raw: str) -> dict[str, str]:
    """``설명|담당역할|기한`` 형식을 조건 dict 로."""
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) != 3 or not all(parts):
        raise ApprovalError(
            f"조건 형식 오류: {raw!r} — '설명|담당역할|YYYY-MM-DD' 필요")
    try:
        date.fromisoformat(parts[2])
    except ValueError as exc:
        raise ApprovalError(f"조건 기한 형식 오류: {parts[2]}") from exc
    return {"description": parts[0], "owner_role": parts[1],
            "due_at": parts[2], "status": "open"}


def grant(*, change_id: str, approver: str, residual_risk: str,
          conditions: list[Mapping[str, Any]], as_of: date,
          deployment_scope: str, enhanced_monitoring: list[str] | None = None,
          enforce_sod: bool = True,
          existing: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """조건부 승인을 기록한다. 조건이 없으면 성립하지 않는다."""
    if not conditions:
        raise ApprovalError(
            "후속조건 없는 조건부 승인은 성립하지 않는다 — 조건이 없다면 "
            "그것은 무조건 승인이며 별도 절차를 따라야 한다")
    if not residual_risk.strip():
        raise ApprovalError("잔여위험을 명시하지 않은 조건부 승인은 불가")
    if not deployment_scope.strip():
        raise ApprovalError("제한 배포 범위를 명시하지 않은 조건부 승인은 불가")

    for c in conditions:
        for field in ("description", "owner_role", "due_at"):
            if not str(c.get(field, "")).strip():
                raise ApprovalError(f"조건 필수 항목 누락: {field} ({c})")

    if enforce_sod:
        from middleware.sod_guard import actor_roles

        roles = actor_roles(approver)
        if "approver" not in roles:
            raise ApprovalError(
                f"{approver} 는 승인 권한이 없다 (역할 {roles or '미등록'}) — "
                "조건부 승인은 approver 역할만 가능하다")

    if any(r["change_id"] == change_id
           for r in (existing or []) if r.get("event") == "granted"):
        raise ApprovalError(f"{change_id}: 이미 조건부 승인이 존재한다")

    return {
        "event": "granted",
        "change_id": change_id,
        "granted_at": as_of.isoformat(),
        "approver": approver,
        "residual_risk": residual_risk,
        "deployment_scope": deployment_scope,
        "enhanced_monitoring": list(enhanced_monitoring or []),
        "conditions": [dict(c) for c in conditions],
        "hitl_note": "잔여위험 수용과 조건 이행 확인은 인간 검증 책임자의 판단이다.",
    }


def fulfil(change_id: str, *, condition_index: int, evidence: str,
           as_of: date, approvals: list[dict[str, Any]]) -> dict[str, Any]:
    """조건 이행을 기록한다."""
    state = derive(approvals).get(change_id)
    if state is None:
        raise ApprovalError(f"{change_id}: 조건부 승인이 없다")
    if not 0 <= condition_index < len(state["conditions"]):
        raise ApprovalError(
            f"{change_id}: 조건 번호 범위 밖 ({condition_index})")
    if state["conditions"][condition_index]["status"] == "fulfilled":
        raise ApprovalError(f"{change_id}: 조건 {condition_index} 는 이미 이행됨")
    if not evidence.strip():
        raise ApprovalError("이행 증빙 없이 조건을 종결할 수 없다")
    return {"event": "condition_fulfilled", "change_id": change_id,
            "condition_index": condition_index, "at": as_of.isoformat(),
            "evidence": evidence}


def derive(approvals: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """이벤트를 폴딩해 승인별 조건 이행 상태를 만든다."""
    state: dict[str, dict[str, Any]] = {}
    for row in approvals:
        cid = row["change_id"]
        if row["event"] == "granted":
            state[cid] = {**{k: v for k, v in row.items() if k != "event"},
                          "conditions": [dict(c) for c in row["conditions"]],
                          "history": [row]}
            continue
        cur = state.get(cid)
        if cur is None:
            raise ApprovalError(f"{cid}: granted 없이 {row['event']} 발생")
        cur["history"].append(row)
        if row["event"] == "condition_fulfilled":
            c = cur["conditions"][row["condition_index"]]
            c["status"] = "fulfilled"
            c["fulfilled_at"] = row["at"]
            c["evidence"] = row["evidence"]
    return state


def compliance(states: Mapping[str, Mapping[str, Any]] | None = None, *,
               as_of: date | None = None) -> list[dict[str, Any]]:
    """승인별 조건 이행 현황. 기한 초과 미이행은 에스컬레이션 대상."""
    st = states if states is not None else derive(load_approvals())
    today = as_of or date.today()
    rows = []
    for cid, s in sorted(st.items()):
        overdue = [c for c in s["conditions"]
                   if c["status"] != "fulfilled"
                   and date.fromisoformat(c["due_at"]) < today]
        open_conditions = [c for c in s["conditions"]
                           if c["status"] != "fulfilled"]
        rows.append({
            "change_id": cid,
            "approver": s["approver"],
            "residual_risk": s["residual_risk"],
            "deployment_scope": s["deployment_scope"],
            "n_conditions": len(s["conditions"]),
            "n_open": len(open_conditions),
            "overdue": overdue,
            "escalate": bool(overdue),
            "fully_fulfilled": not open_conditions,
        })
    return rows


def escalations(states: Mapping[str, Mapping[str, Any]] | None = None, *,
                as_of: date | None = None) -> list[dict[str, Any]]:
    return [r for r in compliance(states, as_of=as_of) if r["escalate"]]


def check_scope(change_id: str, usage: str, *,
                states: Mapping[str, Mapping[str, Any]] | None = None,
                ) -> dict[str, Any]:
    """선언한 제한 배포 범위 안의 사용인지 확인한다.

    범위는 자연어 선언이므로 자동 판정은 **부분 문자열 포함**이라는 보수적
    규칙만 적용한다. 일치하지 않으면 통과시키지 않고 사람 확인으로 보낸다 —
    자동으로 허용하는 것보다 막고 확인받는 편이 안전하다.
    """
    st = states if states is not None else derive(load_approvals())
    s = st.get(change_id)
    if s is None:
        return {"change_id": change_id, "allowed": False,
                "reason": "조건부 승인이 없다 — 제한 배포 근거 없음"}
    scope = s["deployment_scope"]
    if usage.strip() and usage.strip() in scope:
        return {"change_id": change_id, "allowed": True,
                "scope": scope, "usage": usage,
                "reason": "선언된 범위 내 사용"}
    return {"change_id": change_id, "allowed": False,
            "scope": scope, "usage": usage,
            "reason": f"선언 범위 '{scope}' 와 일치하지 않는 사용 '{usage}' — "
                      "범위 확대는 승인 재요청이 필요하다"}


def render_compliance(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "조건부 승인 없음."
    lines = [f"조건부 승인 현황 — {len(rows)}건", ""]
    for r in rows:
        flag = " [에스컬레이션]" if r["escalate"] else ""
        done = " (조건 전부 이행)" if r["fully_fulfilled"] else ""
        lines.append(f"{r['change_id']} · 승인 {r['approver']} · "
                     f"조건 {r['n_conditions'] - r['n_open']}/"
                     f"{r['n_conditions']} 이행{done}{flag}")
        lines.append(f"      잔여위험: {r['residual_risk']}")
        lines.append(f"      배포범위: {r['deployment_scope']}")
        for c in r["overdue"]:
            lines.append(f"      [기한초과] {c['description']} "
                         f"({c['owner_role']}, 기한 {c['due_at']})")
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="조건부 승인·제한 배포 (VAL-017)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_g = sub.add_parser("grant", help="조건부 승인 기록")
    p_g.add_argument("--change-id", required=True)
    p_g.add_argument("--approver", required=True)
    p_g.add_argument("--residual-risk", required=True)
    p_g.add_argument("--scope", required=True, help="제한 배포 범위")
    p_g.add_argument("--condition", action="append", default=[],
                     help="'설명|담당역할|YYYY-MM-DD' (반복 지정)")
    p_g.add_argument("--monitoring", action="append", default=[])
    p_g.add_argument("--as-of", default=None)

    p_f = sub.add_parser("fulfil", help="조건 이행 기록")
    p_f.add_argument("--change-id", required=True)
    p_f.add_argument("--index", type=int, required=True)
    p_f.add_argument("--evidence", required=True)
    p_f.add_argument("--as-of", default=None)

    p_s = sub.add_parser("status", help="조건 이행 현황 (기한초과 시 exit 1)")
    p_s.add_argument("--as-of", default=None)

    p_c = sub.add_parser("check-scope", help="제한 배포 범위 확인")
    p_c.add_argument("--change-id", required=True)
    p_c.add_argument("--usage", required=True)

    args = parser.parse_args(argv)
    as_of = (date.fromisoformat(args.as_of)
             if getattr(args, "as_of", None) else date.today())
    rows = load_approvals()

    try:
        if args.cmd == "grant":
            conditions = [parse_condition(c) for c in args.condition]
            row = grant(change_id=args.change_id, approver=args.approver,
                        residual_risk=args.residual_risk,
                        conditions=conditions, as_of=as_of,
                        deployment_scope=args.scope,
                        enhanced_monitoring=args.monitoring, existing=rows)
            append_approvals([row])
            sys.stdout.write(
                f"{args.change_id} 조건부 승인 기록 — 조건 {len(conditions)}건, "
                f"범위 '{args.scope}'\n"
                "잔여위험 수용 책임은 승인자에게 있습니다 (HITL).\n")
            return 0

        if args.cmd == "fulfil":
            append_approvals([fulfil(args.change_id,
                                     condition_index=args.index,
                                     evidence=args.evidence, as_of=as_of,
                                     approvals=rows)])
            sys.stdout.write(f"{args.change_id} 조건 {args.index} 이행 기록\n")
            return 0

        if args.cmd == "check-scope":
            res = check_scope(args.change_id, args.usage)
            sys.stdout.write(f"{res['reason']}\n")
            return 0 if res["allowed"] else 1

        report = compliance(as_of=as_of)
        sys.stdout.write(render_compliance(report) + "\n")
        return 1 if any(r["escalate"] for r in report) else 0
    except ApprovalError as exc:
        sys.stderr.write(f"거부: {exc}\n")
        return 2


__all__ = ["ApprovalError", "APPROVALS_PATH", "load_approvals",
           "append_approvals", "parse_condition", "grant", "fulfil", "derive",
           "compliance", "escalations", "check_scope", "render_compliance"]


if __name__ == "__main__":
    raise SystemExit(main())
