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

# ---------------------------------------------------------------- 자본 합성

# 자본은 **익스포저 규모**에서 나온다 — 위험가중자산에서 역산하면 안 된다.
# cet1 = rwa × k 로 만들면 cet1_ratio = k 가 되어 비율이 RWA·포트폴리오와
# 무관한 상수가 되고, RWA 오류를 자본비율이 전혀 드러내지 못한다
# (독립검증 F-001). 아래 계수는 자기자본/총익스포저 수준과 발행 구성 가정이며
# 실제 자본 원장으로 교체가 전제다.
CET1_TO_EXPOSURE = 0.10      # 보통주자본 / 총익스포저
AT1_TO_CET1 = 0.13           # 기타기본자본 발행 비중
T2_TO_CET1 = 0.22            # 보완자본 발행 비중


def synthesise_capital(total_exposure: float) -> CapitalStack:
    """총익스포저 규모에서 자본 스택을 만든다 (RWA와 독립).

    RWA가 커지면 비율이 내려가야 통제가 작동한다 — 그것이 이 함수가 RWA를
    인자로 받지 않는 이유다.
    """
    if total_exposure <= 0:
        raise ValueError("total_exposure must be positive")
    cet1 = total_exposure * CET1_TO_EXPOSURE
    return CapitalStack(cet1=cet1,
                        additional_t1=cet1 * AT1_TO_CET1,
                        tier2=cet1 * T2_TO_CET1)
