"""검증 워크플로우 정적 HTML 대시보드 (Q5-2).

``logs/run.jsonl`` 의 step 이벤트를 run 단위로 묶어 단일 self-contained HTML
파일로 시각화한다. 서버·외부 JS·외부 호출 없음 — 파일 기반이며 브라우저로 연다.

run 경계: ``1.req`` step 이벤트가 새 run 의 시작이다 (모든 워크플로우 plan 의
첫 step). ``1.req`` 이전의 고아 이벤트는 직전 run 으로 귀속한다.

산출물은 검증 보조 자료이며 DRAFT 고지가 포함된다 (외부 제출 금지).

사용:
    python -m tools.dashboard --log logs/run.jsonl --out reports/dashboard.html
"""

from __future__ import annotations

import argparse
import html as _html
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_STATUS_COLOR = {
    "ok": "#d4edda",
    "warning": "#fff3cd",
    "fail": "#f8d7da",
    "skipped": "#e2e3e5",
    "simulated": "#d1ecf1",
}


def group_runs(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """step 이벤트를 run 단위로 분할한다. '1.req' 가 새 run 시작."""
    runs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for rec in records:
        if rec.get("step_id") == "1.req" and current:
            runs.append(current)
            current = []
        current.append(rec)
    if current:
        runs.append(current)
    return runs


def summarise_run(run: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for rec in run:
        ws = rec.get("workflow_status", rec.get("status", "?"))
        counts[ws] = counts.get(ws, 0) + 1
    return {
        "started": run[0].get("timestamp", "?"),
        "n_steps": len(run),
        "counts": counts,
        "escalated": any(rec.get("dynamic") for rec in run),
        "fails": counts.get("fail", 0),
        "warnings": counts.get("warning", 0),
    }


def _esc(s: Any) -> str:
    return _html.escape(str(s))


def render_dashboard(records: list[dict[str, Any]], *, title: str = "Validation Workflow Dashboard") -> str:
    runs = group_runs(records)
    summaries = [summarise_run(r) for r in runs]

    rows = []
    for i, s in enumerate(reversed(summaries), start=1):
        idx = len(summaries) - i  # 최신이 위
        badge = "⚠️ escalated" if s["escalated"] else ""
        cls = "fail" if s["fails"] else ("warn" if s["warnings"] else "ok")
        rows.append(
            f'<tr class="{cls}"><td>{idx + 1}</td><td>{_esc(s["started"])}</td>'
            f'<td>{s["n_steps"]}</td><td>{s["fails"]}</td><td>{s["warnings"]}</td>'
            f"<td>{badge}</td></tr>"
        )

    # 최신 run 상세
    detail_rows = []
    if runs:
        for rec in runs[-1]:
            ws = rec.get("workflow_status", rec.get("status", "?"))
            color = _STATUS_COLOR.get(ws, "#fff")
            dyn = " 🔄" if rec.get("dynamic") else ""
            detail_rows.append(
                f'<tr style="background:{color}"><td><code>{_esc(rec.get("step_id"))}</code>{dyn}</td>'
                f"<td>{_esc(ws)}</td><td>{_esc(rec.get('detail', ''))}</td></tr>"
            )

    total = len(summaries)
    total_fail_runs = sum(1 for s in summaries if s["fails"])
    total_escalated = sum(1 for s in summaries if s["escalated"])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>
<style>
body {{ font-family: -apple-system, "Malgun Gothic", sans-serif; margin: 2rem; color: #212529; }}
.draft {{ background: #fff3cd; border: 1px solid #ffc107; padding: .6rem 1rem; font-weight: 600; }}
table {{ border-collapse: collapse; margin: 1rem 0; width: 100%; }}
th, td {{ border: 1px solid #dee2e6; padding: .35rem .6rem; text-align: left; font-size: .9rem; }}
th {{ background: #f8f9fa; }}
tr.fail td {{ background: #f8d7da; }}
tr.warn td {{ background: #fff3cd; }}
.kpi {{ display: inline-block; margin-right: 2rem; }}
.kpi b {{ font-size: 1.6rem; }}
footer {{ margin-top: 2rem; color: #6c757d; font-size: .8rem; }}
</style>
</head>
<body>
<div class="draft">[DRAFT — 외부 제출 금지] 본 대시보드는 검증 보조 자료다. 최종 판단은 인간 검증자 책임.</div>
<h1>{_esc(title)}</h1>
<p>
<span class="kpi"><b>{total}</b><br>총 run</span>
<span class="kpi"><b>{total_fail_runs}</b><br>fail 포함 run</span>
<span class="kpi"><b>{total_escalated}</b><br>escalation 발생</span>
</p>
<h2>Run 이력 (최신순)</h2>
<table>
<tr><th>#</th><th>시작</th><th>steps</th><th>fail</th><th>warning</th><th></th></tr>
{"".join(rows) if rows else '<tr><td colspan="6">step 이벤트 없음</td></tr>'}
</table>
<h2>최신 run 상세</h2>
<table>
<tr><th>Step</th><th>Status</th><th>Detail</th></tr>
{"".join(detail_rows) if detail_rows else '<tr><td colspan="3">없음</td></tr>'}
</table>
<footer>생성: tools/dashboard.py — 합성/로컬 로그 기반, 외부 호출 없음. 🔄 = 동적 escalation step.</footer>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="workflow 정적 HTML 대시보드")
    parser.add_argument("--log", type=Path, default=None,
                        help="run.jsonl 경로 (기본: logs/run.jsonl)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", default="Validation Workflow Dashboard")
    args = parser.parse_args(argv)

    from middleware.run_logger import collect_step_records

    log_path = args.log or (Path(__file__).resolve().parent.parent / "logs" / "run.jsonl")
    records = collect_step_records(log_path)
    html_text = render_dashboard(records, title=args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_text, encoding="utf-8")
    sys.stdout.write(f"대시보드 생성: {args.out} (runs={len(group_runs(records))})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
