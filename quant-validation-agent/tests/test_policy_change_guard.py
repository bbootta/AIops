import os

import pytest

from middleware import policy_change_guard as pcg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_PATH = os.path.join(ROOT, "harness", "threshold_policy.json")
MANIFEST_PATH = os.path.join(ROOT, "harness", "change_manifest.json")


def test_compute_policy_digest_matches_self():
    digest_a = pcg.compute_policy_digest(POLICY_PATH)
    digest_b = pcg.compute_policy_digest(POLICY_PATH)
    assert digest_a == digest_b
    assert len(digest_a) == 64  # sha256 hex length


def test_compute_policy_digest_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        pcg.compute_policy_digest(str(tmp_path / "missing.json"))


def test_find_policy_change_entries_uses_substring():
    manifest = pcg.load_manifest(MANIFEST_PATH)
    entries = pcg.find_policy_change_entries(manifest)
    # CHG-0007, CHG-0010, CHG-0015 reference threshold_policy.json
    ids = {e["change_id"] for e in entries}
    assert {"CHG-0007", "CHG-0010", "CHG-0015"}.issubset(ids)


def test_policy_governance_status_passes_for_repo():
    manifest = pcg.load_manifest(MANIFEST_PATH)
    status = pcg.policy_governance_status(manifest)
    assert status["n_policy_entries"] >= 3
    assert status["all_require_human_approval"] is True
    assert status["violations"] == []


def test_assert_raises_on_missing_approval():
    bad_manifest = {
        "entries": [
            {
                "change_id": "CHG-9001",
                "component": "harness/threshold_policy.json",
                "human_approval_required": False,
            }
        ]
    }
    with pytest.raises(PermissionError):
        pcg.assert_policy_changes_approved(bad_manifest)


def test_assert_passes_on_approved_only():
    ok_manifest = {
        "entries": [
            {
                "change_id": "CHG-9002",
                "component": "harness/threshold_policy.json",
                "human_approval_required": True,
            }
        ]
    }
    pcg.assert_policy_changes_approved(ok_manifest)


def test_assert_ignores_unrelated_components():
    manifest = {
        "entries": [
            {
                "change_id": "CHG-9003",
                "component": "tools/example.py",
                "human_approval_required": False,
            }
        ]
    }
    pcg.assert_policy_changes_approved(manifest)


def test_real_repo_passes_assertion():
    manifest = pcg.load_manifest(MANIFEST_PATH)
    pcg.assert_policy_changes_approved(manifest)
