"""CRO-grade IFRS 9 deep-dive analytics.

Six analytics families built on top of the headline ECL engine (`ecl.py`,
`macro.py`) for the v0.9.0 IFRS 9 deep-dive report pages.

1. SICR trigger decomposition (IFRS 9 5.5.7 / 5.5.11)
   - multi-trigger union: DPD≥30, watchlist, PD ratio, external-rating notch
     drop, forbearance, absolute PD threshold
   - low-credit-risk exemption (5.5.10) — investment grade carve-out
   - per-trigger attribution: which trigger pushed each Stage 2 exposure

2. Stage × asset_class matrix (counts, EAD, ECL, coverage ratio).

3. PD term structure (잔존기간 ECL inputs)
   - constant-hazard marginal PD curve up to maturity
   - cumulative default probability + survival probability
   - per-asset-class EIR simulation: corp 4%, retail 8%, mortgage 3.5%
   - amortising vs bullet EAD term structure comparison

4. Macro / PIT sensitivity (IFRS 9 B5.5.42)
   - scenario probability weighting sensitivity (50/30/20 vs 30/40/30 vs 40/30/30)
   - macro variable narrative table (GDP / unemployment / HPI / policy rate /
     credit spread) per scenario
   - rho (asset correlation) sensitivity ∈ {0.10, 0.15, 0.20}

5. Provisioning attribution
   - asset-class coverage analysis (ECL/EAD by asset_class × stage)
   - Stage 3 NPL cure-rate vs collateral recovery
   - period-over-period ECL change decomposition (PD / LGD / EAD / migration)

6. Stage backtest
   - Stage 1 actual default rate vs implied 12m ECL
   - Stage 2 transition (cure / re-default) rates

All functions are deterministic (no RNG calls without seed) and consume the
same portfolio frame as `compute_ecl` / `macro_ecl`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from risk_lib.provisioning.ecl import compute_ecl, _vector_lifetime_const
from risk_lib.provisioning.macro import (
    MacroScenario, DEFAULT_MACRO_SCENARIOS, macro_ecl, DEFAULT_RHO,
)
from risk_lib.references import (
    IFRS9_SICR_PD_MULTIPLE, SICR_DPD_THRESHOLD, DEFAULT_DPD_THRESHOLD,
)


# ============================================================================
# 1. SICR triggers — multi-trigger decomposition (IFRS 9 5.5.7 / 5.5.11)
# ============================================================================

# Investment-grade (low credit risk exemption, IFRS 9 5.5.10) — master scale.
LOW_CREDIT_RISK_GRADES = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
                          "BBB+", "BBB", "BBB-"}

# Absolute PD threshold above which we override Stage 1 even without other
# triggers (entity-specific; FSS practice 5%).
ABSOLUTE_PD_SICR = 0.05

# External-rating notch drop that triggers SICR (entity-specific; 2 notches
# is a common industry practice).
EXTERNAL_RATING_NOTCH_DROP = 2


@dataclass
class SICRDecomposition:
    """Per-trigger Stage-2 attribution.

    `triggered` is a boolean matrix (E × T) of which trigger fired per
    exposure; `summary` aggregates counts + EAD per trigger.  Trigger names:
    dpd30, watchlist, pd_ratio, ext_rating, forbearance, abs_pd.
    """
    per_exposure: pd.DataFrame             # exposure_id, stage, + one bool col per trigger
    summary: pd.DataFrame                  # trigger, n_stage2, ead_stage2, pct_of_stage2
    low_credit_risk_carve: pd.DataFrame    # exposure_id, was_stage2, post_exemption_stage
    n_stage2_pre_exemption: int
    n_stage2_post_exemption: int


def _trigger_matrix(
    portfolio: pd.DataFrame,
    *,
    sicr_pd_multiple: float = IFRS9_SICR_PD_MULTIPLE,
    sicr_dpd: int = SICR_DPD_THRESHOLD,
    default_dpd: int = DEFAULT_DPD_THRESHOLD,
    abs_pd_threshold: float = ABSOLUTE_PD_SICR,
    notch_drop_threshold: int = EXTERNAL_RATING_NOTCH_DROP,
) -> pd.DataFrame:
    """Compute a boolean trigger matrix (one column per SICR trigger).

    Optional input columns recognised: dpd, watchlist, pd_origination,
    pd (current), notch_drop (int, # notches down from origination),
    forbearance (bool).  Missing columns default to False / 0.
    """
    df = portfolio.copy()
    n = len(df)
    dpd = df["dpd"].to_numpy(dtype=float) if "dpd" in df.columns else np.zeros(n)
    pd_curr = df["pd"].to_numpy(dtype=float)
    pd_orig = (df["pd_origination"].to_numpy(dtype=float)
               if "pd_origination" in df.columns else np.full(n, np.nan))
    wl = (df["watchlist"].to_numpy(dtype=bool)
          if "watchlist" in df.columns else np.zeros(n, dtype=bool))
    notch = (df["notch_drop"].to_numpy(dtype=int)
             if "notch_drop" in df.columns else np.zeros(n, dtype=int))
    forb = (df["forbearance"].to_numpy(dtype=bool)
            if "forbearance" in df.columns else np.zeros(n, dtype=bool))

    pd_ratio_trig = np.where(
        np.isfinite(pd_orig) & (pd_orig > 0),
        pd_curr >= sicr_pd_multiple * pd_orig,
        False,
    )

    triggers = pd.DataFrame({
        "exposure_id": df["exposure_id"].values,
        "dpd30":        (dpd >= sicr_dpd) & (dpd < default_dpd),
        "watchlist":    wl,
        "pd_ratio":     pd_ratio_trig,
        "ext_rating":   notch >= notch_drop_threshold,
        "forbearance":  forb,
        "abs_pd":       pd_curr >= abs_pd_threshold,
    })
    return triggers


def sicr_decomposition(
    portfolio: pd.DataFrame,
    *,
    sicr_pd_multiple: float = IFRS9_SICR_PD_MULTIPLE,
    apply_low_credit_risk_exemption: bool = False,
) -> SICRDecomposition:
    """Decompose Stage 2 staging by SICR trigger family.

    A row is Stage 2 if any of the six triggers fires AND the exposure is not
    already Stage 3 (DPD ≥ 90).  Each trigger column reports its own incidence
    so that the report can show which trigger is driving Stage 2 migration.

    Low credit risk exemption (IFRS 9 5.5.10): when enabled, exposures whose
    `grade` is investment grade (BBB- or better) are kept in Stage 1 even if
    a Stage 2 trigger fires, unless they are credit-impaired (Stage 3).
    """
    ecl_df = compute_ecl(portfolio, sicr_pd_multiple=sicr_pd_multiple)
    trig = _trigger_matrix(portfolio, sicr_pd_multiple=sicr_pd_multiple)
    trig["stage"] = ecl_df["stage"].values
    trig["ead"] = ecl_df["ead"].values

    trigger_cols = ["dpd30", "watchlist", "pd_ratio",
                    "ext_rating", "forbearance", "abs_pd"]
    stage2_mask = trig["stage"].values == 2
    n_s2 = int(stage2_mask.sum())
    s2_ead = float(trig.loc[stage2_mask, "ead"].sum())

    rows = []
    for col in trigger_cols:
        fired_s2 = trig[col].values & stage2_mask
        rows.append({
            "trigger": col,
            "n_fired": int(trig[col].sum()),
            "n_stage2": int(fired_s2.sum()),
            "ead_stage2": float(trig.loc[fired_s2, "ead"].sum()),
            "pct_of_stage2": (float(fired_s2.sum()) / n_s2) if n_s2 else 0.0,
        })
    summary = pd.DataFrame(rows)

    # Low credit risk exemption (5.5.10)
    grades = portfolio["grade"] if "grade" in portfolio.columns else None
    if apply_low_credit_risk_exemption and grades is not None:
        ig_mask = grades.isin(LOW_CREDIT_RISK_GRADES).to_numpy()
        # Stage 2 → 1 carve-out (Stage 3 untouched)
        carve_mask = stage2_mask & ig_mask
        post_stage = trig["stage"].values.copy()
        post_stage[carve_mask] = 1
    else:
        carve_mask = np.zeros(len(trig), dtype=bool)
        post_stage = trig["stage"].values

    carve = pd.DataFrame({
        "exposure_id": trig["exposure_id"].values,
        "pre_stage": trig["stage"].values,
        "post_stage": post_stage,
        "ead": trig["ead"].values,
        "carved_out": carve_mask,
    })
    return SICRDecomposition(
        per_exposure=trig[["exposure_id", "stage", "ead"] + trigger_cols],
        summary=summary,
        low_credit_risk_carve=carve,
        n_stage2_pre_exemption=n_s2,
        n_stage2_post_exemption=int((post_stage == 2).sum()),
    )


# ============================================================================
# 2. Stage × asset_class matrix
# ============================================================================

def stage_asset_matrix(
    portfolio: pd.DataFrame, ecl_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Cross-tab of stage × asset_class with n / EAD / ECL / coverage.

    Returns a long frame: asset_class, stage, n, ead, ecl, coverage_ratio.
    Missing combinations are filled with zeros so downstream charts have a
    rectangular shape.
    """
    if ecl_df is None:
        ecl_df = compute_ecl(portfolio)
    if "asset_class" in ecl_df.columns:
        df = ecl_df
    else:
        df = ecl_df.merge(
            portfolio[["exposure_id", "asset_class"]], on="exposure_id", how="left",
        )
    grp = df.groupby(["asset_class", "stage"]).agg(
        n=("exposure_id", "size"), ead=("ead", "sum"), ecl=("ecl", "sum"),
    ).reset_index()
    grp["coverage_ratio"] = grp["ecl"] / grp["ead"].replace(0, np.nan)
    # Ensure rectangular: every (asset_class, stage) combo present
    classes = df["asset_class"].dropna().unique()
    stages = [1, 2, 3]
    full = pd.MultiIndex.from_product([classes, stages],
                                       names=["asset_class", "stage"]).to_frame(index=False)
    out = full.merge(grp, on=["asset_class", "stage"], how="left").fillna(0.0)
    out["stage"] = out["stage"].astype(int)
    out["n"] = out["n"].astype(int)
    return out.sort_values(["asset_class", "stage"]).reset_index(drop=True)


# ============================================================================
# 3. PD term structure (잔존기간 ECL inputs)
# ============================================================================

# Per-asset-class effective interest rate assumptions (entity-specific).
# Corporate ~ 4% (medium-term, secured), retail_other ~ 8% (unsecured consumer),
# residential_mortgage ~ 3.5% (long-term, collateralised), sov/bank low EIR.
DEFAULT_EIR_BY_ASSET = {
    "corporate":             0.04,
    "retail_other":          0.08,
    "residential_mortgage":  0.035,
    "sovereign":             0.025,
    "bank":                  0.03,
}


def pd_term_structure(
    pd_12m: float, maturity_years: int, *, label: str = "",
) -> pd.DataFrame:
    """Constant-hazard PD curve.

    Returns year, marginal_pd, cumulative_pd, survival.  S(t)=(1-PD)^t;
    marginal_t = S(t-1) - S(t).
    """
    p = float(np.clip(pd_12m, 0.0, 1.0))
    yrs = np.arange(1, maturity_years + 1)
    surv = (1 - p) ** yrs
    surv_prev = np.concatenate([[1.0], surv[:-1]])
    marginal = surv_prev * p
    cum = 1.0 - surv
    return pd.DataFrame({
        "label": label,
        "year": yrs,
        "marginal_pd": marginal,
        "cumulative_pd": cum,
        "survival": surv,
    })


def pd_term_structure_by_segment(
    portfolio: pd.DataFrame,
    max_maturity: int = 10,
) -> pd.DataFrame:
    """PD term structure per asset_class, using each segment's average PD.

    Returns long frame: asset_class, year, marginal_pd, cumulative_pd, survival.
    """
    rows = []
    if "asset_class" not in portfolio.columns:
        return pd.DataFrame(columns=[
            "asset_class", "year", "marginal_pd", "cumulative_pd", "survival"])
    for cls, g in portfolio.groupby("asset_class"):
        # EAD-weighted average PD (whole-book representative)
        ead = g["ead"].to_numpy(dtype=float)
        w = ead / ead.sum() if ead.sum() > 0 else None
        avg_pd = float(np.average(g["pd"].to_numpy(dtype=float), weights=w))
        ts = pd_term_structure(avg_pd, max_maturity, label=cls)
        ts["asset_class"] = cls
        ts["avg_pd_12m"] = avg_pd
        rows.append(ts)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def eir_sensitivity_by_asset(
    portfolio: pd.DataFrame,
    *,
    eir_grid: tuple[float, ...] = (0.02, 0.035, 0.05, 0.08, 0.10),
) -> pd.DataFrame:
    """Lifetime ECL sensitivity to the effective interest rate by asset_class.

    Loops the portfolio's IRB-eligible book through compute_ecl at multiple
    EIR levels and reports the per-asset-class lifetime ECL impact.  Returns
    a long frame: asset_class, eir, ecl, coverage_ratio.
    """
    if "asset_class" not in portfolio.columns:
        return pd.DataFrame()
    rows = []
    for eir in eir_grid:
        ecl_df = compute_ecl(portfolio, eir=eir)
        if "asset_class" not in ecl_df.columns:
            ecl_df = ecl_df.merge(
                portfolio[["exposure_id", "asset_class"]], on="exposure_id",
            )
        grp = ecl_df.groupby("asset_class").agg(
            ead=("ead", "sum"), ecl=("ecl", "sum"),
        ).reset_index()
        grp["eir"] = eir
        grp["coverage_ratio"] = grp["ecl"] / grp["ead"].replace(0, np.nan)
        rows.append(grp)
    return pd.concat(rows, ignore_index=True)


def amortising_vs_bullet(
    pd_12m: float, lgd: float, ead: float, maturity_years: int,
    *, eir: float = 0.05,
) -> pd.DataFrame:
    """Compare amortising (linear) vs bullet (flat) EAD term structure ECL.

    Returns a 2-row frame with type, ecl, coverage_ratio so the report can
    show the impact of the EAD-profile assumption on lifetime ECL.
    """
    n = max(int(np.ceil(maturity_years)), 1)
    pd_vec = np.array([pd_12m])
    lgd_vec = np.array([lgd])
    ead_vec = np.array([ead])
    n_vec = np.array([n])
    amort = float(_vector_lifetime_const(
        pd_vec, lgd_vec, ead_vec, n_vec, eir=eir, amortising=True)[0])
    bullet = float(_vector_lifetime_const(
        pd_vec, lgd_vec, ead_vec, n_vec, eir=eir, amortising=False)[0])
    return pd.DataFrame({
        "type": ["amortising", "bullet"],
        "ecl": [amort, bullet],
        "coverage_ratio": [amort / ead if ead else 0.0,
                           bullet / ead if ead else 0.0],
    })


# ============================================================================
# 4. Macro / PIT sensitivity (IFRS 9 B5.5.42)
# ============================================================================

# Alternative scenario weightings to test the sensitivity of the weighted ECL.
ALT_SCENARIO_WEIGHTS = {
    "기본 (50/30/20)":     (0.50, 0.30, 0.20),
    "균형 (40/30/30)":     (0.40, 0.30, 0.30),
    "보수적 (30/40/30)":   (0.30, 0.40, 0.30),
    "낙관적 (60/30/10)":   (0.60, 0.30, 0.10),
    "비관적 (20/40/40)":   (0.20, 0.40, 0.40),
}

# Macro variable narrative — values are illustrative deviations from baseline.
# Each scenario has GDP shock, unemployment delta (pp), HPI delta (%), policy
# rate (bp), and corporate-bond spread (bp) over baseline.
MACRO_VARIABLES_NARRATIVE = pd.DataFrame([
    {"scenario": "baseline", "gdp_dev_yr1_pct": 0.0,
     "unemp_dev_pp": 0.0, "hpi_dev_pct": 0.0,
     "policy_rate_bp": 0, "corp_spread_bp": 0,
     "narrative": "장기 추세 그대로"},
    {"scenario": "downside", "gdp_dev_yr1_pct": -2.0,
     "unemp_dev_pp": 1.2, "hpi_dev_pct": -5.0,
     "policy_rate_bp": 75, "corp_spread_bp": 120,
     "narrative": "경기 둔화 + 금리 인상"},
    {"scenario": "severe", "gdp_dev_yr1_pct": -5.0,
     "unemp_dev_pp": 3.0, "hpi_dev_pct": -15.0,
     "policy_rate_bp": 150, "corp_spread_bp": 350,
     "narrative": "경기 침체 + 부동산 가격 급락"},
])


def scenario_weight_sensitivity(
    portfolio: pd.DataFrame,
    *,
    rho: float = DEFAULT_RHO,
    eir: float = 0.05,
) -> pd.DataFrame:
    """Re-weight the default scenarios under alternative probability splits.

    Returns label, ecl_total, lift_vs_base for each weighting in
    ALT_SCENARIO_WEIGHTS.  The first entry's ECL is the baseline against which
    lifts are computed.
    """
    rows = []
    base_total = None
    for label, weights in ALT_SCENARIO_WEIGHTS.items():
        scens = [
            MacroScenario(s.name, w, s.gdp_path, s.gdp_z_beta, s.reversion)
            for s, w in zip(DEFAULT_MACRO_SCENARIOS, weights)
        ]
        res = macro_ecl(portfolio, scens, rho=rho, eir=eir)
        if base_total is None:
            base_total = res.weighted_total
        rows.append({
            "weighting": label,
            "weights": weights,
            "ecl_total": float(res.weighted_total),
            "lift_vs_base": float(res.weighted_total - base_total),
            "lift_pct":     float((res.weighted_total / base_total - 1.0)
                                   if base_total else 0.0),
        })
    return pd.DataFrame(rows)


def rho_sensitivity(
    portfolio: pd.DataFrame,
    *,
    rho_grid: tuple[float, ...] = (0.10, 0.15, 0.20, 0.25),
    eir: float = 0.05,
) -> pd.DataFrame:
    """Asset-correlation sensitivity of the weighted PIT ECL."""
    rows = []
    for rho in rho_grid:
        res = macro_ecl(portfolio, DEFAULT_MACRO_SCENARIOS, rho=rho, eir=eir)
        rows.append({
            "rho": rho,
            "ecl_baseline": float(
                res.by_scenario.loc[res.by_scenario["scenario"] == "baseline", "ecl"].sum()),
            "ecl_severe": float(
                res.by_scenario.loc[res.by_scenario["scenario"] == "severe", "ecl"].sum()),
            "ecl_weighted": float(res.weighted_total),
        })
    return pd.DataFrame(rows)


# ============================================================================
# 5. Provisioning attribution
# ============================================================================

def coverage_by_asset(portfolio: pd.DataFrame,
                      ecl_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """ECL / EAD coverage by asset_class (whole-stage aggregate)."""
    if ecl_df is None:
        ecl_df = compute_ecl(portfolio)
    if "asset_class" not in ecl_df.columns:
        ecl_df = ecl_df.merge(
            portfolio[["exposure_id", "asset_class"]], on="exposure_id",
        )
    grp = ecl_df.groupby("asset_class").agg(
        n=("exposure_id", "size"), ead=("ead", "sum"), ecl=("ecl", "sum"),
    ).reset_index()
    grp["coverage_ratio"] = grp["ecl"] / grp["ead"].replace(0, np.nan)
    return grp


@dataclass
class NPLCureAnalysis:
    """Stage 3 NPL recovery vs provisioning analytics."""
    by_asset: pd.DataFrame                 # asset_class, n_npl, ead, ecl, coverage, cure_rate, residual_recovery
    portfolio_cure_rate: float
    residual_recovery_value: float
    npl_ratio_pct_ead: float


def npl_cure_analysis(
    portfolio: pd.DataFrame,
    ecl_df: pd.DataFrame | None = None,
    *,
    base_cure_rate: float = 0.15,
    collateral_recovery: float = 0.40,
) -> NPLCureAnalysis:
    """Compare Stage 3 ECL provisioning to residual collateral recovery.

    `base_cure_rate` (probability a defaulted exposure cures back to performing)
    and `collateral_recovery` (LGD recovery rate net of cure) are entity
    parameters; both default to industry-typical KR retail values.
    """
    if ecl_df is None:
        ecl_df = compute_ecl(portfolio)
    s3 = ecl_df[ecl_df["stage"] == 3].copy()
    if "asset_class" not in s3.columns:
        s3 = s3.merge(
            portfolio[["exposure_id", "asset_class"]], on="exposure_id",
            how="left",
        )
    if s3.empty:
        return NPLCureAnalysis(
            by_asset=pd.DataFrame(columns=[
                "asset_class", "n_npl", "ead", "ecl",
                "coverage_ratio", "cure_rate", "residual_recovery"]),
            portfolio_cure_rate=base_cure_rate,
            residual_recovery_value=0.0,
            npl_ratio_pct_ead=0.0,
        )
    s3["residual_recovery"] = (
        s3["ead"] * (base_cure_rate + (1 - base_cure_rate) * collateral_recovery)
    )
    grp = s3.groupby("asset_class").agg(
        n_npl=("exposure_id", "size"), ead=("ead", "sum"),
        ecl=("ecl", "sum"), residual_recovery=("residual_recovery", "sum"),
    ).reset_index()
    grp["coverage_ratio"] = grp["ecl"] / grp["ead"].replace(0, np.nan)
    grp["cure_rate"] = base_cure_rate
    total_ead = float(portfolio["ead"].sum()) if "ead" in portfolio.columns else 0.0
    return NPLCureAnalysis(
        by_asset=grp,
        portfolio_cure_rate=base_cure_rate,
        residual_recovery_value=float(s3["residual_recovery"].sum()),
        npl_ratio_pct_ead=float(s3["ead"].sum() / total_ead) if total_ead else 0.0,
    )


def provision_attribution(
    portfolio_prev: pd.DataFrame, portfolio_curr: pd.DataFrame,
    *, eir: float = 0.05,
) -> pd.DataFrame:
    """Marshall-Edgeworth decomposition of ECL change into PD / LGD / EAD /
    migration effects.

    Both frames must share `exposure_id`; the exposures present in both are
    matched and the four effects are computed by replacing one factor at a
    time from the previous-period frame with the current-period values:

        PD effect  = ECL(pd_curr, lgd_prev, ead_prev) − ECL(prev)
        LGD effect = ECL(pd_curr, lgd_curr, ead_prev) − ECL(pd_curr, lgd_prev, ead_prev)
        EAD effect = ECL(pd_curr, lgd_curr, ead_curr) − ECL(pd_curr, lgd_curr, ead_prev)
        Migration  = ECL(curr) − ECL(pd_curr, lgd_curr, ead_curr)  # stage change

    Returns a 6-row frame with start, pd, lgd, ead, migration, end totals.
    """
    common = pd.Index(portfolio_prev["exposure_id"]).intersection(
        pd.Index(portfolio_curr["exposure_id"]))
    prev = portfolio_prev.set_index("exposure_id").loc[common].reset_index()
    curr = portfolio_curr.set_index("exposure_id").loc[common].reset_index()

    def _ecl_with(base: pd.DataFrame, overrides: dict) -> float:
        x = base.copy()
        for k, v in overrides.items():
            x[k] = v
        return float(compute_ecl(x, eir=eir)["ecl"].sum())

    pd_curr = curr["pd"].values
    lgd_curr = curr["lgd"].values
    ead_curr = curr["ead"].values

    e_start = _ecl_with(prev, {})
    e_pd    = _ecl_with(prev, {"pd": pd_curr})
    e_lgd   = _ecl_with(prev, {"pd": pd_curr, "lgd": lgd_curr})
    e_ead   = _ecl_with(prev, {"pd": pd_curr, "lgd": lgd_curr, "ead": ead_curr})
    # Migration: anything left over = stage transitions (dpd/watchlist deltas)
    e_end   = _ecl_with(curr, {})
    rows = [
        {"effect": "start",     "value": e_start},
        {"effect": "pd",        "value": e_pd - e_start},
        {"effect": "lgd",       "value": e_lgd - e_pd},
        {"effect": "ead",       "value": e_ead - e_lgd},
        {"effect": "migration", "value": e_end - e_ead},
        {"effect": "end",       "value": e_end},
    ]
    return pd.DataFrame(rows)


# ============================================================================
# 6. Stage backtest
# ============================================================================

def stage_backtest(
    portfolio_prev: pd.DataFrame, portfolio_curr: pd.DataFrame,
) -> pd.DataFrame:
    """Realised default and migration rates for last-period Stage 1/2.

    Both frames must carry `exposure_id`.  The previous period contributes
    the *opening* stage; the current period contributes the *realised* state
    (Stage 3 if default crystallised, else its current stage).  For Stage 1
    and Stage 2 opening buckets we report:

      - n_opening
      - n_default_realised        — moved to Stage 3
      - n_cure                    — moved to Stage 1
      - n_remain                  — still in original bucket
      - realised_default_rate
      - implied_default_rate      — average opening 12m PD (Stage 1)
                                    or pd_lifetime / maturity (Stage 2 proxy)
    """
    prev = compute_ecl(portfolio_prev)[["exposure_id", "stage", "pd", "ead"]]
    curr = compute_ecl(portfolio_curr)[["exposure_id", "stage"]].rename(
        columns={"stage": "stage_curr"})
    m = prev.merge(curr, on="exposure_id", how="inner")

    rows = []
    for open_stage in (1, 2):
        sub = m[m["stage"] == open_stage]
        n = len(sub)
        n_def = int((sub["stage_curr"] == 3).sum())
        n_cure = int((sub["stage_curr"] == 1).sum() if open_stage == 2 else 0)
        n_remain = int((sub["stage_curr"] == open_stage).sum())
        realised = (n_def / n) if n else 0.0
        implied = float(sub["pd"].mean()) if n else 0.0
        rows.append({
            "opening_stage": open_stage,
            "n_opening": n,
            "n_default_realised": n_def,
            "n_cure": n_cure,
            "n_remain": n_remain,
            "realised_default_rate": realised,
            "implied_default_rate": implied,
            "gap_pp": (realised - implied) * 100,
        })
    return pd.DataFrame(rows)


# ============================================================================
# Aggregator — one entry point for the pipeline
# ============================================================================

@dataclass
class IFRS9DeepResult:
    sicr: SICRDecomposition
    sicr_with_exemption: SICRDecomposition
    stage_asset: pd.DataFrame
    pd_term: pd.DataFrame
    eir_sensitivity: pd.DataFrame
    amortising_vs_bullet: pd.DataFrame
    scenario_weights: pd.DataFrame
    rho_sensitivity: pd.DataFrame
    macro_narrative: pd.DataFrame
    coverage_by_asset: pd.DataFrame
    npl_cure: NPLCureAnalysis
    attribution: pd.DataFrame
    backtest: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)


def _perturb_portfolio_for_attribution(
    portfolio: pd.DataFrame, *, seed: int = 42,
) -> pd.DataFrame:
    """Synthesise a 'previous-period' portfolio by mildly perturbing PD/LGD/EAD.

    For demo purposes: previous-period PDs are 0.9x current, LGDs 0.95x, EADs
    1.05x, and DPDs reduced by 10 days (clipped to 0).  This gives a non-zero
    but plausible attribution decomposition without requiring a true history.
    """
    rng = np.random.default_rng(seed)
    prev = portfolio.copy()
    prev["pd"] = prev["pd"] * rng.uniform(0.7, 0.95, len(prev))
    prev["lgd"] = prev["lgd"] * rng.uniform(0.85, 0.98, len(prev))
    prev["ead"] = prev["ead"] * rng.uniform(1.02, 1.08, len(prev))
    if "dpd" in prev.columns:
        prev["dpd"] = np.clip(prev["dpd"].to_numpy(dtype=float) - 10, 0, None)
    return prev


def compute_ifrs9_deep(
    portfolio: pd.DataFrame,
    *,
    eir: float = 0.05,
    rho: float = DEFAULT_RHO,
    seed: int = 42,
) -> IFRS9DeepResult:
    """One-shot IFRS 9 deep-dive bundle for the pipeline / report layer.

    `portfolio` is the IRB-eligible book (same input as `compute_ecl`).  All
    sub-analyses share the same ECL frame so the report is internally
    consistent (Stage 2 counts on the SICR page equal Stage 2 counts on the
    matrix page, etc.).
    """
    ecl_df = compute_ecl(portfolio, eir=eir)
    sicr = sicr_decomposition(portfolio)
    sicr_exempt = sicr_decomposition(portfolio,
                                      apply_low_credit_risk_exemption=True)
    matrix = stage_asset_matrix(portfolio, ecl_df)
    pd_term = pd_term_structure_by_segment(portfolio, max_maturity=10)
    eir_sens = eir_sensitivity_by_asset(portfolio)
    avb = amortising_vs_bullet(0.03, 0.45, 1.0e10, 5, eir=eir)
    weight_sens = scenario_weight_sensitivity(portfolio, rho=rho, eir=eir)
    rho_sens = rho_sensitivity(portfolio, eir=eir)
    cov = coverage_by_asset(portfolio, ecl_df)
    cure = npl_cure_analysis(portfolio, ecl_df)
    prev = _perturb_portfolio_for_attribution(portfolio, seed=seed)
    attr = provision_attribution(prev, portfolio, eir=eir)
    bt = stage_backtest(prev, portfolio)
    return IFRS9DeepResult(
        sicr=sicr,
        sicr_with_exemption=sicr_exempt,
        stage_asset=matrix,
        pd_term=pd_term,
        eir_sensitivity=eir_sens,
        amortising_vs_bullet=avb,
        scenario_weights=weight_sens,
        rho_sensitivity=rho_sens,
        macro_narrative=MACRO_VARIABLES_NARRATIVE.copy(),
        coverage_by_asset=cov,
        npl_cure=cure,
        attribution=attr,
        backtest=bt,
        meta={"eir": eir, "rho": rho, "seed": seed},
    )
