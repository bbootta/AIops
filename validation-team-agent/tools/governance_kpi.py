"""Governance KPI 산출.

분기 CRO/감사위원회 보고용 단일 진입점. 매니페스트 / classify_feedback /
audit.jsonl 에서 핵심 지표를 모아 출력한다.

사용:
    python -m tools.governance_kpi report
    python -m tools.governance_kpi report --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent


def _load_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def manifest_kpi(manifest_path: Path | None = None) -> dict:
    p = manifest_path or (ROOT / "harness" / "change_manifest.json")
    m = _load_json(p)
    if not m:
        return {"available": False}
    counts = Counter(c.get("status") for c in m.get("changes", []))
    total = sum(counts.values()) or 1
    return {
        "available": True,
        "total": sum(counts.values()),
        "proposed_count": counts.get("proposed", 0),
        "applied_count": counts.get("applied", 0),
        "validated_count": counts.get("validated", 0),
        "rolled_back_count": counts.get("rolled_back", 0),
        "validated_ratio": counts.get("validated", 0) / total,
        "applied_or_validated_ratio": (
            counts.get("applied", 0) + counts.get("validated", 0)
        ) / total,
    }


def feedback_kpi(feedback_path: Path | None = None) -> dict:
    p = feedback_path or (ROOT / "memory" / "classify_feedback.jsonl")
    records = _read_jsonl(p)
    n = len(records)
    if n == 0:
        return {"available": False, "feedback_total": 0}
    n_agree = sum(1 for r in records if r.get("agreement"))
    pairs = Counter()
    for r in records:
        if not r.get("agreement"):
            pairs[f"{r.get('predicted_category')}->{r.get('confirmed_category')}"] += 1
    return {
        "available": True,
        "feedback_total": n,
        "agreement_count": n_agree,
        "agreement_rate": n_agree / n,
        "mismatch_top_pairs": pairs.most_common(5),
    }


def audit_kpi(audit_path: Path | None = None) -> dict:
    p = audit_path or (ROOT / "logs" / "audit.jsonl")
    rows = _read_jsonl(p)
    if not rows:
        return {"available": False}
    # 가장 최근 run_ts 기준 통계
    latest_ts = max((r.get("run_ts", "") for r in rows), default="")
    latest_rows = [r for r in rows if r.get("run_ts") == latest_ts]
    counts = Counter(r.get("status") for r in latest_rows)
    return {
        "available": True,
        "latest_run_ts": latest_ts,
        "latest_run_executed": counts.get("executed", 0),
        "latest_run_skipped": counts.get("skipped", 0),
        "latest_run_missing": counts.get("missing", 0),
        "total_rows": len(rows),
    }


def policy_lint_kpi() -> dict:
    try:
        from tools import policy_lint  # type: ignore
    except Exception as exc:  # pragma: no cover
        return {"available": False, "error": str(exc)}
    lint = policy_lint.lint_policies()
    sample = policy_lint.check_sample_size_alignment()
    return {
        "available": True,
        "policy_lint_passed": bool(lint["passed"]),
        "policy_lint_conflicts": len(lint["conflicts"]),
        "sample_size_passed": bool(sample["passed"]),
        "sample_size_conflicts": len(sample["conflicts"]),
    }


def build_report() -> dict[str, Any]:
    return {
        "manifest": manifest_kpi(),
        "feedback": feedback_kpi(),
        "audit": audit_kpi(),
        "policy": policy_lint_kpi(),
    }


def render_markdown(report: dict) -> str:
    lines = ["# Governance KPI Report", ""]

    m = report.get("manifest", {})
    if m.get("available"):
        lines.append("## Change Manifest")
        lines.append(
            f"- total: {m['total']} (proposed={m['proposed_count']}, "
            f"applied={m['applied_count']}, validated={m['validated_count']}, "
            f"rolled_back={m['rolled_back_count']})"
        )
        lines.append(f"- validated_ratio: {m['validated_ratio']:.2%}")
        lines.append(f"- applied_or_validated_ratio: {m['applied_or_validated_ratio']:.2%}")
        lines.append("")

    f = report.get("feedback", {})
    if f.get("available"):
        lines.append("## Classify Feedback")
        lines.append(
            f"- total: {f['feedback_total']}, agreement: {f['agreement_count']} "
            f"({f['agreement_rate']:.2%})"
        )
        if f.get("mismatch_top_pairs"):
            lines.append("- top mismatches:")
            for pair, cnt in f["mismatch_top_pairs"]:
                lines.append(f"    - `{pair}` ({cnt})")
        lines.append("")
    else:
        lines.append("## Classify Feedback")
        lines.append("- (no feedback recorded yet)")
        lines.append("")

    a = report.get("audit", {})
    if a.get("available"):
        lines.append("## Audit (latest run)")
        lines.append(f"- run_ts: {a['latest_run_ts']}")
        lines.append(
            f"- executed={a['latest_run_executed']}, "
            f"skipped={a['latest_run_skipped']}, missing={a['latest_run_missing']}"
        )
        lines.append(f"- total_rows_in_log: {a['total_rows']}")
        lines.append("")
    else:
        lines.append("## Audit")
        lines.append("- (logs/audit.jsonl is empty; run `tools.run_audit demo --append-jsonl`)")
        lines.append("")

    p = report.get("policy", {})
    if p.get("available"):
        lines.append("## Policy Lint")
        lines.append(
            f"- policy_lint: {'PASS' if p['policy_lint_passed'] else 'FAIL'} "
            f"({p['policy_lint_conflicts']} conflicts)"
        )
        lines.append(
            f"- sample_size_alignment: {'PASS' if p['sample_size_passed'] else 'FAIL'} "
            f"({p['sample_size_conflicts']} conflicts)"
        )
        lines.append("")

    lines.append(
        "> 본 KPI 는 자동 산출이며 의사결정 자체가 아닙니다. "
        "CRO/MRMC 의 검토와 함께 해석되어야 합니다."
    )
    return "\n".join(lines) + "\n"


def _cmd_report(args: argparse.Namespace) -> int:
    report = build_report()
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="governance KPI report")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_rep = sub.add_parser("report", help="emit governance KPI report")
    p_rep.add_argument("--json", action="store_true")
    p_rep.set_defaults(func=_cmd_report)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
