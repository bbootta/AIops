"""Downturn LGD identification and computation.

Implements the *standard descriptive workflow* for downturn LGD:

  1. Given a default-date series and a macro/portfolio indicator, identify
     which periods qualify as "downturn" based on a caller-supplied rule
     (e.g., quarterly default rate >= a threshold, GDP contraction).
  2. Compute the mean realized LGD on defaults that occurred during
     downturn periods.
  3. Compare to the non-downturn (TTC, through-the-cycle) average.

This module does NOT prescribe which periods are downturn — the caller
supplies the indicator and threshold. Any regulatory definition of
'downturn' is outside scope; see CLAUDE.md §2.
"""
from __future__ import annotations

from typing import Iterable, Mapping

import numpy as np
import pandas as pd


def identify_downturn_periods(
    indicator_df: pd.DataFrame,
    period_col: str,
    indicator_col: str,
    threshold: float,
    direction: str = "higher_is_worse",
) -> pd.DataFrame:
    """Mark periods where the indicator crosses the threshold as downturn.

    Args:
        direction: 'higher_is_worse' (downturn when indicator >= threshold;
            e.g., default rate) or 'lower_is_worse' (downturn when
            indicator <= threshold; e.g., GDP growth).
    """
    if direction not in ("higher_is_worse", "lower_is_worse"):
        raise ValueError("direction must be 'higher_is_worse' or 'lower_is_worse'.")
    for c in (period_col, indicator_col):
        if c not in indicator_df.columns:
            raise ValueError(f"Column missing: {c}")
    work = indicator_df[[period_col, indicator_col]].dropna().copy()
    if direction == "higher_is_worse":
        work["is_downturn"] = work[indicator_col] >= float(threshold)
    else:
        work["is_downturn"] = work[indicator_col] <= float(threshold)
    return work.sort_values(period_col).reset_index(drop=True)


def compute_downturn_lgd(
    obs_df: pd.DataFrame,
    period_col: str,
    realized_lgd_col: str,
    downturn_flags: pd.DataFrame,
    period_col_flags: str = "period",
    is_downturn_col: str = "is_downturn",
) -> dict:
    """Compute downturn vs non-downturn realized LGD means.

    Joins `obs_df` to `downturn_flags` on the period column and reports
    counts + means for each group.
    """
    for c in (period_col, realized_lgd_col):
        if c not in obs_df.columns:
            raise ValueError(f"Column missing in obs_df: {c}")
    for c in (period_col_flags, is_downturn_col):
        if c not in downturn_flags.columns:
            raise ValueError(f"Column missing in downturn_flags: {c}")
    merged = obs_df.merge(
        downturn_flags[[period_col_flags, is_downturn_col]].rename(
            columns={period_col_flags: period_col}
        ),
        on=period_col,
        how="left",
    )
    merged = merged.dropna(subset=[realized_lgd_col])
    if merged.empty:
        raise ValueError("No non-null rows after merge.")
    # Treat rows without a period match as non-downturn (caller can detect
    # via n_unmatched if needed).
    n_unmatched = int(merged[is_downturn_col].isna().sum())
    merged[is_downturn_col] = merged[is_downturn_col].fillna(False).astype(bool)
    down = merged[merged[is_downturn_col]]
    other = merged[~merged[is_downturn_col]]
    down_mean = float(down[realized_lgd_col].mean()) if not down.empty else float("nan")
    other_mean = float(other[realized_lgd_col].mean()) if not other.empty else float("nan")
    diff = down_mean - other_mean if not (
        np.isnan(down_mean) or np.isnan(other_mean)
    ) else float("nan")
    return {
        "n_downturn": int(down.shape[0]),
        "n_non_downturn": int(other.shape[0]),
        "n_unmatched_periods": n_unmatched,
        "mean_lgd_downturn": down_mean,
        "mean_lgd_non_downturn": other_mean,
        "downturn_minus_non_downturn": diff,
    }
