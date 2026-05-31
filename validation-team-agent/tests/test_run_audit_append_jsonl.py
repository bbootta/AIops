import json
from pathlib import Path

from middleware import run_logger as rl
from tools import run_audit


def test_append_audit_jsonl_writes_run_ts(tmp_path):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rows = run_audit.audit(tmp_path / "run.jsonl")
    out = tmp_path / "audit.jsonl"
    run_audit.append_audit_jsonl(rows, path=out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines
    payload = json.loads(lines[0])
    assert "run_ts" in payload
    assert "status" in payload


def test_append_audit_jsonl_accumulates_across_runs(tmp_path):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rows = run_audit.audit(tmp_path / "run.jsonl")
    out = tmp_path / "audit.jsonl"
    run_audit.append_audit_jsonl(rows, path=out)
    n_first = len(out.read_text(encoding="utf-8").splitlines())
    run_audit.append_audit_jsonl(rows, path=out)
    n_second = len(out.read_text(encoding="utf-8").splitlines())
    assert n_second == 2 * n_first


def test_demo_subcommand_writes_to_custom_path(tmp_path, capsys):
    out = tmp_path / "demo_audit.jsonl"
    rc = run_audit.main(["demo", "--append-jsonl", str(out)])
    captured = capsys.readouterr().out
    assert "executed" in captured
    assert out.exists()
    assert out.read_text(encoding="utf-8").strip()
    assert rc in (0, 1)
