"""PSI (Population Stability Index) 계산.

bin 정의는 호출자가 결정하거나, 분위수 기반 자동 분할을 사용한다.
0 division을 방지하기 위해 모든 bin에 epsilon을 더한 후 비율을 계산한다.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

_EPS = 1e-6


def _percentile_bins(expected: np.ndarray, bins: int) -> np.ndarray:
    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(expected, quantiles))
    if edges.size < 2:
        edges = np.array([expected.min() - 1.0, expected.max() + 1.0])
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def calculate_psi(
    expected: Iterable, actual: Iterable, bins: int = 10
) -> dict:
    """expected 분포와 actual 분포 간 PSI를 반환한다.

    반환 dict 키: psi, bin_edges, expected_pct, actual_pct, n_expected, n_actual
    """
    e = np.asarray(list(expected), dtype=float)
    a = np.asarray(list(actual), dtype=float)
    if e.size == 0 or a.size == 0:
        raise ValueError("expected/actual must not be empty")
    if np.isnan(e).any() or np.isnan(a).any():
        raise ValueError("NaN not allowed in expected/actual")
    if bins < 2:
        raise ValueError("bins must be >= 2")

    edges = _percentile_bins(e, bins)
    e_counts, _ = np.histogram(e, bins=edges)
    a_counts, _ = np.histogram(a, bins=edges)

    e_pct = e_counts / max(e_counts.sum(), 1)
    a_pct = a_counts / max(a_counts.sum(), 1)

    e_pct_safe = np.clip(e_pct, _EPS, None)
    a_pct_safe = np.clip(a_pct, _EPS, None)

    psi_terms = (a_pct_safe - e_pct_safe) * np.log(a_pct_safe / e_pct_safe)
    psi = float(np.sum(psi_terms))

    return {
        "psi": psi,
        "bin_edges": edges.tolist(),
        "expected_pct": e_pct.tolist(),
        "actual_pct": a_pct.tolist(),
        "n_expected": int(e.size),
        "n_actual": int(a.size),
    }


def calculate_psi_by_bucket(
    expected_bucket: Iterable, actual_bucket: Iterable
) -> dict:
    """이미 bucket(등급/구간) 라벨링된 두 분포 간 PSI.

    expected_bucket과 actual_bucket의 카테고리 합집합을 기준으로 비교한다.
    """
    e = pd.Series(list(expected_bucket))
    a = pd.Series(list(actual_bucket))
    if e.empty or a.empty:
        raise ValueError("expected_bucket/actual_bucket must not be empty")

    cats = sorted(set(e.unique().tolist()) | set(a.unique().tolist()))
    e_pct = (e.value_counts(normalize=True).reindex(cats).fillna(0.0)).values
    a_pct = (a.value_counts(normalize=True).reindex(cats).fillna(0.0)).values

    e_safe = np.clip(e_pct, _EPS, None)
    a_safe = np.clip(a_pct, _EPS, None)
    psi = float(np.sum((a_safe - e_safe) * np.log(a_safe / e_safe)))

    return {
        "psi": psi,
        "categories": cats,
        "expected_pct": e_pct.tolist(),
        "actual_pct": a_pct.tolist(),
        "n_expected": int(len(e)),
        "n_actual": int(len(a)),
    }
