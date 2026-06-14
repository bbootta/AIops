"""Tests for CRO-grade RAPM deep-dive (v0.12.0)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.data_gen import generate_portfolio
from risk_lib.performance.rapm import rapm_report
from risk_lib.performance.rapm_deep import (
    HURDLE_DEFAULT,
    RarocScenario,
    adjusted_raroc_npv,
    breakeven_pricing,
    compute_eva_sva,
    compute_rapm_deep,
    eva_by_dimension,
    industry_benchmark,
    obligor_ranking,
    rapm_scenario,
    raroc_dupont,
    risk_adjusted_pricing_premium,
    waterfall_components,
)


# ---------- fixtures -----------------------------------------------------


@pytest.fixture(scope="module")
def irb_book() -> pd.DataFrame:
    port = generate_portfolio(seed=42)
    return port[port["asset_class"].isin(
        ["corporate", "retail_other", "residential_mortgage"]
    )].reset_index(drop=True)


@pytest.fixture(scope="module")
def rapm_with_dims(irb_book):
    cols = ["exposure_id", "asset_class", "ead", "pd", "lgd",
            "maturity", "revenue", "operating_cost"]
    rep = rapm_report(irb_book[cols], hurdle_rate=HURDLE_DEFAULT)
    rep = rep.merge(irb_book[["exposure_id", "asset_class",
                              "obligor_id", "ead", "maturity"]],
                    on="exposure_id")
    return rep


# ---------- Du Pont decomposition ----------------------------------------


def test_dupont_identity_reconstructs_raroc(rapm_with_dims):
    dp = raroc_dupont(rapm_with_dims,
                      asset_class=rapm_with_dims["asset_class"],
                      ead=rapm_with_dims["ead"])
    # raroc_identity should be close to raroc_direct (same accounting net).
    assert (dp["raroc_identity"] - dp["raroc_direct"]).abs().max() < 1e-6


def test_dupont_contains_all_drivers(rapm_with_dims):
    dp = raroc_dupont(rapm_with_dims,
                      asset_class=rapm_with_dims["asset_class"],
                      ead=rapm_with_dims["ead"])
    for col in ["asset_yield", "capital_velocity", "efficiency",
                "loss_ratio", "rf_benefit", "raroc_identity"]:
        assert col in dp.columns


def test_waterfall_components_sum_to_raroc(rapm_with_dims):
    dp = raroc_dupont(rapm_with_dims,
                      asset_class=rapm_with_dims["asset_class"],
                      ead=rapm_with_dims["ead"])
    row = dp.iloc[0]
    items = waterfall_components(row)
    assert items[-1][0] == "RAROC"
    # The first three labels should sum to the RAROC total (identity).
    assert abs(items[0][1] + items[1][1] + items[2][1] - items[3][1]) < 1e-9


# ---------- EVA / SVA -----------------------------------------------------


def test_eva_sva_identity(rapm_with_dims):
    eva = compute_eva_sva(rapm_with_dims, hurdle_rate=HURDLE_DEFAULT)
    expected = (eva["raroc"] - HURDLE_DEFAULT) * eva["economic_capital"]
    assert (eva["eva"] - expected).abs().max() < 1e-9
    # SVA spread = RAROC - hurdle
    assert (eva["sva_spread"] - (eva["raroc"] - HURDLE_DEFAULT)).abs().max() < 1e-9


def test_eva_by_dimension_aggregates(rapm_with_dims):
    eva = compute_eva_sva(rapm_with_dims)
    agg = eva_by_dimension(eva, rapm_with_dims["asset_class"], "asset_class")
    assert {"asset_class", "n", "ec", "eva"}.issubset(agg.columns)
    # Total EVA preserved
    assert abs(agg["eva"].sum() - eva["eva"].sum()) < 1.0


# ---------- Breakeven pricing --------------------------------------------


def test_breakeven_spread_meets_hurdle_exactly(rapm_with_dims):
    bp = breakeven_pricing(rapm_with_dims, ead=rapm_with_dims["ead"],
                           hurdle_rate=HURDLE_DEFAULT, risk_free_rate=0.03)
    # If revenue equals revenue_breakeven exactly, RAROC = hurdle.
    # We verify via the algebraic identity:
    # net at breakeven = hurdle * EC ⇒ check by reconstructing.
    net_at_be = (bp["revenue_breakeven"] - bp["operating_cost"]
                  - bp["expected_loss"]
                  + 0.03 * bp["economic_capital"])
    expected = HURDLE_DEFAULT * bp["economic_capital"]
    assert (net_at_be - expected).abs().max() < 1e-3


def test_breakeven_gap_sign_matches_hurdle(rapm_with_dims):
    bp = breakeven_pricing(rapm_with_dims, ead=rapm_with_dims["ead"],
                           hurdle_rate=HURDLE_DEFAULT)
    # If spread_gap_bp >= 0 then meets_hurdle is True (definitional)
    assert (bp["meets_hurdle"] == (bp["spread_gap_bp"] >= 0)).all()


def test_pricing_premium_components_nonneg(rapm_with_dims):
    pp = risk_adjusted_pricing_premium(rapm_with_dims,
                                       ead=rapm_with_dims["ead"],
                                       asset_class=rapm_with_dims["asset_class"])
    for col in ["cost_of_risk_bp", "cost_of_capital_bp",
                "operating_cost_bp", "target_margin_bp", "target_spread_bp"]:
        assert (pp[col] >= 0).all(), f"{col} should be non-negative"
    # target spread = sum of components
    expected = (pp["cost_of_risk_bp"] + pp["cost_of_capital_bp"]
                 + pp["operating_cost_bp"] + pp["target_margin_bp"])
    assert (pp["target_spread_bp"] - expected).abs().max() < 1e-6


# ---------- Scenarios ----------------------------------------------------


def test_rapm_scenario_base_matches_book(rapm_with_dims):
    sc = rapm_scenario(rapm_with_dims, ead=rapm_with_dims["ead"])
    base = sc[sc["scenario"] == "base"].iloc[0]
    weights = np.maximum(rapm_with_dims["economic_capital"].to_numpy(), 1e-9)
    expected = float(np.average(rapm_with_dims["raroc"].to_numpy(),
                                 weights=weights))
    assert abs(base["raroc_weighted"] - expected) < 1e-6


def test_rapm_scenario_pd_shock_lowers_raroc(rapm_with_dims):
    sc = rapm_scenario(rapm_with_dims, ead=rapm_with_dims["ead"])
    base = sc[sc["scenario"] == "base"].iloc[0]
    shock = sc[sc["scenario"] == "pd_+50%"].iloc[0]
    assert shock["raroc_weighted"] < base["raroc_weighted"]
    assert shock["expected_loss"] > base["expected_loss"]


def test_rapm_scenario_rate_up_increases_revenue(rapm_with_dims):
    sc = rapm_scenario(rapm_with_dims, ead=rapm_with_dims["ead"])
    base = sc[sc["scenario"] == "base"].iloc[0]
    up = sc[sc["scenario"] == "rate_+100bp"].iloc[0]
    assert up["revenue"] > base["revenue"]
    assert up["raroc_weighted"] > base["raroc_weighted"]


def test_custom_scenario_list_runs(rapm_with_dims):
    sc = rapm_scenario(
        rapm_with_dims, ead=rapm_with_dims["ead"],
        scenarios=[RarocScenario("custom", rate_shock_bp=25, pd_uplift=0.10)],
    )
    assert len(sc) == 1
    assert sc.iloc[0]["scenario"] == "custom"


# ---------- Obligor ranking ----------------------------------------------


def test_obligor_ranking_top_bottom(rapm_with_dims):
    out = obligor_ranking(rapm_with_dims,
                           obligor_id=rapm_with_dims["obligor_id"])
    top, bottom = out["top"], out["bottom"]
    assert len(top) == 20 and len(bottom) == 20
    assert top["eva"].iloc[0] >= top["eva"].iloc[-1]
    assert bottom["eva"].iloc[0] <= bottom["eva"].iloc[-1]
    # Recommendation values from the controlled vocabulary
    allowed = {"OK", "가격 재협상", "거래 축소", "한도 조정 / 종결"}
    assert set(top["recommendation"]).issubset(allowed)
    assert set(bottom["recommendation"]).issubset(allowed)


# ---------- NPV adjustment ------------------------------------------------


def test_adjusted_raroc_npv_columns(rapm_with_dims):
    npv = adjusted_raroc_npv(rapm_with_dims,
                              maturity=rapm_with_dims["maturity"])
    for col in ["npv_net", "raroc_npv", "meets_hurdle_npv"]:
        assert col in npv.columns
    assert len(npv) == len(rapm_with_dims)


# ---------- Industry benchmark -------------------------------------------


def test_industry_benchmark_position_field(rapm_with_dims):
    b = industry_benchmark(rapm_with_dims)
    assert b["position"] in ("top-quartile", "above-median",
                              "below-median", "below-hurdle")
    assert abs((b["own_raroc"] - b["peer_median"]) - b["gap_to_median"]) < 1e-9


# ---------- Orchestrator --------------------------------------------------


def test_compute_rapm_deep_returns_full_result(irb_book):
    result = compute_rapm_deep(irb_book, hurdle_rate=HURDLE_DEFAULT)
    # All expected attributes
    for name in ["rapm_exposure", "dupont", "pricing_premium",
                 "breakeven", "breakeven_by_class", "scenarios",
                 "obligor_top", "obligor_bottom", "eva_by_class",
                 "npv_adjusted", "benchmark", "summary"]:
        assert hasattr(result, name)
    # Summary keys
    for key in ["n_exposures", "ec_total", "el_total", "revenue_total",
                "raroc_weighted", "eva_total", "pass_hurdle_pct",
                "value_creating_pct", "n_repricing", "n_terminate",
                "hurdle_rate", "risk_free_rate"]:
        assert key in result.summary
    assert result.summary["n_exposures"] == len(irb_book)


def test_compute_rapm_deep_deterministic(irb_book):
    r1 = compute_rapm_deep(irb_book, hurdle_rate=0.10)
    r2 = compute_rapm_deep(irb_book, hurdle_rate=0.10)
    assert r1.summary["eva_total"] == pytest.approx(r2.summary["eva_total"])
    assert r1.summary["raroc_weighted"] == pytest.approx(
        r2.summary["raroc_weighted"])


def test_pipeline_exposes_rapm_deep():
    """End-to-end: PipelineResult.rapm_deep is populated."""
    from risk_lib.pipeline import run_pipeline
    res = run_pipeline(seed=42)
    assert res.rapm_deep is not None
    assert res.rapm_deep.summary["n_exposures"] > 0
