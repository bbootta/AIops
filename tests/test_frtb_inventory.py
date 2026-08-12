"""Tests for FRTB IMA + Model Inventory modules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.frtb import (
    plat_test, rfet_test, backtest_var, compute_ima_capital,
    _spearman, _ks, _zone_spearman, _zone_ks, _backtest_zone,
)
from risk_lib.model_inventory import (
    ModelInventoryEntry, build_standard_inventory, summarise_inventory,
)


# ----- PLAT primitives ----------------------------------------------------

def test_spearman_perfect_rank():
    a = np.array([1, 2, 3, 4, 5], dtype=float)
    b = np.array([10, 20, 30, 40, 50], dtype=float)
    assert _spearman(a, b) == pytest.approx(1.0, abs=1e-6)


def test_spearman_inverse_rank():
    a = np.array([1, 2, 3, 4, 5], dtype=float)
    b = np.array([5, 4, 3, 2, 1], dtype=float)
    assert _spearman(a, b) == pytest.approx(-1.0, abs=1e-6)


def test_ks_identical_distributions():
    a = np.linspace(0, 1, 100)
    assert _ks(a, a.copy()) == pytest.approx(0.0, abs=1e-9)


def test_ks_disjoint_distributions():
    a = np.linspace(0, 0.5, 100)
    b = np.linspace(0.5, 1.0, 100)
    assert _ks(a, b) > 0.5


def test_zone_classification():
    assert _zone_spearman(0.85) == "green"
    assert _zone_spearman(0.75) == "amber"
    assert _zone_spearman(0.50) == "red"
    assert _zone_ks(0.05) == "green"
    assert _zone_ks(0.10) == "amber"
    assert _zone_ks(0.20) == "red"


def test_plat_well_aligned_green():
    rng = np.random.default_rng(42)
    hpl = rng.normal(0, 10, 250)
    rtpl = hpl * 0.97 + rng.normal(0, 1.0, 250)
    res = plat_test(hpl, rtpl)
    assert res.overall_zone == "green"


def test_plat_misaligned_red():
    rng = np.random.default_rng(42)
    hpl = rng.normal(0, 10, 250)
    rtpl = rng.normal(0, 10, 250)   # independent
    res = plat_test(hpl, rtpl)
    assert res.overall_zone in ("red", "amber")


# ----- RFET / NMRF --------------------------------------------------------

def test_rfet_all_modellable():
    """Dense price history → all factors modellable."""
    df = pd.DataFrame({f"f{i}": np.random.normal(100, 5, 200) for i in range(5)})
    res = rfet_test(df)
    assert res.n_modellable == 5
    assert res.n_nmrf == 0


def test_rfet_sparse_nmrf():
    """Factors with few observations are NMRF."""
    sparse = np.full(20, 100.0)  # only 20 < 24
    df = pd.DataFrame({"sparse": sparse, "dense": np.random.normal(100, 5, 20)})
    # Override observations on dense to be 30
    df = pd.DataFrame({
        "sparse": [100.0] * 20 + [np.nan] * 10,
        "dense":  [100.0] * 30,
    })
    res = rfet_test(df)
    assert not bool(res.factors.loc[res.factors["risk_factor"] == "sparse", "modellable"].iloc[0])
    assert bool(res.factors.loc[res.factors["risk_factor"] == "dense", "modellable"].iloc[0])


# ----- Backtesting traffic light ------------------------------------------

def test_backtest_zone_green():
    z, m, f = _backtest_zone(2)
    assert z == "green" and m == 1.50 and f is False


def test_backtest_zone_yellow_graduated():
    """5–9 exceptions → graduated multiplier 1.70 → 1.92."""
    assert _backtest_zone(5)[1] == 1.70
    assert _backtest_zone(7)[1] == 1.83
    assert _backtest_zone(9)[1] == 1.92


def test_backtest_zone_red():
    z, m, f = _backtest_zone(15)
    assert z == "red" and m == 2.00 and f is True


def test_backtest_var_smoke():
    rng = np.random.default_rng(42)
    pnl = rng.normal(0, 1, 250)
    var = np.full(250, 2.326)        # 99% normal → ~2.5 exceptions expected
    r = backtest_var(pnl, var)
    assert r.zone == "green"


# ----- IMA capital --------------------------------------------------------

def test_ima_capital_active_path():
    rng = np.random.default_rng(42)
    hpl = rng.normal(0, 10, 250)
    rtpl = hpl * 0.97 + rng.normal(0, 1.0, 250)
    plat = plat_test(hpl, rtpl)
    rfet = rfet_test(pd.DataFrame({"f1": np.full(40, 100.0)}))
    bt = backtest_var(rng.normal(0, 1, 250), np.full(250, 2.326))
    ima = compute_ima_capital(es_97_5=5e9, plat=plat, rfet=rfet,
                               backtest=bt, sa_charge=8e9)
    assert ima.pla_status == "active"
    assert ima.ima_capital > 0
    # ima_capital = es * multiplier + nmrf_addon
    expected = 5e9 * bt.multiplier + rfet.nmrf_capital_addon
    assert ima.ima_capital == pytest.approx(expected, rel=1e-9)


def test_ima_capital_forced_sa_on_plat_red():
    """A red PLAT zone forces SA fallback with 30% surcharge."""
    rng = np.random.default_rng(42)
    hpl = rng.normal(0, 10, 250)
    rtpl = rng.normal(0, 10, 250)   # uncorrelated → red
    plat = plat_test(hpl, rtpl)
    rfet = rfet_test(pd.DataFrame({"f1": np.full(40, 100.0)}))
    bt = backtest_var(rng.normal(0, 1, 250), np.full(250, 2.326))
    ima = compute_ima_capital(es_97_5=5e9, plat=plat, rfet=rfet,
                               backtest=bt, sa_charge=10e9)
    assert ima.pla_status == "forced_SA"
    assert ima.ima_capital == 0
    assert ima.sa_capital_fallback == pytest.approx(10e9 * 1.30, rel=1e-9)


# ----- Model inventory ----------------------------------------------------

def test_inventory_builds_with_all_tiers():
    inv = build_standard_inventory()
    tiers = {e.tier for e in inv}
    assert 1 in tiers and 2 in tiers and 3 in tiers


def test_inventory_summary():
    inv = build_standard_inventory()
    s = summarise_inventory(inv)
    assert s.total == len(inv)
    assert sum(s.by_tier.values()) == s.total
    assert sum(s.by_status.values()) == s.total


def test_inventory_overdue_detection():
    """Entry with past next_due is overdue."""
    e = ModelInventoryEntry(
        model_id="X", name="X", tier=1, owner="t",
        status="PROD", last_validation="2025-01-01", next_due="2025-02-01",
        citation="-", purpose="t")
    assert e.is_overdue(today="2025-03-15")
    assert e.days_overdue(today="2025-03-15") > 0


def test_inventory_not_overdue():
    e = ModelInventoryEntry(
        model_id="X", name="X", tier=1, owner="t",
        status="PROD", last_validation="2025-01-01", next_due="2030-01-01",
        citation="-", purpose="t")
    assert not e.is_overdue()


# ----- HTML page registration ---------------------------------------------

def test_frtb_inventory_pages_in_report_set(tmp_path):
    from risk_lib import generate_portfolio, run_pipeline
    from risk_lib.html_report import build_full_report_package
    p = generate_portfolio(seed=42)
    res = run_pipeline(p, seed=42)
    written = build_full_report_package(res, tmp_path, portfolio=p)
    assert "ops/56_frtb_ima.html" in written
    assert "ops/57_model_inventory.html" in written
    import os
    assert os.path.getsize(written["ops/56_frtb_ima.html"]) > 5000
    assert os.path.getsize(written["ops/57_model_inventory.html"]) > 5000
