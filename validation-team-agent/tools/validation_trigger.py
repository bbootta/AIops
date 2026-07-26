"""상시 모니터링 트리거 평가와 검증 사례 생성 (PRD-VAL VAL-001/002/003).

세 가지를 한 흐름으로 잇는다.

1. **트리거 원장** (`harness/validation_triggers.json`) — 지표·임계치·평가주기·
   소유자·중대도. 임계치는 기존 정책 SSoT 를 인용하며 임의로 만들지 않는다.
2. **4요소 평가** — 각 지표를 ``Observed / Expected / Variance / Tolerance`` 로
   평가한다 (variance = observed − expected, 수식랩 VAL-F001 과 동일 정의).
3. **검증 사례 생성** — 위반은 중대도별 SLA 기한과 담당 역할을 가진 사례가 되어
   append-only 원장(``logs/validation_cases.jsonl``)에 적재된다.

설계 원칙:

- 평가는 **판정을 다시 만들지 않는다**. 부문 handler 가 산출한 값을 읽어
  정책 임계와 대조할 뿐이다.
- 지표가 없으면 조용히 통과시키지 않고 ``not_evaluated`` 로 남긴다 — 미산출과
  통과는 다르다.
- 사례 원장은 append-only 다. 상태 전이·종결은 후속 Finding 원장(VAL-013)의
  책임이며 본 모듈은 사례를 열기만 한다.
- ``as_of`` 를 주입할 수 있어 동일 입력이면 동일 사례 ID·기한이 나온다 (재현성).

사용:
    python -m tools.validation_trigger triggers
    python -m tools.validation_trigger evaluate --n 100000 --seed 42
    python -m tools.validation_trigger evaluate --n 100000 --stress --emit
    python -m tools.validation_trigger queue --severity critical
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
TRIGGERS_PATH = ROOT / "harness" / "validation_triggers.json"
CASES_PATH = ROOT / "logs" / "validation_cases.jsonl"

#: 평가 결과 상태. not_evaluated 는 통과가 아니다.
STATUS_OK = "ok"
STATUS_BREACH = "breach"
STATUS_NOT_EVALUATED = "not_evaluated"


def load_triggers(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or TRIGGERS_PATH).read_text(encoding="utf-8"))


def _dig(outputs: Mapping[str, Any], dotted: str) -> Any:
    """'lcr.ratio' 처럼 점 경로로 중첩 dict 를 읽는다. 없으면 None."""
    cur: Any = outputs
    for part in dotted.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return None
        cur = cur[part]
    return cur


def evaluate_trigger(trigger: Mapping[str, Any],
                     demo: Mapping[str, Any]) -> dict[str, Any]:
    """단일 트리거를 4요소로 평가한다."""
    step = demo.get("results", {}).get(trigger["step_id"], {})
    observed = _dig(step.get("outputs", {}) or {}, trigger["output_path"])
    base = {
        "trigger_id": trigger["trigger_id"],
        "domain": trigger["domain"],
        "step_id": trigger["step_id"],
        "metric": trigger["metric"],
        "expected": float(trigger["expected"]),
        "tolerance": float(trigger["tolerance"]),
        "direction": trigger["direction"],
        "severity": trigger["severity"],
        "owner_role": trigger["owner_role"],
        "evaluation_cycle": trigger["evaluation_cycle"],
        "threshold_ref": trigger["threshold_ref"],
    }
    if not isinstance(observed, (int, float)) or isinstance(observed, bool):
        return {**base, "observed": None, "variance": None,
                "status": STATUS_NOT_EVALUATED,
                "detail": f"지표 미산출 — {trigger['step_id']}"
                          f".{trigger['output_path']} 없음 (step status="
                          f"{step.get('status', 'absent')})"}

    observed = float(observed)
    variance = observed - base["expected"]
    tol = base["tolerance"]
    # 부동소수점 표현오차로 경계값이 위반으로 뒤집히지 않게 한다 (R84).
    # 임계 자체는 완화하지 않는다 — 동등성만 보정한다.
    from tools.independent_recalc import within_tolerance

    at_boundary = within_tolerance(variance, tol)
    if trigger["direction"] == "lower":
        breach = (variance < -tol) and not at_boundary
    else:
        breach = (variance > tol) and not at_boundary
    return {**base, "observed": observed, "variance": variance,
            "status": STATUS_BREACH if breach else STATUS_OK,
            "detail": f"observed={observed:.4f} vs expected={base['expected']:.4f}"
                      f" (variance={variance:+.4f}, tolerance={tol:.4f})"}


def evaluate(demo: Mapping[str, Any], *,
             triggers: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """전체 트리거를 평가하고 위반 목록을 함께 반환한다."""
    data = triggers if triggers is not None else load_triggers()
    results = [evaluate_trigger(t, demo) for t in data["triggers"]]
    return {
        "results": results,
        "breaches": [r for r in results if r["status"] == STATUS_BREACH],
        "not_evaluated": [r for r in results
                          if r["status"] == STATUS_NOT_EVALUATED],
        "n_total": len(results),
    }


# ------------------------------------------------------------------ 검증 사례
def _next_seq(existing: list[dict[str, Any]], day: str) -> int:
    return 1 + sum(1 for c in existing if c["case_id"].startswith(f"VC-{day}-"))


def load_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path or CASES_PATH)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def build_cases(breaches: list[dict[str, Any]], *, as_of: date,
                sla_days: Mapping[str, int],
                existing: list[dict[str, Any]] | None = None,
                source: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """위반 → 검증 사례. 동일 입력이면 동일 ID·기한이 산출된다."""
    day = as_of.strftime("%Y%m%d")
    seq = _next_seq(existing or [], day)
    cases = []
    for b in sorted(breaches, key=lambda x: x["trigger_id"]):
        days = int(sla_days.get(b["severity"], 20))
        cases.append({
            "case_id": f"VC-{day}-{seq:04d}",
            "trigger_id": b["trigger_id"],
            "domain": b["domain"],
            "metric": b["metric"],
            "observed": b["observed"],
            "expected": b["expected"],
            "variance": b["variance"],
            "tolerance": b["tolerance"],
            "severity": b["severity"],
            "owner_role": b["owner_role"],
            "opened_at": as_of.isoformat(),
            "due_at": (as_of + timedelta(days=days)).isoformat(),
            "sla_days": days,
            "status": "open",
            "threshold_ref": b["threshold_ref"],
            "source": dict(source or {}),
        })
        seq += 1
    return cases


def emit_cases(cases: list[dict[str, Any]],
               path: str | Path | None = None) -> Path:
    """사례를 append-only 원장에 적재한다."""
    p = Path(path or CASES_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return p


def queue(cases: list[dict[str, Any]] | None = None, *,
          owner_role: str | None = None, severity: str | None = None,
          as_of: date | None = None) -> list[dict[str, Any]]:
    """열린 사례의 검토 큐 — 기한 임박 순. SLA 초과분을 표시한다."""
    rows = [c for c in (cases if cases is not None else load_cases())
            if c.get("status") == "open"]
    if owner_role:
        rows = [c for c in rows if c["owner_role"] == owner_role]
    if severity:
        rows = [c for c in rows if c["severity"] == severity]
    today = as_of or date.today()
    for c in rows:
        c["overdue"] = date.fromisoformat(c["due_at"]) < today
    return sorted(rows, key=lambda c: (c["due_at"], c["case_id"]))


# --------------------------------------------------------------------- 보고
_MARK = {STATUS_OK: "정상", STATUS_BREACH: "위반",
         STATUS_NOT_EVALUATED: "미산출"}


def render_evaluation(ev: Mapping[str, Any]) -> str:
    lines = [
        f"상시 모니터링 트리거 평가 — {ev['n_total']}건 "
        f"(위반 {len(ev['breaches'])} · 미산출 {len(ev['not_evaluated'])})",
        "",
    ]
    for r in ev["results"]:
        obs = "—" if r["observed"] is None else f"{r['observed']:.4f}"
        var = "—" if r["variance"] is None else f"{r['variance']:+.4f}"
        lines.append(
            f"[{_MARK[r['status']]}] {r['trigger_id']} {r['metric']}: "
            f"observed={obs} expected={r['expected']:.4f} "
            f"variance={var} tolerance={r['tolerance']:.4f}")
        if r["status"] != STATUS_OK:
            lines.append(f"      근거: {r['threshold_ref']}")
    return "\n".join(lines)


def render_queue(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "열린 검증 사례 없음."
    lines = [f"검증 사례 검토 큐 — {len(rows)}건", ""]
    for c in rows:
        flag = " [SLA 초과]" if c.get("overdue") else ""
        lines.append(
            f"{c['case_id']} · {c['severity']} · {c['owner_role']} · "
            f"기한 {c['due_at']}{flag}")
        lines.append(f"      {c['trigger_id']} {c['metric']} "
                     f"variance={c['variance']:+.4f} "
                     f"(tolerance {c['tolerance']:.4f})")
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="상시 모니터링 트리거 평가 및 검증 사례 생성")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("triggers", help="트리거 원장 출력")

    p_ev = sub.add_parser("evaluate", help="트리거 평가 (위반 시 exit 1)")
    p_ev.add_argument("--n", type=int, default=100_000)
    p_ev.add_argument("--seed", type=int, default=42)
    p_ev.add_argument("--stress", action="store_true")
    p_ev.add_argument("--emit", action="store_true",
                      help="위반을 검증 사례 원장에 적재")
    p_ev.add_argument("--as-of", default=None, help="기준일 (YYYY-MM-DD)")
    p_ev.add_argument("--log-dir", type=Path, default=None)

    p_q = sub.add_parser("queue", help="열린 검증 사례 큐")
    p_q.add_argument("--owner", default=None)
    p_q.add_argument("--severity", default=None)

    args = parser.parse_args(argv)
    data = load_triggers()

    if args.cmd == "triggers":
        for t in data["triggers"]:
            sys.stdout.write(
                f"{t['trigger_id']} · {t['domain']} · {t['metric']} · "
                f"{t['direction']} expected={t['expected']} "
                f"tolerance={t['tolerance']} · {t['severity']} · "
                f"{t['evaluation_cycle']} · {t['owner_role']}\n")
        return 0

    if args.cmd == "queue":
        sys.stdout.write(render_queue(
            queue(owner_role=args.owner, severity=args.severity)) + "\n")
        return 0

    from tools.run_workflow_demo import run_demo

    log_dir = args.log_dir or (ROOT / "logs")
    demo = run_demo(args.n, args.stress, args.seed, log_dir)
    ev = evaluate(demo, triggers=data)
    sys.stdout.write(render_evaluation(ev) + "\n")

    if args.emit and ev["breaches"]:
        as_of = (date.fromisoformat(args.as_of) if args.as_of else date.today())
        cases = build_cases(
            ev["breaches"], as_of=as_of,
            sla_days=data["sla_days_by_severity"], existing=load_cases(),
            source={"n": args.n, "seed": args.seed, "stress": args.stress})
        emit_cases(cases)
        sys.stdout.write(f"\n검증 사례 {len(cases)}건 생성 → {CASES_PATH}\n")
        for c in cases:
            sys.stdout.write(f"  {c['case_id']} {c['trigger_id']} "
                             f"(기한 {c['due_at']}, {c['owner_role']})\n")
        sys.stdout.write("사례 종결·의견 확정은 인간 검증자 권한입니다 (HITL).\n")
    return 1 if ev["breaches"] else 0


__all__ = [
    "load_triggers", "evaluate", "evaluate_trigger", "build_cases",
    "emit_cases", "load_cases", "queue", "render_evaluation", "render_queue",
    "TRIGGERS_PATH", "CASES_PATH",
]


if __name__ == "__main__":
    raise SystemExit(main())
