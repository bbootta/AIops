"""에러 / 실패 메시지 분류기.

``subagents/harness_debugger.md`` 의 6개 카테고리(데이터/방법론/코드/권한/문서화/입력)로
오류 메시지나 stack trace 문자열을 분류한다. 결과는
``harness/change_manifest.json`` 의 root_cause / targeted_fix 초안에 사용된다.

본 모듈은 자동 확정을 하지 않는다. 분류는 키워드 휴리스틱이며, 추정값이다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

CATEGORIES = ("data", "methodology", "code", "permission", "documentation", "input")

# 카테고리별 키워드 / 정규식 패턴. 우선순위는 리스트 등장 순서.
_RULES: list[tuple[str, str]] = [
    # 권한·실행 환경
    ("permission", r"PermissionError|EACCES|Operation not permitted|read[- ]only file system"),
    ("permission", r"git\s+push.*--force|--no-verify|운영계|operation(?:al)?\s+(?:db|database)"),
    # 사용자 입력
    ("input", r"required\s+columns?\s+missing|column\s+missing|missing\s+columns?\s*:"),
    ("input", r"empty input|must not be empty|must contain both 0 and 1|y_true is empty"),
    ("input", r"required\s+field|missing\s+required|컬럼\s*누락|입력\s*형식"),
    ("input", r"NaN not allowed|결측|NaN"),
    # 데이터 품질
    ("data", r"duplicat|중복|date\s+coverage|기간\s+누락|sample size|표본\s+수"),
    ("data", r"민감정보|sensitive|leakage|target leakage"),
    # 방법론
    ("methodology", r"VIF\s*>|multicoll|stationar|단위근|seasonal|trend|시나리오\s+서열"),
    ("methodology", r"calibration|캘리브|p[-_ ]value|확률|distribution|편향|bias"),
    # 문서화 / 보고
    ("documentation", r"missing_section|empty_critical|누락\s+섹션|한계\s+누락|추가\s+확인사항|워터마크|watermark"),
    ("documentation", r"인용\s+누락|citation"),
    # 코드 / 런타임 마지막 (가장 일반적이라 후순위)
    ("code", r"TypeError|ValueError|KeyError|AttributeError|IndexError|ZeroDivisionError"),
    ("code", r"ModuleNotFoundError|ImportError|SyntaxError|NameError"),
    ("code", r"TraceBack|raise\s+\w*Error"),
]

_FIX_HINTS: Mapping[str, str] = {
    "data": (
        "데이터 입력 단계에서 결측·중복·기간 누락·표본 부족 여부를 점검하고, "
        "필요 시 `tools/data_profile` 또는 `middleware/sample_size_guard`로 보강."
    ),
    "methodology": (
        "모형 가정/시나리오 서열/정상성/다중공선성을 `tools/regression_diagnostics` "
        "또는 `tools/scenario_order_check`로 재점검하고, 가정 변경 시 매니페스트에 기록."
    ),
    "code": (
        "스택트레이스를 분석해 해당 함수의 입력 검증/타입 처리를 강화. "
        "회귀 방지를 위해 pytest에 단위 테스트 추가 후 promote-if-passing 으로 전환."
    ),
    "permission": (
        "운영계 접근/외부 전송/자격증명 노출 여부를 `middleware/permission_guard`로 점검. "
        "위반 시 작업 즉시 중단하고 사용자에게 사유와 함께 질의."
    ),
    "documentation": (
        "보고서 누락 섹션/한계/추가 확인사항/인용/워터마크를 "
        "`middleware/output_completeness_guard` 와 `middleware/draft_watermark_guard` 로 보강."
    ),
    "input": (
        "검증 요청의 입력 정의(컬럼명/타입/표본 기간/목표변수)를 사용자에게 재확인하고, "
        "스키마 가드(`middleware/schema_guard`)에서 차단 메시지를 명확히 제시."
    ),
}


@dataclass(frozen=True)
class Classification:
    category: str
    confidence: str  # "high" | "medium" | "low"
    matched_pattern: str | None
    suggested_fix: str

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "matched_pattern": self.matched_pattern,
            "suggested_fix": self.suggested_fix,
        }


def classify(text: str) -> Classification:
    """문자열을 6개 카테고리 중 하나로 분류한다.

    매칭 패턴이 여러 개면 첫 번째 매칭이 우선된다. 매칭 없으면 'code' (medium)
    으로 보수적 추정.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        return Classification(
            category="input",
            confidence="low",
            matched_pattern=None,
            suggested_fix=_FIX_HINTS["input"],
        )

    matches: list[tuple[str, str]] = []
    for category, pattern in _RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches.append((category, pattern))

    if not matches:
        return Classification(
            category="code",
            confidence="low",
            matched_pattern=None,
            suggested_fix=_FIX_HINTS["code"],
        )

    primary_cat, primary_pattern = matches[0]
    distinct_cats = {cat for cat, _ in matches}
    confidence = "high" if len(distinct_cats) == 1 else "medium"
    return Classification(
        category=primary_cat,
        confidence=confidence,
        matched_pattern=primary_pattern,
        suggested_fix=_FIX_HINTS[primary_cat],
    )


def suggest_manifest_fields(text: str) -> dict:
    """classify 결과를 매니페스트 root_cause / targeted_fix 초안으로 변환."""
    cls = classify(text)
    return {
        "category": cls.category,
        "confidence": cls.confidence,
        "matched_pattern": cls.matched_pattern,
        "root_cause": (
            f"[{cls.category}] 자동 분류 (confidence={cls.confidence}). 인간 검증자가 확정 필요."
        ),
        "targeted_fix": cls.suggested_fix,
    }


_FEEDBACK_PATH = Path(__file__).resolve().parent.parent / "memory" / "classify_feedback.jsonl"


class FeedbackPolicyError(RuntimeError):
    """피드백 기록을 정책상 차단해야 함."""


def _scan_feedback_for_sensitive(text: str) -> list[dict]:
    """data_safety_guard 패턴으로 민감정보 매칭을 본다."""
    try:
        if __package__:
            from middleware.data_safety_guard import scan_text  # type: ignore
        else:  # pragma: no cover - direct module execution
            from middleware.data_safety_guard import scan_text  # type: ignore
    except Exception:
        return []
    return scan_text(text)


def record_feedback(
    text: str,
    confirmed_category: str,
    *,
    notes: str = "",
    feedback_path: Path | None = None,
    allow_sensitive: bool = False,
) -> dict:
    """인간 검증자가 확인한 카테고리를 학습 시그널로 기록한다.

    자동 분류 결과와 비교해 mismatch 여부를 함께 저장하므로, 차후 _RULES 보강의
    근거 자료가 된다. 본 함수는 분류 규칙을 자동 변경하지 않는다.

    민감정보 정책: text/notes에 ``data_safety_guard`` 가 탐지하는 패턴이
    포함되면 기본적으로 차단된다 (FeedbackPolicyError). allow_sensitive=True 로
    호출자가 명시적으로 동의하지 않는 한 기록되지 않는다 — 운영 데이터의
    학습 시그널 누출을 사전 차단.
    """
    if confirmed_category not in CATEGORIES:
        raise ValueError(
            f"confirmed_category must be one of {CATEGORIES}, got {confirmed_category!r}"
        )
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    findings = _scan_feedback_for_sensitive(text) + _scan_feedback_for_sensitive(notes)
    if findings and not allow_sensitive:
        raise FeedbackPolicyError(
            f"feedback blocked: sensitive patterns detected ({len(findings)} hits). "
            "scrub the text or call with allow_sensitive=True after explicit human review."
        )

    cls = classify(text)
    record = {
        "text": text,
        "predicted_category": cls.category,
        "confirmed_category": confirmed_category,
        "confidence": cls.confidence,
        "matched_pattern": cls.matched_pattern,
        "agreement": cls.category == confirmed_category,
        "notes": notes,
        "sensitive_overridden": bool(findings),
    }
    path = feedback_path or _FEEDBACK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


_KEYWORD_RE = re.compile(r"[A-Za-z][A-Za-z_]{3,}|[가-힣]{2,}")


def suggest_rule_changes(
    feedback_path: Path | None = None,
    *,
    min_occurrences: int = 2,
    top_k: int = 5,
) -> list[dict]:
    """피드백 mismatch에서 (confirmed_category 별) 자주 등장한 키워드를 추출.

    각 mismatch 텍스트에서 _KEYWORD_RE 토큰을 모은 뒤, 카테고리별로 빈도 상위
    top_k 키워드를 반환한다. 인간 검증자가 이를 ``_RULES`` 추가 후보로 검토한다.

    반환 list[dict] 키:
        confirmed_category, suggested_keywords (list[(token, count)]), n_samples
    """
    path = feedback_path or _FEEDBACK_PATH
    if not path.exists():
        return []
    by_cat: dict[str, dict[str, int]] = {}
    sample_count: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("agreement"):
            continue
        cat = rec.get("confirmed_category")
        text = rec.get("text", "")
        if not cat or not isinstance(text, str):
            continue
        sample_count[cat] = sample_count.get(cat, 0) + 1
        bag = by_cat.setdefault(cat, {})
        for tok in {t.lower() for t in _KEYWORD_RE.findall(text)}:
            bag[tok] = bag.get(tok, 0) + 1

    out: list[dict] = []
    for cat, bag in by_cat.items():
        ranked = sorted(
            ((tok, cnt) for tok, cnt in bag.items() if cnt >= min_occurrences),
            key=lambda x: (-x[1], x[0]),
        )[:top_k]
        out.append(
            {
                "confirmed_category": cat,
                "n_samples": sample_count.get(cat, 0),
                "suggested_keywords": ranked,
            }
        )
    out.sort(key=lambda r: -r["n_samples"])
    return out


def generate_rule_patch(
    feedback_path: Path | None = None,
    *,
    min_occurrences: int = 2,
    top_k: int = 5,
) -> str:
    """suggest_rule_changes 결과를 _RULES 패치 문자열로 변환한다.

    `("category", r"\\b키워드\\b"),` 형태로 카테고리별 새 규칙 라인을 출력한다.
    인간 검증자가 본 출력을 검토 후 ``_RULES`` 에 직접 추가/수정해야 한다.
    자동 적용은 하지 않는다 — 정책 변경 책임은 인간에게 있다.
    """
    suggestions = suggest_rule_changes(
        feedback_path, min_occurrences=min_occurrences, top_k=top_k
    )
    if not suggestions:
        return "# no rule patch suggestion (no mismatch feedback yet)\n"

    lines = [
        "# Auto-generated rule patch suggestion",
        "# Source: tools/classify_error.suggest_rule_changes",
        "# Review carefully before adding to _RULES; thresholds are heuristic.",
        "",
    ]
    for row in suggestions:
        cat = row["confirmed_category"]
        n = row["n_samples"]
        lines.append(f"# category={cat!r}, n_samples={n}")
        keys = row["suggested_keywords"]
        if not keys:
            lines.append("#   (no candidates met min_occurrences)")
            continue
        for tok, cnt in keys:
            lines.append(
                f'    ({cat!r}, r"\\b{re.escape(tok)}\\b"),  # count={cnt}'
            )
        lines.append("")
    return "\n".join(lines)


def feedback_summary(feedback_path: Path | None = None) -> dict:
    """기록된 피드백을 요약한다 (총 건수 / 일치율 / 카테고리별 mismatch)."""
    path = feedback_path or _FEEDBACK_PATH
    if not path.exists():
        return {"total": 0, "agreement": 0, "agreement_rate": 0.0, "mismatches": {}}
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    n = len(records)
    n_agree = sum(1 for r in records if r.get("agreement"))
    mismatches: dict[str, int] = {}
    for r in records:
        if not r.get("agreement"):
            key = f"{r.get('predicted_category')}->{r.get('confirmed_category')}"
            mismatches[key] = mismatches.get(key, 0) + 1
    return {
        "total": n,
        "agreement": n_agree,
        "agreement_rate": (n_agree / n) if n else 0.0,
        "mismatches": mismatches,
    }


def _cmd_classify(args: argparse.Namespace) -> int:
    text = (
        Path(args.file).read_text(encoding="utf-8") if args.file else (args.text or sys.stdin.read())
    )
    out = classify(text)
    json.dump(out.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_suggest(args: argparse.Namespace) -> int:
    text = (
        Path(args.file).read_text(encoding="utf-8") if args.file else (args.text or sys.stdin.read())
    )
    json.dump(suggest_manifest_fields(text), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_feedback(args: argparse.Namespace) -> int:
    text = (
        Path(args.file).read_text(encoding="utf-8") if args.file else (args.text or sys.stdin.read())
    )
    try:
        record = record_feedback(
            text,
            args.confirmed,
            notes=args.notes or "",
            allow_sensitive=args.allow_sensitive,
        )
    except FeedbackPolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(record, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_feedback_summary(args: argparse.Namespace) -> int:
    json.dump(feedback_summary(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="harness_debugger 6-category error classifier")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cls = sub.add_parser("classify")
    p_cls.add_argument("--file", type=str, default=None, help="path to error log file")
    p_cls.add_argument("--text", type=str, default=None, help="error text inline")
    p_cls.set_defaults(func=_cmd_classify)

    p_sug = sub.add_parser("suggest")
    p_sug.add_argument("--file", type=str, default=None)
    p_sug.add_argument("--text", type=str, default=None)
    p_sug.set_defaults(func=_cmd_suggest)

    p_fb = sub.add_parser("feedback", help="record human-confirmed category for a sample")
    p_fb.add_argument("--confirmed", required=True, choices=list(CATEGORIES))
    p_fb.add_argument("--file", type=str, default=None)
    p_fb.add_argument("--text", type=str, default=None)
    p_fb.add_argument("--notes", type=str, default=None)
    p_fb.add_argument(
        "--allow-sensitive",
        action="store_true",
        help="민감정보 패턴이 탐지되어도 명시적으로 기록 진행 (인간 검토 후에만 사용)",
    )
    p_fb.set_defaults(func=_cmd_feedback)

    sub.add_parser("feedback-summary").set_defaults(func=_cmd_feedback_summary)

    p_src = sub.add_parser(
        "suggest-rule-changes",
        help="mismatch 패턴 분석 → _RULES 추가 키워드 후보 제시",
    )
    p_src.add_argument("--min-occurrences", type=int, default=2)
    p_src.add_argument("--top-k", type=int, default=5)
    p_src.set_defaults(
        func=lambda args: (
            json.dump(
                suggest_rule_changes(
                    min_occurrences=args.min_occurrences, top_k=args.top_k
                ),
                sys.stdout,
                ensure_ascii=False,
                indent=2,
            )
            or sys.stdout.write("\n")
            or 0
        )
    )

    p_rp = sub.add_parser(
        "rule-patch",
        help="suggest-rule-changes 결과를 _RULES 패치 문자열로 출력",
    )
    p_rp.add_argument("--min-occurrences", type=int, default=2)
    p_rp.add_argument("--top-k", type=int, default=5)
    p_rp.set_defaults(
        func=lambda args: (
            sys.stdout.write(
                generate_rule_patch(
                    min_occurrences=args.min_occurrences, top_k=args.top_k
                )
            )
            or 0
        )
    )

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
