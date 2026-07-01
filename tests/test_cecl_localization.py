"""Tests for CECL vs IFRS 9 comparison + English localization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from risk_lib import generate_portfolio, run_pipeline
from risk_lib.cecl import compute_cecl, reconcile_ifrs9_cecl
from risk_lib.localization import build_english_board_pack, _usd


@pytest.fixture(scope="module")
def result():
    return run_pipeline(generate_portfolio(seed=42), seed=42)


@pytest.fixture(scope="module")
def portfolio():
    return generate_portfolio(seed=42)


# ----- CECL ---------------------------------------------------------------

def test_cecl_positive(portfolio):
    r = compute_cecl(portfolio)
    assert r.total_cecl > 0
    assert r.weighted_life_years > 0
    assert not r.by_segment.empty


def test_cecl_deterministic(portfolio):
    a = compute_cecl(portfolio)
    b = compute_cecl(portfolio)
    assert a.total_cecl == pytest.approx(b.total_cecl, rel=1e-12)


def test_cecl_macro_overlay_scales(portfolio):
    """Higher macro factor → larger allowance."""
    low = compute_cecl(portfolio, macro_factor=1.0)
    high = compute_cecl(portfolio, macro_factor=1.20)
    assert high.total_cecl > low.total_cecl
    # overlay is zero at factor 1.0
    assert low.macro_overlay == pytest.approx(0.0, abs=1e-3)


def test_cecl_exceeds_ifrs9_in_benign(result, portfolio):
    """In the benign default book, CECL (day-1 lifetime) > IFRS9 (staged)."""
    bridge = reconcile_ifrs9_cecl(result, portfolio)
    assert bridge.cecl_total > bridge.ifrs9_total
    assert bridge.gap > 0
    assert bridge.gap_pct > 0


def test_bridge_segment_reconciles(result, portfolio):
    """Segment IFRS9 shares sum to the total IFRS9 allowance."""
    bridge = reconcile_ifrs9_cecl(result, portfolio)
    seg_ifrs9 = bridge.by_segment["ifrs9"].sum()
    assert seg_ifrs9 == pytest.approx(bridge.ifrs9_total, rel=1e-6)
    seg_cecl = bridge.by_segment["cecl"].sum()
    assert seg_cecl == pytest.approx(bridge.cecl_total, rel=1e-6)


def test_bridge_gap_equals_cecl_minus_ifrs9(result, portfolio):
    bridge = reconcile_ifrs9_cecl(result, portfolio)
    assert bridge.gap == pytest.approx(
        bridge.cecl_total - bridge.ifrs9_total, rel=1e-9)


# ----- localization -------------------------------------------------------

def test_usd_conversion():
    assert "bn" in _usd(1350e9)     # 1350bn KRW / 1350 = 1bn USD
    assert "$" in _usd(1e6)


def test_english_board_pack_writes(tmp_path, result):
    p = build_english_board_pack(result, tmp_path / "en.html")
    body = Path(p).read_text(encoding="utf-8")
    assert "Risk Committee Pack" in body
    assert "CET1 ratio" in body
    assert "Glossary" in body
    # verdict present in English
    assert ("APPROVED" in body) or ("NOT APPROVED" in body)


def test_english_board_pack_numbers_match_result(tmp_path, result):
    """English pack shows the same CET1 as the pipeline."""
    p = build_english_board_pack(result, tmp_path / "en.html")
    body = Path(p).read_text(encoding="utf-8")
    cet1_pct = f"{result.bis.cet1_ratio*100:.2f}%"
    assert cet1_pct in body


def test_english_glossary_has_cecl(tmp_path, result):
    p = build_english_board_pack(result, tmp_path / "en.html")
    body = Path(p).read_text(encoding="utf-8")
    assert "CECL" in body and "ASC 326" in body


# ----- integration --------------------------------------------------------

def test_full_package_has_english_and_cecl(tmp_path, result, portfolio):
    from risk_lib.html_report import build_full_report_package
    written = build_full_report_package(result, tmp_path, portfolio=portfolio)
    assert "board_pack_en" in written
    assert "ops/62_cecl_ifrs9.html" in written
    assert Path(written["board_pack_en"]).exists()
    import os
    assert os.path.getsize(written["ops/62_cecl_ifrs9.html"]) > 5000
