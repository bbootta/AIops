"""적대적 검증 — 리스크관리팀 검증 의뢰에 대한 2선 독립 대응 (상시 대기).

**주장이 옳다는 근거를 모으지 않는다. 틀렸을 경로를 먼저 찾는다.**

``harness/adversarial_protocol.json`` 의 challenge 는 각각 "무엇이 관측되면 이
주장이 무너지는가"(disconfirming_evidence)를 사전에 못박아 둔다. 사후에 기준을
바꿀 수 없으므로 결론에 맞춘 합리화가 어렵다.

판정 규칙
---------
- ``refuted``   — 반증 근거가 실제로 관측됨. 주장이 성립하지 않는다.
- ``survived``  — 반증을 시도했으나 무너지지 않음. **참이라는 뜻은 아니다.**
- ``unanswered``— 의뢰자가 근거를 제시하지 않음. 확인됨이 아니라 **미확인**이다.
                  입증 책임은 의뢰자에게 있다.

미확인을 통과로 세지 않는 것이 이 모듈의 핵심이다. 근거 없는 항목이 조용히
넘어가면 적대적 검증은 형식만 남는다.

산출물은 **검증의견 초안**이며 적합·부적합을 확정하지 않는다 (CLAUDE.md §7).

의뢰 형식 (JSON)::

    {
      "request_id": "RM-2026-Q3-001",
      "requester": "risk_management_team",
      "claim": "LCR 1.30 으로 규제 기준을 충족한다",
      "target": "lcr",
      "claimed_value": 1.30,
      "tolerance": 0.001,
      "inputs_operational": {"hqla": 130.0, "net_outflow": 100.0},
      "inputs_validation": {"hqla": 126.0, "net_outflow": 100.0},
      "evidence": {"sample_size": {...}, "sod": {...}, ...}
    }

사용:
    python -m tools.adversarial_review challenges
    python -m tools.adversarial_review review --request req.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = ROOT / "harness" / "adversarial_protocol.json"

VERDICT_REFUTED = "refuted"
VERDICT_SURVIVED = "survived"
VERDICT_UNANSWERED = "unanswered"


class ReviewError(ValueError):
    """의뢰 형식 오류."""


def load_protocol(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or PROTOCOL_PATH).read_text(encoding="utf-8"))


def validate_request(request: Mapping[str, Any]) -> None:
    for field in ("request_id", "claim"):
        if not str(request.get(field, "")).strip():
            raise ReviewError(f"의뢰 필수 항목 누락: {field}")


# ----------------------------------------------------------- 자동 반증 시도
def _check_recalc(request: Mapping[str, Any]) -> dict[str, Any] | None:
    """독립 재계산으로 주장값을 반증 시도한다."""
    from tools.independent_recalc import RecalcError, recalculate

    if request.get("target") is None or request.get("claimed_value") is None:
        return None
    try:
        return recalculate(
            request["target"], claimed=float(request["claimed_value"]),
            inputs_operational=request.get("inputs_operational") or {},
            inputs_validation=request.get("inputs_validation"),
            tolerance=float(request.get("tolerance", 0.0)),
            metadata=request.get("metadata"))
    except RecalcError as exc:
        return {"error": str(exc)}


def _auto_verdict(challenge: Mapping[str, Any], request: Mapping[str, Any],
                  recalc: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """자동 판정 가능한 challenge 만 처리한다. 불가하면 None."""
    kind = challenge.get("auto_check")
    if kind is None:
        return None

    if kind in ("recalc", "attribution"):
        if recalc is None:
            return None
        if "error" in recalc:
            return {"verdict": VERDICT_REFUTED,
                    "detail": f"재계산 불가 — {recalc['error']}"}
        if kind == "recalc":
            if recalc["status"] == "breach":
                return {"verdict": VERDICT_REFUTED,
                        "detail": f"독립 재계산 {recalc['recalculated']:.6f} vs "
                                  f"주장 {recalc['claimed']:.6f} "
                                  f"(차이 {recalc['variance']:+.6f} > 허용 "
                                  f"{recalc['tolerance']:.6f})"}
            note = ("" if recalc["independent_inputs_used"]
                    else " — 단, 검증팀 독립 입력이 없어 입력 자체는 검증하지 못함")
            return {"verdict": VERDICT_SURVIVED,
                    "detail": f"허용오차 이내 (차이 {recalc['variance']:+.6f})"
                              f"{note}"}
        attr = recalc["attribution"]
        if not attr["reconciled"]:
            return {"verdict": VERDICT_REFUTED,
                    "detail": "기여도 합계가 총 차이와 대사되지 않음 — "
                              "설명되지 않은 잔차 존재"}
        parts = ", ".join(f"{c['kind']} {c['contribution']:+.6f}"
                          for c in attr["components"])
        return {"verdict": VERDICT_SURVIVED,
                "detail": f"기여도 대사 PASS ({parts})"}

    if kind == "golden":
        from tools.independent_recalc import RECALCULATORS

        if request.get("target") not in RECALCULATORS:
            # 의뢰가 대상을 지정하지 않았다면 우리 계산기의 경계 동작을
            # 확인한들 의뢰 주장과 무관하다 — 통과로 세지 않는다.
            return None
        from tools.golden_regression import run_all

        report = run_all()
        if not report["deploy_allowed"]:
            failed = [r["case_id"] for r in report["changes"]["blocking"]]
            return {"verdict": VERDICT_REFUTED,
                    "detail": f"Golden Case critical 실패 {failed}"}
        return {"verdict": VERDICT_SURVIVED,
                "detail": f"Golden Case {report['n_pass']}/"
                          f"{report['n_total']} 통과 (경계·금지행위 포함)"}

    if kind == "sod":
        actors = request.get("evidence", {}).get("sod")
        if not actors:
            return None
        from middleware.sod_guard import check_sod

        res = check_sod(actors)
        if res["status"] == "FAIL":
            return {"verdict": VERDICT_REFUTED,
                    "detail": " / ".join(v["detail"]
                                         for v in res["violations"])}
        if res["status"] == "NOT_EVALUATED":
            return {"verdict": VERDICT_UNANSWERED,
                    "detail": f"수행자 미기록: {res['unrecorded_activities']}"}
        return {"verdict": VERDICT_SURVIVED, "detail": "직무분리 판정 PASS"}

    if kind == "sample_size":
        ev = request.get("evidence", {}).get("sample_size")
        if not ev:
            return None
        from middleware.sample_size_guard import check_sample_size

        res = check_sample_size(**ev)
        if not res.get("passed", False):
            return {"verdict": VERDICT_REFUTED,
                    "detail": f"표본 충분성 미달 — {res}"}
        return {"verdict": VERDICT_SURVIVED, "detail": "표본 충분성 충족"}

    return None


def review(request: Mapping[str, Any], *,
           protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """의뢰에 대해 전체 challenge 를 적용한다."""
    validate_request(request)
    pol = protocol if protocol is not None else load_protocol()
    recalc = _check_recalc(request)

    results = []
    for ch in pol["challenges"]:
        auto = _auto_verdict(ch, request, recalc)
        if auto is None:
            results.append({
                **{k: ch[k] for k in ("challenge_id", "category", "question",
                                      "severity", "disconfirming_evidence")},
                "verdict": VERDICT_UNANSWERED,
                "detail": "의뢰자 근거 미제출 — 자동 판정 불가 항목이며 "
                          "미확인으로 남는다",
                "auto": ch.get("auto_check") is not None})
            continue
        results.append({
            **{k: ch[k] for k in ("challenge_id", "category", "question",
                                  "severity", "disconfirming_evidence")},
            **auto, "auto": True})

    refuted = [r for r in results if r["verdict"] == VERDICT_REFUTED]
    unanswered = [r for r in results if r["verdict"] == VERDICT_UNANSWERED]
    blocking = [r for r in refuted + unanswered if r["severity"] == "critical"]

    return {
        "request_id": request["request_id"],
        "claim": request["claim"],
        "results": results,
        "n_total": len(results),
        "refuted": refuted,
        "unanswered": unanswered,
        "survived": [r for r in results if r["verdict"] == VERDICT_SURVIVED],
        "blocking": blocking,
        "recalc": recalc,
        # 의견 확정은 사람이 한다. 여기서는 '확정 가능 여부'만 판단한다.
        "opinion_ready": not blocking,
    }


# ------------------------------------------------------------- 의견 초안
_MARK = {VERDICT_REFUTED: "반증됨", VERDICT_SURVIVED: "반증 실패",
         VERDICT_UNANSWERED: "미확인"}


def render_opinion_draft(result: Mapping[str, Any]) -> str:
    """CLAUDE.md §3 10 섹션 구조의 검증의견 초안 (DRAFT)."""
    r = result
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for row in r["results"]:
        by_cat.setdefault(row["category"], []).append(row)

    lines = [
        f"[DRAFT] 적대적 검증 결과 — {r['request_id']}",
        "본 문서는 검증 보조 자료 초안이며, 적합·부적합 의견 확정은 인간 "
        "검증자의 권한입니다 (CLAUDE.md §7).",
        "",
        "## 1. 요약",
        f"의뢰 주장: {r['claim']}",
        f"반증 시도 {r['n_total']}건 중 반증됨 {len(r['refuted'])} · "
        f"미확인 {len(r['unanswered'])} · 반증 실패 {len(r['survived'])}",
        ("의견 확정 가능 (검증 범위 내)"
         if r["opinion_ready"] else
         f"**의견 확정 불가** — Critical 미해소 {len(r['blocking'])}건 "
         "(아래 9. 추가 확인 사항 참조)"),
        "주의: '반증 실패'는 반박 근거를 찾지 못했다는 뜻일 뿐 "
        "참이라는 뜻이 아니며, '미확인'은 통과가 아닙니다.",
        "",
        "## 2. 검증 목적",
        "리스크관리팀 의뢰 주장에 대한 독립 적대적 검증. 주장을 지지하는 근거가 "
        "아니라 주장이 무너지는 조건을 탐색합니다.",
        "",
        "## 3. 입력 데이터 및 전제",
    ]
    if r["recalc"] and "error" not in r["recalc"]:
        rc = r["recalc"]
        lines += [
            f"- 대상: {rc['target']} ({rc['description']}), 근거 산식 "
            f"{rc['formula_ref']}",
            f"- 주장값 {rc['claimed']:.6f} · 독립 재계산 "
            f"{rc['recalculated']:.6f} · 허용오차 {rc['tolerance']:.6f}",
            f"- 검증팀 독립 입력 사용: "
            f"{'예' if rc['independent_inputs_used'] else '아니오'}",
        ]
    else:
        lines.append("- 수치 재계산 대상이 지정되지 않았거나 재계산 불가")
    lines += [
        "",
        "## 4. 검증 방법",
        "harness/adversarial_protocol.json 의 사전 정의 challenge 를 적용했습니다. "
        "각 challenge 는 '무엇이 관측되면 주장이 무너지는가'를 사전에 고정해 두어 "
        "사후 기준 변경이 불가능합니다.",
        "",
        "## 5. 주요 결과",
    ]
    for cat, rows in by_cat.items():
        lines.append(f"### {cat}")
        for row in rows:
            lines.append(f"- [{_MARK[row['verdict']]}] {row['challenge_id']} "
                         f"{row['question']}")
            lines.append(f"      {row['detail']}")

    lines += ["", "## 6. 이상 징후 및 원인 후보"]
    if r["refuted"]:
        for row in r["refuted"]:
            lines.append(f"- {row['challenge_id']} ({row['severity']}): "
                         f"{row['detail']}")
    else:
        lines.append("- 반증된 항목 없음. 다만 미확인 항목은 아래를 참조.")

    lines += [
        "",
        "## 7. 한계와 리스크",
        f"- 미확인 {len(r['unanswered'])}건은 근거가 제출되지 않아 판정하지 "
        "못했습니다. 미확인은 통과가 아닙니다.",
        "- '반증 실패'는 검증 범위 내에서 반박 근거를 찾지 못했다는 뜻이며 "
        "주장의 참을 입증하지 않습니다.",
        "- 자동 판정은 등록된 계산기·정책 범위에 한정되며 복합 내부모형은 "
        "범위 밖입니다.",
        "",
        "## 8. 검증 의견 초안",
        ("제시된 범위에서 결정적 반증은 발견되지 않았습니다. 미확인 항목 해소 후 "
         "검증 책임자가 의견을 확정하십시오."
         if r["opinion_ready"] else
         "현 상태로는 의견을 확정할 수 없습니다. Critical 항목이 해소되거나 "
         "조건부 승인 절차(VAL-017)를 거쳐야 합니다."),
        "",
        "## 9. 추가 확인 사항",
    ]
    todo = sorted(r["refuted"] + r["unanswered"],
                  key=lambda x: {"critical": 0, "high": 1, "medium": 2}[
                      x["severity"]])
    if todo:
        for row in todo:
            lines.append(f"- [{row['severity']}] {row['challenge_id']}: "
                         f"{row['question']}")
            lines.append(f"      반증 기준: {row['disconfirming_evidence']}")
    else:
        lines.append("- 없음")

    lines += [
        "",
        "## 10. 감사추적 및 변경 이력",
        f"- 프로토콜: harness/adversarial_protocol.json "
        f"(policy_version {load_protocol()['policy_version']})",
        "- 판정 근거는 본 문서의 5절에 challenge 단위로 기록됩니다.",
        "- 의견 확정·조건부 승인은 change_manifest 와 조건부 승인 원장에 "
        "별도 기록되어야 합니다.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="적대적 검증 — 검증 의뢰에 대한 반증 중심 독립검증")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("challenges", help="challenge 카탈로그 출력")

    p_r = sub.add_parser("review",
                         help="의뢰 검토 (Critical 미해소 시 exit 1)")
    p_r.add_argument("--request", required=True, help="의뢰 JSON (경로 또는 문자열)")
    p_r.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    pol = load_protocol()

    if args.cmd == "challenges":
        for c in pol["challenges"]:
            auto = "auto" if c.get("auto_check") else "manual"
            sys.stdout.write(
                f"{c['challenge_id']} [{c['category']}/{c['severity']}/{auto}] "
                f"{c['question']}\n      반증 기준: "
                f"{c['disconfirming_evidence']}\n")
        return 0

    p = Path(args.request)
    raw = p.read_text(encoding="utf-8") if p.exists() else args.request
    try:
        result = review(json.loads(raw), protocol=pol)
    except ReviewError as exc:
        sys.stderr.write(f"의뢰 반려: {exc}\n")
        return 2

    sys.stdout.write(
        (json.dumps(result, ensure_ascii=False, indent=2, default=str)
         if args.json else render_opinion_draft(result)) + "\n")
    return 0 if result["opinion_ready"] else 1


__all__ = ["ReviewError", "PROTOCOL_PATH", "VERDICT_REFUTED",
           "VERDICT_SURVIVED", "VERDICT_UNANSWERED", "load_protocol",
           "validate_request", "review", "render_opinion_draft"]


if __name__ == "__main__":
    raise SystemExit(main())
