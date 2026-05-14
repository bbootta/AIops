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


def test_component_strings_are_non_trivial():
    """Sanity: each component string is at least 3 chars and free of ascii control chars."""
    manifest = _load_json(MANIFEST_PATH)
    for e in manifest["entries"]:
        component = e.get("component", "")
        cid = e.get("change_id", "?")
        assert isinstance(component, str), f"{cid}: component must be a string"
        assert len(component.strip()) >= 3, f"{cid}: component too short"
        # No control characters (newlines / tabs) should leak into the field.
        bad = [c for c in component if ord(c) < 32 and c not in (" ",)]
        assert not bad, f"{cid}: component contains control characters"


def test_evidence_targeted_fix_present_and_meaningful():
    """Every entry should record a non-empty evidence + targeted_fix."""
    manifest = _load_json(MANIFEST_PATH)
    for e in manifest["entries"]:
        cid = e.get("change_id", "?")
        for field in ("evidence", "targeted_fix", "rollback_rule", "validation_method"):
            value = e.get(field, "")
            assert isinstance(value, str), f"{cid}: {field} must be a string"
            assert len(value.strip()) >= 8, f"{cid}: {field} too short ({len(value)} chars)"


@pytest.mark.skipif(
    not os.environ.get("QVA_STRICT_PROPOSED"),
    reason="Opt-in: enable QVA_STRICT_PROPOSED=1 once ops requires "
           "all policy changes to leave the 'proposed' state.",
)
def test_no_policy_entries_stuck_in_proposed():
    """Strict invariant: every threshold_policy entry should reach 'applied'
    or 'validated' (or be 'rolled_back')."""
    manifest = _load_json(MANIFEST_PATH)
    stuck = [
        e["change_id"] for e in manifest["entries"]
        if "threshold_policy.json" in str(e.get("component", ""))
        and e.get("status") == "proposed"
    ]
    assert not stuck, f"policy change entries left in 'proposed': {stuck}"


def test_change_ids_are_dense_sequence():
    """No gaps in CHG-#### sequence — append-only manifest invariant."""
    manifest = _load_json(MANIFEST_PATH)
    ids = [e["change_id"] for e in manifest["entries"]]
    nums = sorted(int(cid.split("-")[1]) for cid in ids)
    expected = list(range(nums[0], nums[-1] + 1))
    assert nums == expected, f"gaps in CHG-#### sequence: missing {sorted(set(expected) - set(nums))}"


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
