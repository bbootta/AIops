"""기후리스크 관리 업무요건정의서(개요) + 실무진 해설서(상세설계)에서 요건
72건(CLR-NN-MM)을 추출해 risk_lib/regulatory/requirements_clr.py 를 생성한다.

원문 HTML 두 장은 저장소에 넣지 않는다(고객 제공 문서). SHA-256 만 박아,
어느 판의 문서에서 나온 레지스터인지 재확인할 수 있게 한다.
v9.6.0 BRD 의 tools/gen_requirements.py 와 같은 규약이다.

사용: python3 tools/gen_climate_requirements.py <개요.html> <상세설계.html>
"""
from __future__ import annotations

import hashlib
import html as H
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "risk_lib/regulatory/requirements_clr.py"
N_REQ = 72


def _flat(h: str) -> str:
    h = re.sub(r'<span class="expansion">.*?</span>', '', h, flags=re.S)
    h = re.sub(r'<[^>]+>', ' ', h)
    return re.sub(r'\s+', ' ', H.unescape(h)).strip()


def _title(s: str) -> str:
    return _flat(re.search(r'<title>(.*?)</title>', s, re.S).group(1))


def main(overview: str, detail: str) -> None:
    raw_o = Path(overview).read_bytes()
    raw_d = Path(detail).read_bytes()
    det = raw_d.decode("utf-8")

    chapters = []
    for m in re.finditer(
            r'<section class="chapter" id="ch(\d\d)"[^>]*>.*?<h2>(.*?)</h2>', det, re.S):
        chapters.append((m.group(1), _flat(m.group(2))))

    reqs = []
    for m in re.finditer(r'<article class="requirement" id="(CLR-\d\d-\d\d)"[^>]*>(.*?)</article>',
                         det, re.S):
        rid, body = m.group(1), m.group(2)
        meta = re.search(r'<div class="req-meta">(.*?)</div>', body, re.S).group(1)
        pri = re.search(r'<span class="badge">.*?<abbr[^>]*>([^<]*)</abbr>', meta, re.S)
        title = re.search(r'<h3>(.*?)</h3>', body, re.S)
        # 요건마다 인수시험(AT-NN-MM) 하나가 붙는다. 그것이 수용기준이다.
        n_at = len(re.findall(r'>AT</abbr></a>-\d\d-\d\d', meta))
        reqs.append((rid, _flat(title.group(1)), "은행",
                     _flat(pri.group(1)) if pri else "", n_at))
    assert len(reqs) == N_REQ, f"요건 {len(reqs)}건, {N_REQ}건이어야 한다 (문서가 바뀌었나?)"
    assert len(chapters) == 18, f"장 {len(chapters)}개, 18개여야 한다"

    i, j = det.find('id="ch04"'), det.find('id="ch05"')
    tables = []
    for m in re.finditer(r'(clr_[a-z_]+)\s*·\s*(\d+)개 필드', _flat(det[i:j])):
        if m.group(1) not in {t for t, _ in tables}:
            tables.append((m.group(1), int(m.group(2))))

    lines = [
        '"""기후리스크 관리 업무요건 레지스터, tools/gen_climate_requirements.py 생성.',
        "",
        "손으로 고치지 않는다. 원문이 바뀌면 생성기를 다시 돌린다.",
        "요건 본문은 상세설계 문서에서 나오고, 개요 문서는 결정 항목·근거 목록의",
        "출처라 함께 지문을 남긴다.",
        '"""',
        "",
        "# (역할, 문서 제목, SHA-256)",
        "SOURCES = (",
        f'    ("overview", {_title(raw_o.decode("utf-8"))!r}, "{hashlib.sha256(raw_o).hexdigest()}"),',
        f'    ("detail", {_title(det)!r}, "{hashlib.sha256(raw_d).hexdigest()}"),',
        ")",
        "SOURCE = SOURCES[1][1]",
        "SOURCE_SHA256 = SOURCES[1][2]",
        "",
        "# (장 번호, 제목)",
        "CHAPTERS = (",
    ]
    lines += [f"    ({no!r}, {t!r})," for no, t in chapters]
    lines += [")", "", "# (id, 제목, 업권, 우선순위, 수용기준 수 = 인수시험 수)", "REQUIREMENTS = ("]
    lines += [f"    ({r[0]!r}, {r[1]!r}, {r[2]!r}, {r[3]!r}, {r[4]}),"
              for r in reqs]
    lines += [")", "", "# 상세설계 4장이 정의한 표준 원장 (이름, 필드 수). 이 하네스의",
              "# 카탈로그에는 아직 한 장도 없다. 등재 여부는 req_trace_clr 가 판정한다.",
              "TABLES = ("]
    lines += [f"    ({n!r}, {k})," for n, k in tables]
    lines += [")", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT}: 요건 {len(reqs)}건 · 장 {len(chapters)}개 · 원장 {len(tables)}장")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
