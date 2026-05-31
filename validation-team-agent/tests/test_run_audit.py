from pathlib import Path

from middleware import run_logger as rl
from tools import run_audit


def test_audit_marks_executed_steps(tmp_path: Path):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rl.log_step("4.report", component="y", log_dir=tmp_path)
    rl.log_step("5.complete", component="z", log_dir=tmp_path)
    rows = run_audit.audit(tmp_path / "run.jsonl")
    by_id = {r["id"]: r for r in rows}
    assert by_id["1.req"]["status"] == "executed"
    assert by_id["4.report"]["status"] == "executed"
    assert by_id["5.complete"]["status"] == "executed"


def test_audit_marks_missing_for_always_steps_not_logged(tmp_path: Path):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rows = run_audit.audit(tmp_path / "run.jsonl")
    by_id = {r["id"]: r for r in rows}
    assert by_id["4.report"]["status"] == "missing"
    assert by_id["5.complete"]["status"] == "missing"


def test_audit_marks_skipped_for_gated_steps_not_logged(tmp_path: Path):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rows = run_audit.audit(tmp_path / "run.jsonl")
    by_id = {r["id"]: r for r in rows}
    # 게이트가 닫힌 step (예: 3.macro) → skipped
    assert by_id["3.macro"]["status"] == "skipped"


def test_render_table_contains_status(tmp_path: Path):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rows = run_audit.audit(tmp_path / "run.jsonl")
    md = run_audit.render_table(rows)
    assert "executed" in md
    assert "skipped" in md or "missing" in md


def test_demo_subcommand_runs_and_prints_table(capsys):
    rc = run_audit.main(["demo"])
    captured = capsys.readouterr().out
    assert "executed" in captured
    assert "1.req" in captured
    # 6.audit는 always지만 신용 runner는 manifest 기록 단계를 직접 호출하지
    # 않으므로 missing으로 표시 → rc=1. 그래도 "정상 실행"임을 확인.
    assert rc in (0, 1)
