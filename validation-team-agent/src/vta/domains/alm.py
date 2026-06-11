"""ALM (자산부채관리) 점검 — 만기 갭 / 자금조달 집중 / 예대율.

LCR·NSFR·외화LCR 은 ``vta.domains.liquidity``, IRRBB 는 ``vta.domains.irrbb``
가 담당하고, 본 모듈은 그 외 ALM 관리지표를 점검한다.

임계 SSoT: ``harness/alm_thresholds.json``.
점검 함수는 결정론적·부작용 없는 순수 함수다.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parents[3] / "harness" / "alm_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def check_maturity_gap(
    gaps_by_bucket: Mapping[str, float],
    total_assets: float,
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """만기 bucket 별 갭(자산-부채)의 누적 비율 점검.

    Args:
        gaps_by_bucket: {"1M": gap, "3M": gap, ...} (음수 = 부채 초과).
        total_assets: 총자산 (분모).

    반환 키: passed, level, cumulative, worst_bucket, worst_ratio
    """
    th = thresholds or load_thresholds()
    if not math.isfinite(total_assets) or total_assets <= 0:
        raise ValueError(f"total_assets must be > 0, got {total_assets}")
    buckets = [b for b in th["gap_buckets"] if b in gaps_by_bucket]
    if not buckets:
        raise ValueError(f"gaps_by_bucket has no known bucket: {list(gaps_by_bucket)}")
    for b in buckets:
        if not math.isfinite(float(gaps_by_bucket[b])):
            raise ValueError(f"gap[{b}] is not finite")

    limit = float(th["cumulative_gap_ratio_limit"])
    warning = float(th["cumulative_gap_ratio_warning"])
    cum = 0.0
    cumulative: dict[str, dict[str, float]] = {}
    worst_bucket = buckets[0]
    worst_ratio = math.inf
    for b in buckets:
        cum += float(gaps_by_bucket[b])
        ratio = cum / total_assets
        cumulative[b] = {"gap": float(gaps_by_bucket[b]),
                         "cumulative_gap": round(cum, 6),
                         "cumulative_ratio": round(ratio, 6)}
        if ratio < worst_ratio:
            worst_ratio = ratio
            worst_bucket = b

    if worst_ratio < limit:
        level = "below_min"
    elif worst_ratio < warning:
        level = "warning"
    else:
        level = "ok"
    return {
        "passed": level != "below_min",
        "level": level,
        "cumulative": cumulative,
        "worst_bucket": worst_bucket,
        "worst_ratio": round(worst_ratio, 6),
        "limit": limit,
        "warning": warning,
    }


def check_funding_concentration(
    funding_by_provider: Sequence[float],
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """자금조달 집중도: 단일 / 상위 10개 제공자 비중."""
    th = thresholds or load_thresholds()
    vals = sorted((float(v) for v in funding_by_provider if float(v) > 0),
                  reverse=True)
    if not vals:
        raise ValueError("funding_by_provider has no positive amounts")
    total = sum(vals)
    top1 = vals[0] / total
    top10 = sum(vals[:10]) / total
    findings = []
    if top1 > float(th["funding_top1_share_warning"]):
        findings.append(
            f"단일 조달처 비중 {top1:.1%} > {float(th['funding_top1_share_warning']):.0%}")
    if top10 > float(th["funding_top10_share_warning"]):
        findings.append(
            f"상위10 조달처 비중 {top10:.1%} > {float(th['funding_top10_share_warning']):.0%}")
    return {
        "passed": not findings,
        "level": "warning" if findings else "ok",
        "top1_share": round(top1, 6),
        "top10_share": round(top10, 6),
        "n_providers": len(vals),
        "findings": findings,
    }


def check_loan_to_deposit(
    loans: float,
    deposits: float,
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """원화 예대율 ≤ 100% (감독시행세칙)."""
    th = thresholds or load_thresholds()
    if not math.isfinite(deposits) or deposits <= 0:
        raise ValueError(f"deposits must be > 0, got {deposits}")
    if not math.isfinite(loans) or loans < 0:
        raise ValueError(f"loans must be >= 0, got {loans}")
    ratio = loans / deposits
    if ratio > float(th["loan_to_deposit_max"]):
        level = "below_min"  # 한도 위반
    elif ratio > float(th["loan_to_deposit_warning"]):
        level = "warning"
    else:
        level = "ok"
    return {
        "passed": level != "below_min",
        "level": level,
        "ratio": round(ratio, 6),
        "max": float(th["loan_to_deposit_max"]),
        "warning": float(th["loan_to_deposit_warning"]),
    }
