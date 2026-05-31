import json
from pathlib import Path

import pytest

from tools import runner_result as rr

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "runner_result.schema.json"


def test_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_validate_credit_runner_result(tmp_path):
    pytest.importorskip("jsonschema")
    from tools.run_validation import _build_demo_request, run

    out = run(_build_demo_request(), log_dir=tmp_path)
    rr.validate_result(out)  # 위반 시 예외 발생


def test_validate_macro_runner_result(tmp_path):
    pytest.importorskip("jsonschema")
    from tools.run_macro_validation import _build_demo_request, run

    out = run(_build_demo_request(), log_dir=tmp_path)
    rr.validate_result(out)


def test_validate_ifrs9_runner_result(tmp_path):
    pytest.importorskip("jsonschema")
    from tools.run_ifrs9_validation import _build_demo_request, run

    out = run(_build_demo_request(), log_dir=tmp_path)
    rr.validate_result(out)


def test_validate_rejects_missing_report_md(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    bad = {
        "completeness": {"passed": True},
        "citations": {"passed": True},
        "watermarks": {"passed": True},
    }
    with pytest.raises(jsonschema.ValidationError):
        rr.validate_result(bad)


def test_cli_validates_credit_runner(capsys):
    rc = rr.main(["--runner", "credit"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "schema OK" in out
