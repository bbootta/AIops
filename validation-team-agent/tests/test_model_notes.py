import json
from pathlib import Path

import pytest

from tools import model_notes as mn

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "memory" / "model_specific_notes.json"
MD_PATH = ROOT / "memory" / "model_specific_notes.md"


def test_json_loads():
    data = mn.load()
    assert "groups" in data
    assert all("title" in g and "notes" in g for g in data["groups"])


def test_render_markdown_contains_group_titles():
    md = mn.render_markdown()
    assert "# Model-Specific Notes" in md
    assert "## 신용평가모형" in md
    assert "## IFRS 9 ECL" in md


def test_repo_md_matches_rendered():
    rendered = mn.render_markdown()
    on_disk = MD_PATH.read_text(encoding="utf-8")
    assert rendered == on_disk


def test_sync_writes_markdown(tmp_path):
    json_src = JSON_PATH
    md_dst = tmp_path / "notes.md"
    mn.sync(json_path=json_src, md_path=md_dst)
    assert md_dst.exists()
    text = md_dst.read_text(encoding="utf-8")
    assert "Model-Specific Notes" in text
