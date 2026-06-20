"""Tests for risk_lib.xva and risk_lib.sensitivities — Top-IB grade."""

from __future__ import annotations

from math import isclose

import numpy as np
import pandas as pd
import pytest

from risk_lib.xva import (
    XVAInputs, compute_xva, cva, dva, fva, colva, mva,
    compute_xva_portfolio, synthesise_xva_portfolio,
)
from risk_lib.sensitivities import (
    bs_greeks, dv01, cs01, synthesise_trading_book, desk_aggregate,
)


# ----- XVA primitives ------------------------------------------------------

def _flat_curve():
    t = np.linspace(0.25, 3.0, 12)
    epe = 100e9 * np.ones_like(t)
    ene = 50e9 * np.ones_like(t)
    return t, epe, ene


def test_cva_zero_when_no_default_risk():
    t, epe, _ = _flat_curve()
    assert cva(epe, t, 0.0, 0.6) == pytest.approx(0.0, abs=1e-3)


def test_cva_monotone_in_cds():
    t, epe, _ = _flat_curve()
    a = cva(epe, t, 50.0, 0.6)
    b = cva(epe, t, 200.0, 0.6)
    assert b > a > 0


def test_dva_symmetry_with_cva():
    """DVA is structurally identical to CVA on the negative-exposure side."""
    t, _, ene = _flat_curve()
    own_cds = 80
    own_lgd = 0.6
    expected = cva(ene, t, own_cds, own_lgd)
    assert dva(ene, t, own_cds, own_lgd) == pytest.approx(expected, rel=1e-12)


def test_fva_proportional_to_spread():
    t, epe, _ = _flat_curve()
    a = fva(epe, t, 50)
    b = fva(epe, t, 100)
    assert b == pytest.approx(2 * a, rel=1e-9)


def test_colva_nonneg_and_zero_when_epe_le_ene():
    t = np.linspace(0.25, 3.0, 12)
    # if EPE ≤ ENE always, ColVA = 0
    epe = 20e9 * np.ones_like(t); ene = 100e9 * np.ones_like(t)
    assert colva(epe, ene, t, 10) == pytest.approx(0.0, abs=1e-3)
    # otherwise positive
    assert colva(100e9 * np.ones_like(t), 20e9 * np.ones_like(t), t, 10) > 0


def test_mva_zero_when_no_im():
    t = np.linspace(0.25, 3.0, 12)
    assert mva(0, t, 50) == 0.0


def test_xva_portfolio_smoke():
    """Whole-pipeline path: synthesise → compute → aggregate."""
    bank = pd.DataFrame({
        "obligor_id": ["A", "B", "C"],
        "ead": [100e9, 50e9, 200e9],
        "maturity": [2.0, 3.0, 5.0],
    })
    xp = compute_xva_portfolio(bank, seed=42)
    assert len(xp.by_cpty) == 3
    for k in ("cva", "dva", "fva", "colva", "mva", "net_xva"):
        assert k in xp.totals
    assert xp.totals["cva"] > 0
    # Net = CVA - DVA + FVA + ColVA + MVA
    expected = (xp.totals["cva"] - xp.totals["dva"]
                + xp.totals["fva"] + xp.totals["colva"] + xp.totals["mva"])
    assert xp.totals["net_xva"] == pytest.approx(expected, rel=1e-9)


def test_xva_cds_sensitivity_positive():
    """+10bp CDS shock → positive ΔCVA."""
    bank = pd.DataFrame({
        "obligor_id": ["A", "B"], "ead": [100e9, 100e9],
        "maturity": [3.0, 3.0],
    })
    xp = compute_xva_portfolio(bank, seed=7)
    assert xp.cds_sensitivity_per_10bps > 0


# ----- Black-Scholes Greeks ------------------------------------------------

def test_bs_call_delta_at_the_money():
    """For ATM call with vol·√T ≈ small, Δ ≈ Φ(0.5·σ·√T + drift) ≈ 0.5–0.7."""
    g = bs_greeks(100, 100, 1.0, 0.20, 0.05, call=True)
    assert 0.55 < g["delta"] < 0.70
    assert g["gamma"] > 0
    assert g["vega"] > 0
    assert g["theta"] < 0      # time decay
    assert g["price"] > 0


def test_bs_put_call_parity():
    """C - P = S - K·e^(-rT) (Black-Scholes put-call parity)."""
    c = bs_greeks(100, 100, 1.0, 0.20, 0.05, call=True)["price"]
    p = bs_greeks(100, 100, 1.0, 0.20, 0.05, call=False)["price"]
    expected = 100 - 100 * np.exp(-0.05 * 1.0)
    assert (c - p) == pytest.approx(expected, abs=1e-6)


def test_bs_intrinsic_at_expiry():
    """At expiry (t=0) call worth max(S-K,0)."""
    g = bs_greeks(110, 100, 0.0, 0.20, 0.05, call=True)
    assert g["price"] == pytest.approx(10.0, abs=1e-9)


def test_bs_put_delta_negative():
    g = bs_greeks(100, 100, 1.0, 0.20, 0.05, call=False)
    assert g["delta"] < 0


# ----- dv01 / cs01 ---------------------------------------------------------

def test_dv01_zero_at_zero_maturity():
    assert dv01(100e9, 0.0) == 0.0


def test_dv01_increases_with_maturity():
    """5y > 2y dV01."""
    assert dv01(100e9, 5.0) > dv01(100e9, 2.0) > 0


def test_cs01_proportional_to_notional():
    a = cs01(50e9, 5.0, 100)
    b = cs01(100e9, 5.0, 100)
    assert b == pytest.approx(2 * a, rel=1e-9)


# ----- desk aggregates -----------------------------------------------------

def test_trading_book_smoke():
    bank = pd.DataFrame({
        "obligor_id": [f"B{i}" for i in range(10)],
        "ead": [100e9] * 10,
    })
    book = synthesise_trading_book(bank, seed=42)
    ds = desk_aggregate(book)
    assert len(book.trades) > 0
    assert ds.var_linear_99 >= 0
    assert ds.by_kind.shape[0] >= 1
    # PLA residual must be in [0, 1]
    assert 0.0 <= ds.pla_residual <= 1.0


def test_trading_book_var_nonneg():
    bank = pd.DataFrame({"obligor_id": ["A"], "ead": [100e9]})
    book = synthesise_trading_book(bank, seed=42)
    ds = desk_aggregate(book)
    assert ds.var_linear_99 >= 0


# ----- HTML page registration ---------------------------------------------

def test_xva_page_registered_in_report_set(tmp_path):
    """Pages 53 and 54 must appear in the generated package."""
    from risk_lib import generate_portfolio, run_pipeline
    from risk_lib.html_report import build_full_report_package
    p = generate_portfolio(seed=42)
    res = run_pipeline(p, seed=42)
    written = build_full_report_package(res, tmp_path, portfolio=p)
    assert "ops/53_xva_full.html" in written
    assert "ops/54_trading_sensitivities.html" in written
    # files non-empty
    import os
    assert os.path.getsize(written["ops/53_xva_full.html"]) > 5000
    assert os.path.getsize(written["ops/54_trading_sensitivities.html"]) > 5000
