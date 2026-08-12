"""Delinquency and default monitoring.

Conventions (금감원 자산건전성 분류 + Basel 90-day default):
  - 정상(Pass): 0 dpd
  - 요주의(Special Mention): 1~89 dpd
  - 고정(Substandard): >= 90 dpd  → default 인식
  - 회수의문(Doubtful), 추정손실(Loss): 추가 분류, 모두 default
"""

from __future__ import annotations

import numpy as np
import pandas as pd


DPD_BUCKETS = [
    ("current", 0, 0),
    ("1-29",   1, 29),
    ("30-59",  30, 59),
    ("60-89",  60, 89),
    ("90-179", 90, 179),
    ("180+",   180, 10_000),
]

DEFAULT_DPD_THRESHOLD = 90  # Basel definition


def _bucket(dpd: int) -> str:
    for name, lo, hi in DPD_BUCKETS:
        if lo <= dpd <= hi:
            return name
    return "180+"


def delinquency_summary(
    loans: pd.DataFrame,
    *,
    balance_col: str = "balance",
    dpd_col: str = "dpd",
    segment_col: str | None = None,
) -> pd.DataFrame:
    """Aggregate balances by DPD bucket (overall or per segment).

    Returns columns: bucket, n_loans, balance, balance_share, delinquency_rate.
    delinquency_rate is share of balance with dpd>=30 within each segment.
    """
    df = loans.copy()
    df["bucket"] = df[dpd_col].apply(_bucket)

    grp_keys = ["bucket"]
    if segment_col:
        grp_keys = [segment_col, "bucket"]

    agg = (
        df.groupby(grp_keys, dropna=False)
          .agg(n_loans=(balance_col, "size"), balance=(balance_col, "sum"))
          .reset_index()
    )

    # Per-segment share + delinquency rate
    seg_key = segment_col if segment_col else None
    if seg_key:
        agg["balance_share"] = agg["balance"] / agg.groupby(seg_key)["balance"].transform("sum")
        delq = (df[df[dpd_col] >= 30].groupby(seg_key)[balance_col].sum()
                / df.groupby(seg_key)[balance_col].sum()).rename("delinquency_rate")
        agg = agg.merge(delq.reset_index(), on=seg_key, how="left")
    else:
        total = agg["balance"].sum()
        agg["balance_share"] = agg["balance"] / max(total, 1e-9)
        delq_total = df.loc[df[dpd_col] >= 30, balance_col].sum() / max(total, 1e-9)
        agg["delinquency_rate"] = delq_total
    return agg


def default_rate(
    loans: pd.DataFrame,
    *,
    dpd_col: str = "dpd",
    weight_col: str | None = None,
    threshold: int = DEFAULT_DPD_THRESHOLD,
) -> float:
    """Annual default rate.

    Count-weighted by default; supply weight_col (e.g. 'ead') for exposure-weighted.
    """
    if loans.empty:
        return 0.0
    is_default = loans[dpd_col] >= threshold
    if weight_col is None:
        return float(is_default.mean())
    w = loans[weight_col].astype(float)
    total = w.sum()
    if total <= 0:
        return 0.0
    return float(w[is_default].sum() / total)


def transition_matrix(
    snapshot_t0: pd.DataFrame,
    snapshot_t1: pd.DataFrame,
    *,
    key: str = "exposure_id",
    grade_col: str = "rating",
    grades: list[str] | None = None,
) -> pd.DataFrame:
    """Rating transition matrix between two snapshots.

    Rows are t0 grade, columns t1 grade; values are probabilities (row sum=1).
    A 'DEFAULT' absorbing state can be included by setting grade to 'DEFAULT'
    in snapshot_t1 for defaulted obligors.
    """
    merged = snapshot_t0[[key, grade_col]].merge(
        snapshot_t1[[key, grade_col]], on=key, suffixes=("_t0", "_t1")
    )
    if grades is None:
        grades = sorted(set(merged[f"{grade_col}_t0"]).union(merged[f"{grade_col}_t1"]))
    mat = pd.crosstab(
        merged[f"{grade_col}_t0"],
        merged[f"{grade_col}_t1"],
    ).reindex(columns=grades, fill_value=0)
    # Only keep rows for grades that had at least one obligor at t0
    mat = mat.loc[mat.sum(axis=1) > 0]
    row_sums = mat.sum(axis=1)
    return mat.div(row_sums, axis=0)
