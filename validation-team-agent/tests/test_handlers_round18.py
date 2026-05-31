"""Round 18 추가 handler + 보고서 step + escalation 보고서."""

import pandas as pd
import pytest

from tools import handlers as h
from tools.sample_generators import (
    ccr_exposure_sample,
    cva_counterparty_sample,
    ifrs9_weight_panel,
    macro_random_walk_series,
    macro_stationary_series,
)
from tools.workflow import WorkflowContext


def _ctx():
    return WorkflowContext(request={})


# ---------- 신규 도메인 handler ----------

def test_macro_handler_stationary():
    r = h.macro_handler({"macro_series": macro_stationary_series(n=250)}, _ctx())
    assert r.status == "ok"
    assert r.outputs["label"] == "stationary"


def test_macro_handler_random_walk_warns():
    r = h.macro_handler({"macro_series": macro_random_walk_series(n=250)}, _ctx())
    assert r.status == "warning"
    assert r.outputs["label"] != "stationary"


def test_macro_handler_skipped_without_series():
    assert h.macro_handler({}, _ctx()).status == "skipped"


def test_weights_handler_balanced_panel_ok():
    r = h.scenario_weights_handler(
        {"scenario_weight_panel": ifrs9_weight_panel(balanced=True)},
        _ctx(),
    )
    assert r.status == "ok"
    assert r.outputs["n_fail"] == 0


def test_weights_handler_unbalanced_panel_fails():
    r = h.scenario_weights_handler(
        {"scenario_weight_panel": ifrs9_weight_panel(balanced=False)},
        _ctx(),
    )
    assert r.status == "fail"
    assert r.outputs["n_fail"] >= 1


def test_operational_handler_returns_orc():
    r = h.operational_handler({"op_business_indicator_eur_bn": 5.0}, _ctx())
    assert r.status == "ok"
    assert r.outputs["orc_eur_bn"] > 0


def test_cva_handler_combines_inputs():
    r = h.cva_handler(
        {"cva_counterparty_inputs": cva_counterparty_sample(n=5),
         "cva_trading_book_size_eur_bn": 150.0},
        _ctx(),
    )
    assert r.status == "ok"
    assert r.outputs["sa_cva_required"] is True


def test_ccr_handler_returns_ead():
    r = h.ccr_handler(ccr_exposure_sample(), _ctx())
    assert r.status == "ok"
    assert r.outputs["alpha"] == 1.4
    assert r.outputs["ead"] > 0


# ---------- 보고서 / 점검 handler ----------

def test_report_handler_emits_markdown_with_sections():
    ctx = _ctx()
    ctx.results["3.disc"] = h.StepResult("3.disc", "ok", {}, "KS=0.5")
    r = h.report_handler({"title": "T"}, ctx)
    md = r.outputs["report_md"]
    assert "## 1. 요약" in md
    assert "## 10. 감사추적 및 변경 이력" in md


def test_completeness_handler_passes_for_template_report():
    ctx = _ctx()
    rep = h.report_handler({"title": "T"}, ctx)
    ctx.results["4.report"] = rep
    r = h.completeness_handler({}, ctx)
    assert r.status == "ok"


def test_citation_handler_runs_on_report():
    ctx = _ctx()
    ctx.results["3.disc"] = h.StepResult("3.disc", "ok", {}, "KS=0.5")
    rep = h.report_handler({"title": "T"}, ctx)
    ctx.results["4.report"] = rep
    r = h.citation_handler({}, ctx)
    assert r.status in {"ok", "warning"}


def test_watermark_handler_passes_for_template_report():
    ctx = _ctx()
    rep = h.report_handler({"title": "T"}, ctx)
    ctx.results["4.report"] = rep
    r = h.watermark_handler({}, ctx)
    assert r.status == "ok"


def test_completeness_handler_skipped_without_report():
    assert h.completeness_handler({}, _ctx()).status == "skipped"


# ---------- register_default_handlers 확장 확인 ----------

def test_default_handlers_now_cover_all_domains():
    from tools.workflow import WorkflowEngine

    eng = WorkflowEngine()
    registered = h.register_default_handlers(eng)
    for sid in ("3.macro", "3.weights", "3.operational", "3.cva", "3.ccr",
                "4.report", "5.complete", "5.cite", "5.watermark"):
        assert sid in registered
