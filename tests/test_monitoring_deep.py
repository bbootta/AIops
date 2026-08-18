"""Unit tests for the v0.10.0 자산건전성 deep modules.

Covers:
  - dpd_bucket_matrix, npl_ratio, default_rate_timeseries, roll_rate_matrix,
    markov_projection (risk_lib/monitoring/deep.py)
  - recovery_curve_dual, lgd_distribution, recovery_by_collateral
    (risk_lib/monitoring/recovery_deep.py)
  - simulate_cure_paths, cure_rate_by_segment (risk_lib/monitoring/cure.py)
  - vintage_by_segment, seasoning_factor, vintage_drift
    (risk_lib/monitoring/vintage_deep.py)
  - Pipeline integration: monitoring_deep field populated
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.monitoring.deep import (
    DEEP_DPD_LABELS, compute_delinquency_deep, dpd_bucket_matrix,
    default_rate_timeseries, markov_projection, npl_ratio, roll_rate_matrix,
)
from risk_lib.monitoring.recovery_deep import (
    compute_recovery_deep, lgd_distribution, recovery_by_collateral,
    recovery_curve_dual,
)
from risk_lib.monitoring.cure import (
    CURE_PRIOR, compute_cure, cure_rate_by_segment, simulate_cure_paths,
)
from risk_lib.monitoring.vintage_deep import (
    compute_vintage_deep, seasoning_factor, vintage_by_segment, vintage_drift,
)


# ----- fixtures --------------------------------------------------------------

@pytest.fixture
def mini_portfolio():
    rng = np.random.default_rng(7)
    n = 60
    asset = (["corporate"] * 20 + ["retail_other"] * 25 +
             ["residential_mortgage"] * 15)
    dpd = list(rng.integers(0, 200, n))
    pd_vals = rng.uniform(0.005, 0.30, n)
    return pd.DataFrame({
        "exposure_id": [f"E{i:04d}" for i in range(n)],
        "asset_class": asset,
        "ead": rng.uniform(1e7, 5e9, n),
        "dpd": dpd,
        "pd": pd_vals,
        "default_12m": (np.array(dpd) >= 90).astype(int),
        "lgd_realized": rng.uniform(0.1, 0.85, n),
    })


# ============================================================ delinquency deep

def test_dpd_bucket_matrix_segments_and_share(mini_portfolio):
    m = dpd_bucket_matrix(mini_portfolio)
    # all five buckets × all three segments → 15 rows (one per pair, even if 0)
    assert set(m["bucket"].astype(str).unique()) == set(DEEP_DPD_LABELS)
    # ead_share sums to 1 per segment
    for seg, sub in m.groupby("segment"):
        assert abs(sub["ead_share"].sum() - 1.0) < 1e-6


def test_npl_ratio_includes_total_row(mini_portfolio):
    npl = npl_ratio(mini_portfolio)
    assert "전체" in npl["segment"].values
    total_row = npl[npl["segment"] == "전체"].iloc[0]
    # 전체 NPL EAD = sum of segment NPL EADs
    seg_sum = npl[npl["segment"] != "전체"]["npl_ead"].sum()
    assert abs(total_row["npl_ead"] - seg_sum) < 1e-3
    # all ratios in [0, 1]
    assert (npl["npl_ratio"] >= 0).all() and (npl["npl_ratio"] <= 1).all()


def test_dr_timeseries_shape(mini_portfolio):
    ts = default_rate_timeseries(mini_portfolio, n_quarters=4, seed=42)
    n_segs = mini_portfolio["asset_class"].nunique()
    assert len(ts) == n_segs * 4
    assert {"quarter", "segment", "dr_count", "dr_ead"} <= set(ts.columns)
    # rates clamped to [0,1)
    assert (ts["dr_count"].between(0, 1)).all()
    assert (ts["dr_ead"].between(0, 1)).all()


def test_roll_matrix_rows_sum_to_one(mini_portfolio):
    rm = roll_rate_matrix(mini_portfolio, seed=42)
    assert list(rm.index) == DEEP_DPD_LABELS
    for lab, row in rm.iterrows():
        assert abs(row.sum() - 1.0) < 1e-6
    # 90+ should be largely absorbing — diagonal entry > 0.7
    assert rm.loc["90+", "90+"] > 0.7


def test_markov_projection_conserves_mass(mini_portfolio):
    rm = roll_rate_matrix(mini_portfolio, seed=42)
    proj = markov_projection(mini_portfolio, rm, horizon_months=3)
    # total EAD per month should equal the starting EAD (Markov preserves mass)
    initial_total = float(proj[proj["month"] == 0]["ead"].sum())
    for m in [0, 1, 2, 3]:
        total = float(proj[proj["month"] == m]["ead"].sum())
        assert abs(total - initial_total) / initial_total < 1e-6


def test_markov_projection_shares_sum_to_one(mini_portfolio):
    rm = roll_rate_matrix(mini_portfolio, seed=42)
    proj = markov_projection(mini_portfolio, rm, horizon_months=3)
    for m, sub in proj.groupby("month"):
        assert abs(sub["share"].sum() - 1.0) < 1e-6


def test_compute_delinquency_deep_deterministic(mini_portfolio):
    r1 = compute_delinquency_deep(mini_portfolio, seed=42)
    r2 = compute_delinquency_deep(mini_portfolio, seed=42)
    pd.testing.assert_frame_equal(r1.roll_matrix, r2.roll_matrix)
    pd.testing.assert_frame_equal(r1.npl_ratio, r2.npl_ratio)


# ============================================================ recovery deep

@pytest.fixture
def workouts_fixture():
    return pd.DataFrame({
        "default_id": ["D1"] * 6 + ["D2"] * 6,
        "months_since_default": [1, 6, 12, 18, 24, 36, 3, 12, 18, 24, 30, 36],
        "recovery_amount": [10, 20, 15, 10, 5, 5, 15, 25, 10, 5, 5, 5],
        "ead_at_default": [100] * 6 + [100] * 6,
    })


def test_recovery_curve_dual_monotone(workouts_fixture):
    curve = recovery_curve_dual(workouts_fixture, horizon_months=36, eir=0.06)
    # both curves are monotone non-decreasing
    assert curve["cum_recovery_undisc"].is_monotonic_increasing
    assert curve["cum_recovery_disc"].is_monotonic_increasing
    # discount factor < 1 in later months ⇒ discounted ≤ undiscounted
    assert (curve["cum_recovery_disc"] <= curve["cum_recovery_undisc"] + 1e-9).all()


def test_recovery_curve_dual_final_matches(workouts_fixture):
    curve = recovery_curve_dual(workouts_fixture, horizon_months=36, eir=0.0)
    # zero discount ⇒ both curves equal
    assert curve["cum_recovery_disc"].iloc[-1] == pytest.approx(
        curve["cum_recovery_undisc"].iloc[-1])


def test_lgd_distribution_quantiles_ordered(mini_portfolio):
    defaults = mini_portfolio[mini_portfolio["default_12m"] == 1]
    out = lgd_distribution(defaults)
    if not out["quantiles"].empty:
        for _, row in out["quantiles"].iterrows():
            assert row["p10"] <= row["p25"] <= row["median"] <= row["p75"] <= row["p90"]


def test_recovery_by_collateral_sorted(mini_portfolio):
    defaults = mini_portfolio[mini_portfolio["default_12m"] == 1]
    coll = recovery_by_collateral(defaults, seed=42)
    if not coll.empty:
        # sorted descending by avg_recovery
        rec = coll["avg_recovery"].tolist()
        assert rec == sorted(rec, reverse=True)
        # avg_lgd + avg_recovery ≈ 1
        assert ((coll["avg_recovery"] + coll["avg_lgd"]) -
                1.0).abs().max() < 1e-6


def test_compute_recovery_deep_runs(mini_portfolio, workouts_fixture):
    out = compute_recovery_deep(mini_portfolio, workouts_fixture, seed=42)
    assert not out.curve_dual.empty
    assert "collateral_type" in out.collateral.columns


# ============================================================ cure analytics

def test_simulate_cure_paths_only_defaulted(mini_portfolio):
    paths = simulate_cure_paths(mini_portfolio, seed=42)
    assert (paths["ead"] > 0).all()
    # n_paths == n_defaults
    assert len(paths) == int(mini_portfolio["default_12m"].sum())


def test_cure_rate_priors_respected(mini_portfolio):
    # mortgage prior > corporate prior > retail prior
    assert CURE_PRIOR["residential_mortgage"] > CURE_PRIOR["corporate"]
    assert CURE_PRIOR["corporate"] > CURE_PRIOR["retail_other"]


def test_cure_rate_by_segment_sums(mini_portfolio):
    paths = simulate_cure_paths(mini_portfolio, seed=42)
    bs = cure_rate_by_segment(paths)
    # 전체 row matches sum
    total = bs[bs["segment"] == "전체"].iloc[0]
    seg_sum_n = bs[bs["segment"] != "전체"]["n_defaults"].sum()
    assert total["n_defaults"] == seg_sum_n


def test_compute_cure_window_propagates(mini_portfolio):
    out = compute_cure(mini_portfolio, seed=42, cure_window=9)
    assert out.cure_window == 9
    # time-to-cure capped by window
    cured = out.paths[out.paths["cured"]]
    assert (cured["time_to_cure_months"] <= 9).all()


# ============================================================ vintage deep

def test_vintage_by_segment_has_all_segments(mini_portfolio):
    vb = vintage_by_segment(mini_portfolio, n_cohorts=6, seed=42)
    seg_in = set(mini_portfolio["asset_class"].unique())
    seg_out = set(vb["segment"].unique())
    assert seg_in <= seg_out  # may include extras for portfolios w/ NA grades


def test_seasoning_factor_positive(mini_portfolio):
    vb = vintage_by_segment(mini_portfolio, n_cohorts=6, seed=42)
    sf = seasoning_factor(vb)
    assert (sf["seasoning_factor"] >= 1.0 - 1e-9).all()


def test_vintage_drift_verdict_categorical(mini_portfolio):
    vb = vintage_by_segment(mini_portfolio, n_cohorts=8, seed=42)
    dr = vintage_drift(vb, recent_n=2, mob_window=1)
    if not dr.empty:
        assert set(dr["verdict"]) <= {"악화", "안정", "개선"}


def test_compute_vintage_deep_aggregates(mini_portfolio):
    out = compute_vintage_deep(mini_portfolio, seed=42, n_cohorts=6)
    assert not out.by_segment.empty
    assert not out.seasoning.empty


# ============================================================ empty-input safety

def test_dpd_bucket_matrix_empty():
    empty = pd.DataFrame(columns=["asset_class", "ead", "dpd", "pd"])
    out = dpd_bucket_matrix(empty)
    assert out.empty


def test_cure_empty_portfolio():
    empty = pd.DataFrame(columns=["asset_class", "default_12m", "ead",
                                   "exposure_id"])
    paths = simulate_cure_paths(empty, seed=42)
    assert paths.empty


def test_recovery_curve_empty():
    out = recovery_curve_dual(pd.DataFrame(
        columns=["default_id", "months_since_default",
                 "recovery_amount", "ead_at_default"]))
    assert out.empty


# ============================================================ pipeline wiring

def test_pipeline_exposes_monitoring_deep():
    from risk_lib.pipeline import run_pipeline
    r = run_pipeline()
    assert {"delinquency", "recovery", "cure", "vintage", "workouts"} \
        <= set(r.monitoring_deep.keys())
    md = r.monitoring_deep
    assert not md["delinquency"].roll_matrix.empty
    assert not md["recovery"].curve_dual.empty
    assert not md["cure"].by_segment.empty
    assert not md["vintage"].by_segment.empty
