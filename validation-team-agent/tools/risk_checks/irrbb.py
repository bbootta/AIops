"""IRRBB (SRP31) 점검.

ΔEVE / ΔNII 표준 시나리오 산출 결과의 outlier test (15% Tier1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "harness" / "irrbb_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def check_scenarios_present(
    delta_eve_by_scenario: Mapping[str, float],
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """BCBS 표준 6 시나리오가 모두 산출되었는지 점검."""
    th = thresholds or load_thresholds()
    required = set(th["standard_scenarios"])
    provided = set(delta_eve_by_scenario.keys())
    missing = sorted(required - provided)
    extra = sorted(provided - required)
    return {
        "passed": len(missing) == 0,
        "missing": missing,
        "extra": extra,
        "n_provided": len(provided),
    }


def check_eve_outlier(
    delta_eve_by_scenario: Mapping[str, float],
    tier1_capital: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """max(|ΔEVE|) / Tier1 비율이 15% 초과 시 outlier bank.

    BCBS 표준: 손실 방향(절대값) 기준. 6 시나리오 중 최대 손실.
    """
    if tier1_capital <= 0:
        raise ValueError("tier1_capital must be > 0")
    th = thresholds or load_thresholds()
    limit = float(th["delta_eve_outlier_pct_tier1"])
    if not delta_eve_by_scenario:
        raise ValueError("delta_eve_by_scenario must not be empty")
    worst_scenario, worst_value = min(
        delta_eve_by_scenario.items(), key=lambda kv: kv[1]
    )
    worst_abs = abs(min(0.0, worst_value))  # 손실 (음수) 절대값
    ratio = worst_abs / tier1_capital
    return {
        "worst_scenario": worst_scenario,
        "worst_delta_eve": worst_value,
        "tier1_capital": tier1_capital,
        "ratio": ratio,
        "limit_pct_tier1": limit,
        "outlier": ratio > limit,
    }


def check_nii_warning(
    delta_nii_12m: float,
    baseline_nii_12m: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """ΔNII / baseline NII 비율 경고선 점검."""
    if baseline_nii_12m <= 0:
        raise ValueError("baseline_nii_12m must be > 0")
    th = thresholds or load_thresholds()
    warn = float(th["delta_nii_warning_pct_nii"])
    ratio = abs(delta_nii_12m) / baseline_nii_12m
    return {
        "delta_nii": delta_nii_12m,
        "baseline_nii": baseline_nii_12m,
        "ratio": ratio,
        "warning_threshold": warn,
        "warning": ratio > warn,
    }
