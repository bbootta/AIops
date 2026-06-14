"""Cure-rate / time-to-cure analytics.

Definition (Basel III CRE36.81 + 감독세칙 자산건전성):
  cure = 부도(90+ DPD 또는 unlikely-to-pay) 인식 후 ``cure_window`` 개월 내에
        정상(<30 DPD)으로 복귀한 obligor 의 비율.

본 모듈은 정적 portfolio 스냅샷 위에서 합성 cure 경로를 생성한다 — 실제로는
워크아웃 로그가 필요하지만, 자산군별 cure 가능성 prior를 stylised로 적용하여
재현 가능한 분석 결과를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# 자산군별 cure rate prior (Basel/BCBS 2017 문제자산 보고서 참조)
CURE_PRIOR = {
    "residential_mortgage": 0.42,   # 담보 + 가계 회복력
    "corporate": 0.28,              # 기업 워크아웃 협의
    "retail_other": 0.18,           # 무담보 신용 — 낮음
    "sovereign": 0.05,
    "bank": 0.10,
}
DEFAULT_CURE_WINDOW = 6   # months


def simulate_cure_paths(
    portfolio: pd.DataFrame,
    *,
    cure_window: int = DEFAULT_CURE_WINDOW,
    segment_col: str = "asset_class",
    default_col: str = "default_12m",
    ead_col: str = "ead",
    seed: int = 42,
) -> pd.DataFrame:
    """부도 obligor 에 대한 합성 cure 경로 생성.

    반환 컬럼: exposure_id, segment, ead, cured (bool),
    time_to_cure_months (cured인 경우만, NaN 가능).
    """
    if portfolio.empty:
        return pd.DataFrame(columns=["exposure_id", "segment", "ead",
                                     "cured", "time_to_cure_months"])
    defaults = portfolio[portfolio[default_col] == 1].copy()
    if defaults.empty:
        return pd.DataFrame(columns=["exposure_id", "segment", "ead",
                                     "cured", "time_to_cure_months"])
    rng = np.random.default_rng(seed + 1212)
    rows = []
    for _, row in defaults.iterrows():
        seg = row[segment_col]
        prior = CURE_PRIOR.get(seg, 0.20)
        # cure 결정
        cured = rng.random() < prior
        # cure 시간: cured 인 경우 Weibull-like분포(평균 ~ 3개월) 안에서 추출
        if cured:
            ttc = float(np.clip(rng.gamma(2.0, 1.5), 0.5, cure_window))
        else:
            ttc = float("nan")
        rows.append({
            "exposure_id": row.get("exposure_id"),
            "segment": seg,
            "ead": float(row[ead_col]),
            "cured": bool(cured),
            "time_to_cure_months": ttc,
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------- aggregations

def cure_rate_by_segment(paths: pd.DataFrame) -> pd.DataFrame:
    """자산군별 cure rate (건수 / EAD-가중).

    반환 컬럼: segment, n_defaults, n_cured, cure_rate_count,
    cure_rate_ead, avg_time_to_cure.
    """
    if paths.empty:
        return pd.DataFrame(columns=["segment", "n_defaults", "n_cured",
                                     "cure_rate_count", "cure_rate_ead",
                                     "avg_time_to_cure"])
    rows = []
    for seg, sub in paths.groupby("segment"):
        n = len(sub)
        n_cured = int(sub["cured"].sum())
        ead_total = float(sub["ead"].sum())
        ead_cured = float(sub.loc[sub["cured"], "ead"].sum())
        ttc = sub.loc[sub["cured"], "time_to_cure_months"].mean()
        rows.append({
            "segment": seg,
            "n_defaults": n,
            "n_cured": n_cured,
            "cure_rate_count": n_cured / n if n else 0.0,
            "cure_rate_ead": ead_cured / ead_total if ead_total else 0.0,
            "avg_time_to_cure": float(ttc) if not np.isnan(ttc) else 0.0,
        })
    # 전체
    n = len(paths)
    n_cured = int(paths["cured"].sum())
    ead_total = float(paths["ead"].sum())
    ead_cured = float(paths.loc[paths["cured"], "ead"].sum())
    ttc_all = paths.loc[paths["cured"], "time_to_cure_months"].mean()
    rows.append({
        "segment": "전체",
        "n_defaults": n,
        "n_cured": n_cured,
        "cure_rate_count": n_cured / n if n else 0.0,
        "cure_rate_ead": ead_cured / ead_total if ead_total else 0.0,
        "avg_time_to_cure": float(ttc_all) if not np.isnan(ttc_all) else 0.0,
    })
    return pd.DataFrame(rows)


def time_to_cure_distribution(
    paths: pd.DataFrame, *, bins: int = 6,
    cure_window: int = DEFAULT_CURE_WINDOW,
) -> pd.DataFrame:
    """time-to-cure 분포 (cured 만).

    반환 컬럼: bin_lo, bin_hi, n, share.
    """
    if paths.empty:
        return pd.DataFrame(columns=["bin_lo", "bin_hi", "n", "share"])
    cured = paths[paths["cured"]]
    if cured.empty:
        return pd.DataFrame(columns=["bin_lo", "bin_hi", "n", "share"])
    edges = np.linspace(0.0, float(cure_window), bins + 1)
    counts, _ = np.histogram(cured["time_to_cure_months"].dropna(), bins=edges)
    total = max(int(counts.sum()), 1)
    rows = []
    for i, c in enumerate(counts):
        rows.append({
            "bin_lo": float(edges[i]),
            "bin_hi": float(edges[i + 1]),
            "n": int(c),
            "share": float(c) / total,
        })
    return pd.DataFrame(rows)


# =========================================================== aggregate entry

@dataclass
class CureResult:
    paths: pd.DataFrame
    by_segment: pd.DataFrame
    ttc_distribution: pd.DataFrame
    cure_window: int


def compute_cure(
    portfolio: pd.DataFrame, *, seed: int = 42,
    cure_window: int = DEFAULT_CURE_WINDOW,
) -> CureResult:
    paths = simulate_cure_paths(portfolio, seed=seed, cure_window=cure_window)
    return CureResult(
        paths=paths,
        by_segment=cure_rate_by_segment(paths),
        ttc_distribution=time_to_cure_distribution(paths, cure_window=cure_window),
        cure_window=cure_window,
    )
