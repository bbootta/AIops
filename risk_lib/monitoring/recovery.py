"""Recovery analytics from workout cashflows."""

from __future__ import annotations

import numpy as np
import pandas as pd


def recovery_curve(
    workouts: pd.DataFrame,
    *,
    default_id_col: str = "default_id",
    months_col: str = "months_since_default",
    recovery_col: str = "recovery_amount",
    ead_col: str = "ead_at_default",
    horizon_months: int = 60,
) -> pd.DataFrame:
    """Aggregate cumulative recovery rate vs months since default.

    Returns: month, cum_recovery_rate (average across defaults),
             n_defaults_observed.
    """
    if workouts.empty:
        return pd.DataFrame(columns=["month", "cum_recovery_rate", "n_defaults_observed"])

    # Sum recoveries per default per month, then cumulative, then divide by EAD.
    df = workouts.copy()
    df = df[df[months_col] <= horizon_months]
    grouped = (
        df.groupby([default_id_col, months_col])[recovery_col].sum()
          .reset_index()
    )
    ead = workouts.groupby(default_id_col)[ead_col].first()

    months = range(horizon_months + 1)
    rows = []
    for m in months:
        # cumulative recovery per default up to month m
        cum = (
            grouped[grouped[months_col] <= m]
            .groupby(default_id_col)[recovery_col].sum()
        )
        # align to all defaults (those with no recoveries get 0)
        cum = cum.reindex(ead.index, fill_value=0.0)
        rates = (cum / ead).clip(lower=0.0, upper=1.0)
        rows.append({
            "month": m,
            "cum_recovery_rate": float(rates.mean()),
            "n_defaults_observed": int(len(ead)),
        })
    return pd.DataFrame(rows)


def cumulative_recovery_rate(
    workouts: pd.DataFrame,
    *,
    default_id_col: str = "default_id",
    recovery_col: str = "recovery_amount",
    ead_col: str = "ead_at_default",
) -> float:
    """Portfolio cumulative recovery rate (sum recoveries / sum EAD)."""
    if workouts.empty:
        return 0.0
    rec_total = workouts[recovery_col].sum()
    ead_total = workouts.groupby(default_id_col)[ead_col].first().sum()
    if ead_total <= 0:
        return 0.0
    return float(min(max(rec_total / ead_total, 0.0), 1.0))
