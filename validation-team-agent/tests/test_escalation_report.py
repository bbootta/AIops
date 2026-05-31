import json

from tools import handlers as h
from tools.escalation_report import render_json, render_markdown
from tools.workflow import StepResult, WorkflowEngine


def _failing_run(tmp_path):
    eng = WorkflowEngine()
    h.register_default_handlers(eng)
    request = {
        "capital_cet1": 0.03,
        "capital_tier1": 0.04,
        "capital_total": 0.05,
        "capital_leverage": 0.02,
        "market_var_exceptions": 12,
        "liquidity_hqla": 80.0,
        "liquidity_outflow": 100.0,
    }
    return eng.run(request, log_dir=tmp_path)


def test_render_markdown_includes_failed_section(tmp_path):
    run = _failing_run(tmp_path)
    md = render_markdown(run)
    assert "Escalation Report" in md
    assert "## 1. 실패" in md
    assert "🔴 fail" in md
    assert "외부 제출 금지" in md


def test_render_markdown_handles_clean_run(tmp_path):
    eng = WorkflowEngine()
    run = eng.run({}, log_dir=tmp_path)
    md = render_markdown(run)
    assert "즉시 조치 사항 없음" in md


def test_render_json_is_well_formed(tmp_path):
    run = _failing_run(tmp_path)
    payload = json.loads(render_json(run))
    assert "summary" in payload
    assert "failed_steps" in payload
    assert any(s["id"] == "3.capital" for s in payload["failed_steps"])
