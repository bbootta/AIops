import json
from pathlib import Path

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
                        "component": "demo/comp",
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
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p


def test_export_csv_contains_header_and_row(tmp_path):
    p = _seed(tmp_path)
    csv_text = m.export_csv(m.load(p))
    lines = csv_text.strip().splitlines()
    assert "change_id" in lines[0]
    assert "CHG-0001" in lines[1]


def test_export_markdown_emits_table(tmp_path):
    p = _seed(tmp_path)
    md = m.export_markdown(m.load(p))
    assert "# Change Manifest Summary" in md
    assert "| CHG-0001 |" in md


def test_main_export_csv_cli(tmp_path, capsys):
    p = _seed(tmp_path)
    rc = m.main(["--manifest", str(p), "export", "--format", "csv"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "CHG-0001" in out


def test_main_export_markdown_cli(tmp_path, capsys):
    p = _seed(tmp_path)
    rc = m.main(["--manifest", str(p), "export", "--format", "markdown"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Change Manifest Summary" in out
