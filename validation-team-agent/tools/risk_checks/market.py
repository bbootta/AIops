"""Market risk (FRTB) 검증 점검.

VaR 백테스트 traffic light (BCBS 표준), ES horizon 비교, NMRF 분류 점검 보조.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "harness" / "market_risk_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def var_backtest_traffic_light(
    exceptions: int,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """1일 99% VaR 250 영업일 exception 수로 traffic light 분류.

    BCBS 표준: green 0–4, yellow 5–9, red ≥10. Yellow/Red 시 multiplier 가산.
    """
    if exceptions < 0:
        raise ValueError("exceptions must be >= 0")
    th = (thresholds or load_thresholds())["var_backtest_traffic_light"]
    if exceptions <= th["green_max_exceptions"]:
        zone = "green"
    elif exceptions <= th["yellow_max_exceptions"]:
        zone = "yellow"
    else:
        zone = "red"
    return {
        "exceptions": exceptions,
        "horizon_days": th["horizon_days"],
        "p_value": th["p_value"],
        "zone": zone,
    }


def check_var_multiplier(multiplier: float, *, thresholds: Mapping | None = None) -> dict:
    """VaR multiplier 가 floor 이상인지 점검. BCBS 표준 floor = 3.0."""
    th = thresholds or load_thresholds()
    floor = float(th["var_multiplier_floor"])
    return {
        "multiplier": float(multiplier),
        "floor": floor,
        "passed": multiplier >= floor,
    }


def check_es_consistency(
    es_horizon_days_by_factor: Mapping[str, int],
    *,
    min_horizon_days: int = 10,
) -> dict:
    """Expected Shortfall horizon (liquidity-adjusted) 가 risk factor 별 최소 horizon 이상인지."""
    violations = []
    for factor, h in es_horizon_days_by_factor.items():
        if h < min_horizon_days:
            violations.append({"factor": factor, "horizon_days": h, "min": min_horizon_days})
    return {"passed": len(violations) == 0, "violations": violations}


def summarize_nmrf(non_modellable_count: int, total_count: int) -> dict:
    """NMRF (Non-Modellable Risk Factor) 비율 보고. 자동 의견 확정 안 함."""
    if total_count <= 0:
        raise ValueError("total_count must be > 0")
    ratio = non_modellable_count / total_count
    return {
        "non_modellable_count": non_modellable_count,
        "total_count": total_count,
        "ratio": ratio,
        "note": "ratio > 0.10 (10%) 시 모형 한계 보고서 명시 권고",
    }
