"""Concentration risk metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def hhi(exposures: pd.Series | np.ndarray) -> float:
    """Herfindahl-Hirschman Index = Σ share^2 (1/n .. 1).

    Higher = more concentrated.  A common 'concentrated' threshold is 0.18.
    """
    e = np.asarray(exposures, dtype=float)
    total = e.sum()
    if total <= 0:
        return 0.0
    shares = e / total
    return float(np.sum(shares ** 2))


def normalised_hhi(exposures: pd.Series | np.ndarray) -> float:
    """HHI* = (HHI - 1/n) / (1 - 1/n), scaled to [0, 1]."""
    e = np.asarray(exposures, dtype=float)
    n = len(e[e > 0])
    if n <= 1:
        return 1.0
    h = hhi(e)
    return float((h - 1 / n) / (1 - 1 / n))


def concentration_report(
    portfolio: pd.DataFrame,
    dimensions: list[str],
    *,
    exposure_col: str = "ead",
) -> pd.DataFrame:
    """HHI per dimension (e.g. obligor_id, sector, country)."""
    rows = []
    for dim in dimensions:
        if dim not in portfolio.columns:
            raise ValueError(f"dimension {dim!r} not in portfolio")
        grp = portfolio.groupby(dim)[exposure_col].sum()
        rows.append({
            "dimension": dim,
            "n_buckets": int((grp > 0).sum()),
            "hhi": hhi(grp),
            "normalised_hhi": normalised_hhi(grp),
            "top1_share": float(grp.max() / grp.sum()) if grp.sum() > 0 else 0.0,
        })
    return pd.DataFrame(rows)
