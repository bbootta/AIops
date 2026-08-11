from pathlib import Path

from tools import limitations as lm

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "memory" / "known_limitations.md"


def test_load_returns_categories():
    data = lm.load()
    assert "categories" in data
    assert all("title" in c and "items" in c for c in data["categories"])


def test_render_markdown_includes_section_headers():
    md = lm.render_markdown()
    assert "# Known Limitations" in md
    assert "## 1." in md
    assert "## 5." in md


def test_repo_md_matches_rendered():
    assert lm.render_markdown() == MD_PATH.read_text(encoding="utf-8")


def test_sync_writes_to_custom_path(tmp_path):
    out = tmp_path / "limits.md"
    lm.sync(md_path=out)
    assert out.exists()
    assert "Known Limitations" in out.read_text(encoding="utf-8")
