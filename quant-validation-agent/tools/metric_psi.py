"""Population Stability Index (PSI)."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

DEFAULT_EPSILON = 1e-6


def _to_array(x: Iterable) -> np.ndarray:
    arr = np.asarray(list(x), dtype=float)
    if arr.size == 0:
        raise ValueError("Input is empty.")
    if np.isnan(arr).any():
        raise ValueError("Input contains NaN.")
    return arr


def calculate_psi(
    expected: Iterable,
    actual: Iterable,
    bins: int = 10,
    epsilon: float = DEFAULT_EPSILON,
) -> float:
    """Compute PSI between two continuous distributions using quantile binning of `expected`.

    Args:
        bins: number of quantile bins from `expected`. Must be >= 2.
        epsilon: small value added to bucket ratios to avoid division by zero.
    """
    if bins < 2:
        raise ValueError("bins must be >= 2.")
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0.")
    e = _to_array(expected)
    a = _to_array(actual)
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(e, quantiles))
    if edges.size < 2:
        raise ValueError("expected has insufficient variation for binning.")
    edges[0] = -np.inf
    edges[-1] = np.inf
    e_counts, _ = np.histogram(e, bins=edges)
    a_counts, _ = np.histogram(a, bins=edges)
    e_ratio = e_counts / max(e_counts.sum(), 1)
    a_ratio = a_counts / max(a_counts.sum(), 1)
    e_ratio = np.where(e_ratio == 0, epsilon, e_ratio)
    a_ratio = np.where(a_ratio == 0, epsilon, a_ratio)
    psi = float(np.sum((a_ratio - e_ratio) * np.log(a_ratio / e_ratio)))
    if not np.isfinite(psi):
        raise ValueError(
            f"PSI is non-finite ({psi}); inputs may have degenerate distributions."
        )
    return psi


def calculate_psi_by_bucket(
    expected_bucket: Iterable,
    actual_bucket: Iterable,
    epsilon: float = DEFAULT_EPSILON,
) -> float:
    """PSI when buckets are pre-assigned (e.g., grades)."""
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0.")
    e = pd.Series(list(expected_bucket)).astype("object")
    a = pd.Series(list(actual_bucket)).astype("object")
    if e.empty or a.empty:
        raise ValueError("Buckets are empty.")
    cats = sorted(set(e.unique()).union(set(a.unique())), key=str)
    e_counts = np.array([(e == c).sum() for c in cats], dtype=float)
    a_counts = np.array([(a == c).sum() for c in cats], dtype=float)
    e_ratio = e_counts / max(e_counts.sum(), 1)
    a_ratio = a_counts / max(a_counts.sum(), 1)
    e_ratio = np.where(e_ratio == 0, epsilon, e_ratio)
    a_ratio = np.where(a_ratio == 0, epsilon, a_ratio)
    psi = float(np.sum((a_ratio - e_ratio) * np.log(a_ratio / e_ratio)))
    if not np.isfinite(psi):
        raise ValueError(
            f"PSI is non-finite ({psi}); buckets may be empty or degenerate."
        )
    return psi


def build_distribution_table(
    expected: Iterable,
    actual: Iterable,
    bins: int = 10,
    epsilon: float = DEFAULT_EPSILON,
) -> pd.DataFrame:
    """Per-bin distribution and PSI contribution for two continuous samples."""
    if bins < 2:
        raise ValueError("bins must be >= 2.")
    e = _to_array(expected)
    a = _to_array(actual)
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(e, quantiles))
    if edges.size < 2:
        raise ValueError("expected has insufficient variation for binning.")
    edges[0] = -np.inf
    edges[-1] = np.inf
    e_counts, _ = np.histogram(e, bins=edges)
    a_counts, _ = np.histogram(a, bins=edges)
    e_ratio = e_counts / max(e_counts.sum(), 1)
    a_ratio = a_counts / max(a_counts.sum(), 1)
    e_safe = np.where(e_ratio == 0, epsilon, e_ratio)
    a_safe = np.where(a_ratio == 0, epsilon, a_ratio)
    contrib = (a_safe - e_safe) * np.log(a_safe / e_safe)
    return pd.DataFrame(
        {
            "bin_index": np.arange(len(e_counts)),
            "edge_low": edges[:-1],
            "edge_high": edges[1:],
            "expected_count": e_counts,
            "actual_count": a_counts,
            "expected_ratio": e_ratio,
            "actual_ratio": a_ratio,
            "psi_contribution": contrib,
        }
    )
