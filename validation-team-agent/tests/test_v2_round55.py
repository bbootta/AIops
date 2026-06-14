"""Round 55 — 운영리스크 BI components + ILDC."""

from __future__ import annotations

import pytest


def test_bi_components_sample():
    from tools.sample_generators import operational_bi_components_sample

    b = operational_bi_components_sample()
    assert "Interest/Lease/Dividend" in b["components"]
    assert "Services" in b["components"]
    assert abs(sum(b["components"].values()) - b["total_bi"]) < 1e-6
    assert "OPE25" in b["framework"]


def test_loss_history_sample_10_years():
    from tools.sample_generators import operational_loss_history_sample

    h = operational_loss_history_sample()
    assert len(h) == 10
    for r in h:
        assert "year" in r and "n_events" in r and "total_loss_bn" in r
        assert r["avg_loss_bn"] > 0


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r55")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_operational_bi_deep_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "operational_bi_deep.html" in names


def test_page_shows_5_bi_components(pack):
    out, _ = pack
    text = (out / "operational_bi_deep.html").read_text(encoding="utf-8")
    for comp in ("Interest/Lease/Dividend", "Services", "Financial (Trading book)"):
        assert comp in text


def test_page_shows_ildc_history(pack):
    out, _ = pack
    text = (out / "operational_bi_deep.html").read_text(encoding="utf-8")
    assert "ILDC" in text
    for year in range(2016, 2026):
        assert str(year) in text


def test_page_shows_bic_tier_breakdown(pack):
    out, _ = pack
    text = (out / "operational_bi_deep.html").read_text(encoding="utf-8")
    for label in ("12%", "15%", "18%", "BIC", "ORC"):
        assert label in text


def test_market_ops_links_to_bi_deep(pack):
    out, _ = pack
    text = (out / "market_ops.html").read_text(encoding="utf-8")
    assert 'href="operational_bi_deep.html"' in text


def test_index_links_to_bi_deep(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="operational_bi_deep.html"' in idx


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "operational_bi_deep.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
