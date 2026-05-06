"""CDR / SDR helpers for PD validation."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_div(num: float, den: float) -> float:
    if den == 0 or den is None or (isinstance(den, float) and np.isnan(den)):
        return float("nan")
    return float(num) / float(den)


def calculate_cdr(default_count: int, exposure_count: int) -> float:
    """Cumulative default rate."""
    if default_count < 0 or exposure_count < 0:
        raise ValueError("Counts must be non-negative.")
    return _safe_div(default_count, exposure_count)


def calculate_sdr(survival_count: int, exposure_count: int) -> float:
    """Survival default rate (defaulted = exposure - survival)."""
    if survival_count < 0 or exposure_count < 0:
        raise ValueError("Counts must be non-negative.")
    if survival_count > exposure_count:
        raise ValueError("survival_count cannot exceed exposure_count.")
    defaults = exposure_count - survival_count
    return _safe_div(defaults, exposure_count)


def summarize_cdr_by_grade(
    df: pd.DataFrame, grade_col: str, default_col: str
) -> pd.DataFrame:
    """Per-grade count, defaults, default rate."""
    for c in (grade_col, default_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    g = df.groupby(grade_col, dropna=False, as_index=False).agg(
        count=(default_col, "size"),
        defaults=(default_col, "sum"),
    )
    g["default_rate"] = g.apply(
        lambda r: _safe_div(r["defaults"], r["count"]), axis=1
    )
    return g.reset_index(drop=True)


def compare_cdr_between_periods(
    base_df: pd.DataFrame,
    current_df: pd.DataFrame,
    grade_col: str,
    default_col: str,
) -> pd.DataFrame:
    """Side-by-side base vs current default rate by grade."""
    base = summarize_cdr_by_grade(base_df, grade_col, default_col).rename(
        columns={"count": "base_count", "defaults": "base_defaults", "default_rate": "base_dr"}
    )
    cur = summarize_cdr_by_grade(current_df, grade_col, default_col).rename(
        columns={"count": "cur_count", "defaults": "cur_defaults", "default_rate": "cur_dr"}
    )
    out = base.merge(cur, on=grade_col, how="outer").sort_values(grade_col).reset_index(drop=True)
    out["dr_diff"] = out["cur_dr"] - out["base_dr"]
    return out
