import json
from pathlib import Path

import pytest

from tools import governance_kpi as gk


def _seed_manifest(tmp_path: Path) -> Path:
    p = tmp_path / "change_manifest.json"
    p.write_text(
        json.dumps(
            {
                "manifest_version": "1.0",
                "changes": [
                    _entry("CHG-0001", "proposed"),
                    _entry("CHG-0002", "applied"),
                    _entry("CHG-0003", "validated"),
                    _entry("CHG-0004", "validated"),
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p


def _entry(cid: str, status: str) -> dict:
    return {
        "change_id": cid,
        "timestamp": "2026-05-06 00:00:00",
        "component": "x",
        "change_type": "create",
        "evidence": "e",
        "root_cause": "rc",
        "targeted_fix": "tf",
        "expected_benefit": "eb",
        "expected_regression_risk": "err",
        "validation_method": "vm",
        "rollback_rule": "rr",
        "human_approval_required": True,
        "status": status,
    }


def test_manifest_kpi_counts(tmp_path):
    p = _seed_manifest(tmp_path)
    out = gk.manifest_kpi(p)
    assert out["available"] is True
    assert out["total"] == 4
    assert out["validated_count"] == 2
    assert out["validated_ratio"] == pytest.approx(0.5)


def test_manifest_kpi_missing_file(tmp_path):
    out = gk.manifest_kpi(tmp_path / "absent.json")
    assert out["available"] is False


def test_feedback_kpi_aggregates(tmp_path):
    fp = tmp_path / "fb.jsonl"
    fp.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"predicted_category": "permission", "confirmed_category": "permission", "agreement": True},
                {"predicted_category": "code", "confirmed_category": "documentation", "agreement": False},
                {"predicted_category": "code", "confirmed_category": "documentation", "agreement": False},
            ]
        ),
        encoding="utf-8",
    )
    out = gk.feedback_kpi(fp)
    assert out["feedback_total"] == 3
    assert out["agreement_count"] == 1
    assert out["agreement_rate"] == pytest.approx(1 / 3)
    assert ("code->documentation", 2) in out["mismatch_top_pairs"]


def test_audit_kpi_latest_run(tmp_path):
    ap = tmp_path / "audit.jsonl"
    ap.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"run_ts": "2026-05-06 00:00:00", "status": "executed"},
                {"run_ts": "2026-05-06 00:00:00", "status": "skipped"},
                {"run_ts": "2026-05-07 00:00:00", "status": "executed"},
                {"run_ts": "2026-05-07 00:00:00", "status": "executed"},
                {"run_ts": "2026-05-07 00:00:00", "status": "missing"},
            ]
        ),
        encoding="utf-8",
    )
    out = gk.audit_kpi(ap)
    assert out["latest_run_ts"] == "2026-05-07 00:00:00"
    assert out["latest_run_executed"] == 2
    assert out["latest_run_missing"] == 1


def test_build_report_returns_subsections():
    report = gk.build_report()
    assert {"manifest", "feedback", "audit", "policy"} <= set(report)


def test_render_markdown_smoke():
    md = gk.render_markdown(gk.build_report())
    assert "# Governance KPI Report" in md
    assert "Change Manifest" in md


def test_cli_report_runs(capsys):
    rc = gk.main(["report"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Governance KPI Report" in out
