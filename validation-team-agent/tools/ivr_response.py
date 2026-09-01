"""독립검증 응답(response.json) 작성과 검증 (3선 → 2선).

2선의 게이트(``risk_lib.validation.independent.check_gate``)는 fail-closed 다.
응답의 run_id·request_id 가 요청과 다르거나, 요청의 재계산 대상 중 하나라도
``recalc_matches`` 에 없으면 그대로 부적합이다. 지금까지 응답은 손으로 썼고,
그 형식이 게이트가 읽는 형식과 같은지 확인하는 도구가 하니스에 없었다.
응답을 내는 쪽이 먼저 거절 사유를 찾아내야 한다.

검증하는 것
-----------
- 스키마 (``harness/ivr_response.schema.json``)
- request_id · run_id 가 요청과 같다
- ``recalc_matches`` 의 키가 요청의 ``recalc_targets`` 키와 **정확히** 같다.
  빠지면 게이트가 거절하고, 요청에 없는 키는 본 적 없는 값을 보고한 것이다
- finding_id 유일
- 판정이 지적에서 파생된 값과 같다: 중부적합 1건 이상이면 중부적합, 아니면
  경부적합 1건 이상이면 경부적합, 아니면 적합. 손으로 적은 판정이 지적과
  어긋나면 위반이다
- 재계산 불일치(``recalc_matches[k] == false``)는 그 대상을 가리키는
  중부적합 지적으로 설명돼야 한다. 불일치를 적합으로 넘기는 응답을 막는다
- 수치를 실은 지적(recomputed·reported)의 target 은 요청 대상이어야 한다

사용:
    python -m tools.ivr_response validate --request R.request.json --response R.response.json
    python -m tools.ivr_response build --request R.request.json \\
        --matches '{"lcr": true, ...}' --findings findings.json --out R.response.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "harness" / "ivr_response.schema.json"

SEVERITIES = ("적합", "경부적합", "중부적합")
VALIDATED_BY = "적합성검증 팀에이전트"


def _load_json(raw: str | Path) -> Any:
    p = Path(raw)
    text = p.read_text(encoding="utf-8") if p.exists() else str(raw)
    return json.loads(text)


def request_target_keys(request: Mapping[str, Any]) -> list[str]:
    targets = request.get("recalc_targets")
    if not isinstance(targets, list):
        raise ValueError("요청에 recalc_targets 목록이 없다")
    return [str(t["key"]) for t in targets]


def derive_verdict(findings: Sequence[Mapping[str, Any]]) -> str:
    sev = {str(f.get("severity")) for f in findings}
    if "중부적합" in sev:
        return "중부적합"
    if "경부적합" in sev:
        return "경부적합"
    return "적합"


def schema_violations(response: Mapping[str, Any]) -> list[str]:
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"스키마: {'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
            for e in sorted(validator.iter_errors(response), key=lambda e: list(e.absolute_path))]


def violations(response: Mapping[str, Any], request: Mapping[str, Any]) -> list[str]:
    out = schema_violations(response)
    if out:
        return out

    if response["run_id"] != request.get("run_id"):
        out.append(f"run_id 불일치: 응답 {response['run_id']} / 요청 {request.get('run_id')}")
    if response["request_id"] != request.get("request_id"):
        out.append(f"request_id 불일치: 응답 {response['request_id']} / "
                   f"요청 {request.get('request_id')}")

    wanted = request_target_keys(request)
    got = set(response["recalc_matches"])
    missing = sorted(set(wanted) - got)
    extra = sorted(got - set(wanted))
    if missing:
        out.append(f"재계산 미보고 {len(missing)}/{len(wanted)}건: {', '.join(missing)}")
    if extra:
        out.append(f"요청에 없는 재계산 대상: {', '.join(extra)}")

    findings = response["findings"]
    dup = [k for k, n in Counter(f["finding_id"] for f in findings).items() if n > 1]
    if dup:
        out.append(f"finding_id 중복: {', '.join(sorted(dup))}")

    derived = derive_verdict(findings)
    if response["verdict"] != derived:
        out.append(f"판정 {response['verdict']} 이 지적에서 파생된 값 {derived} 과 다르다")

    explained = {f["target"] for f in findings if f["severity"] == "중부적합"}
    for key, ok in response["recalc_matches"].items():
        if ok is False and key not in explained:
            out.append(f"재계산 불일치 {key} 를 설명하는 중부적합 지적이 없다")

    for f in findings:
        has_numbers = f.get("recomputed") is not None or f.get("reported") is not None
        if has_numbers and f["target"] not in wanted:
            out.append(f"{f['finding_id']}: 수치를 실은 지적의 target {f['target']} 이 "
                       f"요청 대상이 아니다")
    return out


def build(request: Mapping[str, Any], *, matches: Mapping[str, bool],
          findings: Sequence[Mapping[str, Any]],
          validated_by: str = VALIDATED_BY,
          validated_at: str | None = None) -> dict[str, Any]:
    """판정을 손으로 적지 않는다: 지적에서 파생한다. 위반이 있으면 예외."""
    response = {
        "request_id": request.get("request_id"),
        "run_id": request.get("run_id"),
        "verdict": derive_verdict(findings),
        "validated_by": validated_by,
        "validated_at": validated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recalc_matches": {k: bool(v) for k, v in matches.items()},
        "findings": [dict(f) for f in findings],
    }
    bad = violations(response, request)
    if bad:
        raise ValueError("응답 위반:\n  " + "\n  ".join(bad))
    return response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="독립검증 응답(response.json) 작성·검증: 게이트가 거절할 응답을 먼저 잡는다")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="응답을 요청과 대조 (위반 시 exit 1)")
    p_val.add_argument("--request", required=True)
    p_val.add_argument("--response", required=True)

    p_build = sub.add_parser("build", help="지적·재계산 결과에서 응답을 만든다")
    p_build.add_argument("--request", required=True)
    p_build.add_argument("--matches", required=True, help="JSON (문자열 또는 파일)")
    p_build.add_argument("--findings", default="[]", help="JSON 배열 (문자열 또는 파일)")
    p_build.add_argument("--validated-by", default=VALIDATED_BY)
    p_build.add_argument("--validated-at", default=None)
    p_build.add_argument("--out", default=None)

    args = parser.parse_args(argv)
    request = _load_json(args.request)

    if args.cmd == "validate":
        bad = violations(_load_json(args.response), request)
        if bad:
            for b in bad:
                sys.stdout.write(f"위반: {b}\n")
            return 1
        sys.stdout.write(f"응답 정상: {request.get('request_id')} · "
                         f"재계산 {len(request_target_keys(request))}건 전부 보고\n")
        return 0

    try:
        response = build(request, matches=_load_json(args.matches),
                         findings=_load_json(args.findings),
                         validated_by=args.validated_by, validated_at=args.validated_at)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    text = json.dumps(response, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        sys.stdout.write(f"작성: {args.out} (판정 {response['verdict']})\n")
    else:
        sys.stdout.write(text)
    return 0


__all__ = ["SEVERITIES", "derive_verdict", "violations", "build", "request_target_keys"]


if __name__ == "__main__":
    raise SystemExit(main())
