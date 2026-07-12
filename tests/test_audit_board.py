"""Tests for audit trail ledger + Risk Committee board pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from risk_lib import generate_portfolio
from risk_lib.audit_trail import (
    LedgerEntry, AuditLedger, build_ledger_from_result,
)
from risk_lib.board_pack import build_board_pack

# `result` fixture: session-scoped shared — see conftest.py.


# ----- ledger primitives ---------------------------------------------------

def test_ledger_entry_has_all_fields():
    e = LedgerEntry(figure_id="bis.cet1", label="CET1",
                    value=0.115, unit="ratio",
                    code_module="risk_lib.capital.bis",
                    code_function="compute_bis_ratios",
                    citation="CRE10.4")
    assert e.figure_id == "bis.cet1"
    assert e.schema_version == "1.0"
    assert e.asof  # auto-timestamped


def test_ledger_append():
    led = AuditLedger()
    led.add(LedgerEntry(figure_id="a", label="A", value=1.0))
    led.add(LedgerEntry(figure_id="b", label="B", value=2.0))
    assert len(led.entries) == 2


def test_ledger_json_roundtrip(tmp_path):
    led = AuditLedger()
    led.add(LedgerEntry(figure_id="rwa.final", label="RWA",
                         value=1.0e12, citation="RBC30.1"))
    p = led.export_json(tmp_path / "ledger.json")
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["figure_id"] == "rwa.final"
    assert data[0]["citation"] == "RBC30.1"


def test_ledger_from_result_covers_headlines(result):
    led = build_ledger_from_result(result, git_commit="testsha")
    ids = {e.figure_id for e in led.entries}
    must_have = {
        "rwa.sa", "rwa.irb", "rwa.market", "rwa.op",
        "rwa.standardised_total", "rwa.final_total",
        "bis.cet1", "bis.tier1", "bis.total",
        "leverage",
        "ecl.ttc_total", "ecl.pit_weighted",
        "alm.lcr", "alm.nsfr", "alm.irrbb_worst_pct_tier1",
        "reverse_stress.severity",
        # v0.28 coverage extension (ISO 42001 continual improvement)
        "stress.trough_cet1", "concentration.worst_hhi",
        "ccr.cva_charge", "op_loss.var_99_9",
        "climate.worst_transition_uplift", "raf.worst",
    }
    missing = must_have - ids
    assert not missing, f"missing ledger entries: {missing}"


def test_ledger_carries_git_commit(result):
    led = build_ledger_from_result(result, git_commit="abc123")
    for e in led.entries:
        assert e.git_commit == "abc123"


def test_ledger_citations_present(result):
    led = build_ledger_from_result(result)
    # Every entry must carry at least one citation
    no_cite = [e.figure_id for e in led.entries if not e.citation]
    assert not no_cite, f"missing citations: {no_cite}"


# ----- board pack ----------------------------------------------------------

def test_board_pack_writes_html(tmp_path, result):
    p = build_board_pack(result, tmp_path / "bp.html",
                         meeting_date="2026-06-20 RC")
    assert Path(p).exists()
    body = Path(p).read_text(encoding="utf-8")
    # 12-page structure: 1 cover + 11 sections
    assert body.count('class="cover"') == 1
    assert body.count('class="page"') == 11


def test_board_pack_contains_all_sections(tmp_path, result):
    p = build_board_pack(result, tmp_path / "bp.html")
    body = Path(p).read_text(encoding="utf-8")
    for needle in (
        "Executive Summary",
        "KRI Traffic-Light",
        "Capital Position",
        "Liquidity Position",
        "Credit Risk",
        "Market Risk",
        "Operational Risk",
        "Stress Test Results",
        "Scenario Library",
        "Action Items",
        "Audit Trail",
        "Sign-off",
    ):
        assert needle in body, f"missing section: {needle}"


def test_board_pack_renders_korean(tmp_path, result):
    p = build_board_pack(result, tmp_path / "bp.html")
    body = Path(p).read_text(encoding="utf-8")
    for term in ("결재", "리스크 위원회", "근거", "재현"):
        assert term in body


def test_board_pack_includes_abbreviation_dict(tmp_path, result):
    p = build_board_pack(result, tmp_path / "bp.html")
    body = Path(p).read_text(encoding="utf-8")
    assert "약어 사전" in body


# ----- integration into build_full_report_package -------------------------

def test_full_package_includes_board_pack_and_ledger(tmp_path, result):
    from risk_lib.html_report import build_full_report_package
    p = generate_portfolio(seed=42)
    written = build_full_report_package(result, tmp_path, portfolio=p)
    assert "board_pack" in written
    assert "audit_ledger" in written
    assert Path(written["board_pack"]).exists()
    assert Path(written["audit_ledger"]).exists()
    # Ledger is parseable JSON
    data = json.loads(Path(written["audit_ledger"]).read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 10        # at least 10 headline ledger entries
