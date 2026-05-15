"""classify_feedback.jsonl retention 정책 도구.

학습 시그널이 누적되면 운영 환경 정보의 흔적이 길어진다. 본 도구는 다음 두 가지를
제공한다.

1. ``prune`` — 지정 일수 이상 된 항목을 삭제 (또는 별도 파일로 격리)
2. ``anonymize`` — text/notes 필드를 길이 + sha256 prefix 로 치환

본 도구는 자동 실행되지 않는다. 운영자가 명시적으로 호출한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "memory" / "classify_feedback.jsonl"


def _read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _write_records(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _anonymize_text(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"<{len(text)}c#{digest}>"


def prune(
    path: Path | None = None,
    *,
    max_age_days: int = 90,
    now_epoch: float | None = None,
) -> dict:
    """현재 시각 기준 max_age_days 이상 된 항목을 제거한다.

    각 record에 ``recorded_at`` epoch 필드가 없으면 보존 (제거 안 함). 호출자가
    record 작성 시 ``recorded_at`` 을 채워두는 것이 권장.

    반환 dict 키: kept, removed, path
    """
    p = path or DEFAULT_PATH
    now = now_epoch if now_epoch is not None else time.time()
    cutoff = now - max_age_days * 86400.0
    records = _read_records(p)
    kept: list[dict] = []
    removed = 0
    for rec in records:
        ts = rec.get("recorded_at")
        if isinstance(ts, (int, float)) and ts < cutoff:
            removed += 1
            continue
        kept.append(rec)
    _write_records(p, kept)
    return {"kept": len(kept), "removed": removed, "path": str(p)}


def anonymize(path: Path | None = None) -> dict:
    """모든 record의 text/notes 필드를 hash placeholder로 치환한다."""
    p = path or DEFAULT_PATH
    records = _read_records(p)
    n_changed = 0
    for rec in records:
        for key in ("text", "notes"):
            val = rec.get(key)
            if isinstance(val, str) and val and not val.startswith("<") and "#" not in val[:2]:
                rec[key] = _anonymize_text(val)
                n_changed += 1
    _write_records(p, records)
    return {"records": len(records), "fields_anonymized": n_changed, "path": str(p)}


def _cmd_prune(args: argparse.Namespace) -> int:
    res = prune(path=args.path, max_age_days=args.max_age_days)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_anonymize(args: argparse.Namespace) -> int:
    res = anonymize(path=args.path)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="classify_feedback.jsonl retention tools")
    parser.add_argument("--path", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pr = sub.add_parser("prune", help="recorded_at 기준 오래된 record 제거")
    p_pr.add_argument("--max-age-days", type=int, default=90)
    p_pr.set_defaults(func=_cmd_prune)

    p_an = sub.add_parser("anonymize", help="text/notes를 sha256 placeholder로 치환")
    p_an.set_defaults(func=_cmd_anonymize)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
