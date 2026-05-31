import json
from datetime import datetime, timedelta
from pathlib import Path

from tools import audit_retention as ar


def _seed(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_prune_drops_old_run_ts(tmp_path):
    p = tmp_path / "audit.jsonl"
    now = datetime(2026, 5, 6, 0, 0, 0)
    old = (now - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    new = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    _seed(
        p,
        [
            {"run_ts": old, "id": "1.req", "status": "executed"},
            {"run_ts": new, "id": "1.req", "status": "executed"},
            {"run_ts": new, "id": "4.report", "status": "executed"},
        ],
    )
    res = ar.prune(p, max_age_days=30, now=now)
    assert res["removed"] == 1
    assert res["kept"] == 2


def test_prune_keeps_rows_without_ts(tmp_path):
    p = tmp_path / "audit.jsonl"
    _seed(p, [{"id": "1.req"}])
    res = ar.prune(p, max_age_days=1, now=datetime(2030, 1, 1))
    assert res["removed"] == 0
    assert res["kept"] == 1


def test_truncate_keeps_last_n_runs(tmp_path):
    p = tmp_path / "audit.jsonl"
    rows = []
    for i in range(5):
        ts = f"2026-05-{i+1:02d} 00:00:00"
        rows.append({"run_ts": ts, "id": "1.req", "status": "executed"})
        rows.append({"run_ts": ts, "id": "4.report", "status": "executed"})
    _seed(p, rows)
    res = ar.truncate(p, keep_last_runs=2)
    assert res["kept"] == 4  # 2 runs × 2 rows
    assert res["removed"] == 6


def test_truncate_noop_when_under_limit(tmp_path):
    p = tmp_path / "audit.jsonl"
    rows = [{"run_ts": "2026-05-01 00:00:00", "id": "1.req"}]
    _seed(p, rows)
    res = ar.truncate(p, keep_last_runs=10)
    assert res["removed"] == 0
