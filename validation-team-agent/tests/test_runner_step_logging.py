"""Runner 들이 log_step으로 매트릭스 step_id를 기록하는지 확인."""

import json
from pathlib import Path

from middleware.run_logger import collect_step_ids


def _step_ids(tmp_path: Path) -> list[str]:
    return collect_step_ids(tmp_path / "run.jsonl")


def test_run_validation_logs_core_steps(tmp_path):
    from tools.run_validation import _build_demo_request, run

    req = _build_demo_request()
    run(req, log_dir=tmp_path)
    ids = _step_ids(tmp_path)
    for required in ("1.req", "2.schema", "2.safety", "2.sample", "3.disc",
                     "3.psi", "3.cal", "4.report", "5.complete", "5.cite", "5.watermark"):
        assert required in ids, f"{required} missing from runner log: {ids}"


def test_run_macro_validation_logs_macro_step(tmp_path):
    from tools.run_macro_validation import _build_demo_request, run

    req = _build_demo_request()
    run(req, log_dir=tmp_path)
    ids = _step_ids(tmp_path)
    assert "3.macro" in ids
    for required in ("1.req", "2.schema", "4.report", "5.complete", "5.cite", "5.watermark"):
        assert required in ids


def test_run_ifrs9_validation_logs_weights(tmp_path):
    from tools.run_ifrs9_validation import _build_demo_request, run

    req = _build_demo_request()
    run(req, log_dir=tmp_path)
    ids = _step_ids(tmp_path)
    for required in ("1.req", "3.weights", "4.report", "5.complete",
                     "5.cite", "5.watermark"):
        assert required in ids
