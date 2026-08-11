import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "permission_matrix.schema.json"
MATRIX_PATH = ROOT / "harness" / "permission_matrix.json"


def test_schema_and_matrix_files_exist():
    assert SCHEMA_PATH.exists()
    assert MATRIX_PATH.exists()


def test_repo_permission_matrix_validates():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(matrix, schema)


def test_schema_rejects_unknown_category():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {
        "matrix_version": "x",
        "patterns": [
            {"category": "made_up_category", "regex": "abc"},
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_schema_requires_regex():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {
        "matrix_version": "x",
        "patterns": [{"category": "ops_db"}],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
