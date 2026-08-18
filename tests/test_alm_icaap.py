"""ALM (IRRBB / LCR / NSFR) + ICAAP unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.alm import params as P
from risk_lib.alm.balance_sheet import generate_balance_sheet, REPRICING_BUCKETS
from risk_lib.alm.irrbb import compute_irrbb, shock_curve, SCENARIOS
from risk_lib.alm.lcr import compute_lcr
from risk_lib.alm.nsfr import compute_nsfr
from risk_lib.data_gen import generate_portfolio
from risk_lib.icaap.economic_capital import compute_icaap, concentration_addon_rate
from risk_lib.references import (
    LCR_L2_CAP, LCR_L2B_CAP, LCR_INFLOW_CAP, IRRBB_SHOCK_PARALLEL_BP,
)


@pytest.fixture(scope="module")
def bs():
    p = generate_portfolio(seed=42)
    return generate_balance_sheet(p, capital_total=float(p["ead"].sum()) * 0.14,
                                  seed=42)


# ---- balance sheet -------------------------------------------------------

def test_balance_sheet_balances(bs):
    assert bs.total_assets == pytest.approx(
        bs.loans + sum(bs.hqla.values()) + bs.other_assets, rel=1e-9)
    assert bs.total_assets == pytest.approx(
        bs.funding_total() + bs.equity, rel=1e-9)
    # 사다리 길이는 만기구간 원장이 정한다. 상수 목록과 대조하면 원장이 규정
    # 사다리로 옮길 때(9구간 → [별표 9-1] <표2> 19구간) 이 검사가 먼저 깨진다.
    assert len(bs.repricing) == len(P.build_time_buckets())
    assert (bs.repricing["assets"] >= 0).all()
    assert (bs.repricing["liabilities"] >= 0).all()


def test_balance_sheet_deterministic():
    p = generate_portfolio(seed=42)
    a = generate_balance_sheet(p, 1e12, seed=42)
    b = generate_balance_sheet(p, 1e12, seed=42)
    assert a.total_assets == b.total_assets
    pd.testing.assert_frame_equal(a.repricing, b.repricing)


# ---- IRRBB ---------------------------------------------------------------

def test_shock_curves_shapes():
    t = np.array([0.05, 0.5, 1, 3, 5, 10, 20])
    par = shock_curve("parallel_up", t)
    assert np.allclose(par, IRRBB_SHOCK_PARALLEL_BP / 1e4)
    assert np.allclose(shock_curve("parallel_down", t), -par)
    # short shock decays with tenor; long shock grows with tenor
    s = shock_curve("short_up", t)
    assert (np.diff(s) < 0).all() and s[0] > 0
    steep = shock_curve("steepener", t)
    assert steep[0] < 0 and steep[-1] > 0     # short rates down, long rates up
    flat = shock_curve("flattener", t)
    assert flat[0] > 0 and flat[-1] < 0


def test_irrbb_six_scenarios_and_outlier(bs):
    r = compute_irrbb(bs.repricing, tier1=bs.equity * 0.9)
    assert set(r.delta_eve["scenario"]) == set(SCENARIOS)
    assert len(r.delta_nii) == 2
    assert r.worst_eve_decline >= 0
    assert r.worst_eve_scenario in SCENARIOS
    # worst decline must equal the most negative ΔEVE
    assert r.worst_eve_decline == pytest.approx(
        max(0.0, -float(r.delta_eve["delta_eve"].min())), rel=1e-9)


def test_irrbb_zero_gap_zero_eve():
    rep = pd.DataFrame({"bucket": ["1-2y"], "t_mid": [1.5], "assets": [1e12],
                        "liabilities": [1e12], "gap": [0.0]})
    r = compute_irrbb(rep, tier1=1e11)
    assert float(r.delta_eve["delta_eve"].abs().max()) == 0.0
    assert r.worst_eve_decline == 0.0


# ---- LCR -----------------------------------------------------------------

def test_lcr_caps_and_ratio(bs):
    r = compute_lcr(bs)
    d = r.hqla_detail.set_index("component")
    # included never exceeds post-haircut value
    assert (d["included"] <= d["post_haircut"] + 1e-6).all()
    # L2 caps hold on the final HQLA stack
    l2 = d.loc["Level 2A", "included"] + d.loc["Level 2B", "included"]
    assert l2 <= LCR_L2_CAP * r.hqla_total + 1e-6
    assert d.loc["Level 2B", "included"] <= LCR_L2B_CAP * r.hqla_total + 1e-6
    # inflow cap
    assert r.inflow_capped <= LCR_INFLOW_CAP * r.gross_outflow + 1e-6
    assert r.lcr == pytest.approx(r.hqla_total / r.net_outflow, rel=1e-12)
    assert r.passes()


def _bs_with_hqla(l1: float, l2a: float, l2b: float):
    from risk_lib.alm.balance_sheet import BalanceSheet
    return BalanceSheet(
        total_assets=10e12, loans=7e12,
        hqla={"level_1": l1, "level_2a": l2a, "level_2b": l2b},
        other_assets=10e12 - 7e12 - l1 - l2a - l2b,
        funding={"retail_stable": 3e12, "retail_less_stable": 2e12,
                 "corporate_operational": 1e12, "corporate_non_operational": 1e12,
                 "wholesale_fi_lt6m": 1e12, "wholesale_fi_6to12m": 0.3e12,
                 "funding_gt1y": 0.2e12},
        equity=1.5e12,
        repricing=pd.DataFrame({"bucket": [], "t_mid": [], "assets": [],
                                "liabilities": [], "gap": []}),
        asset_split={},
    )


def test_lcr_l2b_cap_binds_alone():
    """Only the 15% L2B cap binding → L2B lands exactly at 15% of HQLA."""
    # post-haircut: L1=3.0, L2A=0.0425, L2B=0.75 → L2 total well under 40%
    r = compute_lcr(_bs_with_hqla(3.0e12, 0.05e12, 1.5e12))
    d = r.hqla_detail.set_index("component")
    assert d.loc["Level 2B", "included"] == pytest.approx(
        LCR_L2B_CAP * r.hqla_total, rel=1e-6)


def test_lcr_both_caps_bind_official_formula():
    """Both caps binding → HQLA equals the LCR30.47 closed form (5/3·L1)."""
    r = compute_lcr(_bs_with_hqla(0.2e12, 0.1e12, 2.0e12))
    l1 = 0.2e12
    # with both adjustments binding, HQLA collapses to L1·(1 + 2/3) = 5/3·L1
    assert r.hqla_total == pytest.approx(l1 * 5 / 3, rel=1e-9)
    d = r.hqla_detail.set_index("component")
    l2 = d.loc["Level 2A", "included"] + d.loc["Level 2B", "included"]
    assert l2 == pytest.approx(LCR_L2_CAP * r.hqla_total, rel=1e-6)


# ---- NSFR ----------------------------------------------------------------

def test_nsfr_weighted_sums(bs):
    r = compute_nsfr(bs)
    assert r.asf_total == pytest.approx(
        float((r.asf["amount"] * r.asf["factor"]).sum()), rel=1e-12)
    assert r.rsf_total == pytest.approx(
        float((r.rsf["amount"] * r.rsf["factor"]).sum()), rel=1e-12)
    assert r.nsfr == pytest.approx(r.asf_total / r.rsf_total, rel=1e-12)
    assert r.passes()


# ---- ICAAP ---------------------------------------------------------------

def test_concentration_addon_capped():
    assert concentration_addon_rate(0.0, 0.0) == 0.0
    assert concentration_addon_rate(1.0, 1.0) == 0.15   # cap binds


def test_icaap_diversification_and_grades():
    r = compute_icaap(credit_ec=8e11, market_ec=1e11, op_ec=1.5e11,
                      irrbb_ec=0.8e11, hhi_sector=0.10, hhi_country=0.27,
                      available_capital=2.0e12)
    # diversified EC between max standalone and simple sum
    assert max(r.ec_by_type["ec"]) <= r.ec_diversified <= r.ec_standalone_sum
    assert r.diversification_benefit >= 0
    assert r.grade == "GREEN" and r.passes()

    red = compute_icaap(credit_ec=8e11, market_ec=1e11, op_ec=1.5e11,
                        irrbb_ec=0.8e11, hhi_sector=0.1, hhi_country=0.27,
                        available_capital=0.9e12)
    assert red.grade == "RED" and not red.passes()


def test_icaap_perfect_correlation_equals_sum():
    """With ρ=1 everywhere the diversified EC equals the simple sum."""
    import risk_lib.icaap.economic_capital as ec_mod
    import risk_lib.references as refs
    ones = [[1.0] * 4 for _ in range(4)]
    orig = refs.ICAAP_CORRELATION
    try:
        refs.ICAAP_CORRELATION = ones
        ec_mod.ICAAP_CORRELATION = ones
        r = compute_icaap(credit_ec=5e11, market_ec=2e11, op_ec=1e11,
                          irrbb_ec=1e11, hhi_sector=0.0, hhi_country=0.0,
                          available_capital=2e12)
        assert r.ec_diversified == pytest.approx(r.ec_standalone_sum, rel=1e-9)
    finally:
        refs.ICAAP_CORRELATION = orig
        ec_mod.ICAAP_CORRELATION = orig
