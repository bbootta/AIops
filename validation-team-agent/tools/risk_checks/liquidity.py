"""Liquidity risk (LCR / NSFR) 점검."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "harness" / "liquidity_risk_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def check_lcr(
    hqla: float,
    net_cash_outflow_30d: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """LCR = HQLA / Net Cash Outflow ≥ 100% (BCBS 표준)."""
    if net_cash_outflow_30d <= 0:
        raise ValueError("net_cash_outflow_30d must be > 0")
    if hqla < 0:
        raise ValueError("hqla must be >= 0")
    th = thresholds or load_thresholds()
    ratio = hqla / net_cash_outflow_30d
    return {
        "ratio": ratio,
        "min_required": float(th["lcr_min"]),
        "warning_threshold": float(th["lcr_warning"]),
        "status": (
            "below_min"
            if ratio < th["lcr_min"]
            else "warning"
            if ratio < th["lcr_warning"]
            else "ok"
        ),
    }


def check_nsfr(
    available_stable_funding: float,
    required_stable_funding: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """NSFR = ASF / RSF ≥ 100%."""
    if required_stable_funding <= 0:
        raise ValueError("required_stable_funding must be > 0")
    if available_stable_funding < 0:
        raise ValueError("available_stable_funding must be >= 0")
    th = thresholds or load_thresholds()
    ratio = available_stable_funding / required_stable_funding
    return {
        "ratio": ratio,
        "min_required": float(th["nsfr_min"]),
        "warning_threshold": float(th["nsfr_warning"]),
        "status": (
            "below_min"
            if ratio < th["nsfr_min"]
            else "warning"
            if ratio < th["nsfr_warning"]
            else "ok"
        ),
    }
