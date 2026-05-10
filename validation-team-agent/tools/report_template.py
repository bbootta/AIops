"""보고서 / 점검표 템플릿.

산출물은 마크다운 문자열로 반환한다. 외부 제출본 확정에는 사용하지 않는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

REQUIRED_SECTIONS = [
    "summary",
    "purpose",
    "input_data",
    "method",
    "results",
    "anomalies",
    "limitations",
    "draft_opinion",
    "follow_ups",
    "audit_trail",
]

SECTION_TITLES = {
    "summary": "요약",
    "purpose": "검증 목적",
    "input_data": "입력 데이터 및 전제",
    "method": "검증 방법",
    "results": "주요 결과",
    "anomalies": "이상 징후 및 원인 후보",
    "limitations": "한계와 리스크",
    "draft_opinion": "검증 의견 초안",
    "follow_ups": "추가 확인 사항",
    "audit_trail": "감사추적 및 변경 이력",
}

SECTION_TITLES_EN = {
    "summary": "Summary",
    "purpose": "Validation Purpose",
    "input_data": "Input Data and Assumptions",
    "method": "Validation Method",
    "results": "Key Results",
    "anomalies": "Anomalies and Candidate Root Causes",
    "limitations": "Limitations and Risks",
    "draft_opinion": "Draft Validation Opinion",
    "follow_ups": "Follow-up Items",
    "audit_trail": "Audit Trail and Change History",
}

SECTION_TITLES_BY_LANG = {"ko": SECTION_TITLES, "en": SECTION_TITLES_EN}

_FOOTER_BY_LANG = {
    "ko": (
        "> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은 "
        "인간 검증자의 검토와 승인을 거쳐야 합니다."
    ),
    "en": (
        "> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은 "
        "인간 검증자의 검토와 승인을 거쳐야 합니다. "
        "(English: this is a draft validation aid; the final opinion and "
        "external publication require human reviewer approval.)"
    ),
}

_HEADER_BY_LANG = {
    "ko": "> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가",
    "en": (
        "> [DRAFT — 외부 제출 금지 / Do Not Distribute] "
        "인간 검증자 승인 전 사용 불가 / pending human reviewer approval"
    ),
}


# lang='en' 본문 hook: 도메인 키워드의 영문 병기. 자동 완역이 아니라 인간 검증자가
# 영문 보고서 작성 시 비용을 줄이는 용도. 사전에 없는 표현은 한글 그대로 보존된다.
_EN_BODY_GLOSSARY = {
    "검증 보조 산출물": "validation aid",
    "인간 검증자": "human reviewer",
    "외부 제출": "external publication",
    "운영계": "production system",
    "스테이지": "stage",
    "시나리오 가중치": "scenario weights",
    "캘리브레이션": "calibration",
    "다중공선성": "multicollinearity",
    "정상성": "stationarity",
    "표본": "sample",
    "변별력": "discrimination",
    "안정성": "stability",
    "이상 징후": "anomaly",
    "한계": "limitation",
    "추가 확인 사항": "follow-up",
    "감사추적": "audit trail",
    "변경 이력": "change history",
    "임계": "threshold",
}


def _translate_en(text: str) -> str:
    """간단한 도메인 사전 치환. 원문(한글) 옆에 영문을 괄호로 병기한다."""
    out = text
    seen: set[str] = set()
    for ko, en in _EN_BODY_GLOSSARY.items():
        if ko in out and ko not in seen:
            out = out.replace(ko, f"{ko} ({en})", 1)
            seen.add(ko)
    return out


def _apply_translation(body, lang: str):
    """body가 문자열/리스트일 때 lang에 따라 도메인 사전을 적용한다."""
    if lang != "en":
        return body
    if isinstance(body, list):
        return [_translate_en(str(item)) for item in body]
    return _translate_en(str(body))


def build_validation_report(
    result_dict: dict,
    *,
    lang: str = "ko",
    translate_body: bool | None = None,
) -> str:
    """표준 10개 섹션을 갖는 검증보고서 초안을 마크다운으로 반환한다.

    누락된 섹션은 "(작성 필요)" 자리표시자로 채운다. lang='en' 인 경우 섹션 제목은
    영문이지만 워터마크는 한·영 병기 (ko 한글 워터마크가 사라지면 기존 점검 도구가
    누락 판정함을 방지).

    translate_body: lang='en'일 때 True면 도메인 키워드를 영문 병기한다 (기본 True).
    False면 본문은 한글 그대로 보존된다.
    """
    if not isinstance(result_dict, dict):
        raise TypeError("result_dict must be a dict")
    if lang not in SECTION_TITLES_BY_LANG:
        raise ValueError(f"unsupported lang {lang!r}; expected one of {list(SECTION_TITLES_BY_LANG)}")

    if translate_body is None:
        translate_body = lang == "en"

    titles = SECTION_TITLES_BY_LANG[lang]
    title = result_dict.get("title", "검증 보고서 초안")
    lines = [f"# {title}", ""]
    lines.append(_HEADER_BY_LANG[lang])
    lines.append("")
    for i, key in enumerate(REQUIRED_SECTIONS, start=1):
        section_title = titles[key]
        body = result_dict.get(key, "(작성 필요)")
        if translate_body:
            body = _apply_translation(body, lang)
        lines.append(f"## {i}. {section_title}")
        if isinstance(body, list):
            for item in body:
                lines.append(f"- {item}")
        else:
            lines.append(str(body))
        lines.append("")

    lines.append(_FOOTER_BY_LANG[lang])
    return "\n".join(lines)


_PRINT_CSS_PATH = (
    Path(__file__).resolve().parent.parent / "harness" / "report_print.css"
)
_PRINT_CSS_FALLBACK = (
    "@page{size:A4;margin:18mm;}"
    "@media print{"
    "  body{font-size:10.5pt;}"
    "  h1{page-break-before:auto;}"
    "  h2{page-break-after:avoid;}"
    "  table{page-break-inside:avoid;}"
    "  blockquote{page-break-inside:avoid;}"
    "}"
)


def _load_print_css() -> str:
    """harness/report_print.css에서 인쇄용 CSS를 읽는다. 파일이 없으면 fallback."""
    try:
        return _PRINT_CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        return _PRINT_CSS_FALLBACK


def render_html(
    report_md: str,
    *,
    title: str | None = None,
    print_friendly: bool = True,
    page_break_before_h2: bool = False,
) -> str:
    """검증 보고서 마크다운을 단순 HTML로 변환한다.

    워터마크 / 표 / 헤더 / 인용 백틱은 보존된다. 외부 라이브러리 의존성 없이 안전한
    이스케이프와 최소 변환만 수행한다. 외부 제출본 확정에는 사용하지 않는다.

    print_friendly: True면 ``@page`` 와 ``@media print`` 규칙을 포함해
    브라우저 인쇄 / PDF 변환에서 페이지가 깨지지 않도록 한다.

    page_break_before_h2: True면 모든 h2 (## 섹션) 앞에 페이지 분리. 보고서 섹션
    하나당 1페이지로 분리하고 싶을 때 사용한다.
    """
    if not isinstance(report_md, str):
        raise TypeError("report_md must be a string")

    import html as _html

    head_title = title or "Validation Report"
    h2_class = ' class="pb"' if page_break_before_h2 else ""
    body_lines: list[str] = []
    in_table = False
    for line in report_md.splitlines():
        stripped = line.strip()
        if not stripped:
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append("")
            continue

        if stripped.startswith("# "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<h1>{_html.escape(stripped[2:])}</h1>")
            continue
        if stripped.startswith("## "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<h2{h2_class}>{_html.escape(stripped[3:])}</h2>")
            continue
        if stripped.startswith("> "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(
                f"<blockquote>{_html.escape(stripped[2:])}</blockquote>"
            )
            continue
        if stripped.startswith("- "):
            if in_table:
                body_lines.append("</table>")
                in_table = False
            body_lines.append(f"<li>{_render_inline(stripped[2:])}</li>")
            continue
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            if not in_table:
                body_lines.append("<table>")
                in_table = True
            tag = "td"
            row_html = "".join(f"<{tag}>{_render_inline(c)}</{tag}>" for c in cells)
            body_lines.append(f"<tr>{row_html}</tr>")
            continue

        if in_table:
            body_lines.append("</table>")
            in_table = False
        body_lines.append(f"<p>{_render_inline(stripped)}</p>")

    if in_table:
        body_lines.append("</table>")

    body = "\n".join(body_lines)

    base_css = (
        "body{font-family:sans-serif;max-width:880px;margin:2em auto;padding:0 1em;}"
        "table{border-collapse:collapse;}td{border:1px solid #ccc;padding:4px 8px;}"
        "blockquote{border-left:3px solid #888;padding:4px 12px;color:#444;background:#f7f7f7;}"
        "code{background:#f0f0f0;padding:1px 4px;border-radius:3px;}"
        ".pb{page-break-before:always;}"
    )
    css = base_css + (_load_print_css() if print_friendly else "")

    return (
        "<!doctype html>\n"
        "<html lang=\"ko\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{_html.escape(head_title)}</title>\n"
        f"<style>{css}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )


def _render_inline(text: str) -> str:
    """백틱 인용을 <code>로 감싸고 나머지는 HTML 이스케이프."""
    import html as _html
    import re as _re

    parts: list[str] = []
    last = 0
    for m in _re.finditer(r"`([^`]+)`", text):
        parts.append(_html.escape(text[last:m.start()]))
        parts.append(f"<code>{_html.escape(m.group(1))}</code>")
        last = m.end()
    parts.append(_html.escape(text[last:]))
    return "".join(parts)


def build_issue_summary(issue_list: Iterable[dict]) -> str:
    """이슈 / 이상 징후 목록을 표 형식의 마크다운으로 반환한다.

    각 이슈 dict는 다음 키를 가진다고 가정:
        id, severity, component, description, suggested_action
    누락된 키는 "(미기재)"로 채운다.
    """
    rows = list(issue_list)
    header = "| ID | Severity | Component | Description | Suggested Action |"
    sep = "|---|---|---|---|---|"
    out = [header, sep]
    for r in rows:
        out.append(
            "| {id} | {sev} | {comp} | {desc} | {act} |".format(
                id=r.get("id", "(미기재)"),
                sev=r.get("severity", "(미기재)"),
                comp=r.get("component", "(미기재)"),
                desc=r.get("description", "(미기재)").replace("|", "/"),
                act=r.get("suggested_action", "(미기재)").replace("|", "/"),
            )
        )
    return "\n".join(out)
