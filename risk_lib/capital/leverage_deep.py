"""Leverage ratio deep-dive (Basel III LEV10/30/40 / 감독세칙 레버리지비율).

Adds beyond the headline `leverage.py`:

  * Exposure measure decomposition:
      on-balance + derivatives (SA-CCR conversion) + SFT + off-balance(CCF).
  * G-SIB leverage buffer = 50% × G-SIB risk-weighted buffer (LEV40).
  * AT1-coupon distribution lock when leverage buffer is breached
    (analogue of the risk-based MDA), mirroring RBC30 logic.

Pure, deterministic.  Returns dataclasses / DataFrames for the report pages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from risk_lib.capital.leverage import (
    MIN_LEVERAGE_RATIO, OFF_BALANCE_CCF_FLOOR,
)


@dataclass
class LeverageComponent:
    name: str
    notional: float       # gross notional
    factor: float         # CCF / alpha multiplier applied
    exposure: float       # notional × factor


@dataclass
class LeverageExposureBreakdown:
    components: list[LeverageComponent]
    total_exposure: float

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"component": c.name, "notional": c.notional,
             "factor": c.factor, "exposure": c.exposure,
             "share": (c.exposure / self.total_exposure
                       if self.total_exposure else 0.0)}
            for c in self.components
        ])


def decompose_exposure_measure(
    on_balance: float,
    *,
    derivatives_replacement_cost: float = 0.0,
    derivatives_pfe_notional: float = 0.0,
    derivatives_alpha: float = 1.4,        # SA-CCR α (LEV30.20)
    sft_gross: float = 0.0,
    sft_collateral_offset: float = 0.0,
    off_balance_notional: float = 0.0,
    off_balance_ccf: float = OFF_BALANCE_CCF_FLOOR,
) -> LeverageExposureBreakdown:
    """Exposure measure (EM) 구성요소별 분해 (LEV30).

      EM = on-balance
         + derivatives:  RC + α · PFE             (SA-CCR, LEV30.20)
         + SFT:          max(gross − collateral, 0)
         + off-balance:  notional × max(CCF, 10%)

    Returns a breakdown with per-component exposure and total.
    """
    derivatives_pfe_exp = max(0.0, derivatives_pfe_notional) * derivatives_alpha
    sft_net = max(0.0, sft_gross - sft_collateral_offset)
    ccf = max(off_balance_ccf, OFF_BALANCE_CCF_FLOOR)
    off_exp = max(0.0, off_balance_notional) * ccf

    comps = [
        LeverageComponent("on-balance (대차대조표상)",
                          on_balance, 1.0, max(0.0, on_balance)),
        LeverageComponent("파생상품 RC (replacement cost)",
                          derivatives_replacement_cost, 1.0,
                          max(0.0, derivatives_replacement_cost)),
        LeverageComponent(f"파생상품 PFE (α={derivatives_alpha:.2f} · 잠재익스포저)",
                          derivatives_pfe_notional, derivatives_alpha,
                          derivatives_pfe_exp),
        LeverageComponent("SFT (담보차감 후)",
                          sft_gross, 1.0, sft_net),
        LeverageComponent(f"부외 (CCF {ccf*100:.0f}% 적용)",
                          off_balance_notional, ccf, off_exp),
    ]
    total = sum(c.exposure for c in comps)
    return LeverageExposureBreakdown(components=comps, total_exposure=total)


# ============================================================================
# G-SIB leverage buffer (LEV40)
# ============================================================================


# G-SIB bucket 1~5 → risk-weighted buffer rate (BCBS G-SIB framework).
# Leverage buffer = 50% × risk-weighted buffer (LEV40.5).
GSIB_RWB_BUCKETS = {
    1: 0.010,
    2: 0.015,
    3: 0.020,
    4: 0.025,
    5: 0.035,
}


def gsib_leverage_buffer(bucket: int | None = None,
                         risk_weighted_rate: float | None = None) -> float:
    """G-SIB leverage buffer (LEV40) — 50% of risk-weighted G-SIB buffer."""
    if risk_weighted_rate is not None:
        return max(0.0, risk_weighted_rate) * 0.5
    if bucket is None:
        return 0.0
    if bucket not in GSIB_RWB_BUCKETS:
        raise ValueError(f"G-SIB bucket은 1~5만 허용 (입력={bucket})")
    return GSIB_RWB_BUCKETS[bucket] * 0.5


# ============================================================================
# Leverage MDA-equivalent (LEV40 — AT1 coupon lock on buffer breach)
# ============================================================================


@dataclass
class LeverageMDAResult:
    leverage_ratio: float
    minimum: float           # 3%
    gsib_buffer: float       # leverage buffer (LEV40)
    requirement_total: float # 3% + gsib_buffer
    buffer_shortfall: float  # positive if breach
    buffer_quartile: int     # 0 = no breach, 1~4 mirror RBC30
    retention_ratio: float
    distributable_pct: float

    @property
    def in_breach(self) -> bool:
        return self.buffer_quartile > 0


def leverage_mda(
    leverage_ratio: float, *, gsib_buffer: float = 0.0,
    minimum: float = MIN_LEVERAGE_RATIO,
) -> LeverageMDAResult:
    """레버리지 비율의 MDA-equivalent (LEV40 analogue).

    G-SIB leverage buffer를 침범하면 risk-based MDA와 동일한 4분위 분배제한.
    레버리지 비율이 3% 미만이면 100% 보유 (분배 금지).
    """
    requirement_total = minimum + max(0.0, gsib_buffer)
    if leverage_ratio >= requirement_total - 1e-12:
        return LeverageMDAResult(
            leverage_ratio=leverage_ratio, minimum=minimum,
            gsib_buffer=gsib_buffer, requirement_total=requirement_total,
            buffer_shortfall=0.0, buffer_quartile=0,
            retention_ratio=0.0, distributable_pct=1.0,
        )
    if leverage_ratio < minimum:
        return LeverageMDAResult(
            leverage_ratio=leverage_ratio, minimum=minimum,
            gsib_buffer=gsib_buffer, requirement_total=requirement_total,
            buffer_shortfall=requirement_total - leverage_ratio,
            buffer_quartile=1, retention_ratio=1.0,
            distributable_pct=0.0,
        )
    # In the buffer zone — 4 quartiles.
    if gsib_buffer <= 0:
        return LeverageMDAResult(
            leverage_ratio=leverage_ratio, minimum=minimum,
            gsib_buffer=0.0, requirement_total=requirement_total,
            buffer_shortfall=0.0, buffer_quartile=0,
            retention_ratio=0.0, distributable_pct=1.0,
        )
    shortfall_pct = requirement_total - leverage_ratio
    qw = gsib_buffer / 4
    q_from_bottom = min(4, max(1, int(shortfall_pct / qw) + 1))
    q = 5 - q_from_bottom
    retention_map = {1: 1.00, 2: 0.80, 3: 0.60, 4: 0.40}
    retention = retention_map[q]
    return LeverageMDAResult(
        leverage_ratio=leverage_ratio, minimum=minimum,
        gsib_buffer=gsib_buffer, requirement_total=requirement_total,
        buffer_shortfall=shortfall_pct, buffer_quartile=q,
        retention_ratio=retention, distributable_pct=1 - retention,
    )


# ============================================================================
# Aggregated container
# ============================================================================


@dataclass
class LeverageDeepResult:
    breakdown: LeverageExposureBreakdown
    tier1: float
    leverage_ratio: float
    minimum: float
    gsib_buffer: float
    requirement_total: float
    surplus_shortfall: float
    mda: LeverageMDAResult

    @property
    def passes_minimum(self) -> bool:
        return self.leverage_ratio >= self.minimum - 1e-12

    @property
    def passes_with_buffer(self) -> bool:
        return self.leverage_ratio >= self.requirement_total - 1e-12


def compute_leverage_deep(
    tier1: float,
    *,
    on_balance: float,
    derivatives_replacement_cost: float = 0.0,
    derivatives_pfe_notional: float = 0.0,
    derivatives_alpha: float = 1.4,
    sft_gross: float = 0.0,
    sft_collateral_offset: float = 0.0,
    off_balance_notional: float = 0.0,
    off_balance_ccf: float = OFF_BALANCE_CCF_FLOOR,
    gsib_bucket: int | None = None,
    gsib_rwb: float | None = None,
) -> LeverageDeepResult:
    """Leverage deep-dive single-call entry."""
    breakdown = decompose_exposure_measure(
        on_balance,
        derivatives_replacement_cost=derivatives_replacement_cost,
        derivatives_pfe_notional=derivatives_pfe_notional,
        derivatives_alpha=derivatives_alpha,
        sft_gross=sft_gross,
        sft_collateral_offset=sft_collateral_offset,
        off_balance_notional=off_balance_notional,
        off_balance_ccf=off_balance_ccf,
    )
    em = breakdown.total_exposure
    if em <= 0:
        raise ValueError("exposure measure must be positive")
    gsib_buf = gsib_leverage_buffer(bucket=gsib_bucket,
                                    risk_weighted_rate=gsib_rwb)
    lr = tier1 / em
    req_total = MIN_LEVERAGE_RATIO + gsib_buf
    mda = leverage_mda(lr, gsib_buffer=gsib_buf)
    return LeverageDeepResult(
        breakdown=breakdown, tier1=tier1, leverage_ratio=lr,
        minimum=MIN_LEVERAGE_RATIO, gsib_buffer=gsib_buf,
        requirement_total=req_total, surplus_shortfall=lr - req_total,
        mda=mda,
    )
