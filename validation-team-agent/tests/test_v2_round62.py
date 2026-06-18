"""Round 62 — CRO 1페이지 TL;DR (exec_summary)."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def pack_stress(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r62s")
    demo = run_demo(2_000, True, 42, out / "logs")
    request = build_request(2_000, stress=True, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


@pytest.fixture(scope="module")
def pack_normal(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r62n")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_exec_summary_page_generated(pack_stress):
    out, files = pack_stress
    names = {p.name for p in files}
    assert "exec_summary.html" in names


def test_stress_shows_red_overall(pack_stress):
    out, _ = pack_stress
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "🔴 위험" in text


def test_normal_shows_green_or_yellow(pack_normal):
    out, _ = pack_normal
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "🟢 안정" in text or "🟡 주의" in text


def test_signal_lights_for_15_domains(pack_stress):
    out, _ = pack_stress
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "부문별 신호등" in text
    # 신용/자본/ICAAP/유동성/시장/운영/CVA/CCR/집중 등 부문 label
    for label in ("신용", "자본", "내부자본", "유동성", "ALM", "시장",
                  "운영", "집중"):
        assert label in text


def test_qoq_metrics_shown(pack_stress):
    out, _ = pack_stress
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "전 분기 대비" in text
    # QoQ 6 지표
    for metric in ("CET1", "LCR", "ICAAP", "ΔEVE", "PSI", "HHI"):
        assert metric in text
    # 변화 화살표
    assert "▲" in text or "▼" in text or "—" in text


def test_top3_risk_watch_present(pack_stress):
    out, _ = pack_stress
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "Top 3 Risk Watch" in text


def test_decision_guide_three_levels(pack_stress):
    out, _ = pack_stress
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "🟢 안정" in text
    assert "🟡 주의" in text
    assert "🔴 위험" in text
    assert "9.escalate" in text or "MRMC" in text


def test_navigation_links(pack_stress):
    out, _ = pack_stress
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    for href in ("executive.html", "trends.html", "stress_test.html",
                 "change_audit.html", "index.html"):
        assert f'href="{href}"' in text


def test_index_links_to_exec_summary(pack_stress):
    out, _ = pack_stress
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="exec_summary.html"' in idx


def test_executive_links_to_exec_summary(pack_stress):
    out, _ = pack_stress
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="exec_summary.html"' in exe


def test_self_contained(pack_stress):
    out, _ = pack_stress
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
