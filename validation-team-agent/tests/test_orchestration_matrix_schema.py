import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "orchestration_matrix.schema.json"
MATRIX_PATH = ROOT / "harness" / "orchestration_matrix.json"


def test_matrix_validates_against_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(matrix, schema)


def test_schema_rejects_step_without_gate():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {
        "matrix_version": "x",
        "steps": [
            {
                "id": "1.req",
                "name": "x",
                "component": "y",
                "rationale": "z",
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_every_step_has_expected_outputs():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    for step in matrix["steps"]:
        assert "expected_outputs" in step, f"missing expected_outputs in {step['id']}"
        assert isinstance(step["expected_outputs"], list)
        assert step["expected_outputs"], f"empty expected_outputs in {step['id']}"
