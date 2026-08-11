"""Round 32 — Q5-2: 정적 HTML 대시보드."""

from __future__ import annotations

from tools.dashboard import group_runs, render_dashboard, summarise_run


def _rec(step_id, ws="ok", dynamic=False, ts="2026-06-10 09:00:00"):
    return {"timestamp": ts, "event": "step", "step_id": step_id,
            "workflow_status": ws, "detail": f"{step_id} detail", "dynamic": dynamic}


def test_group_runs_splits_on_1req():
    records = [_rec("1.req"), _rec("3.capital"),
               _rec("1.req"), _rec("3.capital", "fail"), _rec("9.escalate", dynamic=True)]
    runs = group_runs(records)
    assert len(runs) == 2
    assert len(runs[0]) == 2
    assert len(runs[1]) == 3


def test_group_runs_orphan_events_kept():
    records = [_rec("3.capital"), _rec("1.req"), _rec("3.capital")]
    runs = group_runs(records)
    assert len(runs) == 2
    assert runs[0][0]["step_id"] == "3.capital"


def test_summarise_run_counts_and_escalation():
    run = [_rec("1.req"), _rec("3.capital", "fail"), _rec("9.escalate", dynamic=True)]
    s = summarise_run(run)
    assert s["n_steps"] == 3
    assert s["fails"] == 1
    assert s["escalated"] is True
    assert s["counts"]["ok"] == 2


def test_render_dashboard_contains_draft_and_runs():
    records = [_rec("1.req"), _rec("3.capital", "fail"), _rec("9.escalate", dynamic=True)]
    html = render_dashboard(records)
    assert "DRAFT — 외부 제출 금지" in html
    assert "3.capital" in html
    assert "🔄" in html  # 동적 step 마커
    assert "<script" not in html  # 외부/inline JS 없음


def test_render_dashboard_empty_records():
    html = render_dashboard([])
    assert "step 이벤트 없음" in html
    assert "DRAFT" in html


def test_render_dashboard_escapes_html():
    records = [_rec("1.req"), {"timestamp": "t", "event": "step",
                               "step_id": "<img src=x>", "workflow_status": "ok",
                               "detail": "<script>alert(1)</script>", "dynamic": False}]
    html = render_dashboard(records)
    assert "<img src=x>" not in html
    assert "<script>alert" not in html


def test_cli_writes_dashboard(tmp_path):
    from middleware.run_logger import log_step
    from tools.dashboard import main

    log_step("1.req", component="x", log_dir=tmp_path,
             extra={"workflow_status": "ok"})
    out = tmp_path / "dash.html"
    rc = main(["--log", str(tmp_path / "run.jsonl"), "--out", str(out)])
    assert rc == 0
    assert "1.req" in out.read_text(encoding="utf-8")


def test_vta_cli_has_dashboard_dispatch():
    from vta.cli.__main__ import _DISPATCH

    assert _DISPATCH[("dashboard",)] == "tools.dashboard"
