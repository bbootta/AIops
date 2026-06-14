"""Round 53 — 신용집중 고도화 (산업/지역/통화 + Top 10 exposures)."""

from __future__ import annotations

import pytest


def test_concentration_segments_sample_complete():
    from tools.sample_generators import concentration_segments_sample

    s = concentration_segments_sample()
    for k in ("industry", "region", "currency", "top_exposures"):
        assert k in s
    assert len(s["top_exposures"]) == 10
    # 모든 top exposure 에 산업·tier1 비중
    for e in s["top_exposures"]:
        assert "name" in e and "industry" in e and "pct_tier1" in e


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r53")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_concentration_segments_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "concentration_segments.html" in names


def test_page_shows_industry_breakdown(pack):
    out, _ = pack
    text = (out / "concentration_segments.html").read_text(encoding="utf-8")
    assert "산업별 집중" in text
    for ind in ("제조업", "부동산", "건설", "금융업"):
        assert ind in text


def test_page_shows_region_breakdown(pack):
    out, _ = pack
    text = (out / "concentration_segments.html").read_text(encoding="utf-8")
    assert "지역별 집중" in text
    for r in ("수도권", "영남권"):
        assert r in text


def test_page_shows_currency_breakdown(pack):
    out, _ = pack
    text = (out / "concentration_segments.html").read_text(encoding="utf-8")
    assert "통화별 집중" in text
    for c in ("KRW", "USD", "JPY"):
        assert c in text


def test_page_shows_top_10_groups(pack):
    out, _ = pack
    text = (out / "concentration_segments.html").read_text(encoding="utf-8")
    assert "Top 10" in text
    for i in range(10):
        assert f"Group-{i:02d}" in text


def test_page_shows_hhi_per_segment(pack):
    out, _ = pack
    text = (out / "concentration_segments.html").read_text(encoding="utf-8")
    # 산업/지역/통화 각각 HHI band
    assert text.count("합계 HHI") == 3


def test_concentration_parent_links_to_segments(pack):
    out, _ = pack
    text = (out / "concentration.html").read_text(encoding="utf-8")
    assert 'href="concentration_segments.html"' in text


def test_index_links_to_segments(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="concentration_segments.html"' in idx


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "concentration_segments.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
