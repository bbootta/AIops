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
                        "change_id": "CHG-0001",
                        "timestamp": "2026-05-06 00:00:00",
                        "component": "x",
                        "change_type": "create",
                        "evidence": "e",
                        "root_cause": "r",
                        "targeted_fix": "t",
                        "expected_benefit": "b",
                        "expected_regression_risk": "rr",
                        "validation_method": "v",
                        "rollback_rule": "rb",
                        "human_approval_required": True,
                        "status": "proposed",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p


def test_ci_default_runner_blocked(tmp_path, monkeypatch):
    p = _seed(tmp_path)
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("VTA_ALLOW_AUTOMATED_PROMOTE", raising=False)
    with pytest.raises(m.ManifestError) as exc:
        m.promote_if_passing(["CHG-0001"], "applied", confirmed_by_human=True, manifest_path=p)
    assert "CI" in str(exc.value)


def test_ci_with_explicit_allow_proceeds(tmp_path, monkeypatch):
    p = _seed(tmp_path)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("VTA_ALLOW_AUTOMATED_PROMOTE", "1")
    out = m.promote_if_passing(
        ["CHG-0001"],
        "applied",
        confirmed_by_human=True,
        pytest_runner=lambda: (0, "ok"),
        manifest_path=p,
    )
    assert out["promoted"][0]["status"] == "applied"


def test_explicit_pytest_runner_bypasses_ci_guard(tmp_path, monkeypatch):
    p = _seed(tmp_path)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("VTA_ALLOW_AUTOMATED_PROMOTE", raising=False)
    # 명시적 테스트 격리: pytest_runner 인자가 있으면 CI 가드 우회 (round 13 정책).
    out = m.promote_if_passing(
        ["CHG-0001"],
        "applied",
        confirmed_by_human=True,
        pytest_runner=lambda: (0, "ok"),
        manifest_path=p,
    )
    assert out["promoted"][0]["status"] == "applied"


def test_non_ci_environment_proceeds(tmp_path, monkeypatch):
    p = _seed(tmp_path)
    for key in ("CI", "GITHUB_ACTIONS", "GITLAB_CI"):
        monkeypatch.delenv(key, raising=False)
    out = m.promote_if_passing(
        ["CHG-0001"],
        "applied",
        confirmed_by_human=True,
        pytest_runner=lambda: (0, "ok"),
        manifest_path=p,
    )
    assert out["promoted"][0]["status"] == "applied"
