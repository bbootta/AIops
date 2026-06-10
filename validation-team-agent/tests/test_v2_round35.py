"""Round 35 — benchmark --async 모드 + recurring finding 기록."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_benchmark_async_mode_runs(tmp_path):
    from tools.benchmark import benchmark_workflow

    rpt = benchmark_workflow(n_rows=300, runs=1, log_dir=tmp_path, use_async=True)
    assert rpt["async"] is True
    assert rpt["total"]["n"] == 1
    assert rpt["executed_steps"] >= 1
    # per-step 타이밍이 async 경로에서도 수집된다 (worker thread 기록)
    assert len(rpt["per_step"]) >= 1


def test_benchmark_sync_default_reports_async_false(tmp_path):
    from tools.benchmark import benchmark_workflow

    rpt = benchmark_workflow(n_rows=300, runs=1, log_dir=tmp_path)
    assert rpt["async"] is False


def test_benchmark_markdown_shows_async_flag(tmp_path):
    from tools.benchmark import benchmark_workflow, render_markdown

    rpt = benchmark_workflow(n_rows=200, runs=1, log_dir=tmp_path, use_async=True)
    md = render_markdown(rpt)
    assert "async=True" in md


def test_benchmark_cli_async_flag(tmp_path):
    from tools.benchmark import main

    out = tmp_path / "bench_async.json"
    rc = main(["--n", "200", "--runs", "1", "--json", "--async",
               "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["async"] is True


def test_catalog_drift_recorded_in_recurring_findings():
    """R34 카탈로그 드리프트 finding 이 memory SSoT 에 기록돼 있다."""
    data = json.loads(
        (ROOT / "memory" / "recurring_findings.json").read_text(encoding="utf-8")
    )
    descs = " ".join(f["description"] for f in data["findings"])
    assert "카탈로그" in descs or "cli_index" in descs
