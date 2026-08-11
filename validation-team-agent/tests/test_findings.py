import json
from pathlib import Path

import pytest

from tools import findings as fd


def _seed(tmp_path: Path) -> Path:
    p = tmp_path / "recurring_findings.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "findings": [
                    {
                        "id": "RF-001",
                        "frequency": "rare",
                        "domain": "data",
                        "description": "demo",
                        "primary_tool": "tools/x.py",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return p


def test_add_finding_increments_id(tmp_path):
    p = _seed(tmp_path)
    entry = fd.add_finding(
        domain="calibration",
        frequency="moderate",
        description="추가",
        primary_tool="tools/y.py",
        json_path=p,
    )
    assert entry["id"] == "RF-002"
    data = fd.load(p)
    assert len(data["findings"]) == 2


def test_bump_frequency_progresses(tmp_path):
    p = _seed(tmp_path)
    fd.bump_frequency("RF-001", json_path=p)
    fd.bump_frequency("RF-001", json_path=p)
    fd.bump_frequency("RF-001", json_path=p)  # frequent에서 더 진행 안 함
    data = fd.load(p)
    assert data["findings"][0]["frequency"] == "frequent"


def test_bump_unknown_id_raises(tmp_path):
    p = _seed(tmp_path)
    with pytest.raises(KeyError):
        fd.bump_frequency("RF-999", json_path=p)


def test_render_markdown_contains_table_and_warning(tmp_path):
    p = _seed(tmp_path)
    md = fd.render_markdown(fd.load(p))
    assert "| ID |" in md
    assert "자동 생성" in md
    assert "RF-001" in md


def test_repo_json_renders_consistent_with_markdown():
    json_data = fd.load()
    rendered = fd.render_markdown(json_data)
    on_disk = fd.MD_PATH.read_text(encoding="utf-8")
    assert rendered == on_disk
