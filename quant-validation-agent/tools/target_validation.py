"""Target / score validation helpers."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def validate_binary_target(y: Iterable) -> np.ndarray:
    """Validate that y is binary 0/1.

    Returns:
        np.ndarray of int (0/1).

    Raises:
        ValueError on non-binary, NaN, or empty input.
    """
    arr = np.asarray(list(y))
    if arr.size == 0:
        raise ValueError("Target is empty.")
    if pd.isna(arr).any():
        raise ValueError("Target contains NaN.")
    unique = set(np.unique(arr).tolist())
    allowed = {0, 1, 0.0, 1.0, True, False}
    if not unique.issubset(allowed):
        raise ValueError(f"Target must be binary 0/1; got: {sorted(unique)}")
    return arr.astype(int)


def validate_probability_values(values: Iterable) -> np.ndarray:
    """Validate that values are within [0, 1] and not NaN."""
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("Probability values are empty.")
    if np.isnan(arr).any():
        raise ValueError("Probability values contain NaN.")
    if (arr < 0).any() or (arr > 1).any():
        bad_min = float(np.nanmin(arr))
        bad_max = float(np.nanmax(arr))
        raise ValueError(
            f"Probability values must be in [0,1]; observed min={bad_min}, max={bad_max}"
        )
    return arr


def infer_score_direction(y_true: Iterable, score: Iterable) -> dict:
    """Infer whether higher score implies higher risk (default=1) or lower risk.

    Computes mean score for default=1 vs default=0 and compares.
    Returns a dict with 'higher_is_worse' (bool) and the two means.
    """
    y = np.asarray(list(y_true)).astype(int)
    s = np.asarray(list(score), dtype=float)
    if y.shape[0] != s.shape[0]:
        raise ValueError("y_true and score length mismatch.")
    if not np.any(y == 1) or not np.any(y == 0):
        raise ValueError("Cannot infer direction without both 0 and 1 in y_true.")
    mean_bad = float(np.nanmean(s[y == 1]))
    mean_good = float(np.nanmean(s[y == 0]))
    return {
        "mean_score_bad": mean_bad,
        "mean_score_good": mean_good,
        "higher_is_worse": mean_bad > mean_good,
    }


def check_default_rate(y_true: Iterable) -> dict:
    """Return total, defaults, and rate."""
    arr = validate_binary_target(y_true)
    n = int(arr.shape[0])
    d = int(arr.sum())
    return {
        "n": n,
        "defaults": d,
        "default_rate": (d / n) if n > 0 else float("nan"),
    }
