"""Round 52 — 시장리스크 고도화 (VaR 구성요소 + SVaR + IRC)."""

from __future__ import annotations

import pytest


def test_var_components_sample_complete():
    from tools.sample_generators import var_components_sample

    v = var_components_sample()
    for k in ("var_99_total", "var_general_market", "var_specific",
              "svar_99", "irc_99_9", "multiplier", "asset_classes",
              "framework"):
        assert k in v
    # SVaR 는 VaR 보다 보수적이어야 함
    assert v["svar_99"] >= v["var_99_total"]
    # General + Specific ~= total
    assert abs((v["var_general_market"] + v["var_specific"])
               - v["var_99_total"]) < 0.5


def test_var_components_asset_classes_cover_5():
    from tools.sample_generators import var_components_sample

    classes = set(var_components_sample()["asset_classes"])
    for c in ("Interest Rate", "Equity", "FX", "Commodity", "Credit Spread"):
        assert c in classes


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r52")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_market_components_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "market_components_deep.html" in names


def test_page_shows_var_components(pack):
    out, _ = pack
    text = (out / "market_components_deep.html").read_text(encoding="utf-8")
    for label in ("General Market", "Specific", "Stressed VaR", "SVaR", "IRC"):
        assert label in text


def test_page_shows_asset_class_breakdown(pack):
    out, _ = pack
    text = (out / "market_components_deep.html").read_text(encoding="utf-8")
    for cls in ("Interest Rate", "Equity", "FX", "Commodity", "Credit Spread"):
        assert cls in text


def test_page_shows_traffic_light_multiplier(pack):
    out, _ = pack
    text = (out / "market_components_deep.html").read_text(encoding="utf-8")
    assert "multiplier" in text
    assert "yellow" in text
    assert "MAR99" in text


def test_market_ops_links_to_components_deep(pack):
    out, _ = pack
    text = (out / "market_ops.html").read_text(encoding="utf-8")
    assert 'href="market_components_deep.html"' in text


def test_index_links_to_components_deep(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="market_components_deep.html"' in idx


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "market_components_deep.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
