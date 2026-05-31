import json
from pathlib import Path

from tools import dry_run_diff as drd


def _write_matrix(path: Path, steps: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {"matrix_version": "test", "steps": steps},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _step(sid: str, name: str = "n") -> dict:
    return {
        "id": sid,
        "name": name,
        "component": "comp",
        "rationale": "r",
        "always": True,
    }


def test_no_changes(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    steps = [_step("1.req"), _step("4.report")]
    _write_matrix(a, steps)
    _write_matrix(b, steps)
    diff = drd.diff_plans(a, b, request={})
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["reordered"] == []


def test_added_and_removed_steps(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_matrix(a, [_step("1.req"), _step("4.report")])
    _write_matrix(b, [_step("1.req"), _step("3.disc"), _step("5.complete")])
    diff = drd.diff_plans(a, b, request={})
    assert "3.disc" in diff["added"]
    assert "5.complete" in diff["added"]
    assert "4.report" in diff["removed"]


def test_reorder_detected(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_matrix(a, [_step("1.req"), _step("4.report"), _step("5.complete")])
    _write_matrix(b, [_step("1.req"), _step("5.complete"), _step("4.report")])
    diff = drd.diff_plans(a, b, request={})
    reordered_ids = {x[0] for x in diff["reordered"]}
    assert "5.complete" in reordered_ids
    assert "4.report" in reordered_ids


def test_render_markdown_smoke(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_matrix(a, [_step("1.req")])
    _write_matrix(b, [_step("1.req"), _step("9.new")])
    diff = drd.diff_plans(a, b, request={})
    md = drd.render_markdown(diff)
    assert "# Orchestration Plan Diff" in md
    assert "9.new" in md


def test_main_returns_nonzero_on_diff(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_matrix(a, [_step("1.req")])
    _write_matrix(b, [_step("1.req"), _step("9.new")])
    rc = drd.main(["--before", str(a), "--after", str(b), "--json"])
    assert rc == 1


def test_main_returns_zero_when_identical(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_matrix(a, [_step("1.req")])
    _write_matrix(b, [_step("1.req")])
    rc = drd.main(["--before", str(a), "--after", str(b), "--json"])
    assert rc == 0
