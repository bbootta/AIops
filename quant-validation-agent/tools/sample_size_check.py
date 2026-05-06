"""Sample size adequacy checks."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def check_min_observations(df: pd.DataFrame, min_n: int) -> dict:
    """Total row count vs min_n."""
    if min_n < 0:
        raise ValueError("min_n must be >= 0.")
    n = int(df.shape[0])
    return {"n": n, "min_n": int(min_n), "pass": n >= min_n}


def check_min_defaults(df: pd.DataFrame, default_col: str, min_defaults: int) -> dict:
    """Default count vs min_defaults."""
    if default_col not in df.columns:
        raise ValueError(f"default_col missing: {default_col}")
    if min_defaults < 0:
        raise ValueError("min_defaults must be >= 0.")
    d = int(df[default_col].fillna(0).astype(int).sum())
    return {"defaults": d, "min_defaults": int(min_defaults), "pass": d >= min_defaults}


def check_grade_level_counts(
    df: pd.DataFrame, grade_col: str, min_count: int
) -> pd.DataFrame:
    """Per-grade count vs min_count."""
    if grade_col not in df.columns:
        raise ValueError(f"grade_col missing: {grade_col}")
    if min_count < 0:
        raise ValueError("min_count must be >= 0.")
    counts = df[grade_col].value_counts(dropna=False).rename("count").reset_index()
    counts.columns = [grade_col, "count"]
    counts["min_count"] = int(min_count)
    counts["pass"] = counts["count"] >= int(min_count)
    return counts.sort_values(grade_col).reset_index(drop=True)


def summarize_sample_size_issues(
    df: pd.DataFrame,
    grade_col: Optional[str] = None,
    default_col: Optional[str] = None,
) -> dict:
    """High-level sample-size summary across the dataset."""
    out = {"n": int(df.shape[0])}
    if default_col and default_col in df.columns:
        out["defaults"] = int(df[default_col].fillna(0).astype(int).sum())
    if grade_col and grade_col in df.columns:
        counts = df[grade_col].value_counts(dropna=False)
        out["n_grades"] = int(counts.shape[0])
        out["min_grade_count"] = int(counts.min()) if not counts.empty else 0
        out["max_grade_count"] = int(counts.max()) if not counts.empty else 0
    return out
