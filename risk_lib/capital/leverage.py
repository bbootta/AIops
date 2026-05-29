"""Basel III leverage ratio (LEV).

  LR = Tier1 capital / Total exposure measure
  Minimum 3% (+ G-SIB leverage buffer = 50% of risk-weighted G-SIB buffer).

Exposure measure = on-balance + off-balance(with CCF, floor 10%)
                   + derivatives (SA-CCR) + securities financing transactions.
"""

from __future__ import annotations

from dataclasses import dataclass


MIN_LEVERAGE_RATIO = 0.03
OFF_BALANCE_CCF_FLOOR = 0.10  # leverage framework floors CCF at 10%


@dataclass
class LeverageResult:
    tier1: float
    exposure_measure: float
    leverage_ratio: float
    required: float
    surplus_shortfall: float

    def passes(self) -> bool:
        return self.surplus_shortfall >= -1e-9


def exposure_measure(
    on_balance: float,
    off_balance_notional: float = 0.0,
    off_balance_ccf: float = OFF_BALANCE_CCF_FLOOR,
    derivatives: float = 0.0,
    sft: float = 0.0,
) -> float:
    ccf = max(off_balance_ccf, OFF_BALANCE_CCF_FLOOR)
    return on_balance + off_balance_notional * ccf + derivatives + sft


def compute_leverage_ratio(
    tier1: float,
    total_exposure_measure: float,
    *,
    gsib_buffer: float = 0.0,
) -> LeverageResult:
    if total_exposure_measure <= 0:
        raise ValueError("exposure measure must be positive")
    required = MIN_LEVERAGE_RATIO + gsib_buffer
    lr = tier1 / total_exposure_measure
    return LeverageResult(
        tier1=tier1,
        exposure_measure=total_exposure_measure,
        leverage_ratio=lr,
        required=required,
        surplus_shortfall=lr - required,
    )
