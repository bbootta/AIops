"""KS / AUROC / Gini 계산.

부도 여부 (binary target)와 모형 점수에 기반한다.
score의 부호 규약은 호출자가 명시한다 (높을수록 위험 또는 양호).
본 모듈은 score가 높을수록 위험할 것으로 가정한다. 반대 규약일 경우
호출자가 score에 음수를 곱해 전달한다.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
from sklearn.metrics import roc_auc_score


def validate_binary_target(y_true: Iterable) -> np.ndarray:
    """y_true가 0/1만 포함하는지 확인하고 numpy 배열로 반환한다."""
    arr = np.asarray(list(y_true))
    if arr.size == 0:
        raise ValueError("y_true is empty")
    unique = set(np.unique(arr).tolist())
    if not unique.issubset({0, 1}):
        raise ValueError(f"y_true must be binary 0/1, got {sorted(unique)}")
    if len(unique) < 2:
        raise ValueError("y_true must contain both 0 and 1")
    return arr.astype(int)


def calculate_ks(y_true: Iterable, score: Iterable) -> dict:
    """KS 통계량과 그 임계 점수를 반환한다.

    반환 dict 키: ks, threshold, n, n_bad, n_good
    """
    y = validate_binary_target(y_true)
    s = np.asarray(list(score), dtype=float)
    if s.shape != y.shape:
        raise ValueError("y_true and score length mismatch")
    if np.isnan(s).any():
        raise ValueError("score contains NaN; impute or drop before calling")

    order = np.argsort(s)
    s_sorted = s[order]
    y_sorted = y[order]

    n_bad = int(y.sum())
    n_good = int(len(y) - n_bad)
    if n_bad == 0 or n_good == 0:
        raise ValueError("both classes must have at least one sample")

    cum_bad = np.cumsum(y_sorted) / n_bad
    cum_good = np.cumsum(1 - y_sorted) / n_good
    diff = np.abs(cum_bad - cum_good)
    idx = int(np.argmax(diff))
    return {
        "ks": float(diff[idx]),
        "threshold": float(s_sorted[idx]),
        "n": int(len(y)),
        "n_bad": n_bad,
        "n_good": n_good,
    }


def calculate_auc_gini(y_true: Iterable, score: Iterable) -> dict:
    """AUROC와 Gini(=2*AUROC-1)를 반환한다."""
    y = validate_binary_target(y_true)
    s = np.asarray(list(score), dtype=float)
    if s.shape != y.shape:
        raise ValueError("y_true and score length mismatch")
    if np.isnan(s).any():
        raise ValueError("score contains NaN; impute or drop before calling")

    auc = float(roc_auc_score(y, s))
    return {"auc": auc, "gini": float(2 * auc - 1), "n": int(len(y))}
