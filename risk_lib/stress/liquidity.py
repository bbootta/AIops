"""유동성 스트레스 (LCR / NSFR) + HQLA 매각 vs 자본 보충 우선순위.

심한 시장충격은:
  1. HQLA 시장가치 하락 (L2A 5pp / L2B 10pp 추가 haircut)
  2. 도매 자금 runoff 가속 (corporate non-op +25%, FI +40%)
  3. committed facility 인출 가속 (+30%)
을 일으킨다.  본 모듈은 각 충격을 단독/결합으로 적용한 LCR/NSFR을 산출한다.

이후 LCR breach 시:
  - 우선순위 1: HQLA L2B 매각 (capital 무영향, 즉시 효과)
  - 우선순위 2: 단기 도매자금 갱신
  - 우선순위 3: CD 발행 (NSFR 영향)
  - 우선순위 4: AT1 / Tier2 발행 (자본 비율 개선)
  - 우선순위 5: 신주 발행 (자본 + 유동성, 비용 高)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from risk_lib.alm.lcr import LCRResult
from risk_lib.alm.nsfr import NSFRResult
from risk_lib.references import LCR_MIN, NSFR_MIN
from risk_lib.stress.multi_reverse import stress_lcr, stress_nsfr


# ---------------------------------------------------------------- stress legs


@dataclass
class LiquidityStressLeg:
    """단일 시나리오 LCR/NSFR 결과."""
    scenario: str
    narrative: str
    lcr: float
    nsfr: float
    lcr_passes: bool
    nsfr_passes: bool
    severity: float


LIQUIDITY_SCENARIOS = {
    "baseline": (0.0, "정상상태 — 충격 없음."),
    "market_shock": (1.0, "시장충격 — HQLA 가치 5~10pp 하락 + 도매 funding 단축."),
    "funding_run": (1.8, "조달 위기 — 비예금 runoff 25%p 가속 + 신뢰도 저하."),
    "combined_severe": (2.8, "통합 위기 — 시장충격 + 조달위기 동시 발현."),
}


def run_liquidity_stress(
    base_lcr: LCRResult, base_nsfr: NSFRResult,
    *, scenarios: dict[str, tuple[float, str]] | None = None,
) -> pd.DataFrame:
    """LCR/NSFR 시나리오 stress 결과 long-form."""
    scenarios = scenarios or LIQUIDITY_SCENARIOS
    rows = []
    for name, (sev, narrative) in scenarios.items():
        lcr = stress_lcr(base_lcr, sev)
        nsfr = stress_nsfr(base_nsfr, sev)
        rows.append({
            "scenario": name,
            "narrative": narrative,
            "severity": sev,
            "lcr": lcr,
            "nsfr": nsfr,
            "lcr_passes": lcr >= LCR_MIN,
            "nsfr_passes": nsfr >= NSFR_MIN,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- recovery priority

@dataclass
class RecoveryAction:
    rank: int
    name: str
    capacity: float           # KRW 동원 가능 금액
    lcr_impact: float         # 즉시 LCR 분자 효과 (HQLA 증가 or 분모 감소)
    nsfr_impact: float        # NSFR 효과
    capital_impact: str       # CET1/Tier1/Total 영향 텍스트
    cost: str                 # 비용 코멘트


def recovery_priority_ladder(
    lcr_shortfall: float,    # LCR breach 회복 위해 필요한 HQLA 증가분 (KRW)
    base_lcr: LCRResult,
    *, hqla_l2b: float | None = None,
) -> pd.DataFrame:
    """LCR breach 시 자본·유동성 보충 우선순위 사다리.

    우선순위는 비용·자본효과 trade-off:
      1. HQLA L2B 매각 — 즉시·무비용 (자본 무관)
      2. 단기 도매 자금 갱신/연장
      3. CD/CP 신규 발행
      4. AT1 발행 (Tier1 보충, 쿠폰 비용)
      5. 신주 발행 (CET1 직접, 희석 비용)
    """
    if hqla_l2b is None:
        hd = base_lcr.hqla_detail
        hqla_l2b = float(hd[hd["component"] == "Level 2B"]["included"].iloc[0])
    actions = [
        RecoveryAction(
            rank=1, name="HQLA L2B 매각",
            capacity=hqla_l2b * 0.7,
            lcr_impact=hqla_l2b * 0.7,
            nsfr_impact=0.0,
            capital_impact="없음",
            cost="시장 bid-ask spread (단기·무이자비용)",
        ),
        RecoveryAction(
            rank=2, name="도매 자금 만기연장 협상",
            capacity=lcr_shortfall * 0.5,
            lcr_impact=lcr_shortfall * 0.5,
            nsfr_impact=lcr_shortfall * 0.5 * 0.5,
            capital_impact="없음",
            cost="협상 spread 가산 (5~15bp)",
        ),
        RecoveryAction(
            rank=3, name="CD/CP 신규 발행 (1년)",
            capacity=2.0e12,
            lcr_impact=2.0e12,
            nsfr_impact=2.0e12 * 1.00,
            capital_impact="없음",
            cost="조달비용 50~80bp 가산",
        ),
        RecoveryAction(
            rank=4, name="AT1 발행 1조원",
            capacity=1.0e12,
            lcr_impact=1.0e12,
            nsfr_impact=1.0e12 * 1.00,
            capital_impact="Tier1 +1조 (CET1 무영향)",
            cost="쿠폰 7~8% (P2R/CBR 침범 시 차감)",
        ),
        RecoveryAction(
            rank=5, name="신주 2조원 발행",
            capacity=2.0e12,
            lcr_impact=2.0e12,
            nsfr_impact=2.0e12 * 1.00,
            capital_impact="CET1 +2조 (가장 강력)",
            cost="기존 주주 희석, 인수수수료 2~4%",
        ),
    ]
    rows = []
    cumulative = 0.0
    for a in actions:
        cumulative += a.lcr_impact
        rows.append({
            "rank": a.rank,
            "action": a.name,
            "capacity": a.capacity,
            "lcr_impact": a.lcr_impact,
            "nsfr_impact": a.nsfr_impact,
            "capital_impact": a.capital_impact,
            "cost": a.cost,
            "cumulative_lcr_relief": cumulative,
            "covers_shortfall": cumulative >= lcr_shortfall,
        })
    return pd.DataFrame(rows)
