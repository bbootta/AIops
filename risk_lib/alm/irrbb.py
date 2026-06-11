"""IRRBB — interest rate risk in the banking book.

BCBS IRRBB standard (2016) / Basel framework SRP31:
  - six prescribed rate-shock scenarios built from parallel / short / long
    components: S_short(t) = R_short·e^(-t/x), S_long(t) = R_long·(1-e^(-t/x))
  - ΔEVE: PV change of the repricing gap ladder under each shock
  - ΔNII: 12-month net interest income sensitivity to the parallel shocks
  - supervisory outlier test: max ΔEVE decline ≤ 15% of Tier 1
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.references import (
    IRRBB_SHOCK_PARALLEL_BP, IRRBB_SHOCK_SHORT_BP, IRRBB_SHOCK_LONG_BP,
    IRRBB_SHOCK_DECAY_X, IRRBB_OUTLIER_EVE_PCT_TIER1,
    IRRBB_EARLY_WARNING_PCT_TIER1,
)

SCENARIOS = ["parallel_up", "parallel_down", "steepener", "flattener",
             "short_up", "short_down"]


def shock_curve(scenario: str, t: np.ndarray) -> np.ndarray:
    """Rate shock (decimal) at tenor t (years) for one of the six scenarios."""
    r_par = IRRBB_SHOCK_PARALLEL_BP / 1e4
    r_s = IRRBB_SHOCK_SHORT_BP / 1e4
    r_l = IRRBB_SHOCK_LONG_BP / 1e4
    t = np.asarray(t, dtype=float)
    s_short = np.exp(-t / IRRBB_SHOCK_DECAY_X)
    s_long = 1.0 - s_short
    if scenario == "parallel_up":
        return np.full_like(t, r_par)
    if scenario == "parallel_down":
        return np.full_like(t, -r_par)
    if scenario == "short_up":
        return r_s * s_short
    if scenario == "short_down":
        return -r_s * s_short
    if scenario == "steepener":
        return -0.65 * r_s * s_short + 0.9 * r_l * s_long
    if scenario == "flattener":
        return 0.8 * r_s * s_short - 0.6 * r_l * s_long
    raise ValueError(f"unknown IRRBB scenario: {scenario}")


@dataclass
class IRRBBResult:
    delta_eve: pd.DataFrame      # scenario, delta_eve (signed), pct_tier1
    delta_nii: pd.DataFrame      # scenario (parallel up/down), delta_nii
    worst_eve_decline: float     # positive = decline (KRW)
    worst_eve_scenario: str
    worst_pct_tier1: float
    tier1: float
    base_rate: float
    repricing: pd.DataFrame      # ladder with per-bucket worst-scenario PV effect

    def outlier(self) -> bool:
        return self.worst_pct_tier1 > IRRBB_OUTLIER_EVE_PCT_TIER1

    def early_warning(self) -> bool:
        return self.worst_pct_tier1 > IRRBB_EARLY_WARNING_PCT_TIER1


def compute_irrbb(
    repricing: pd.DataFrame,
    tier1: float,
    *,
    base_rate: float = 0.03,
) -> IRRBBResult:
    """ΔEVE / ΔNII over the repricing gap ladder.

    repricing: DataFrame with t_mid (years) and gap (assets - liabilities).
    EVE per scenario: PV of gap cashflows at midpoints, continuous discounting
    on a flat base curve; ΔEVE = PV_shocked − PV_base (negative = loss).
    ΔNII: Δr × gap × remaining-year fraction over the ≤1y buckets, parallel
    shocks only.
    """
    t = repricing["t_mid"].to_numpy(dtype=float)
    gap = repricing["gap"].to_numpy(dtype=float)

    pv_base = float(np.sum(gap * np.exp(-base_rate * t)))

    eve_rows = []
    per_bucket_worst = None
    worst_decline, worst_name = -np.inf, ""
    for sc in SCENARIOS:
        dr = shock_curve(sc, t)
        contrib = gap * np.exp(-(base_rate + dr) * t)
        pv_s = float(np.sum(contrib))
        d_eve = pv_s - pv_base
        decline = -d_eve
        eve_rows.append({"scenario": sc, "delta_eve": d_eve,
                         "pct_tier1": d_eve / tier1})
        if decline > worst_decline:
            worst_decline, worst_name = decline, sc
            per_bucket_worst = contrib - gap * np.exp(-base_rate * t)

    nii_rows = []
    one_year = t <= 1.0
    for sc in ("parallel_up", "parallel_down"):
        dr = shock_curve(sc, t)
        d_nii = float(np.sum(dr[one_year] * gap[one_year] * (1.0 - t[one_year])))
        nii_rows.append({"scenario": sc, "delta_nii": d_nii})

    ladder = repricing.copy()
    ladder["pv_effect_worst"] = per_bucket_worst

    worst_decline = max(worst_decline, 0.0)
    return IRRBBResult(
        delta_eve=pd.DataFrame(eve_rows),
        delta_nii=pd.DataFrame(nii_rows),
        worst_eve_decline=worst_decline,
        worst_eve_scenario=worst_name,
        worst_pct_tier1=worst_decline / tier1,
        tier1=tier1,
        base_rate=base_rate,
        repricing=ladder,
    )
