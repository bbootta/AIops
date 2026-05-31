import json
from pathlib import Path

import pytest

from tools import workflow as wf
from tools.workflow import StepResult, WorkflowEngine, WorkflowError


def _matrix(tmp_path: Path, steps: list[dict]) -> Path:
    p = tmp_path / "matrix.json"
    p.write_text(json.dumps({"matrix_version": "t", "steps": steps}, ensure_ascii=False),
                 encoding="utf-8")
    return p


def _step(sid, **kw):
    base = {"id": sid, "name": sid, "component": "comp", "rationale": "r"}
    base.update(kw)
    return base


# ---------- StepResult ----------

def test_step_result_rejects_unknown_status():
    with pytest.raises(ValueError):
        StepResult("1.x", "weird")


# ---------- resolve_plan / gating ----------

def test_resolve_plan_respects_gates(tmp_path):
    m = _matrix(tmp_path, [
        _step("1.req", always=True),
        _step("3.market", requires_any=["market_var_exceptions"]),
    ])
    eng = WorkflowEngine(m)
    plan = eng.resolve_plan({})
    assert plan == ["1.req"]
    plan2 = eng.resolve_plan({"market_var_exceptions": 7})
    assert "3.market" in plan2


def test_resolve_plan_excludes_activated_on_fail(tmp_path):
    m = _matrix(tmp_path, [
        _step("1.req", always=True),
        _step("9.escalate", activated_on_fail=True),
    ])
    eng = WorkflowEngine(m)
    assert eng.resolve_plan({}) == ["1.req"]


# ---------- topological order ----------

def test_depends_on_orders_steps(tmp_path):
    m = _matrix(tmp_path, [
        _step("6.audit", always=True, depends_on=["4.report"]),
        _step("4.report", always=True),
    ])
    eng = WorkflowEngine(m)
    plan = eng.resolve_plan({})
    assert plan.index("4.report") < plan.index("6.audit")


def test_cycle_detected(tmp_path):
    m = _matrix(tmp_path, [
        _step("1.a", always=True, depends_on=["1.b"]),
        _step("1.b", always=True, depends_on=["1.a"]),
    ])
    eng = WorkflowEngine(m)
    with pytest.raises(WorkflowError):
        eng.resolve_plan({})


# ---------- handler dispatch ----------

def test_unregistered_step_is_simulated(tmp_path):
    m = _matrix(tmp_path, [_step("1.req", always=True)])
    eng = WorkflowEngine(m)
    run = eng.run({}, log_dir=tmp_path)
    assert run.context.results["1.req"].status == "simulated"


def test_registered_handler_runs(tmp_path):
    m = _matrix(tmp_path, [_step("1.req", always=True)])
    eng = WorkflowEngine(m)
    eng.register("1.req", lambda req, ctx: StepResult("1.req", "ok", {"v": 1}, "done"))
    run = eng.run({}, log_dir=tmp_path)
    assert run.context.results["1.req"].status == "ok"
    assert run.context.results["1.req"].outputs["v"] == 1


def test_register_unknown_step_raises(tmp_path):
    m = _matrix(tmp_path, [_step("1.req", always=True)])
    eng = WorkflowEngine(m)
    with pytest.raises(KeyError):
        eng.register("9.nonexistent", lambda req, ctx: StepResult("9.nonexistent", "ok"))


def test_handler_exception_becomes_fail_with_category(tmp_path):
    m = _matrix(tmp_path, [_step("3.capital", always=True)])
    eng = WorkflowEngine(m)

    def boom(req, ctx):
        raise ValueError("required columns missing: ['x']")

    eng.register("3.capital", boom)
    run = eng.run({}, log_dir=tmp_path)
    r = run.context.results["3.capital"]
    assert r.status == "fail"
    assert "category" in r.outputs


# ---------- dynamic branching ----------

def test_fail_activates_escalation_step(tmp_path):
    m = _matrix(tmp_path, [
        _step("3.capital", always=True, on_fail_activate=["9.escalate"]),
        _step("9.escalate", activated_on_fail=True),
    ])
    eng = WorkflowEngine(m)
    eng.register("3.capital", lambda req, ctx: StepResult("3.capital", "fail", {}, "CET1 below floor"))
    run = eng.run({}, log_dir=tmp_path)
    assert "9.escalate" in run.executed_order
    assert "9.escalate" not in run.plan  # dynamic, not in static plan
    assert run.summary()["escalated"] is True


def test_ok_does_not_activate_escalation(tmp_path):
    m = _matrix(tmp_path, [
        _step("3.capital", always=True, on_fail_activate=["9.escalate"]),
        _step("9.escalate", activated_on_fail=True),
    ])
    eng = WorkflowEngine(m)
    eng.register("3.capital", lambda req, ctx: StepResult("3.capital", "ok", {}, "passed"))
    run = eng.run({}, log_dir=tmp_path)
    assert "9.escalate" not in run.executed_order
    assert run.summary()["escalated"] is False


# ---------- repo matrix integration ----------

def test_repo_matrix_loads_and_capital_escalation_wired():
    eng = WorkflowEngine()
    cap = eng.steps_by_id["3.capital"]
    assert "9.escalate" in cap.get("on_fail_activate", [])
    assert eng.steps_by_id["9.escalate"].get("activated_on_fail") is True


def test_render_markdown_smoke(tmp_path):
    m = _matrix(tmp_path, [_step("1.req", always=True)])
    eng = WorkflowEngine(m)
    run = eng.run({}, log_dir=tmp_path)
    md = run.render_markdown()
    assert "# Workflow Run" in md
    assert "1.req" in md
