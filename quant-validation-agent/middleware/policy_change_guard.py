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
