"""PD (Probability of Default) modeling.

Logistic regression over borrower features.  Outputs include:
  - fit/predict
  - rank-order metrics (Gini, KS)
  - calibration to master scale
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


@dataclass
class PDModel:
    features: list[str]
    scaler: StandardScaler
    clf: LogisticRegression
    central_tendency: float | None = None  # long-run avg default rate

    def predict_pd(self, X: pd.DataFrame) -> np.ndarray:
        Xs = self.scaler.transform(X[self.features].values)
        p = self.clf.predict_proba(Xs)[:, 1]
        return np.clip(p, 1e-6, 1 - 1e-6)

    def recalibrate(self, predictions: np.ndarray) -> np.ndarray:
        """Shift PDs so that mean = central_tendency (log-odds shift)."""
        if self.central_tendency is None:
            return predictions
        cur = predictions.mean()
        if cur <= 0 or cur >= 1:
            return predictions
        target = self.central_tendency
        # Solve for delta in logit space such that mean of sigmoid(logit + d) = target
        # Use bisection (monotonic in delta).
        logits = np.log(predictions / (1 - predictions))

        def mean_at(d: float) -> float:
            return float((1.0 / (1.0 + np.exp(-(logits + d)))).mean())

        lo, hi = -10.0, 10.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if mean_at(mid) < target:
                lo = mid
            else:
                hi = mid
        d = (lo + hi) / 2
        return 1 / (1 + np.exp(-(logits + d)))


def fit_pd_model(
    train: pd.DataFrame,
    features: list[str],
    target: str = "default_12m",
    central_tendency: float | None = None,
    random_state: int = 42,
) -> PDModel:
    """Fit logistic PD model.

    train: dataframe with `features` columns and `target` (0/1).
    central_tendency: anchor for portfolio long-run default rate (e.g. through-the-cycle).
    """
    X = train[features].values
    y = train[target].astype(int).values

    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)

    clf = LogisticRegression(
        max_iter=1000,
        random_state=random_state,
        C=1.0,
        solver="lbfgs",
    ).fit(Xs, y)

    return PDModel(
        features=list(features),
        scaler=scaler,
        clf=clf,
        central_tendency=central_tendency,
    )


def gini(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Gini = 2*AUC - 1, computed without sklearn for portability of result."""
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.0
    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    sum_ranks_pos = ranks[y_true == 1].sum()
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return 2 * auc - 1


def ks_statistic(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Kolmogorov-Smirnov for score discrimination."""
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    order = np.argsort(-scores)
    y_sorted = y_true[order]
    cum_pos = np.cumsum(y_sorted) / max(y_sorted.sum(), 1)
    cum_neg = np.cumsum(1 - y_sorted) / max((1 - y_sorted).sum(), 1)
    return float(np.max(np.abs(cum_pos - cum_neg)))


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index (binned by quantiles of expected)."""
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    qs = np.quantile(expected, np.linspace(0, 1, bins + 1))
    qs[0] = -np.inf
    qs[-1] = np.inf
    e_counts, _ = np.histogram(expected, bins=qs)
    a_counts, _ = np.histogram(actual, bins=qs)
    e_pct = np.clip(e_counts / max(len(expected), 1), 1e-6, None)
    a_pct = np.clip(a_counts / max(len(actual), 1), 1e-6, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))
