"""실행 로그 (``logs/run.jsonl``) 시계열 분석.

워크플로우가 다회 실행되면 누적 로그가 쌓인다. 본 모듈은 누적 로그를 run
단위로 묶고, 다음을 산출한다:

- **run 단위 KPI**: 총 step / fail / warning / escalation 여부, 시작·종료 시각
- **부문별 fail 빈도**: step_id 별 fail count + fail rate (across runs)
- **dynamic step 발생**: escalation 등 동적으로 활성된 step 의 history
- **시간 trend**: run 별로 fail/warning 수의 추이

run 경계는 ``1.req`` 이벤트가 새 run 의 시작이다 (모든 plan 의 첫 step).

본 모듈은 read-only — 로그를 수정하지 않으며 운영 데이터에 접근하지 않는다.
"""

from __future__ import annotations

import statistics
from datetime import datetime
from pathlib import Path

_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
)


def _parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


def split_runs(records: list[dict]) -> list[list[dict]]:
    """step 이벤트를 run 단위로 분할 — '1.req' 가 새 run 의 시작."""
    runs: list[list[dict]] = []
    current: list[dict] = []
    for rec in records:
        if rec.get("step_id") == "1.req" and current:
            runs.append(current)
            current = []
        current.append(rec)
    if current:
        runs.append(current)
    return runs


def summarise_run(run: list[dict]) -> dict:
    """단일 run 의 KPI 요약."""
    counts: dict[str, int] = {}
    for rec in run:
        ws = rec.get("workflow_status", rec.get("status", "?"))
        counts[ws] = counts.get(ws, 0) + 1
    fails = counts.get("fail", 0)
    warns = counts.get("warning", 0)
    skipped = counts.get("skipped", 0)
    escalated = any(rec.get("dynamic") for rec in run)
    fail_step_ids = [rec.get("step_id") for rec in run
                     if rec.get("workflow_status") == "fail"]
    start_ts = _parse_ts(run[0].get("timestamp", "") if run else "")
    end_ts = _parse_ts(run[-1].get("timestamp", "") if run else "")
    elapsed_sec = None
    if start_ts and end_ts:
        elapsed_sec = (end_ts - start_ts).total_seconds()
    return {
        "n_steps": len(run),
        "counts": counts,
        "fails": fails,
        "warnings": warns,
        "skipped": skipped,
        "escalated": escalated,
        "fail_step_ids": fail_step_ids,
        "started_at": run[0].get("timestamp") if run else None,
        "ended_at": run[-1].get("timestamp") if run else None,
        "elapsed_sec": elapsed_sec,
    }


def step_fail_rates(runs: list[list[dict]]) -> list[dict]:
    """step_id 별 누적 fail count 와 fail rate (across runs).

    분모 = step_id 가 실행된 run 수 (skipped 포함). 분자 = workflow_status=fail
    이 한 번이라도 발생한 run 수.
    """
    if not runs:
        return []
    runs_with_step: dict[str, int] = {}
    fails_per_step: dict[str, int] = {}
    for run in runs:
        in_run = {rec.get("step_id"): rec for rec in run
                  if rec.get("step_id")}
        for sid, rec in in_run.items():
            runs_with_step[sid] = runs_with_step.get(sid, 0) + 1
            if rec.get("workflow_status") == "fail":
                fails_per_step[sid] = fails_per_step.get(sid, 0) + 1
    out = []
    for sid in sorted(runs_with_step):
        n = runs_with_step[sid]
        f = fails_per_step.get(sid, 0)
        out.append({
            "step_id": sid,
            "runs_with_step": n,
            "n_fails": f,
            "fail_rate": (f / n) if n else 0.0,
        })
    out.sort(key=lambda r: -r["fail_rate"])
    return out


def dynamic_activations(runs: list[list[dict]]) -> list[dict]:
    """동적 활성 step (escalation 등) 의 history — run × step."""
    out = []
    for i, run in enumerate(runs):
        for rec in run:
            if rec.get("dynamic"):
                out.append({
                    "run_index": i,
                    "step_id": rec.get("step_id"),
                    "timestamp": rec.get("timestamp"),
                    "status": rec.get("workflow_status"),
                    "detail": rec.get("detail", ""),
                })
    return out


def run_trend(runs: list[list[dict]]) -> list[dict]:
    """run 별 trend — fails/warnings/elapsed."""
    out = []
    for i, run in enumerate(runs):
        s = summarise_run(run)
        out.append({
            "run_index": i,
            "started_at": s["started_at"],
            "n_steps": s["n_steps"],
            "fails": s["fails"],
            "warnings": s["warnings"],
            "escalated": s["escalated"],
            "elapsed_sec": s["elapsed_sec"],
        })
    return out


def elapsed_stats(runs: list[list[dict]]) -> dict:
    """run elapsed 통계 (median/p90/min/max)."""
    elapsed = [s["elapsed_sec"] for s in (summarise_run(r) for r in runs)
               if s["elapsed_sec"] is not None and s["elapsed_sec"] >= 0]
    if not elapsed:
        return {"n": 0}
    sorted_e = sorted(elapsed)
    return {
        "n": len(elapsed),
        "min_sec": min(elapsed),
        "max_sec": max(elapsed),
        "median_sec": statistics.median(elapsed),
        "p90_sec": sorted_e[max(0, int(0.90 * len(sorted_e)) - 1)],
        "mean_sec": statistics.fmean(elapsed),
    }


def analyse_log(log_path: str | Path) -> dict:
    """누적 run.jsonl 의 전체 분석 결과를 dict 로 반환."""
    from middleware.run_logger import collect_step_records

    records = collect_step_records(log_path)
    runs = split_runs(records)
    return {
        "log_path": str(log_path),
        "n_records": len(records),
        "n_runs": len(runs),
        "run_trend": run_trend(runs),
        "step_fail_rates": step_fail_rates(runs),
        "dynamic_activations": dynamic_activations(runs),
        "elapsed_stats": elapsed_stats(runs),
    }


__all__ = [
    "split_runs", "summarise_run", "step_fail_rates",
    "dynamic_activations", "run_trend", "elapsed_stats", "analyse_log",
]
