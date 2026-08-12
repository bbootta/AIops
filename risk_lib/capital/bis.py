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

# ---------------------------------------------------------------- 자본 원장

# 자본은 **RWA에서도 익스포저에서도 파생되지 않는다**. 어느 쪽에 비례시켜도
# 그쪽을 감시하는 비율이 상수가 되어 통제가 소멸한다 —
#   cet1 = rwa × k      → cet1_ratio 가 상수 (독립검증 F-001)
#   cet1 = ead × k      → leverage  가 상수 (독립검증 F-101, 변동 1.4bp)
# 그래서 자본 원장은 파이프라인의 **입력**이며, 실제 원장이 없을 때만 아래
# 합성기를 쓴다. 합성기의 두 축 중 규모에 비례하지 않는 것은 하나뿐이다:
#   발행자본(고정)  — 증자는 이산적 사건이지 자산 증가에 비례하지 않는다
#   이익잉여금      — 연간이익 × 4년. 합성 데이터에서 연간이익은
#                     revenue = ead × spread (data_gen.py) 이므로 **익스포저에
#                     대체로 비례한다**. 자산 구성에 따른 spread 믹스만큼만
#                     벗어난다 (이익/EAD 변동계수 3.8%).
#
# 따라서 규모 독립성은 고정 발행자본 6,400억(자본금 5,000 + AT1 1,400)에서만
# 나오며, 자산이 커지면 그 비중이 희석되어 레버리지비율이 4×margin/1.01 로
# 수렴한다 — 실측 EAD 10.4조 0.1171 → 104조 0.0625 → 520조 0.0576
# (독립검증 지적 F-201 · F-202). 합성기는 **시험용**이며, 규모 민감도가 필요한
# 산출에서는 실제 자본 원장을 주입해야 한다.
PAID_IN_CAPITAL = 5.0e11      # 자본금 + 자본잉여금 (고정 발행액)
RETAINED_YEARS = 4.0          # 누적 유보 연수
AT1_ISSUED = 1.40e11          # 신종자본증권 발행잔액 (고정)
TIER2_ISSUED = 2.40e11        # 후순위채 발행잔액 (고정)

# 발행자본은 자산 규모와 무관하게 유지한다 — 자산이 늘었다고 이 상수를 함께
# 키우면 자본이 다시 규모의 함수가 되어 레버리지 통제가 소멸한다 (지적 F-202).


def synthesise_capital(annual_profit: float) -> CapitalStack:
    """자본 원장 합성 (시험용 fallback) — RWA에서는 파생되지 않는다.

    `annual_profit`은 연간 영업이익(수익 − 비용)이다. 합성 데이터에서는 수익이
    익스포저에 비례하므로 이익잉여금도 익스포저를 따라간다. 규모와 무관한 축은
    고정 발행자본뿐이며, 자산이 커질수록 그 비중이 희석된다 (지적 F-201·F-202).
    실제 자본 원장이 있으면 `run_pipeline(capital_ledger=...)`로 주입하고 이
    함수를 쓰지 않는다.
    """
    retained = max(annual_profit, 0.0) * RETAINED_YEARS
    return CapitalStack(cet1=PAID_IN_CAPITAL + retained,
                        additional_t1=AT1_ISSUED, tier2=TIER2_ISSUED)
