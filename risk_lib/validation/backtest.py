"""PD backtesting (정량적 검증).

  - Hosmer-Lemeshow goodness-of-fit on rating buckets
  - Per-grade binomial test (one-sided: realized > predicted)
  - 변별력(AUC/AUPRC/Brier) + Kupiec POF + Christoffersen 통합
  - 캘리브레이션 곡선 데이터(reliability diagram)
  - Consolidated report
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2, binom

from risk_lib.models.discrimination import (
    discrimination_summary, kupiec_pof, christoffersen_cc, calibration_curve,
)


def hosmer_lemeshow(
    pd_predicted: np.ndarray,
    defaults: np.ndarray,
    n_groups: int = 10,
) -> dict[str, float]:
    """Hosmer-Lemeshow chi-square test.

    H0: model is well-calibrated.  Small p-value rejects calibration.
    """
    pd_predicted = np.asarray(pd_predicted, dtype=float)
    defaults = np.asarray(defaults, dtype=int)
    order = np.argsort(pd_predicted)
    p = pd_predicted[order]
    d = defaults[order]

    edges = np.linspace(0, len(p), n_groups + 1, dtype=int)
    chi_sq = 0.0
    dof = 0
    for i in range(n_groups):
        lo, hi = edges[i], edges[i + 1]
        if hi <= lo:
            continue
        n = hi - lo
        observed = d[lo:hi].sum()
        expected = p[lo:hi].sum()
        var = (p[lo:hi] * (1 - p[lo:hi])).sum()
        if var <= 0:
            continue
        chi_sq += (observed - expected) ** 2 / var
        dof += 1
    dof = max(dof - 2, 1)
    p_value = 1 - chi2.cdf(chi_sq, dof)
    return {"chi_square": float(chi_sq), "dof": float(dof), "p_value": float(p_value)}


def binomial_test_per_grade(
    grade: np.ndarray,
    pd_predicted: np.ndarray,
    defaults: np.ndarray,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """One-sided binomial (green/yellow/red zone).

    For each grade, test H0: realised default rate <= calibrated PD.
    Reject when P(X >= observed | PD=calibrated) < alpha.
    """
    grade = np.asarray(grade)
    pd_predicted = np.asarray(pd_predicted, dtype=float)
    defaults = np.asarray(defaults, dtype=int)

    rows = []
    for g in pd.unique(grade):
        mask = grade == g
        n = int(mask.sum())
        observed = int(defaults[mask].sum())
        avg_pd = float(pd_predicted[mask].mean()) if n else 0.0
        realised = observed / n if n else 0.0
        p_value = 1.0 - binom.cdf(observed - 1, n, max(avg_pd, 1e-9)) if n else 1.0
        if p_value < alpha / 2:
            zone = "RED"
        elif p_value < alpha:
            zone = "YELLOW"
        else:
            zone = "GREEN"
        rows.append({
            "grade": g,
            "n": n,
            "calibrated_pd": avg_pd,
            "realised_dr": realised,
            "observed_defaults": observed,
            "p_value": p_value,
            "zone": zone,
        })
    return pd.DataFrame(rows).sort_values("calibrated_pd").reset_index(drop=True)


def pd_backtest_report(
    obligors: pd.DataFrame,
    *,
    grade_col: str = "grade",
    pd_col: str = "pd",
    default_col: str = "default_12m",
) -> dict[str, object]:
    """Consolidated PD validation.

    포함 지표:
      * Hosmer-Lemeshow χ² (캘리브레이션)
      * 등급별 신호등 (binomial, 한쪽)
      * 변별력 summary (AUC, Gini, AUPRC, Brier, base rate)
      * Kupiec POF (unconditional coverage)
      * Christoffersen 조건부 coverage (LR_cc)
      * 캘리브레이션 곡선(reliability diagram, 십분위)
    """
    y = obligors[default_col].values
    p = obligors[pd_col].values
    hl = hosmer_lemeshow(p, y)
    per_grade = binomial_test_per_grade(
        obligors[grade_col].values, p, y,
    )
    disc = discrimination_summary(y, p)
    n = int(len(y))
    observed = int(y.sum())
    avg_pd = float(p.mean()) if n else 0.0
    pof = kupiec_pof(observed, n, avg_pd)
    cc = christoffersen_cc(y, avg_pd)
    cal = calibration_curve(p, y, n_bins=10)
    return {
        "hosmer_lemeshow": hl,
        "per_grade": per_grade,
        "discrimination": disc,
        "kupiec_pof": pof,
        "christoffersen_cc": cc,
        "calibration_curve": cal,
        "overall_dr": float(y.mean()),
        "overall_pd": avg_pd,
    }
