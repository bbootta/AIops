"""산출물 완결성 점검.

검증보고서가 표준 10개 섹션을 모두 포함하는지, '한계' / '추가 확인사항'이
실제로 비어있지 않은지 점검한다.
"""

from __future__ import annotations

from typing import Iterable, List

REQUIRED_SECTION_TITLES = [
    "요약",
    "검증 목적",
    "입력 데이터 및 전제",
    "검증 방법",
    "주요 결과",
    "이상 징후 및 원인 후보",
    "한계와 리스크",
    "검증 의견 초안",
    "추가 확인 사항",
    "감사추적 및 변경 이력",
]

CRITICAL_SECTIONS = ["한계와 리스크", "추가 확인 사항"]


def _section_body(report_md: str, title: str) -> str:
    """report_md에서 ## [숫자.] {title} 섹션의 본문(다음 ## 헤더 직전까지)을 반환한다."""
    lines = report_md.splitlines()
    in_section = False
    body: List[str] = []
    target = title.strip()
    for line in lines:
        if line.startswith("## "):
            header = line[3:].strip()
            # "1. 요약" 형식 또는 "요약" 형식 모두 허용
            without_num = header
            if "." in header:
                left, right = header.split(".", 1)
                if left.strip().isdigit():
                    without_num = right.strip()
            if without_num == target:
                in_section = True
                body = []
                continue
            elif in_section:
                break
        elif in_section:
            body.append(line)
    return "\n".join(body).strip()


def check_report(
    report_md: str,
    required_titles: Iterable[str] | None = None,
    critical_titles: Iterable[str] | None = None,
) -> dict:
    """report_md (마크다운 문자열)의 완결성을 점검한다.

    반환 dict 키: passed, missing_sections, empty_critical, found_titles
    """
    if not isinstance(report_md, str):
        raise TypeError("report_md must be a string")

    titles = list(required_titles) if required_titles else list(REQUIRED_SECTION_TITLES)
    critical = list(critical_titles) if critical_titles else list(CRITICAL_SECTIONS)

    found = []
    missing = []
    for t in titles:
        body = _section_body(report_md, t)
        if body:
            found.append(t)
        else:
            # 섹션 헤더는 있지만 본문이 빈 경우도 missing으로 간주
            missing.append(t)

    empty_critical = []
    for t in critical:
        body = _section_body(report_md, t)
        if not body or body == "(작성 필요)":
            empty_critical.append(t)

    return {
        "passed": len(missing) == 0 and len(empty_critical) == 0,
        "missing_sections": missing,
        "empty_critical": empty_critical,
        "found_titles": found,
    }
