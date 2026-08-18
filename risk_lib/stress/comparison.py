"""Scenario comparison — 자본 / 유동성 / 수익성 정합 비교.

baseline / adverse / severely_adverse 각 시나리오에 대해 한 표에서 비교:
  - 자본: CET1, Tier1, Total, MDA distributable, capital raise
  - 유동성: LCR, NSFR (각 시나리오 severity로 환산)
  - 수익성: ECL uplift, RWA 증가율, ROA 영향 (approx)
"""

from __future__ import annotations

import pandas as pd

from risk_lib.alm.lcr import LCRResult
from risk_lib.alm.nsfr import NSFRResult
from risk_lib.references import LCR_MIN, NSFR_MIN
from risk_lib.stress.multi_reverse import stress_lcr, stress_nsfr
from risk_lib.stress.recovery import build_recovery_plan


# scenario name → liquidity severity 매핑
SCENARIO_LIQ_SEVERITY = {
    "baseline": 0.0,
    "adverse": 1.0,
    "severely_adverse": 2.2,
}


def compare_scenarios(
    stress_df: pd.DataFrame,
    base_lcr: LCRResult,
    base_nsfr: NSFRResult,
    *,
    buffers: dict[str, float] | None = None,
    capital_total: float | None = None,
    base_revenue: float | None = None,
) -> pd.DataFrame:
    """시나리오별 자본·유동성·수익성 정합 비교 (long-form table)."""
    rows = []
    base_ecl = float(stress_df.loc[stress_df["scenario"] == "baseline", "ecl"].iloc[0]) \
        if "baseline" in stress_df["scenario"].values else 0.0
    base_rwa = float(stress_df.loc[stress_df["scenario"] == "baseline", "rwa_total"].iloc[0]) \
        if "baseline" in stress_df["scenario"].values else 0.0
    for _, r in stress_df.iterrows():
        name = r["scenario"]
        sev = SCENARIO_LIQ_SEVERITY.get(name, 1.0)
        lcr = stress_lcr(base_lcr, sev) if sev > 0 else base_lcr.lcr
        nsfr = stress_nsfr(base_nsfr, sev) if sev > 0 else base_nsfr.nsfr
        rec = build_recovery_plan(r["cet1_ratio"], r["cet1_ratio"] * r["rwa_total"],
                                  r["rwa_total"], buffers=buffers)
        ecl_uplift = max(r["ecl"] - base_ecl, 0.0)
        rwa_growth = (r["rwa_total"] - base_rwa) / base_rwa if base_rwa > 0 else 0.0
        roa_impact = -ecl_uplift / r["rwa_total"] if r["rwa_total"] > 0 else 0.0
        rows.append({
            "scenario": name,
            # 자본
            "cet1_ratio": r["cet1_ratio"],
            "total_ratio": r["total_ratio"],
            "cet1_surplus_pp": r["cet1_surplus"] * 100,
            "mda_distributable_pct": rec.mda_distributable_pct,
            "capital_raise_required": rec.capital_raise_required,
            "severity_level": rec.severity_level,
            # 유동성
            "lcr": lcr,
            "nsfr": nsfr,
            "lcr_passes": lcr >= LCR_MIN,
            "nsfr_passes": nsfr >= NSFR_MIN,
            # 수익성
            "ecl_uplift": ecl_uplift,
            "rwa_growth_pct": rwa_growth * 100,
            "roa_impact_pp": roa_impact * 100,
            # 통합 판정
            "passes_all": (r["passes"] and lcr >= LCR_MIN and nsfr >= NSFR_MIN),
        })
    return pd.DataFrame(rows)
