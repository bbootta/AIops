"""스트레스 임계 도달 시 권고 행동 (Recovery Plan).

CBR 침범 / AT1 trigger / Pillar-1 미달 시 자동 권고:
  - MDA quartile 적용 → 배당·자기자본·성과보수·AT1 쿠폰 상한
  - CET1 5.125% 미달 시 AT1 conversion/write-down trigger
  - CET1 7.0% 미달 → 신주 발행 권고 규모 산출

BCBS 'Principles for sound stress testing' §9 / CRD V Article 73 — recovery
plan 요건: 'specific, credible, timely actions' linked to capital triggers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from risk_lib.references import BIS_MIN_CET1


# AT1 conversion / temp write-down trigger: CET1 < 5.125%
AT1_TRIGGER_CET1 = 0.05125
# 최소 CET1 목표 (Pillar 2 가산 포함, 회복 후 도달해야 할 수준)
RECOVERY_TARGET_CET1 = 0.085


@dataclass
class RecoveryRecommendation:
    severity_level: str           # "정상"/"주의"/"경고"/"위기"
    cet1_ratio: float
    cet1_amount: float
    rwa: float
    actions: list[str]
    capital_raise_required: float    # 신주 발행 권고 규모
    at1_trigger_active: bool
    mda_distributable_pct: float


def build_recovery_plan(
    cet1_ratio: float, cet1_amount: float, rwa: float,
    *, buffers: dict[str, float] | None = None,
    target_cet1: float = RECOVERY_TARGET_CET1,
) -> RecoveryRecommendation:
    """현재 CET1을 기준으로 적용해야 할 액션 체크리스트."""
    buf = buffers or {"capital_conservation": 0.025,
                       "countercyclical": 0.0, "dsib": 0.01}
    cbr = sum(buf.values())
    cbr_top = BIS_MIN_CET1 + cbr   # 침범 임계
    actions: list[str] = []

    # 단계 분류
    if cet1_ratio >= cbr_top:
        level = "정상"
    elif cet1_ratio >= BIS_MIN_CET1 + cbr * 0.5:
        level = "주의 (CBR 상위 절반 침범)"
    elif cet1_ratio >= BIS_MIN_CET1:
        level = "경고 (CBR 하위 절반 침범)"
    else:
        level = "위기 (Pillar 1 미달)"

    # MDA 4분위 산출
    if cet1_ratio >= cbr_top:
        mda_dist = 1.0
    elif cet1_ratio < BIS_MIN_CET1:
        mda_dist = 0.0
    else:
        shortfall_pct = cbr_top - cet1_ratio
        q_width = cbr / 4
        q_from_bot = min(4, max(1, int(shortfall_pct / q_width) + 1))
        q = 5 - q_from_bot
        retention = {1: 1.00, 2: 0.80, 3: 0.60, 4: 0.40}[q]
        mda_dist = 1 - retention

    # MDA quartile 행동
    if mda_dist < 1.0:
        if mda_dist <= 0.0:
            actions.append("배당 완전 중단 (MDA 1분위 — 100% 보유)")
            actions.append("변동성과보수 전액 보류")
            actions.append("자기주식 매입 전면 금지")
            actions.append("AT1 쿠폰 지급 중단 (재량 정지)")
        else:
            actions.append(f"배당 상한 {mda_dist*100:.0f}%로 제한 (MDA 적용)")
            actions.append(f"변동성과보수 {mda_dist*100:.0f}%만 지급")
            actions.append("자기주식 매입 제한")

    # AT1 trigger
    at1_trigger = cet1_ratio < AT1_TRIGGER_CET1
    if at1_trigger:
        actions.append("AT1 conversion/write-down trigger 발동 — 즉시 통보 + 처리")

    # 신주 발행 권고
    if cet1_ratio < target_cet1:
        deficit_pp = target_cet1 - cet1_ratio
        capital_raise = deficit_pp * rwa
        actions.append(
            f"신주 발행 권고 {capital_raise/1e12:.2f}조원 — "
            f"{deficit_pp*100:.2f}%p CET1 회복 (목표 {target_cet1*100:.1f}%)"
        )
    else:
        capital_raise = 0.0

    # 위기 단계 추가 행동
    if level.startswith("위기"):
        actions.append("감독당국 즉시 보고 + 회복계획(RP) 발동")
        actions.append("리스크자산 매각·증권화 검토 (RWA 감축)")
    elif level.startswith("경고"):
        actions.append("리스크자산 신규 취득 동결")
        actions.append("주간 자본위원회 소집 + 감독당국 사전 협의")

    return RecoveryRecommendation(
        severity_level=level,
        cet1_ratio=cet1_ratio,
        cet1_amount=cet1_amount,
        rwa=rwa,
        actions=actions,
        capital_raise_required=capital_raise,
        at1_trigger_active=at1_trigger,
        mda_distributable_pct=mda_dist,
    )


def scenario_recovery_table(stress_df: pd.DataFrame, rwa_col: str = "rwa_total",
                             *, buffers: dict[str, float] | None = None,
                             capital_total_at_base: float | None = None,
                             ) -> pd.DataFrame:
    """run_stress 결과 각 시나리오에 대해 권고행동 압축본."""
    rows = []
    for _, r in stress_df.iterrows():
        cet1 = r["cet1_ratio"]
        rwa = r[rwa_col]
        cet1_amt = cet1 * rwa
        rec = build_recovery_plan(cet1, cet1_amt, rwa, buffers=buffers)
        rows.append({
            "scenario": r["scenario"],
            "cet1_ratio": cet1,
            "severity_level": rec.severity_level,
            "mda_distributable_pct": rec.mda_distributable_pct,
            "at1_trigger": rec.at1_trigger_active,
            "capital_raise_required": rec.capital_raise_required,
            "n_actions": len(rec.actions),
            "primary_action": rec.actions[0] if rec.actions else "(권고 없음)",
        })
    return pd.DataFrame(rows)
