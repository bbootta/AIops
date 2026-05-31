import json
from pathlib import Path

from tools import report_template as rt

GLOSSARY_PATH = (
    Path(__file__).resolve().parent.parent / "harness" / "report_glossary.json"
)


def test_glossary_file_exists_and_loads():
    cfg = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    assert isinstance(cfg["ko_to_en"], dict)
    assert "표본" in cfg["ko_to_en"]


def test_load_glossary_returns_dict():
    g = rt._load_glossary()
    assert isinstance(g, dict)
    assert g.get("표본") == "sample"


def test_translate_uses_loaded_glossary():
    out = rt._translate_en("표본 부족 한계")
    assert "표본 (sample)" in out
    assert "한계 (limitation)" in out


def test_translate_with_custom_glossary():
    out = rt._translate_en("표본 부족", glossary={"표본": "demo"})
    assert "표본 (demo)" in out


def test_load_glossary_fallback_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("tools.report_template._GLOSSARY_PATH", tmp_path / "missing.json")
    g = rt._load_glossary()
    # fallback dict는 한글 도메인 키를 포함해야 한다
    assert "표본" in g
