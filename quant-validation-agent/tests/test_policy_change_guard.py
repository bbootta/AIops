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


def test_update_lock_round_trip(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text('{"metrics": {}}', encoding="utf-8")
    lock_path = tmp_path / "policy.lock.json"
    rec = pcg.update_lock(str(fake_policy), "CHG-9100", str(lock_path),
                          approved_at="2026-05-06 10:00:00")
    assert rec["approved_change_id"] == "CHG-9100"
    info = pcg.verify_against_lock(str(fake_policy), str(lock_path))
    assert info["is_synced"] is True
    assert info["lock_present"] is True


def test_update_lock_rejects_invalid_change_id(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    lock_path = tmp_path / "policy.lock.json"
    with pytest.raises(ValueError):
        pcg.update_lock(str(fake_policy), "not-a-valid-id", str(lock_path))


def test_verify_detects_drift(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text('{"metrics": {}}', encoding="utf-8")
    lock_path = tmp_path / "policy.lock.json"
    pcg.update_lock(str(fake_policy), "CHG-9101", str(lock_path))
    # Drift the policy without updating the lock.
    fake_policy.write_text('{"metrics": {"new": {}}}', encoding="utf-8")
    info = pcg.verify_against_lock(str(fake_policy), str(lock_path))
    assert info["is_synced"] is False


def test_assert_synced_raises_when_missing_lock(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    lock_path = tmp_path / "missing.json"
    with pytest.raises(PermissionError):
        pcg.assert_policy_synced_with_lock(str(fake_policy), str(lock_path))


def test_assert_synced_raises_when_drifted(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    lock_path = tmp_path / "policy.lock.json"
    pcg.update_lock(str(fake_policy), "CHG-9102", str(lock_path))
    fake_policy.write_text('{"x": 1}', encoding="utf-8")
    with pytest.raises(PermissionError):
        pcg.assert_policy_synced_with_lock(str(fake_policy), str(lock_path))


def test_assert_synced_passes_when_locked(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    lock_path = tmp_path / "policy.lock.json"
    pcg.update_lock(str(fake_policy), "CHG-9103", str(lock_path))
    pcg.assert_policy_synced_with_lock(str(fake_policy), str(lock_path))


@pytest.mark.skipif(
    not os.environ.get("QVA_STRICT_POLICY_LOCK"),
    reason="Opt-in: requires the lock-file workflow to be in operational use.",
)
def test_lock_references_latest_policy_change_entry():
    """Operations-strict invariant: the on-disk lock points at the most recent
    manifest entry that mutated threshold_policy.json."""
    lock_path = os.path.join(ROOT, "harness", "threshold_policy.lock.json")
    manifest = pcg.load_manifest(MANIFEST_PATH)
    entries = pcg.find_policy_change_entries(manifest)
    assert entries, "no policy-change entries to compare against"
    # By convention the most recently appended entry is the latest approval.
    latest = entries[-1]
    lock = pcg.load_lock(lock_path)
    assert lock, f"no lock at {lock_path}; run update_lock after approval"
    assert lock.get("approved_change_id") == latest.get("change_id"), (
        f"Lock references {lock.get('approved_change_id')} but latest manifest "
        f"policy change is {latest.get('change_id')}."
    )
    info = pcg.verify_against_lock(POLICY_PATH, lock_path)
    assert info["is_synced"] is True
