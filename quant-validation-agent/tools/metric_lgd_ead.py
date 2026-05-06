"""LGD / EAD error metrics."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _to_pair(y_true: Iterable, y_pred: Iterable):
    yt = np.asarray(list(y_true), dtype=float)
    yp = np.asarray(list(y_pred), dtype=float)
    if yt.shape[0] != yp.shape[0]:
        raise ValueError("Length mismatch.")
    if yt.size == 0:
        raise ValueError("Inputs are empty.")
    if np.isnan(yt).any() or np.isnan(yp).any():
        raise ValueError("Inputs contain NaN.")
    return yt, yp


def calculate_mae(y_true: Iterable, y_pred: Iterable) -> float:
    yt, yp = _to_pair(y_true, y_pred)
    return float(np.mean(np.abs(yt - yp)))


def calculate_rmse(y_true: Iterable, y_pred: Iterable) -> float:
    yt, yp = _to_pair(y_true, y_pred)
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def calculate_bias(y_true: Iterable, y_pred: Iterable) -> float:
    """Mean(pred - actual). Positive => over-prediction."""
    yt, yp = _to_pair(y_true, y_pred)
    return float(np.mean(yp - yt))


def validate_lgd_range(lgd_values: Iterable) -> dict:
    """Report counts of negative, in-range, and >100% LGD values.

    Does NOT clip. Caller decides handling per policy.
    """
    arr = np.asarray(list(lgd_values), dtype=float)
    if arr.size == 0:
        raise ValueError("LGD values are empty.")
    n_nan = int(np.isnan(arr).sum())
    finite = arr[~np.isnan(arr)]
    return {
        "n": int(arr.shape[0]),
        "n_nan": n_nan,
        "n_negative": int((finite < 0).sum()),
        "n_above_one": int((finite > 1).sum()),
        "n_in_unit_range": int(((finite >= 0) & (finite <= 1)).sum()),
        "min": float(finite.min()) if finite.size else float("nan"),
        "max": float(finite.max()) if finite.size else float("nan"),
    }


def validate_ead_values(ead_values: Iterable) -> dict:
    """Report counts of negative / NaN EAD values."""
    arr = np.asarray(list(ead_values), dtype=float)
    if arr.size == 0:
        raise ValueError("EAD values are empty.")
    n_nan = int(np.isnan(arr).sum())
    finite = arr[~np.isnan(arr)]
    return {
        "n": int(arr.shape[0]),
        "n_nan": n_nan,
        "n_negative": int((finite < 0).sum()),
        "min": float(finite.min()) if finite.size else float("nan"),
        "max": float(finite.max()) if finite.size else float("nan"),
    }


def summarize_error_by_segment(
    df: pd.DataFrame, actual_col: str, pred_col: str, segment_col: str
) -> pd.DataFrame:
    """Per-segment MAE / RMSE / bias / count."""
    for c in (actual_col, pred_col, segment_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    work = df.dropna(subset=[actual_col, pred_col]).copy()
    if work.empty:
        raise ValueError("No non-null rows.")
    work["__abs_err__"] = (work[actual_col] - work[pred_col]).abs()
    work["__sq_err__"] = (work[actual_col] - work[pred_col]) ** 2
    work["__bias__"] = work[pred_col] - work[actual_col]
    grouped = work.groupby(segment_col, dropna=False, as_index=False).agg(
        count=(actual_col, "size"),
        mae=("__abs_err__", "mean"),
        mse=("__sq_err__", "mean"),
        bias=("__bias__", "mean"),
    )
    grouped["rmse"] = np.sqrt(grouped["mse"])
    grouped = grouped.drop(columns=["mse"])
    return grouped.sort_values(segment_col).reset_index(drop=True)
