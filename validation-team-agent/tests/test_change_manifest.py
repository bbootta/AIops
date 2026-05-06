import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "change_manifest.schema.json"
MANIFEST_PATH = ROOT / "harness" / "change_manifest.json"


def test_manifest_files_exist():
    assert SCHEMA_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_manifest_validates_against_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)


def test_manifest_has_initial_entry_and_unique_change_ids():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["manifest_version"]
    assert isinstance(manifest["changes"], list)
    assert len(manifest["changes"]) >= 1
    ids = [c["change_id"] for c in manifest["changes"]]
    assert len(set(ids)) == len(ids)
    for c in manifest["changes"]:
        assert c["change_type"] in {"create", "modify", "delete", "rollback"}
        assert c["status"] in {"proposed", "applied", "validated", "rolled_back"}
