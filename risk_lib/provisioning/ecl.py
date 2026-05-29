"""IFRS 9 Expected Credit Loss (ECL) — 3-stage model.

Stage 1 (performing)        : 12-month ECL
Stage 2 (SICR)              : lifetime ECL
Stage 3 (credit-impaired)   : lifetime ECL, PD = 1 (already defaulted)

Lifetime PD term structure derived from the 12-month PD under a constant-hazard
assumption:  S(t) = (1 - PD_12m)^t ;  marginal default in year t = S(t-1) - S(t).
ECL = Σ_t  marginal_PD_t * LGD * EAD_t * DF_t,  DF = 1/(1+EIR)^t.

References: IFRS 9 5.5, 금감원 「대손충당금 적립기준」 (IFRS9 정합).
"""

from __future__ import annotations

from enum import IntEnum

import numpy as np
import pandas as pd


class Stage(IntEnum):
    STAGE_1 = 1
    STAGE_2 = 2
    STAGE_3 = 3


def classify_stage(
    dpd: int,
    pd_current: float,
    pd_origination: float | None = None,
    *,
    sicr_pd_multiple: float = 2.0,
    sicr_dpd: int = 30,
    default_dpd: int = 90,
    watchlist: bool = False,
) -> Stage:
    """Assign IFRS 9 stage.

    SICR (→ Stage 2) triggers on any of: dpd >= 30, on watchlist, or current PD
    has risen to >= `sicr_pd_multiple` x origination PD.
    """
    if dpd >= default_dpd:
        return Stage.STAGE_3
    sicr = dpd >= sicr_dpd or watchlist
    if pd_origination is not None and pd_origination > 0:
        if pd_current >= sicr_pd_multiple * pd_origination:
            sicr = True
    return Stage.STAGE_2 if sicr else Stage.STAGE_1


def twelve_month_ecl(pd_12m: float, lgd: float, ead: float) -> float:
    return max(pd_12m, 0.0) * max(min(lgd, 1.0), 0.0) * max(ead, 0.0)


def _discounted_loss(
    one_year_pds,
    lgd: float,
    ead: float,
    *,
    eir: float = 0.05,
    amortising: bool = True,
) -> float:
    """Σ_t marginal_PD_t · LGD · EAD_t · DF_t over a per-year 1y-PD sequence.

    S(0)=1; marginal_PD_t = S(t-1)·p_t; S(t)=S(t-1)·(1-p_t); DF=1/(1+EIR)^t.
    EAD_t is the beginning-of-year balance under linear amortisation when
    `amortising`, else flat.  Shared by the constant-hazard (TTC) and PIT paths.
    """
    n = len(one_year_pds)
    surv_prev = 1.0
    ecl = 0.0
    for t in range(1, n + 1):
        p_t = one_year_pds[t - 1]
        marginal_pd = surv_prev * p_t
        ead_t = ead * (1 - (t - 1) / n) if amortising else ead
        df = 1.0 / ((1 + eir) ** t)
        ecl += marginal_pd * lgd * ead_t * df
        surv_prev *= (1 - p_t)
    return ecl


def lifetime_ecl(
    pd_12m: float,
    lgd: float,
    ead: float,
    maturity_years: float,
    *,
    eir: float = 0.05,
    amortising: bool = True,
) -> float:
    """Lifetime ECL via constant-hazard marginal PDs, discounted at EIR."""
    pd_12m = float(np.clip(pd_12m, 0.0, 1.0))
    lgd = float(np.clip(lgd, 0.0, 1.0))
    n = max(int(np.ceil(maturity_years)), 1)
    return _discounted_loss([pd_12m] * n, lgd, ead, eir=eir, amortising=amortising)


def _vector_lifetime_const(
    pd_vec: np.ndarray,
    lgd_vec: np.ndarray,
    ead_vec: np.ndarray,
    n_vec: np.ndarray,
    *,
    eir: float = 0.05,
    amortising: bool = True,
) -> np.ndarray:
    """Vectorised constant-hazard lifetime ECL over a book.

    Equivalent to calling `lifetime_ecl` per exposure; constant per-period PD,
    linear amortisation, EIR discounting.  n_vec is the integer year count.
    """
    pd_vec = np.clip(np.asarray(pd_vec, dtype=float), 0.0, 1.0)
    lgd_vec = np.clip(np.asarray(lgd_vec, dtype=float), 0.0, 1.0)
    ead_vec = np.asarray(ead_vec, dtype=float)
    n_vec = np.maximum(np.asarray(n_vec, dtype=int), 1)
    if len(pd_vec) == 0:
        return np.zeros(0)

    n_max = int(n_vec.max())
    t = np.arange(1, n_max + 1)                       # (T,)
    p = pd_vec[:, None]                               # (E,1)
    n = n_vec[:, None]
    surv_prev = (1 - p) ** (t - 1)                    # (E,T)
    marginal = surv_prev * p
    ead_t = ead_vec[:, None] * (1 - (t - 1) / n) if amortising else \
        np.broadcast_to(ead_vec[:, None], (len(pd_vec), n_max))
    df = (1.0 + eir) ** (-t)                          # (T,)
    mask = t <= n                                     # (E,T)
    contrib = marginal * lgd_vec[:, None] * ead_t * df * mask
    return contrib.sum(axis=1)


def classify_stage_vector(
    dpd: np.ndarray,
    pd_current: np.ndarray,
    pd_origination: np.ndarray | None = None,
    *,
    watchlist: np.ndarray | None = None,
    sicr_pd_multiple: float = 2.0,
    sicr_dpd: int = 30,
    default_dpd: int = 90,
) -> np.ndarray:
    """Vectorised IFRS 9 staging (int array of 1/2/3); see `classify_stage`."""
    dpd = np.asarray(dpd, dtype=float)
    pd_current = np.asarray(pd_current, dtype=float)
    n = len(dpd)
    wl = np.zeros(n, dtype=bool) if watchlist is None else np.asarray(watchlist, dtype=bool)
    if pd_origination is not None:
        po = np.asarray(pd_origination, dtype=float)
        pd_jump = (po > 0) & (pd_current >= sicr_pd_multiple * po)
    else:
        pd_jump = np.zeros(n, dtype=bool)
    stage3 = dpd >= default_dpd
    sicr = (dpd >= sicr_dpd) | wl | pd_jump
    return np.where(stage3, 3, np.where(sicr & ~stage3, 2, 1)).astype(int)


def compute_ecl(
    portfolio: pd.DataFrame,
    *,
    eir: float = 0.05,
    sicr_pd_multiple: float = 2.0,
) -> pd.DataFrame:
    """Add IFRS 9 stage and ECL to a portfolio (vectorised).

    Required columns: exposure_id, ead, pd, lgd
    Optional: dpd (default 0), maturity (default 1.0), pd_origination, watchlist
    """
    required = {"exposure_id", "ead", "pd", "lgd"}
    missing = required - set(portfolio.columns)
    if missing:
        raise ValueError(f"portfolio missing columns: {missing}")

    df = portfolio.copy()
    if "dpd" not in df.columns:
        df["dpd"] = 0
    if "maturity" not in df.columns:
        df["maturity"] = 1.0

    pd_arr = df["pd"].to_numpy(dtype=float)
    lgd = df["lgd"].to_numpy(dtype=float)
    ead = df["ead"].to_numpy(dtype=float)
    watchlist = (df["watchlist"].to_numpy(dtype=bool) if "watchlist" in df.columns
                 else None)
    pd_orig = (df["pd_origination"].to_numpy(dtype=float)
               if "pd_origination" in df.columns else None)

    stage = classify_stage_vector(
        df["dpd"].to_numpy(dtype=float), pd_arr, pd_orig,
        watchlist=watchlist, sicr_pd_multiple=sicr_pd_multiple,
    )

    n_vec = np.maximum(np.ceil(df["maturity"].to_numpy(dtype=float)).astype(int), 1)
    ecl_12m = np.maximum(pd_arr, 0.0) * np.clip(lgd, 0.0, 1.0) * np.maximum(ead, 0.0)
    ecl_life = _vector_lifetime_const(pd_arr, lgd, ead, n_vec, eir=eir)
    ecl_def = np.maximum(lgd, 0.0) * np.maximum(ead, 0.0)
    ecl = np.select([stage == 1, stage == 2, stage == 3],
                    [ecl_12m, ecl_life, ecl_def])

    df["stage"] = stage
    df["ecl"] = ecl
    df["coverage_ratio"] = df["ecl"] / df["ead"].replace(0, np.nan)
    return df
