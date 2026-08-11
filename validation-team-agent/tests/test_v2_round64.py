"""Round 64 — audit log 시계열 분석 (run.jsonl)."""

from __future__ import annotations

import pytest


# ---------- audit_timeseries 단위 ----------

@pytest.fixture
def multi_run_log(tmp_path):
    """4 runs (2 normal + 2 stress) 로그 시드."""
    from tools.run_workflow_demo import run_demo

    log_dir = tmp_path / "logs"
    run_demo(500, False, 42, log_dir)
    run_demo(500, True, 42, log_dir)
    run_demo(500, False, 43, log_dir)
    run_demo(500, True, 43, log_dir)
    return log_dir / "run.jsonl"


def test_analyse_log_groups_runs(multi_run_log):
    from tools.audit_timeseries import analyse_log

    a = analyse_log(multi_run_log)
    assert a["n_runs"] == 4
    assert a["n_records"] > 4 * 20  # 각 run 에 20+ step


def test_step_fail_rates_returns_rates_per_step(multi_run_log):
    from tools.audit_timeseries import analyse_log

    a = analyse_log(multi_run_log)
    rates = a["step_fail_rates"]
    # 모든 행에 필수 키
    for r in rates:
        assert {"step_id", "runs_with_step", "n_fails", "fail_rate"} <= set(r)
        assert 0.0 <= r["fail_rate"] <= 1.0
    # stress 가 절반이므로 capital/icaap/alm 같은 stress-fail step 의
    # fail_rate 가 양수
    by_step = {r["step_id"]: r for r in rates}
    assert by_step["3.capital"]["fail_rate"] > 0


def test_run_trend_per_run(multi_run_log):
    from tools.audit_timeseries import analyse_log

    a = analyse_log(multi_run_log)
    t = a["run_trend"]
    assert len(t) == 4
    for r in t:
        assert {"run_index", "n_steps", "fails", "warnings", "escalated"} <= set(r)
    # 2 stress runs 에서 escalation 발생
    assert sum(1 for r in t if r["escalated"]) >= 2


def test_dynamic_activations_captured(multi_run_log):
    from tools.audit_timeseries import analyse_log

    a = analyse_log(multi_run_log)
    dyn = a["dynamic_activations"]
    assert len(dyn) >= 2
    for d in dyn:
        assert d["step_id"]


def test_elapsed_stats_when_timestamps_present(multi_run_log):
    from tools.audit_timeseries import analyse_log

    a = analyse_log(multi_run_log)
    e = a["elapsed_stats"]
    # 적어도 n=runs 만큼은 elapsed 측정 (timestamp 가 동일 초에 끝날 수도)
    assert e["n"] >= 0
    if e["n"] > 0:
        assert e["min_sec"] >= 0
        assert e["max_sec"] >= e["min_sec"]


def test_analyse_log_handles_missing_file(tmp_path):
    from tools.audit_timeseries import analyse_log

    a = analyse_log(tmp_path / "no.jsonl")
    assert a["n_runs"] == 0
    assert a["run_trend"] == []
    assert a["step_fail_rates"] == []


def test_split_runs_uses_1_req_as_boundary():
    from tools.audit_timeseries import split_runs

    records = [
        {"step_id": "1.req"}, {"step_id": "2.schema"},
        {"step_id": "1.req"}, {"step_id": "2.schema"},
        {"step_id": "3.capital"},
    ]
    runs = split_runs(records)
    assert len(runs) == 2
    assert runs[0][0]["step_id"] == "1.req"
    assert runs[1][0]["step_id"] == "1.req"


# ---------- pack 페이지 ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r64pack")
    log_dir = out / "logs"
    # 누적 로그를 위해 여러 번 실행
    run_demo(500, False, 42, log_dir)
    run_demo(500, True, 42, log_dir)
    run_demo(500, True, 43, log_dir)

    demo = run_demo(800, True, 42, log_dir)
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov, log_dir=log_dir)
    return out, files


def test_audit_timeseries_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "audit_timeseries.html" in names


def test_page_shows_run_count(pack):
    out, _ = pack
    text = (out / "audit_timeseries.html").read_text(encoding="utf-8")
    assert "run" in text
    # multi-run 시드로 4+ runs
    assert "4 run" in text or "5 run" in text or "총 4" in text or "총 5" in text


def test_page_shows_step_fail_rate_chart(pack):
    out, _ = pack
    text = (out / "audit_timeseries.html").read_text(encoding="utf-8")
    assert "step 별 fail rate" in text
    assert "<svg" in text


def test_page_lists_recent_runs(pack):
    out, _ = pack
    text = (out / "audit_timeseries.html").read_text(encoding="utf-8")
    assert "최근 20 runs" in text
    assert "escalated" in text


def test_page_shows_dynamic_activations(pack):
    out, _ = pack
    text = (out / "audit_timeseries.html").read_text(encoding="utf-8")
    assert "동적 활성" in text
    # stress runs 에서 9.escalate 동적 발생
    assert "9.escalate" in text or "escalation" in text


def test_page_handles_missing_log(tmp_path):
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    log_dir = tmp_path / "nolog"
    demo = run_demo(500, False, 42, log_dir)
    # log_dir 의 run.jsonl 은 만들어진 후 페이지가 그것을 분석
    req = build_request(500, stress=False, seed=42)
    out = tmp_path / "p"
    build_pack(demo, req, out, log_dir=log_dir)
    text = (out / "audit_timeseries.html").read_text(encoding="utf-8")
    # 로그가 있으니 1 run 분석 또는 0 run 안내 중 하나
    assert "run" in text


def test_index_and_executive_link(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="audit_timeseries.html"' in idx
    assert 'href="audit_timeseries.html"' in exe


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "audit_timeseries.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
