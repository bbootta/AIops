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


MEASUREMENT_BASES = ("monthly_average", "spot")


def check_won_loan_to_deposit(
    *,
    won_loans: float,
    won_deposits: float,
    policy_loans_excluded: float = 0.0,
    covered_bond_5_10y: float = 0.0,
    covered_bond_10y_plus: float = 0.0,
    benchmark_cd: float = 0.0,
    other_cd: float = 0.0,
    loan_breakdown: Mapping[str, float] | None = None,
    prior_quarter_end_won_loans: float | None = None,
    basis: str | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """규정 제26조제1항제3호 · 세칙 별표 3의7 의 원화예대율.

        예대율 = (원화대출금 − 정책자금대출 등 ± 가감) / (원화예수금 + 커버드본드 + CD)

    - 모든 금액은 월평잔이어야 한다 (별표 3의7 · 세칙 제17조제2항). ``basis``
      를 주면 대조하고, 주지 않으면 ``basis_ok`` 는 None 이다.
    - 커버드본드: 만기 5~10년분은 원화예수금의 1/100 까지, 그 인정분과 10년
      이상분의 합은 2/100 까지 산입한다.
    - CD: 지표물(80~100일)은 50% 가산, 그 외는 50% 차감한 뒤 원화예수금의
      1/100 까지 산입한다. 규정 문언은 한도와 가감의 순서를 정하지 않는다.
      한도를 마지막에 적용하면 어느 순서든 산입액이 한도를 넘지 않으므로
      그렇게 둔다. 바젤에는 대응 기준이 없어 보충할 원문이 없다.
    - 가감: ``loan_breakdown`` (corporate_metro · corporate_nonmetro ·
      sole_proprietor_nonmetro · household) 이 있을 때만 적용한다. 없으면
      가감 없이 산출하고 그 사실을 notes 에 남긴다. 2020~2021년 신규 개인사업자
      대출의 경과 가감은 다루지 않는다.
    - 직전분기말월 원화대출금이 4조원 미만이면 적용 대상이 아니다 (규정
      제26조제1항 단서). 값을 주지 않으면 적용 대상으로 본다.
    """
    th = (thresholds or load_thresholds())["won_ltd"]
    amounts = {
        "won_loans": won_loans, "won_deposits": won_deposits,
        "policy_loans_excluded": policy_loans_excluded,
        "covered_bond_5_10y": covered_bond_5_10y,
        "covered_bond_10y_plus": covered_bond_10y_plus,
        "benchmark_cd": benchmark_cd, "other_cd": other_cd,
    }
    for k, v in amounts.items():
        if not math.isfinite(float(v)) or float(v) < 0:
            raise ValueError(f"{k} must be finite and >= 0, got {v}")
    if won_deposits <= 0:
        raise ValueError(f"won_deposits must be > 0, got {won_deposits}")
    if basis is not None and basis not in MEASUREMENT_BASES:
        raise ValueError(f"basis must be one of {MEASUREMENT_BASES}, got {basis!r}")

    notes: list[str] = []
    exempt_below = float(th["exemption_prior_quarter_won_loans_below"])
    applicable = True
    if prior_quarter_end_won_loans is not None:
        applicable = float(prior_quarter_end_won_loans) >= exempt_below
    else:
        notes.append("직전분기말월 원화대출금 미제공: 적용 대상으로 간주")

    adjustment = 0.0
    if loan_breakdown is None:
        notes.append("가감 미적용: 대출 내역(loan_breakdown) 미제공")
    else:
        rates = th["loan_adjustments"]
        unknown = sorted(set(loan_breakdown) - set(rates))
        if unknown:
            raise ValueError(f"loan_breakdown has unknown keys: {unknown}")
        adjustment = sum(float(loan_breakdown[k]) * float(rates[k]) for k in loan_breakdown)
    numerator = won_loans - policy_loans_excluded + adjustment

    cb_5_10_cap = won_deposits * float(th["covered_bond_5_10y_cap_share"])
    cb_5_10_counted = min(covered_bond_5_10y, cb_5_10_cap)
    cb_total_cap = won_deposits * float(th["covered_bond_total_cap_share"])
    covered_bond_counted = min(cb_5_10_counted + covered_bond_10y_plus, cb_total_cap)
    cd_adjusted = (benchmark_cd * (1.0 + float(th["benchmark_cd_addon"]))
                   + other_cd * (1.0 - float(th["other_cd_haircut"])))
    cd_counted = min(cd_adjusted, won_deposits * float(th["cd_cap_share_of_deposits"]))
    denominator = won_deposits + covered_bond_counted + cd_counted

    ratio = numerator / denominator
    if not applicable:
        level = "not_applicable"
    elif ratio > float(th["max"]):
        level = "below_min"  # 한도 위반
    elif ratio > float(th["warning"]):
        level = "warning"
    else:
        level = "ok"
    return {
        "passed": level != "below_min",
        "level": level,
        "applicable": applicable,
        "ratio": round(ratio, 6),
        "numerator": round(numerator, 2),
        "denominator": round(denominator, 2),
        "components": {
            "loan_adjustment": round(adjustment, 2),
            "covered_bond_counted": round(covered_bond_counted, 2),
            "cd_counted": round(cd_counted, 2),
        },
        "max": float(th["max"]),
        "warning": float(th["warning"]),
        "basis": basis,
        "basis_ok": None if basis is None else basis == "monthly_average",
        "notes": notes,
    }


def check_loan_to_deposit(
    loans: float,
    deposits: float,
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """잔액 기준 예대율 관리지표. 규정의 원화예대율은 check_won_loan_to_deposit."""
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
