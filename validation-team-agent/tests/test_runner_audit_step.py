"""Runner들이 6.audit step을 명시적으로 'skipped'로 기록하는지."""

import json
from pathlib import Path

from middleware.run_logger import collect_step_records


def _audit_record(tmp_path: Path) -> dict:
    for rec in collect_step_records(tmp_path / "run.jsonl"):
        if rec.get("step_id") == "6.audit":
            return rec
    raise AssertionError("6.audit not logged")


def test_run_validation_logs_audit_skip(tmp_path):
    from tools.run_validation import _build_demo_request, run

    run(_build_demo_request(), log_dir=tmp_path)
    rec = _audit_record(tmp_path)
    assert rec["status"] == "skipped"
    assert "human-driven" in rec.get("reason", "")


def test_run_macro_validation_logs_audit_skip(tmp_path):
    from tools.run_macro_validation import _build_demo_request, run

    run(_build_demo_request(), log_dir=tmp_path)
    rec = _audit_record(tmp_path)
    assert rec["status"] == "skipped"


def test_run_ifrs9_validation_logs_audit_skip(tmp_path):
    from tools.run_ifrs9_validation import _build_demo_request, run

    run(_build_demo_request(), log_dir=tmp_path)
    rec = _audit_record(tmp_path)
    assert rec["status"] == "skipped"


def test_run_audit_marks_audit_step_as_skipped(tmp_path):
    from tools.run_audit import audit
    from tools.run_validation import _build_demo_request, run

    run(_build_demo_request(), log_dir=tmp_path)
    rows = audit(tmp_path / "run.jsonl")
    by_id = {r["id"]: r for r in rows}
    assert by_id["6.audit"]["status"] == "skipped"
