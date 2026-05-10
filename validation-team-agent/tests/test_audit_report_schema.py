import json
from pathlib import Path

import pytest

from tools.run_audit import audit
from tools.run_validation import _build_demo_request, run

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "audit_report.schema.json"


def test_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_audit_output_validates_against_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    run(_build_demo_request(), log_dir=tmp_path)
    rows = audit(tmp_path / "run.jsonl")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(rows, schema)


def test_schema_rejects_unknown_status():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = [
        {
            "id": "1.req",
            "name": "x",
            "status": "weird",
            "component": "y",
        }
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_schema_requires_id_pattern():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = [{"id": "no_dot", "name": "x", "status": "executed", "component": "y"}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
