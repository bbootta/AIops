"""자본적정성 점검 (감독시행세칙 + Basel III).

CET1/Tier1/BIS 최소 + 보전버퍼 + D-SIB / 경기대응완충자본 점검.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "harness"
    / "capital_adequacy_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def check_ratios(
    cet1_ratio: float,
    tier1_ratio: float,
    total_ratio: float,
    *,
    conservation_buffer_applied: bool = True,
    countercyclical_buffer: float = 0.0,
    dsib_surcharge: float = 0.0,
    thresholds: Mapping | None = None,
) -> dict:
    """CET1/T1/BIS 최소 + 추가 buffer 충족 여부.

    감독시행세칙: 보전버퍼 + 경기대응완충자본 + D-SIB 부과는 CET1 에 누적 적용.
    실제 부과율은 감독원 고시값을 사용. 본 함수는 input 그대로 비교만 수행.
    """
    if any(r < 0 for r in (cet1_ratio, tier1_ratio, total_ratio)):
        raise ValueError("ratios must be >= 0")
    if any(b < 0 for b in (countercyclical_buffer, dsib_surcharge)):
        raise ValueError("buffer rates must be >= 0")

    th = thresholds or load_thresholds()
    mins = th["minimum_ratios"]
    bufs = th["buffers"]

    add_buffer = (
        (bufs["conservation_buffer"] if conservation_buffer_applied else 0.0)
        + countercyclical_buffer
        + dsib_surcharge
    )

    cet1_required = float(mins["cet1_min"]) + add_buffer
    tier1_required = float(mins["tier1_min"]) + add_buffer
    total_required = float(mins["total_capital_min"]) + add_buffer

    violations = []
    if cet1_ratio < cet1_required:
        violations.append({"metric": "cet1", "actual": cet1_ratio, "required": cet1_required})
    if tier1_ratio < tier1_required:
        violations.append({"metric": "tier1", "actual": tier1_ratio, "required": tier1_required})
    if total_ratio < total_required:
        violations.append({"metric": "total", "actual": total_ratio, "required": total_required})

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "cet1_required": cet1_required,
        "tier1_required": tier1_required,
        "total_required": total_required,
        "add_buffer": add_buffer,
    }


def check_leverage(
    leverage_ratio: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """레버리지비율 ≥ 3% (감독시행세칙 + Basel III)."""
    if leverage_ratio < 0:
        raise ValueError("leverage_ratio must be >= 0")
    th = thresholds or load_thresholds()
    minimum = float(th["leverage_ratio_min"])
    return {
        "ratio": leverage_ratio,
        "minimum": minimum,
        "passed": leverage_ratio >= minimum,
    }


def check_dividend_eligibility(
    cet1_ratio: float,
    *,
    countercyclical_buffer: float = 0.0,
    dsib_surcharge: float = 0.0,
    thresholds: Mapping | None = None,
) -> dict:
    """자본보전버퍼 미충족 시 배당·성과급 제한 (감독원 행정지도).

    CET1 < (4.5% + 2.5% 보전 + 추가 buffer) 이면 배당 제한 권고.
    """
    th = thresholds or load_thresholds()
    floor = (
        float(th["minimum_ratios"]["cet1_min"])
        + float(th["buffers"]["conservation_buffer"])
        + float(countercyclical_buffer)
        + float(dsib_surcharge)
    )
    return {
        "cet1": cet1_ratio,
        "floor_for_unrestricted_dividend": floor,
        "dividend_unrestricted": cet1_ratio >= floor,
    }
