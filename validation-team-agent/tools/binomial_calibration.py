"""등급별 PD 캘리브레이션 검정.

각 등급에서 추정 PD 대비 실측 부도 건수가 통계적으로 유의하게 다른지
이항분포 양측검정으로 평가하고, Wilson score 신뢰구간을 함께 제공한다.

- 신뢰구간: Wilson score interval (불균형 표본에 더 안정적)
- 검정: scipy.stats.binomtest 양측, alternative='two-sided'
- 다중 등급 동시 검정 시 Holm 보정 옵션 제공

본 모듈은 임계값을 임의로 완화하지 않는다. 호출자가 alpha를 명시한다.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Mapping

import pandas as pd
from scipy.stats import binomtest, norm


def wilson_interval(default_count: int, exposure_count: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score 신뢰구간 (lower, upper) 반환."""
    if exposure_count <= 0:
        raise ValueError("exposure_count must be > 0")
    if default_count < 0 or default_count > exposure_count:
        raise ValueError("default_count must be within [0, exposure_count]")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")

    n = float(exposure_count)
    if default_count == 0:
        return (0.0, _wilson_upper_only(0, n, alpha))
    if default_count == exposure_count:
        return (1.0 - _wilson_upper_only(0, n, alpha), 1.0)
    p_hat = default_count / n
    z = float(norm.ppf(1.0 - alpha / 2.0))
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _wilson_upper_only(default_count: int, n: float, alpha: float) -> float:
    """k=0 또는 k=n 경계용 단측 Wilson 한계."""
    p_hat = default_count / n
    z = float(norm.ppf(1.0 - alpha / 2.0))
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n))) / denom
    return min(1.0, center + half)


def _holm_adjust(pvalues: List[float]) -> List[float]:
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i])
    adj = [0.0] * n
    running_max = 0.0
    for rank, idx in enumerate(order):
        val = min(1.0, pvalues[idx] * (n - rank))
        running_max = max(running_max, val)
        adj[idx] = running_max
    return adj


def calibration_test_per_grade(
    grades: Iterable[Mapping],
    alpha: float = 0.05,
    multitest: str = "holm",
) -> pd.DataFrame:
    """등급별 PD 캘리브레이션 결과 표를 반환한다.

    grades 의 각 항목은 다음 키를 가진다:
        grade, pd_estimated, default_count, exposure_count

    반환 컬럼:
        grade, pd_estimated, observed_rate, default_count, exposure_count,
        ci_lower, ci_upper, p_value, p_value_adj, reject (bool)

    multitest:
        - "holm": Holm-Bonferroni 보정 적용
        - "none": 보정 없음
    """
    if multitest not in {"holm", "none"}:
        raise ValueError("multitest must be 'holm' or 'none'")

    rows: List[dict] = []
    for g in grades:
        for key in ("grade", "pd_estimated", "default_count", "exposure_count"):
            if key not in g:
                raise KeyError(f"grade entry missing key: {key}")
        n = int(g["exposure_count"])
        k = int(g["default_count"])
        pd_est = float(g["pd_estimated"])
        if n <= 0:
            raise ValueError(f"grade {g['grade']}: exposure_count must be > 0")
        if not 0.0 <= pd_est <= 1.0:
            raise ValueError(f"grade {g['grade']}: pd_estimated must be in [0, 1]")
        if k < 0 or k > n:
            raise ValueError(f"grade {g['grade']}: default_count out of range")

        ci_lo, ci_hi = wilson_interval(k, n, alpha=alpha)
        p_val = float(binomtest(k=k, n=n, p=pd_est, alternative="two-sided").pvalue)
        rows.append(
            {
                "grade": g["grade"],
                "pd_estimated": pd_est,
                "observed_rate": k / n,
                "default_count": k,
                "exposure_count": n,
                "ci_lower": ci_lo,
                "ci_upper": ci_hi,
                "p_value": p_val,
            }
        )

    pvals = [r["p_value"] for r in rows]
    if multitest == "holm":
        adj = _holm_adjust(pvals)
    else:
        adj = pvals[:]
    for r, a in zip(rows, adj):
        r["p_value_adj"] = a
        r["reject"] = bool(a < alpha)
    return pd.DataFrame(rows)
