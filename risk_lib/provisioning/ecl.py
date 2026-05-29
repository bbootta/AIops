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


def compute_ecl(
    portfolio: pd.DataFrame,
    *,
    eir: float = 0.05,
    sicr_pd_multiple: float = 2.0,
) -> pd.DataFrame:
    """Add IFRS 9 stage and ECL to a portfolio.

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

    stages, ecls = [], []
    for _, r in df.iterrows():
        stage = classify_stage(
            int(r["dpd"]), float(r["pd"]),
            r.get("pd_origination"),
            sicr_pd_multiple=sicr_pd_multiple,
            watchlist=bool(r.get("watchlist", False)),
        )
        if stage == Stage.STAGE_1:
            ecl = twelve_month_ecl(r["pd"], r["lgd"], r["ead"])
        elif stage == Stage.STAGE_2:
            ecl = lifetime_ecl(r["pd"], r["lgd"], r["ead"], r["maturity"], eir=eir)
        else:  # Stage 3: defaulted, PD=1
            ecl = max(r["lgd"], 0.0) * max(r["ead"], 0.0)
        stages.append(int(stage))
        ecls.append(ecl)

    df["stage"] = stages
    df["ecl"] = ecls
    df["coverage_ratio"] = df["ecl"] / df["ead"].replace(0, np.nan)
    return df
