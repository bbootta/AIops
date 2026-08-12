"""기후 시나리오 → 자본 비율 통합 (NGFS 30Y horizon).

기존 climate.py는 ECL uplift만 산출.  본 모듈은:
  1. NGFS orderly / disorderly / hot_house 시나리오에 대해
  2. 섹터별 PD/LGD 충격을 portfolio에 적용하고
  3. RWA + ECL 변화를 → CET1 비율로 변환
  4. 5Y 간격(2030/2035/2040/2045/2050/2055/2060)으로 30Y horizon path

NGFS Phase IV 시나리오 narratives:
  - orderly      : Net Zero 2050 — 점진적 전환, 자산좌초 완만
  - disorderly   : Delayed Transition — 2030 이후 급격한 정책 강화
  - hot_house    : Current Policies — 물리리스크 누적, 3.0°C+
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.climate import (
    TRANSITION_PD_BETA, PHYSICAL_LGD_BETA,
)


# 30Y horizon: 5Y 간격으로 7 시점 (2030, 2035, ..., 2060)
HORIZON_YEARS = [2030, 2035, 2040, 2045, 2050, 2055, 2060]


# NGFS Phase IV 탄소가격 경로 ($/tCO2) — 5Y interpolation
NGFS_CO2_PATHS = {
    "orderly":    [100, 140, 180, 220, 250, 270, 290],
    "disorderly": [50,  100, 200, 320, 400, 420, 440],
    "hot_house":  [10,  15,  20,  25,  30,  35,  40],
}

# 물리 hazard intensity 누적 (해수면/홍수/태풍 빈도)
NGFS_HAZARD_PATHS = {
    "orderly":    [0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32],
    "disorderly": [0.20, 0.25, 0.30, 0.36, 0.42, 0.48, 0.55],
    "hot_house":  [0.25, 0.35, 0.45, 0.58, 0.70, 0.85, 1.00],
}

NGFS_NARRATIVES = {
    "orderly": "Net Zero 2050 (1.5°C) — 점진적 정책 강화, 전환비용 분산.",
    "disorderly": "Delayed Transition — 2030 이후 급격 정책 강화로 자산좌초 가속.",
    "hot_house": "Current Policies (3.0°C+) — 물리 hazard 누적, 전환비용 최소.",
}


@dataclass
class ClimateCapitalPoint:
    """단일 시점 climate 자본 영향."""
    scenario: str
    year: int
    co2_price: float
    hazard_intensity: float
    rwa_total: float
    ecl: float
    cet1_ratio: float
    tier1_ratio: float
    delta_cet1_pp: float


@dataclass
class ClimateCapitalResult:
    """3 시나리오 × 7 시점 path."""
    path: pd.DataFrame
    worst_point: pd.Series
    binding_year: dict[str, int]   # scenario → 최저 CET1 도달 연도


def _apply_climate_shock(portfolio: pd.DataFrame, co2_price: float,
                          hazard: float) -> pd.DataFrame:
    """섹터별 PD/LGD에 climate 충격 가산."""
    df = portfolio.copy()
    if "sector" not in df.columns:
        return df
    pd_uplift = df["sector"].map(TRANSITION_PD_BETA).fillna(0.0) * (co2_price / 100.0)
    lgd_uplift = df["sector"].map(PHYSICAL_LGD_BETA).fillna(0.0) * hazard
    df["pd"] = np.clip(df["pd"].values + pd_uplift.values, 0.0, 1.0)
    df["lgd"] = np.clip(df["lgd"].values + lgd_uplift.values, 0.0, 1.0)
    return df


def run_climate_capital(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    *,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
    horizon: list[int] | None = None,
) -> ClimateCapitalResult:
    """기후 시나리오를 자본 비율 경로로 변환."""
    horizon = horizon or HORIZON_YEARS
    base_ecl = compute_ecl(irb_portfolio, eir=eir)["ecl"].sum()

    # 기준 CET1 (climate 무충격) — first point에서 referencing
    base_irb_rwa = compute_rwa_irb(irb_portfolio)["rwa"].sum()
    base_rwa = base_irb_rwa + rwa_other
    base_bis = compute_bis_ratios(capital, base_rwa, buffers=buffers)
    base_cet1 = base_bis.cet1_ratio

    rows = []
    for scenario in NGFS_CO2_PATHS:
        co2_path = NGFS_CO2_PATHS[scenario]
        hz_path = NGFS_HAZARD_PATHS[scenario]
        for i, year in enumerate(horizon):
            co2 = co2_path[i] if i < len(co2_path) else co2_path[-1]
            hz = hz_path[i] if i < len(hz_path) else hz_path[-1]
            stressed = _apply_climate_shock(irb_portfolio, co2, hz)
            irb_rwa = compute_rwa_irb(stressed)["rwa"].sum()
            ecl = compute_ecl(stressed, eir=eir)["ecl"].sum()
            rwa_total = irb_rwa + rwa_other
            incremental = max(ecl - base_ecl, 0.0)
            cap_q = CapitalStack(
                cet1=capital.cet1 - incremental,
                additional_t1=capital.additional_t1,
                tier2=capital.tier2,
            )
            bis_q = compute_bis_ratios(cap_q, rwa_total, buffers=buffers)
            rows.append({
                "scenario": scenario,
                "year": year,
                "co2_price": co2,
                "hazard_intensity": hz,
                "rwa_total": rwa_total,
                "ecl": ecl,
                "incremental_ecl": incremental,
                "cet1_ratio": bis_q.cet1_ratio,
                "tier1_ratio": bis_q.tier1_ratio,
                "total_ratio": bis_q.total_ratio,
                "delta_cet1_pp": (bis_q.cet1_ratio - base_cet1) * 100,
                "narrative": NGFS_NARRATIVES[scenario],
            })
    df = pd.DataFrame(rows)
    worst = df.loc[df["cet1_ratio"].idxmin()]
    binding = {}
    for s, g in df.groupby("scenario", sort=False):
        binding[s] = int(g.loc[g["cet1_ratio"].idxmin(), "year"])
    return ClimateCapitalResult(path=df, worst_point=worst, binding_year=binding)
