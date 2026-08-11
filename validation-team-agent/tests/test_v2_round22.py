"""Round 22 — workflow viz + handler 도메인 alias + README 확인."""

from pathlib import Path



# ---------- handler 도메인 alias 동일성 ----------

def test_credit_aliases_match_v1():
    import vta.handlers.credit as c
    import tools.handlers as v1

    assert c.discrimination is v1.credit_discrimination_handler
    assert c.psi is v1.credit_psi_handler
    assert c.calibration is v1.credit_calibration_handler
    assert c.sample_size is v1.sample_size_handler


def test_basel_aliases_match_v1():
    import vta.handlers.basel as b
    import tools.handlers as v1

    assert b.capital is v1.capital_handler
    assert b.market is v1.market_handler
    assert b.liquidity is v1.liquidity_handler
    assert b.irrbb is v1.irrbb_handler
    assert b.operational is v1.operational_handler
    assert b.cva is v1.cva_handler
    assert b.ccr is v1.ccr_handler


def test_report_aliases_match_v1():
    import vta.handlers.report as r
    import tools.handlers as v1

    assert r.report is v1.report_handler
    assert r.completeness is v1.completeness_handler
    assert r.citation is v1.citation_handler
    assert r.watermark is v1.watermark_handler
    assert r.escalation is v1.escalation_handler


def test_data_aliases_match_v1():
    import vta.handlers.data as d
    import tools.handlers as v1

    assert d.request is v1.request_reconstruction_handler
    assert d.schema is v1.schema_check_handler
    assert d.safety is v1.safety_check_handler
    assert d.leakage is v1.leakage_check_handler
    assert d.date_coverage is v1.date_coverage_handler
    assert d.duplicates is v1.duplicates_check_handler
    assert d.audit is v1.audit_handler


def test_macro_aliases_match_v1():
    import vta.handlers.macro as m
    import tools.handlers as v1

    assert m.stationarity is v1.macro_handler
    assert m.scenario_weights is v1.scenario_weights_handler


def test_all_handler_aliases_cover_v1_default():
    """domain alias 의 union 이 v1 _DEFAULT 의 모든 handler 를 포함."""
    import vta.handlers.credit as credit
    import vta.handlers.basel as basel
    import vta.handlers.report as report
    import vta.handlers.data as data
    import vta.handlers.macro as macro
    import tools.handlers as v1

    aliased = set()
    for mod in (credit, basel, report, data, macro):
        for name in mod.__all__:
            aliased.add(id(getattr(mod, name)))

    v1_set = {id(h) for h in v1._DEFAULT.values()}
    missing = v1_set - aliased
    assert not missing, f"v1 _DEFAULT 중 alias 누락: {missing}"


# ---------- workflow viz ----------

def test_viz_render_flowchart_for_simple_run(tmp_path):
    from tools.handlers import register_default_handlers
    from tools.workflow import WorkflowEngine
    from tools.workflow_viz import render_flowchart

    eng = WorkflowEngine()
    register_default_handlers(eng)
    run = eng.run({"capital_cet1": 0.03, "capital_tier1": 0.04,
                   "capital_total": 0.05, "capital_leverage": 0.02},
                  log_dir=tmp_path)
    md = render_flowchart(run)
    assert md.startswith("```mermaid")
    assert "flowchart TD" in md
    assert "3_capital" in md
    assert "9_escalate" in md
    assert "fill:#f8d7da" in md  # fail color
    assert "-.->\n" in md or "-.->" in md  # dynamic arrow


def test_viz_render_sequence_uses_participants(tmp_path):
    from tools.handlers import register_default_handlers
    from tools.workflow import WorkflowEngine
    from tools.workflow_viz import render_sequence

    eng = WorkflowEngine()
    register_default_handlers(eng)
    run = eng.run({"capital_cet1": 0.13}, log_dir=tmp_path)
    md = render_sequence(run)
    assert "sequenceDiagram" in md
    assert "participant Eng" in md
    assert "Handler" in md


def test_viz_render_table_shows_dynamic_marker(tmp_path):
    from tools.handlers import register_default_handlers
    from tools.workflow import WorkflowEngine
    from tools.workflow_viz import render_table

    eng = WorkflowEngine()
    register_default_handlers(eng)
    run = eng.run({"capital_cet1": 0.02, "capital_tier1": 0.03,
                   "capital_total": 0.04, "capital_leverage": 0.01},
                  log_dir=tmp_path)
    md = render_table(run)
    # 동적 escalation step 행에 🔄 마커
    assert "9.escalate" in md
    assert "🔄" in md


def test_viz_render_from_log_handles_missing_file(tmp_path):
    from tools.workflow_viz import render_from_log

    out = render_from_log(tmp_path / "no.jsonl")
    assert "no step events" in out


def test_viz_render_from_log_with_real_events(tmp_path):
    from middleware.run_logger import log_step
    from tools.workflow_viz import render_from_log

    log_step("1.req", component="x", log_dir=tmp_path,
             extra={"workflow_status": "ok"})
    log_step("3.capital", component="y", status="failed", log_dir=tmp_path,
             extra={"workflow_status": "fail", "detail": "CET1 below"})
    md = render_from_log(tmp_path / "run.jsonl")
    assert "mermaid" in md
    assert "1_req" in md
    assert "3_capital" in md


def test_viz_cli_writes_output_file(tmp_path, capsys):
    from middleware.run_logger import log_step
    from tools.workflow_viz import main

    log_step("1.req", component="x", log_dir=tmp_path,
             extra={"workflow_status": "ok"})
    out_path = tmp_path / "diagram.md"
    rc = main(["--log", str(tmp_path / "run.jsonl"),
               "--out", str(out_path)])
    assert rc == 0
    assert out_path.exists()
    assert "mermaid" in out_path.read_text(encoding="utf-8")


# ---------- README ----------

def test_readme_mentions_vta_cli():
    root = Path(__file__).resolve().parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "python -m vta" in readme
    assert "vta workflow" in readme
    assert "vta policy list" in readme
