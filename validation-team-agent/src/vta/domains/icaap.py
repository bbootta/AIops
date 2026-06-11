"""내부자본 적정성 (ICAAP, Pillar 2) 점검.

가용내부자본 vs 필요내부자본 (리스크 유형별 경제적 자본 합계, 분산효과 반영),
스트레스 후 버퍼, 리스크 구성 집중을 점검한다.

임계 SSoT: ``harness/icaap_thresholds.json``.
점검 함수는 결정론적·부작용 없는 순수 함수다. 경제적 자본 산정 자체는
리스크 측정 시스템에서 수행하며 본 모듈은 적정성 점검만 한다.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parents[3] / "harness" / "icaap_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def check_internal_capital(
    available_capital: float,
    required_by_risk: Mapping[str, float],
    *,
    diversification_benefit: float = 0.0,
    post_stress_available: float | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """내부자본 적정성 점검.

    Args:
        available_capital: 가용내부자본.
        required_by_risk: 리스크 유형별 필요내부자본 {"credit": x, ...}.
        diversification_benefit: 분산효과 차감액 (0 이상, 합계 대비 비중으로 점검).
        post_stress_available: 스트레스 시나리오 후 가용내부자본 (선택).

    반환 키: passed, ratio, post_stress_ratio, required_total, findings,
            risk_shares, missing_risk_types, diversification_share
    """
    th = thresholds or load_thresholds()
    if not math.isfinite(available_capital) or available_capital < 0:
        raise ValueError(f"available_capital must be >= 0, got {available_capital}")
    if not required_by_risk:
        raise ValueError("required_by_risk must not be empty")
    for k, v in required_by_risk.items():
        if not math.isfinite(float(v)) or float(v) < 0:
            raise ValueError(f"required_by_risk[{k}] must be >= 0, got {v}")
    if diversification_benefit < 0:
        raise ValueError("diversification_benefit must be >= 0")

    gross_total = sum(float(v) for v in required_by_risk.values())
    if gross_total <= 0:
        raise ValueError("sum of required_by_risk must be > 0")
    net_total = gross_total - float(diversification_benefit)
    if net_total <= 0:
        raise ValueError("diversification_benefit exceeds gross required capital")

    findings: list[str] = []
    ratio = available_capital / net_total

    # 필수 리스크 유형 커버리지
    missing = [r for r in th["required_risk_types"] if r not in required_by_risk]
    if missing:
        findings.append(f"필요내부자본에 누락된 리스크 유형: {missing}")

    # 분산효과 보수성
    div_share = float(diversification_benefit) / gross_total
    if div_share > float(th["diversification_benefit_max"]):
        findings.append(
            f"분산효과 차감 {div_share:.1%} > 한도 "
            f"{float(th['diversification_benefit_max']):.0%} (보수성 원칙)"
        )

    # 단일 리스크 집중
    risk_shares = {k: float(v) / gross_total for k, v in required_by_risk.items()}
    for k, share in risk_shares.items():
        if share > float(th["single_risk_share_warning"]):
            findings.append(f"단일 리스크({k}) 비중 {share:.1%} > 60% 경고")

    # 비율 판정
    if ratio < float(th["internal_capital_ratio_min"]):
        findings.append(
            f"내부자본비율 {ratio:.3f} < 최소 {th['internal_capital_ratio_min']}"
        )
        level = "below_min"
    elif ratio < float(th["internal_capital_ratio_warning"]):
        level = "warning"
    else:
        level = "ok"

    post_ratio = None
    post_level = None
    if post_stress_available is not None:
        if not math.isfinite(float(post_stress_available)) or post_stress_available < 0:
            raise ValueError("post_stress_available must be >= 0")
        post_ratio = float(post_stress_available) / net_total
        if post_ratio < float(th["post_stress_ratio_min"]):
            findings.append(
                f"스트레스 후 비율 {post_ratio:.3f} < 최소 {th['post_stress_ratio_min']}"
            )
            post_level = "below_min"
        elif post_ratio < float(th["post_stress_ratio_warning"]):
            post_level = "warning"
        else:
            post_level = "ok"

    hard_fail = level == "below_min" or post_level == "below_min"
    return {
        "passed": not hard_fail,
        "level": level,
        "ratio": round(ratio, 6),
        "post_stress_ratio": round(post_ratio, 6) if post_ratio is not None else None,
        "post_stress_level": post_level,
        "available": float(available_capital),
        "required_total": round(net_total, 6),
        "required_gross": round(gross_total, 6),
        "diversification_share": round(div_share, 6),
        "risk_shares": {k: round(v, 6) for k, v in risk_shares.items()},
        "missing_risk_types": missing,
        "findings": findings,
        "policy_version": th.get("policy_version"),
    }
