"""Draft 워터마크 점검 / 자동 삽입.

검증 산출물 초안이 외부 제출본으로 오인되어 유출되는 것을 방지하기 위해
다음 두 가지 워터마크의 존재를 강제한다.

1. HEADER 워터마크: 보고서 최상단 1순위 헤더 직후
   ``> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가``
2. FOOTER 워터마크: 보고서 말미
   ``> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은
   인간 검증자의 검토와 승인을 거쳐야 합니다.``

본 모듈은 외부 제출 자체를 차단하지 않는다. 작성·검토 단계의 사고 방지가 목적.
"""

from __future__ import annotations

HEADER_MARK = "> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가"
FOOTER_MARK = (
    "> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은 "
    "인간 검증자의 검토와 승인을 거쳐야 합니다."
)

_HEADER_KEY = "[DRAFT"
_HEADER_KEY_TAIL = "외부 제출 금지"
_FOOTER_KEY = "본 문서는 검증 보조 산출물 초안입니다"


def check_watermarks(report_md: str) -> dict:
    """헤더/푸터 워터마크 존재 여부를 점검한다.

    반환 dict 키: passed, has_header, has_footer
    """
    if not isinstance(report_md, str):
        raise TypeError("report_md must be a string")
    has_header = (_HEADER_KEY in report_md) and (_HEADER_KEY_TAIL in report_md)
    has_footer = _FOOTER_KEY in report_md
    return {
        "passed": has_header and has_footer,
        "has_header": has_header,
        "has_footer": has_footer,
    }


def ensure_watermarks(report_md: str) -> str:
    """헤더/푸터 워터마크를 누락된 경우에만 삽입한 신규 문자열을 반환한다.

    원본을 변경하지 않는다. 이미 존재하는 워터마크는 중복 삽입하지 않는다.
    """
    if not isinstance(report_md, str):
        raise TypeError("report_md must be a string")
    text = report_md
    state = check_watermarks(text)
    if not state["has_header"]:
        lines = text.splitlines()
        insert_at = 0
        for idx, line in enumerate(lines):
            if line.startswith("# "):
                insert_at = idx + 1
                break
        if insert_at == 0:
            lines = [HEADER_MARK, ""] + lines
        else:
            lines.insert(insert_at, "")
            lines.insert(insert_at + 1, HEADER_MARK)
        text = "\n".join(lines)
    state = check_watermarks(text)
    if not state["has_footer"]:
        sep = "" if text.endswith("\n") else "\n"
        text = f"{text}{sep}\n{FOOTER_MARK}\n"
    return text
