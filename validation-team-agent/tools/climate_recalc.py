"""기후리스크 합성 사례 독립 재계산 (기후리스크 관리 업무요건정의서 CLR-18-02).

요건정의서(설계 버전 1.0.0 · 2026.09.06)는 부록의 합성 fixture 와 기대값을
손실 → 재무 → PD → EAD → EL → ECL → RWA → 자본 순서로 단계별 대사하라고
요구한다(CLR-18-02). 본 모듈은 문서에 실린 참조계산기와 **코드를 공유하지
않고** 유리수(Fraction) 산술로 같은 계약을 다시 구현한다. 문서의 계산기와
운영 엔진이 같은 잘못된 모듈을 공유한 결과만으로는 독립검증이 아니기 때문이다
(CLR-18-02 오류 사례).

문서가 못박은 한계를 그대로 둔다: 모든 값은 SAMPLE_ONLY 합성값이며 실제
회계·규제·신용모형이 아니다. PD 1%·beta 2·LGD 50% 는 승인된 모형 값이
아니다. 본 모듈이 확인하는 것은 **요구사항·단위·수식 계약**이지 모형
적합성이 아니다 (DEC-20: 계산 재현이 모형 적합성 승인은 아니다).

사용:
    python -m tools.climate_recalc self-test
    python -m tools.climate_recalc run --fixture f.json [--claimed results.json]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class ClimateRecalcError(ValueError):
    """계약 위반 입력. 메시지 앞머리는 요건정의서의 오류 코드를 따른다."""


# --------------------------------------------------------------- 입력 계약
def _num(x: Any, label: str) -> Fraction:
    if isinstance(x, bool) or x is None:
        raise ClimateRecalcError(f"INPUT_DECIMAL: {label} 가 수치가 아니다 ({x!r})")
    if isinstance(x, float) and not math.isfinite(x):
        raise ClimateRecalcError(f"INPUT_FINITE: {label} 가 유한하지 않다")
    try:
        return Fraction(str(x))
    except (ValueError, ZeroDivisionError) as exc:
        raise ClimateRecalcError(f"INPUT_DECIMAL: {label} = {x!r}") from exc


def _ratio(x: Any, label: str) -> Fraction:
    v = _num(x, label)
    if not 0 <= v <= 1:
        raise ClimateRecalcError(f"RATIO_RANGE: {label} = {x!r} 가 [0,1] 밖")
    return v


def _amount(x: Any, label: str) -> Fraction:
    v = _num(x, label)
    if v < 0:
        raise ClimateRecalcError(f"AMOUNT_NEGATIVE: {label} = {x!r}")
    return v


def round_half_up(v: Fraction) -> int:
    """최종 금액만 원단위 ROUND_HALF_UP (CLR-04-03). 중간값은 반올림하지 않는다."""
    if v >= 0:
        return math.floor(v + Fraction(1, 2))
    return -math.floor(-v + Fraction(1, 2))


# --------------------------------------------------------------- 단계 산식
def insurance_recovery(loss: Any, deductible: Any, coverage_limit: Any,
                       recovery_factor: Any, valid: bool = True) -> Fraction:
    """min(한도, max(손실 − 자기부담, 0)) × 지급가능성. 무효 계약은 0 (CLR-07-03)."""
    if not isinstance(valid, bool):
        raise ClimateRecalcError("BOOLEAN_REQUIRED: insurance_valid")
    if not valid:
        return Fraction(0)
    covered = max(_amount(loss, "loss") - _amount(deductible, "deductible"), Fraction(0))
    return min(_amount(coverage_limit, "coverage_limit"), covered) * _ratio(recovery_factor, "recovery_factor")


def physical_loss(asset_value: Any, damage_ratio: Any, adaptation_ratio: Any,
                  insurance: Mapping[str, Any] | None) -> dict[str, Fraction]:
    """직접피해 → 적응후피해 → 보험회수 → 잔여피해 (CLR-07-01 · CLR-07-03)."""
    gross = _amount(asset_value, "asset_value") * _ratio(damage_ratio, "damage_ratio")
    adapted = gross * (1 - _ratio(adaptation_ratio, "adaptation_ratio"))
    recovery = Fraction(0)
    if insurance is not None:
        recovery = insurance_recovery(adapted, insurance["deductible"], insurance["coverage_limit"],
                                      insurance["recovery_factor"], insurance.get("valid", True))
    return {"gross_damage": gross, "adapted_damage": adapted,
            "insurance_recovery": recovery, "net_direct_damage": adapted - recovery}


def compound_damage(asset_value: Any, damage_ratios: Sequence[Any]) -> Fraction:
    """같은 자산·같은 사건의 복합 손상: V × [1 − ∏(1 − d_i)] (CLR-07-04).

    독립 항목의 단순 합산은 손상률 합이 1 을 넘을 수 있으므로 금지된다.
    """
    if not damage_ratios:
        raise ClimateRecalcError("TERM_SHAPE: 손상률이 비어 있다")
    survive = Fraction(1)
    for i, d in enumerate(damage_ratios):
        survive *= 1 - _ratio(d, f"damage_ratio[{i}]")
    return _amount(asset_value, "asset_value") * (1 - survive)


def business_interruption(annual_revenue: Any, downtime_days: Any, operating_days: Any,
                          contribution_margin: Any) -> dict[str, Fraction]:
    """매출손실 = 매출 × 중단일/가동일, 이익영향 = 매출손실 × 공헌이익률 (CLR-07-02).

    매출손실 전액과 공헌이익손실을 함께 EBITDA 에서 차감하지 않는다.
    """
    op = _num(operating_days, "operating_days")
    down = _num(downtime_days, "downtime_days")
    if op <= 0 or not 0 <= down <= op:
        raise ClimateRecalcError("DAY_RANGE: downtime_days 는 0 이상 operating_days 이하")
    lost = _amount(annual_revenue, "annual_revenue") * down / op
    return {"lost_revenue": lost,
            "interruption_margin_loss": lost * _ratio(contribution_margin, "contribution_margin")}


def carbon_cost(emissions: Any, free_allowance: Any, price: Any, pass_through: Any) -> Fraction:
    """max(배출 − 무상할당, 0) × 가격 × (1 − 전가율). 음수 순배출은 구매 0 (CLR-08-01)."""
    net = max(_amount(emissions, "emissions") - _amount(free_allowance, "free_allowance"), Fraction(0))
    return net * _amount(price, "carbon_price") * (1 - _ratio(pass_through, "pass_through"))


def pd_logit_shift(pd0: Any, ebitda_reduction: Any, beta: Any) -> float:
    """예제 로짓 보정 logit(PD0) + beta × EBITDA 감소율 (CLR-09-02). beta 는 합성값이다.

    경계 PD 0·1 은 별도 정책 대상이라 거부한다. 기부도 자산에 비부도 로짓을
    적용하는 것이 PD-001 이다.
    """
    p = _ratio(pd0, "pd_base")
    if p in (0, 1):
        raise ClimateRecalcError("PD_BOUNDARY_SEPARATE_MODEL: PD 0 또는 1 (PD-001)")
    z = math.log(float(p) / (1.0 - float(p))) + float(_num(beta, "pd_beta") * _num(ebitda_reduction, "ebitda_reduction"))
    out = 1.0 / (1.0 + math.exp(-z))
    if not math.isfinite(out):
        raise ClimateRecalcError("PD_NUMERICAL")
    return out


def ead(drawn: Any, undrawn: Any, ccf: Any) -> Fraction:
    """EAD = 잔액 + CCF × 미사용한도 (CLR-09-04)."""
    return _amount(drawn, "drawn") + _amount(undrawn, "undrawn") * _ratio(ccf, "ccf")


def ecl_term_structure(hazards: Sequence[Any], lgds: Sequence[Any], eads: Sequence[Any],
                       eir: Any, stage: int) -> tuple[Fraction, list[dict[str, Any]]]:
    """생존확률 × 조건부 PD × LGD × EAD × 할인계수의 기간 합 (CLR-10-01).

    Stage 1 은 1차연도 손실만, Stage 2 는 전 기간. Stage 3 은 현금부족액
    엔진이 따로 있어야 하므로 거부한다.
    """
    if stage not in (1, 2):
        raise ClimateRecalcError("STAGE3_CASHFLOW_MODEL_REQUIRED: Stage 는 1 또는 2")
    if not hazards or not (len(hazards) == len(lgds) == len(eads)):
        raise ClimateRecalcError("TERM_SHAPE: 기간별 PD·LGD·EAD 길이가 다르다")
    r = _num(eir, "eir")
    if r <= -1:
        raise ClimateRecalcError("EIR_RANGE: EIR 은 -1 초과")
    survival = Fraction(1)
    total = Fraction(0)
    rows = []
    for year, (q, l, e) in enumerate(zip(hazards, lgds, eads), 1):
        marginal = survival * _ratio(q, f"q[{year}]")
        df = 1 / (1 + r) ** year
        loss = marginal * _ratio(l, f"lgd[{year}]") * _amount(e, f"ead[{year}]") * df
        included = stage == 2 or year == 1
        if included:
            total += loss
        rows.append({"year": year, "survival_start": survival, "marginal_pd": marginal,
                     "discount_factor": df, "discounted_loss": loss, "included": included})
        survival *= 1 - _ratio(q, f"q[{year}]")
    return total, rows


def scenario_weighted(values: Sequence[Any], weights: Sequence[Any]) -> Fraction:
    """회계 목적 시나리오 가중합: 가중치 합 1, 음수 불가 (CLR-06-03)."""
    if not values or len(values) != len(weights):
        raise ClimateRecalcError("WEIGHT_SHAPE")
    w = [_ratio(x, "weight") for x in weights]
    if sum(w) != 1:
        raise ClimateRecalcError(f"WEIGHT_SUM: 가중치 합 {float(sum(w))} ≠ 1 (SCN-002)")
    return sum(_num(v, "value") * x for v, x in zip(values, w))


def capital_bridge(cet1_start: Any, pre_impairment_profit: Any, impairment_expense: Any,
                   dividend: Any, other_adjustment: Any) -> Fraction:
    """기초자본 + 충당금차감전이익 − 충당금비용 − 배당 ± 기타조정 (CLR-10-03).

    누적 ECL 전체를 자본에서 차감하지 않는다: 충당금 비용은 별도 입력이다.
    """
    return (_num(cet1_start, "cet1_start") + _num(pre_impairment_profit, "pre_impairment_profit")
            - _num(impairment_expense, "impairment_expense") - _num(dividend, "dividend")
            + _num(other_adjustment, "other_capital_adjustment"))


# ------------------------------------------------------------- 통합 사례
#: 요건정의서 부록의 공통 합성 fixture (SAMPLE_ONLY). 실제 고객·기관 자료가 아니다.
DEMO_FIXTURE: dict[str, Any] = {
    "schema_version": "1.0.0", "classification": "SAMPLE_ONLY", "currency": "KRW",
    "asset_value": "10000000000", "damage_ratio": "0.20", "adaptation_ratio": "0.25",
    "insurance_valid": True, "deductible": "200000000", "coverage_limit": "800000000",
    "recovery_factor": "0.90", "payout_delay_days": 180,
    "annual_revenue": "20000000000", "operating_days": 365, "downtime_days": 30,
    "contribution_margin": "0.30",
    "emissions_base": "10000", "emissions_stress": "10000", "free_base": "2000", "free_stress": "2000",
    "carbon_price_base": "20000", "carbon_price_stress": "80000", "pass_through": "0.25",
    "ebitda_base": "4000000000", "net_damage_expensed_share": "0.50",
    "pd_base": "0.01", "pd_beta": "2", "lgd_base": "0.40", "lgd_stress": "0.50",
    "drawn": "8000000000", "undrawn": "2000000000", "ccf_base": "0.50", "ccf_stress": "0.75",
    "eir": "0.05", "weight_base": "0.70", "weight_stress": "0.30",
    "q_base": ["0.01", "0.012", "0.014"], "q_stress_later": ["0.025", "0.03"],
    "ead_base_later": ["8000000000", "7000000000"], "ead_stress_later": ["8500000000", "7500000000"],
    "rw_demo": "1.0", "bank_rwa_base": "1000000000000", "cet1_start": "120000000000",
    "pre_impairment_profit": "8000000000", "impairment_expense": "3000000000",
    "dividend": "2000000000", "other_capital_adjustment": "-500000000",
}

#: 요건정의서 '통합 샘플과 재현 가능한 검증자료' 절이 공표한 기대값. 원단위 반올림 금액과 비율.
PUBLISHED: dict[str, Any] = {
    "gross_damage": 2_000_000_000, "adapted_damage": 1_500_000_000,
    "insurance_recovery": 720_000_000, "net_direct_damage": 780_000_000,
    "interruption_margin_loss": 493_150_685, "carbon_cost_delta": 360_000_000,
    "ebitda_stress": 2_756_849_315,
    "ead_base": 9_000_000_000, "ead_stress": 9_500_000_000,
    "el_base": 36_000_000, "el_stress": 87_682_593, "delta_el": 51_682_593,
    "ecl_s1_weighted": 49_052_169, "ecl_s2_weighted": 152_653_183,
    "rwa_base": 9_000_000_000, "rwa_stress": 9_500_000_000,
    "cet1_end": 122_500_000_000, "bank_rwa_stress": 1_000_500_000_000,
    "ratios": {"pd_stress": 0.01845949321, "ebitda_reduction": 0.31078767123,
               "cet1_ratio_end": 0.12243878061},
}


def run(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """fixture → 단계별 금액(유리수)·비율. 반올림은 ``amounts_krw`` 에서만 한다."""
    f = fixture
    if f.get("classification") != "SAMPLE_ONLY":
        raise ClimateRecalcError("SAMPLE_PROFILE_ONLY: 합성 사례만 재계산한다 (CLR-01-03)")
    if f.get("currency") != "KRW":
        raise ClimateRecalcError("UNIT-001: 통화는 KRW 원단위")

    loss = physical_loss(f["asset_value"], f["damage_ratio"], f["adaptation_ratio"],
                         {"deductible": f["deductible"], "coverage_limit": f["coverage_limit"],
                          "recovery_factor": f["recovery_factor"], "valid": f["insurance_valid"]})
    bi = business_interruption(f["annual_revenue"], f["downtime_days"], f["operating_days"],
                               f["contribution_margin"])
    carbon_base = carbon_cost(f["emissions_base"], f["free_base"], f["carbon_price_base"], f["pass_through"])
    carbon_stress = carbon_cost(f["emissions_stress"], f["free_stress"], f["carbon_price_stress"], f["pass_through"])
    carbon_delta = carbon_stress - carbon_base

    ebitda_base = _num(f["ebitda_base"], "ebitda_base")
    if ebitda_base <= 0:
        raise ClimateRecalcError("EBITDA_NONPOSITIVE_SEPARATE_MODEL")
    expensed = loss["net_direct_damage"] * _ratio(f["net_damage_expensed_share"], "net_damage_expensed_share")
    ebitda_stress = ebitda_base - bi["interruption_margin_loss"] - carbon_delta - expensed
    reduction = (ebitda_base - ebitda_stress) / ebitda_base

    pd_stress = pd_logit_shift(f["pd_base"], reduction, f["pd_beta"])
    pd_stress_f = Fraction(repr(pd_stress))
    ead_base = ead(f["drawn"], f["undrawn"], f["ccf_base"])
    ead_stress = ead(f["drawn"], f["undrawn"], f["ccf_stress"])
    el_base = ead_base * _ratio(f["pd_base"], "pd_base") * _ratio(f["lgd_base"], "lgd_base")
    el_stress = ead_stress * pd_stress_f * _ratio(f["lgd_stress"], "lgd_stress")

    n = len(f["q_base"])
    base_eads = [ead_base] + [_amount(x, "ead_base_later") for x in f["ead_base_later"]]
    stress_eads = [ead_stress] + [_amount(x, "ead_stress_later") for x in f["ead_stress_later"]]
    q_stress = [pd_stress_f] + [Fraction(str(x)) for x in f["q_stress_later"]]
    ecl: dict[str, Fraction] = {}
    term_rows: dict[str, list] = {}
    for stage in (1, 2):
        a, rows_a = ecl_term_structure(f["q_base"], [f["lgd_base"]] * n, base_eads, f["eir"], stage)
        b, rows_b = ecl_term_structure(q_stress, [f["lgd_stress"]] * n, stress_eads, f["eir"], stage)
        ecl[f"ecl_s{stage}_base"] = a
        ecl[f"ecl_s{stage}_stress"] = b
        ecl[f"ecl_s{stage}_weighted"] = scenario_weighted([a, b], [f["weight_base"], f["weight_stress"]])
        if stage == 2:
            term_rows = {"base": rows_a, "stress": rows_b}

    rw = _amount(f["rw_demo"], "rw_demo")
    rwa_base, rwa_stress = ead_base * rw, ead_stress * rw
    bank_rwa = _amount(f["bank_rwa_base"], "bank_rwa_base") + rwa_stress - rwa_base
    if bank_rwa <= 0:
        raise ClimateRecalcError("RWA_DENOMINATOR")
    cet1 = capital_bridge(f["cet1_start"], f["pre_impairment_profit"], f["impairment_expense"],
                          f["dividend"], f["other_capital_adjustment"])

    amounts: dict[str, Fraction] = {
        **loss, **bi,
        "carbon_cost_base": carbon_base, "carbon_cost_stress": carbon_stress,
        "carbon_cost_delta": carbon_delta, "demo_expensed_damage": expensed,
        "ebitda_stress": ebitda_stress, "ead_base": ead_base, "ead_stress": ead_stress,
        "el_base": el_base, "el_stress": el_stress, "delta_el": el_stress - el_base,
        **ecl, "rwa_base": rwa_base, "rwa_stress": rwa_stress,
        "bank_rwa_stress": bank_rwa, "cet1_end": cet1,
    }
    return {
        "classification": "SAMPLE_ONLY",
        "currency": "KRW",
        "amounts_krw": {k: round_half_up(v) for k, v in amounts.items()},
        "amounts_exact": {k: str(v) for k, v in amounts.items()},
        "ratios": {"ebitda_reduction": float(reduction), "pd_stress": pd_stress,
                   "cet1_ratio_end": float(cet1 / bank_rwa)},
        "ecl_term_rows": {k: [{**r, **{kk: str(vv) for kk, vv in r.items() if isinstance(vv, Fraction)}}
                              for r in v] for k, v in term_rows.items()},
        "limits": [
            "SAMPLE_ONLY: 합성 사례의 수식 계약 재계산이며 모형 적합성 승인이 아니다 (DEC-20)",
            "부도 시점은 연말, 보험 지급 지연은 EBITDA 에 반영하지 않는다 (유동성 경로 별도)",
            "Stage 1·2 는 대안 계산이며 SICR 판정을 대신하지 않는다 (CLR-10-01)",
            "rw_demo 100% 는 이 사례에만 적용된다 (CLR-10-02)",
        ],
    }


def compare(result: Mapping[str, Any], claimed: Mapping[str, Any], *,
            ratio_tolerance: float = 1e-9) -> list[dict[str, Any]]:
    """단계별 대사. 금액은 원단위 정수 일치, 비율은 허용오차 이내."""
    rows = []
    for key, mine in result["amounts_krw"].items():
        if key in claimed:
            theirs = int(claimed[key])
            rows.append({"key": key, "recomputed": mine, "claimed": theirs,
                         "status": "ok" if mine == theirs else "breach"})
    for key, mine in result["ratios"].items():
        if key in claimed.get("ratios", {}):
            theirs = float(claimed["ratios"][key])
            ok = math.isclose(mine, theirs, rel_tol=ratio_tolerance, abs_tol=ratio_tolerance)
            rows.append({"key": key, "recomputed": mine, "claimed": theirs,
                         "status": "ok" if ok else "breach"})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="기후리스크 합성 사례 독립 재계산: 손실·재무·PD·EAD·ECL·RWA·자본 단계별 대사 (CLR-18-02)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test", help="문서 공표값과 대조 (불일치 시 exit 1)")
    p_run = sub.add_parser("run", help="fixture 재계산, --claimed 가 있으면 대사")
    p_run.add_argument("--fixture", default=None)
    p_run.add_argument("--claimed", default=None)
    p_run.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "self-test":
        rows = compare(run(DEMO_FIXTURE), PUBLISHED)
    else:
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8")) if args.fixture else DEMO_FIXTURE
        try:
            result = run(fixture)
        except ClimateRecalcError as exc:
            sys.stderr.write(f"오류: {exc}\n")
            return 2
        if not args.claimed:
            sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            return 0
        rows = compare(result, json.loads(Path(args.claimed).read_text(encoding="utf-8")))

    bad = [r for r in rows if r["status"] == "breach"]
    if args.cmd == "run" and args.json:
        sys.stdout.write(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    else:
        for r in rows:
            mark = "일치" if r["status"] == "ok" else "불일치"
            sys.stdout.write(f"[{mark}] {r['key']:<26} 재계산 {r['recomputed']} / 주장 {r['claimed']}\n")
        sys.stdout.write(f"{len(rows)}건 · 일치 {len(rows) - len(bad)} · 불일치 {len(bad)} · SAMPLE_ONLY\n")
    return 1 if bad else 0


__all__ = ["ClimateRecalcError", "DEMO_FIXTURE", "PUBLISHED", "run", "compare",
           "insurance_recovery", "physical_loss", "business_interruption", "carbon_cost",
           "pd_logit_shift", "ead", "ecl_term_structure", "scenario_weighted", "compound_damage",
           "capital_bridge", "round_half_up"]


if __name__ == "__main__":
    raise SystemExit(main())
