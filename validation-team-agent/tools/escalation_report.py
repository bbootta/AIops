"""WorkflowRun 의 fail step 들을 MRMC/CRO 보고용 escalation 보고서로 정리.

본 도구는 의견을 확정하지 않는다. fail 사유를 모아 인간 검증자가 즉시 다음
조치를 결정할 수 있도록 정형화된 markdown 을 산출한다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.workflow import WorkflowRun


_SEVERITY = {"fail": "🔴 fail", "warning": "🟡 warning", "ok": "🟢 ok",
             "skipped": "⚪ skipped", "simulated": "⚫ simulated"}


def render_markdown(run: WorkflowRun, *, title: str | None = None) -> str:
    failed_ids = [sid for sid, r in run.context.results.items() if r.status == "fail"]
    warned_ids = [sid for sid, r in run.context.results.items() if r.status == "warning"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    head = title or "Escalation Report (MRMC / CRO)"
    summary = run.summary()

    lines = [
        f"# {head}",
        "",
        f"- 생성 시각: {ts}",
        f"- 정적 plan step 수: {summary['n_planned']}",
        f"- 실제 실행 step 수: {summary['n_executed']}",
        f"- escalation 동적 활성 여부: **{summary['escalated']}**",
        f"- fail step: {len(failed_ids)} / warning step: {len(warned_ids)}",
        "",
        "> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가",
        "",
    ]

    if failed_ids:
        lines.append("## 1. 실패 (fail) 사유")
        lines.append("")
        lines.append("| Step | Severity | 사유 |")
        lines.append("|---|---|---|")
        for sid in failed_ids:
            r = run.context.results[sid]
            lines.append(
                f"| `{sid}` | {_SEVERITY[r.status]} | {r.detail.replace('|', '/')} |"
            )
        lines.append("")

    if warned_ids:
        lines.append("## 2. 주의 (warning) 사유")
        lines.append("")
        lines.append("| Step | Severity | 사유 |")
        lines.append("|---|---|---|")
        for sid in warned_ids:
            r = run.context.results[sid]
            lines.append(
                f"| `{sid}` | {_SEVERITY[r.status]} | {r.detail.replace('|', '/')} |"
            )
        lines.append("")

    lines.append("## 3. 권고 조치")
    if failed_ids:
        lines.append("- 인간 검증자가 즉시 fail step 별 원인 분석 후 매니페스트 CHG 항목 추가")
        lines.append("- 자본/유동성/시장/IRRBB 부문 fail 은 MRMC 보고 의무 (감독시행세칙)")
        lines.append("- 외부 제출 / 감독원 대응 문안 확정은 본 보고서로 갈음할 수 없음 (CLAUDE.md §5)")
    else:
        lines.append("- 즉시 조치 사항 없음 (warning 만 발생).")
    lines.append("")

    lines.append("## 4. 실행 trace")
    lines.append("")
    lines.append("| Order | Step | Status | Detail |")
    lines.append("|---|---|---|---|")
    for i, sid in enumerate(run.executed_order, start=1):
        r = run.context.results[sid]
        dyn = " (dynamic)" if sid not in run.plan else ""
        lines.append(
            f"| {i} | `{sid}`{dyn} | {_SEVERITY[r.status]} | "
            f"{r.detail.replace('|', '/')} |"
        )
    lines.append("")

    lines.append(
        "> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은 "
        "인간 검증자의 검토와 승인을 거쳐야 합니다."
    )
    return "\n".join(lines) + "\n"


def render_json(run: WorkflowRun) -> str:
    """SOC 모니터링 / MRMC 시스템 입력용 정형 JSON."""
    payload = {
        "summary": run.summary(),
        "failed_steps": [
            {"id": sid, "detail": r.detail, "outputs": _coerce(r.outputs)}
            for sid, r in run.context.results.items() if r.status == "fail"
        ],
        "warning_steps": [
            {"id": sid, "detail": r.detail, "outputs": _coerce(r.outputs)}
            for sid, r in run.context.results.items() if r.status == "warning"
        ],
        "executed_order": run.executed_order,
        "static_plan": run.plan,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _coerce(obj):
    import numpy as np

    if isinstance(obj, dict):
        return {str(k): _coerce(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce(x) for x in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return obj
