"""변별력·캘리브레이션 진단 지표.

PD 모형 검증을 위한 추가 통계.  ``pd_model.gini`` / ``ks_statistic`` 과 함께
사용한다.

산출식
------
* **AUC-ROC**  - Mann-Whitney 통계로부터.  Gini = 2·AUC - 1.
* **AUPRC**    - precision–recall 곡선 아래 면적(사다리꼴 적분).
* **Brier**    - mean squared forecast error: ``mean((pd - y)^2)``.  0에 가까울수록
  좋고, 기준값(``y_bar(1-y_bar)``) 미만이면 단순 base-rate 예측보다 우수.
* **Kupiec POF** - 부도 이벤트 발생률에 대한 unconditional coverage 검정
  (Kupiec, 1995).  H0: 실현 부도건수 ~ Binomial(N, mean(pd)).
* **Christoffersen 독립성/조건부 coverage** - 시계열로 정렬된 부도 이벤트의
  Markov chain 검정 (Christoffersen, 1998).  H0: 연속 부도가 독립.
* **calibration_curve** - 십분위 buckets별 (mean PD, 실현 DR) - 캘리브레이션
  plot 데이터 산출.

참고: Basel III CRE36, BCBS WP 14 (모형 검증), 금감원 「모형리스크관리 모범규준」.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2


def auc_roc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Mann-Whitney 기반 AUC. 양·음 표본이 모두 필요."""
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=float)
    # average ranks 처리(공동 순위)
    sorted_s = s[order]
    i = 0
    n = len(s)
    while i < n:
        j = i
        while j + 1 < n and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        avg_rank = (i + j + 2) / 2.0  # 1-based ranks
        ranks[order[i:j + 1]] = avg_rank
        i = j + 1
    sum_pos = ranks[y == 1].sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def auprc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Precision-Recall 곡선 아래 면적 (사다리꼴)."""
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    if y.sum() == 0:
        return float("nan")
    order = np.argsort(-s)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / y_sorted.sum()
    # prepend (recall=0, precision=1) so the curve starts at the y-axis
    recall = np.concatenate([[0.0], recall])
    precision = np.concatenate([[1.0], precision])
    return float(np.trapezoid(precision, recall))


def brier_score(y_true: np.ndarray, pd_predicted: np.ndarray) -> float:
    """Mean squared forecast error of PD predictions."""
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(pd_predicted, dtype=float)
    return float(np.mean((p - y) ** 2))


def kupiec_pof(observed_defaults: int, n: int, expected_pd: float) -> dict[str, float]:
    """Unconditional coverage test (Kupiec POF).

    Likelihood-ratio statistic
        LR = -2 ln[ (p^x (1-p)^(n-x)) / (π^x (1-π)^(n-x)) ]
    where x = observed defaults, π = x/n, p = expected_pd.  ~ χ²(1).
    """
    p = max(min(float(expected_pd), 1 - 1e-12), 1e-12)
    x = int(observed_defaults)
    pi = x / n if n > 0 else 0.0
    if n == 0:
        return {"lr": 0.0, "p_value": 1.0, "expected_pd": p, "realised_pd": pi}
    if pi <= 0:
        ll_alt = 0.0
    elif pi >= 1:
        ll_alt = 0.0
    else:
        ll_alt = x * np.log(pi) + (n - x) * np.log(1 - pi)
    ll_null = x * np.log(p) + (n - x) * np.log(1 - p)
    lr = -2.0 * (ll_null - ll_alt)
    return {"lr": float(lr), "p_value": float(1 - chi2.cdf(lr, 1)),
            "expected_pd": p, "realised_pd": pi, "n": n,
            "observed_defaults": x}


def christoffersen_independence(events: np.ndarray) -> dict[str, float]:
    """Christoffersen 독립성 검정.

    events: 0/1 시퀀스(시간 정렬).  ~ χ²(1) under H0: P(d_t=1|d_{t-1}=0)
    = P(d_t=1|d_{t-1}=1).
    """
    e = np.asarray(events, dtype=int)
    if len(e) < 2:
        return {"lr": 0.0, "p_value": 1.0}
    n00 = int(((e[:-1] == 0) & (e[1:] == 0)).sum())
    n01 = int(((e[:-1] == 0) & (e[1:] == 1)).sum())
    n10 = int(((e[:-1] == 1) & (e[1:] == 0)).sum())
    n11 = int(((e[:-1] == 1) & (e[1:] == 1)).sum())
    pi01 = n01 / max(n00 + n01, 1)
    pi11 = n11 / max(n10 + n11, 1)
    pi = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    if pi <= 0 or pi >= 1:
        return {"lr": 0.0, "p_value": 1.0, "n01": n01, "n11": n11}

    def lln(p, k0, k1):
        if p <= 0 or p >= 1:
            return 0.0
        return k0 * np.log(1 - p) + k1 * np.log(p)

    ll_null = lln(pi, n00 + n10, n01 + n11)
    ll_alt = lln(pi01, n00, n01) + lln(pi11, n10, n11)
    lr = -2.0 * (ll_null - ll_alt)
    return {"lr": float(lr), "p_value": float(1 - chi2.cdf(lr, 1)),
            "pi01": float(pi01), "pi11": float(pi11),
            "n00": n00, "n01": n01, "n10": n10, "n11": n11}


def christoffersen_cc(events: np.ndarray, expected_pd: float) -> dict[str, float]:
    """조건부 coverage = unconditional + independence (LR ~ χ²(2))."""
    e = np.asarray(events, dtype=int)
    n = len(e)
    x = int(e.sum())
    uc = kupiec_pof(x, n, expected_pd)
    ind = christoffersen_independence(e)
    lr_cc = uc["lr"] + ind["lr"]
    return {"lr": float(lr_cc), "p_value": float(1 - chi2.cdf(lr_cc, 2)),
            "lr_uc": uc["lr"], "lr_ind": ind["lr"]}


def calibration_curve(
    pd_predicted: np.ndarray,
    y_true: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Reliability diagram 데이터.

    PD 십분위 buckets별 (mean_pd, realised_dr, n) 반환.  HL 검정과 동일한
    cut과 호환.
    """
    p = np.asarray(pd_predicted, dtype=float)
    y = np.asarray(y_true, dtype=int)
    order = np.argsort(p)
    p_sorted = p[order]
    y_sorted = y[order]
    edges = np.linspace(0, len(p_sorted), n_bins + 1, dtype=int)
    rows = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if hi <= lo:
            continue
        bucket_p = p_sorted[lo:hi]
        bucket_y = y_sorted[lo:hi]
        rows.append({
            "bucket": i + 1,
            "n": int(hi - lo),
            "mean_pd": float(bucket_p.mean()),
            "realised_dr": float(bucket_y.mean()),
            "lower_pd": float(bucket_p.min()),
            "upper_pd": float(bucket_p.max()),
        })
    return pd.DataFrame(rows)


def discrimination_summary(
    y_true: np.ndarray, pd_predicted: np.ndarray,
) -> dict[str, float]:
    """Headline 변별력/캘리브레이션 metric set."""
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(pd_predicted, dtype=float)
    auc = auc_roc(y, s)
    base = float(y.mean())
    base_brier = base * (1 - base)
    bs = brier_score(y, s)
    return {
        "auc_roc": float(auc),
        "gini": float(2 * auc - 1) if not np.isnan(auc) else float("nan"),
        "auprc": auprc(y, s),
        "brier": bs,
        "brier_base": base_brier,
        "brier_skill": float(1 - bs / base_brier) if base_brier > 0 else float("nan"),
        "base_rate": base,
    }
