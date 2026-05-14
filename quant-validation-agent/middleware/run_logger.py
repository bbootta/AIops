"""Run logger that writes execution metadata to logs/."""
from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Optional

LOG_DIR_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

_counter = 0


def _now_str() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _next_counter() -> int:
    global _counter
    _counter = (_counter + 1) % 1_000_000
    return _counter


def write_run_log(
    request_summary: str,
    inputs: list,
    functions_used: list,
    main_results: dict,
    errors: Optional[list] = None,
    artifacts: Optional[list] = None,
    test_results: Optional[dict] = None,
    incomplete_items: Optional[list] = None,
    log_dir: Optional[str] = None,
) -> str:
    """Write a run record to logs/ as JSON. Returns the file path."""
    log_dir = log_dir or LOG_DIR_DEFAULT
    os.makedirs(log_dir, exist_ok=True)
    record = {
        "timestamp": _now_str(),
        "request_summary": request_summary,
        "inputs": inputs or [],
        "functions_used": functions_used or [],
        "main_results": main_results or {},
        "errors": errors or [],
        "artifacts": artifacts or [],
        "test_results": test_results or {},
        "incomplete_items": incomplete_items or [],
    }
    # Include the PID + a monotonically increasing counter to keep filenames
    # unique under concurrent invocations (timestamp_us alone is insufficient
    # when two processes start in the same microsecond).
    counter = _next_counter()
    fname = (
        "run_"
        + _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        + f"_pid{os.getpid()}_{counter:06d}.json"
    )
    path = os.path.join(log_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=str)
    return path
