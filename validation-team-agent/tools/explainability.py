"""설명가능성 (Explainability) 헬퍼.

각 부문 step 에 대해 (a) 임계 규제 근거 attribution 과 (b) 자동 narrative
("왜 이 결과인가") 를 생성한다. 본 모듈은 판정을 변경하지 않으며 SSoT
``harness/explainability_attributions.json`` 의 사실(인용) 만 사용한다.
"""

from __future__ import annotations

import json
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent / "harness"


def load_attributions() -> list[dict]:
    p = _HARNESS / "explainability_attributions.json"
    return json.loads(p.read_text(encoding="utf-8"))["attributions"]  # type: ignore[no-any-return]


def attributions_for(step_id: str) -> list[dict]:
    return [a for a in load_attributions() if a["step"] == step_id]


def narrate(step_id: str, result: dict) -> str:
    """결과 status·detail 을 SSoT 임계 근거와 결합한 1~2 문장 narrative."""
    if not result:
        return ""
    status = result.get("status", "skipped")
    detail = result.get("detail", "")
    attrs = attributions_for(step_id)
    if not attrs:
        return f"판정 {status}. 상세: {detail}"
    a = attrs[0]
    base = (
        f"판정 <b>{status}</b>. 적용 임계: {a['minimum']} "
        f"(<i>{a['source']}</i>). 산식: <code>{a['formula']}</code>. ")
    if status == "fail":
        narrative = (
            f"<b>위반 사유:</b> {detail}. "
            f"해석: {a['interpretation']} 본 위반은 SSoT 정책의 한도/최소 기준 "
            f"미달이며, 임계 자체는 임의 완화 대상이 아닙니다 (CLAUDE.md §5).")
    elif status == "warning":
        narrative = (
            f"<b>주의 사유:</b> {detail}. "
            f"해석: {a['interpretation']} 경고 구간은 추세 모니터링 + 원인 "
            f"분석 대상이며, 후속 분기 결과로 추세 판정.")
    elif status == "ok":
        narrative = (
            f"<b>정상:</b> {detail}. 해석: {a['interpretation']}")
    else:
        narrative = f"상태 {status}. 상세: {detail}"
    return base + narrative


def render_attribution_block(step_id: str) -> str:
    """부문 페이지에 삽입할 attribution 표 (HTML)."""
    attrs = attributions_for(step_id)
    if not attrs:
        return ""
    rows = "".join(
        f"<tr><td><b>{a['metric']}</b></td>"
        f"<td><code>{a['formula']}</code></td>"
        f"<td>{a['minimum']}</td><td>{a['source']}</td>"
        f"<td><code>{a['policy_ssot']}</code></td></tr>"
        for a in attrs)
    return (
        '<details><summary><b>임계 규제 근거 (Explainability)</b> — '
        '산식 · 출처 · 정책 SSoT</summary>'
        '<table><tr><th>지표</th><th>산식</th><th>최소/임계</th>'
        '<th>출처</th><th>정책 파일</th></tr>'
        f"{rows}</table></details>")


__all__ = [
    "load_attributions",
    "attributions_for",
    "narrate",
    "render_attribution_block",
]
