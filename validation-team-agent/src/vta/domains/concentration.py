"""신용집중리스크 점검 (Basel LEX + 은행법 제35조).

거액익스포저 (Tier1 10% 보고 / 25% 한도), 동일차주·동일인 신용공여한도,
거액신용공여 총량 (자기자본 5배), HHI 집중도를 점검한다.

임계 SSoT: ``harness/concentration_thresholds.json``.
점검 함수는 결정론적·부작용 없는 순수 함수다. 산정(익스포저 측정) 자체는
여신 시스템에서 수행하며 본 모듈은 한도·집중도 점검만 한다.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parents[3] / "harness" / "concentration_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def herfindahl(exposures: Sequence[float]) -> float:
    """HHI = Σ (점유율)². 0 < HHI ≤ 1. 빈 입력은 0."""
    vals = [float(e) for e in exposures if e and float(e) > 0]
    total = sum(vals)
    if total <= 0:
        return 0.0
    return sum((v / total) ** 2 for v in vals)


def _group_totals(
    exposures: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    """동일차주(group_id) 단위 합산. group_id 없으면 counterparty_id."""
    out: dict[str, float] = {}
    for e in exposures:
        key = str(e.get("group_id") or e.get("counterparty_id"))
        out[key] = out.get(key, 0.0) + float(e["exposure"])
    return out


def check_concentration(
    exposures: Sequence[Mapping[str, Any]],
    tier1: float,
    *,
    equity: float | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """집중리스크 한도·집중도 점검.

    Args:
        exposures: [{"counterparty_id": str, "exposure": float,
                     "group_id": str | None}, ...]
        tier1: 기본자본 (Basel LEX 분모).
        equity: 자기자본 (은행법 분모). 미제공 시 tier1 사용 (보수적).

    반환 키: passed, hhi, hhi_band, large_exposures, limit_breaches,
            aggregate_large, aggregate_limit, n_groups
    """
    th = thresholds or load_thresholds()
    if not math.isfinite(tier1) or tier1 <= 0:
        raise ValueError(f"tier1 must be a positive finite number, got {tier1}")
    eq = float(equity) if equity is not None else float(tier1)
    if not math.isfinite(eq) or eq <= 0:
        raise ValueError(f"equity must be a positive finite number, got {equity}")

    groups = _group_totals(exposures)
    reporting = float(th["large_exposure_reporting_pct_tier1"])
    single_limit = float(th["single_counterparty_limit_pct_tier1"])
    dom = th["domestic"]
    group_limit_eq = float(dom["same_borrower_group_limit_pct_equity"])
    agg_multiple = float(dom["large_exposure_aggregate_multiple_equity"])

    large = []
    breaches = []
    for gid, total in sorted(groups.items(), key=lambda kv: -kv[1]):
        pct_tier1 = total / tier1
        pct_eq = total / eq
        if pct_tier1 > reporting:
            large.append({"group": gid, "exposure": total,
                          "pct_tier1": round(pct_tier1, 6)})
        if pct_tier1 > single_limit:
            breaches.append({"group": gid, "rule": "LEX 25% Tier1",
                             "pct_tier1": round(pct_tier1, 6)})
        if pct_eq > group_limit_eq:
            breaches.append({"group": gid, "rule": "동일차주 25% 자기자본",
                             "pct_equity": round(pct_eq, 6)})

    aggregate_large = sum(item["exposure"] for item in large)
    aggregate_limit = agg_multiple * eq
    if aggregate_large > aggregate_limit:
        breaches.append({"group": "(합계)", "rule": "거액신용공여 합계 ≤ 자기자본 5배",
                         "aggregate": aggregate_large, "limit": aggregate_limit})

    hhi = herfindahl([float(e["exposure"]) for e in exposures])
    bands = th["hhi_bands"]
    if hhi <= float(bands["low_max"]):
        band = "low"
    elif hhi <= float(bands["moderate_max"]):
        band = "moderate"
    else:
        band = "high"

    return {
        "passed": not breaches,
        "hhi": round(hhi, 6),
        "hhi_band": band,
        "large_exposures": large,
        "limit_breaches": breaches,
        "aggregate_large": aggregate_large,
        "aggregate_limit": aggregate_limit,
        "n_groups": len(groups),
        "policy_version": th.get("policy_version"),
    }
