"""Workflow / handler 성능 측정.

각 step 의 wall-clock 시간을 측정해 어느 부문이 병목인지 식별한다. 운영 데이터
없이 합성 샘플로만 동작하며 외부 호출이 없다.

사용:
    from tools.benchmark import benchmark_workflow
    report = benchmark_workflow(n_rows=100_000)

CLI:
    python -m tools.benchmark --n 100000 --stress
    python -m tools.benchmark --n 10000 --runs 5  # 평균 + p95
"""

from __future__ import annotations

import argparse
import json
import statistics as stats
import sys
import time
from pathlib import Path
from typing import Any, Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _build_request(n_rows: int, *, stress: bool, seed: int) -> dict:
    from tools.run_workflow_demo import build_request

    return build_request(n_rows, stress=stress, seed=seed)


def benchmark_workflow(
    n_rows: int = 100_000,
    *,
    runs: int = 1,
    stress: bool = False,
    seed: int = 42,
    log_dir: Path | None = None,
) -> dict:
    """워크플로우를 runs 회 실행해 총 시간 / step 별 시간을 통계로 산출."""
    from tools.handlers import register_default_handlers
    from tools.workflow import WorkflowEngine

    log_dir = log_dir or Path("logs/bench")
    log_dir.mkdir(parents=True, exist_ok=True)

    request = _build_request(n_rows, stress=stress, seed=seed)
    total_times: list[float] = []
    per_step: dict[str, list[float]] = {}

    for r in range(runs):
        eng = WorkflowEngine()
        register_default_handlers(eng)

        # 각 handler 를 timing 으로 감싼다
        timings: dict[str, float] = {}
        original = eng._handlers.copy()  # noqa: SLF001

        def _wrap(sid: str, fn):
            def inner(req, ctx):
                t0 = time.perf_counter()
                try:
                    return fn(req, ctx)
                finally:
                    timings[sid] = time.perf_counter() - t0
            return inner

        eng._handlers = {sid: _wrap(sid, fn) for sid, fn in original.items()}  # noqa: SLF001

        t0 = time.perf_counter()
        run = eng.run(request, log_dir=log_dir)
        total_times.append(time.perf_counter() - t0)

        for sid, t in timings.items():
            per_step.setdefault(sid, []).append(t)

    return {
        "n_rows": n_rows,
        "stress": stress,
        "runs": runs,
        "executed_steps": len(run.executed_order),
        "total": _summarise(total_times),
        "per_step": {sid: _summarise(times) for sid, times in per_step.items()},
        "top5_slowest_mean": _top_n(per_step, 5),
    }


def _summarise(values: Iterable[float]) -> dict:
    arr = list(values)
    if not arr:
        return {"n": 0}
    sorted_arr = sorted(arr)
    return {
        "n": len(arr),
        "mean_ms": round(stats.fmean(arr) * 1000, 3),
        "min_ms": round(min(arr) * 1000, 3),
        "max_ms": round(max(arr) * 1000, 3),
        "p95_ms": round(
            sorted_arr[max(0, int(0.95 * len(sorted_arr)) - 1)] * 1000, 3
        ),
    }


def _top_n(per_step: dict[str, list[float]], n: int) -> list[dict]:
    means = [
        (sid, stats.fmean(times) if times else 0.0)
        for sid, times in per_step.items()
    ]
    means.sort(key=lambda x: -x[1])
    return [{"step": sid, "mean_ms": round(m * 1000, 3)} for sid, m in means[:n]]


def render_markdown(report: dict) -> str:
    lines = [
        f"# Workflow Benchmark (n={report['n_rows']:,}, stress={report['stress']}, runs={report['runs']})",
        "",
        f"- 실행된 step 수: {report['executed_steps']}",
        f"- 총 시간: mean {report['total']['mean_ms']} ms / "
        f"min {report['total']['min_ms']} / max {report['total']['max_ms']} / "
        f"p95 {report['total']['p95_ms']}",
        "",
        "## Top 5 가장 느린 step (mean)",
        "",
        "| Step | mean_ms |",
        "|---|---|",
    ]
    for row in report["top5_slowest_mean"]:
        lines.append(f"| `{row['step']}` | {row['mean_ms']} |")
    lines.append("")
    lines.append("## Step 별 시간")
    lines.append("")
    lines.append("| Step | n | mean_ms | min_ms | max_ms | p95_ms |")
    lines.append("|---|---|---|---|---|---|")
    for sid in sorted(report["per_step"]):
        s = report["per_step"][sid]
        lines.append(
            f"| `{sid}` | {s['n']} | {s['mean_ms']} | {s['min_ms']} | "
            f"{s['max_ms']} | {s['p95_ms']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="workflow benchmark")
    parser.add_argument("--n", type=int, default=100_000)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = benchmark_workflow(
        n_rows=args.n, runs=args.runs, stress=args.stress, seed=args.seed,
    )
    if args.json:
        text = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        text = render_markdown(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
