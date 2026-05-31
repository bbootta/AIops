import json
from pathlib import Path

from tools import manifest as m


def _seed(tmp_path: Path) -> Path:
    p = tmp_path / "change_manifest.json"
    p.write_text(
        json.dumps({"manifest_version": "1.0", "changes": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p


def test_from_classification_cli_appends_entry(tmp_path: Path):
    p = _seed(tmp_path)
    rc = m.main([
        "--manifest", str(p),
        "from-classification",
        "--component", "tools/x.py",
        "--type", "create",
        "--evidence", "demo evidence",
        "--expected-benefit", "demo benefit",
        "--expected-regression-risk", "demo risk",
        "--validation-method", "demo validation",
        "--rollback-rule", "demo rollback",
        "--error-text", "PermissionError: Operation not permitted",
    ])
    assert rc == 0
    data = m.load(p)
    assert len(data["changes"]) == 1
    entry = data["changes"][0]
    assert entry["component"] == "tools/x.py"
    assert "permission" in entry["root_cause"]
    assert entry["targeted_fix"]
    assert entry["status"] == "proposed"


def test_from_classification_warns_on_low_confidence(tmp_path: Path, capsys):
    p = _seed(tmp_path)
    rc = m.main([
        "--manifest", str(p),
        "from-classification",
        "--component", "x",
        "--type", "create",
        "--evidence", "e",
        "--expected-benefit", "b",
        "--expected-regression-risk", "r",
        "--validation-method", "v",
        "--rollback-rule", "rr",
        "--error-text", "",  # empty -> low confidence
    ])
    assert rc == 0
    err = capsys.readouterr().err
    assert "low-confidence" in err
