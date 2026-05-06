"""실행 로깅.

실행 시작/종료 시각, 입력 파일명, 수행 함수, 주요 결과, 오류 메시지, 생성 파일
목록을 JSON Lines 형태로 logs/에 기록한다. 본 모듈은 운영계와 무관하게
로컬 파일에만 기록한다.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


_DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _ensure_log_dir(log_dir: str | os.PathLike | None) -> Path:
    p = Path(log_dir) if log_dir else _DEFAULT_LOG_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def write_event(
    event: Mapping[str, Any],
    log_dir: str | os.PathLike | None = None,
    log_file: str = "run.jsonl",
) -> Path:
    """단일 이벤트를 JSON Lines로 기록한다."""
    if not isinstance(event, Mapping):
        raise TypeError("event must be a mapping")
    path = _ensure_log_dir(log_dir) / log_file
    record = {"timestamp": _now_iso(), **dict(event)}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return path


@contextmanager
def run_logger(
    function_name: str,
    inputs: Mapping[str, Any] | None = None,
    log_dir: str | os.PathLike | None = None,
    log_file: str = "run.jsonl",
):
    """함수 실행을 시작/종료 이벤트로 감싸 기록한다.

    사용 예:
        with run_logger("calculate_ks", {"input_path": "x.csv"}) as ctx:
            ctx["result_summary"] = {"ks": 0.32}
            ctx["outputs"] = ["reports/ks.md"]
    """
    started = time.perf_counter()
    ctx: dict[str, Any] = {
        "function": function_name,
        "inputs": dict(inputs or {}),
        "result_summary": None,
        "outputs": [],
        "error": None,
    }
    write_event({"event": "start", **ctx}, log_dir=log_dir, log_file=log_file)
    try:
        yield ctx
    except Exception as exc:
        ctx["error"] = {"type": type(exc).__name__, "message": str(exc), "trace": traceback.format_exc()}
        write_event(
            {"event": "error", "duration_sec": round(time.perf_counter() - started, 4), **ctx},
            log_dir=log_dir,
            log_file=log_file,
        )
        raise
    else:
        write_event(
            {"event": "end", "duration_sec": round(time.perf_counter() - started, 4), **ctx},
            log_dir=log_dir,
            log_file=log_file,
        )


def summarize_outputs(paths: Iterable[str | os.PathLike]) -> list[str]:
    """생성된 파일 경로 목록을 문자열 리스트로 정규화한다."""
    return [str(p) for p in paths]
