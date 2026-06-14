"""Unit tests for the v0.9.0 IFRS 9 deep-dive analytics.

Covers SICR multi-trigger decomposition, low-credit-risk exemption,
PD term structure (constant-hazard survival), EIR sensitivity, scenario
weighting and rho sensitivity, provision attribution decomposition, and
the Stage 1/2 backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.provisioning.ifrs9_deep import (
    sicr_decomposition,
    stage_asset_matrix,
    pd_term_structure,
    pd_term_structure_by_segment,
    eir_sensitivity_by_asset,
    amortising_vs_bullet,
    scenario_weight_sensitivity,
    rho_sensitivity,
    coverage_by_asset,
    npl_cure_analysis,
    provision_attribution,
    stage_backtest,
    compute_ifrs9_deep,
    LOW_CREDIT_RISK_GRADES,
    ALT_SCENARIO_WEIGHTS,
    MACRO_VARIABLES_NARRATIVE,
)


# ---------------------------------------------------------------- fixtures

def _mixed_book(n_per: int = 20) -> pd.DataFrame:
    """Three asset classes × clean / SICR / defaulted exposures, plus optional
    SICR-trigger flags so the trigger matrix exercises every column."""
    rng = np.random.default_rng(7)
    rows = []
    for cls in ("corporate", "retail_other", "residential_mortgage"):
        for i in range(n_per):
            dpd = 0 if i < n_per // 2 else (60 if i < int(n_per * 0.8) else 120)
            rows.append({
                "exposure_id": f"{cls[:3]}_{i}",
                "asset_class": cls,
                "ead": 1e8 + i * 1e6,
                "pd": float(np.clip(rng.uniform(0.01, 0.08), 1e-4, 1)),
                "pd_origination": 0.02,
                "lgd": 0.4,
                "maturity": 3,
                "dpd": dpd,
                "watchlist": (i % 7 == 0),
                "notch_drop": 0 if i % 5 else 3,
                "forbearance": (i % 11 == 0),
                "grade": "BBB" if cls == "corporate" and i < 5 else "B",
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- SICR

def test_sicr_triggers_every_column_present():
    book = _mixed_book()
    d = sicr_decomposition(book)
    cols = set(d.summary["trigger"])
    assert cols == {"dpd30", "watchlist", "pd_ratio",
                    "ext_rating", "forbearance", "abs_pd"}


def test_sicr_dpd30_only_in_stage2_range():
    book = _mixed_book()
    d = sicr_decomposition(book)
    # dpd30 trigger by definition cannot fire for Stage 3 (90+) rows
    stage = compute_ecl(book)["stage"]
    per = d.per_exposure.set_index("exposure_id")
    s3 = stage[stage == 3].index
    s3_ids = book.set_index(book.index)["exposure_id"][s3].tolist()
    assert not per.loc[s3_ids, "dpd30"].any()


def test_sicr_stage2_count_matches_compute_ecl():
    book = _mixed_book()
    d = sicr_decomposition(book)
    n_s2 = int((compute_ecl(book)["stage"] == 2).sum())
    assert d.n_stage2_pre_exemption == n_s2


def test_sicr_low_credit_risk_exemption_reduces_stage2():
    book = _mixed_book()
    base = sicr_decomposition(book, apply_low_credit_risk_exemption=False)
    ex   = sicr_decomposition(book, apply_low_credit_risk_exemption=True)
    # exemption can only reduce or hold Stage 2
    assert ex.n_stage2_post_exemption <= base.n_stage2_pre_exemption


def test_low_credit_risk_grades_include_investment_grade():
    assert "BBB" in LOW_CREDIT_RISK_GRADES
    assert "AAA" in LOW_CREDIT_RISK_GRADES
    assert "B" not in LOW_CREDIT_RISK_GRADES


# ---------------------------------------------------------------- Stage matrix

def test_stage_asset_matrix_rectangular():
    book = _mixed_book()
    m = stage_asset_matrix(book)
    assert set(m["stage"]) == {1, 2, 3}
    assert set(m["asset_class"]) == set(book["asset_class"])
    # each combo present
    assert len(m) == 3 * book["asset_class"].nunique()


def test_stage_asset_matrix_ead_reconciles():
    book = _mixed_book()
    m = stage_asset_matrix(book)
    # totals reconcile to compute_ecl
    assert m["ead"].sum() == pytest.approx(book["ead"].sum())


# ---------------------------------------------------------------- PD term

def test_pd_term_structure_marginal_decreasing():
    ts = pd_term_structure(0.03, 5)
    # under constant hazard, marginal PD decreases over time
    assert all(ts["marginal_pd"].diff().dropna() < 0)


def test_pd_term_structure_cum_plus_surv_eq_one():
    ts = pd_term_structure(0.05, 7)
    np.testing.assert_allclose(ts["cumulative_pd"] + ts["survival"], 1.0)


def test_pd_term_structure_by_segment_emits_classes():
    book = _mixed_book()
    df = pd_term_structure_by_segment(book, max_maturity=5)
    assert set(df["asset_class"]) == set(book["asset_class"])
    # year goes 1..5
    assert df["year"].max() == 5 and df["year"].min() == 1


# ---------------------------------------------------------------- EIR sens

def test_eir_sensitivity_monotone_in_eir():
    """Higher EIR ⇒ heavier discount ⇒ smaller lifetime ECL (Stage 2 portion)."""
    book = _mixed_book()
    es = eir_sensitivity_by_asset(book, eir_grid=(0.02, 0.05, 0.10))
    # For at least one asset class with non-trivial Stage 2 weight, ECL must
    # weakly decrease as eir rises.
    pivot = es.pivot(index="eir", columns="asset_class", values="ecl")
    for cls in pivot.columns:
        vals = pivot[cls].tolist()
        assert vals[0] >= vals[-1] - 1e-6     # weak monotone


def test_amortising_vs_bullet_bullet_higher():
    avb = amortising_vs_bullet(0.05, 0.5, 1e9, 4, eir=0.05)
    bullet = avb.loc[avb["type"] == "bullet", "ecl"].iloc[0]
    amort  = avb.loc[avb["type"] == "amortising", "ecl"].iloc[0]
    assert bullet > amort


# ---------------------------------------------------------------- scenario sens

def test_scenario_weight_sensitivity_pessimistic_highest():
    book = _mixed_book()
    ws = scenario_weight_sensitivity(book)
    # 비관적 has the highest severe weight ⇒ highest ECL
    pess = ws.loc[ws["weighting"].str.contains("비관"), "ecl_total"].iloc[0]
    opt  = ws.loc[ws["weighting"].str.contains("낙관"), "ecl_total"].iloc[0]
    assert pess > opt


def test_scenario_weight_first_row_is_base():
    book = _mixed_book()
    ws = scenario_weight_sensitivity(book)
    assert ws.iloc[0]["lift_vs_base"] == pytest.approx(0.0)
    assert ws.iloc[0]["weights"] == (0.50, 0.30, 0.20)


def test_rho_sensitivity_severe_increases_with_rho():
    book = _mixed_book()
    rs = rho_sensitivity(book, rho_grid=(0.10, 0.15, 0.20, 0.25))
    severe = rs.sort_values("rho")["ecl_severe"].tolist()
    assert all(b >= a - 1e-6 for a, b in zip(severe, severe[1:]))


def test_macro_narrative_has_three_scenarios():
    nar = MACRO_VARIABLES_NARRATIVE
    assert set(nar["scenario"]) == {"baseline", "downside", "severe"}
    # severe has the largest downside shocks
    sev = nar[nar["scenario"] == "severe"].iloc[0]
    assert sev["gdp_dev_yr1_pct"] < 0
    assert sev["corp_spread_bp"] >= 300


def test_alt_weights_sum_to_one():
    for label, w in ALT_SCENARIO_WEIGHTS.items():
        assert sum(w) == pytest.approx(1.0), label


# ---------------------------------------------------------------- attribution

def test_coverage_by_asset_returns_one_row_per_class():
    book = _mixed_book()
    cov = coverage_by_asset(book)
    assert set(cov["asset_class"]) == set(book["asset_class"])
    assert (cov["coverage_ratio"] >= 0).all()


def test_npl_cure_analysis_consistent():
    book = _mixed_book()
    cure = npl_cure_analysis(book, base_cure_rate=0.2, collateral_recovery=0.5)
    # residual recovery cannot exceed EAD
    if not cure.by_asset.empty:
        assert (cure.by_asset["residual_recovery"]
                <= cure.by_asset["ead"] + 1).all()
    # 0 ≤ NPL ratio ≤ 1
    assert 0.0 <= cure.npl_ratio_pct_ead <= 1.0


def test_provision_attribution_closes():
    """start + Σ(effects) ≈ end."""
    book = _mixed_book()
    prev = book.copy()
    prev["pd"] = prev["pd"] * 0.8
    prev["lgd"] = prev["lgd"] * 0.9
    prev["ead"] = prev["ead"] * 1.05
    attr = provision_attribution(prev, book)
    start = attr[attr["effect"] == "start"]["value"].iloc[0]
    end   = attr[attr["effect"] == "end"]["value"].iloc[0]
    middle = attr[attr["effect"].isin(["pd", "lgd", "ead", "migration"])]["value"].sum()
    assert (start + middle) == pytest.approx(end, rel=1e-6)


def test_provision_attribution_pd_effect_positive_when_pd_rises():
    """If current PD > previous PD (rest equal), PD effect must be ≥ 0."""
    book = _mixed_book()
    prev = book.copy()
    prev["pd"] = prev["pd"] * 0.5
    attr = provision_attribution(prev, book)
    pd_eff = attr.loc[attr["effect"] == "pd", "value"].iloc[0]
    assert pd_eff >= 0


# ---------------------------------------------------------------- backtest

def test_stage_backtest_rows_for_stage_1_and_2():
    book = _mixed_book()
    prev = book.copy()
    bt = stage_backtest(prev, book)
    assert set(bt["opening_stage"]) == {1, 2}
    assert (bt["realised_default_rate"] >= 0).all()
    assert (bt["realised_default_rate"] <= 1).all()


# ---------------------------------------------------------------- aggregator

def test_compute_ifrs9_deep_returns_all_fields():
    book = _mixed_book()
    res = compute_ifrs9_deep(book, seed=42)
    assert res.sicr is not None
    assert res.sicr_with_exemption is not None
    assert not res.stage_asset.empty
    assert not res.pd_term.empty
    assert not res.eir_sensitivity.empty
    assert not res.amortising_vs_bullet.empty
    assert not res.scenario_weights.empty
    assert not res.rho_sensitivity.empty
    assert not res.macro_narrative.empty
    assert not res.coverage_by_asset.empty
    assert not res.attribution.empty
    assert not res.backtest.empty


def test_compute_ifrs9_deep_deterministic():
    book = _mixed_book()
    a = compute_ifrs9_deep(book, seed=42)
    b = compute_ifrs9_deep(book, seed=42)
    # attribution waterfall is the most seed-sensitive field
    np.testing.assert_allclose(
        a.attribution["value"].values, b.attribution["value"].values,
    )
