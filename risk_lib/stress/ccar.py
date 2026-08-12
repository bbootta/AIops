"""CCAR / DFAST-style 3년 분기 자본 경로 + 자본 보충 액션.

FED CCAR / DFAST는 9-quarter (≈ 2.25년) horizon인데, 본 구현은 보수적으로
3년 = 12 분기로 확장한다.

주요 출력:
  - 분기별 CET1 / Tier1 / Total 비율 경로 + RWA + 누적 ECL
  - 연속 4분기 CBR 침범 카운트 (4분기 이상 시 supervisory action 트리거)
  - 자본 보충 액션 시뮬레이션:
      * 배당 중단 (dividend halt)
      * AT1 발행 (CET1 회복 X, Tier1 회복 O)
      * 신주 발행 (CET1 직접 보충)
      * 변동성과보수 삭감 (MDA 4분위 적용)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.references import BIS_MIN_CET1, BIS_MIN_TIER1
from risk_lib.stress.scenario import StressAxis, evaluate_scenario


# ---------------------------------------------------------------- severity path


@dataclass
class CCARPath:
    """3년 (12 분기) severity 궤적."""
    name: str
    severities: list[float]

    def __len__(self) -> int:
        return len(self.severities)


def hump_severities(peak: float, peak_q: int, n: int,
                    *, decay: float = 0.85) -> list[float]:
    """0 → peak (peak_q 시점) → 지수감쇠 → 0 부근."""
    out = []
    for i in range(n):
        if peak_q <= 0:
            out.append(peak)
        elif i <= peak_q:
            out.append(peak * (i + 1) / (peak_q + 1))
        else:
            out.append(peak * decay ** (i - peak_q))
    return out


DEFAULT_CCAR_PATHS = [
    CCARPath("baseline", [0.0] * 12),
    CCARPath("adverse", hump_severities(1.2, peak_q=4, n=12, decay=0.85)),
    CCARPath("severely_adverse", hump_severities(2.5, peak_q=3, n=12, decay=0.85)),
]


# ---------------------------------------------------------------- capital actions


@dataclass
class CapitalAction:
    """분기별 자본 보충 액션 (모두 양수 = 자본 증가 방향)."""
    name: str
    cet1_add_per_q: float = 0.0       # 신주발행, 배당중단 (보유이익 분배 안함)
    at1_add_per_q: float = 0.0        # AT1 발행
    tier2_add_per_q: float = 0.0      # 후순위 발행
    start_q: int = 4                  # 액션 시작 분기 (CBR 침범 후 통상 4Q 지연)
    end_q: int | None = None          # None → 시점 종료까지


DEFAULT_ACTIONS = {
    "passive": [],                    # 무액션 (base)
    "dividend_halt": [
        CapitalAction("배당중단", cet1_add_per_q=0.0, start_q=2),
        # 효과는 capital_q에 직접 반영 (배당 미차감 = CET1 유지)
    ],
    "at1_issuance": [
        CapitalAction("AT1 발행 1조원", at1_add_per_q=1.0e12 / 4, start_q=4, end_q=7),
    ],
    "rights_issue": [
        CapitalAction("신주 2조원 발행", cet1_add_per_q=2.0e12 / 4, start_q=4, end_q=7),
    ],
    "full_recovery": [
        CapitalAction("배당중단+AT1+신주", cet1_add_per_q=1.5e12 / 4,
                      at1_add_per_q=0.5e12 / 4, start_q=3, end_q=8),
    ],
}


def _capital_at_q(base: CapitalStack, actions: list[CapitalAction], q: int,
                  cumulative_ecl_uplift: float,
                  *, dividend_per_q: float = 0.0) -> CapitalStack:
    """누적 ECL 충격 차감 + 액션 누적 가산."""
    cet1 = base.cet1 - cumulative_ecl_uplift
    at1 = base.additional_t1
    t2 = base.tier2
    # 배당 차감 (base에는 들어가지 않음 — 명시 차감)
    cet1 -= dividend_per_q * q
    # 액션 누적
    for a in actions:
        end = a.end_q if a.end_q is not None else 11
        active_qs = max(0, min(q, end) - a.start_q + 1) if q >= a.start_q else 0
        cet1 += a.cet1_add_per_q * active_qs
        at1 += a.at1_add_per_q * active_qs
        t2 += a.tier2_add_per_q * active_qs
    return CapitalStack(cet1=cet1, additional_t1=at1, tier2=t2)


# ---------------------------------------------------------------- run


@dataclass
class CCARResult:
    paths: pd.DataFrame                       # scenario, q, severity, cet1_ratio, tier1, ...
    consecutive_breach: pd.DataFrame          # per-scenario max consecutive breach
    capital_actions: pd.DataFrame             # scenario × action × q
    recovery_summary: pd.DataFrame            # action별 최저 CET1 / 회복 시점


def quarter_labels_3y(n: int = 12) -> list[str]:
    """간이 분기 라벨 (현재 분기로부터 +1Q .. +nQ)."""
    return [f"+{i + 1}Q" for i in range(n)]


def run_ccar(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    *,
    paths: list[CCARPath] | None = None,
    axis: StressAxis | None = None,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
    quarters: list[str] | None = None,
    actions_map: dict[str, list[CapitalAction]] | None = None,
    dividend_per_q: float = 0.0,
) -> CCARResult:
    """3년 분기별 자본 경로 + 액션 시나리오."""
    paths = paths or DEFAULT_CCAR_PATHS
    axis = axis or StressAxis()
    quarters = quarters or quarter_labels_3y(len(paths[0]))
    actions_map = actions_map or DEFAULT_ACTIONS

    base_ecl = compute_ecl(irb_portfolio, eir=eir)["ecl"].sum()
    n = len(quarters)

    rows = []
    action_rows = []
    for path in paths:
        cum_ecl_uplift = 0.0
        for i in range(n):
            s = path.severities[i]
            sc = axis.scenario_at(s)
            ev = evaluate_scenario(irb_portfolio, capital, rwa_other, sc,
                                   base_ecl=base_ecl, buffers=buffers, eir=eir)
            # 누적 ECL 충격 (수렴해서 매분기 incremental의 일부만 반영)
            cum_ecl_uplift = max(cum_ecl_uplift, ev["incremental_ecl"])
            bis = ev["bis"]
            req_cet1 = bis.required["cet1"]
            rows.append({
                "scenario": path.name,
                "quarter": quarters[i],
                "q_index": i,
                "severity": s,
                "rwa_total": ev["rwa_total"],
                "ecl": ev["ecl"],
                "incremental_ecl": ev["incremental_ecl"],
                "cet1_ratio": ev["cet1_ratio"],
                "tier1_ratio": bis.tier1_ratio,
                "total_ratio": bis.total_ratio,
                "cbr_breach": ev["cet1_ratio"] < req_cet1,
                "pillar1_breach": ev["cet1_ratio"] < BIS_MIN_CET1,
                "tier1_breach": bis.tier1_ratio < BIS_MIN_TIER1,
            })
            # 액션 시뮬레이션
            for action_name, actions in actions_map.items():
                cap_q = _capital_at_q(capital, actions, i + 1,
                                      cum_ecl_uplift,
                                      dividend_per_q=dividend_per_q if action_name != "dividend_halt" else 0.0)
                bis_q = compute_bis_ratios(cap_q, ev["rwa_total"], buffers=buffers)
                action_rows.append({
                    "scenario": path.name,
                    "action": action_name,
                    "quarter": quarters[i],
                    "q_index": i,
                    "cet1_ratio": bis_q.cet1_ratio,
                    "tier1_ratio": bis_q.tier1_ratio,
                    "total_ratio": bis_q.total_ratio,
                    "cbr_breach": bis_q.cet1_ratio < req_cet1,
                })

    paths_df = pd.DataFrame(rows)
    actions_df = pd.DataFrame(action_rows)

    # 연속 4Q 침범 카운트 — supervisory action 트리거
    consec_rows = []
    for name, g in paths_df.groupby("scenario", sort=False):
        breaches = g["cbr_breach"].values
        max_streak = cur = 0
        for b in breaches:
            cur = cur + 1 if b else 0
            max_streak = max(max_streak, cur)
        consec_rows.append({
            "scenario": name,
            "max_consecutive_breach": int(max_streak),
            "supervisory_trigger": max_streak >= 4,
            "min_cet1": float(g["cet1_ratio"].min()),
            "min_tier1": float(g["tier1_ratio"].min()),
        })
    consec_df = pd.DataFrame(consec_rows)

    # 액션별 회복 요약: severe 시나리오 한정
    sev = actions_df[actions_df["scenario"] == "severely_adverse"]
    rec_rows = []
    if not sev.empty:
        for action_name, g in sev.groupby("action", sort=False):
            trough = g.loc[g["cet1_ratio"].idxmin()]
            req_cet1 = BIS_MIN_CET1 + sum((buffers or {"capital_conservation": 0.025,
                                                       "countercyclical": 0.0,
                                                       "dsib": 0.01}).values())
            after_trough = g[g["q_index"] > trough["q_index"]]
            recovered = after_trough[after_trough["cet1_ratio"] >= req_cet1]
            recovery_q = recovered["quarter"].iloc[0] if not recovered.empty else None
            rec_rows.append({
                "action": action_name,
                "trough_cet1": float(trough["cet1_ratio"]),
                "trough_quarter": trough["quarter"],
                "end_cet1": float(g.iloc[-1]["cet1_ratio"]),
                "recovery_quarter": recovery_q,
                "recovered": recovery_q is not None,
            })
    recovery_df = pd.DataFrame(rec_rows)

    return CCARResult(
        paths=paths_df,
        consecutive_breach=consec_df,
        capital_actions=actions_df,
        recovery_summary=recovery_df,
    )
