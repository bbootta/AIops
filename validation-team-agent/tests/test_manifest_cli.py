import json
from pathlib import Path

import pytest

from tools import manifest as m

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_SRC = ROOT / "harness" / "change_manifest.schema.json"


def _seed_manifest(tmp_path: Path) -> Path:
    """초기 manifest 1건을 갖는 임시 파일 경로를 만든다."""
    p = tmp_path / "change_manifest.json"
    p.write_text(
        json.dumps(
            {
                "manifest_version": "1.0",
                "changes": [
                    {
                        "change_id": "CHG-0001",
                        "timestamp": "2026-05-06 00:00:00",
                        "component": "demo/component",
                        "change_type": "create",
                        "evidence": "demo",
                        "root_cause": "demo",
                        "targeted_fix": "demo",
                        "expected_benefit": "demo",
                        "expected_regression_risk": "demo",
                        "validation_method": "demo",
                        "rollback_rule": "demo",
                        "human_approval_required": True,
                        "status": "proposed",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return p


def test_validate_passes_for_seed(tmp_path):
    p = _seed_manifest(tmp_path)
    m.validate(manifest=m.load(p))


def test_promote_proposed_to_applied(tmp_path):
    p = _seed_manifest(tmp_path)
    out = m.promote("CHG-0001", "applied", manifest_path=p)
    assert out["status"] == "applied"
    refreshed = m.load(p)
    assert refreshed["changes"][0]["status"] == "applied"


def test_promote_skip_state_is_blocked(tmp_path):
    p = _seed_manifest(tmp_path)
    with pytest.raises(m.ManifestError):
        m.promote("CHG-0001", "validated", manifest_path=p)


def test_promote_validated_is_terminal(tmp_path):
    p = _seed_manifest(tmp_path)
    m.promote("CHG-0001", "applied", manifest_path=p)
    m.promote("CHG-0001", "validated", manifest_path=p)
    with pytest.raises(m.ManifestError):
        m.promote("CHG-0001", "applied", manifest_path=p)


def test_promote_unknown_id_raises(tmp_path):
    p = _seed_manifest(tmp_path)
    with pytest.raises(m.ManifestError):
        m.promote("CHG-9999", "applied", manifest_path=p)


def test_add_change_increments_id(tmp_path):
    p = _seed_manifest(tmp_path)
    entry = m.add_change(
        component="tools/foo.py",
        change_type="create",
        evidence="ev",
        root_cause="rc",
        targeted_fix="tf",
        expected_benefit="eb",
        expected_regression_risk="err",
        validation_method="vm",
        rollback_rule="rr",
        manifest_path=p,
    )
    assert entry["change_id"] == "CHG-0002"
    assert entry["status"] == "proposed"


def test_repo_manifest_is_valid():
    """Real manifest in the repo must validate against schema."""
    m.validate()
