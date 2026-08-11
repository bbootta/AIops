import json
from pathlib import Path

from middleware import permission_guard as pg

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "harness" / "permission_matrix.json"


def test_matrix_file_loads_and_has_categories():
    cfg = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    cats = {item["category"] for item in cfg["patterns"]}
    for required in (
        "destructive_fs",
        "force_push",
        "skip_hook",
        "ops_db",
        "external_io",
        "credential_exposure",
    ):
        assert required in cats


def test_load_patterns_returns_pairs_from_file():
    pats = pg.load_patterns()
    assert pats
    for cat, regex in pats:
        assert isinstance(cat, str) and cat
        assert isinstance(regex, str) and regex


def test_load_patterns_falls_back_for_missing_file(tmp_path):
    pats = pg.load_patterns(matrix_path=tmp_path / "nope.json")
    assert pats == pg._FALLBACK_PATTERNS


def test_check_commands_uses_custom_patterns():
    custom = [("custom_cat", r"\bSUPER_BAD\b")]
    out = pg.check_commands(["echo SUPER_BAD now"], patterns=custom)
    assert out["clean"] is False
    assert out["findings"][0]["category"] == "custom_cat"


def test_default_command_check_still_detects_rm_rf():
    out = pg.check_commands(["rm -rf /tmp/foo"])
    assert out["clean"] is False
    assert any(f["category"] == "destructive_fs" for f in out["findings"])
