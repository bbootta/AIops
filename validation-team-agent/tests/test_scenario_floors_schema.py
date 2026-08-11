import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "scenario_floors.schema.json"
DATA_PATH = ROOT / "harness" / "scenario_floors.json"


def test_repo_scenario_floors_validates():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)


def test_schema_requires_three_scenarios():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {"floors": {"base": 1.0, "adverse": 1.2}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_schema_rejects_negative_floor():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {"floors": {"base": -0.5, "adverse": 1.2, "severe": 1.5}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
