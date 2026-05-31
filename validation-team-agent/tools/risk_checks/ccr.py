"""Counterparty Credit Risk (SA-CCR, CRE52) 점검.

EAD = α × (RC + PFE). α default 1.4. Asset class 별 supervisory factor
조회 + PFE multiplier 범위 점검.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "harness" / "ccr_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def lookup_supervisory_factor(asset_class: str, *, thresholds: Mapping | None = None) -> float:
    """SA-CCR supervisory factor 조회."""
    th = thresholds or load_thresholds()
    factors = th["supervisory_factors"]
    if asset_class not in factors:
        raise KeyError(
            f"unknown asset_class {asset_class!r}; expected one of {sorted(factors)}"
        )
    return float(factors[asset_class])


def check_pfe_multiplier(
    multiplier: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """PFE multiplier 가 [0.05, 1.0] 범위 안인지 점검."""
    th = thresholds or load_thresholds()
    lo = float(th["pfe_multiplier_min"])
    hi = float(th["pfe_multiplier_max"])
    return {
        "multiplier": multiplier,
        "lower": lo,
        "upper": hi,
        "passed": lo <= multiplier <= hi,
    }


def compute_ead(
    replacement_cost: float,
    pfe: float,
    *,
    alpha: float | None = None,
    thresholds: Mapping | None = None,
) -> dict:
    """EAD = α × (RC + PFE). α default 는 임계 SSoT 값(1.4)."""
    if replacement_cost < 0:
        raise ValueError("replacement_cost must be >= 0")
    if pfe < 0:
        raise ValueError("pfe must be >= 0")
    th = thresholds or load_thresholds()
    a = float(th["alpha"] if alpha is None else alpha)
    if a < 1.0:
        raise ValueError(f"alpha={a} below floor 1.0 (IMM 미승인 시 1.4 default)")
    ead = a * (replacement_cost + pfe)
    return {"alpha": a, "rc": replacement_cost, "pfe": pfe, "ead": ead}
