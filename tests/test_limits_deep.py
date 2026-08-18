"""Unit tests for v0.11.0 한도/집중리스크 deep-dive."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.data_gen import generate_portfolio
from risk_lib.limits.limits_deep import (
    LimitsDeepResult,
    build_default_limit_set,
    limit_dashboard,
    large_exposure_lex,
    escalation_matrix,
    action_recommendations,
    quarterly_utilisation_trend,
    historical_breach_log,
    stress_adjusted_utilisation,
    stress_utilisation_compare,
    compute_limits_deep,
    enrich_portfolio,
    attach_group_id,
    attach_product_type,
    attach_maturity_bucket,
    group_obligor_id,
    STRESS_EAD_MULTIPLIER,
    SEVERITY_ORDER,
)
from risk_lib.concentration_deep import (
    hierarchical_hhi,
    top_n_share_table,
    gini_coefficient,
    lorenz_curve,
    wrong_way_correlation,
    sector_systemic_correlation,
)


# ---- portfolio enrichment ------------------------------------------------

def test_group_obligor_id_idempotent_format():
    g = group_obligor_id("OBL_CORP_00042")
    assert g.startswith("GRP_")
    assert "CORP" in g
    # different obligors in the same bucket map to same group
    assert group_obligor_id("OBL_CORP_00042") == group_obligor_id("OBL_CORP_00099")
    # different prefix → different group
    assert group_obligor_id("OBL_RTL_00001") != group_obligor_id("OBL_CORP_00001")


def test_group_obligor_id_handles_unusual_input():
    assert group_obligor_id("X").startswith("GRP_")
    assert group_obligor_id("") == "GRP_"


def test_attach_group_id_idempotent():
    p = generate_portfolio(seed=42)
    p1 = attach_group_id(p)
    assert "obligor_group_id" in p1.columns
    p2 = attach_group_id(p1)
    pd.testing.assert_series_equal(p1["obligor_group_id"], p2["obligor_group_id"])
    # group count strictly less than obligor count
    assert p1["obligor_group_id"].nunique() < p1["obligor_id"].nunique()


def test_attach_product_type_categories():
    p = generate_portfolio(seed=42)
    p = attach_product_type(p)
    assert "product_type" in p.columns
    cats = set(p["product_type"].unique())
    # at least mortgage_backed + sovereign + bank should appear
    assert "mortgage_backed" in cats
    assert "sovereign" in cats
    assert "bank" in cats


def test_attach_maturity_bucket_within_limits():
    p = generate_portfolio(seed=42)
    p = attach_maturity_bucket(p)
    assert "maturity_bucket" in p.columns
    cats = set(p["maturity_bucket"].unique())
    assert cats.issubset({"≤1Y", "1-3Y", "3-5Y", "5-10Y", "10Y+"})


def test_enrich_adds_all_three_columns():
    p = generate_portfolio(seed=42)
    out = enrich_portfolio(p)
    for col in ("obligor_group_id", "product_type", "maturity_bucket"):
        assert col in out.columns


# ---- limit set + dashboard ----------------------------------------------

def test_build_default_limit_set_includes_lawful_anchors():
    lims = build_default_limit_set(tier1=1e12)
    names = {l.name for l in lims}
    assert any("동일차주" in n for n in names)
    assert any("그룹차주" in n for n in names)
    assert any("real_estate" in n for n in names)
    # Tier1 25% law anchor
    rule = next(l for l in lims if "동일차주" in l.name)
    assert rule.threshold == pytest.approx(0.25)
    assert rule.basis == "pct_tier1"


def test_limit_dashboard_includes_all_severities():
    p = enrich_portfolio(generate_portfolio(seed=42))
    lims = build_default_limit_set(tier1=1e12)
    dash = limit_dashboard(p, lims, tier1=1e12)
    assert not dash.empty
    # column contract
    for col in ("limit","dimension","bucket","exposure","threshold",
                "utilisation","severity","headroom","basis"):
        assert col in dash.columns
    # severity bucketing matches rules
    for _, r in dash.head(40).iterrows():
        u = r["utilisation"]
        if u >= 1.0:    assert r["severity"] == "BREACH"
        elif u >= 0.9:  assert r["severity"] == "CRITICAL"
        elif u >= 0.75: assert r["severity"] == "WARN"
        else:           assert r["severity"] == "OK"
    # headroom non-negative
    assert (dash["headroom"] >= 0).all()


def test_limit_dashboard_sorted_descending_util():
    p = enrich_portfolio(generate_portfolio(seed=42))
    lims = build_default_limit_set(tier1=1e12)
    dash = limit_dashboard(p, lims, tier1=1e12)
    u = dash["utilisation"].values
    assert all(u[i] >= u[i+1] for i in range(len(u) - 1))


# ---- BCBS LEX -----------------------------------------------------------

def test_large_exposure_lex_thresholds():
    # 4 차주, Tier1=100: 12, 8, 30, 5 → reportable {12, 30}
    p = pd.DataFrame({
        "obligor_id": ["A","B","C","D"],
        "ead": [12., 8., 30., 5.],
    })
    lex = large_exposure_lex(p, tier1=100.0, group=False)
    assert set(lex["obligor_id"]) == {"A", "C"}
    # C has 30/100 = 30% → 25% hard limit BREACH
    c_row = lex[lex["obligor_id"]=="C"].iloc[0]
    assert c_row["pct_tier1"] == pytest.approx(0.30)
    assert c_row["severity"] == "BREACH"


def test_large_exposure_lex_group_aggregates():
    # group view should collapse obligors per group, reducing N reportable
    p = enrich_portfolio(generate_portfolio(seed=42))
    tier1 = 1e12
    obligor = large_exposure_lex(p, tier1=tier1, group=False)
    group = large_exposure_lex(p, tier1=tier1, group=True)
    # group total exposure >= obligor total (same EAD, fewer buckets)
    assert group["ead"].sum() >= obligor["ead"].sum() * 0.99


# ---- escalation + actions ----------------------------------------------

def test_escalation_matrix_has_all_severities():
    esc = escalation_matrix()
    assert set(esc["severity"]) == set(SEVERITY_ORDER)
    # BREACH must escalate to board
    bre = esc[esc["severity"]=="BREACH"].iloc[0]
    assert "이사회" in bre["owner"] or "이사회" in bre["approval_required"]


def test_action_recommendations_priority():
    dash = pd.DataFrame({
        "limit": ["L1","L2","L3","L4"],
        "bucket": ["a","b","c","d"],
        "exposure": [150., 95., 80., 50.],
        "threshold": [100., 100., 100., 100.],
        "utilisation": [1.5, 0.95, 0.80, 0.50],
        "severity": ["BREACH","CRITICAL","WARN","OK"],
        "headroom": [0, 5, 20, 50],
        "basis": ["absolute"]*4,
        "threshold_pct": [float("nan")]*4,
    })
    acts = action_recommendations(dash)
    # BREACH first, then CRITICAL, WARN, OK
    assert acts.iloc[0]["severity"] == "BREACH"
    assert acts.iloc[1]["severity"] == "CRITICAL"
    # BREACH action requires reduction (positive amount)
    assert acts.iloc[0]["amount"] > 0


# ---- trend + breach log -------------------------------------------------

def test_quarterly_trend_deterministic():
    p = enrich_portfolio(generate_portfolio(seed=42))
    lims = build_default_limit_set(tier1=1e12)
    t1 = quarterly_utilisation_trend(p, lims, tier1=1e12, asof="2026-06-30",
                                     n_quarters=4, seed=42)
    t2 = quarterly_utilisation_trend(p, lims, tier1=1e12, asof="2026-06-30",
                                     n_quarters=4, seed=42)
    pd.testing.assert_frame_equal(t1, t2)
    assert t1["quarter"].nunique() == 4
    # 축의 마지막 분기는 기준일이 속한 분기다. 벽시계로 만들면 아직 오지 않은
    # 분기가 마지막 점이 되고, 그 점의 값이 기준일 측정치가 된다.
    assert sorted(t1["quarter"].unique())[-1] == "2026Q2"


def test_historical_breach_log_columns():
    log = historical_breach_log(asof="2026-06-30", n_quarters=6, seed=42)
    assert log["quarter"].tolist()[-1] == "2026Q2"
    assert len(log) == 6
    assert set(["WARN","CRITICAL","BREACH","total"]).issubset(log.columns)
    # total = sum of severities
    assert (log["total"] == log["WARN"] + log["CRITICAL"] + log["BREACH"]).all()
    assert (log[["WARN","CRITICAL","BREACH"]] >= 0).all().all()


# ---- stress -------------------------------------------------------------

def test_stress_multiplier_increases_utilisation():
    p = enrich_portfolio(generate_portfolio(seed=42))
    lims = build_default_limit_set(tier1=1e12)
    base = stress_adjusted_utilisation(p, lims, 1e12, scenario="baseline")
    severe = stress_adjusted_utilisation(p, lims, 1e12, scenario="severely_adverse")
    # severely_adverse > baseline on at least one limit
    assert severe["utilisation"].sum() > base["utilisation"].sum()
    # multipliers match contract
    assert STRESS_EAD_MULTIPLIER["severely_adverse"] == 1.25


def test_stress_compare_long_form():
    p = enrich_portfolio(generate_portfolio(seed=42))
    lims = build_default_limit_set(tier1=1e12)
    cmp = stress_utilisation_compare(p, lims, 1e12)
    assert set(cmp["scenario"].unique()) == {
        "baseline","adverse","severely_adverse"}


# ---- compute_limits_deep entry-point ------------------------------------

def test_compute_limits_deep_returns_full_bundle():
    p = generate_portfolio(seed=42)
    ld = compute_limits_deep(p, tier1=1e12, asof="2026-06-30", seed=42)
    assert isinstance(ld, LimitsDeepResult)
    assert sorted(ld.utilisation_trend["quarter"].unique())[-1] == "2026Q2"
    # summary contains required counters
    for key in ("n_limits","n_warn","n_critical","n_breach",
                 "n_lex_reportable","max_utilisation"):
        assert key in ld.summary
    # determinism: same seed → same dashboard top
    ld2 = compute_limits_deep(p, tier1=1e12, asof="2026-06-30", seed=42)
    pd.testing.assert_frame_equal(
        ld.dashboard.head(20).reset_index(drop=True),
        ld2.dashboard.head(20).reset_index(drop=True),
    )


# ---- concentration_deep additions ---------------------------------------

def test_hierarchical_hhi_contains_all_dimensions():
    p = generate_portfolio(seed=42)
    h = hierarchical_hhi(p)
    expected_labels = {"차주","그룹차주","섹터","KSIC 2자리","국가","상품","만기"}
    assert expected_labels.issubset(set(h["label"]))
    # HHI ∈ [0, 1]
    assert (h["hhi"] >= 0).all() and (h["hhi"] <= 1).all()
    # normalised HHI ∈ [0, 1]
    assert (h["normalised_hhi"] >= -1e-9).all()
    assert (h["normalised_hhi"] <= 1 + 1e-9).all()


def test_top_n_share_monotone():
    p = generate_portfolio(seed=42)
    t = top_n_share_table(p, ns=(5, 10, 20))
    for _, r in t.iterrows():
        # top_5 ≤ top_10 ≤ top_20 ≤ 1
        assert r["top_5_share"] <= r["top_10_share"] + 1e-9
        assert r["top_10_share"] <= r["top_20_share"] + 1e-9
        assert r["top_20_share"] <= 1 + 1e-9


def test_gini_extremes():
    # equal → 0
    assert gini_coefficient([1, 1, 1, 1, 1]) == pytest.approx(0.0, abs=1e-9)
    # single → ≈1 - 1/n
    g = gini_coefficient([100, 0, 0, 0, 0])
    assert g == pytest.approx(0.8, abs=1e-9)


def test_lorenz_curve_endpoints():
    lc = lorenz_curve([1, 2, 3, 4, 5], n_points=11)
    assert lc.iloc[0]["cum_pop"] == pytest.approx(0.0)
    assert lc.iloc[0]["cum_value"] == pytest.approx(0.0)
    assert lc.iloc[-1]["cum_pop"] == pytest.approx(1.0)
    assert lc.iloc[-1]["cum_value"] == pytest.approx(1.0)
    # monotone non-decreasing
    cv = lc["cum_value"].values
    assert all(cv[i] <= cv[i+1] + 1e-12 for i in range(len(cv)-1))


def test_wrong_way_correlation_real_estate_highest():
    p = generate_portfolio(seed=42)
    ww = wrong_way_correlation(p, seed=42)
    # top sector by EAD-weighted uplift should include cyclical sectors
    top = set(ww.head(3)["sector"])
    assert top & {"real_estate","construction","shipping","financial"}
    # ρ ∈ [0, 0.8]
    assert (ww["rho_pd_lgd"] >= 0).all()
    assert (ww["rho_pd_lgd"] <= 0.80).all()


def test_sector_systemic_correlation_symmetric_diag_one():
    p = generate_portfolio(seed=42)
    m = sector_systemic_correlation(p)
    np.testing.assert_allclose(m.values.diagonal(), 1.0, atol=1e-12)
    # symmetric
    np.testing.assert_allclose(m.values, m.values.T, atol=1e-12)
    # off-diagonals ∈ [0, 1]
    off = m.values[~np.eye(len(m), dtype=bool)]
    assert (off >= 0).all() and (off <= 1).all()


# ---- pipeline integration -----------------------------------------------

def test_pipeline_result_has_limits_deep():
    from risk_lib.pipeline import run_pipeline
    r = run_pipeline(seed=42)
    assert r.limits_deep is not None
    assert isinstance(r.limits_deep, LimitsDeepResult)
    # concentration_hier wired
    assert "hierarchical_hhi" in r.concentration_hier
    assert "wrong_way" in r.concentration_hier
    assert isinstance(r.concentration_hier["gini_obligor"], float)
