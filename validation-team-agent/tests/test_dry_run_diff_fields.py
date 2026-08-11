import json
from pathlib import Path

from tools import dry_run_diff as drd


def _write(path: Path, steps: list[dict]) -> None:
    path.write_text(
        json.dumps({"matrix_version": "t", "steps": steps}, ensure_ascii=False),
        encoding="utf-8",
    )


def _step(sid: str, **overrides) -> dict:
    base = {
        "id": sid,
        "name": sid,
        "component": "comp.a",
        "rationale": "rationale.a",
        "always": True,
    }
    base.update(overrides)
    return base


def test_detects_component_change(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _write(a, [_step("1.req", component="comp.old")])
    _write(b, [_step("1.req", component="comp.new")])
    diff = drd.diff_plans(a, b, request={})
    fields = {(c["id"], c["field"]) for c in diff["field_changes"]}
    assert ("1.req", "component") in fields


def test_detects_expected_outputs_change(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _write(a, [_step("4.report", expected_outputs=["report_md"])])
    _write(b, [_step("4.report", expected_outputs=["report_md", "extra"])])
    diff = drd.diff_plans(a, b, request={})
    assert any(
        c["id"] == "4.report" and c["field"] == "expected_outputs"
        for c in diff["field_changes"]
    )


def test_render_markdown_lists_field_changes(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _write(a, [_step("1.req", rationale="old reason")])
    _write(b, [_step("1.req", rationale="new reason")])
    diff = drd.diff_plans(a, b, request={})
    md = drd.render_markdown(diff)
    assert "Field Changes" in md
    assert "rationale" in md


def test_main_returns_nonzero_for_field_only_change(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _write(a, [_step("1.req", component="x")])
    _write(b, [_step("1.req", component="y")])
    rc = drd.main(["--before", str(a), "--after", str(b), "--json"])
    assert rc == 1
