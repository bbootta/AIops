"""Operational risk capital — Basel III Standardised Approach (CRE / OPE25).

ORC = BIC * ILM
  BIC = marginal-coefficient(Business Indicator) over buckets
  ILM = ln(e - 1 + (LC / BIC)^0.8),  LC = 15 * avg annual losses (10y)
RWA_op = 12.5 * ORC

National discretion (incl. 금감원 for smaller banks): ILM may be set to 1.
Bucket thresholds are in EUR per Basel; override for KRW-equivalent supervision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# Marginal BI coefficients and bucket upper thresholds (EUR).
_BI_BUCKETS = [
    (1_000_000_000, 0.12),     # Bucket 1: BI <= 1bn -> 12%
    (30_000_000_000, 0.15),    # Bucket 2: 1bn < BI <= 30bn -> marginal 15%
    (math.inf, 0.18),          # Bucket 3: BI > 30bn -> marginal 18%
]


@dataclass
class BusinessIndicator:
    """Three components of the Business Indicator (3-year averages)."""
    ildc: float  # interest, leases, dividend component
    sc: float    # services component
    fc: float    # financial component

    @property
    def bi(self) -> float:
        return self.ildc + self.sc + self.fc


def business_indicator_component(bi: float) -> float:
    """Marginal-coefficient sum across BI buckets."""
    if bi < 0:
        raise ValueError("BI must be >= 0")
    bic = 0.0
    lower = 0.0
    for upper, coef in _BI_BUCKETS:
        if bi > upper:
            bic += (upper - lower) * coef
            lower = upper
        else:
            bic += (bi - lower) * coef
            break
    return bic


def internal_loss_multiplier(
    bic: float,
    avg_annual_losses_10y: float,
    *,
    use_ilm: bool = True,
) -> float:
    """ILM = ln(e - 1 + (LC/BIC)^0.8), LC = 15 * avg annual losses.

    Returns 1.0 if use_ilm is False (national discretion / Bucket 1).
    """
    if not use_ilm or bic <= 0:
        return 1.0
    lc = 15.0 * avg_annual_losses_10y
    return math.log(math.e - 1 + (lc / bic) ** 0.8)


@dataclass
class OpRiskResult:
    bi: float
    bic: float
    ilm: float
    orc: float
    rwa: float


def compute_op_risk_rwa(
    bi_components: BusinessIndicator,
    avg_annual_losses_10y: float = 0.0,
    *,
    use_ilm: bool = True,
) -> OpRiskResult:
    bi = bi_components.bi
    bic = business_indicator_component(bi)
    ilm = internal_loss_multiplier(bic, avg_annual_losses_10y, use_ilm=use_ilm)
    orc = bic * ilm
    return OpRiskResult(bi=bi, bic=bic, ilm=ilm, orc=orc, rwa=orc * 12.5)
