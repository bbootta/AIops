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


def _rotate_if_needed(path: Path, max_bytes: int | None, backup_count: int) -> None:
    """현재 로그 파일이 max_bytes 초과 시 .1, .2 … 형태로 회전.

    backup_count == 0 이면 회전 없이 truncate. backup_count > 0 이면
    오래된 백업이 backup_count를 넘으면 가장 오래된 것을 삭제한다.
    """
    if max_bytes is None or max_bytes <= 0 or not path.exists():
        return
    if path.stat().st_size < max_bytes:
        return
    if backup_count <= 0:
        path.unlink(missing_ok=True)
        return
    for i in range(backup_count - 1, 0, -1):
        src = path.with_suffix(path.suffix + f".{i}")
        dst = path.with_suffix(path.suffix + f".{i + 1}")
        if src.exists():
            src.replace(dst)
    path.replace(path.with_suffix(path.suffix + ".1"))


def write_event(
    event: Mapping[str, Any],
    log_dir: str | os.PathLike | None = None,
    log_file: str = "run.jsonl",
    max_bytes: int | None = None,
    backup_count: int = 3,
) -> Path:
    """단일 이벤트를 JSON Lines로 기록한다.

    max_bytes가 양수이면 파일이 그 크기를 초과할 때 회전한다.
    """
    if not isinstance(event, Mapping):
        raise TypeError("event must be a mapping")
    path = _ensure_log_dir(log_dir) / log_file
    _rotate_if_needed(path, max_bytes, backup_count)
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
    step_id: str | None = None,
):
    """함수 실행을 시작/종료 이벤트로 감싸 기록한다.

    step_id가 주어지면 ``harness/orchestration_matrix.json``의 step과 매칭되는
    문자열을 함께 기록해 사후에 plan vs actual 비교가 가능하다.

    사용 예:
        with run_logger("calculate_ks", {"input_path": "x.csv"}) as ctx:
            ctx["result_summary"] = {"ks": 0.32}
            ctx["outputs"] = ["reports/ks.md"]
    """
    started = time.perf_counter()
    ctx: dict[str, Any] = {
        "function": function_name,
        "step_id": step_id,
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


def log_step(
    step_id: str,
    *,
    component: str,
    status: str = "executed",
    log_dir: str | os.PathLike | None = None,
    log_file: str = "run.jsonl",
    extra: Mapping[str, Any] | None = None,
) -> Path:
    """단일 step의 실행 흔적을 1라인 이벤트로 기록한다.

    status는 "executed", "skipped", "failed" 중 하나를 사용한다. extra에 추가
    필드를 dict로 전달할 수 있다.
    """
    if status not in {"executed", "skipped", "failed"}:
        raise ValueError(f"unknown step status: {status!r}")
    payload: dict[str, Any] = {
        "event": "step",
        "step_id": step_id,
        "component": component,
        "status": status,
    }
    if extra:
        payload.update(dict(extra))
    return write_event(payload, log_dir=log_dir, log_file=log_file)


def collect_step_ids(log_path: str | os.PathLike) -> list[str]:
    """로그 파일에서 실행된 step_id 목록을 순서대로 수집한다.

    "step" 이벤트 우선이며 없을 경우 run_logger의 start 이벤트 step_id를 사용.
    status가 "skipped"인 step은 제외 — 실제로 수행된 단계만 반환.
    """
    p = Path(log_path)
    if not p.exists():
        return []
    seen: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == "step" and rec.get("step_id"):
            if rec.get("status") == "skipped":
                continue
            seen.append(rec["step_id"])
        elif rec.get("event") == "start" and rec.get("step_id"):
            seen.append(rec["step_id"])
    return seen


def collect_step_records(log_path: str | os.PathLike) -> list[dict]:
    """로그 파일의 'step' 이벤트 raw record를 순서대로 반환한다."""
    p = Path(log_path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == "step":
            out.append(rec)
    return out
