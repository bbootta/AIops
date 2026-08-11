"""Round 66 — 분기 거버넌스 KPI 시계열."""

from __future__ import annotations

import pytest


# ---------- panel ----------

def test_synthetic_panel_has_4_quarters():
    from tools.governance_timeseries import synthetic_governance_panel

    p = synthetic_governance_panel()
    assert len(p) == 4
    for row in p:
        for k in ("quarter", "validated_ratio", "audit_fail_ratio",
                  "feedback_agreement_rate", "policy_lint_conflicts",
                  "manifest_total", "rf_total"):
            assert k in row
        assert 0 <= row["validated_ratio"] <= 1
        assert 0 <= row["audit_fail_ratio"] <= 1


def test_synthetic_panel_shows_improvement_trend():
    from tools.governance_timeseries import synthetic_governance_panel

    p = synthetic_governance_panel()
    assert p[-1]["validated_ratio"] >= p[0]["validated_ratio"]
    assert p[-1]["audit_fail_ratio"] <= p[0]["audit_fail_ratio"]


def test_quarter_of_iso_timestamp():
    from tools.governance_timeseries import quarter_of

    assert quarter_of("2026-02-15 10:00:00") == "2026Q1"
    assert quarter_of("2026-04-15 10:00:00") == "2026Q2"
    assert quarter_of("2026-12-31 23:59:59") == "2026Q4"
    assert quarter_of("garbage") is None


def test_audit_panel_from_log(tmp_path):
    from tools.governance_timeseries import audit_panel_from_log
    from tools.run_workflow_demo import run_demo

    run_demo(500, True, 42, tmp_path)
    p = audit_panel_from_log(tmp_path / "run.jsonl")
    assert p
    for row in p:
        assert {"quarter", "audit_total_steps", "audit_fail_steps",
                "audit_fail_ratio"} <= set(row)


def test_audit_panel_handles_missing(tmp_path):
    from tools.governance_timeseries import audit_panel_from_log

    assert audit_panel_from_log(tmp_path / "no.jsonl") == []


def test_build_panel_merges_audit_into_synthetic(tmp_path):
    from tools.governance_timeseries import build_panel
    from tools.run_workflow_demo import run_demo

    run_demo(500, True, 42, tmp_path)
    panel = build_panel(tmp_path / "run.jsonl")
    # 일부 분기는 live 출처
    sources = {row.get("audit_source") for row in panel}
    assert "synthetic" in sources or "live" in sources


# ---------- 보고서 페이지 ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r66")
    log_dir = out / "logs"
    run_demo(500, True, 42, log_dir)

    demo = run_demo(500, True, 42, log_dir)
    request = build_request(500, stress=True, seed=42)
    prov = build_provenance(request, n=500, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov, log_dir=log_dir)
    return out, files


def test_governance_trend_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "governance_trend.html" in names


def test_page_shows_4_trend_charts(pack):
    out, _ = pack
    text = (out / "governance_trend.html").read_text(encoding="utf-8")
    for label in ("validated_ratio", "fail_ratio", "agreement_rate",
                  "Policy lint"):
        assert label in text
    assert text.count("<svg") >= 4


def test_page_shows_phase_2_threshold(pack):
    out, _ = pack
    text = (out / "governance_trend.html").read_text(encoding="utf-8")
    assert "70%" in text
    assert "Phase 2" in text or "통합 운영" in text


def test_page_links_to_findings_and_change_audit(pack):
    out, _ = pack
    text = (out / "governance_trend.html").read_text(encoding="utf-8")
    assert 'href="findings_mapping.html"' in text
    assert 'href="change_audit.html"' in text


def test_index_and_executive_links(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="governance_trend.html"' in idx
    assert 'href="governance_trend.html"' in exe


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "governance_trend.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
