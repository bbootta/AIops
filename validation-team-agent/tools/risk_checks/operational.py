"""Operational risk (OPE25 SMA) 검증 점검.

BI 3-yr 평균, BIC bucket 누진 합산, ILM floor 점검. ORC = BIC × ILM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "harness" / "operational_risk_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def business_indicator_average(annual_bi_values: Sequence[float]) -> dict:
    """BI 3-yr 단순 평균. 누락 연도는 호출자가 0 또는 None 제외 후 전달.

    BCBS: 직전 3개 연도. 본 함수는 평균만 산출; 회계 매핑은 호출자 책임.
    """
    if not annual_bi_values:
        raise ValueError("annual_bi_values must not be empty")
    if any(v < 0 for v in annual_bi_values):
        raise ValueError("annual BI values must be >= 0")
    if len(annual_bi_values) > 3:
        raise ValueError("Basel SMA uses up to 3 most recent years")
    avg = sum(annual_bi_values) / len(annual_bi_values)
    return {"years": len(annual_bi_values), "average_bi": avg}


def compute_bic(
    business_indicator_eur_bn: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """BIC 누진 합산.

    BCBS: bucket1 (0, 1bn) × 12%, bucket2 (1bn, 30bn) × 15%, bucket3 (30bn+) × 18%.
    """
    if business_indicator_eur_bn < 0:
        raise ValueError("business_indicator_eur_bn must be >= 0")
    th = thresholds or load_thresholds()
    bic = 0.0
    used = []
    remaining = business_indicator_eur_bn
    for bucket in th["buckets"]:
        lo = float(bucket["bi_lower_eur_bn"])
        hi = bucket["bi_upper_eur_bn"]
        coef = float(bucket["marginal_coef"])
        if remaining <= 0:
            break
        cap = float("inf") if hi is None else float(hi)
        slice_amount = min(remaining + lo, cap) - lo
        slice_amount = max(0.0, slice_amount)
        if slice_amount > 0:
            bic += slice_amount * coef
            used.append({"bucket": bucket["bucket"], "amount": slice_amount, "coef": coef})
            remaining -= slice_amount
        # 다음 bucket 으로 넘어가도 remaining 은 hi-lo 만큼 소진됐다.
    return {"bi": business_indicator_eur_bn, "bic_eur_bn": bic, "bucket_breakdown": used}


def compute_orc(bic: float, ilm: float, *, thresholds: Mapping | None = None) -> dict:
    """ORC = BIC × ILM. ILM 은 floor 강제."""
    th = thresholds or load_thresholds()
    floor = float(th["ilm_floor"])
    if ilm < floor:
        raise ValueError(f"ILM={ilm} below floor={floor}")
    return {"bic": bic, "ilm": ilm, "orc": bic * ilm}


def check_loss_history_years(years: int, *, thresholds: Mapping | None = None) -> dict:
    """ILM 산정 손실이력 최소 연수."""
    th = thresholds or load_thresholds()
    min_y = int(th["ilm_loss_history_min_years"])
    return {"years": years, "min_required": min_y, "passed": years >= min_y}
