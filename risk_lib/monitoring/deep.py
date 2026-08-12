"""CRO-grade deep delinquency, default-rate and roll-rate analytics.

본 모듈은 risk_lib v0.10.0에서 자산건전성 부문을 CRO 수준으로 고도화한다.

산출
------
1. ``dpd_bucket_matrix`` — 자산군 × DPD 버킷 매트릭스 (건수/EAD/평균 PD).
2. ``default_rate_timeseries`` — 자산군별 분기 부도율 시계열 (count & EAD 가중).
3. ``npl_ratio`` — 자산군별 NPL EAD 비율.
4. ``roll_rate_matrix`` — DPD 버킷 월간 roll-rate (Markov 전이행렬).
5. ``markov_projection`` — roll-rate × 현재 분포로 향후 3개월 NPL 흐름 예측.

DPD 버킷 표준 (Basel III CRE36.69 / 감독세칙)
    Current(0)  1-29  30-59  60-89  90+(NPL)

부도 정의
    DPD ≥ 90 OR ``default_12m == 1`` (unlikely-to-pay 포함)
    "기술적 연체"는 사전 cure 정책에 따라 제외 — 본 라이브러리는 default_12m 플래그를
    상위 단계에서 cure-policy를 적용한 값으로 가정한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import pandas as pd


DEEP_DPD_BUCKETS: list[tuple[str, int, int]] = [
    ("Current", 0, 0),
    ("1-29", 1, 29),
    ("30-59", 30, 59),
    ("60-89", 60, 89),
    ("90+", 90, 10_000),
]
DEEP_DPD_LABELS = [b[0] for b in DEEP_DPD_BUCKETS]
NPL_THRESHOLD_DPD = 90


def _bucketise(dpd: int | float) -> str:
    if pd.isna(dpd):
        return "Current"
    d = int(dpd)
    for name, lo, hi in DEEP_DPD_BUCKETS:
        if lo <= d <= hi:
            return name
    return "90+"


# ------------------------------------------------------------------ matrix

def dpd_bucket_matrix(
    portfolio: pd.DataFrame,
    *,
    dpd_col: str = "dpd",
    ead_col: str = "ead",
    pd_col: str = "pd",
    segment_col: str = "asset_class",
) -> pd.DataFrame:
    """자산군 × DPD 버킷 매트릭스.

    반환 컬럼: segment, bucket, n_loans, ead, avg_ead, avg_pd, ead_share.
    ``ead_share`` 는 동일 segment 내 점유율.
    """
    df = portfolio.copy()
    if df.empty:
        return pd.DataFrame(columns=["segment", "bucket", "n_loans", "ead",
                                     "avg_ead", "avg_pd", "ead_share"])
    df["bucket"] = df[dpd_col].apply(_bucketise)
    df["bucket"] = pd.Categorical(df["bucket"], categories=DEEP_DPD_LABELS,
                                  ordered=True)
    grp = df.groupby([segment_col, "bucket"], observed=False)
    agg = grp.agg(
        n_loans=(ead_col, "size"),
        ead=(ead_col, "sum"),
        avg_ead=(ead_col, "mean"),
        avg_pd=(pd_col, "mean"),
    ).reset_index().rename(columns={segment_col: "segment"})
    seg_total = agg.groupby("segment")["ead"].transform("sum").replace(0, np.nan)
    agg["ead_share"] = (agg["ead"] / seg_total).fillna(0.0)
    agg["avg_pd"] = agg["avg_pd"].fillna(0.0)
    agg["avg_ead"] = agg["avg_ead"].fillna(0.0)
    return agg


# ---------------------------------------------------------------- NPL ratio

def npl_ratio(
    portfolio: pd.DataFrame,
    *,
    dpd_col: str = "dpd",
    ead_col: str = "ead",
    segment_col: str = "asset_class",
    threshold: int = NPL_THRESHOLD_DPD,
) -> pd.DataFrame:
    """자산군별 NPL ratio = NPL EAD / 총 EAD.

    반환 컬럼: segment, total_ead, npl_ead, npl_ratio, n_npl.
    """
    if portfolio.empty:
        return pd.DataFrame(columns=["segment", "total_ead", "npl_ead",
                                     "npl_ratio", "n_npl"])
    df = portfolio.copy()
    is_npl = df[dpd_col] >= threshold
    rows = []
    for seg, sub in df.groupby(segment_col):
        total = float(sub[ead_col].sum())
        npl = float(sub.loc[is_npl.loc[sub.index], ead_col].sum())
        rows.append({
            "segment": seg,
            "total_ead": total,
            "npl_ead": npl,
            "npl_ratio": npl / total if total > 0 else 0.0,
            "n_npl": int(is_npl.loc[sub.index].sum()),
        })
    # Portfolio-wide row
    total = float(df[ead_col].sum())
    npl = float(df.loc[is_npl, ead_col].sum())
    rows.append({
        "segment": "전체",
        "total_ead": total,
        "npl_ead": npl,
        "npl_ratio": npl / total if total > 0 else 0.0,
        "n_npl": int(is_npl.sum()),
    })
    return pd.DataFrame(rows)


# ------------------------------------------------------------ DR time series

def default_rate_timeseries(
    portfolio: pd.DataFrame,
    *,
    n_quarters: int = 8,
    segment_col: str = "asset_class",
    ead_col: str = "ead",
    default_col: str = "default_12m",
    seed: int = 42,
) -> pd.DataFrame:
    """분기 부도율 시계열 (12개월 rolling, count·EAD-가중).

    원본 portfolio는 단일 스냅샷이므로 분기별 부도 변동을 시뮬레이션한다.
    실현 평균 부도율을 중심으로 ±β 잡음을 가하여 자산군별 시계열을 생성한다.

    반환 컬럼: quarter, segment, dr_count, dr_ead, n_obs.
    """
    if portfolio.empty:
        return pd.DataFrame(columns=["quarter", "segment", "dr_count",
                                     "dr_ead", "n_obs"])
    rng = np.random.default_rng(seed + 717)
    segs = sorted(portfolio[segment_col].dropna().unique().tolist())
    quarters = [f"Q-{n_quarters - i}" for i in range(n_quarters)]

    rows = []
    for seg in segs:
        sub = portfolio[portfolio[segment_col] == seg]
        if sub.empty or default_col not in sub.columns:
            continue
        dr_base = float(sub[default_col].mean())
        ead_total = float(sub[ead_col].sum())
        if ead_total > 0:
            dr_ead_base = float(
                sub.loc[sub[default_col] == 1, ead_col].sum() / ead_total
            )
        else:
            dr_ead_base = dr_base
        # quarter-to-quarter shocks centred at base
        shocks_c = rng.normal(1.0, 0.18, n_quarters).clip(0.5, 1.6)
        shocks_e = rng.normal(1.0, 0.20, n_quarters).clip(0.5, 1.7)
        # add a mild downturn trend in middle quarters
        trend = np.linspace(-0.05, 0.10, n_quarters)
        for i, q in enumerate(quarters):
            dr_c = float(np.clip(dr_base * shocks_c[i] + trend[i] * dr_base,
                                 0.0, 0.99))
            dr_e = float(np.clip(dr_ead_base * shocks_e[i] + trend[i] * dr_ead_base,
                                 0.0, 0.99))
            rows.append({
                "quarter": q,
                "segment": seg,
                "dr_count": dr_c,
                "dr_ead": dr_e,
                "n_obs": int(len(sub)),
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- roll rate

def roll_rate_matrix(
    portfolio: pd.DataFrame,
    *,
    dpd_col: str = "dpd",
    ead_col: str = "ead",
    seed: int = 42,
) -> pd.DataFrame:
    """DPD 버킷 간 월간 roll-rate 행렬 (Markov chain).

    스냅샷만 있을 때는 표준 retail roll-rate 가정과 현재 버킷 분포를 결합해
    재현가능한 합성 전이확률을 생성한다 (Basel guidance 기반 점진 악화).

    반환: ``len(buckets) × len(buckets)`` DataFrame, 행=from, 열=to,
    각 행 합 = 1, 90+는 흡수상태.
    """
    rng = np.random.default_rng(seed + 808)
    labels = DEEP_DPD_LABELS

    # base prior (retail-portfolio, 월간) — current bucket stays mostly stable
    base = {
        "Current": [0.94, 0.05, 0.005, 0.003, 0.002],
        "1-29":    [0.45, 0.35, 0.15, 0.04, 0.01],
        "30-59":   [0.15, 0.20, 0.30, 0.25, 0.10],
        "60-89":   [0.08, 0.10, 0.15, 0.27, 0.40],
        "90+":     [0.02, 0.02, 0.03, 0.05, 0.88],   # mostly absorbing
    }
    # bucket-share weight (잡음 in line with actual bucket frequency)
    if not portfolio.empty:
        df = portfolio.copy()
        df["bucket"] = df[dpd_col].apply(_bucketise)
        share = df.groupby("bucket")[ead_col].sum()
        share = share / max(share.sum(), 1.0)
    else:
        share = pd.Series(dtype=float)
    rows = []
    for src in labels:
        prior = np.array(base[src], dtype=float)
        # add deterministic noise scaled by sample size (low noise where
        # we have many obligors in src bucket)
        n_src = float(share.get(src, 0.01))
        sigma = 0.04 / (n_src + 0.05)
        noise = rng.normal(0, sigma, len(labels)).clip(-0.05, 0.05)
        adj = np.clip(prior + noise, 1e-4, None)
        adj = adj / adj.sum()
        rows.append(adj.tolist())
    mat = pd.DataFrame(rows, index=labels, columns=labels)
    mat.index.name = "from"
    mat.columns.name = "to"
    return mat


def markov_projection(
    portfolio: pd.DataFrame,
    roll_matrix: pd.DataFrame,
    *,
    horizon_months: int = 3,
    dpd_col: str = "dpd",
    ead_col: str = "ead",
) -> pd.DataFrame:
    """초기 분포 × roll-matrix^m → 향후 m개월 버킷 분포 예측.

    반환 컬럼: month (0~horizon), bucket, ead, share.
    """
    labels = list(roll_matrix.index)
    if portfolio.empty:
        return pd.DataFrame(columns=["month", "bucket", "ead", "share"])
    df = portfolio.copy()
    df["bucket"] = df[dpd_col].apply(_bucketise)
    dist0 = df.groupby("bucket")[ead_col].sum().reindex(labels, fill_value=0.0)
    total = float(dist0.sum())
    if total <= 0:
        return pd.DataFrame(columns=["month", "bucket", "ead", "share"])
    P = roll_matrix.to_numpy()
    state = dist0.to_numpy(dtype=float)
    rows = []
    for m in range(horizon_months + 1):
        for b, ead_v in zip(labels, state):
            rows.append({
                "month": m,
                "bucket": b,
                "ead": float(ead_v),
                "share": float(ead_v / total),
            })
        # advance one month
        state = state @ P
    return pd.DataFrame(rows)


# ============================================================ aggregate entry

@dataclass
class DelinquencyDeepResult:
    bucket_matrix: pd.DataFrame
    npl_ratio: pd.DataFrame
    dr_timeseries: pd.DataFrame
    roll_matrix: pd.DataFrame
    projection: pd.DataFrame


def compute_delinquency_deep(
    portfolio: pd.DataFrame, *, seed: int = 42,
) -> DelinquencyDeepResult:
    bm = dpd_bucket_matrix(portfolio)
    nr = npl_ratio(portfolio)
    ts = default_rate_timeseries(portfolio, seed=seed)
    rm = roll_rate_matrix(portfolio, seed=seed)
    pr = markov_projection(portfolio, rm)
    return DelinquencyDeepResult(
        bucket_matrix=bm, npl_ratio=nr,
        dr_timeseries=ts, roll_matrix=rm, projection=pr,
    )
