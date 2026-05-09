"""Policy-change governance guard.

Verifies that any modification of `harness/threshold_policy.json` is
matched by a corresponding `change_manifest.json` entry whose
`human_approval_required` is true.

This is a CI-style audit helper. It does NOT mutate files.

Two layers are provided:
1. `find_policy_change_entries(manifest, component_substr)` — list relevant
   manifest entries.
2. `assert_policy_changes_approved(manifest, ...)` — raise PermissionError
   if any policy-change entry lacks `human_approval_required: true`.

A digest helper is included for future lock-file workflows; it is not
mandatory for the assertion.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Iterable, List

DEFAULT_POLICY_COMPONENT_SUBSTRING = "threshold_policy.json"


def compute_policy_digest(policy_path: str) -> str:
    """SHA-256 hex digest of the policy file's bytes."""
    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Policy not found: {policy_path}")
    with open(policy_path, "rb") as f:
        data = f.read()
    return hashlib.sha256(data).hexdigest()


def find_policy_change_entries(
    manifest: dict,
    component_substr: str = DEFAULT_POLICY_COMPONENT_SUBSTRING,
) -> List[dict]:
    """Return manifest entries whose `component` contains `component_substr`."""
    entries = (manifest or {}).get("entries", []) or []
    out = []
    for e in entries:
        comp = str(e.get("component", ""))
        if component_substr in comp:
            out.append(e)
    return out


def policy_governance_status(
    manifest: dict,
    component_substr: str = DEFAULT_POLICY_COMPONENT_SUBSTRING,
) -> dict:
    """Summarize policy-change governance from a manifest dict.

    Returns:
        {
            "n_policy_entries": int,
            "all_require_human_approval": bool,
            "violations": [<entries that lack human_approval_required>],
        }
    """
    entries = find_policy_change_entries(manifest, component_substr)
    violations = [
        e for e in entries
        if not bool(e.get("human_approval_required"))
    ]
    return {
        "n_policy_entries": len(entries),
        "all_require_human_approval": len(violations) == 0,
        "violations": violations,
    }


def assert_policy_changes_approved(
    manifest: dict,
    component_substr: str = DEFAULT_POLICY_COMPONENT_SUBSTRING,
) -> None:
    """Raise PermissionError if any policy entry lacks human approval.

    This is the canonical guard for CI: every change touching
    `threshold_policy.json` must be tagged with
    `human_approval_required: true`.
    """
    status = policy_governance_status(manifest, component_substr)
    if not status["all_require_human_approval"]:
        ids = [v.get("change_id", "?") for v in status["violations"]]
        raise PermissionError(
            f"Policy change entries without human_approval_required=true: {ids}"
        )


def load_manifest(manifest_path: str) -> dict:
    """Convenience JSON loader."""
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Lock-file workflow
#
# A lock file pins the last *approved* policy digest along with the change_id
# that approved it. The flow is:
#   1. Reviewer approves a manifest entry that mutates threshold_policy.json
#      (human_approval_required: true).
#   2. After applying the change, an authorized actor calls update_lock to
#      record the new digest + change_id + timestamp.
#   3. CI (or a pre-flight check) calls verify_against_lock to confirm the
#      live policy digest matches the lock. A mismatch blocks usage until
#      the lock is updated through the approved flow.
# ---------------------------------------------------------------------------

import datetime as _dt


def update_lock(
    policy_path: str,
    change_id: str,
    lock_path: str,
    approved_at: str | None = None,
) -> dict:
    """Write the lock-file pinning the current policy digest to a change_id.

    The caller is responsible for ensuring the change is actually approved;
    this helper does not re-validate that. It is intended to be invoked by
    an authorized actor after manifest approval.
    """
    if not change_id or not str(change_id).startswith("CHG-"):
        raise ValueError("change_id must be of the form 'CHG-####'.")
    digest = compute_policy_digest(policy_path)
    record = {
        "policy_path": os.path.abspath(policy_path),
        "policy_digest": digest,
        "approved_change_id": change_id,
        "approved_at": approved_at or _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    parent = os.path.dirname(os.path.abspath(lock_path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def load_lock(lock_path: str) -> dict:
    """Read a lock-file. Returns an empty dict if missing."""
    if not os.path.exists(lock_path):
        return {}
    with open(lock_path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_against_lock(policy_path: str, lock_path: str) -> dict:
    """Compare the live policy digest against the recorded lock digest.

    Returns:
        {
            "current_digest": <hex>,
            "lock_digest": <hex|None>,
            "approved_change_id": <str|None>,
            "is_synced": bool,        # True only when digests match exactly
            "lock_present": bool,
        }
    """
    current = compute_policy_digest(policy_path)
    lock = load_lock(lock_path)
    lock_digest = lock.get("policy_digest")
    return {
        "current_digest": current,
        "lock_digest": lock_digest,
        "approved_change_id": lock.get("approved_change_id"),
        "approved_at": lock.get("approved_at"),
        "is_synced": bool(lock_digest) and lock_digest == current,
        "lock_present": bool(lock),
    }


def assert_policy_synced_with_lock(policy_path: str, lock_path: str) -> None:
    """Raise PermissionError when the live policy diverges from the lock."""
    info = verify_against_lock(policy_path, lock_path)
    if not info["lock_present"]:
        raise PermissionError(
            f"No policy lock found at {lock_path}. Approve the policy and run update_lock first."
        )
    if not info["is_synced"]:
        raise PermissionError(
            "Policy digest does not match lock. "
            f"current={info['current_digest']}, lock={info['lock_digest']}, "
            f"approved_change_id={info['approved_change_id']}."
        )
