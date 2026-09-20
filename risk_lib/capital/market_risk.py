"""Market risk capital — Simplified Standardised Approach (Basel MAR40).

Per risk class, capital charge = risk-weighted net position, then multiplied by
a supervisory scaling factor (SF).  RWA = 12.5 * total capital charge.

This is the simplified (not the full sensitivities-based) method, intended for
banks with limited trading activity — appropriate for an illustrative harness.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# 감독조정계수 (MAR40.2). 규정에는 금리 1.30 · 주식 3.50 · 외환 1.20 · 상품 1.90
# 네 값만 있다. credit_spread 는 간편법에서 금리 위험군의 개별위험으로 다뤄지므로
# 별도 계수가 없고, 아래 1.00 은 위험군 어휘를 맞추기 위한 자리값이다 (규정값 아님).
# 파이프라인은 fx·equity·interest_rate 세 위험군만 생성해 이 값은 산출에 타지 않는다.
SSA_SCALING = {
    "interest_rate": 1.30,
    "equity": 3.50,
    "fx": 1.20,
    "commodity": 1.90,
    "credit_spread": 1.00,
}

# Illustrative default standardized risk weights when none supplied.
DEFAULT_RISK_WEIGHTS = {
    "interest_rate": 0.015,   # general IR (maturity-dependent in full method)
    "equity": 0.08,
    "fx": 0.08,
    "commodity": 0.15,
    "credit_spread": 0.05,
}


@dataclass
class MarketRiskResult:
    capital_charge: float
    rwa: float
    by_class: dict[str, float]


def compute_market_risk_rwa(positions: pd.DataFrame) -> MarketRiskResult:
    """Compute market risk RWA from net positions.

    Required columns:
      risk_class  - one of SSA_SCALING keys
      net_position - signed notional (absolute value is charged)
    Optional:
      risk_weight - override DEFAULT_RISK_WEIGHTS
    """
    required = {"risk_class", "net_position"}
    missing = required - set(positions.columns)
    if missing:
        raise ValueError(f"positions missing columns: {missing}")

    by_class: dict[str, float] = {}
    for rc, sub in positions.groupby("risk_class"):
        if rc not in SSA_SCALING:
            raise ValueError(f"unknown risk_class: {rc}")
        if "risk_weight" in sub.columns and sub["risk_weight"].notna().any():
            rw = sub["risk_weight"].fillna(DEFAULT_RISK_WEIGHTS[rc])
        else:
            rw = DEFAULT_RISK_WEIGHTS[rc]
        charge = (sub["net_position"].abs() * rw).sum() * SSA_SCALING[rc]
        by_class[rc] = float(charge)

    total = sum(by_class.values())
    return MarketRiskResult(capital_charge=total, rwa=total * 12.5, by_class=by_class)
