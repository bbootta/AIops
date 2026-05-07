"""IFRS 9 ECL 시나리오 가중치 정합성 점검.

- sum(weights) == 1.0 (허용 오차 적용)
- 음수 / NaN 가중치 금지
- 시나리오 종류 일관성 (예: base/adverse/severe만 허용)
- 시점별(period) 가중치 변동 추적

본 모듈은 가중치를 자동으로 정규화하지 않는다. 위반은 보고만 한다.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping

import pandas as pd


_DEFAULT_SCENARIOS = ("base", "adverse", "severe")


def check_weight_sum(
    weights: Mapping[str, float],
    *,
    expected_sum: float = 1.0,
    tolerance: float = 1e-6,
    allowed_scenarios: Iterable[str] | None = None,
) -> dict:
    """시나리오 가중치 1세트(시점 1개) 점검.

    반환 dict 키: passed, sum, violations(list of dict)
    """
    if not isinstance(weights, Mapping) or not weights:
        raise ValueError("weights must be a non-empty mapping")
    allowed = set(allowed_scenarios) if allowed_scenarios else set(_DEFAULT_SCENARIOS)

    violations: list[dict] = []
    total = 0.0
    for k, v in weights.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            violations.append({"type": "type", "scenario": k, "value": v})
            continue
        if math.isnan(v):
            violations.append({"type": "nan", "scenario": k, "value": v})
            continue
        if v < 0:
            violations.append({"type": "negative", "scenario": k, "value": float(v)})
        if k not in allowed:
            violations.append({"type": "unknown_scenario", "scenario": k, "allowed": sorted(allowed)})
        total += float(v)

    if not math.isclose(total, expected_sum, abs_tol=tolerance):
        violations.append(
            {"type": "sum", "actual": total, "expected": expected_sum, "tolerance": tolerance}
        )

    missing = sorted(allowed - set(weights.keys()))
    if missing:
        violations.append({"type": "missing_scenarios", "missing": missing})

    return {"passed": len(violations) == 0, "sum": total, "violations": violations}


def check_weight_panel(
    df: pd.DataFrame,
    *,
    period_col: str,
    scenario_col: str,
    weight_col: str,
    expected_sum: float = 1.0,
    tolerance: float = 1e-6,
    allowed_scenarios: Iterable[str] | None = None,
) -> pd.DataFrame:
    """시점 패널(period × scenario × weight) 데이터에 대해 시점별로 점검한다.

    반환 DataFrame 컬럼:
        period, sum, passed, n_violations, violation_types(set as comma string)
    """
    for c in (period_col, scenario_col, weight_col):
        if c not in df.columns:
            raise KeyError(f"column missing: {c}")

    rows: list[dict] = []
    for period, sub in df.groupby(period_col, sort=True):
        weights = dict(zip(sub[scenario_col].astype(str), sub[weight_col].astype(float)))
        out = check_weight_sum(
            weights,
            expected_sum=expected_sum,
            tolerance=tolerance,
            allowed_scenarios=allowed_scenarios,
        )
        types = sorted({v["type"] for v in out["violations"]})
        rows.append(
            {
                "period": period,
                "sum": out["sum"],
                "passed": out["passed"],
                "n_violations": len(out["violations"]),
                "violation_types": ",".join(types),
            }
        )
    return pd.DataFrame(rows)
