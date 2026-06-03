"""BIS capital ratios (CET1, Tier1, Total).

References (cited via risk_lib.references):
  - Basel III CRE10.4: Pillar 1 minima (CET1 4.5% / Tier1 6.0% / Total 8.0%).
  - Basel III RBC20.1: 자본보전버퍼 2.5% (상시).
  - RBC20 (CCyB) + RBC40 (D-SIB): jurisdiction-set add-ons.
  - 금감원 「은행업감독업무시행세칙」 자본적정성 편.
"""

from __future__ import annotations

from dataclasses import dataclass

from risk_lib.references import (
    BIS_MIN_CET1, BIS_MIN_TIER1, BIS_MIN_TOTAL,
    CAPITAL_CONSERVATION_BUFFER,
)


# Minimum ratios excluding buffers (Pillar 1 minimums) — CRE10.4.
BIS_MINIMUMS = {
    "cet1": BIS_MIN_CET1,
    "tier1": BIS_MIN_TIER1,
    "total": BIS_MIN_TOTAL,
}

# Buffers applied on top per RBC20 / 감독세칙.
BIS_BUFFERS_DEFAULT = {
    "capital_conservation": CAPITAL_CONSERVATION_BUFFER,
    "countercyclical": 0.0,   # set per jurisdiction by FSS
    "dsib": 0.0,              # 0–2.0% by systemic group
}


@dataclass
class CapitalStack:
    """Regulatory capital components after deductions (단위 일치 필요)."""
    cet1: float          # 보통주자본 (CET1)
    additional_t1: float # 기타기본자본 (AT1)
    tier2: float         # 보완자본 (Tier 2)

    @property
    def tier1(self) -> float:
        return self.cet1 + self.additional_t1

    @property
    def total(self) -> float:
        return self.tier1 + self.tier2


@dataclass
class BISResult:
    cet1_ratio: float
    tier1_ratio: float
    total_ratio: float
    rwa: float
    required: dict[str, float]
    surplus_shortfall: dict[str, float]  # actual - required, per layer

    def passes(self) -> bool:
        return all(v >= -1e-9 for v in self.surplus_shortfall.values())


def compute_bis_ratios(
    capital: CapitalStack,
    rwa: float,
    *,
    buffers: dict[str, float] | None = None,
) -> BISResult:
    """Compute CET1/Tier1/Total ratios and compare against required levels.

    rwa: total risk-weighted assets (credit + market + operational, sum).
    buffers: override; defaults to capital conservation 2.5% only.
    """
    if rwa <= 0:
        raise ValueError("rwa must be positive")

    buf = dict(BIS_BUFFERS_DEFAULT)
    if buffers:
        buf.update(buffers)
    buffer_total = buf["capital_conservation"] + buf["countercyclical"] + buf["dsib"]

    required = {
        "cet1": BIS_MINIMUMS["cet1"] + buffer_total,
        "tier1": BIS_MINIMUMS["tier1"] + buffer_total,
        "total": BIS_MINIMUMS["total"] + buffer_total,
    }

    cet1_ratio = capital.cet1 / rwa
    tier1_ratio = capital.tier1 / rwa
    total_ratio = capital.total / rwa

    surplus = {
        "cet1": cet1_ratio - required["cet1"],
        "tier1": tier1_ratio - required["tier1"],
        "total": total_ratio - required["total"],
    }

    return BISResult(
        cet1_ratio=cet1_ratio,
        tier1_ratio=tier1_ratio,
        total_ratio=total_ratio,
        rwa=rwa,
        required=required,
        surplus_shortfall=surplus,
    )
