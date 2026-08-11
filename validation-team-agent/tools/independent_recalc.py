"""독립 재계산과 차이 원인 분해 (PRD-VAL VAL-007/008).

운영(또는 개발 조직)이 산출했다고 주장하는 값을 **분리된 구현**으로 다시 계산해
차이를 대조하고, 그 차이가 어디서 왔는지 분해한다.

독립성의 의미
-------------
본 모듈의 계산기는 ``src/vta/domains`` 나 ``tools/risk_checks`` 를 **호출하지
않고** 표준 산식을 직접 구현한다. 같은 코드를 다시 부르는 것은 재계산이 아니라
동어반복이므로, 도메인 모듈 미참조를 테스트로 강제한다.

한계는 명확히 둔다. 여기서 다루는 것은 비율형 표준 산출(LCR·NSFR·CET1·
레버리지·ICAAP·포트폴리오 부도율)이며, IRB·FRTB 내부모형처럼 복합적인 산출의
완전 독립 구현은 범위 밖이다. 다만 실무에서 발견되는 차이의 다수는 난해한
수학이 아니라 **입력과 규칙 적용**에서 발생하므로, 이 범위만으로도 통제 가치가
있다.

차이 원인 분해 (VAL-008)
------------------------
단계적 치환(step-wise substitution)으로 기여도를 분리한다::

    v_op  = f(운영이 사용했다는 입력)
    v_val = f(검증팀이 원천에서 확보한 입력)

    구현·산식·모형 기여 = v_op  − claimed   (같은 입력인데 결과가 다름)
    데이터 기여        = v_val − v_op       (산식 같고 입력이 다름)
    합계               = v_val − claimed = 총 차이

합계가 총 차이와 대사되므로 분해가 임의적이지 않다. 앞쪽 기여는 메타데이터
(모형·산식 버전)를 보고 ``model`` / ``formula`` / ``implementation`` 중 하나로
귀속시킨다. 의도된 보수성인지 오류인지는 사람이 판단할 몫이며 본 모듈은
그 판단 근거를 제시할 뿐이다.

사용:
    python -m tools.independent_recalc list
    python -m tools.independent_recalc run --target lcr --claimed 1.30 \\
        --inputs '{"hqla": 130.0, "net_outflow": 100.0}'
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent

#: 차이 귀속 축 — validation_finding.ROOT_CAUSES 와 동일하게 유지한다.
ATTRIBUTION_KINDS = ("data", "model", "formula", "implementation")


class RecalcError(ValueError):
    """재계산 입력 오류."""


def within_tolerance(variance: float, tolerance: float) -> bool:
    """|variance| <= tolerance. 부동소수점 표현오차만 흡수한다.

    1.30 − 1.29 는 float 에서 0.010000000000000009 이므로 단순 비교하면 허용오차
    0.01 에 정확히 걸친 값이 초과로 판정된다. 이는 기준의 문제가 아니라 표현의
    문제이므로 상대오차 1e-9 로 동등성만 보정한다. **임계 자체를 완화하지 않으며**
    (CLAUDE.md §5), 유의미한 초과는 그대로 초과로 남는다.
    """
    v, t = abs(float(variance)), float(tolerance)
    return v <= t or math.isclose(v, t, rel_tol=1e-9, abs_tol=1e-12)


def _ratio(numerator: float, denominator: float, *, label: str) -> float:
    if denominator == 0:
        raise RecalcError(f"{label}: 분모가 0 — 비율을 정의할 수 없다")
    if not all(math.isfinite(float(v)) for v in (numerator, denominator)):
        raise RecalcError(f"{label}: 유한하지 않은 입력")
    return float(numerator) / float(denominator)


def _need(inputs: Mapping[str, Any], *keys: str, label: str) -> list[float]:
    missing = [k for k in keys if k not in inputs]
    if missing:
        raise RecalcError(f"{label}: 필수 입력 누락 {missing}")
    out = []
    for k in keys:
        v = inputs[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise RecalcError(f"{label}: {k} 가 수치가 아니다 ({v!r})")
        out.append(float(v))
    return out


# --------------------------------------------------------- 독립 계산기 정의
def recalc_lcr(inputs: Mapping[str, Any]) -> float:
    hqla, outflow = _need(inputs, "hqla", "net_outflow", label="LCR")
    return _ratio(hqla, outflow, label="LCR")


def recalc_nsfr(inputs: Mapping[str, Any]) -> float:
    asf, rsf = _need(inputs, "available_stable_funding",
                     "required_stable_funding", label="NSFR")
    return _ratio(asf, rsf, label="NSFR")


def recalc_cet1_ratio(inputs: Mapping[str, Any]) -> float:
    cet1, rwa = _need(inputs, "cet1_capital", "rwa", label="CET1")
    return _ratio(cet1, rwa, label="CET1")


def recalc_leverage_ratio(inputs: Mapping[str, Any]) -> float:
    tier1, exposure = _need(inputs, "tier1_capital", "total_exposure",
                            label="Leverage")
    return _ratio(tier1, exposure, label="Leverage")


def recalc_icaap_ratio(inputs: Mapping[str, Any]) -> float:
    """가용내부자본 / 필요내부자본(분산효과 반영 후)."""
    available, gross = _need(inputs, "available_capital", "required_gross",
                             label="ICAAP")
    benefit = float(inputs.get("diversification_benefit", 0.0))
    if not 0.0 <= benefit < 1.0:
        raise RecalcError(f"ICAAP: 분산효과 {benefit} 가 [0,1) 범위 밖")
    return _ratio(available, gross * (1.0 - benefit), label="ICAAP")


def recalc_portfolio_default_rate(inputs: Mapping[str, Any]) -> float:
    defaults, obligors = _need(inputs, "default_count", "obligor_count",
                               label="부도율")
    if defaults < 0 or obligors < 0:
        raise RecalcError("부도율: 음수 건수")
    if defaults > obligors:
        raise RecalcError(
            f"부도율: 부도 {defaults:.0f} > 차주 {obligors:.0f} — 입력 모순")
    return _ratio(defaults, obligors, label="부도율")


#: target → (계산기, 설명, 산식 근거)
RECALCULATORS: dict[str, tuple[Callable[[Mapping[str, Any]], float], str, str]] = {
    "lcr": (recalc_lcr, "LCR = HQLA / 순현금유출", "BCBS LIQ40"),
    "nsfr": (recalc_nsfr, "NSFR = 가용안정자금 / 필요안정자금", "BCBS LIQ20"),
    "cet1_ratio": (recalc_cet1_ratio, "CET1 비율 = 보통주자본 / 위험가중자산",
                   "BCBS RBC20"),
    "leverage_ratio": (recalc_leverage_ratio,
                       "레버리지비율 = 기본자본 / 총익스포저", "BCBS LEV20"),
    "icaap_ratio": (recalc_icaap_ratio,
                    "내부자본비율 = 가용내부자본 / (필요내부자본 × (1−분산효과))",
                    "BCBS SRP20/30"),
    "portfolio_default_rate": (recalc_portfolio_default_rate,
                               "부도율 = 부도 차주 수 / 전체 차주 수",
                               "harness/metric_policy.md §3"),
}


# ------------------------------------------------------------- 차이 분해
def _classify_non_data(metadata: Mapping[str, Any]) -> str:
    """입력이 같은데 결과가 다르면 그 원인을 메타데이터로 귀속시킨다."""
    if metadata.get("model_version_operational") != \
            metadata.get("model_version_validation"):
        return "model"
    if metadata.get("formula_version_operational") != \
            metadata.get("formula_version_validation"):
        return "formula"
    return "implementation"


def decompose(claimed: float, value_operational_inputs: float,
              value_validation_inputs: float,
              metadata: Mapping[str, Any] | None = None,
              ) -> dict[str, Any]:
    """단계적 치환으로 총 차이를 원인별 기여도로 분해한다."""
    meta = metadata or {}
    non_data = value_operational_inputs - claimed
    data = value_validation_inputs - value_operational_inputs
    total = value_validation_inputs - claimed

    components = [
        {"kind": _classify_non_data(meta), "contribution": non_data,
         "detail": "동일 입력에 대해 운영 주장값과 독립 재계산이 다르다"},
        {"kind": "data", "contribution": data,
         "detail": "동일 산식에 대해 운영 입력과 검증 입력이 다르다"},
    ]
    reconciled = math.isclose(
        sum(c["contribution"] for c in components), total,
        rel_tol=1e-9, abs_tol=1e-12)
    return {
        "total_variance": total,
        "components": components,
        "reconciled": reconciled,
        "note": "의도된 보수성인지 오류인지는 독립 검증자가 판단한다.",
    }


# ------------------------------------------------------------ 재계산 실행
def recalculate(target: str, *, claimed: float,
                inputs_operational: Mapping[str, Any],
                inputs_validation: Mapping[str, Any] | None = None,
                tolerance: float = 0.0,
                metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """독립 재계산 + 허용오차 대조 + 차이 원인 분해.

    ``inputs_validation`` 이 없으면 운영 입력을 그대로 쓴 것으로 보며, 이때
    데이터 기여는 0 이 된다 (입력 자체를 검증하지 못했음을 뜻한다).
    """
    if target not in RECALCULATORS:
        raise RecalcError(f"등록되지 않은 재계산 대상: {target} "
                          f"(가능: {sorted(RECALCULATORS)})")
    fn, description, formula_ref = RECALCULATORS[target]
    val_inputs = (dict(inputs_validation) if inputs_validation is not None
                  else dict(inputs_operational))
    independent_inputs_used = inputs_validation is not None

    v_op = fn(inputs_operational)
    v_val = fn(val_inputs)
    variance = v_val - float(claimed)
    within = within_tolerance(variance, tolerance)

    return {
        "target": target,
        "description": description,
        "formula_ref": formula_ref,
        "claimed": float(claimed),
        "recalculated": v_val,
        "recalculated_with_operational_inputs": v_op,
        "variance": variance,
        "tolerance": float(tolerance),
        "status": "ok" if within else "breach",
        "independent_inputs_used": independent_inputs_used,
        "attribution": decompose(float(claimed), v_op, v_val, metadata),
        "hitl_note": ("허용오차 초과 건은 잠정 상태로 두고 이슈로 전환해야 한다 "
                      "(VAL-007)."),
    }


def to_finding(result: Mapping[str, Any], *, domain: str,
               owner_role: str) -> dict[str, Any]:
    """허용오차 초과 결과를 Finding 개시 인자로 변환한다 (VAL-007 → VAL-013).

    근본원인은 기여도가 가장 큰 축으로 **제안**하며, 확정은 사람이 한다.
    """
    if result["status"] != "breach":
        raise RecalcError("허용오차 이내 결과는 Finding 으로 전환하지 않는다")
    comps = [c for c in result["attribution"]["components"]
             if c["contribution"] != 0]
    dominant = max(comps, key=lambda c: abs(c["contribution"]))["kind"] \
        if comps else None
    return {
        "title": f"{result['target']} 독립 재계산 차이 "
                 f"{result['variance']:+.6f} (허용오차 {result['tolerance']})",
        "domain": domain,
        "severity": "high",
        "owner_role": owner_role,
        "target": result["target"],
        "root_cause": dominant,
    }


def render(result: Mapping[str, Any]) -> str:
    a = result["attribution"]
    lines = [
        f"독립 재계산 — {result['target']} ({result['description']})",
        f"  근거 산식: {result['formula_ref']}",
        f"  주장값 {result['claimed']:.6f} vs 재계산 "
        f"{result['recalculated']:.6f}",
        f"  차이 {result['variance']:+.6f} / 허용오차 {result['tolerance']:.6f}"
        f" → {'허용 이내' if result['status'] == 'ok' else '허용오차 초과'}",
        f"  검증팀 독립 입력 사용: "
        f"{'예' if result['independent_inputs_used'] else '아니오 (운영 입력 사용)'}",
        "",
        "차이 원인 분해:",
    ]
    for c in a["components"]:
        lines.append(f"  {c['kind']:>15}: {c['contribution']:+.6f}"
                     f"  — {c['detail']}")
    lines.append(f"  {'합계 대사':>15}: "
                 f"{'PASS' if a['reconciled'] else 'FAIL'} "
                 f"(총 차이 {a['total_variance']:+.6f})")
    lines.append("")
    lines.append(a["note"])
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="독립 재계산 및 차이 원인 분해 (VAL-007/008)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="등록된 독립 계산기 목록")

    p_run = sub.add_parser("run", help="재계산 실행 (허용오차 초과 시 exit 1)")
    p_run.add_argument("--target", required=True, choices=sorted(RECALCULATORS))
    p_run.add_argument("--claimed", type=float, required=True)
    p_run.add_argument("--inputs", required=True,
                       help="운영 입력 JSON (문자열 또는 파일 경로)")
    p_run.add_argument("--validation-inputs", default=None,
                       help="검증팀 독립 입력 JSON (선택)")
    p_run.add_argument("--tolerance", type=float, default=0.0)
    p_run.add_argument("--metadata", default=None,
                       help="모형·산식 버전 JSON (원인 귀속에 사용)")
    p_run.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "list":
        for name, (_fn, desc, ref) in sorted(RECALCULATORS.items()):
            sys.stdout.write(f"{name}: {desc} · 근거 {ref}\n")
        return 0

    def _load(raw: str | None) -> dict[str, Any] | None:
        if raw is None:
            return None
        p = Path(raw)
        text = p.read_text(encoding="utf-8") if p.exists() else raw
        return json.loads(text)

    try:
        result = recalculate(
            args.target, claimed=args.claimed,
            inputs_operational=_load(args.inputs) or {},
            inputs_validation=_load(args.validation_inputs),
            tolerance=args.tolerance, metadata=_load(args.metadata))
    except RecalcError as exc:
        sys.stderr.write(f"오류: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render(result) + "\n")
    return 0 if result["status"] == "ok" else 1


__all__ = [
    "RecalcError", "RECALCULATORS", "ATTRIBUTION_KINDS", "within_tolerance",
    "recalculate", "decompose", "to_finding", "render",
]


if __name__ == "__main__":
    raise SystemExit(main())
