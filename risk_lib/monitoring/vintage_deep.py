"""Asset-class-aware vintage analytics and drift detection.

기존 ``risk_lib.vintage.synthesise_vintage`` 가 portfolio 전체에 대해 단일
PD 기반 cohort 곡선을 만든다면, 본 모듈은 자산군별로 분리된 vintage 곡선과
신규 vintage 의 drift (vs 과거 평균) 를 계산한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ---------------------------------------------------------- vintage by segment

def vintage_by_segment(
    portfolio: pd.DataFrame,
    *,
    n_cohorts: int = 12,
    segment_col: str = "asset_class",
    pd_col: str = "pd",
    seed: int = 42,
) -> pd.DataFrame:
    """자산군별 cohort × MOB 누적 부도율.

    반환 컬럼: segment, cohort, cohort_month, mob, n, cum_default_rate.
    """
    if portfolio.empty:
        return pd.DataFrame(columns=["segment", "cohort", "cohort_month",
                                     "mob", "n", "cum_default_rate"])
    rng = np.random.default_rng(seed + 401)
    rows = []
    for seg, sub in portfolio.groupby(segment_col):
        n = len(sub)
        if n == 0:
            continue
        pd_base = sub[pd_col].fillna(0.01).to_numpy(dtype=float)
        cohort_idx = rng.integers(0, n_cohorts, n)
        cohort_factor = 0.80 + 0.50 * rng.beta(2, 2, n_cohorts)
        for c in range(n_cohorts):
            mask = cohort_idx == c
            n_c = int(mask.sum())
            if n_c == 0:
                continue
            pd_eff = pd_base[mask] * cohort_factor[c]
            for mob in range(1, n_cohorts - c + 1):
                pd_m = np.clip(pd_eff / 12.0, 0, 0.99)
                cum = float(np.mean(1 - (1 - pd_m) ** mob))
                rows.append({
                    "segment": seg,
                    "cohort": c,
                    "cohort_month": f"M-{c}",
                    "mob": mob,
                    "n": n_c,
                    "cum_default_rate": cum,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------- seasoning factor

def seasoning_factor(vintage_df: pd.DataFrame) -> pd.DataFrame:
    """자산군별 peak MOB (= 부도 hazard 정점까지의 평균 기간) + peak DR.

    seasoning_factor = peak_DR / DR(mob=1) — 1이면 first month 가 정점.
    """
    if vintage_df.empty:
        return pd.DataFrame(columns=["segment", "peak_mob", "peak_dr",
                                     "early_dr", "seasoning_factor"])
    rows = []
    for seg, sub in vintage_df.groupby("segment"):
        # average across cohorts at each MOB
        avg = sub.groupby("mob")["cum_default_rate"].mean()
        if avg.empty:
            continue
        peak_mob = int(avg.idxmax())
        peak_dr = float(avg.max())
        early = float(avg.iloc[0]) if len(avg) > 0 else 0.0
        rows.append({
            "segment": seg,
            "peak_mob": peak_mob,
            "peak_dr": peak_dr,
            "early_dr": early,
            "seasoning_factor": peak_dr / early if early > 0 else 0.0,
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------- vintage drift

def vintage_drift(vintage_df: pd.DataFrame, *,
                   recent_n: int = 3, mob_window: int = 1) -> pd.DataFrame:
    """신규 vintage (최근 ``recent_n`` cohorts) 가 과거 평균 대비
    악화/개선됐는지 판정.

    공정 비교를 위해 ``cum_default_rate`` 를 동일 MOB (=``mob_window``) 시점에서
    측정한 평균을 비교한다 — peak MOB은 cohort마다 다르므로 직접 비교가
    편향된다. ``mob_window=1`` → 1개월 vintage 비교 (PSI-like indicator).

    drift = mean(recent DR @ mob_window) / mean(legacy DR @ mob_window) − 1.
    drift > +10% → 악화 (RED);  ±10% → 안정 (GREEN);  < -10% → 개선 (GREEN)
    """
    if vintage_df.empty:
        return pd.DataFrame(columns=["segment", "recent_avg_dr",
                                     "legacy_avg_dr", "drift", "verdict"])
    rows = []
    for seg, sub in vintage_df.groupby("segment"):
        # filter to fixed MOB so cohort horizon doesn't bias the comparison
        at_mob = sub[sub["mob"] == mob_window]
        if at_mob.empty:
            continue
        per_cohort = at_mob.groupby("cohort")["cum_default_rate"].mean()
        if len(per_cohort) < recent_n + 1:
            continue
        per_cohort = per_cohort.sort_index()
        recent = per_cohort.iloc[-recent_n:]
        legacy = per_cohort.iloc[:-recent_n]
        recent_avg = float(recent.mean())
        legacy_avg = float(legacy.mean()) if len(legacy) else 0.0
        drift = (recent_avg / legacy_avg - 1.0) if legacy_avg > 0 else 0.0
        if drift > 0.10:
            verdict = "악화"
        elif drift < -0.10:
            verdict = "개선"
        else:
            verdict = "안정"
        rows.append({
            "segment": seg,
            "recent_avg_dr": recent_avg,
            "legacy_avg_dr": legacy_avg,
            "drift": drift,
            "verdict": verdict,
        })
    return pd.DataFrame(rows)


# =========================================================== aggregate entry

@dataclass
class VintageDeepResult:
    by_segment: pd.DataFrame
    seasoning: pd.DataFrame
    drift: pd.DataFrame


def compute_vintage_deep(
    portfolio: pd.DataFrame, *, seed: int = 42, n_cohorts: int = 12,
) -> VintageDeepResult:
    vb = vintage_by_segment(portfolio, seed=seed, n_cohorts=n_cohorts)
    sf = seasoning_factor(vb)
    dr = vintage_drift(vb)
    return VintageDeepResult(by_segment=vb, seasoning=sf, drift=dr)
