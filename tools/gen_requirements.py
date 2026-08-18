"""RYNTA v9.6.0 업무요건정의서(BRD)에서 Level 1 요건 131건을 추출해
risk_lib/regulatory/requirements_v960.py 데이터 모듈을 생성한다.

원문 HTML은 저장소에 넣지 않는다(고객 제공 문서) — SHA-256만 박아,
어느 판의 문서에서 나온 레지스터인지 재확인할 수 있게 한다.

사용: python3 tools/gen_requirements.py <BRD.html>
"""
from __future__ import annotations

import hashlib
import html as H
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "risk_lib/regulatory/requirements_v960.py"


def main(src: str) -> None:
    raw = Path(src).read_bytes()
    s = raw.decode("utf-8")
    cards = []
    for m in re.finditer(r'<details class="req-card"([^>]*)>(.*?)</details>', s, re.S):
        attrs = dict(re.findall(r'data-(\w+)="([^"]*)"', m.group(1)))
        body = m.group(2)
        rid = re.search(r'<span class="req-id">([^<]+)</span>', body)
        title = re.search(r'<span class="req-title">([^<]+)</span>', body)
        cards.append({
            "id": H.unescape(rid.group(1)).strip(),
            "title": H.unescape(title.group(1)).strip(),
            "sector": attrs.get("sector", ""),
            "priority": attrs.get("priority", ""),
            "n_ac": len(re.findall(r'class="ac-item"', body)),
        })
    assert len(cards) == 131, f"요건 {len(cards)}건 — 131건이어야 한다 (문서가 바뀌었나?)"

    lines = [
        '"""RYNTA v9.6.0 BRD Level 1 업무요건 레지스터 — tools/gen_requirements.py 생성.',
        "",
        "손으로 고치지 않는다. 원문이 바뀌면 생성기를 다시 돌린다.",
        '"""',
        "",
        f'SOURCE = "RYNTA_Business_Requirements_v9.6.0.html"',
        f'SOURCE_SHA256 = "{hashlib.sha256(raw).hexdigest()}"',
        "",
        "# (id, 제목, 업권, 우선순위, 수용기준 수)",
        "REQUIREMENTS = (",
    ]
    for c in cards:
        lines.append(
            f'    ({c["id"]!r}, {c["title"]!r}, {c["sector"]!r}, '
            f'{c["priority"]!r}, {c["n_ac"]}),')
    lines += [")", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT} — {len(cards)}건")


if __name__ == "__main__":
    main(sys.argv[1])
