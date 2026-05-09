import json
from pathlib import Path

import pytest

from middleware import run_logger as rl


def test_log_step_writes_entry(tmp_path: Path):
    rl.log_step("3.disc", component="metric_ks_auc.calculate_ks", log_dir=tmp_path)
    rec = [
        json.loads(l)
        for l in (tmp_path / "run.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert len(rec) == 1
    assert rec[0]["event"] == "step"
    assert rec[0]["step_id"] == "3.disc"
    assert rec[0]["status"] == "executed"
    assert rec[0]["component"] == "metric_ks_auc.calculate_ks"


def test_log_step_supports_skipped_and_failed(tmp_path: Path):
    rl.log_step("3.psi", component="metric_psi.calculate_psi",
                status="skipped", log_dir=tmp_path)
    rl.log_step("4.report", component="report_template.build_validation_report",
                status="failed", log_dir=tmp_path,
                extra={"error_type": "ValueError"})
    rec = [
        json.loads(l)
        for l in (tmp_path / "run.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert {r["status"] for r in rec} == {"skipped", "failed"}
    assert rec[1]["error_type"] == "ValueError"


def test_log_step_rejects_unknown_status(tmp_path):
    with pytest.raises(ValueError):
        rl.log_step("x", component="y", status="other", log_dir=tmp_path)


def test_run_logger_records_step_id(tmp_path):
    with rl.run_logger("my_fn", inputs={"k": 1}, log_dir=tmp_path, step_id="3.disc"):
        pass
    rec = [
        json.loads(l)
        for l in (tmp_path / "run.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert all(r["step_id"] == "3.disc" for r in rec)


def test_collect_step_ids_returns_order(tmp_path):
    rl.log_step("1.req", component="a", log_dir=tmp_path)
    rl.log_step("2.schema", component="b", log_dir=tmp_path)
    with rl.run_logger("fn", log_dir=tmp_path, step_id="3.disc"):
        pass
    ids = rl.collect_step_ids(tmp_path / "run.jsonl")
    assert ids[0] == "1.req"
    assert ids[1] == "2.schema"
    assert "3.disc" in ids


def test_collect_step_ids_handles_missing_file(tmp_path):
    assert rl.collect_step_ids(tmp_path / "absent.jsonl") == []
