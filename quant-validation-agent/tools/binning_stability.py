"""Binning stability and rank-ordering checks."""
from __future__ import annotations

import pandas as pd


def check_rank_ordering(
    df: pd.DataFrame, grade_col: str, bad_rate_col: str,
    expected: str = "ascending",
) -> dict:
    """Check whether `bad_rate_col` is monotonic across ordered grades.

    Args:
        expected: 'ascending' (bad rate should rise with grade index) or
            'descending'. Used to compute `n_violations` relative to the
            caller's expectation.

    Returns:
        monotonic_increasing / monotonic_decreasing booleans, n_grades,
        n_strict_increases, n_strict_decreases, and n_violations (count of
        adjacent pairs that contradict `expected`).
    """
    if expected not in ("ascending", "descending"):
        raise ValueError("expected must be 'ascending' or 'descending'.")
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
        return {
            "monotonic_increasing": None,
            "monotonic_decreasing": None,
            "n_grades": int(s.shape[0]),
            "n_strict_increases": 0,
            "n_strict_decreases": 0,
            "n_violations": 0,
            "expected": expected,
        }
    vals = s[bad_rate_col].astype(float).values
    diffs = vals[1:] - vals[:-1]
    n_up = int((diffs > 0).sum())
    n_down = int((diffs < 0).sum())
    n_viol = n_down if expected == "ascending" else n_up
    return {
        "monotonic_increasing": bool((diffs >= 0).all()),
        "monotonic_decreasing": bool((diffs <= 0).all()),
        "n_grades": int(s.shape[0]),
        "n_strict_increases": n_up,
        "n_strict_decreases": n_down,
        "n_violations": n_viol,
        "expected": expected,
    }


def compare_grade_distribution(
    base_df: pd.DataFrame, current_df: pd.DataFrame, grade_col: str,
    epsilon: float = 1e-6,
) -> pd.DataFrame:
    """Side-by-side distribution by grade between two snapshots.

    Also emits per-grade PSI contribution `(cur - base) * log(cur / base)`
    using `epsilon` to avoid division by zero, plus a `total_psi` row.
    """
    import numpy as _np

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
    safe_base = out["base_ratio"].where(out["base_ratio"] > 0, epsilon)
    safe_cur = out["cur_ratio"].where(out["cur_ratio"] > 0, epsilon)
    out["psi_contribution"] = (safe_cur - safe_base) * _np.log(safe_cur / safe_base)
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
