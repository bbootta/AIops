import json
from pathlib import Path

from middleware import run_logger as rl


def _write_n_events(n: int, log_dir: Path, **kwargs) -> Path:
    last = None
    for i in range(n):
        last = rl.write_event({"i": i, "payload": "x" * 200}, log_dir=log_dir, **kwargs)
    return last


def test_no_rotation_by_default(tmp_path: Path):
    _write_n_events(50, tmp_path)
    assert (tmp_path / "run.jsonl").exists()
    assert not list(tmp_path.glob("run.jsonl.*"))


def test_rotation_creates_backup_when_size_exceeded(tmp_path: Path):
    _write_n_events(20, tmp_path, max_bytes=300, backup_count=3)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert "run.jsonl" in files
    assert any(name.startswith("run.jsonl.") for name in files)


def test_rotation_caps_backup_count(tmp_path: Path):
    _write_n_events(60, tmp_path, max_bytes=200, backup_count=2)
    backups = [p for p in tmp_path.iterdir() if p.name.startswith("run.jsonl.")]
    assert len(backups) <= 2


def test_rotation_truncate_when_backup_count_zero(tmp_path: Path):
    _write_n_events(10, tmp_path, max_bytes=200, backup_count=0)
    backups = [p for p in tmp_path.iterdir() if p.name.startswith("run.jsonl.")]
    assert backups == []
    # last write should still be present after truncation
    content = (tmp_path / "run.jsonl").read_text(encoding="utf-8")
    assert content.strip()


def test_run_logger_context_writes_start_and_end(tmp_path: Path):
    with rl.run_logger("demo_fn", inputs={"k": 1}, log_dir=tmp_path) as ctx:
        ctx["result_summary"] = {"ok": True}
    lines = [json.loads(l) for l in (tmp_path / "run.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    events = {l["event"] for l in lines}
    assert events == {"start", "end"}
