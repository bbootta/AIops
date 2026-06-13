"""Round 42 — 시계열 추세 (4분기 panel + trend 차트)."""

from __future__ import annotations

import pytest


def test_quarterly_panel_deterministic():
    from tools.sample_generators import quarterly_panel

    p1 = quarterly_panel(seed=31)
    p2 = quarterly_panel(seed=31)
    assert p1 == p2


def test_quarterly_panel_different_seeds_differ():
    from tools.sample_generators import quarterly_panel

    p1 = quarterly_panel(seed=31)
    p2 = quarterly_panel(seed=32)
    assert p1 != p2


def test_quarterly_panel_default_4_quarters():
    from tools.sample_generators import quarterly_panel

    p = quarterly_panel()
    assert [r["period"] for r in p] == ["Q1", "Q2", "Q3", "Q4"]


def test_quarterly_panel_covers_required_metrics():
    from tools.sample_generators import quarterly_panel

    p = quarterly_panel()
    keys = set(p[0])
    for required in ("cet1", "leverage", "lcr", "nsfr", "icaap",
                     "delta_eve", "psi", "hhi"):
        assert required in keys


def test_quarterly_panel_shows_degradation_trend():
    """본 panel 은 점진 악화 trend 를 시연 — 일부 metric 은 분기 진행에 따라 악화."""
    from tools.sample_generators import quarterly_panel

    p = quarterly_panel()
    # CET1 / LCR 는 분기 진행에 따라 감소 추세
    assert p[0]["cet1"] >= p[-1]["cet1"]
    assert p[0]["lcr"] >= p[-1]["lcr"]
    # ΔEVE / PSI 는 증가 추세
    assert p[0]["delta_eve"] <= p[-1]["delta_eve"]
    assert p[0]["psi"] <= p[-1]["psi"]


# ---------- trends 페이지 ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r42")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_trends_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "trends.html" in names


def test_trends_page_has_8_trend_charts(pack):
    out, _ = pack
    text = (out / "trends.html").read_text(encoding="utf-8")
    # 본문 SVG 8개 + provenance 카드는 SVG 미포함
    assert text.count("<svg") == 8


def test_trends_page_labels_quarters(pack):
    out, _ = pack
    text = (out / "trends.html").read_text(encoding="utf-8")
    for q in ("Q1", "Q2", "Q3", "Q4"):
        assert q in text


def test_trends_page_shows_minimum_lines(pack):
    out, _ = pack
    text = (out / "trends.html").read_text(encoding="utf-8")
    # 임계선 label 들이 출력
    assert "min 7.00%" in text or "min 0.070" in text  # CET1
    assert "min 1.00" in text  # LCR/NSFR/ICAAP
    assert "min 15.0%" in text or "min 0.150" in text  # ΔEVE


def test_trends_page_summary_table_present(pack):
    out, _ = pack
    text = (out / "trends.html").read_text(encoding="utf-8")
    assert "분기별 수치" in text
    assert "<table>" in text


def test_trends_page_has_provenance_and_draft(pack):
    out, _ = pack
    text = (out / "trends.html").read_text(encoding="utf-8")
    assert "Reproducibility" in text
    assert "[DRAFT" in text


def test_trends_page_self_contained(pack):
    out, _ = pack
    text = (out / "trends.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text


def test_index_and_executive_link_to_trends(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="trends.html"' in idx
    assert 'href="trends.html"' in exe


def test_trend_line_handles_minimum_violations():
    """차트의 빨간 점은 임계 위반 — trend_line 함수 단위 검증."""
    from tools.svg_charts import trend_line

    svg = trend_line(
        [("Q1", 1.10), ("Q2", 0.95)], minimum=1.0, title="t")
    # 1.10 은 ok 색, 0.95 는 fail 색 — palette 색상이 모두 포함
    assert "#2e7d32" in svg  # ok (Q1)
    assert "#c62828" in svg  # fail (Q2)


def test_pack_total_pages_after_r42(pack):
    """trends.html 가 추가되어 R41 대비 최소 1페이지 증가."""
    _, files = pack
    names = {p.name for p in files}
    assert "trends.html" in names
    assert len(files) >= 17  # 후속 라운드에서 증가 가능
