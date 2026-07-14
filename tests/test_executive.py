"""Tests for the executive (CRO) report — briefing narrative + full deep-dive nav."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def exec_html(tmp_path_factory, result):
    from risk_lib.html_exec import build_executive
    out = build_executive(result, tmp_path_factory.mktemp("exec"),
                          manifest_digest="cafebabe12345678")
    return Path(out).read_text(encoding="utf-8")


def test_executive_has_cro_briefing(exec_html, result):
    assert "CRO 브리핑" in exec_html
    # deterministic derivations actually appear in the narrative
    sev = result.stress_path_trough
    trough = float(sev[sev["scenario"] == "severely_adverse"].iloc[0]["trough_cet1"])
    assert f"{trough*100:.2f}%" in exec_html          # severe trough CET1
    pit, ttc = result.macro_ecl.weighted_total, result.ecl["total"]
    assert f"{(pit/ttc-1)*100:+.0f}%" in exec_html     # PIT vs TTC gap


def test_executive_links_every_ops_page(exec_html):
    """Deep-dive nav derives from page_registry — all pages must be linked."""
    from risk_lib.page_registry import PAGES
    missing = [s.filename for s in PAGES
               if f'href="ops/{s.filename}"' not in exec_html]
    assert not missing, f"executive missing deep-dive links: {missing}"


def test_executive_repro_and_abbreviations(exec_html):
    assert "cafebabe12345678"[:16] in exec_html        # manifest digest surfaced
    assert "약어" in exec_html                          # abbreviation card


def test_executive_buffer_ladder_and_tornado(exec_html, result):
    assert "CET1 버퍼 사다리" in exec_html
    assert "민감도 토네이도" in exec_html
    # ladder renders one bar per requirement layer
    hr = result.attribution["cet1_headroom"]
    for _, row in hr.iterrows():
        assert f"{row['headroom']*100:+.2f}%p" in exec_html


def test_tornado_ranks_worst_adverse_first(result):
    from risk_lib.html_exec import _sensitivity_tornado
    import re
    svg = _sensitivity_tornado(result)
    values = [float(m) for m in re.findall(r">([\d.]+)%</text>", svg)]
    assert values == sorted(values, reverse=True)
    assert len(values) >= 5


def test_kri_scorecard_sparklines(exec_html, result):
    """Every KRI card carries a 12M sparkline + trend label, reproducibly."""
    assert exec_html.count("<polyline") >= len(result.raf.kris)
    assert exec_html.count("12M ") == len(result.raf.kris)
    from risk_lib.html_exec import _kri_card_data
    a = _kri_card_data(result.raf, seed=42)
    b = _kri_card_data(result.raf, seed=42)
    assert all(x.get("spark") == y.get("spark") for x, y in zip(a, b))
    # without seed the scorecard input is unchanged (no spark keys)
    plain = _kri_card_data(result.raf)
    assert all("spark" not in row for row in plain)


def test_board_pack_carries_briefing(tmp_path, result):
    from risk_lib.board_pack import build_board_pack
    p = build_board_pack(result, tmp_path / "bp.html")
    body = Path(p).read_text(encoding="utf-8")
    assert "CRO 브리핑" in body
    seg = body.split("CRO 브리핑")[1].split("<h3>")[0]
    assert "<a " not in seg      # standalone A4 — links stripped


def test_english_briefing_shares_derivations(tmp_path, result):
    """EN board pack briefing uses briefing_facts — same numbers as Korean."""
    from risk_lib.localization import build_english_board_pack
    from risk_lib.html_exec import briefing_facts
    p = build_english_board_pack(result, tmp_path / "en.html")
    body = Path(p).read_text(encoding="utf-8")
    assert "CRO Briefing" in body
    f = briefing_facts(result)
    assert f"{f['sev']['trough']*100:.2f}%" in body   # severe trough CET1
    assert f"{f['gap_pct']:+.0f}%" in body            # PIT vs TTC gap
    assert f"HHI {f['conc_hhi']:.3f}" in body         # concentration
