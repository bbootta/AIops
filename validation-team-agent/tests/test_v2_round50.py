"""Round 50 — 자본적정성 고도화 (RWA 분해 + Output Floor + SREP)."""

from __future__ import annotations

import pytest


def test_rwa_decomposition_sample_complete():
    from tools.sample_generators import rwa_decomposition_sample

    r = rwa_decomposition_sample()
    assert "by_approach" in r
    assert "standardised_full" in r
    assert r["output_floor_ratio"] == 0.725
    assert r["rwa_after_floor"] >= r["total_internal"]
    assert isinstance(r["floor_binding"], bool)


def test_srep_capital_sample_has_p2r_p2g():
    from tools.sample_generators import srep_capital_sample

    s = srep_capital_sample()
    for k in ("p2r_pct", "p2g_pct", "stress_buffer_pct", "framework"):
        assert k in s
    assert 0 < s["p2r_pct"] < 0.05
    assert s["rationale"]  # 비어있지 않음


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r50")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_capital_rwa_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "capital_rwa_deep.html" in names


def test_rwa_page_shows_internal_approaches(pack):
    out, _ = pack
    text = (out / "capital_rwa_deep.html").read_text(encoding="utf-8")
    for approach in ("credit_irba", "market_imm", "operational_sma",
                     "cva_basa", "ccr_sa"):
        assert approach in text


def test_rwa_page_shows_output_floor(pack):
    out, _ = pack
    text = (out / "capital_rwa_deep.html").read_text(encoding="utf-8")
    assert "Output Floor" in text
    assert "72.5%" in text or "72%" in text
    assert "BCBS d424" in text or "d424" in text


def test_rwa_page_shows_srep_components(pack):
    out, _ = pack
    text = (out / "capital_rwa_deep.html").read_text(encoding="utf-8")
    assert "P2R" in text
    assert "P2G" in text
    assert "SREP" in text


def test_rwa_page_has_floor_binding_status(pack):
    out, _ = pack
    text = (out / "capital_rwa_deep.html").read_text(encoding="utf-8")
    assert "Floor binding" in text


def test_capital_main_page_links_to_rwa_deep(pack):
    out, _ = pack
    text = (out / "capital_icaap.html").read_text(encoding="utf-8")
    assert 'href="capital_rwa_deep.html"' in text


def test_index_links_to_rwa_deep(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="capital_rwa_deep.html"' in idx


def test_rwa_page_self_contained_and_provenance(pack):
    out, _ = pack
    text = (out / "capital_rwa_deep.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
