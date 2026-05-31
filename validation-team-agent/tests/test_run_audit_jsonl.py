import json

from middleware import run_logger as rl
from tools import run_audit


def test_jsonl_emits_one_object_per_line(tmp_path, capsys):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rl.log_step("4.report", component="y", log_dir=tmp_path)
    rc = run_audit.main(["log", "--log", str(tmp_path / "run.jsonl"), "--jsonl"])
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) >= 5  # 매트릭스 전체 step 수
    parsed = [json.loads(line) for line in out]
    assert all("status" in r for r in parsed)
    # rc는 missing 여부에 따라 0/1
    assert rc in (0, 1)


def test_json_pretty_still_works(tmp_path, capsys):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    run_audit.main(["log", "--log", str(tmp_path / "run.jsonl"), "--json"])
    out = capsys.readouterr().out
    # pretty JSON array 형식
    assert out.lstrip().startswith("[")
    assert "]" in out


def test_jsonl_lines_match_audit_function(tmp_path, capsys):
    rl.log_step("1.req", component="x", log_dir=tmp_path)
    rl.log_step("4.report", component="y", log_dir=tmp_path)
    run_audit.main(["log", "--log", str(tmp_path / "run.jsonl"), "--jsonl"])
    captured = capsys.readouterr().out.strip().splitlines()
    parsed = [json.loads(l) for l in captured]
    direct = run_audit.audit(tmp_path / "run.jsonl")
    assert [r["id"] for r in parsed] == [r["id"] for r in direct]
    assert [r["status"] for r in parsed] == [r["status"] for r in direct]
