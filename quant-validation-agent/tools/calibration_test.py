"""Statistical calibration tests for PD models.

These tests complement the descriptive calibration table in metric_calibration.py
by providing inferential checks: Hosmer–Lemeshow goodness-of-fit, Spiegelhalter
Z, and a per-bucket binomial test.

All tests assume:
- y in {0, 1}
- pred_pd in [0, 1]

They are descriptive diagnostics; failing a test does NOT establish model
inadequacy by itself. Always combine with sample size, definition checks,
and human review (see CLAUDE.md).
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .target_validation import validate_binary_target, validate_probability_values


def _align(y_true: Iterable, pred_pd: Iterable):
    y = validate_binary_target(y_true)
    p = validate_probability_values(pred_pd)
    if y.shape[0] != p.shape[0]:
        raise ValueError("y_true and pred_pd length mismatch.")
    return y, p


def hosmer_lemeshow_test(
    y_true: Iterable,
    pred_pd: Iterable,
    n_bins: int = 10,
) -> dict:
    """Hosmer–Lemeshow goodness-of-fit test.

    Splits the sample into `n_bins` quantile buckets of pred_pd and computes
    Σ ((O - E)^2 / (E * (1 - E/N_g))) over groups, with df = n_bins - 2.
    Returns the chi-square statistic, df, and p-value.
    """
    if n_bins < 2:
        raise ValueError("n_bins must be >= 2.")
    y, p = _align(y_true, pred_pd)
    if y.shape[0] < n_bins:
        raise ValueError(f"Sample size {y.shape[0]} is smaller than n_bins {n_bins}.")
    ranks = pd.Series(p).rank(method="average", pct=True)
    bins = np.minimum((ranks * n_bins).astype(int), n_bins - 1).values
    chi2 = 0.0
    used_bins = 0
    for b in range(n_bins):
        mask = bins == b
        n_g = int(mask.sum())
        if n_g == 0:
            continue
        used_bins += 1
        observed = float(y[mask].sum())
        expected = float(p[mask].sum())
        denom = expected * (1.0 - expected / n_g) if n_g > 0 else 0.0
        if denom <= 0:
            # Degenerate bucket (all p == 0 or 1, or zero size). Skip safely.
            continue
        chi2 += (observed - expected) ** 2 / denom
    df = max(used_bins - 2, 1)
    try:
        from scipy.stats import chi2 as chi2_dist

        pvalue = float(1.0 - chi2_dist.cdf(chi2, df))
    except Exception:
        pvalue = float("nan")
    return {
        "chi2": float(chi2),
        "df": int(df),
        "pvalue": pvalue,
        "n_bins_used": int(used_bins),
        "n": int(y.shape[0]),
    }


def spiegelhalter_z_test(y_true: Iterable, pred_pd: Iterable) -> dict:
    """Spiegelhalter Z test for overall PD calibration.

    Z = Σ (y - p)(1 - 2p) / sqrt(Σ (1 - 2p)^2 * p * (1 - p))

    Under H0 (perfect calibration), Z ~ N(0, 1). Two-sided p-value reported.
    """
    y, p = _align(y_true, pred_pd)
    # Clip to avoid degenerate variance from p exactly 0 or 1.
    eps = 1e-12
    p_safe = np.clip(p, eps, 1.0 - eps)
    num = float(np.sum((y - p_safe) * (1.0 - 2.0 * p_safe)))
    var = float(np.sum(((1.0 - 2.0 * p_safe) ** 2) * p_safe * (1.0 - p_safe)))
    if var <= 0:
        return {"z": float("nan"), "pvalue": float("nan"), "n": int(y.shape[0])}
    z = num / np.sqrt(var)
    try:
        from scipy.stats import norm

        pvalue = float(2.0 * (1.0 - norm.cdf(abs(z))))
    except Exception:
        pvalue = float("nan")
    return {"z": float(z), "pvalue": pvalue, "n": int(y.shape[0])}


def binomial_calibration_test(
    df: pd.DataFrame,
    pred_col: str,
    actual_col: str,
    bucket_col: str,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Per-bucket exact binomial test of observed vs predicted PD.

    For each bucket: H0 — observed defaults ~ Binomial(N, mean(pred_pd)).
    Returns a per-bucket DataFrame including the two-sided p-value and a
    pass/fail flag at significance `alpha`.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1).")
    for c in (pred_col, actual_col, bucket_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    work = df.dropna(subset=[pred_col, actual_col, bucket_col])
    if work.empty:
        raise ValueError("No non-null rows.")
    try:
        from scipy.stats import binomtest
    except Exception as e:
        raise RuntimeError(f"scipy.stats.binomtest not available: {e}")
    rows = []
    for bucket, g in work.groupby(bucket_col, dropna=False):
        n = int(g.shape[0])
        observed = int(g[actual_col].sum())
        expected_p = float(g[pred_col].mean())
        if n == 0:
            continue
        # binomtest requires p in [0, 1]; clip slightly for numerical safety.
        p_for_test = float(np.clip(expected_p, 1e-12, 1.0 - 1e-12))
        result = binomtest(observed, n, p_for_test, alternative="two-sided")
        rows.append(
            {
                "bucket": bucket,
                "n": n,
                "observed_defaults": observed,
                "expected_pd": expected_p,
                "observed_default_rate": observed / n,
                "pvalue": float(result.pvalue),
                "reject_h0": bool(result.pvalue < alpha),
            }
        )
    return pd.DataFrame(rows).sort_values("bucket").reset_index(drop=True)
