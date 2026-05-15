from pathlib import Path

import pytest

from tools import runner_result as rr

ROOT = Path(__file__).resolve().parent.parent


def test_sub_schema_files_exist():
    for runner in ("credit", "macro", "ifrs9"):
        assert rr.SUB_SCHEMA_PATHS[runner].exists()


def test_credit_subschema_validates(tmp_path):
    pytest.importorskip("jsonschema")
    from tools.run_validation import _build_demo_request, run

    out = run(_build_demo_request(), log_dir=tmp_path)
    rr.validate_result_subschema(out, "credit")


def test_macro_subschema_validates(tmp_path):
    pytest.importorskip("jsonschema")
    from tools.run_macro_validation import _build_demo_request, run

    out = run(_build_demo_request(), log_dir=tmp_path)
    rr.validate_result_subschema(out, "macro")


def test_ifrs9_subschema_validates(tmp_path):
    pytest.importorskip("jsonschema")
    from tools.run_ifrs9_validation import _build_demo_request, run

    out = run(_build_demo_request(), log_dir=tmp_path)
    rr.validate_result_subschema(out, "ifrs9")


def test_unknown_runner_rejected():
    with pytest.raises(ValueError):
        rr.load_sub_schema("other")
