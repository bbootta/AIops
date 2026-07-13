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
