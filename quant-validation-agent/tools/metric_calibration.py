"""Calibration helpers for PD models."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .target_validation import validate_binary_target, validate_probability_values


def build_calibration_table(
    df: pd.DataFrame,
    pred_col: str,
    actual_col: str,
    bucket_col: Optional[str] = None,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Build a calibration table comparing predicted vs realized.

    If `bucket_col` is provided, group by that column.
    Otherwise, group by `n_bins` quantile bins of `pred_col`.
    """
    for c in (pred_col, actual_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    work = df.dropna(subset=[pred_col, actual_col]).copy()
    if work.empty:
        raise ValueError("No non-null rows for calibration.")
    if bucket_col is None:
        if n_bins < 2:
            raise ValueError("n_bins must be >= 2.")
        ranks = work[pred_col].rank(method="average", pct=True)
        work["__bucket__"] = np.minimum((ranks * n_bins).astype(int), n_bins - 1)
        bucket_col_eff = "__bucket__"
    else:
        if bucket_col not in df.columns:
            raise ValueError(f"bucket_col missing: {bucket_col}")
        bucket_col_eff = bucket_col
    grouped = work.groupby(bucket_col_eff, dropna=False, as_index=False).agg(
        count=(pred_col, "size"),
        mean_pred=(pred_col, "mean"),
        mean_actual=(actual_col, "mean"),
    )
    grouped["diff"] = grouped["mean_pred"] - grouped["mean_actual"]
    return grouped.sort_values(bucket_col_eff).reset_index(drop=True)


def calculate_brier_score(y_true, pred_pd) -> float:
    """Mean squared error between PD and binary outcome."""
    y = validate_binary_target(y_true)
    p = validate_probability_values(pred_pd)
    if y.shape[0] != p.shape[0]:
        raise ValueError("Length mismatch.")
    return float(np.mean((p - y) ** 2))


def calculate_pd_bias(df: pd.DataFrame, pred_pd_col: str, default_col: str) -> dict:
    """Mean predicted PD vs observed default rate; returns absolute and relative bias."""
    for c in (pred_pd_col, default_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    work = df.dropna(subset=[pred_pd_col, default_col])
    if work.empty:
        raise ValueError("No non-null rows for PD bias.")
    mean_pred = float(work[pred_pd_col].mean())
    mean_obs = float(work[default_col].mean())
    abs_bias = mean_pred - mean_obs
    rel_bias = abs_bias / mean_obs if mean_obs != 0 else float("nan")
    return {
        "n": int(work.shape[0]),
        "mean_predicted_pd": mean_pred,
        "observed_default_rate": mean_obs,
        "abs_bias": abs_bias,
        "rel_bias": rel_bias,
    }


def summarize_observed_vs_predicted(
    df: pd.DataFrame, pred_col: str, actual_col: str, group_col: str
) -> pd.DataFrame:
    """Group-wise observed vs predicted summary."""
    for c in (pred_col, actual_col, group_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    grouped = df.groupby(group_col, dropna=False, as_index=False).agg(
        count=(pred_col, "size"),
        mean_pred=(pred_col, "mean"),
        mean_actual=(actual_col, "mean"),
    )
    grouped["diff"] = grouped["mean_pred"] - grouped["mean_actual"]
    return grouped.sort_values(group_col).reset_index(drop=True)
