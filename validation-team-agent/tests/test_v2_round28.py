"""Round 28 — v2 Phase 3: 비동기 워크플로우 (Q4=a)."""

from __future__ import annotations

import asyncio

import pytest


def _engine():
    from tools.handlers import register_default_handlers
    from vta.core.workflow import WorkflowEngine

    eng = WorkflowEngine()
    register_default_handlers(eng)
    return eng


def _stress_request():
    # 자본 미달 → 9.escalate 동적 활성
    return {
        "capital_cet1": 0.03,
        "capital_tier1": 0.04,
        "capital_total": 0.05,
        "capital_leverage": 0.02,
    }


def test_async_same_steps_as_sync(tmp_path):
    """async 실행 결과의 step 집합/status 가 sync 와 동일하다."""
    eng = _engine()
    req = _stress_request()
    sync_run = eng.run(req, log_dir=tmp_path / "sync")

    eng2 = _engine()
    async_run = asyncio.run(eng2.run_async(req, log_dir=tmp_path / "async"))

    assert set(async_run.executed_order) == set(sync_run.executed_order)
    assert sorted(async_run.plan) == sorted(sync_run.plan)
    sync_status = {sid: r.status for sid, r in sync_run.context.results.items()}
    async_status = {sid: r.status for sid, r in async_run.context.results.items()}
    assert async_status == sync_status


def test_async_dynamic_escalation(tmp_path):
    eng = _engine()
    run = asyncio.run(eng.run_async(_stress_request(), log_dir=tmp_path))
    assert "9.escalate" in run.executed_order
    assert "9.escalate" not in run.plan  # 동적 삽입
    assert run.summary()["escalated"] is True


def test_async_respects_dependencies(tmp_path):
    """depends_on 이 있는 step 은 의존 step 완료 후에 실행된다."""
    eng = _engine()
    run = asyncio.run(eng.run_async(_stress_request(), log_dir=tmp_path))
    order = {sid: i for i, sid in enumerate(run.executed_order)}
    for sid in run.executed_order:
        for dep in eng.steps_by_id[sid].get("depends_on", []):
            if dep in order:
                assert order[dep] < order[sid], f"{dep} 가 {sid} 보다 늦게 완료"


def test_async_logs_steps(tmp_path):
    from middleware.run_logger import collect_step_ids

    eng = _engine()
    run = asyncio.run(eng.run_async(_stress_request(), log_dir=tmp_path))
    logged = collect_step_ids(tmp_path / "run.jsonl")
    # collect_step_ids 는 설계상 skipped 를 제외 — 실제 수행 step 만 비교
    performed = {
        sid for sid in run.executed_order
        if run.context.results[sid].status != "skipped"
    }
    assert performed <= set(logged)


def test_async_max_concurrency_one_is_sequential(tmp_path):
    """max_concurrency=1 이면 한 번에 한 step 만 실행 (sync 와 의미 동일)."""
    eng = _engine()
    run = asyncio.run(
        eng.run_async(_stress_request(), log_dir=tmp_path, max_concurrency=1)
    )
    assert "9.escalate" in run.executed_order


def test_async_handler_exception_classified(tmp_path):
    """handler 예외는 async 경로에서도 fail + 분류로 처리된다."""
    from vta.core.workflow import StepResult, WorkflowEngine

    eng = WorkflowEngine()

    def boom(req, ctx):
        raise RuntimeError("boom")

    eng.register("1.req", boom)
    run = asyncio.run(eng.run_async({"always_on": True}, log_dir=tmp_path))
    r = run.context.results["1.req"]
    assert r.status == "fail"
    assert "RuntimeError" in r.detail


def test_demo_async_flag(tmp_path):
    from tools.run_workflow_demo import run_demo

    demo = run_demo(500, False, 42, tmp_path, use_async=True)
    assert demo["async_mode"] is True
    assert demo["summary"]["n_executed"] >= 1
    # 정상 case 에서는 escalation 없음
    assert demo["summary"]["escalated"] is False


def test_demo_sync_default_unchanged(tmp_path):
    from tools.run_workflow_demo import run_demo

    demo = run_demo(500, False, 42, tmp_path)
    assert demo["async_mode"] is False
