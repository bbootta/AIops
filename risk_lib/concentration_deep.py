"""Concentration deep-dive — exposure-level drill-down.

Outputs:
  - top_n_obligors: top 20 by EAD with PD/LGD/EL/grade/sector/country
  - top_n_at_risk: top 20 by EAD × PD (potential default contribution)
  - sector_country_matrix: heatmap-ready cross-tab
  - large_exposure_test: 동일차주 한도(은행법 §35) 차주별 잉여/위반
  - granularity_adjustment: Gordy granularity addon estimate
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def top_obligors(portfolio: pd.DataFrame, n: int = 20,
                 by: str = "ead") -> pd.DataFrame:
    """Top-N obligors aggregated by chosen metric (ead | el | risk_score)."""
    work = portfolio.copy()
    if "pd" in work.columns and "lgd" in work.columns:
        work["el"] = work["pd"] * work["lgd"] * work["ead"]
        work["risk_score"] = work["pd"] * work["ead"]
    g = work.groupby("obligor_id").agg(
        ead=("ead", "sum"),
        pd_avg=("pd", "mean"),
        lgd_avg=("lgd", "mean"),
        el=("el", "sum") if "el" in work.columns else ("ead", lambda s: 0),
        risk_score=("risk_score", "sum") if "risk_score" in work.columns else ("ead", lambda s: 0),
        sector=("sector", lambda s: s.iloc[0]),
        country=("country", lambda s: s.iloc[0]),
        asset_class=("asset_class", lambda s: s.iloc[0]),
        n_exposures=("exposure_id", "count"),
    ).reset_index()
    return g.nlargest(n, by)


def sector_country_matrix(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Cross-tab of EAD by (sector, country)."""
    return portfolio.pivot_table(
        index="sector", columns="country", values="ead",
        aggfunc="sum", fill_value=0,
    )


def large_exposure_test(portfolio: pd.DataFrame, tier1: float,
                        limit_pct: float = 0.25) -> pd.DataFrame:
    """동일차주 한도 (은행법 §35) 차주별 사용률.

    Returns: obligor_id, ead, threshold, utilisation, severity (1행/차주).
    """
    threshold = tier1 * limit_pct
    g = portfolio.groupby("obligor_id")["ead"].sum().reset_index()
    g["threshold"] = threshold
    g["utilisation"] = g["ead"] / threshold
    def sev(u):
        if u >= 1.0:      return "BREACH"
        if u >= 0.90:     return "CRITICAL"
        if u >= 0.75:     return "WARN"
        return "OK"
    g["severity"] = g["utilisation"].apply(sev)
    return g.sort_values("ead", ascending=False)


def granularity_addon(portfolio: pd.DataFrame) -> float:
    """Gordy-style single-obligor granularity addon (simplified).

    GA ≈ K · HHI(obligor)  (Gordy 2003; we use the obligor HHI as the
    granularity proxy.  At very high N this collapses to ~0 quickly.)
    """
    s = portfolio.groupby("obligor_id")["ead"].sum()
    w = s / s.sum()
    hhi = float((w ** 2).sum())
    # K depends on the Vasicek model parameters; we use a flat coefficient
    # calibrated so a single-obligor book (HHI=1) gets a ~5% addon.
    return float(0.05 * hhi)
