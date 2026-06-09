"""Workflow trace 를 Mermaid 다이어그램으로 변환.

PR / 리뷰에서 동적 workflow 실행 결과의 plan vs actual 을 한눈에 보이도록
flowchart + sequence 두 가지 형태로 출력한다. 본 도구는 트레이스만 읽고
의견을 만들지 않는다.

사용:
    from tools.workflow_viz import render_flowchart, render_sequence
    md = render_flowchart(workflow_run)
    md = render_sequence(workflow_run)

CLI:
    python -m tools.workflow_viz --log logs/run.jsonl --format flowchart
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_STATUS_STYLE = {
    "ok": "fill:#d4edda,stroke:#28a745,color:#155724",
    "warning": "fill:#fff3cd,stroke:#ffc107,color:#856404",
    "fail": "fill:#f8d7da,stroke:#dc3545,color:#721c24",
    "skipped": "fill:#e2e3e5,stroke:#6c757d,color:#383d41",
    "simulated": "fill:#d1ecf1,stroke:#17a2b8,color:#0c5460",
    "executed": "fill:#d4edda,stroke:#28a745,color:#155724",
    "failed": "fill:#f8d7da,stroke:#dc3545,color:#721c24",
}


def _node_id(step_id: str) -> str:
    return step_id.replace(".", "_").replace("-", "_")


def _escape(text: str, *, limit: int = 60) -> str:
    text = text.replace("\n", " ").replace("|", "/").replace("\"", "'")
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    return text


def render_flowchart(run: Any) -> str:
    """WorkflowRun → mermaid flowchart (실행 순서 + 상태 색).

    동적으로 추가된 step (escalation 등) 은 점선 화살표로 표시.
    """
    plan = list(run.plan)
    executed = list(run.executed_order)
    results = run.context.results

    lines = ["```mermaid", "flowchart TD"]
    # 노드 정의
    for sid in executed:
        r = results[sid]
        label = f"{sid}<br/>{_escape(r.detail, limit=40)}"
        lines.append(f"    {_node_id(sid)}[{label}]")
        style = _STATUS_STYLE.get(r.status, "")
        if style:
            lines.append(f"    style {_node_id(sid)} {style}")

    # 간선: 실행 순서대로
    plan_set = set(plan)
    for a, b in zip(executed, executed[1:]):
        arrow = "-.->" if (a not in plan_set or b not in plan_set) else "-->"
        lines.append(f"    {_node_id(a)} {arrow} {_node_id(b)}")

    lines.append("```")
    return "\n".join(lines)


def render_sequence(run: Any) -> str:
    """WorkflowRun → mermaid sequence (각 step 의 component 호출 trace)."""
    lines = ["```mermaid", "sequenceDiagram",
             "    participant Eng as WorkflowEngine",
             "    participant H as Handler",
             "    participant L as Logger"]
    for sid in run.executed_order:
        r = run.context.results[sid]
        comp = _escape(getattr(run, "matrix", {}).get(sid, {}).get("component", ""), limit=40)
        lines.append(f"    Eng->>H: {sid}")
        if r.status == "fail":
            lines.append(f"    H-->>Eng: FAIL ({_escape(r.detail, limit=40)})")
        elif r.status == "warning":
            lines.append(f"    H-->>Eng: WARN ({_escape(r.detail, limit=40)})")
        else:
            lines.append(f"    H-->>Eng: {r.status}")
        lines.append(f"    Eng->>L: log_step({sid}, {r.status})")
    lines.append("```")
    return "\n".join(lines)


def render_table(run: Any) -> str:
    """간단 markdown 표 — IDE / PR comment 에 부담 없이 첨부 가능."""
    plan = set(run.plan)
    lines = ["| # | Step | Status | Dynamic | Detail |", "|---|---|---|---|---|"]
    for i, sid in enumerate(run.executed_order, start=1):
        r = run.context.results[sid]
        dyn = "🔄" if sid not in plan else ""
        lines.append(
            f"| {i} | `{sid}` | {r.status} | {dyn} | {_escape(r.detail, limit=80)} |"
        )
    return "\n".join(lines)


def render_from_log(log_path: Path, matrix_path: Path | None = None,
                    fmt: str = "flowchart") -> str:
    """logs/run.jsonl 의 step 이벤트만으로 시각화 (WorkflowRun 없이도)."""
    from middleware.run_logger import collect_step_records

    records = collect_step_records(log_path)
    if not records:
        return "(no step events in log)"

    # 매트릭스 로드 (plan 추출용; 없으면 모두 dynamic 표기 안 함)
    plan_ids: set[str] = set()
    if matrix_path and matrix_path.exists():
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        plan_ids = {s["id"] for s in matrix.get("steps", [])}

    lines = ["```mermaid", "flowchart TD" if fmt == "flowchart" else "graph LR"]
    prev_id = None
    for rec in records:
        sid = rec.get("step_id")
        if not sid:
            continue
        status = rec.get("workflow_status") or rec.get("status", "executed")
        label = f"{sid}<br/>{_escape(rec.get('detail', ''), limit=40)}"
        node = _node_id(sid)
        lines.append(f"    {node}[{label}]")
        style = _STATUS_STYLE.get(status, "")
        if style:
            lines.append(f"    style {node} {style}")
        if prev_id is not None:
            arrow = "-.->" if (sid not in plan_ids) else "-->"
            lines.append(f"    {_node_id(prev_id)} {arrow} {node}")
        prev_id = sid
    lines.append("```")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="workflow trace → mermaid")
    parser.add_argument("--log", type=Path, required=True,
                        help="logs/run.jsonl path")
    parser.add_argument("--matrix", type=Path, default=None,
                        help="orchestration_matrix.json (선택, dynamic 표기용)")
    parser.add_argument("--format", choices=["flowchart", "graph"],
                        default="flowchart")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    md = render_from_log(args.log, matrix_path=args.matrix, fmt=args.format)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
