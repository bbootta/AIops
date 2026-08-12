"""Tests for systemic risk aggregation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from risk_lib.case_studies import run_all_banks, BANK7_2026Q1
from risk_lib.systemic import (
    compute_srisk, compute_covar, simulate_contagion,
    contagion_tipping_point, build_systemic_report, build_systemic_html,
)


@pytest.fixture(scope="module")
def analyses():
    return run_all_banks(seed=42, banks=BANK7_2026Q1)


# ----- SRISK --------------------------------------------------------------

def test_srisk_shape_and_share(analyses):
    r = compute_srisk(analyses)
    assert len(r.by_bank) == len(analyses)
    # shares of positive SRISK sum to 1 (or 0 if no shortfall)
    total_share = r.by_bank["srisk_share"].sum()
    assert total_share == pytest.approx(1.0, abs=1e-6) or total_share == 0.0


def test_srisk_larger_banks_contribute_more(analyses):
    """Commercial banks (much larger) should dominate system SRISK."""
    r = compute_srisk(analyses)
    df = r.by_bank.set_index("bank")
    # KB국민은행 assets >> 카카오뱅크 → higher SRISK
    assert df.loc["KB국민은행", "srisk"] > df.loc["카카오뱅크", "srisk"]


def test_srisk_deterministic(analyses):
    a = compute_srisk(analyses)
    b = compute_srisk(analyses)
    assert a.system_shortfall == pytest.approx(b.system_shortfall, rel=1e-12)


# ----- CoVaR --------------------------------------------------------------

def test_covar_shape(analyses):
    r = compute_covar(analyses, seed=42)
    assert len(r.by_bank) == len(analyses)
    assert r.system_var > 0
    assert {"var_i", "covar", "delta_covar"} <= set(r.by_bank.columns)


def test_covar_sorted_descending(analyses):
    r = compute_covar(analyses, seed=42)
    dc = r.by_bank["delta_covar"].tolist()
    assert dc == sorted(dc, reverse=True)


def test_covar_reproducible(analyses):
    a = compute_covar(analyses, seed=42)
    b = compute_covar(analyses, seed=42)
    assert a.system_var == pytest.approx(b.system_var, rel=1e-12)


# ----- Contagion ----------------------------------------------------------

def test_contagion_matrix_square_zero_diag(analyses):
    r = simulate_contagion(analyses, seed=42)
    m = r.exposure_matrix
    assert m.shape[0] == m.shape[1] == len(analyses)
    # zero diagonal (no self-exposure)
    assert np.allclose(np.diag(m.values), 0)


def test_contagion_more_exposure_more_failures(analyses):
    """Cascade failures are non-decreasing in interbank exposure fraction."""
    low = simulate_contagion(analyses, seed=42, exposure_frac=0.03)
    high = simulate_contagion(analyses, seed=42, exposure_frac=0.60)
    assert high.max_failures >= low.max_failures


def test_contagion_tipping_point_positive(analyses):
    tp = contagion_tipping_point(analyses, seed=42)
    assert 0 < tp <= 0.80


# ----- System report ------------------------------------------------------

def test_systemic_report_assembles(analyses):
    rep = build_systemic_report(analyses, seed=42)
    assert rep.n_banks == len(analyses)
    assert rep.total_assets > 0
    assert 0 < rep.hhi_assets <= 1
    assert rep.srisk.system_shortfall >= 0


def test_systemic_html(tmp_path, analyses):
    p = build_systemic_html(analyses, tmp_path / "sys.html")
    body = Path(p).read_text(encoding="utf-8")
    assert "시스템리스크" in body
    assert "SRISK" in body and "CoVaR" in body
    assert "약어 사전" in body
    assert body.count("<svg") >= 3
