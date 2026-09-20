"""Deep-dive RWA analytics for the CRO report.

Adds analytics that the headline RWA / BIS pipeline already produces — but
broken down to a level a CRO can read off a single page:

  * SA RWA — asset-class composition, rating × asset-class RW matrix,
    before/after CRM decomposition.
  * IRB RWA — per-exposure (PD, LGD, M, ρ, K, RWA) plus LGD downturn and
    AIRB→FIRB switch scenarios.
  * Market risk — parametric VaR(99) and ES(97.5), stressed VaR uplift,
    by-risk-class capital charge.
  * Op risk — Business Indicator decomposition (ILDC/SC/FC) with marginal
    coefficients and SMA vs LDA capital comparison.
  * Output floor — full RBC30.5 phase-in schedule and break-even analysis
    showing at which floor level the floor becomes binding.

Every helper is pure and deterministic so the CRO numbers reproduce.

Reference: Basel III CRE20 / CRE31 / CRE32, MAR20, OPE25, RBC30.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from risk_lib.references import (
    MR_STRESS_MULTIPLIER, MR_VOL_PRIOR, SBM_LITE_CURV_SCALE, SBM_LITE_RW_CURV,
    SBM_LITE_RW_DELTA, SBM_LITE_RW_VEGA,
)
from scipy.stats import norm

from risk_lib.capital.rwa_sa import (
    SA_RISK_WEIGHTS, mortgage_rw_vector, sa_risk_weight_vector,
)
from risk_lib.capital.rwa_irb import irb_k_vector
from risk_lib.capital.op_risk import _BI_BUCKETS, BusinessIndicator
from risk_lib.capital.output_floor import apply_output_floor
from risk_lib.references import (
    OUTPUT_FLOOR_PHASE_IN, OUTPUT_FLOOR_FULLY_LOADED,
    LGD_FLOOR_UNSECURED_CORP, LGD_FLOOR_MORTGAGE,
)


# ============================================================================
# SA decomposition (CRE20)
# ============================================================================


def sa_decomposition(sa_results: pd.DataFrame) -> pd.DataFrame:
    """Per asset-class summary of SA RWA: count, EAD, RWA, avg RW, share.

    Expects the frame returned by :func:`compute_rwa_sa` (has columns
    ``asset_class``, ``ead``, ``rw``, ``rwa``).
    """
    if sa_results.empty:
        return pd.DataFrame(columns=["asset_class", "n", "ead", "rwa",
                                     "avg_rw", "rwa_share"])
    total_rwa = float(sa_results["rwa"].sum()) or 1.0
    g = sa_results.groupby("asset_class").agg(
        n=("exposure_id", "size"),
        ead=("ead", "sum"),
        rwa=("rwa", "sum"),
    ).reset_index()
    g["avg_rw"] = np.where(g["ead"] > 0, g["rwa"] / g["ead"], 0.0)
    g["rwa_share"] = g["rwa"] / total_rwa
    return g.sort_values("rwa", ascending=False).reset_index(drop=True)


def sa_rating_class_matrix(sa_results: pd.DataFrame) -> pd.DataFrame:
    """Rating × asset_class RWA matrix (a heatmap source).

    Returns a long-form frame with columns (rating, asset_class, rwa).
    Asset classes without rating (retail / mortgage) are bucketed under
    the ``N/A`` rating to make the matrix rectangular.
    """
    if sa_results.empty:
        return pd.DataFrame(columns=["rating", "asset_class", "rwa"])
    df = sa_results.copy()
    df["rating"] = df["rating"].fillna("N/A")
    # asset classes that do not consume the rating column use N/A
    no_rating = ~df["asset_class"].isin(["sovereign", "bank", "corporate"])
    df.loc[no_rating, "rating"] = "N/A"
    out = df.groupby(["rating", "asset_class"])["rwa"].sum().reset_index()
    return out


def sa_crm_decomposition(
    sa_book_pre: pd.DataFrame,
    sa_book_post: pd.DataFrame,
) -> pd.DataFrame:
    """Before/after-CRM RWA decomposition.

    Both frames are expected to already carry an ``rwa`` column.  The PRE
    frame represents RWA using ``ead_gross`` (or original EAD) and the POST
    frame uses the CRM-adjusted EAD.  Returns one row per asset class plus
    a TOTAL row.
    """
    pre = (sa_book_pre.groupby("asset_class")["rwa"].sum()
           if "asset_class" in sa_book_pre.columns else pd.Series(dtype=float))
    post = (sa_book_post.groupby("asset_class")["rwa"].sum()
            if "asset_class" in sa_book_post.columns else pd.Series(dtype=float))
    classes = sorted(set(pre.index) | set(post.index))
    rows = []
    for c in classes:
        p = float(pre.get(c, 0.0))
        q = float(post.get(c, 0.0))
        rows.append({
            "asset_class": c, "rwa_pre_crm": p, "rwa_post_crm": q,
            "crm_relief": p - q,
            "relief_pct": (p - q) / p if p > 0 else 0.0,
        })
    p_tot = float(pre.sum()); q_tot = float(post.sum())
    rows.append({
        "asset_class": "TOTAL", "rwa_pre_crm": p_tot, "rwa_post_crm": q_tot,
        "crm_relief": p_tot - q_tot,
        "relief_pct": (p_tot - q_tot) / p_tot if p_tot > 0 else 0.0,
    })
    return pd.DataFrame(rows)


# ============================================================================
# IRB decomposition (CRE31, CRE32)
# ============================================================================


def _correlation_vec(pd_value: np.ndarray, asset_class: np.ndarray) -> np.ndarray:
    """Vectorised CRE31 correlation R(PD, AC) — matches rwa_irb._correlation."""
    pd_value = np.clip(pd_value, 1e-10, 1.0)
    ac = np.asarray([str(a).lower() for a in asset_class])
    wholesale = np.isin(ac, ("corporate", "sovereign", "bank"))
    w50 = (1 - np.exp(-50 * pd_value)) / (1 - math.exp(-50))
    r_wholesale = 0.12 * w50 + 0.24 * (1 - w50)
    w35 = (1 - np.exp(-35 * pd_value)) / (1 - math.exp(-35))
    r_retail_other = 0.03 * w35 + 0.16 * (1 - w35)
    return np.select(
        [wholesale, ac == "residential_mortgage",
         ac == "retail_revolving", ac == "retail_other"],
        [r_wholesale, np.full_like(pd_value, 0.15),
         np.full_like(pd_value, 0.04), r_retail_other],
        default=np.nan,
    )


def irb_decomposition(irb_results: pd.DataFrame) -> pd.DataFrame:
    """Augment compute_rwa_irb output with R (asset correlation) and a
    capped/floored maturity column.  Pure derivation — no new RWA, just
    transparency for the per-exposure table."""
    if irb_results.empty:
        return irb_results.copy()
    df = irb_results.copy()
    df["rho"] = _correlation_vec(df["pd"].to_numpy(dtype=float),
                                 df["asset_class"].to_numpy())
    if "maturity" in df.columns:
        df["m_eff"] = np.clip(df["maturity"].to_numpy(dtype=float), 1.0, 5.0)
    return df


def irb_summary_by_class(irb_results: pd.DataFrame) -> pd.DataFrame:
    """Per asset-class IRB roll-up: count, EAD, weighted PD/LGD/M, K, RWA."""
    if irb_results.empty:
        return pd.DataFrame(columns=["asset_class", "n", "ead", "pd_w",
                                     "lgd_w", "m_w", "k_w", "rwa"])
    df = irb_results
    def w_avg(col: str, weight: str = "ead") -> pd.Series:
        return (df[col] * df[weight]).groupby(df["asset_class"]).sum() / \
               df.groupby("asset_class")[weight].sum()
    out = pd.DataFrame({
        "asset_class": sorted(df["asset_class"].unique()),
    })
    grp = df.groupby("asset_class")
    out["n"] = grp.size().reindex(out["asset_class"]).values
    out["ead"] = grp["ead"].sum().reindex(out["asset_class"]).values
    out["pd_w"] = w_avg("pd").reindex(out["asset_class"]).values
    out["lgd_w"] = w_avg("lgd").reindex(out["asset_class"]).values
    if "maturity" in df.columns:
        out["m_w"] = w_avg("maturity").reindex(out["asset_class"]).values
    else:
        out["m_w"] = np.nan
    out["k_w"] = w_avg("k").reindex(out["asset_class"]).values
    out["rwa"] = grp["rwa"].sum().reindex(out["asset_class"]).values
    return out.sort_values("rwa", ascending=False).reset_index(drop=True)


def irb_histogram(irb_results: pd.DataFrame, col: str = "k",
                  bins: int = 10) -> pd.DataFrame:
    """Histogram counts + RWA sum per bin for the named column.

    Used by the IRB deep-dive page to plot the K (capital coefficient)
    distribution.  Returns columns (bin_lo, bin_hi, n, rwa).
    """
    if irb_results.empty or col not in irb_results.columns:
        return pd.DataFrame(columns=["bin_lo", "bin_hi", "n", "rwa"])
    x = irb_results[col].to_numpy(dtype=float)
    rwa = irb_results["rwa"].to_numpy(dtype=float)
    lo, hi = float(np.nanmin(x)), float(np.nanmax(x))
    if lo == hi:
        hi = lo + 1e-6
    edges = np.linspace(lo, hi, bins + 1)
    idx = np.clip(np.digitize(x, edges) - 1, 0, bins - 1)
    rows = []
    for b in range(bins):
        m = idx == b
        rows.append({
            "bin_lo": float(edges[b]),
            "bin_hi": float(edges[b + 1]),
            "n": int(m.sum()),
            "rwa": float(rwa[m].sum()),
        })
    return pd.DataFrame(rows)


def lgd_downturn_scenario(
    irb_results: pd.DataFrame,
    method: str = "max",
    add_pp: float = 0.10,
) -> dict[str, Any]:
    """Apply a downturn LGD overlay and re-run IRB risk weight function.

    method:
      ``"max"`` — LGD_down = max(LGD, 1.06 * LGD)  (CRE32.41 anchor multiplier)
      ``"add"`` — LGD_down = min(1.0, LGD + add_pp)

    Returns the original and stressed RWA totals + the per-class delta.
    """
    if irb_results.empty:
        return {"rwa_base": 0.0, "rwa_downturn": 0.0, "uplift": 0.0,
                "uplift_pct": 0.0, "by_class": pd.DataFrame()}
    df = irb_results.copy()
    base = float(df["rwa"].sum())
    if method == "max":
        df["lgd_down"] = np.minimum(1.0, np.maximum(df["lgd"], df["lgd"] * 1.06))
    elif method == "add":
        df["lgd_down"] = np.minimum(1.0, df["lgd"] + add_pp)
    else:
        raise ValueError(f"unknown method: {method}")
    k_new = irb_k_vector(
        df["pd"].to_numpy(dtype=float),
        df["lgd_down"].to_numpy(dtype=float),
        df["asset_class"].to_numpy(),
        df.get("maturity", pd.Series(2.5, index=df.index)).to_numpy(dtype=float),
    )
    df["rwa_down"] = k_new * 12.5 * df["ead"]
    rwa_down = float(df["rwa_down"].sum())
    by_class = df.groupby("asset_class").agg(
        rwa_base=("rwa", "sum"),
        rwa_down=("rwa_down", "sum"),
    ).reset_index()
    by_class["uplift"] = by_class["rwa_down"] - by_class["rwa_base"]
    by_class["uplift_pct"] = np.where(
        by_class["rwa_base"] > 0,
        by_class["uplift"] / by_class["rwa_base"], 0.0,
    )
    return {
        "rwa_base": base, "rwa_downturn": rwa_down,
        "uplift": rwa_down - base,
        "uplift_pct": (rwa_down - base) / base if base > 0 else 0.0,
        "method": method, "by_class": by_class,
    }


# FIRB fixed LGDs (CRE32.13).
FIRB_LGD = {
    "corporate_senior_unsecured": 0.45,
    "corporate_subordinated":     0.75,
    "sovereign_unsecured":        0.45,
    "bank_unsecured":             0.45,
    "residential_mortgage":       LGD_FLOOR_MORTGAGE,  # senior secured
    "retail_other":               0.45,
    "retail_revolving":           0.45,
}


def firb_simulation(irb_results: pd.DataFrame) -> dict[str, Any]:
    """Re-run IRB with FIRB fixed LGD assumptions (CRE32.13).

    The harness defaults to AIRB (advanced — bank-supplied LGD).  This
    function shows how RWA would shift if the bank were on FIRB, where
    supervisors fix LGD at 45% for senior unsecured corporate / sovereign /
    bank and 75% for subordinated exposures.
    """
    if irb_results.empty:
        return {"rwa_airb": 0.0, "rwa_firb": 0.0, "delta": 0.0,
                "by_class": pd.DataFrame()}
    df = irb_results.copy()
    ac = df["asset_class"].to_numpy()
    firb_lgd = np.where(
        np.isin(ac, ("corporate", "sovereign", "bank")), 0.45,
        np.where(ac == "residential_mortgage", LGD_FLOOR_MORTGAGE, 0.45),
    )
    df["lgd_firb"] = firb_lgd
    k_firb = irb_k_vector(
        df["pd"].to_numpy(dtype=float),
        df["lgd_firb"],
        df["asset_class"].to_numpy(),
        df.get("maturity", pd.Series(2.5, index=df.index)).to_numpy(dtype=float),
    )
    df["rwa_firb"] = k_firb * 12.5 * df["ead"]
    base = float(df["rwa"].sum()); firb = float(df["rwa_firb"].sum())
    by_class = df.groupby("asset_class").agg(
        rwa_airb=("rwa", "sum"),
        rwa_firb=("rwa_firb", "sum"),
        lgd_airb=("lgd", "mean"),
        lgd_firb=("lgd_firb", "mean"),
    ).reset_index()
    by_class["delta"] = by_class["rwa_firb"] - by_class["rwa_airb"]
    return {
        "rwa_airb": base, "rwa_firb": firb, "delta": firb - base,
        "delta_pct": (firb - base) / base if base > 0 else 0.0,
        "by_class": by_class,
    }


# ============================================================================
# Market risk (MAR20) — parametric VaR / SVaR overlay
# ============================================================================


# 파라메트릭 VaR 의 변동성 사전값과 SVaR 배수. 둘 다 내부 가정이다. MAR20 에
# SVaR 배수 규정은 없다 (SVaR 은 스트레스 관측기간으로 재산출하는 값이다).
# 값은 references.py 내부 가정 구역에 있고 여기서는 이름만 이어 쓴다.
_MR_VOL_PRIOR = MR_VOL_PRIOR
_MR_STRESS_MULTIPLIER = MR_STRESS_MULTIPLIER


def parametric_var(positions: pd.DataFrame,
                   confidence: float = 0.99,
                   horizon_days: int = 10) -> pd.DataFrame:
    """Parametric VaR & 97.5% ES per risk class.

    VaR = z(α) * σ * √(h/250) * |position|.  σ defaults from a supervisory
    prior keyed on the risk class; callers may override by passing a
    ``sigma`` column.
    """
    if positions.empty:
        return pd.DataFrame(columns=["risk_class", "abs_position", "sigma",
                                     "var_99", "es_975", "svar_99"])
    df = positions.copy()
    df["abs_position"] = df["net_position"].abs()
    if "sigma" not in df.columns:
        df["sigma"] = df["risk_class"].map(_MR_VOL_PRIOR).fillna(0.10)
    scale = math.sqrt(horizon_days / 250)
    z = norm.ppf(confidence)
    df["var_99"] = z * df["sigma"] * scale * df["abs_position"]
    # 97.5% ES under normality:  ES = σ * φ(z_α) / (1 - α)
    a = 0.975
    z_a = norm.ppf(a)
    es_mult = norm.pdf(z_a) / (1 - a)
    df["es_975"] = es_mult * df["sigma"] * scale * df["abs_position"]
    df["svar_99"] = df["var_99"] * _MR_STRESS_MULTIPLIER
    by = df.groupby("risk_class").agg(
        abs_position=("abs_position", "sum"),
        sigma=("sigma", "mean"),
        var_99=("var_99", "sum"),
        es_975=("es_975", "sum"),
        svar_99=("svar_99", "sum"),
    ).reset_index()
    return by


@dataclass
class MarketDeepResult:
    by_class: pd.DataFrame          # capital charge by risk_class (SA)
    var_table: pd.DataFrame         # parametric VaR / ES / SVaR
    var_total: float
    svar_total: float
    es_total: float
    sensitivities: pd.DataFrame     # Delta / Vega / Curvature breakdown
    capital_compare: pd.DataFrame   # SA vs VaR+SVaR comparison


def sensitivities_charge(positions: pd.DataFrame) -> pd.DataFrame:
    """Simplified Delta/Vega/Curvature decomposition (FRTB SA, MAR21 lite).

    Each risk class contributes:
      Delta     = position * RW_delta
      Vega      = position * RW_vega           (only equity / IR / commodity)
      Curvature = position * RW_curv * 0.5
    Returns one row per risk class.
    """
    if positions.empty:
        return pd.DataFrame(columns=["risk_class", "delta", "vega",
                                     "curvature", "total"])
    df = positions.copy()
    # SbM 대용 계수. MAR21 의 버킷·상관 구조가 아니다 (references 참조).
    rw_delta, rw_vega, rw_curv = SBM_LITE_RW_DELTA, SBM_LITE_RW_VEGA, SBM_LITE_RW_CURV
    df["abs_position"] = df["net_position"].abs()
    df["delta"]     = df["abs_position"] * df["risk_class"].map(rw_delta).fillna(0.0)
    df["vega"]      = df["abs_position"] * df["risk_class"].map(rw_vega).fillna(0.0)
    df["curvature"] = df["abs_position"] * df["risk_class"].map(rw_curv).fillna(0.0) * SBM_LITE_CURV_SCALE
    by = df.groupby("risk_class").agg(
        delta=("delta", "sum"),
        vega=("vega", "sum"),
        curvature=("curvature", "sum"),
    ).reset_index()
    by["total"] = by["delta"] + by["vega"] + by["curvature"]
    return by


def market_risk_deep(positions: pd.DataFrame,
                     sa_result: Any) -> MarketDeepResult:
    """Run all market-risk deep analytics in one call.

    `sa_result` is the :class:`MarketRiskResult` from
    :func:`compute_market_risk_rwa`.
    """
    by_class = pd.DataFrame([
        {"risk_class": k, "capital_charge": v,
         "rwa": v * 12.5, "share": v / (sum(sa_result.by_class.values()) or 1)}
        for k, v in sa_result.by_class.items()
    ])
    var_t = parametric_var(positions)
    sens = sensitivities_charge(positions)
    var_total = float(var_t["var_99"].sum()) if not var_t.empty else 0.0
    svar_total = float(var_t["svar_99"].sum()) if not var_t.empty else 0.0
    es_total = float(var_t["es_975"].sum()) if not var_t.empty else 0.0
    capital_compare = pd.DataFrame([
        {"approach": "SA (MAR40)", "capital": float(sa_result.capital_charge)},
        {"approach": "VaR 99% (10일)", "capital": var_total},
        {"approach": "SVaR 99% (스트레스)", "capital": svar_total},
        {"approach": "VaR + SVaR (IMA 가산)", "capital": var_total + svar_total},
        {"approach": "Sensitivities (Delta+Vega+Curvature)",
         "capital": float(sens["total"].sum()) if not sens.empty else 0.0},
    ])
    return MarketDeepResult(by_class, var_t, var_total, svar_total,
                            es_total, sens, capital_compare)


# ============================================================================
# Op risk (OPE25) — BI decomposition + SMA vs LDA
# ============================================================================


@dataclass
class OpRiskDeepResult:
    bi_decomp: pd.DataFrame         # ILDC / SC / FC absolute + share
    bucket_decomp: pd.DataFrame     # marginal BIC across bucket 1/2/3
    sma_capital: float              # = ORC
    lda_var_999: float              # input from compute_op_loss
    ratio_sma_lda: float            # SMA / LDA — > 1 means SMA conservative


def bi_decomposition(bi: BusinessIndicator) -> pd.DataFrame:
    """Decompose the Business Indicator into its three components with shares."""
    total = bi.bi or 1.0
    rows = [
        {"component": "ILDC (이자·리스·배당)", "value": bi.ildc,
         "share": bi.ildc / total},
        {"component": "SC (서비스)", "value": bi.sc, "share": bi.sc / total},
        {"component": "FC (금융)", "value": bi.fc, "share": bi.fc / total},
        {"component": "BI (합계)", "value": bi.bi, "share": 1.0},
    ]
    return pd.DataFrame(rows)


def bic_bucket_decomposition(bi_value: float) -> pd.DataFrame:
    """Marginal BIC contribution across the three buckets (OPE25.2)."""
    rows = []
    lower = 0.0
    for i, (upper, coef) in enumerate(_BI_BUCKETS, start=1):
        if bi_value > upper:
            applied = upper - lower
        else:
            applied = max(0.0, bi_value - lower)
        rows.append({
            "bucket": f"Bucket {i}", "lower": lower, "upper": upper,
            "coefficient": coef, "applied": applied,
            "marginal_bic": applied * coef,
        })
        lower = upper
    return pd.DataFrame(rows)


def op_risk_deep(bi: BusinessIndicator, sma_result: Any,
                 lda_var_999: float = 0.0) -> OpRiskDeepResult:
    bi_dec = bi_decomposition(bi)
    bucket_dec = bic_bucket_decomposition(bi.bi)
    sma_cap = float(sma_result.orc)
    ratio = sma_cap / lda_var_999 if lda_var_999 > 0 else float("nan")
    return OpRiskDeepResult(
        bi_decomp=bi_dec, bucket_decomp=bucket_dec,
        sma_capital=sma_cap, lda_var_999=lda_var_999,
        ratio_sma_lda=ratio,
    )


# ============================================================================
# Output floor phase-in (RBC30.5)
# ============================================================================


def output_floor_schedule(rwa_internal: float,
                          rwa_standardised: float) -> pd.DataFrame:
    """Apply the full RBC30.5 phase-in schedule (2023..2028).

    Shows whether the floor is binding at each level and how much add-on
    it would impose this year.
    """
    rows = []
    for year, lvl in sorted(OUTPUT_FLOOR_PHASE_IN.items()):
        res = apply_output_floor(rwa_internal, rwa_standardised, lvl)
        rows.append({
            "year": year, "floor_pct": lvl,
            "floor_amount": res.floor_amount,
            "rwa_final": res.rwa_final,
            "add_on": res.add_on,
            "is_binding": res.is_binding,
        })
    return pd.DataFrame(rows)


def output_floor_breakeven(rwa_internal: float,
                           rwa_standardised: float) -> dict[str, float]:
    """At which floor level does the floor become binding?

    The floor binds when floor * rwa_standardised >= rwa_internal, i.e.
    floor >= rwa_internal / rwa_standardised.  Returns the break-even level
    plus the headroom (difference vs the fully-loaded 72.5%).
    """
    if rwa_standardised <= 0:
        return {"breakeven_floor": float("nan"),
                "headroom_vs_full": float("nan"),
                "current_ratio": float("nan")}
    breakeven = rwa_internal / rwa_standardised
    return {
        "breakeven_floor": breakeven,
        "headroom_vs_full": breakeven - OUTPUT_FLOOR_FULLY_LOADED,
        "current_ratio": breakeven,
    }


# ============================================================================
# RWA bridge by asset class × product (deeper than attribution.rwa_bridge)
# ============================================================================


def rwa_bridge_detail(sa_results: pd.DataFrame,
                      irb_results: pd.DataFrame) -> pd.DataFrame:
    """Asset class × method (SA / IRB) RWA detail for the bridge chart.

    Returns columns (asset_class, method, ead, rwa, share_total).
    """
    rows = []
    if not sa_results.empty:
        for c, sub in sa_results.groupby("asset_class"):
            rows.append({"asset_class": c, "method": "SA",
                         "ead": float(sub["ead"].sum()),
                         "rwa": float(sub["rwa"].sum())})
    if not irb_results.empty:
        for c, sub in irb_results.groupby("asset_class"):
            rows.append({"asset_class": c, "method": "IRB",
                         "ead": float(sub["ead"].sum()),
                         "rwa": float(sub["rwa"].sum())})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    total = df["rwa"].sum() or 1.0
    df["share_total"] = df["rwa"] / total
    return df.sort_values("rwa", ascending=False).reset_index(drop=True)


# ============================================================================
# Convenience: aggregate every deep-dive result
# ============================================================================


@dataclass
class RWADeepResult:
    """Container for the CRO deep-dive numbers used by the report pages."""
    sa_decomposition: pd.DataFrame = field(default_factory=pd.DataFrame)
    sa_rating_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)
    sa_crm: pd.DataFrame = field(default_factory=pd.DataFrame)
    irb_per_exposure: pd.DataFrame = field(default_factory=pd.DataFrame)
    irb_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    irb_k_hist: pd.DataFrame = field(default_factory=pd.DataFrame)
    irb_pd_hist: pd.DataFrame = field(default_factory=pd.DataFrame)
    lgd_downturn: dict[str, Any] = field(default_factory=dict)
    firb: dict[str, Any] = field(default_factory=dict)
    market: MarketDeepResult | None = None
    op: OpRiskDeepResult | None = None
    floor_schedule: pd.DataFrame = field(default_factory=pd.DataFrame)
    floor_breakeven: dict[str, float] = field(default_factory=dict)
    rwa_bridge: pd.DataFrame = field(default_factory=pd.DataFrame)


def compute_rwa_deep(
    sa_results: pd.DataFrame,
    irb_results: pd.DataFrame,
    sa_results_pre_crm: pd.DataFrame | None,
    market_positions: pd.DataFrame,
    market_sa_result: Any,
    bi: BusinessIndicator,
    op_sa_result: Any,
    lda_var_999: float,
    rwa_internal: float,
    rwa_standardised: float,
) -> RWADeepResult:
    """Run every deep-dive analytic in one call.  Pure, deterministic."""
    irb_aug = irb_decomposition(irb_results)
    return RWADeepResult(
        sa_decomposition=sa_decomposition(sa_results),
        sa_rating_matrix=sa_rating_class_matrix(sa_results),
        sa_crm=(sa_crm_decomposition(sa_results_pre_crm, sa_results)
                if sa_results_pre_crm is not None
                else sa_crm_decomposition(sa_results, sa_results)),
        irb_per_exposure=irb_aug,
        irb_summary=irb_summary_by_class(irb_results),
        irb_k_hist=irb_histogram(irb_results, "k", bins=10),
        irb_pd_hist=irb_histogram(irb_results, "pd", bins=10),
        lgd_downturn=lgd_downturn_scenario(irb_results, method="max"),
        firb=firb_simulation(irb_results),
        market=market_risk_deep(market_positions, market_sa_result),
        op=op_risk_deep(bi, op_sa_result, lda_var_999),
        floor_schedule=output_floor_schedule(rwa_internal, rwa_standardised),
        floor_breakeven=output_floor_breakeven(rwa_internal, rwa_standardised),
        rwa_bridge=rwa_bridge_detail(sa_results, irb_results),
    )
