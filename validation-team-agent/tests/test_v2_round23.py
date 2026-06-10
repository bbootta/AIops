"""Round 23 — workflow benchmark tool 검증."""

from __future__ import annotations

import json

import pytest


def test_benchmark_runs_smoke(tmp_path):
    """소규모 benchmark 가 한 번 돌고 report 구조를 갖춘다."""
    from tools.benchmark import benchmark_workflow

    rpt = benchmark_workflow(n_rows=500, runs=1, log_dir=tmp_path)
    assert rpt["n_rows"] == 500
    assert rpt["runs"] == 1
    assert rpt["stress"] is False
    assert rpt["executed_steps"] >= 1
    assert rpt["total"]["n"] == 1
    assert rpt["total"]["mean_ms"] >= 0
    assert "min_ms" in rpt["total"]
    assert "max_ms" in rpt["total"]
    assert "p95_ms" in rpt["total"]
    assert isinstance(rpt["per_step"], dict)
    assert len(rpt["per_step"]) >= 1


def test_benchmark_runs_multiple(tmp_path):
    """runs=3 이면 total.n == 3, per_step 도 누적."""
    from tools.benchmark import benchmark_workflow

    rpt = benchmark_workflow(n_rows=200, runs=3, log_dir=tmp_path)
    assert rpt["total"]["n"] == 3
    for sid, summ in rpt["per_step"].items():
        assert summ["n"] == 3, f"{sid} runs 누락"


def test_benchmark_top5_returns_at_most_5(tmp_path):
    from tools.benchmark import benchmark_workflow

    rpt = benchmark_workflow(n_rows=300, runs=1, log_dir=tmp_path)
    top = rpt["top5_slowest_mean"]
    assert isinstance(top, list)
    assert len(top) <= 5
    for row in top:
        assert "step" in row
        assert "mean_ms" in row


def test_benchmark_stress_changes_request(tmp_path):
    """stress 모드면 stress 플래그가 그대로 보고서에 반영."""
    from tools.benchmark import benchmark_workflow

    rpt = benchmark_workflow(n_rows=300, runs=1, stress=True, log_dir=tmp_path)
    assert rpt["stress"] is True


def test_benchmark_render_markdown(tmp_path):
    from tools.benchmark import benchmark_workflow, render_markdown

    rpt = benchmark_workflow(n_rows=200, runs=1, log_dir=tmp_path)
    md = render_markdown(rpt)
    assert "Workflow Benchmark" in md
    assert "Top 5" in md
    assert "Step 별 시간" in md
    # 표 헤더가 있어야 한다
    assert "| Step | n | mean_ms" in md


def test_benchmark_cli_writes_json(tmp_path, capsys):
    from tools.benchmark import main

    out = tmp_path / "bench.json"
    rc = main(["--n", "200", "--runs", "1", "--json", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["n_rows"] == 200
    assert data["total"]["n"] == 1


def test_benchmark_cli_writes_markdown(tmp_path):
    from tools.benchmark import main

    out = tmp_path / "bench.md"
    rc = main(["--n", "200", "--runs", "1", "--out", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Workflow Benchmark" in text


def test_benchmark_summarise_empty():
    from tools.benchmark import _summarise

    assert _summarise([]) == {"n": 0}


def test_benchmark_summarise_single_value():
    from tools.benchmark import _summarise

    summ = _summarise([0.5])
    assert summ["n"] == 1
    assert summ["mean_ms"] == 500.0
    assert summ["min_ms"] == 500.0
    assert summ["max_ms"] == 500.0
    assert summ["p95_ms"] == 500.0
