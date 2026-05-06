"""Sample-size guard.

Wraps tools.sample_size_check with policy-driven thresholds and returns RAG.
Threshold values are inputs (no hardcoding policy). Defaults are conservative
references aligned with `harness/threshold_policy.md`.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from tools import sample_size_check


def evaluate_sample_size(
    df: pd.DataFrame,
    grade_col: Optional[str] = None,
    default_col: Optional[str] = None,
    min_n_green: int = 5000,
    min_n_yellow: int = 1000,
    min_defaults_green: int = 200,
    min_defaults_yellow: int = 50,
    min_grade_count_green: int = 30,
    min_grade_count_yellow: int = 10,
) -> dict:
    """Return a structured RAG-style sample-size summary."""
    n = int(df.shape[0])
    if n >= min_n_green:
        n_status = "Green"
    elif n >= min_n_yellow:
        n_status = "Yellow"
    else:
        n_status = "Red"

    out: dict = {
        "n": n,
        "n_status": n_status,
        "n_threshold_green": min_n_green,
        "n_threshold_yellow": min_n_yellow,
    }

    if default_col is not None and default_col in df.columns:
        d = int(df[default_col].fillna(0).astype(int).sum())
        if d >= min_defaults_green:
            d_status = "Green"
        elif d >= min_defaults_yellow:
            d_status = "Yellow"
        else:
            d_status = "Red"
        out.update(
            {
                "defaults": d,
                "defaults_status": d_status,
                "defaults_threshold_green": min_defaults_green,
                "defaults_threshold_yellow": min_defaults_yellow,
            }
        )

    if grade_col is not None and grade_col in df.columns:
        per_grade = sample_size_check.check_grade_level_counts(
            df, grade_col, min_grade_count_yellow
        )
        worst = int(per_grade["count"].min()) if not per_grade.empty else 0
        if worst >= min_grade_count_green:
            g_status = "Green"
        elif worst >= min_grade_count_yellow:
            g_status = "Yellow"
        else:
            g_status = "Red"
        out.update(
            {
                "min_grade_count": worst,
                "grade_status": g_status,
                "grade_threshold_green": min_grade_count_green,
                "grade_threshold_yellow": min_grade_count_yellow,
                "per_grade_counts": per_grade.to_dict(orient="records"),
            }
        )

    return out
