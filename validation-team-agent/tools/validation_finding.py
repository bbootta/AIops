"""Finding 원장 — 발견·원인·보완·재검증·종결 계보 (PRD-VAL VAL-013/014).

검증 사례(VAL-003)가 "무엇이 임계를 벗어났는가"를 연다면, Finding 원장은
"그래서 무엇을 고쳤고 정말 해소됐는가"를 끝까지 추적한다.

**append-only 이벤트 로그**로 저장하고 현재 상태는 폴딩으로 유도한다. 상태를
덮어쓰지 않으므로 발견부터 종결까지의 계보가 그대로 남는다 (감사추적).

강제하는 통제:

- **재검증 없이 종결 불가**. 마지막 재검증이 pass 가 아니면 close 가 거부된다.
- **근본원인 없이 종결 불가**. 원인 미상 종결은 재발 관리를 무력화한다.
- **SLA 초과 자동 식별**. 기한을 넘긴 미종결 건을 에스컬레이션 대상으로 표시.
- **재발 시 중대도 상향** (VAL-014). 종결된 Finding 과 동일 (도메인·근본원인·
  대상) 조합이 다시 열리면 재발로 판정하고 한 단계 올린다.
- **미종결 Critical 은 변경 승인을 차단** (VAL-016). ``approval_blockers`` 가
  차단 사유를 반환하며 tools.manifest promote 가 이를 조회한다.

CLAUDE.md §7: Finding 종결·의견 확정은 인간 검증자의 판단이며, 본 모듈은
기록·게이트만 제공한다.

사용:
    python -m tools.validation_finding open --title "PSI 임계 초과" \\
        --domain credit --severity medium --owner credit_model_owner
    python -m tools.validation_finding remediate --id VF-20260725-0001 \\
        --action "재캘리브레이션 수행" --root-cause model
    python -m tools.validation_finding reverify --id VF-20260725-0001 --result pass
    python -m tools.validation_finding close --id VF-20260725-0001
    python -m tools.validation_finding queue
    python -m tools.validation_finding blockers
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
FINDINGS_PATH = ROOT / "logs" / "validation_findings.jsonl"

#: 근본원인 분류 — VAL-008(차이 원인 분해)과 동일 축을 사용한다.
ROOT_CAUSES = ("data", "model", "formula", "implementation", "process")

#: 중대도 — validation_triggers.json 의 sla_days_by_severity 와 같은 축.
SEVERITY_ORDER = ("medium", "high", "critical")

#: 상태 전이. 종결 이후에는 상태가 바뀌지 않는다 (재발은 새 Finding 으로 연다).
_TRANSITIONS = {
    "open": {"remediating"},
    "remediating": {"reverifying"},
    "reverifying": {"closed", "remediating"},   # 재검증 실패 시 보완으로 되돌림
    "closed": set(),
}

EVENT_TYPES = ("opened", "remediation_recorded", "reverified", "closed",
               "severity_raised")


class FindingError(RuntimeError):
    """Finding 원장 규칙 위반."""


def _sla_days() -> dict[str, int]:
    from tools.validation_trigger import load_triggers

    return dict(load_triggers()["sla_days_by_severity"])


# ------------------------------------------------------------------ 저장소
def load_events(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path or FINDINGS_PATH)
    if not p.exists():
        return []
    return [json.loads(line)
            for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def append_events(events: Iterable[Mapping[str, Any]],
                  path: str | Path | None = None) -> Path:
    p = Path(path or FINDINGS_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return p


# --------------------------------------------------------------- 상태 유도
def derive(events: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """이벤트를 폴딩해 Finding 별 현재 상태와 계보를 만든다."""
    state: dict[str, dict[str, Any]] = {}
    for e in events:
        fid = e["finding_id"]
        if e["event"] == "opened":
            state[fid] = {
                "finding_id": fid,
                "title": e["title"],
                "domain": e["domain"],
                "severity": e["severity"],
                "owner_role": e["owner_role"],
                "case_id": e.get("case_id"),
                "target": e.get("target"),
                "root_cause": e.get("root_cause"),
                "opened_at": e["at"],
                "due_at": e["due_at"],
                "status": "open",
                "recurrence_of": e.get("recurrence_of"),
                "history": [e],
            }
            continue
        cur = state.get(fid)
        if cur is None:
            raise FindingError(f"{fid}: opened 이벤트 없이 {e['event']} 발생")
        cur["history"].append(e)
        if e["event"] == "remediation_recorded":
            cur["status"] = "remediating"
            cur["remediation"] = e["action"]
            if e.get("root_cause"):
                cur["root_cause"] = e["root_cause"]
        elif e["event"] == "reverified":
            # 재검증 실패는 보완 단계로 되돌린다 — 실패를 통과처럼 두지 않는다.
            cur["status"] = ("reverifying" if e["result"] == "pass"
                             else "remediating")
            cur["last_reverification"] = e["result"]
        elif e["event"] == "closed":
            cur["status"] = "closed"
            cur["closed_at"] = e["at"]
        elif e["event"] == "severity_raised":
            cur["severity"] = e["to"]
            cur["due_at"] = e["due_at"]
    return state


def _next_id(events: list[dict[str, Any]], day: str) -> str:
    n = 1 + sum(1 for e in events
                if e["event"] == "opened"
                and e["finding_id"].startswith(f"VF-{day}-"))
    return f"VF-{day}-{n:04d}"


# ------------------------------------------------------------------- 연산
def detect_recurrence(domain: str, root_cause: str | None, target: str | None,
                      states: Mapping[str, Mapping[str, Any]],
                      ) -> str | None:
    """종결된 Finding 중 동일 (도메인·근본원인·대상) 건이 있으면 그 ID 반환."""
    if not root_cause:
        return None
    for fid, s in states.items():
        if (s["status"] == "closed" and s["domain"] == domain
                and s.get("root_cause") == root_cause
                and s.get("target") == target):
            return fid
    return None


def _raise_severity(sev: str) -> str:
    i = SEVERITY_ORDER.index(sev)
    return SEVERITY_ORDER[min(i + 1, len(SEVERITY_ORDER) - 1)]


def open_finding(*, title: str, domain: str, severity: str, owner_role: str,
                 as_of: date, events: list[dict[str, Any]] | None = None,
                 case_id: str | None = None, target: str | None = None,
                 root_cause: str | None = None,
                 sla_days: Mapping[str, int] | None = None,
                 ) -> list[dict[str, Any]]:
    """Finding 을 연다. 재발이면 중대도를 한 단계 올린다 (VAL-014)."""
    if severity not in SEVERITY_ORDER:
        raise FindingError(f"알 수 없는 중대도: {severity}")
    if root_cause is not None and root_cause not in ROOT_CAUSES:
        raise FindingError(f"알 수 없는 근본원인: {root_cause}")
    events = list(events or [])
    states = derive(events)
    days = dict(sla_days or _sla_days())

    prior = detect_recurrence(domain, root_cause, target, states)
    effective = _raise_severity(severity) if prior else severity
    day = as_of.strftime("%Y%m%d")
    fid = _next_id(events, day)
    due = (as_of + timedelta(days=int(days.get(effective, 20)))).isoformat()

    opened = {
        "event": "opened", "finding_id": fid, "at": as_of.isoformat(),
        "title": title, "domain": domain, "severity": effective,
        "owner_role": owner_role, "case_id": case_id, "target": target,
        "root_cause": root_cause, "due_at": due,
        "recurrence_of": prior,
    }
    out = [opened]
    if prior:
        out.append({
            "event": "severity_raised", "finding_id": fid,
            "at": as_of.isoformat(), "from": severity, "to": effective,
            "reason": f"{prior} 와 동일 근본원인 재발 (domain={domain}, "
                      f"root_cause={root_cause}, target={target})",
            "due_at": due,
        })
    return out


def record_remediation(finding_id: str, *, action: str, root_cause: str,
                       as_of: date, events: list[dict[str, Any]],
                       ) -> dict[str, Any]:
    if root_cause not in ROOT_CAUSES:
        raise FindingError(f"알 수 없는 근본원인: {root_cause}")
    _require_transition(finding_id, "remediating", events)
    return {"event": "remediation_recorded", "finding_id": finding_id,
            "at": as_of.isoformat(), "action": action,
            "root_cause": root_cause}


def record_reverification(finding_id: str, *, result: str, evidence: str,
                          as_of: date, events: list[dict[str, Any]],
                          ) -> dict[str, Any]:
    if result not in ("pass", "fail"):
        raise FindingError("result 는 pass 또는 fail")
    _require_transition(finding_id, "reverifying", events)
    return {"event": "reverified", "finding_id": finding_id,
            "at": as_of.isoformat(), "result": result, "evidence": evidence}


def close_finding(finding_id: str, *, as_of: date,
                  events: list[dict[str, Any]]) -> dict[str, Any]:
    """재검증 pass 와 근본원인이 있어야만 종결할 수 있다."""
    states = derive(events)
    cur = states.get(finding_id)
    if cur is None:
        raise FindingError(f"{finding_id}: 존재하지 않는 Finding")
    if cur["status"] == "closed":
        raise FindingError(f"{finding_id}: 이미 종결됨")
    if cur.get("last_reverification") != "pass":
        raise FindingError(
            f"{finding_id}: 재검증 통과 기록 없이 종결할 수 없다 "
            f"(현재 상태={cur['status']}, "
            f"재검증={cur.get('last_reverification', '없음')})")
    if not cur.get("root_cause"):
        raise FindingError(
            f"{finding_id}: 근본원인 없이 종결할 수 없다 (재발 관리 불가)")
    return {"event": "closed", "finding_id": finding_id,
            "at": as_of.isoformat()}


def _require_transition(finding_id: str, to: str,
                        events: list[dict[str, Any]]) -> None:
    states = derive(events)
    cur = states.get(finding_id)
    if cur is None:
        raise FindingError(f"{finding_id}: 존재하지 않는 Finding")
    allowed = _TRANSITIONS[cur["status"]]
    if to not in allowed:
        raise FindingError(
            f"{finding_id}: {cur['status']} → {to} 전이 불가 "
            f"(허용: {sorted(allowed) or '없음'})")


# --------------------------------------------------------------- 조회·게이트
def queue(states: Mapping[str, Mapping[str, Any]] | None = None, *,
          as_of: date | None = None, severity: str | None = None,
          owner_role: str | None = None) -> list[dict[str, Any]]:
    """미종결 Finding — 기한순. SLA 초과 표시."""
    st = states if states is not None else derive(load_events())
    today = as_of or date.today()
    rows = []
    for s in st.values():
        if s["status"] == "closed":
            continue
        if severity and s["severity"] != severity:
            continue
        if owner_role and s["owner_role"] != owner_role:
            continue
        rows.append({**s, "overdue": date.fromisoformat(s["due_at"]) < today})
    return sorted(rows, key=lambda r: (r["due_at"], r["finding_id"]))


def approval_blockers(states: Mapping[str, Mapping[str, Any]] | None = None,
                      ) -> list[dict[str, Any]]:
    """변경 승인을 차단하는 미종결 Critical Finding (VAL-016)."""
    st = states if states is not None else derive(load_events())
    return sorted(
        ({"finding_id": s["finding_id"], "title": s["title"],
          "severity": s["severity"], "status": s["status"],
          "due_at": s["due_at"], "owner_role": s["owner_role"]}
         for s in st.values()
         if s["status"] != "closed" and s["severity"] == "critical"),
        key=lambda r: r["finding_id"])


def render_queue(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "미종결 Finding 없음."
    lines = [f"Finding 검토 큐 — {len(rows)}건", ""]
    for r in rows:
        flag = " [SLA 초과]" if r.get("overdue") else ""
        rec = f" · 재발({r['recurrence_of']})" if r.get("recurrence_of") else ""
        lines.append(f"{r['finding_id']} · {r['severity']} · {r['status']} · "
                     f"{r['owner_role']} · 기한 {r['due_at']}{flag}{rec}")
        lines.append(f"      {r['title']} "
                     f"(근본원인 {r.get('root_cause') or '미상'})")
    return "\n".join(lines)


def render_lineage(state: Mapping[str, Any]) -> str:
    """발견–원인–보완–재검증–종결 계보 (VAL-013 산출물)."""
    lines = [f"{state['finding_id']} {state['title']} "
             f"[{state['status']}] {state['severity']}"]
    for e in state["history"]:
        extra = ""
        if e["event"] == "remediation_recorded":
            extra = f" — {e['action']} (근본원인 {e['root_cause']})"
        elif e["event"] == "reverified":
            extra = f" — {e['result']} ({e['evidence']})"
        elif e["event"] == "severity_raised":
            extra = f" — {e['from']}→{e['to']}: {e['reason']}"
        lines.append(f"  {e['at']} {e['event']}{extra}")
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI
def _as_of(args: argparse.Namespace) -> date:
    return date.fromisoformat(args.as_of) if args.as_of else date.today()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Finding 원장 — 발견·원인·보완·재검증·종결 계보")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open", help="Finding 개시")
    p_open.add_argument("--title", required=True)
    p_open.add_argument("--domain", required=True)
    p_open.add_argument("--severity", required=True, choices=SEVERITY_ORDER)
    p_open.add_argument("--owner", required=True)
    p_open.add_argument("--case-id", default=None)
    p_open.add_argument("--target", default=None)
    p_open.add_argument("--root-cause", default=None, choices=ROOT_CAUSES)
    p_open.add_argument("--as-of", default=None)

    p_rem = sub.add_parser("remediate", help="보완조치 기록")
    p_rem.add_argument("--id", required=True)
    p_rem.add_argument("--action", required=True)
    p_rem.add_argument("--root-cause", required=True, choices=ROOT_CAUSES)
    p_rem.add_argument("--as-of", default=None)

    p_rev = sub.add_parser("reverify", help="재검증 결과 기록")
    p_rev.add_argument("--id", required=True)
    p_rev.add_argument("--result", required=True, choices=["pass", "fail"])
    p_rev.add_argument("--evidence", default="")
    p_rev.add_argument("--as-of", default=None)

    p_cls = sub.add_parser("close", help="종결 (재검증 pass 필요)")
    p_cls.add_argument("--id", required=True)
    p_cls.add_argument("--as-of", default=None)

    p_q = sub.add_parser("queue", help="미종결 Finding 큐")
    p_q.add_argument("--severity", default=None, choices=SEVERITY_ORDER)
    p_q.add_argument("--owner", default=None)

    p_lin = sub.add_parser("lineage", help="Finding 계보 출력")
    p_lin.add_argument("--id", required=True)

    sub.add_parser("blockers", help="승인 차단 Critical Finding")

    args = parser.parse_args(argv)
    events = load_events()

    try:
        if args.cmd == "open":
            new = open_finding(
                title=args.title, domain=args.domain, severity=args.severity,
                owner_role=args.owner, as_of=_as_of(args), events=events,
                case_id=args.case_id, target=args.target,
                root_cause=args.root_cause)
            append_events(new)
            fid = new[0]["finding_id"]
            sys.stdout.write(f"{fid} 개시 (중대도 {new[0]['severity']}, "
                             f"기한 {new[0]['due_at']})\n")
            if new[0]["recurrence_of"]:
                sys.stdout.write(
                    f"재발 판정: {new[0]['recurrence_of']} 와 동일 근본원인 "
                    "→ 중대도 상향\n")
            return 0

        if args.cmd == "remediate":
            append_events([record_remediation(
                args.id, action=args.action, root_cause=args.root_cause,
                as_of=_as_of(args), events=events)])
        elif args.cmd == "reverify":
            append_events([record_reverification(
                args.id, result=args.result, evidence=args.evidence,
                as_of=_as_of(args), events=events)])
        elif args.cmd == "close":
            append_events([close_finding(
                args.id, as_of=_as_of(args), events=events)])
            sys.stdout.write(f"{args.id} 종결 — 종결 판단의 책임은 "
                             "인간 검증자에게 있습니다 (HITL).\n")
            return 0
        elif args.cmd == "queue":
            sys.stdout.write(render_queue(queue(
                severity=args.severity, owner_role=args.owner)) + "\n")
            return 0
        elif args.cmd == "lineage":
            st = derive(events).get(args.id)
            if st is None:
                sys.stderr.write(f"없는 Finding: {args.id}\n")
                return 1
            sys.stdout.write(render_lineage(st) + "\n")
            return 0
        elif args.cmd == "blockers":
            rows = approval_blockers()
            if not rows:
                sys.stdout.write("승인 차단 Finding 없음.\n")
                return 0
            sys.stdout.write(f"승인 차단 Critical Finding {len(rows)}건\n")
            for r in rows:
                sys.stdout.write(
                    f"  {r['finding_id']} {r['title']} "
                    f"({r['status']}, 기한 {r['due_at']}, {r['owner_role']})\n")
            return 1
    except FindingError as exc:
        sys.stderr.write(f"거부: {exc}\n")
        return 1

    sys.stdout.write(f"{args.id} 기록 완료\n")
    return 0


__all__ = [
    "FindingError", "ROOT_CAUSES", "SEVERITY_ORDER", "FINDINGS_PATH",
    "load_events", "append_events", "derive", "open_finding",
    "record_remediation", "record_reverification", "close_finding",
    "detect_recurrence", "queue", "approval_blockers", "render_queue",
    "render_lineage",
]


if __name__ == "__main__":
    raise SystemExit(main())
