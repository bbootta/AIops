import json

from tools import cli_index


def test_index_lists_core_runners():
    rows = cli_index.build_index()
    modules = {r["module"] for r in rows}
    for required in (
        "tools.run_validation",
        "tools.run_macro_validation",
        "tools.run_ifrs9_validation",
        "tools.manifest",
        "tools.findings",
    ):
        assert required in modules


def test_render_markdown_smoke():
    md = cli_index.render_markdown(cli_index.build_index())
    assert "# CLI Index" in md
    assert "`tools.run_validation`" in md
    assert "|" in md


def test_main_json_emits_array(capsys):
    rc = cli_index.main(["--json"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert rc == 0
    assert isinstance(parsed, list)
    assert all("module" in row for row in parsed)
