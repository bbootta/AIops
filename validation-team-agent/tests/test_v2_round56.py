"""Round 56 — CCR netting set + Wrong-Way Risk."""

from __future__ import annotations

import pytest


def test_ccr_netting_sample_complete():
    from tools.sample_generators import ccr_netting_sample

    s = ccr_netting_sample()
    assert len(s) >= 5
    for ns in s:
        for k in ("netting_set", "counterparty", "asset_class", "rc", "pfe",
                  "collateral_bn", "wrong_way_risk"):
            assert k in ns


def test_ccr_netting_has_wwr_case():
    from tools.sample_generators import ccr_netting_sample

    s = ccr_netting_sample()
    assert any(ns["wrong_way_risk"] for ns in s)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r56")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_ccr_netting_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "ccr_netting_deep.html" in names


def test_page_shows_netting_sets(pack):
    out, _ = pack
    text = (out / "ccr_netting_deep.html").read_text(encoding="utf-8")
    for ns in ("NS-001", "NS-002", "NS-003"):
        assert ns in text


def test_page_shows_asset_class_breakdown(pack):
    out, _ = pack
    text = (out / "ccr_netting_deep.html").read_text(encoding="utf-8")
    for cls in ("Interest Rate", "FX", "Credit", "Equity"):
        assert cls in text


def test_page_shows_wrong_way_risk(pack):
    out, _ = pack
    text = (out / "ccr_netting_deep.html").read_text(encoding="utf-8")
    assert "Wrong-Way Risk" in text or "WWR" in text
    assert "α 가산" in text or "CRE52" in text


def test_page_shows_ead_formula(pack):
    out, _ = pack
    text = (out / "ccr_netting_deep.html").read_text(encoding="utf-8")
    assert "RC" in text and "PFE" in text and "Collateral" in text
    assert "EAD" in text


def test_market_ops_links_to_netting_deep(pack):
    out, _ = pack
    text = (out / "market_ops.html").read_text(encoding="utf-8")
    assert 'href="ccr_netting_deep.html"' in text


def test_index_links_to_netting_deep(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="ccr_netting_deep.html"' in idx


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "ccr_netting_deep.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
