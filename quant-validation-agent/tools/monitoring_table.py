"""Time × grade monitoring tables for ongoing model validation."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .metric_psi import calculate_psi_by_bucket


def build_time_grade_matrix(
    df: pd.DataFrame,
    date_col: str,
    grade_col: str,
    default_col: str,
    count_col: Optional[str] = None,
) -> pd.DataFrame:
    """Build a long-form (date, grade) panel of count / defaults / default_rate.

    Args:
        count_col: optional pre-aggregated count. If None, count = len(rows).
    """
    for c in (date_col, grade_col, default_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    if count_col is not None and count_col not in df.columns:
        raise ValueError(f"count_col missing: {count_col}")

    if count_col is None:
        agg = (
            df.groupby([date_col, grade_col], dropna=False, as_index=False)
            .agg(count=(default_col, "size"), defaults=(default_col, "sum"))
        )
    else:
        agg = (
            df.groupby([date_col, grade_col], dropna=False, as_index=False)
            .agg(count=(count_col, "sum"), defaults=(default_col, "sum"))
        )
    agg["default_rate"] = np.where(
        agg["count"] > 0, agg["defaults"] / agg["count"].clip(lower=1), float("nan")
    )
    return agg.sort_values([date_col, grade_col]).reset_index(drop=True)


def compute_period_psi_vs_baseline(
    df: pd.DataFrame,
    date_col: str,
    grade_col: str,
    baseline_period,
    count_col: Optional[str] = None,
) -> pd.DataFrame:
    """For each non-baseline period, compute PSI of grade distribution vs baseline.

    Works on either row-level data (count_col=None) or pre-aggregated data.
    """
    for c in (date_col, grade_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    if count_col is not None and count_col not in df.columns:
        raise ValueError(f"count_col missing: {count_col}")

    if count_col is None:
        period_grade = (
            df.groupby([date_col, grade_col], dropna=False, as_index=False)
            .size()
            .rename(columns={"size": "count"})
        )
    else:
        period_grade = (
            df.groupby([date_col, grade_col], dropna=False, as_index=False)[count_col]
            .sum()
            .rename(columns={count_col: "count"})
        )

    if baseline_period not in period_grade[date_col].unique():
        raise ValueError(f"baseline_period {baseline_period!r} not present in data.")

    base = period_grade[period_grade[date_col] == baseline_period]
    base_buckets = []
    for _, row in base.iterrows():
        base_buckets.extend([row[grade_col]] * int(row["count"]))

    rows = []
    for period in sorted(period_grade[date_col].unique(), key=str):
        if period == baseline_period:
            continue
        cur = period_grade[period_grade[date_col] == period]
        cur_buckets = []
        for _, row in cur.iterrows():
            cur_buckets.extend([row[grade_col]] * int(row["count"]))
        if not base_buckets or not cur_buckets:
            psi_val = float("nan")
        else:
            psi_val = calculate_psi_by_bucket(base_buckets, cur_buckets)
        rows.append({"period": period, "baseline": baseline_period, "psi": psi_val})
    return pd.DataFrame(rows)


def summarize_default_rate_trend(
    df: pd.DataFrame, date_col: str, default_col: str, count_col: Optional[str] = None
) -> pd.DataFrame:
    """Per-period count, defaults, and default rate (no grade dimension)."""
    for c in (date_col, default_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    if count_col is not None and count_col not in df.columns:
        raise ValueError(f"count_col missing: {count_col}")
    if count_col is None:
        agg = (
            df.groupby(date_col, dropna=False, as_index=False)
            .agg(count=(default_col, "size"), defaults=(default_col, "sum"))
        )
    else:
        agg = (
            df.groupby(date_col, dropna=False, as_index=False)
            .agg(count=(count_col, "sum"), defaults=(default_col, "sum"))
        )
    agg["default_rate"] = np.where(
        agg["count"] > 0, agg["defaults"] / agg["count"].clip(lower=1), float("nan")
    )
    return agg.sort_values(date_col).reset_index(drop=True)
