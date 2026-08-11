"""logs/audit.jsonl retention 도구.

``run_audit append_audit_jsonl`` 이 누적한 시계열 파일을 정책에 따라 정리한다.
- prune: run_ts 가 max_age_days 이상 된 row 제거
- truncate: 마지막 N 개 run_ts 만 보존
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "logs" / "audit.jsonl"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def prune(path: Path | None = None, *, max_age_days: int = 30,
          now: datetime | None = None) -> dict:
    """run_ts 가 max_age_days 이상 된 row 제거."""
    p = path or DEFAULT_PATH
    now = now or datetime.now()
    rows = _read(p)
    kept: list[dict] = []
    removed = 0
    for row in rows:
        ts = _parse_ts(row.get("run_ts", ""))
        if ts is None:
            kept.append(row)  # ts 부재시 보수적으로 보존
            continue
        if (now - ts).days >= max_age_days:
            removed += 1
            continue
        kept.append(row)
    _write(p, kept)
    return {"kept": len(kept), "removed": removed, "path": str(p)}


def truncate(path: Path | None = None, *, keep_last_runs: int = 50) -> dict:
    """마지막 N 개 run_ts 만 보존."""
    p = path or DEFAULT_PATH
    rows = _read(p)
    distinct = []
    seen = set()
    for row in rows:
        ts = row.get("run_ts")
        if ts is not None and ts not in seen:
            distinct.append(ts)
            seen.add(ts)
    if len(distinct) <= keep_last_runs:
        return {"kept": len(rows), "removed": 0, "path": str(p)}
    keep_set = set(distinct[-keep_last_runs:])
    kept = [r for r in rows if r.get("run_ts") in keep_set]
    removed = len(rows) - len(kept)
    _write(p, kept)
    return {"kept": len(kept), "removed": removed, "path": str(p)}


def _cmd_prune(args: argparse.Namespace) -> int:
    json.dump(prune(path=args.path, max_age_days=args.max_age_days),
              sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_truncate(args: argparse.Namespace) -> int:
    json.dump(truncate(path=args.path, keep_last_runs=args.keep_last_runs),
              sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="audit.jsonl retention tool")
    parser.add_argument("--path", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pr = sub.add_parser("prune")
    p_pr.add_argument("--max-age-days", type=int, default=30)
    p_pr.set_defaults(func=_cmd_prune)

    p_tr = sub.add_parser("truncate")
    p_tr.add_argument("--keep-last-runs", type=int, default=50)
    p_tr.set_defaults(func=_cmd_truncate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
