"""Round 41 — 부문 심화 (deep drill-down) 확장."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r41")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_four_new_deep_pages_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    for new_page in ("capital_buffer_deep.html", "icaap_deep.html",
                     "operational_deep.html", "ccr_deep.html"):
        assert new_page in names


def test_capital_buffer_page_decomposes_components(pack):
    out, _ = pack
    text = (out / "capital_buffer_deep.html").read_text(encoding="utf-8")
    # 4 buffer 구성 요소 모두 등장
    for piece in ("Pillar 1", "자본보전", "경기대응", "D-SIB", "Sensitivity"):
        assert piece in text
    # 표 + 차트
    assert text.count("<svg") >= 2


def test_capital_buffer_sensitivity_includes_negative_shocks(pack):
    out, _ = pack
    text = (out / "capital_buffer_deep.html").read_text(encoding="utf-8")
    for bps in ("-50 bps", "-100 bps", "-150 bps"):
        assert bps in text


def test_icaap_deep_page_shows_risk_breakdown(pack):
    out, _ = pack
    text = (out / "icaap_deep.html").read_text(encoding="utf-8")
    assert "필요내부자본 리스크 구성" in text
    # 5 리스크 유형
    for risk in ("credit", "market", "operational", "irrbb", "concentration"):
        assert risk in text
    # 비율 단계
    assert "baseline" in text
    assert "post-stress" in text
    assert "severe" in text


def test_operational_deep_breaks_down_bic_tiers(pack):
    out, _ = pack
    text = (out / "operational_deep.html").read_text(encoding="utf-8")
    assert "0 ~ 1bn" in text
    assert "1bn ~ 30bn" in text
    assert "&gt;30bn" in text or ">30bn" in text
    assert "12%" in text and "15%" in text and "18%" in text
    assert "ILM" in text


def test_ccr_deep_decomposes_ead(pack):
    out, _ = pack
    text = (out / "ccr_deep.html").read_text(encoding="utf-8")
    assert "Replacement Cost" in text
    assert "Potential Future Exposure" in text
    assert "α" in text or "1.4" in text
    assert "Wrong-Way Risk" in text


def test_all_deep_pages_self_contained(pack):
    out, _ = pack
    for name in ("capital_buffer_deep.html", "icaap_deep.html",
                 "operational_deep.html", "ccr_deep.html"):
        text = (out / name).read_text(encoding="utf-8")
        assert "https://" not in text
        assert "<script" not in text


def test_all_deep_pages_have_provenance_card(pack):
    out, _ = pack
    for name in ("capital_buffer_deep.html", "icaap_deep.html",
                 "operational_deep.html", "ccr_deep.html"):
        text = (out / name).read_text(encoding="utf-8")
        assert "Reproducibility" in text


def test_detail_pages_link_to_their_deep(pack):
    out, _ = pack
    cap = (out / "capital_icaap.html").read_text(encoding="utf-8")
    mo = (out / "market_ops.html").read_text(encoding="utf-8")
    assert 'href="capital_buffer_deep.html"' in cap
    assert 'href="icaap_deep.html"' in cap
    assert 'href="operational_deep.html"' in mo
    assert 'href="ccr_deep.html"' in mo


def test_index_links_to_all_deep_pages(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    for name in ("capital_buffer_deep.html", "icaap_deep.html",
                 "operational_deep.html", "ccr_deep.html"):
        assert f'href="{name}"' in idx


def test_deep_pages_have_drilldown_link_back_to_parent(pack):
    out, _ = pack
    for child, parent in [
        ("capital_buffer_deep.html", "capital_icaap.html"),
        ("icaap_deep.html", "capital_icaap.html"),
        ("operational_deep.html", "market_ops.html"),
        ("ccr_deep.html", "market_ops.html"),
    ]:
        text = (out / child).read_text(encoding="utf-8")
        assert f'href="{parent}"' in text


def test_total_page_count_after_r41(pack):
    """16 페이지: index/executive/explainability + 6 부문 + 4 기존 심화 + 4 신규 심화"""
    _, files = pack
    assert len(files) == 16
