"""Output completeness guard.

Verifies that a validation report covers the standard sections defined in
`docs/validation_output_spec.md`.
"""
from __future__ import annotations

from typing import Iterable, List

REQUIRED_SECTIONS = [
    "검증 요약",
    "입력 데이터 점검",
    "주요 지표",
    "세부 분석",
    "이상 징후",
    "한계",
    "검증 의견 초안",
    "추가 확인사항",
    "감사추적",
]


def check_report_sections(
    report_text: str, required: Iterable[str] | None = None
) -> dict:
    """Check whether the report text contains each required section title."""
    required = list(required) if required is not None else list(REQUIRED_SECTIONS)
    if report_text is None:
        return {"required": required, "missing": required, "pass": False}
    missing = [s for s in required if s not in report_text]
    return {"required": required, "missing": missing, "pass": len(missing) == 0}


def assert_report_complete(report_text: str) -> None:
    """Raise ValueError when required sections are missing."""
    res = check_report_sections(report_text)
    if not res["pass"]:
        raise ValueError(f"Report missing required sections: {res['missing']}")
