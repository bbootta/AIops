"""Synthetic data generators with analytically-known properties.

Every generator takes a `seed` so tests are reproducible.

Most generators expose either the gold-standard expected value (e.g.,
`expected_auc` for two-normal mixture) or a property the tool should
respect (e.g., 'must classify as Red zone').
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


# ----------------------------- discrimination ---------------------------------

def perfect_separator(n: int = 1000, seed: int = 1):
    """All y=1 above all y=0. KS=1, AUC=1, AR=1, top-decile lift = n / n_bad."""
    rng = np.random.default_rng(seed)
    y = rng.binomial(1, 0.3, size=n)
    # Score: y=1 gets [100, 200], y=0 gets [0, 99]
    score = np.where(y == 1,
                     rng.uniform(100, 200, size=n),
                     rng.uniform(0, 99, size=n))
    return y, score


def two_normal_mixture(n: int = 5000, shift: float = 1.5, bad_rate: float = 0.3,
                       seed: int = 2) -> Tuple[np.ndarray, np.ndarray, float]:
    """Two normals separated by `shift` (in pooled sd units).

    Analytical AUC = Phi(shift / sqrt(2)) for equal-variance normals.
    Returns (y, score, expected_auc).
    """
    from scipy.stats import norm

    rng = np.random.default_rng(seed)
    y = rng.binomial(1, bad_rate, size=n)
    score = np.where(y == 1,
                     rng.normal(shift, 1.0, size=n),
                     rng.normal(0.0, 1.0, size=n))
    expected_auc = float(norm.cdf(shift / np.sqrt(2.0)))
    return y, score, expected_auc


def random_score(n: int = 5000, bad_rate: float = 0.3, seed: int = 3):
    """Score independent of y. AUC ≈ 0.5."""
    rng = np.random.default_rng(seed)
    y = rng.binomial(1, bad_rate, size=n)
    score = rng.normal(0, 1, size=n)
    return y, score


# ------------------------------- calibration ---------------------------------

def well_calibrated_pd(n: int = 5000, seed: int = 11):
    """pred_pd ~ Beta(2, 8); y = Bernoulli(pred_pd). Expected:
    - Brier ≈ mean(pred_pd*(1-pred_pd))
    - HL p-value > 0.05 in large samples
    """
    rng = np.random.default_rng(seed)
    p = np.clip(rng.beta(2, 8, size=n), 1e-4, 1 - 1e-4)
    y = (rng.uniform(size=n) < p).astype(int)
    return y, p


def miscalibrated_pd(n: int = 5000, factor: float = 0.5, seed: int = 12):
    """True PD = pred_pd / factor (i.e., predicted is too small if factor<1)."""
    rng = np.random.default_rng(seed)
    p_true = np.clip(rng.beta(2, 8, size=n), 1e-4, 1 - 1e-4)
    pred = np.clip(p_true * factor, 1e-4, 1 - 1e-4)
    y = (rng.uniform(size=n) < p_true).astype(int)
    return y, pred


# --------------------------------- PSI ---------------------------------------

def identical_distributions(n: int = 5000, seed: int = 21):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 1, size=n)
    cur = rng.normal(0, 1, size=n)  # different draws, same distribution
    return base, cur


def shifted_distribution(n: int = 5000, mean_shift: float = 1.0, seed: int = 22):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 1, size=n)
    cur = rng.normal(mean_shift, 1, size=n)
    return base, cur


def disjoint_distribution(n: int = 5000, seed: int = 23):
    """Almost no overlap; PSI should be very large."""
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 0.5, size=n)
    cur = rng.normal(6, 0.5, size=n)
    return base, cur


# --------------------------------- LGD ---------------------------------------

def lgd_constant_error(n: int = 200, true_lgd: float = 0.5,
                       pred_lgd: float = 0.55, seed: int = 31):
    """Predictions constant; realized constant. MAE = |pred - true|."""
    rng = np.random.default_rng(seed)
    realized = np.full(n, true_lgd) + rng.normal(0, 1e-6, size=n)
    predicted = np.full(n, pred_lgd)
    return realized, predicted


def lgd_segmented(seed: int = 32) -> pd.DataFrame:
    """Two segments with different mean errors."""
    rng = np.random.default_rng(seed)
    n_per = 200
    seg_a = pd.DataFrame({
        "segment": ["A"] * n_per,
        "actual": rng.uniform(0.2, 0.4, size=n_per),
        "predicted": rng.uniform(0.2, 0.4, size=n_per),
    })
    seg_b = pd.DataFrame({
        "segment": ["B"] * n_per,
        "actual": rng.uniform(0.5, 0.8, size=n_per),
        "predicted": rng.uniform(0.5, 0.8, size=n_per) + 0.1,  # systematic over-predict
    })
    return pd.concat([seg_a, seg_b], ignore_index=True)


# --------------------------------- scenario ---------------------------------

def scenario_monotonic_severity() -> pd.DataFrame:
    return pd.DataFrame({
        "period": [f"2026Q{i}" for i in range(1, 5)] * 3,
        "scenario": ["base"] * 4 + ["adverse"] * 4 + ["severe"] * 4,
        "pd_multiplier": [
            1.00, 1.02, 1.03, 1.04,
            1.40, 1.55, 1.65, 1.72,
            2.10, 2.40, 2.60, 2.75,
        ],
    })


def scenario_with_violation() -> pd.DataFrame:
    """2026Q1 severe < adverse — must produce >= 1 violation."""
    df = scenario_monotonic_severity()
    mask = (df["scenario"] == "severe") & (df["period"] == "2026Q1")
    df.loc[mask, "pd_multiplier"] = 1.30  # below 1.40 adverse
    return df


# ------------------------------ regression ---------------------------------

def collinear_features(n: int = 200, seed: int = 41) -> Tuple[np.ndarray, pd.DataFrame]:
    """x3 ≈ 0.9 * x1; VIF for x1 and x3 must be high."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, size=n)
    x2 = rng.normal(0, 1, size=n)
    x3 = 0.9 * x1 + rng.normal(0, 0.05, size=n)
    y = 1.0 + 0.5 * x1 - 0.3 * x2 + rng.normal(0, 0.3, size=n)
    return y, pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})


def orthogonal_features(n: int = 500, seed: int = 42) -> Tuple[np.ndarray, pd.DataFrame]:
    """All features near-independent; VIF should be near 1."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, size=n)
    x2 = rng.normal(0, 1, size=n)
    x3 = rng.normal(0, 1, size=n)
    y = 0.4 * x1 - 0.2 * x2 + 0.1 * x3 + rng.normal(0, 0.5, size=n)
    return y, pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})


# --------------------------------- stationarity ---------------------------------

def white_noise_series(n: int = 300, seed: int = 51) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0, 1, size=n))


def random_walk_series(n: int = 300, seed: int = 52) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(np.cumsum(rng.normal(0, 1, size=n)))


# ------------------------------ traffic light --------------------------------

def traffic_light_calibrated(seed: int = 61) -> pd.DataFrame:
    """Predicted PD ≈ realized rate; binomial test stays in Green."""
    return pd.DataFrame({"n": [5000], "defaults": [100], "pred_pd": [0.02]})


def traffic_light_severe(seed: int = 62) -> pd.DataFrame:
    """Heavy under-prediction; binomial p << 0.0001 → Red."""
    return pd.DataFrame({"n": [1000], "defaults": [200], "pred_pd": [0.02]})
