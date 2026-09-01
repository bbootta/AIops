"""Liquidity risk (LCR / NSFR) 점검."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parents[3] / "harness" / "liquidity_risk_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


MEASUREMENT_BASES = ("monthly_average", "spot")


def check_lcr(
    hqla: float,
    net_cash_outflow_30d: float,
    *,
    thresholds: Mapping | None = None,
    basis: str | None = None,
) -> dict:
    """LCR = HQLA / Net Cash Outflow ≥ 100% (BCBS 표준).

    ``basis`` 는 산정 시점 기준이다. 세칙 제17조제2항은 경영지도비율 LCR 을
    **매월 평잔**으로 산정하도록 하므로 ``"spot"`` 이면 비율이 충분해도
    ``basis_ok`` 가 False 다. 주지 않으면 판단하지 않고 ``None`` 으로 남긴다:
    시점값을 평잔으로 보고하는 것을 잡으려면 호출자가 기준을 밝혀야 한다.
    """
    if net_cash_outflow_30d <= 0:
        raise ValueError("net_cash_outflow_30d must be > 0")
    if hqla < 0:
        raise ValueError("hqla must be >= 0")
    if basis is not None and basis not in MEASUREMENT_BASES:
        raise ValueError(f"basis must be one of {MEASUREMENT_BASES}, got {basis!r}")
    th = thresholds or load_thresholds()
    required_basis = str(th["lcr_measurement_basis"])
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
        "basis": basis,
        "required_basis": required_basis,
        "basis_ok": None if basis is None else basis == required_basis,
    }


def check_foreign_currency_lcr(
    foreign_hqla: float,
    foreign_net_outflow_30d: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """외화 LCR (감독시행세칙). 최소 80% 행정지도 기준, 90% 미만 경고."""
    if foreign_net_outflow_30d <= 0:
        raise ValueError("foreign_net_outflow_30d must be > 0")
    if foreign_hqla < 0:
        raise ValueError("foreign_hqla must be >= 0")
    th = thresholds or load_thresholds()
    ratio = foreign_hqla / foreign_net_outflow_30d
    return {
        "ratio": ratio,
        "min_required": float(th["foreign_currency_lcr_min"]),
        "warning_threshold": float(th["foreign_currency_lcr_warning"]),
        "status": (
            "below_min"
            if ratio < th["foreign_currency_lcr_min"]
            else "warning"
            if ratio < th["foreign_currency_lcr_warning"]
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
