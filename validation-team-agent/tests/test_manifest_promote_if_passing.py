import json
from pathlib import Path

import pytest

from tools import manifest as m


def _seed(tmp_path: Path) -> Path:
    p = tmp_path / "change_manifest.json"
    p.write_text(
        json.dumps(
            {
                "manifest_version": "1.0",
                "changes": [
                    {
                        "change_id": cid,
                        "timestamp": "2026-05-06 00:00:00",
                        "component": f"comp-{cid}",
                        "change_type": "create",
                        "evidence": "ev",
                        "root_cause": "rc",
                        "targeted_fix": "tf",
                        "expected_benefit": "eb",
                        "expected_regression_risk": "err",
                        "validation_method": "vm",
                        "rollback_rule": "rr",
                        "human_approval_required": True,
                        "status": "proposed",
                    }
                    for cid in ("CHG-0001", "CHG-0002")
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return p


def test_blocked_without_human_flag(tmp_path):
    p = _seed(tmp_path)
    with pytest.raises(m.ManifestError):
        m.promote_if_passing(["CHG-0001"], "applied", confirmed_by_human=False, manifest_path=p)


def test_blocked_when_pytest_fails(tmp_path):
    p = _seed(tmp_path)
    with pytest.raises(m.ManifestError):
        m.promote_if_passing(
            ["CHG-0001"],
            "applied",
            confirmed_by_human=True,
            pytest_runner=lambda: (1, "pytest output"),
            manifest_path=p,
        )


def test_promotes_multiple_when_pytest_passes(tmp_path):
    p = _seed(tmp_path)
    out = m.promote_if_passing(
        ["CHG-0001", "CHG-0002"],
        "applied",
        confirmed_by_human=True,
        pytest_runner=lambda: (0, "all good"),
        manifest_path=p,
    )
    assert out["pytest_returncode"] == 0
    assert {e["change_id"] for e in out["promoted"]} == {"CHG-0001", "CHG-0002"}
    refreshed = m.load(p)
    assert all(c["status"] == "applied" for c in refreshed["changes"])


def test_rejects_invalid_target_status(tmp_path):
    p = _seed(tmp_path)
    with pytest.raises(m.ManifestError):
        m.promote_if_passing(
            ["CHG-0001"],
            "rolled_back",
            confirmed_by_human=True,
            pytest_runner=lambda: (0, ""),
            manifest_path=p,
        )
