"""CECL (US GAAP ASC 326) vs IFRS 9 provisioning comparison.

A global Top-IB bank reporting under both US GAAP and IFRS must reconcile two
different expected-loss regimes:

  - **IFRS 9** (already in risk_lib.provisioning): 3-stage model. Stage 1 =
    12-month ECL; Stage 2/3 = lifetime ECL. Only "significant increase in
    credit risk" (SICR) exposures carry lifetime loss.

  - **CECL** (ASC 326, Current Expected Credit Losses): *day-1 lifetime* loss
    on the entire portfolio. There is no staging — every performing loan
    carries a lifetime expected loss from origination. Generally more
    conservative (larger allowance) than IFRS 9 in benign conditions because
    Stage 1 loans carry only 12-month loss under IFRS 9 but full lifetime
    under CECL.

This module computes the CECL allowance on the same book and reconciles the
two, so the board can see the GAAP/IFRS gap ("dual-reporting bridge").

Reference: FASB ASC 326 (CECL, 2016), IFRS 9 5.5, BCBS "Regulatory
treatment of accounting provisions" (2017).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class CECLResult:
    total_cecl: float                 # day-1 lifetime allowance
    by_segment: pd.DataFrame          # segment, ead, lifetime_pd, lgd, cecl
    weighted_life_years: float
    macro_overlay: float              # forward-looking adjustment


def compute_cecl(portfolio: pd.DataFrame, *, eir: float = 0.05,
                 macro_factor: float = 1.10) -> CECLResult:
    """Lifetime expected loss on the *entire* book (no staging).

    CECL_i = Σ_t marginal_PD_t · LGD · EAD_t · DF_t over the full remaining
    life of each exposure, with a forward-looking macro overlay.
    """
    df = portfolio.copy()
    if "pd" not in df.columns:
        df["pd"] = 0.01
    if "lgd" not in df.columns:
        df["lgd"] = 0.45
    df["pd"] = df["pd"].fillna(0.01).clip(1e-4, 0.99)
    df["lgd"] = df["lgd"].fillna(0.45).clip(0.05, 0.95)
    df["maturity"] = df.get("maturity", pd.Series(3.0, index=df.index)).fillna(3.0)

    def _lifetime_ecl(pd_12m, lgd, ead, life):
        n = max(int(np.ceil(life)), 1)
        surv = 1.0
        ecl = 0.0
        for t in range(1, n + 1):
            marginal = surv * pd_12m
            ead_t = ead * (1 - (t - 1) / n)          # linear amortisation
            df_t = 1.0 / ((1 + eir) ** t)
            ecl += marginal * lgd * ead_t * df_t
            surv *= (1 - pd_12m)
        return ecl

    df["cecl_raw"] = df.apply(
        lambda r: _lifetime_ecl(r["pd"], r["lgd"], r["ead"], r["maturity"]),
        axis=1)
    df["cecl"] = df["cecl_raw"] * macro_factor       # macro overlay

    seg = df.groupby("asset_class").agg(
        ead=("ead", "sum"),
        lifetime_pd=("pd", "mean"),
        lgd=("lgd", "mean"),
        cecl=("cecl", "sum"),
        life=("maturity", "mean"),
    ).reset_index()

    total = float(df["cecl"].sum())
    w_life = float((df["ead"] * df["maturity"]).sum() / df["ead"].sum())
    overlay = float(df["cecl"].sum() - df["cecl_raw"].sum())
    return CECLResult(
        total_cecl=total, by_segment=seg,
        weighted_life_years=w_life, macro_overlay=overlay,
    )


@dataclass
class DualReportBridge:
    ifrs9_total: float
    cecl_total: float
    gap: float                        # cecl - ifrs9 (usually positive)
    gap_pct: float
    by_segment: pd.DataFrame          # segment, ifrs9, cecl, gap
    driver: str                       # narrative on the main gap driver


def reconcile_ifrs9_cecl(result, portfolio: pd.DataFrame,
                         *, cecl: CECLResult | None = None) -> DualReportBridge:
    """Bridge IFRS 9 (from pipeline) to CECL (computed here)."""
    if cecl is None:
        cecl = compute_cecl(portfolio)

    ifrs9_total = float(result.ecl["total"])
    cecl_total = cecl.total_cecl
    gap = cecl_total - ifrs9_total
    gap_pct = gap / ifrs9_total if ifrs9_total else 0.0

    # segment bridge — IFRS9 by asset_class from the pipeline is not directly
    # available; approximate IFRS9 per segment as ECL share by EAD.
    seg = cecl.by_segment.copy()
    ead_total = seg["ead"].sum()
    seg["ifrs9"] = seg["ead"] / ead_total * ifrs9_total
    seg["gap"] = seg["cecl"] - seg["ifrs9"]
    seg = seg[["asset_class", "ifrs9", "cecl", "gap"]]

    # driver narrative
    if gap > 0:
        driver = ("CECL이 IFRS9보다 큼 — Stage 1 여신이 IFRS9에서는 12개월 손실만 "
                  "인식하나 CECL은 day-1 잔존기간 손실 전액을 인식하기 때문. "
                  "장기 만기(주담대 등) 비중이 클수록 gap 확대.")
    else:
        driver = ("IFRS9이 CECL보다 큼 — Stage 2/3 lifetime + 거시 PIT overlay가 "
                  "CECL day-1 손실을 초과. 자산건전성 악화 국면에서 발생 가능.")

    return DualReportBridge(
        ifrs9_total=ifrs9_total, cecl_total=cecl_total,
        gap=gap, gap_pct=gap_pct, by_segment=seg, driver=driver,
    )
