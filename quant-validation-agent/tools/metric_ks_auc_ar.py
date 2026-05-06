"""KS / AUROC / Gini-AR / decile lift for scoring & PD models."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .target_validation import validate_binary_target


def _to_arrays(y_true: Iterable, score: Iterable):
    y = validate_binary_target(y_true)
    s = np.asarray(list(score), dtype=float)
    if s.shape[0] != y.shape[0]:
        raise ValueError("y_true and score length mismatch.")
    if np.isnan(s).any():
        raise ValueError("score contains NaN.")
    return y, s


def calculate_ks(y_true: Iterable, score: Iterable, higher_is_worse: bool = True) -> float:
    """Kolmogorov–Smirnov statistic.

    Args:
        higher_is_worse: True if higher score means higher default risk.
    """
    y, s = _to_arrays(y_true, score)
    if not higher_is_worse:
        s = -s
    order = np.argsort(s)
    y_sorted = y[order]
    n_pos = max(int(y.sum()), 1)
    n_neg = max(int((1 - y).sum()), 1)
    cum_pos = np.cumsum(y_sorted) / n_pos
    cum_neg = np.cumsum(1 - y_sorted) / n_neg
    return float(np.max(np.abs(cum_pos - cum_neg)))


def calculate_auc(y_true: Iterable, score: Iterable, higher_is_worse: bool = True) -> float:
    """AUROC computed via Mann–Whitney U (no sklearn dependency)."""
    y, s = _to_arrays(y_true, score)
    if not higher_is_worse:
        s = -s
    pos = s[y == 1]
    neg = s[y == 0]
    if pos.size == 0 or neg.size == 0:
        raise ValueError("AUC requires both positive and negative samples.")
    # rank-based computation
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    # average ranks for ties
    df = pd.DataFrame({"s": s, "r": ranks})
    df["r"] = df.groupby("s")["r"].transform("mean")
    sum_pos_ranks = df.loc[y == 1, "r"].sum()
    n_p = pos.size
    n_n = neg.size
    auc = (sum_pos_ranks - n_p * (n_p + 1) / 2.0) / (n_p * n_n)
    return float(auc)


def calculate_gini(y_true: Iterable, score: Iterable, higher_is_worse: bool = True) -> float:
    """Gini = 2 * AUC - 1."""
    return 2.0 * calculate_auc(y_true, score, higher_is_worse=higher_is_worse) - 1.0


def calculate_accuracy_ratio(
    y_true: Iterable, score: Iterable, higher_is_worse: bool = True
) -> float:
    """Accuracy Ratio (a.k.a. Gini)."""
    return calculate_gini(y_true, score, higher_is_worse=higher_is_worse)


def build_decile_table(
    y_true: Iterable,
    score: Iterable,
    n_bins: int = 10,
    higher_is_worse: bool = True,
) -> pd.DataFrame:
    """Group by score deciles and compute count, defaults, default rate."""
    y, s = _to_arrays(y_true, score)
    if n_bins < 2:
        raise ValueError("n_bins must be >= 2.")
    s_for_bin = s if higher_is_worse else -s
    # rank-based binning to avoid duplicate edge issues
    ranks = pd.Series(s_for_bin).rank(method="average", pct=True)
    bins = np.minimum((ranks * n_bins).astype(int), n_bins - 1)
    df = pd.DataFrame({"bin": bins.values, "y": y, "score": s})
    grouped = df.groupby("bin", as_index=False).agg(
        count=("y", "size"),
        defaults=("y", "sum"),
        score_min=("score", "min"),
        score_max=("score", "max"),
    )
    grouped["default_rate"] = grouped["defaults"] / grouped["count"].clip(lower=1)
    grouped = grouped.sort_values("bin").reset_index(drop=True)
    return grouped
