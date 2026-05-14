"""Binning stability and rank-ordering checks."""
from __future__ import annotations

import pandas as pd


def check_rank_ordering(
    df: pd.DataFrame, grade_col: str, bad_rate_col: str
) -> dict:
    """Check whether bad rate is monotonic across ordered grades.

    Grades are ordered by their natural sort.
    """
    for c in (grade_col, bad_rate_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    s = (
        df[[grade_col, bad_rate_col]]
        .dropna()
        .sort_values(grade_col)
        .reset_index(drop=True)
    )
    if s.shape[0] < 2:
        return {"monotonic_increasing": None, "monotonic_decreasing": None, "n_grades": int(s.shape[0])}
    vals = s[bad_rate_col].astype(float).values
    diffs = vals[1:] - vals[:-1]
    return {
        "monotonic_increasing": bool((diffs >= 0).all()),
        "monotonic_decreasing": bool((diffs <= 0).all()),
        "n_grades": int(s.shape[0]),
        "n_inversions": int((diffs > 0).sum() if (diffs <= 0).all() else (diffs < 0).sum() if (diffs >= 0).all() else (diffs < 0).sum() + (diffs > 0).sum()),
    }


def compare_grade_distribution(
    base_df: pd.DataFrame, current_df: pd.DataFrame, grade_col: str
) -> pd.DataFrame:
    """Side-by-side distribution by grade between two snapshots."""
    for d, name in ((base_df, "base"), (current_df, "current")):
        if grade_col not in d.columns:
            raise ValueError(f"grade_col missing in {name}: {grade_col}")
    base_counts = base_df[grade_col].value_counts(dropna=False).rename("base_count")
    cur_counts = current_df[grade_col].value_counts(dropna=False).rename("cur_count")
    out = pd.concat([base_counts, cur_counts], axis=1).fillna(0).astype(int)
    base_total = max(int(out["base_count"].sum()), 1)
    cur_total = max(int(out["cur_count"].sum()), 1)
    out["base_ratio"] = out["base_count"] / base_total
    out["cur_ratio"] = out["cur_count"] / cur_total
    out["ratio_diff"] = out["cur_ratio"] - out["base_ratio"]
    out = out.reset_index().rename(columns={"index": grade_col})
    return out.sort_values(grade_col).reset_index(drop=True)


def detect_grade_inversion(
    df: pd.DataFrame, grade_col: str, metric_col: str, ascending: bool = True
) -> pd.DataFrame:
    """Return adjacent grade pairs whose `metric_col` violates the expected order.

    If ascending=True, we expect metric to increase as grade index increases.

    Accepts pandas nullable dtypes (Int64/Float64) by converting `metric_col`
    to a plain float and dropping `pd.NA` before sorting.
    """
    import numpy as _np

    for c in (grade_col, metric_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    work = df[[grade_col, metric_col]].copy()
    # Force float64 for the metric column to neutralize Int64/Float64 / pd.NA.
    work[metric_col] = pd.to_numeric(work[metric_col], errors="coerce").astype("float64")
    # And drop NaN rows in either column.
    work = work[~work[grade_col].isna() & ~_np.isnan(work[metric_col])]
    s = (
        work[[grade_col, metric_col]]
        .sort_values(grade_col)
        .reset_index(drop=True)
    )
    rows = []
    for i in range(1, s.shape[0]):
        prev_g = s.loc[i - 1, grade_col]
        cur_g = s.loc[i, grade_col]
        prev_v = float(s.loc[i - 1, metric_col])
        cur_v = float(s.loc[i, metric_col])
        violated = (prev_v > cur_v) if ascending else (prev_v < cur_v)
        if violated:
            rows.append(
                {
                    "from_grade": prev_g,
                    "to_grade": cur_g,
                    "from_value": prev_v,
                    "to_value": cur_v,
                    "expected": "ascending" if ascending else "descending",
                }
            )
    return pd.DataFrame(rows)
