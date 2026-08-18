"""Multi-period capital simulation — Top-IB CCAR/DFAST-grade.

Projects CET1 / Tier1 / Total ratios forward 4–12 quarters under:
  - baseline (organic earnings, normal RWA growth)
  - adverse (stress GDP -3.5%, RWA +12%, ECL +50%)
  - severe (stress GDP -7.5%, RWA +20%, ECL +120%)

With overlays:
  - dividend distribution (with MDA quartile constraint)
  - share buy-back program
  - AT1 / Tier 2 issuance schedule
  - new share issuance
  - AT1 conversion trigger (CET1 ≤ 5.125%)

For each quarter:
  CET1_{t+1} = CET1_t + earnings_t · (1 - dividend_payout)
              - buyback_t - writedown_t + share_issuance_t

  RWA_{t+1} = RWA_t · (1 + growth_t)

  Ratio_{t+1} = CET1_{t+1} / RWA_{t+1}

Outputs a tidy multi-scenario projection frame + a status flag per quarter
(buffer-breach trigger, MDA quartile, AT1 trigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class CapitalAction:
    """A planned capital action at a quarter."""
    quarter: int                 # 1-indexed (Q+1 = next quarter)
    action: str                  # "dividend" / "buyback" / "at1_issue" / "share_issue"
    amount: float                # KRW (positive = cash out / capital in)


@dataclass
class CapitalScenario:
    name: str
    rwa_growth_qoq: list[float]      # per-quarter RWA growth
    ecl_uplift_total: float           # cumulative ECL hit absorbed by CET1
    earnings_qoq: list[float]         # per-quarter earnings / RWA
    severity: float = 1.0             # 1=base, 2=adverse, 3=severe


def _baseline(n_q: int) -> CapitalScenario:
    return CapitalScenario(
        name="baseline",
        rwa_growth_qoq=[0.015] * n_q,
        ecl_uplift_total=0,
        earnings_qoq=[0.012] * n_q,
        severity=1.0,
    )


def _adverse(n_q: int) -> CapitalScenario:
    return CapitalScenario(
        name="adverse",
        rwa_growth_qoq=[0.030, 0.040, 0.045, 0.040, 0.020, 0.015, 0.010, 0.010][:n_q],
        ecl_uplift_total=0.020,    # 200bp of RWA absorbed cumulatively
        earnings_qoq=[0.008, 0.005, 0.003, 0.005, 0.007, 0.009, 0.011, 0.012][:n_q],
        severity=2.0,
    )


def _severe(n_q: int) -> CapitalScenario:
    return CapitalScenario(
        name="severe",
        rwa_growth_qoq=[0.05, 0.06, 0.07, 0.05, 0.03, 0.02, 0.01, 0.01][:n_q],
        ecl_uplift_total=0.045,
        earnings_qoq=[0.003, -0.005, -0.008, -0.003, 0.002, 0.006, 0.010, 0.012][:n_q],
        severity=3.0,
    )


# ----- MDA constraint helper ----------------------------------------------

def _mda_quartile(cet1_ratio: float, *, p1_minimum: float = 0.045,
                  cbr: float = 0.025) -> int:
    """Return 0 if above CBR, else 1–4 quartile (1=top, 4=bottom)."""
    top_buffer = p1_minimum + cbr
    if cet1_ratio >= top_buffer:
        return 0
    if cet1_ratio < p1_minimum:
        return 4
    used = (top_buffer - cet1_ratio) / cbr
    if used <= 0.25: return 1
    if used <= 0.50: return 2
    if used <= 0.75: return 3
    return 4


def _mda_retention(quartile: int) -> float:
    """Max retention of earnings (=1 - max payout) at each quartile."""
    return {0: 0.0, 1: 0.40, 2: 0.60, 3: 0.80, 4: 1.00}[quartile]


# ----- simulator ----------------------------------------------------------

@dataclass
class CapitalProjection:
    quarter: int
    scenario: str
    cet1: float                      # absolute KRW
    tier1: float
    total: float
    rwa: float
    cet1_ratio: float
    tier1_ratio: float
    total_ratio: float
    mda_quartile: int
    at1_triggered: bool
    leverage: float
    actions: list[str] = field(default_factory=list)


def simulate_capital_path(
    base_cet1: float, base_tier1: float, base_total: float,
    base_rwa: float,
    *,
    n_quarters: int = 8,
    scenarios: list[CapitalScenario] | None = None,
    planned_actions: list[CapitalAction] | None = None,
    at1_trigger_ratio: float = 0.05125,
    at1_writedown_amount: float = 0.0,
    dividend_payout_target: float = 0.30,
    leverage_exposure: float | None = None,
) -> pd.DataFrame:
    """Project CET1/Tier1/Total ratios n_quarters forward across scenarios.

    Returns a tidy frame with one row per (quarter × scenario).
    """
    if scenarios is None:
        scenarios = [_baseline(n_quarters), _adverse(n_quarters), _severe(n_quarters)]
    actions = planned_actions or []

    if leverage_exposure is None:
        leverage_exposure = base_rwa * 1.1  # rough proxy

    out: list[CapitalProjection] = []

    for scen in scenarios:
        cet1 = base_cet1; tier1 = base_tier1; total = base_total
        rwa = base_rwa
        at1_triggered = False
        ecl_remaining = scen.ecl_uplift_total * base_rwa  # KRW to absorb total

        for q in range(1, n_quarters + 1):
            applied_actions: list[str] = []
            # 1) RWA growth
            growth = scen.rwa_growth_qoq[q - 1] if q - 1 < len(scen.rwa_growth_qoq) else 0
            rwa *= (1 + growth)

            # 2) ECL absorption — first 4Q of adverse/severe
            if ecl_remaining > 0 and q <= 4 and scen.severity > 1:
                hit = ecl_remaining / min(4, n_quarters)
                cet1 -= hit
                tier1 -= hit
                total -= hit
                ecl_remaining -= hit
                applied_actions.append(f"ECL absorbed −{hit/1e9:.1f}bn")

            # 3) Earnings
            er = scen.earnings_qoq[q - 1] if q - 1 < len(scen.earnings_qoq) else 0
            earnings = er * base_rwa  # earnings as a fraction of base RWA
            cet1_ratio_before_div = cet1 / rwa if rwa else 0
            quartile = _mda_quartile(cet1_ratio_before_div)
            retention = _mda_retention(quartile)
            payout = min(dividend_payout_target, 1 - retention) * max(earnings, 0)
            retained = earnings - payout
            cet1 += retained
            tier1 += retained
            total += retained
            if payout > 0:
                applied_actions.append(f"배당 {payout/1e9:.1f}bn (Q{quartile}, "
                                       f"retention {retention*100:.0f}%)")

            # 4) Planned actions for this quarter
            for act in actions:
                if act.quarter != q:
                    continue
                if act.action == "share_issue":
                    cet1 += act.amount
                    tier1 += act.amount
                    total += act.amount
                    applied_actions.append(f"신주 발행 +{act.amount/1e9:.0f}bn")
                elif act.action == "at1_issue":
                    tier1 += act.amount
                    total += act.amount
                    applied_actions.append(f"AT1 발행 +{act.amount/1e9:.0f}bn")
                elif act.action == "tier2_issue":
                    total += act.amount
                    applied_actions.append(f"Tier2 발행 +{act.amount/1e9:.0f}bn")
                elif act.action == "buyback":
                    cet1 -= act.amount
                    tier1 -= act.amount
                    total -= act.amount
                    applied_actions.append(f"자사주매입 −{act.amount/1e9:.0f}bn")
                elif act.action == "dividend":
                    cet1 -= act.amount
                    tier1 -= act.amount
                    total -= act.amount
                    applied_actions.append(f"특별배당 −{act.amount/1e9:.0f}bn")

            # 5) AT1 trigger check (CET1 ≤ 5.125%)
            cet1_ratio = cet1 / rwa if rwa else 0
            if cet1_ratio <= at1_trigger_ratio and not at1_triggered:
                at1_triggered = True
                # convert AT1 to CET1 (synthetic 1tn write-down)
                conversion = at1_writedown_amount or (tier1 - cet1) * 0.3
                cet1 += conversion
                tier1 = cet1 + (tier1 - cet1 - conversion)  # AT1 burnt
                applied_actions.append(
                    f"AT1 trigger 발동 — {conversion/1e9:.0f}bn 전환")

            tier1_ratio = tier1 / rwa if rwa else 0
            total_ratio = total / rwa if rwa else 0
            lev_ratio = tier1 / leverage_exposure if leverage_exposure else 0

            out.append(CapitalProjection(
                quarter=q, scenario=scen.name,
                cet1=cet1, tier1=tier1, total=total, rwa=rwa,
                cet1_ratio=cet1 / rwa if rwa else 0,
                tier1_ratio=tier1_ratio, total_ratio=total_ratio,
                mda_quartile=_mda_quartile(cet1 / rwa if rwa else 0),
                at1_triggered=at1_triggered, leverage=lev_ratio,
                actions=applied_actions,
            ))

    df = pd.DataFrame([
        {"quarter": p.quarter, "scenario": p.scenario,
         "cet1": p.cet1, "tier1": p.tier1, "total": p.total, "rwa": p.rwa,
         "cet1_ratio": p.cet1_ratio, "tier1_ratio": p.tier1_ratio,
         "total_ratio": p.total_ratio, "leverage": p.leverage,
         "mda_quartile": p.mda_quartile, "at1_triggered": p.at1_triggered,
         "actions": "; ".join(p.actions)}
        for p in out
    ])
    return df


# ----- summary -------------------------------------------------------------

def projection_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-scenario summary: min CET1, terminal CET1, first breach quarter,
    AT1 trigger flag."""
    rows = []
    for scen in df["scenario"].unique():
        sub = df[df["scenario"] == scen].sort_values("quarter")
        min_cet1 = float(sub["cet1_ratio"].min())
        end_cet1 = float(sub["cet1_ratio"].iloc[-1])
        breach = sub[sub["cet1_ratio"] < 0.07]   # buffer-inclusive threshold
        first_breach = int(breach["quarter"].iloc[0]) if len(breach) else None
        at1 = bool(sub["at1_triggered"].any())
        rows.append({
            "scenario": scen,
            "min_cet1": min_cet1, "end_cet1": end_cet1,
            "first_breach_q": first_breach,
            "at1_triggered": at1,
            "passes_all": first_breach is None,
        })
    return pd.DataFrame(rows)
