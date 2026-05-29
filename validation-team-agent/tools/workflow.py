"""Dynamic workflow engine for the validation harness.

정적 ``harness/orchestration_matrix.json`` 을 실행 가능한 워크플로우로 끌어올린다.
``tools.dry_run`` 이 plan(어떤 step 이 활성인지)을 시뮬레이션하는 반면, 본 엔진은:

1. request 게이트 평가 (dry_run 로직 재사용) 로 활성 step 결정
2. ``depends_on`` 위상정렬로 실행 순서 결정 (cycle 감지)
3. 등록된 handler 를 동적 dispatch (registry 패턴). 미등록 step 은 simulated.
4. step 결과 status 가 fail 이면 해당 step 의 ``on_fail_activate`` 에 나열된
   escalation step 을 plan 에 **동적 삽입** (정적 plan 이 실행 결과에 따라 변함).
5. 모든 step 을 ``middleware.run_logger.log_step`` 으로 기록.
6. handler 예외는 ``tools.classify_error`` 로 6-카테고리 분류 후 fail 처리.

본 엔진은 검증 의견을 확정하지 않는다. handler 는 점검 결과(StepResult)만 만들고,
최종 판단은 인간 검증자가 수행한다 (CLAUDE.md HITL 원칙).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from middleware.run_logger import log_step
from tools.dry_run import _gate_passes, load_matrix

# handler(request, context) -> StepResult
Handler = Callable[[Mapping[str, Any], "WorkflowContext"], "StepResult"]

_VALID_STATUS = {"ok", "warning", "fail", "skipped", "simulated"}
_LOG_STATUS = {
    "ok": "executed",
    "warning": "executed",
    "simulated": "executed",
    "fail": "failed",
    "skipped": "skipped",
}


@dataclass
class StepResult:
    step_id: str
    status: str  # ok | warning | fail | skipped | simulated
    outputs: dict = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self):
        if self.status not in _VALID_STATUS:
            raise ValueError(f"invalid status {self.status!r}; expected {sorted(_VALID_STATUS)}")


@dataclass
class WorkflowContext:
    """step 간 공유 컨텍스트. handler 가 이전 결과를 참조할 수 있다."""

    request: Mapping[str, Any]
    results: dict[str, StepResult] = field(default_factory=dict)

    def result(self, step_id: str) -> StepResult | None:
        return self.results.get(step_id)


class WorkflowError(RuntimeError):
    pass


def _topological_order(step_ids: list[str], steps_by_id: Mapping[str, dict]) -> list[str]:
    """depends_on 기반 위상정렬 (Kahn). plan 에 없는 의존성은 무시. cycle 시 WorkflowError."""
    in_plan = set(step_ids)
    indeg = {sid: 0 for sid in step_ids}
    adj: dict[str, list[str]] = {sid: [] for sid in step_ids}
    for sid in step_ids:
        for dep in steps_by_id[sid].get("depends_on", []):
            if dep in in_plan:
                adj[dep].append(sid)
                indeg[sid] += 1
    # 안정 정렬: 매트릭스 원래 순서를 보존하기 위해 step_ids 순서로 큐 초기화
    queue = [sid for sid in step_ids if indeg[sid] == 0]
    order: list[str] = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                # 원래 순서 보존하며 삽입
                queue.append(nxt)
                queue.sort(key=lambda s: step_ids.index(s))
    if len(order) != len(step_ids):
        raise WorkflowError(f"dependency cycle detected among {step_ids}")
    return order


class WorkflowEngine:
    def __init__(self, matrix_path: Path | None = None):
        self.matrix = load_matrix(matrix_path)
        self.steps_by_id = {s["id"]: s for s in self.matrix["steps"]}
        self._handlers: dict[str, Handler] = {}

    def register(self, step_id: str, handler: Handler) -> None:
        if step_id not in self.steps_by_id:
            raise KeyError(f"unknown step_id {step_id!r}; not in orchestration_matrix")
        self._handlers[step_id] = handler

    def resolve_plan(self, request: Mapping[str, Any]) -> list[str]:
        """게이트 통과 step 의 id 를 위상정렬 순서로 반환 (escalation step 제외)."""
        active = [s["id"] for s in self.matrix["steps"] if _gate_passes(s, request)]
        return _topological_order(active, self.steps_by_id)

    def run(
        self,
        request: Mapping[str, Any],
        *,
        log_dir: str | Path | None = None,
    ) -> "WorkflowRun":
        """plan 을 실행하고, fail 시 on_fail_activate step 을 동적 삽입한다."""
        plan = self.resolve_plan(request)
        ctx = WorkflowContext(request=request)
        executed_order: list[str] = []
        pending = list(plan)
        seen: set[str] = set()

        while pending:
            sid = pending.pop(0)
            if sid in seen:
                continue
            seen.add(sid)
            step = self.steps_by_id[sid]
            result = self._dispatch(sid, step, request, ctx)
            ctx.results[sid] = result
            executed_order.append(sid)

            log_step(
                sid,
                component=step["component"],
                status=_LOG_STATUS[result.status],
                log_dir=log_dir,
                extra={
                    "workflow_status": result.status,
                    "detail": result.detail,
                    "dynamic": sid not in plan,
                },
            )

            # 동적 분기: fail 이면 on_fail_activate 의 escalation step 을 삽입
            if result.status == "fail":
                for nxt in step.get("on_fail_activate", []):
                    if nxt in self.steps_by_id and nxt not in seen and nxt not in pending:
                        pending.append(nxt)

        return WorkflowRun(plan=plan, executed_order=executed_order, context=ctx)

    def _dispatch(
        self,
        sid: str,
        step: Mapping[str, Any],
        request: Mapping[str, Any],
        ctx: WorkflowContext,
    ) -> StepResult:
        handler = self._handlers.get(sid)
        if handler is None:
            return StepResult(sid, "simulated", {}, "no handler registered")
        try:
            result = handler(request, ctx)
        except Exception as exc:  # noqa: BLE001 - 분류 후 fail 처리
            category = _classify(exc)
            return StepResult(
                sid,
                "fail",
                {"error_type": type(exc).__name__, "category": category},
                f"handler raised {type(exc).__name__}: {exc} [{category}]",
            )
        if not isinstance(result, StepResult):
            raise WorkflowError(f"handler for {sid} must return StepResult, got {type(result)}")
        return result


def _classify(exc: Exception) -> str:
    try:
        from tools.classify_error import classify

        return classify(f"{type(exc).__name__}: {exc}").category
    except Exception:  # pragma: no cover
        return "code"


@dataclass
class WorkflowRun:
    plan: list[str]
    executed_order: list[str]
    context: WorkflowContext

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for r in self.context.results.values():
            counts[r.status] = counts.get(r.status, 0) + 1
        return {
            "n_planned": len(self.plan),
            "n_executed": len(self.executed_order),
            "status_counts": counts,
            "escalated": any(
                sid not in self.plan for sid in self.executed_order
            ),
        }

    def render_markdown(self) -> str:
        lines = ["# Workflow Run", "", f"- planned: {len(self.plan)} steps",
                 f"- executed: {len(self.executed_order)} steps", ""]
        lines.append("| Order | Step | Status | Detail |")
        lines.append("|---|---|---|---|")
        for i, sid in enumerate(self.executed_order, start=1):
            r = self.context.results[sid]
            dyn = " (dynamic)" if sid not in self.plan else ""
            lines.append(f"| {i} | `{sid}`{dyn} | {r.status} | {r.detail} |")
        return "\n".join(lines) + "\n"
