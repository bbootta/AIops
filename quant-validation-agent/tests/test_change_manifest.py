import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "harness", "change_manifest.schema.json")
MANIFEST_PATH = os.path.join(ROOT, "harness", "change_manifest.json")

jsonschema = pytest.importorskip("jsonschema")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_schema_loads():
    schema = _load_json(SCHEMA_PATH)
    assert schema.get("title") == "Change Manifest Entry"


def test_manifest_loads_and_has_entries():
    manifest = _load_json(MANIFEST_PATH)
    assert "entries" in manifest
    assert isinstance(manifest["entries"], list)
    assert len(manifest["entries"]) >= 1


def test_each_entry_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    manifest = _load_json(MANIFEST_PATH)
    for entry in manifest["entries"]:
        jsonschema.validate(entry, schema)


def test_change_ids_are_unique_and_well_formed():
    manifest = _load_json(MANIFEST_PATH)
    ids = [e["change_id"] for e in manifest["entries"]]
    assert len(ids) == len(set(ids)), f"duplicate change_id in {ids}"
    for cid in ids:
        assert cid.startswith("CHG-")


def test_status_values_allowed():
    manifest = _load_json(MANIFEST_PATH)
    allowed = {"proposed", "applied", "validated", "rolled_back"}
    for e in manifest["entries"]:
        assert e["status"] in allowed


@pytest.mark.skipif(
    not os.environ.get("QVA_STRICT_MANIFEST"),
    reason="Opt-in via QVA_STRICT_MANIFEST=1.",
)
def test_timestamps_are_monotonic_non_decreasing():
    """Operationally-recommended invariant: change entries appended in order.

    Disabled by default — enable by setting QVA_STRICT_MANIFEST=1 once the
    operations team has agreed to enforce it.
    """
    manifest = _load_json(MANIFEST_PATH)
    timestamps = [e["timestamp"] for e in manifest["entries"]]
    assert timestamps == sorted(timestamps), (
        f"Timestamps must be non-decreasing in append order: {timestamps}"
    )
