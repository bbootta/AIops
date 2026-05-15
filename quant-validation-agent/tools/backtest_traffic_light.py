"""Basel-style traffic-light backtest for PD models.

The concept (binomial-test based zoning of exception counts) is widely
documented in BIS publications for market risk VaR backtesting and has
been adapted for credit risk PD backtesting in academic and industry
literature. This module implements only the *standard binomial-test
zoning* — it does NOT cite specific regulatory paragraphs.

Inputs
------
- Observed defaults per bucket / period (counts)
- Predicted PD per bucket / period
- Sample size per bucket / period

Method
------
For each bucket, treat the observed default count `k` as a sample from
Binomial(n, p) where `p` is the predicted PD. Compute the one-sided
right-tailed p-value (probability of observing at least k defaults
under H0 that the model's PD is correct). Map the p-value to a zone:

  Green  : p_value >= alpha_green  (no evidence of under-prediction)
  Yellow : alpha_red <= p_value < alpha_green
  Red    : p_value < alpha_red    (strong evidence of under-prediction)

Defaults: alpha_green=0.05, alpha_red=0.0001. These align with widely
referenced conventions; callers may override per policy.

The output is *descriptive*. It does NOT establish model adequacy on
its own — sample size, definition consistency, and economic context
must be considered (see CLAUDE.md §8).
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


def _binomial_right_tail(k: int, n: int, p: float) -> float:
    """One-sided right-tailed binomial p-value: P(X >= k | n, p)."""
    if n <= 0:
        return float("nan")
    if k <= 0:
        return 1.0
    if p <= 0:
        return 0.0 if k > 0 else 1.0
    if p >= 1:
        return 1.0 if k <= n else 0.0
    try:
        from scipy.stats import binom

        # P(X >= k) = 1 - P(X <= k-1) = sf(k-1)
        return float(binom.sf(k - 1, n, p))
    except Exception:
        # Manual fallback using survival via cumulative ln-gamma. Accurate enough
        # for the test cases used by this module.
        from math import lgamma, log, exp

        def log_choose(n, k):
            return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)

        total = 0.0
        for j in range(k, n + 1):
            log_pmf = log_choose(n, j) + j * log(p) + (n - j) * log(1.0 - p)
            total += exp(log_pmf)
        return float(min(max(total, 0.0), 1.0))


def classify_zone(pvalue: float, alpha_green: float = 0.05,
                  alpha_red: float = 0.0001) -> str:
    """Return 'Green', 'Yellow', 'Red', or 'Gray' for a p-value."""
    if pvalue is None or (isinstance(pvalue, float) and np.isnan(pvalue)):
        return "Gray"
    if not 0 < alpha_red < alpha_green < 1:
        raise ValueError("require 0 < alpha_red < alpha_green < 1")
    if pvalue >= alpha_green:
        return "Green"
    if pvalue >= alpha_red:
        return "Yellow"
    return "Red"


def traffic_light_per_bucket(
    df: pd.DataFrame,
    n_col: str,
    defaults_col: str,
    pred_pd_col: str,
    bucket_col: Optional[str] = None,
    alpha_green: float = 0.05,
    alpha_red: float = 0.0001,
) -> pd.DataFrame:
    """Per-bucket traffic-light zoning.

    If `bucket_col` is None, treats the whole dataframe as one bucket.
    """
    for c in (n_col, defaults_col, pred_pd_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    if bucket_col is not None and bucket_col not in df.columns:
        raise ValueError(f"bucket_col missing: {bucket_col}")
    work = df.dropna(subset=[n_col, defaults_col, pred_pd_col]).copy()
    if work.empty:
        raise ValueError("No non-null rows.")
    if bucket_col is None:
        n_total = int(work[n_col].sum())
        d_total = int(work[defaults_col].sum())
        # Sample-weighted mean predicted PD
        p_mean = float((work[pred_pd_col] * work[n_col]).sum() / max(n_total, 1))
        pv = _binomial_right_tail(d_total, n_total, p_mean)
        zone = classify_zone(pv, alpha_green, alpha_red)
        return pd.DataFrame([{
            "bucket": "__all__",
            "n": n_total,
            "defaults": d_total,
            "predicted_pd": p_mean,
            "pvalue": pv,
            "zone": zone,
            "alpha_green": alpha_green,
            "alpha_red": alpha_red,
        }])
    rows = []
    for bucket, g in work.groupby(bucket_col, dropna=False):
        n_b = int(g[n_col].sum())
        d_b = int(g[defaults_col].sum())
        p_b = float((g[pred_pd_col] * g[n_col]).sum() / max(n_b, 1)) if n_b > 0 else float("nan")
        pv = _binomial_right_tail(d_b, n_b, p_b) if n_b > 0 else float("nan")
        zone = classify_zone(pv, alpha_green, alpha_red)
        rows.append({
            "bucket": bucket,
            "n": n_b,
            "defaults": d_b,
            "predicted_pd": p_b,
            "pvalue": pv,
            "zone": zone,
            "alpha_green": alpha_green,
            "alpha_red": alpha_red,
        })
    return pd.DataFrame(rows).sort_values("bucket").reset_index(drop=True)


def aggregate_zone(per_bucket: pd.DataFrame) -> str:
    """Worst zone across per-bucket rows."""
    if per_bucket is None or per_bucket.empty:
        return "Gray"
    rank = {"Gray": 0, "Green": 1, "Yellow": 2, "Red": 3}
    worst = max(per_bucket["zone"].tolist(), key=lambda z: rank.get(z, 0))
    return worst
