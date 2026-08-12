"""Tests for risk_lib.capital.rwa_deep (CRO-grade RWA deep dive)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from risk_lib.capital.market_risk import compute_market_risk_rwa
from risk_lib.capital.op_risk import (
    BusinessIndicator, business_indicator_component, compute_op_risk_rwa,
)
from risk_lib.capital.rwa_irb import compute_rwa_irb, irb_k_vector
from risk_lib.capital.rwa_sa import compute_rwa_sa
from risk_lib.capital.rwa_deep import (
    sa_decomposition, sa_rating_class_matrix, sa_crm_decomposition,
    irb_decomposition, irb_summary_by_class, irb_histogram,
    lgd_downturn_scenario, firb_simulation,
    parametric_var, sensitivities_charge, market_risk_deep,
    bi_decomposition, bic_bucket_decomposition, op_risk_deep,
    output_floor_schedule, output_floor_breakeven,
    rwa_bridge_detail, compute_rwa_deep,
)


# ---------- fixtures -----------------------------------------------------


@pytest.fixture
def sa_book():
    return pd.DataFrame({
        "exposure_id": ["E1", "E2", "E3", "E4"],
        "asset_class": ["sovereign", "bank", "corporate", "corporate"],
        "ead": [1e9, 2e9, 5e9, 3e9],
        "rating": ["AAA-AA", "A", "BBB", "BB"],
        "ltv": [None, None, None, None],
        "past_due": [False, False, False, False],
    })


@pytest.fixture
def irb_book():
    return pd.DataFrame({
        "exposure_id": ["I1", "I2", "I3", "I4"],
        "asset_class": ["corporate", "corporate",
                        "residential_mortgage", "retail_other"],
        "ead": [10e9, 5e9, 8e9, 3e9],
        "pd": [0.01, 0.03, 0.005, 0.04],
        "lgd": [0.45, 0.50, 0.20, 0.60],
        "maturity": [3.0, 2.5, 5.0, 1.0],
    })


@pytest.fixture
def sa_result(sa_book):
    return compute_rwa_sa(sa_book)


@pytest.fixture
def irb_result(irb_book):
    return compute_rwa_irb(irb_book)


# ---------- SA decomposition ---------------------------------------------


def test_sa_decomposition_shape_and_totals(sa_result):
    out = sa_decomposition(sa_result)
    assert {"asset_class", "n", "ead", "rwa", "avg_rw", "rwa_share"} \
        .issubset(out.columns)
    # rwa_share sums to 1
    assert out["rwa_share"].sum() == pytest.approx(1.0, abs=1e-9)
    # totals reconcile to source
    assert out["rwa"].sum() == pytest.approx(sa_result["rwa"].sum())
    assert out["ead"].sum() == pytest.approx(sa_result["ead"].sum())


def test_sa_decomposition_empty():
    out = sa_decomposition(pd.DataFrame(
        columns=["exposure_id", "asset_class", "ead", "rw", "rwa"]))
    assert out.empty


def test_sa_rating_matrix_columns(sa_result):
    m = sa_rating_class_matrix(sa_result)
    assert {"rating", "asset_class", "rwa"}.issubset(m.columns)
    # All RWA accounted for
    assert m["rwa"].sum() == pytest.approx(sa_result["rwa"].sum())


def test_sa_crm_decomposition_relief(sa_book):
    pre = compute_rwa_sa(sa_book)
    post = sa_book.copy()
    post["ead"] = post["ead"] * 0.5   # mimic 50% CRM relief on EAD
    post_res = compute_rwa_sa(post)
    out = sa_crm_decomposition(pre, post_res)
    total = out[out["asset_class"] == "TOTAL"].iloc[0]
    # relief 50% of pre
    assert total["relief_pct"] == pytest.approx(0.5, abs=1e-9)
    assert total["rwa_post_crm"] == pytest.approx(total["rwa_pre_crm"] * 0.5)


# ---------- IRB decomposition --------------------------------------------


def test_irb_decomposition_adds_rho_and_m_eff(irb_result):
    aug = irb_decomposition(irb_result)
    assert "rho" in aug.columns and "m_eff" in aug.columns
    # ρ for retail revolving would be 0.04, but here we have retail_other
    # asset_class so use the formula range.  Just sanity-check bounds.
    assert (aug["rho"] >= 0.03).all() and (aug["rho"] <= 0.24).all()
    # m_eff respects [1, 5] (CRE31.6)
    assert (aug["m_eff"] >= 1.0).all() and (aug["m_eff"] <= 5.0).all()


def test_irb_summary_reconciles(irb_result):
    s = irb_summary_by_class(irb_result)
    assert s["rwa"].sum() == pytest.approx(irb_result["rwa"].sum())
    assert s["ead"].sum() == pytest.approx(irb_result["ead"].sum())


def test_irb_histogram_bin_count_sums_to_n(irb_result):
    h = irb_histogram(irb_result, "k", bins=5)
    assert h["n"].sum() == len(irb_result)
    assert h["rwa"].sum() == pytest.approx(irb_result["rwa"].sum())


# ---------- LGD downturn -------------------------------------------------


def test_lgd_downturn_max_method_uplift_positive(irb_result):
    out = lgd_downturn_scenario(irb_result, method="max")
    assert out["rwa_downturn"] >= out["rwa_base"]
    # 6% LGD multiplier ⇒ RWA up by ≈ 6%
    assert out["uplift_pct"] == pytest.approx(0.06, abs=1e-6)


def test_lgd_downturn_add_method_strictly_greater(irb_result):
    out = lgd_downturn_scenario(irb_result, method="add", add_pp=0.10)
    assert out["rwa_downturn"] > out["rwa_base"]


def test_lgd_downturn_unknown_method_raises(irb_result):
    with pytest.raises(ValueError):
        lgd_downturn_scenario(irb_result, method="nonsense")


# ---------- FIRB simulation ----------------------------------------------


def test_firb_simulation_uses_fixed_lgd(irb_result):
    out = firb_simulation(irb_result)
    bc = out["by_class"]
    # Corporate row LGD(FIRB) = 0.45
    corp = bc[bc["asset_class"] == "corporate"].iloc[0]
    assert corp["lgd_firb"] == pytest.approx(0.45)
    # Mortgage row LGD(FIRB) = 0.05 (LGD_FLOOR_MORTGAGE)
    mort = bc[bc["asset_class"] == "residential_mortgage"].iloc[0]
    assert mort["lgd_firb"] == pytest.approx(0.05)


def test_firb_delta_sign_consistent_with_lgd_shift(irb_result):
    out = firb_simulation(irb_result)
    bc = out["by_class"]
    # Corporate: AIRB LGD ~0.475 avg; FIRB 0.45 → RWA should fall
    corp = bc[bc["asset_class"] == "corporate"].iloc[0]
    assert (corp["lgd_firb"] - corp["lgd_airb"]) * corp["delta"] >= 0 \
        or abs(corp["delta"]) < 1e-6


# ---------- Market risk --------------------------------------------------


def test_parametric_var_z99_factor():
    positions = pd.DataFrame({
        "risk_class": ["fx"],
        "net_position": [1e12],
    })
    out = parametric_var(positions)
    # σ_fx prior = 0.10; horizon √(10/250) ≈ 0.2; z(0.99)≈2.326 ⇒ VaR ≈ 4.65e10
    assert out.iloc[0]["var_99"] == pytest.approx(
        2.3263478740408408 * 0.10 * math.sqrt(10/250) * 1e12, rel=1e-3)


def test_parametric_var_svar_scaled():
    positions = pd.DataFrame({
        "risk_class": ["equity", "fx"],
        "net_position": [1e12, 5e11],
    })
    out = parametric_var(positions)
    # SVaR = 2.5 * VaR per class
    for _, row in out.iterrows():
        assert row["svar_99"] == pytest.approx(row["var_99"] * 2.5)


def test_sensitivities_charge_components_nonneg():
    positions = pd.DataFrame({
        "risk_class": ["interest_rate", "equity"],
        "net_position": [1e12, 5e11],
    })
    out = sensitivities_charge(positions)
    assert (out["delta"] >= 0).all()
    assert (out["vega"] >= 0).all()
    assert (out["curvature"] >= 0).all()
    assert (out["total"] == out["delta"] + out["vega"] + out["curvature"]).all()


def test_market_risk_deep_reconciles_sa():
    positions = pd.DataFrame({
        "risk_class": ["fx", "equity", "interest_rate"],
        "net_position": [1e12, 5e11, 2e12],
    })
    sa_result = compute_market_risk_rwa(positions)
    out = market_risk_deep(positions, sa_result)
    # SA capital charge by_class sum reconciles
    assert out.by_class["capital_charge"].sum() == \
        pytest.approx(sum(sa_result.by_class.values()))
    # capital_compare contains the SA row equal to sa_result.capital_charge
    sa_row = out.capital_compare[out.capital_compare["approach"] == "SA (MAR40)"]
    assert sa_row.iloc[0]["capital"] == pytest.approx(sa_result.capital_charge)


# ---------- Op risk ------------------------------------------------------


def test_bi_decomposition_shares_sum_to_one():
    bi = BusinessIndicator(ildc=1e12, sc=5e11, fc=2e11)
    out = bi_decomposition(bi)
    components = out.iloc[:3]
    assert components["share"].sum() == pytest.approx(1.0)
    # The 4th row is the total
    assert out.iloc[3]["component"].startswith("BI")


def test_bic_bucket_decomposition_parity():
    """Sum of marginal_bic across buckets equals
    business_indicator_component(bi) for any BI."""
    for bi_val in [5e8, 1e9, 1.5e9, 5e9, 3e10, 5e10, 1.7e12]:
        ref = business_indicator_component(bi_val)
        got = bic_bucket_decomposition(bi_val)["marginal_bic"].sum()
        assert got == pytest.approx(ref, rel=1e-12)


def test_op_risk_deep_ratio_when_lda_zero():
    bi = BusinessIndicator(ildc=1e12, sc=5e11, fc=2e11)
    op_sa = compute_op_risk_rwa(bi)
    out = op_risk_deep(bi, op_sa, lda_var_999=0.0)
    assert math.isnan(out.ratio_sma_lda)


def test_op_risk_deep_ratio_when_lda_positive():
    bi = BusinessIndicator(ildc=1e12, sc=5e11, fc=2e11)
    op_sa = compute_op_risk_rwa(bi)
    out = op_risk_deep(bi, op_sa, lda_var_999=op_sa.orc * 2)
    assert out.ratio_sma_lda == pytest.approx(0.5)


# ---------- Output floor schedule ----------------------------------------


def test_output_floor_schedule_monotone_in_year():
    s = output_floor_schedule(rwa_internal=8e13, rwa_standardised=1.2e14)
    # phase-in is monotone increasing in year (50% → 72.5%)
    assert s["floor_pct"].is_monotonic_increasing
    assert s["floor_amount"].is_monotonic_increasing


def test_output_floor_schedule_binding_when_floor_exceeds_internal():
    s = output_floor_schedule(rwa_internal=8e13, rwa_standardised=1.2e14)
    # 0.725 * 1.2e14 = 8.7e13 > 8e13 ⇒ binding at 2028
    last = s.iloc[-1]
    assert last["is_binding"]
    assert last["rwa_final"] == pytest.approx(0.725 * 1.2e14)


def test_output_floor_breakeven_matches_definition():
    out = output_floor_breakeven(rwa_internal=8e13, rwa_standardised=1.2e14)
    assert out["breakeven_floor"] == pytest.approx(8e13 / 1.2e14)


def test_output_floor_breakeven_zero_standardised():
    out = output_floor_breakeven(rwa_internal=1e13, rwa_standardised=0.0)
    assert math.isnan(out["breakeven_floor"])


# ---------- RWA bridge detail --------------------------------------------


def test_rwa_bridge_detail_share_sums_to_one(sa_result, irb_result):
    b = rwa_bridge_detail(sa_result, irb_result)
    assert b["share_total"].sum() == pytest.approx(1.0, abs=1e-12)
    assert b["rwa"].sum() == pytest.approx(
        sa_result["rwa"].sum() + irb_result["rwa"].sum())


# ---------- compute_rwa_deep (integration) -------------------------------


def test_compute_rwa_deep_smoke(sa_result, irb_result):
    positions = pd.DataFrame({
        "risk_class": ["fx", "equity", "interest_rate"],
        "net_position": [1e12, 5e11, 2e12],
    })
    mkt_sa = compute_market_risk_rwa(positions)
    bi = BusinessIndicator(ildc=1e12, sc=5e11, fc=2e11)
    op_sa = compute_op_risk_rwa(bi, avg_annual_losses_10y=1e9)
    deep = compute_rwa_deep(
        sa_results=sa_result, irb_results=irb_result,
        sa_results_pre_crm=None,
        market_positions=positions, market_sa_result=mkt_sa,
        bi=bi, op_sa_result=op_sa,
        lda_var_999=1e10,
        rwa_internal=8e13, rwa_standardised=1.1e14,
    )
    # core frames are populated
    assert not deep.sa_decomposition.empty
    assert not deep.irb_summary.empty
    assert not deep.floor_schedule.empty
    assert deep.market is not None and deep.op is not None
    # determinism — running twice yields identical numbers
    deep2 = compute_rwa_deep(
        sa_results=sa_result, irb_results=irb_result,
        sa_results_pre_crm=None,
        market_positions=positions, market_sa_result=mkt_sa,
        bi=bi, op_sa_result=op_sa,
        lda_var_999=1e10,
        rwa_internal=8e13, rwa_standardised=1.1e14,
    )
    assert deep.market.var_total == deep2.market.var_total
    assert deep.op.sma_capital == deep2.op.sma_capital


def test_rwa_deep_in_pipeline_result_field():
    """The PipelineResult dataclass exposes rwa_deep as a field, kept
    optional so old reports continue to work."""
    from risk_lib.pipeline import PipelineResult
    fields = {f.name for f in PipelineResult.__dataclass_fields__.values()}
    assert "rwa_deep" in fields
