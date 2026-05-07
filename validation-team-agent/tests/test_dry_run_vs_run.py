"""Reconcile dry_run plan against tools that run_validation actually calls.

Each simulated step's component string mentions a function (e.g.
`tools/metric_ks_auc.calculate_ks`). For each such function used in
run_validation's actual execution path, this test confirms the simulator
also lists it for an equivalent request — and vice versa for steps gated
out by missing inputs.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools import dry_run as dr
from tools.run_validation import _build_demo_request


_FUNC_RE = re.compile(r"`[\w/]+\.[\w_]+(?:\s*\+\s*[\w_]+)?`")


def _called_functions_in_runner() -> set[str]:
    src = Path(__file__).resolve().parent.parent / "tools" / "run_validation.py"
    text = src.read_text(encoding="utf-8")
    funcs = set()
    if "calculate_ks(" in text:
        funcs.add("metric_ks_auc.calculate_ks")
    if "calculate_auc_gini(" in text:
        funcs.add("metric_ks_auc.calculate_auc_gini")
    if "calculate_psi(" in text:
        funcs.add("metric_psi.calculate_psi")
    if "calibration_test_per_grade(" in text:
        funcs.add("binomial_calibration.calibration_test_per_grade")
    if "check_sample_size(" in text:
        funcs.add("sample_size_guard.check_sample_size")
    if "scan_dataframe(" in text:
        funcs.add("data_safety_guard.scan_dataframe")
    if "check_schema(" in text:
        funcs.add("schema_guard.check_schema")
    if "check_report(" in text:
        funcs.add("output_completeness_guard.check_report")
    if "check_numeric_citations(" in text:
        funcs.add("output_completeness_guard.check_numeric_citations")
    if "check_watermarks(" in text:
        funcs.add("draft_watermark_guard.check_watermarks")
    if "build_validation_report(" in text:
        funcs.add("report_template.build_validation_report")
    return funcs


def _components_in_plan(plan: list[dict]) -> set[str]:
    out: set[str] = set()
    for step in plan:
        for token in re.findall(r"[\w/]+\.[\w_]+", step["component"]):
            tail = "/".join(token.split("/")[-1:])
            out.add(tail)
    return out


def test_runner_functions_appear_in_simulator_plan():
    req = _build_demo_request()
    request_dict = {
        "title": req.title,
        "score_col": req.score_col,
        "target_col": req.target_col,
        "set_col": req.set_col,
        "grade_col": req.grade_col,
        "pd_col": req.pd_col,
    }
    plan = dr.simulate(request_dict)
    plan_funcs = _components_in_plan(plan)
    runner_funcs = _called_functions_in_runner()

    # core mandatory tools
    for required in (
        "metric_ks_auc.calculate_ks",
        "report_template.build_validation_report",
        "output_completeness_guard.check_report",
        "output_completeness_guard.check_numeric_citations",
        "draft_watermark_guard.check_watermarks",
        "schema_guard.check_schema",
        "sample_size_guard.check_sample_size",
    ):
        assert required in runner_funcs, f"runner missing {required}"
        assert required in plan_funcs, f"simulator missing {required}"

    # if calibration is enabled by request, runner should call it
    assert "binomial_calibration.calibration_test_per_grade" in runner_funcs
    assert "binomial_calibration.calibration_test_per_grade" in plan_funcs


def test_plan_skips_calibration_without_grade_pd():
    plan = dr.simulate({"score_col": "score", "target_col": "target"})
    funcs = _components_in_plan(plan)
    assert "binomial_calibration.calibration_test_per_grade" not in funcs
