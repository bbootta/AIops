"""보고서 / 점검표 템플릿.

산출물은 마크다운 문자열로 반환한다. 외부 제출본 확정에는 사용하지 않는다.
"""

from __future__ import annotations

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


def build_validation_report(result_dict: dict) -> str:
    """표준 10개 섹션을 갖는 검증보고서 초안을 마크다운으로 반환한다.

    누락된 섹션은 "(작성 필요)" 자리표시자로 채운다.
    """
    if not isinstance(result_dict, dict):
        raise TypeError("result_dict must be a dict")

    title = result_dict.get("title", "검증 보고서 초안")
    lines = [f"# {title}", ""]
    lines.append("> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가")
    lines.append("")
    for i, key in enumerate(REQUIRED_SECTIONS, start=1):
        section_title = SECTION_TITLES[key]
        body = result_dict.get(key, "(작성 필요)")
        lines.append(f"## {i}. {section_title}")
        if isinstance(body, list):
            for item in body:
                lines.append(f"- {item}")
        else:
            lines.append(str(body))
        lines.append("")

    lines.append(
        "> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은 "
        "인간 검증자의 검토와 승인을 거쳐야 합니다."
    )
    return "\n".join(lines)


def render_html(report_md: str, *, title: str | None = None) -> str:
    """검증 보고서 마크다운을 단순 HTML로 변환한다.

    워터마크 / 표 / 헤더 / 인용 백틱은 보존된다. 외부 라이브러리 의존성 없이 안전한
    이스케이프와 최소 변환만 수행한다. 외부 제출본 확정에는 사용하지 않는다.
    """
    if not isinstance(report_md, str):
        raise TypeError("report_md must be a string")

    import html as _html

    head_title = title or "Validation Report"
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
            body_lines.append(f"<h2>{_html.escape(stripped[3:])}</h2>")
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
    return (
        "<!doctype html>\n"
        "<html lang=\"ko\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{_html.escape(head_title)}</title>\n"
        "<style>body{font-family:sans-serif;max-width:880px;margin:2em auto;padding:0 1em;}"
        "table{border-collapse:collapse;}td{border:1px solid #ccc;padding:4px 8px;}"
        "blockquote{border-left:3px solid #888;padding:4px 12px;color:#444;background:#f7f7f7;}"
        "code{background:#f0f0f0;padding:1px 4px;border-radius:3px;}</style>\n"
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
