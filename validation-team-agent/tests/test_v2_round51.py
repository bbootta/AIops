"""Round 51 — ALM/유동성 고도화 (통화별 LCR + ΔNII + 일중유동성)."""

from __future__ import annotations

import pytest


def test_lcr_by_currency_sample_covers_major():
    from tools.sample_generators import lcr_by_currency_sample

    s = lcr_by_currency_sample()
    currencies = {x["currency"] for x in s}
    assert any("KRW" in c for c in currencies)
    assert any("USD" in c for c in currencies)
    for row in s:
        assert "hqla" in row and "outflow" in row and "min_required" in row


def test_nii_sensitivity_sample_six_scenarios():
    from tools.sample_generators import nii_sensitivity_sample

    n = nii_sensitivity_sample()
    names = {x["scenario"] for x in n}
    for required in ("parallel_up", "parallel_down", "steepener", "flattener",
                     "short_rate_up", "short_rate_down"):
        assert required in names


def test_intraday_liquidity_sample_has_framework():
    from tools.sample_generators import intraday_liquidity_sample

    s = intraday_liquidity_sample()
    assert "BCBS d423" in s["framework"]
    assert s["peak_to_average_ratio"] >= 1.0


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r51")
    demo = run_demo(2_000, True, 42, out / "logs")
    request = build_request(2_000, stress=True, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_alm_currency_deep_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "alm_currency_deep.html" in names


def test_page_shows_all_major_currencies(pack):
    out, _ = pack
    text = (out / "alm_currency_deep.html").read_text(encoding="utf-8")
    for currency in ("KRW", "USD", "JPY", "EUR", "CNY"):
        assert currency in text


def test_page_shows_nii_scenarios(pack):
    out, _ = pack
    text = (out / "alm_currency_deep.html").read_text(encoding="utf-8")
    assert "ΔNII" in text
    for s in ("parallel_up", "steepener", "flattener"):
        assert s in text


def test_page_shows_intraday_metrics(pack):
    out, _ = pack
    text = (out / "alm_currency_deep.html").read_text(encoding="utf-8")
    assert "일중유동성" in text
    assert "BCBS d423" in text
    assert "피크/평균" in text


def test_page_shows_foreign_lcr_80pct(pack):
    out, _ = pack
    text = (out / "alm_currency_deep.html").read_text(encoding="utf-8")
    assert "80%" in text
    assert "행정지도" in text or "외화" in text


def test_alm_parent_links_to_currency_deep(pack):
    out, _ = pack
    text = (out / "alm.html").read_text(encoding="utf-8")
    assert 'href="alm_currency_deep.html"' in text


def test_index_links_to_currency_deep(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="alm_currency_deep.html"' in idx


def test_currency_deep_self_contained(pack):
    out, _ = pack
    text = (out / "alm_currency_deep.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
