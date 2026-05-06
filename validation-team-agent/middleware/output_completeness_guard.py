"""산출물 완결성 점검.

검증보고서가 표준 10개 섹션을 모두 포함하는지, '한계' / '추가 확인사항'이
실제로 비어있지 않은지, 결과 섹션의 수치가 출처(파일명·함수명)를 인용하는지
점검한다.
"""

from __future__ import annotations

import re
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


_NUMERIC_RE = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?%?")
_CITATION_RE = re.compile(
    r"`[A-Za-z_][\w/]*?(?:\.py|\.md|\.json)?(?:[:\.][A-Za-z_]\w*)+`"
    r"|`[A-Za-z_]\w*\.[A-Za-z_]\w*`"
    r"|`[A-Za-z_][\w/]*\.(?:py|md|json|jsonl|csv|parquet|xlsx|feather)`"
)
_NUMBERED_HEADER_RE = re.compile(r"^\s*\d+\.\s")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?[\s\-:|]+\|?\s*$")
_PROSE_LINE = re.compile(r"[가-힣A-Za-z]")

# 단위/범위만 표기된 라인은 출처 없이도 통과한다 (예: "(0~1)", "(%)", "단위: %", "(p < 0.05)").
_UNIT_OR_RANGE_LINE_RE = re.compile(
    r"^[\s\-•*\(\[]*"
    r"(?:단위\s*[:：]\s*)?"
    r"(?:[\d\s.~∼\-+%]*"
    r"|p\s*[<>=]\s*\d+(?:\.\d+)?"
    r"|alpha\s*=\s*\d+(?:\.\d+)?"
    r"|n\s*=\s*\d+)"
    r"[\s\)\].]*$",
    flags=re.IGNORECASE,
)


def _line_is_unit_or_range(stripped: str) -> bool:
    if _UNIT_OR_RANGE_LINE_RE.match(stripped):
        return True
    no_brackets = re.sub(r"[\(\)\[\]]", "", stripped)
    if not re.search(r"[가-힣A-Za-z]", no_brackets):
        return True
    return False


def check_numeric_citations(
    report_md: str,
    target_titles: Iterable[str] | None = None,
) -> dict:
    """결과·이상징후 섹션의 수치가 출처(파일명/함수명)를 인용하는지 점검.

    인정 규칙:
        - 산문 라인의 수치는 같은 라인에 백틱 인용이 있으면 통과.
        - 표 본문의 수치는 표 헤더, 분리자 직전 산문 라인, 또는 같은 표 안에
          인용이 있으면 통과.
        - 단위/범위 표기만 있는 라인 (예: "(0~1)", "(%)") 은 통과.
        - 번호 헤더 라인(예: "1. 요약") 은 무시.

    반환 dict 키: passed, violations(list of {section, line_no, line, numbers})
    """
    if not isinstance(report_md, str):
        raise TypeError("report_md must be a string")
    titles = list(target_titles) if target_titles else ["주요 결과", "이상 징후 및 원인 후보"]

    violations: List[dict] = []
    for title in titles:
        body = _section_body(report_md, title)
        if not body:
            continue
        lines = body.splitlines()
        n = len(lines)

        in_table = False
        table_block_has_citation = False
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                in_table = False
                table_block_has_citation = False
                continue

            if _TABLE_ROW_RE.match(stripped):
                if not in_table:
                    in_table = True
                    # look-back: 직전 산문 라인(빈 줄 1개까지 허용)에 인용이 있는지
                    table_block_has_citation = False
                    j = i - 2
                    saw_blank = 0
                    while j >= 0:
                        prev = lines[j].strip()
                        if not prev:
                            saw_blank += 1
                            if saw_blank > 1:
                                break
                            j -= 1
                            continue
                        if _CITATION_RE.search(prev):
                            table_block_has_citation = True
                            break
                        if _TABLE_ROW_RE.match(prev):
                            break
                        j -= 1
                if _CITATION_RE.search(stripped):
                    table_block_has_citation = True
                # look-ahead: 같은 표 블록 내 다른 라인에 인용이 있는지
                if not table_block_has_citation:
                    k = i
                    while k < n:
                        nxt = lines[k].strip()
                        if not nxt or not _TABLE_ROW_RE.match(nxt):
                            break
                        if _CITATION_RE.search(nxt):
                            table_block_has_citation = True
                            break
                        k += 1

                if _TABLE_SEPARATOR_RE.match(stripped):
                    continue
                nums = _NUMERIC_RE.findall(stripped)
                if nums and not table_block_has_citation:
                    violations.append(
                        {
                            "section": title,
                            "line_no": i,
                            "line": stripped,
                            "numbers": nums,
                        }
                    )
                continue

            in_table = False
            if _NUMBERED_HEADER_RE.match(stripped):
                continue
            if not _PROSE_LINE.search(stripped):
                continue
            nums = _NUMERIC_RE.findall(stripped)
            if not nums:
                continue
            if _line_is_unit_or_range(stripped):
                continue
            if not _CITATION_RE.search(stripped):
                violations.append(
                    {
                        "section": title,
                        "line_no": i,
                        "line": stripped,
                        "numbers": nums,
                    }
                )

    return {"passed": len(violations) == 0, "violations": violations}
