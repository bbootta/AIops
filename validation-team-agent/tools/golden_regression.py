"""Golden Case 회귀검증과 비의도 변경 차단 (PRD-VAL VAL-010/012).

배포 전에 승인된 기대결과 집합을 전량 실행해 **기존 정상 기능이 의도치 않게
바뀌지 않았는지** 확인한다. pytest 스위트가 하니스 *코드*의 회귀를 막는다면,
본 모듈은 검증 *산출값*의 회귀를 막는다.

네 가지 사례 유형을 다룬다.

- ``regression`` — 정상 입력의 기대 산출값
- ``boundary`` — 임계에 정확히 걸친 입력에서의 판정 안정성
- ``sensitivity`` — 입력 변화 시 산출이 기대한 방향·크기로 움직이는지
- ``prohibited`` — 정의되지 않은/모순된 입력은 **반드시 거부**되어야 한다
  (조용히 값을 내놓으면 실패로 본다)

비의도 변경 판정 (VAL-012)
--------------------------
실패한 사례를 변경요청서에 선언된 범위와 대조한다.

- 범위 **안**의 실패 → 의도된 변경. Golden Case 갱신과 승인이 필요하다.
- 범위 **밖**의 실패 → **비의도 변경**. 배포를 차단한다.

변경요청이 없으면 모든 실패가 비의도 변경이다 — 아무도 바뀐다고 말하지 않았기
때문이다.

사용:
    python -m tools.golden_regression run
    python -m tools.golden_regression run --change-request cr.json
    python -m tools.golden_regression list
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT / "harness" / "golden_cases.json"

KINDS = ("regression", "boundary", "sensitivity", "prohibited")


def load_cases(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or GOLDEN_PATH).read_text(encoding="utf-8"))


def _close(a: float, b: float, tol: float) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=max(tol, 1e-12))


def _invoke(fn: Any, inputs: Mapping[str, Any]) -> tuple[float | None, Any]:
    """계산기를 호출해 (값, 예외) 를 돌려준다.

    계산기가 예상 밖의 예외를 던져도 회귀 실행 전체가 중단되지 않아야 한다.
    게이트가 통째로 죽으면 리포트조차 남지 않아 사례 하나가 실패하는 것보다
    나쁘다. 예외는 삼키지 않고 실패 사유로 보고한다.
    """
    try:
        return float(fn(inputs)), None
    except Exception as exc:  # noqa: BLE001 - 사유를 보고하고 계속 진행한다
        return None, exc


def run_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """단일 Golden Case 실행. 판정은 유형별로 다르다."""
    from tools.independent_recalc import RECALCULATORS, RecalcError

    base = {"case_id": case["case_id"], "kind": case["kind"],
            "target": case["target"], "critical": bool(case.get("critical")),
            "rationale": case.get("rationale", "")}
    fn = RECALCULATORS.get(case["target"], (None,))[0]
    if fn is None:
        return {**base, "status": "fail",
                "detail": f"등록되지 않은 재계산 대상: {case['target']}"}

    # 금지행위 — 반드시 거부되어야 한다
    if case["kind"] == "prohibited":
        value, err = _invoke(fn, case["inputs"])
        if err is None:
            return {**base, "status": "fail",
                    "detail": f"거부되어야 할 입력이 값 {value} 를 산출했다"}
        if not isinstance(err, RecalcError):
            # 거부는 되었으나 통제된 방식이 아니다 — 통과로 보지 않는다.
            return {**base, "status": "fail",
                    "detail": f"정의되지 않은 예외로 실패: "
                              f"{type(err).__name__}: {err}"}
        expected_msg = case.get("expect_error", "")
        if expected_msg and expected_msg not in str(err):
            return {**base, "status": "fail",
                    "detail": f"거부되었으나 사유가 다르다: {err} "
                              f"(기대 '{expected_msg}')"}
        return {**base, "status": "pass",
                "detail": f"기대대로 거부됨: {err}"}

    # 민감도 — 방향과 크기
    if case["kind"] == "sensitivity":
        base_value, err1 = _invoke(fn, case["inputs"])
        perturbed, err2 = _invoke(fn, case["perturbed_inputs"])
        if err1 or err2:
            return {**base, "status": "fail",
                    "detail": f"산출 실패: {err1 or err2}"}
        delta = perturbed - base_value
        direction = ("increase" if delta > 0 else
                     "decrease" if delta < 0 else "flat")
        if direction != case["expected_direction"]:
            return {**base, "status": "fail",
                    "detail": f"방향 불일치: {direction} "
                              f"(기대 {case['expected_direction']}, "
                              f"delta={delta:+.9f})"}
        if "expected_delta" in case and not _close(
                delta, float(case["expected_delta"]),
                float(case.get("tolerance", 0.0))):
            return {**base, "status": "fail",
                    "detail": f"변화량 불일치: {delta:+.9f} "
                              f"(기대 {case['expected_delta']:+.9f})"}
        return {**base, "status": "pass", "observed": delta,
                "expected": case.get("expected_delta"),
                "detail": f"delta={delta:+.9f} ({direction})"}

    # 회귀 / 경계값 — 기대값 대조
    value, err = _invoke(fn, case["inputs"])
    if err is not None:
        return {**base, "status": "fail", "detail": f"산출 실패: {err}"}
    expected = float(case["expected"])
    tol = float(case.get("tolerance", 0.0))
    if not _close(value, expected, tol):
        return {**base, "status": "fail", "observed": value,
                "expected": expected,
                "detail": f"기대 {expected:.9f} vs 실제 {value:.9f} "
                          f"(차이 {value - expected:+.9f}, 허용 {tol:g})"}
    return {**base, "status": "pass", "observed": value, "expected": expected,
            "detail": f"{value:.9f}"}


def classify_changes(results: list[dict[str, Any]],
                     change_request: Mapping[str, Any] | None = None,
                     ) -> dict[str, Any]:
    """실패 사례를 변경요청 범위와 대조해 의도/비의도로 나눈다 (VAL-012)."""
    scope = (change_request or {}).get("scope", {})
    scoped_cases = set(scope.get("cases", []))
    scoped_targets = set(scope.get("targets", []))

    intended, unintended = [], []
    for r in results:
        if r["status"] != "fail":
            continue
        in_scope = (r["case_id"] in scoped_cases
                    or r["target"] in scoped_targets)
        (intended if in_scope else unintended).append(r)
    return {
        "change_id": (change_request or {}).get("change_id"),
        "intended": intended,
        "unintended": unintended,
        "blocking": [r for r in unintended if r["critical"]],
    }


def run_all(cases: Mapping[str, Any] | None = None, *,
            change_request: Mapping[str, Any] | None = None,
            ) -> dict[str, Any]:
    data = cases if cases is not None else load_cases()
    results = [run_case(c) for c in data["cases"]]
    changes = classify_changes(results, change_request)
    n_fail = sum(1 for r in results if r["status"] == "fail")
    return {
        "results": results,
        "n_total": len(results),
        "n_pass": len(results) - n_fail,
        "n_fail": n_fail,
        "changes": changes,
        # Critical 비의도 변경이 하나라도 있으면 배포 차단
        "deploy_allowed": not changes["blocking"],
    }


def render(report: Mapping[str, Any]) -> str:
    lines = [
        f"Golden Case 회귀검증 — {report['n_pass']}/{report['n_total']} 통과",
        "",
    ]
    kind = None
    for r in report["results"]:
        if r["kind"] != kind:
            kind = r["kind"]
            lines.append(f"[{kind}]")
        mark = "PASS" if r["status"] == "pass" else "FAIL"
        crit = " *critical" if r["critical"] else ""
        lines.append(f"  [{mark}] {r['case_id']} {r['target']}{crit}: "
                     f"{r['detail']}")

    ch = report["changes"]
    lines.append("")
    if ch["intended"]:
        lines.append(f"의도된 변경 {len(ch['intended'])}건 "
                     f"(변경요청 {ch['change_id']} 범위 내) — "
                     "Golden Case 갱신과 승인이 필요하다:")
        for r in ch["intended"]:
            lines.append(f"  - {r['case_id']} {r['target']}")
    if ch["unintended"]:
        lines.append(f"비의도 변경 {len(ch['unintended'])}건 "
                     "(변경요청 범위 밖):")
        for r in ch["unintended"]:
            flag = " [배포 차단]" if r["critical"] else ""
            lines.append(f"  - {r['case_id']} {r['target']}{flag}: "
                         f"{r['detail']}")
    lines.append("")
    lines.append("배포 가능" if report["deploy_allowed"]
                 else "배포 차단 — Critical 비의도 변경 미해소")
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Golden Case 회귀검증 (VAL-010) 및 비의도 변경 차단 (VAL-012)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Golden Case 목록")

    p_run = sub.add_parser("run", help="전량 실행 (배포 차단 시 exit 1)")
    p_run.add_argument("--change-request", type=Path, default=None,
                       help="변경요청 JSON (change_id, scope.targets/cases)")
    p_run.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    data = load_cases()

    if args.cmd == "list":
        for c in data["cases"]:
            crit = " *critical" if c.get("critical") else ""
            sys.stdout.write(
                f"{c['case_id']} [{c['kind']}] {c['target']}{crit} — "
                f"{c.get('rationale', '')}\n")
        return 0

    cr = None
    if args.change_request:
        cr = json.loads(args.change_request.read_text(encoding="utf-8"))

    report = run_all(data, change_request=cr)
    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render(report) + "\n")
    return 0 if report["deploy_allowed"] else 1


__all__ = ["GOLDEN_PATH", "KINDS", "load_cases", "run_case", "run_all",
           "classify_changes", "render"]


if __name__ == "__main__":
    raise SystemExit(main())
