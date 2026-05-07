"""Decile lift table and KS plot coordinates for scoring / PD models."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .target_validation import validate_binary_target


def _prepare(y_true: Iterable, score: Iterable, higher_is_worse: bool):
    y = validate_binary_target(y_true)
    s = np.asarray(list(score), dtype=float)
    if s.shape[0] != y.shape[0]:
        raise ValueError("y_true and score length mismatch.")
    if np.isnan(s).any():
        raise ValueError("score contains NaN.")
    s_for_order = s if higher_is_worse else -s
    return y, s, s_for_order


def build_lift_table(
    y_true: Iterable,
    score: Iterable,
    n_bins: int = 10,
    higher_is_worse: bool = True,
) -> pd.DataFrame:
    """Return a per-bucket lift table.

    Buckets are ranked so that bucket 0 is the *worst* (highest predicted risk
    when higher_is_worse=True) and the last bucket is the best.
    Cumulative gain and lift are computed from the worst bucket.
    """
    if n_bins < 2:
        raise ValueError("n_bins must be >= 2.")
    y, s, s_for_order = _prepare(y_true, score, higher_is_worse)
    # Rank descending so worst-risk first when higher_is_worse=True
    ranks_desc = pd.Series(-s_for_order).rank(method="average", pct=True)
    bins = np.minimum((ranks_desc * n_bins).astype(int), n_bins - 1).values
    df = pd.DataFrame({"bin": bins, "y": y, "score": s})
    grouped = df.groupby("bin", as_index=False).agg(
        count=("y", "size"),
        defaults=("y", "sum"),
        score_min=("score", "min"),
        score_max=("score", "max"),
    )
    grouped["bin"] = grouped["bin"].astype(int)
    grouped = grouped.sort_values("bin").reset_index(drop=True)
    n_total = max(int(df.shape[0]), 1)
    n_def_total = max(int(df["y"].sum()), 1)
    grouped["bucket_default_rate"] = grouped["defaults"] / grouped["count"].clip(lower=1)
    grouped["cum_count"] = grouped["count"].cumsum()
    grouped["cum_defaults"] = grouped["defaults"].cumsum()
    grouped["cum_pop_share"] = grouped["cum_count"] / n_total
    grouped["cum_default_share"] = grouped["cum_defaults"] / n_def_total
    base_rate = n_def_total / n_total
    grouped["lift"] = np.where(
        grouped["cum_pop_share"] > 0,
        grouped["cum_default_share"] / grouped["cum_pop_share"] / max(base_rate, 1e-12),
        np.nan,
    )
    return grouped


def ks_plot_coordinates(
    y_true: Iterable,
    score: Iterable,
    higher_is_worse: bool = True,
) -> pd.DataFrame:
    """Cumulative bad/good distribution coordinates and per-row KS distance.

    Returns columns: rank_pct, cum_bad, cum_good, ks_distance.
    """
    y, _, s_for_order = _prepare(y_true, score, higher_is_worse)
    order = np.argsort(s_for_order)  # ascending of "risk" so high-risk last
    y_sorted = y[order]
    n = y.shape[0]
    n_bad = max(int(y.sum()), 1)
    n_good = max(int((1 - y).sum()), 1)
    cum_bad = np.cumsum(y_sorted) / n_bad
    cum_good = np.cumsum(1 - y_sorted) / n_good
    rank_pct = np.arange(1, n + 1) / n
    return pd.DataFrame(
        {
            "rank_pct": rank_pct,
            "cum_bad": cum_bad,
            "cum_good": cum_good,
            "ks_distance": np.abs(cum_bad - cum_good),
        }
    )
