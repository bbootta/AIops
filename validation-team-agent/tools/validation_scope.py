"""검증 범위·중요도 등급 (PRD-VAL VAL-004).

모형의 중요도를 요소별 점수로 산정해 등급을 부여하고, 등급별 **최소** 검증
심도·주기를 강제한다. 검증 계획이 최소 기준에 미달하면 통과시키지 않는다.

핵심 통제:

- 중요도는 ``harness/model_materiality.json`` 의 요소·배점으로만 산정한다.
  점수 근거가 결과에 함께 나오므로 왜 그 등급인지 설명할 수 있다.
- 심도·주기를 낮추는 **예외는 사유·승인권자·만료일이 모두 있어야** 하며,
  만료된 예외는 효력이 없다. 예외로 등급 자체를 바꿀 수는 없다.
- 미등록 모형이 검증 계획 없이 운영되는 상황은 위반으로 보고한다.

사용:
    python -m tools.validation_scope tiers
    python -m tools.validation_scope score --attributes model.json
    python -m tools.validation_scope check --attributes model.json --plan plan.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
MATERIALITY_PATH = ROOT / "harness" / "model_materiality.json"


class ScopeError(ValueError):
    """중요도·검증계획 입력 오류."""


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or MATERIALITY_PATH).read_text(encoding="utf-8"))


def _score_factor(factor: Mapping[str, Any], value: Any) -> tuple[int, str]:
    if "bands" in factor:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ScopeError(f"{factor['key']}: 수치가 필요하다 ({value!r})")
        v = float(value)
        if v < 0:
            raise ScopeError(f"{factor['key']}: 음수 비중 {v}")
        for band in factor["bands"]:          # 정책 파일이 내림차순으로 정의
            if v >= float(band["min"]):
                return int(band["points"]), band["label"]
        raise ScopeError(f"{factor['key']}: 해당 구간 없음 ({v})")

    cats = factor["categories"]
    if value not in cats:
        raise ScopeError(
            f"{factor['key']}: 알 수 없는 값 {value!r} (가능: {sorted(cats)})")
    return int(cats[value]["points"]), cats[value]["label"]


def score_model(attributes: Mapping[str, Any], *,
                policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """모형 속성 → 요소별 배점과 중요도 등급."""
    pol = policy if policy is not None else load_policy()
    breakdown = []
    total = 0
    for factor in pol["scoring_factors"]:
        key = factor["key"]
        if key not in attributes:
            raise ScopeError(f"중요도 산정 입력 누락: {key}")
        points, label = _score_factor(factor, attributes[key])
        total += points
        breakdown.append({"key": key, "label": factor["label"],
                          "value_label": label, "points": points,
                          "rationale": factor["rationale"]})

    tier = None
    for band in pol["tier_bands"]:            # 정책 파일이 내림차순으로 정의
        if total >= int(band["min_score"]):
            tier = band["tier"]
            tier_label = band["label"]
            break
    if tier is None:
        raise ScopeError(f"등급 구간을 찾지 못했다 (score={total})")

    req = pol["tier_requirements"][tier]
    return {
        "model_id": attributes.get("model_id"),
        "score": total,
        "max_score": sum(
            max(int(b["points"]) for b in f["bands"]) if "bands" in f
            else max(int(c["points"]) for c in f["categories"].values())
            for f in pol["scoring_factors"]),
        "tier": tier,
        "tier_label": tier_label,
        "breakdown": breakdown,
        "requirements": dict(req),
    }


def _exception_active(exc: Mapping[str, Any], as_of: date,
                      required_fields: list[str]) -> tuple[bool, str]:
    missing = [f for f in required_fields if not exc.get(f)]
    if missing:
        return False, f"예외 필수 항목 누락 {missing} — 효력 없음"
    try:
        expires = date.fromisoformat(str(exc["expires_at"]))
    except ValueError:
        return False, f"예외 만료일 형식 오류: {exc['expires_at']}"
    if expires < as_of:
        return False, f"예외 만료됨 ({expires.isoformat()}) — 효력 없음"
    return True, f"예외 유효 (만료 {expires.isoformat()}, 승인 {exc['approver']})"


def check_plan(attributes: Mapping[str, Any], plan: Mapping[str, Any], *,
               as_of: date | None = None,
               policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """검증 계획이 등급별 최소 기준을 만족하는지 판정한다."""
    pol = policy if policy is not None else load_policy()
    today = as_of or date.today()
    scored = score_model(attributes, policy=pol)
    req = scored["requirements"]
    ranks = {k: int(v["rank"]) for k, v in pol["depth_levels"].items()}

    violations: list[dict[str, str]] = []
    notes: list[str] = []

    exception = plan.get("exception")
    exc_ok = False
    if exception:
        exc_ok, note = _exception_active(
            exception, today, pol["exception_policy"]["downgrade_requires"])
        notes.append(note)

    depth = plan.get("depth")
    if depth not in ranks:
        violations.append({"type": "unknown_depth",
                           "detail": f"알 수 없는 심도: {depth!r} "
                                     f"(가능: {sorted(ranks)})"})
    elif ranks[depth] < ranks[req["min_depth"]]:
        if exc_ok:
            notes.append(
                f"심도 {depth} < 최소 {req['min_depth']} 이나 유효한 예외로 허용")
        else:
            violations.append({
                "type": "depth_below_minimum",
                "detail": f"{scored['tier']} 최소 심도는 {req['min_depth']} "
                          f"인데 계획은 {depth} — 유효한 예외 없음"})

    cycle = plan.get("revalidation_cycle_months")
    if not isinstance(cycle, (int, float)) or isinstance(cycle, bool):
        violations.append({"type": "missing_cycle",
                           "detail": "revalidation_cycle_months 미제공"})
    elif float(cycle) > float(req["revalidation_cycle_months"]):
        if exc_ok:
            notes.append(
                f"재검증 주기 {cycle}개월 > 최소 기준 "
                f"{req['revalidation_cycle_months']}개월 이나 유효한 예외로 허용")
        else:
            violations.append({
                "type": "cycle_exceeds_maximum",
                "detail": f"{scored['tier']} 재검증 주기는 "
                          f"{req['revalidation_cycle_months']}개월 이내여야 하는데 "
                          f"계획은 {cycle}개월 — 유효한 예외 없음"})

    if req["independent_validation_required"] and not plan.get(
            "independent_validation"):
        # 독립성은 예외로 면제하지 않는다 — 등급 자체를 바꾸는 것과 같다.
        violations.append({
            "type": "independence_missing",
            "detail": f"{scored['tier']} 는 독립검증이 필수인데 계획에 없다 "
                      "(예외로 면제 불가)"})

    return {
        "model_id": scored["model_id"],
        "tier": scored["tier"],
        "score": scored["score"],
        "requirements": req,
        "plan": dict(plan),
        "passed": not violations,
        "violations": violations,
        "notes": notes,
    }


def render_score(scored: Mapping[str, Any]) -> str:
    lines = [
        f"중요도 산정 — {scored.get('model_id') or '(model_id 미기재)'}",
        f"  점수 {scored['score']}/{scored['max_score']} → "
        f"{scored['tier']} ({scored['tier_label']})",
        "",
    ]
    for b in scored["breakdown"]:
        lines.append(f"  {b['points']}점  {b['label']}: {b['value_label']}")
        lines.append(f"        근거: {b['rationale']}")
    req = scored["requirements"]
    lines += [
        "",
        f"  최소 심도: {req['min_depth']} · 재검증 주기 "
        f"{req['revalidation_cycle_months']}개월 · 모니터링 "
        f"{req['monitoring_cycle']} · 독립검증 "
        f"{'필수' if req['independent_validation_required'] else '선택'}",
        f"  {req['note']}",
    ]
    return "\n".join(lines)


def render_check(result: Mapping[str, Any]) -> str:
    lines = [
        f"검증계획 적정성 — {result.get('model_id') or '(model_id 미기재)'} "
        f"[{result['tier']}, 점수 {result['score']}]",
        "",
    ]
    for n in result["notes"]:
        lines.append(f"  [참고] {n}")
    for v in result["violations"]:
        lines.append(f"  [위반] {v['detail']}")
    lines.append("")
    lines.append("계획 적정" if result["passed"]
                 else "계획 부적정 — 최소 기준 미달 (상기 위반 해소 필요)")
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI
def _load_json(raw: str) -> dict[str, Any]:
    p = Path(raw)
    return json.loads(p.read_text(encoding="utf-8") if p.exists() else raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="모형 중요도 등급과 검증 범위 적정성 (VAL-004)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tiers", help="등급별 최소 기준 출력")

    p_score = sub.add_parser("score", help="중요도 산정")
    p_score.add_argument("--attributes", required=True)
    p_score.add_argument("--json", action="store_true")

    p_check = sub.add_parser("check", help="검증계획 적정성 (미달 시 exit 1)")
    p_check.add_argument("--attributes", required=True)
    p_check.add_argument("--plan", required=True)
    p_check.add_argument("--as-of", default=None)
    p_check.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    pol = load_policy()

    if args.cmd == "tiers":
        for tier, req in pol["tier_requirements"].items():
            sys.stdout.write(
                f"{tier}: 심도 {req['min_depth']} · 재검증 "
                f"{req['revalidation_cycle_months']}개월 · 모니터링 "
                f"{req['monitoring_cycle']} · 독립검증 "
                f"{'필수' if req['independent_validation_required'] else '선택'}\n")
        return 0

    try:
        attributes = _load_json(args.attributes)
        if args.cmd == "score":
            scored = score_model(attributes, policy=pol)
            sys.stdout.write(
                (json.dumps(scored, ensure_ascii=False, indent=2)
                 if args.json else render_score(scored)) + "\n")
            return 0

        plan = _load_json(args.plan)
        as_of = date.fromisoformat(args.as_of) if args.as_of else None
        result = check_plan(attributes, plan, as_of=as_of, policy=pol)
    except ScopeError as exc:
        sys.stderr.write(f"오류: {exc}\n")
        return 2

    sys.stdout.write(
        (json.dumps(result, ensure_ascii=False, indent=2)
         if args.json else render_check(result)) + "\n")
    return 0 if result["passed"] else 1


__all__ = ["ScopeError", "MATERIALITY_PATH", "load_policy", "score_model",
           "check_plan", "render_score", "render_check"]


if __name__ == "__main__":
    raise SystemExit(main())
