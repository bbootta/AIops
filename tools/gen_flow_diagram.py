"""배치·테이블·화면 흐름도를 계보 추출기에서 그린다.

손으로 그리지 않는다. 노드 이름도 숫자도 화살표 굵기도 전부
``risk_lib.datamodel.lineage.build_lineage()`` 가 소스에서 읽어낸 값이다.
배선이 바뀌면 다시 돌려 그림을 갱신한다. 그림과 코드가 갈라지지 않게 하려는
것이고, 갈라지면 이 파일을 고칠 것이 아니라 배선을 봐야 한다.

    python tools/gen_flow_diagram.py --out docs/flow.svg

출력은 SVG 하나다. PNG 가 필요하면 크로미움으로 변환한다 (README 참조).
"""

from __future__ import annotations

import argparse
import collections
import html
from pathlib import Path

# 도화지. 세 절을 세로로 쌓는다.
W = 1640
PAD = 44

# 블록 배치 순서. 산출이 흐르는 방향(원천 → 산출 → 보고)을 따른다.
BLOCK_ORDER = (
    "원천·리스크데이터", "신용", "시장", "운영", "ALM",
    "위기상황", "규제서식", "거버넌스·통제",
)
BLOCK_HUE = {
    "원천·리스크데이터": "#4c6ef5", "신용": "#1c7ed6", "시장": "#0ca678",
    "운영": "#f08c00", "ALM": "#7048e8", "위기상황": "#e8590c",
    "규제서식": "#495057", "거버넌스·통제": "#c2255c",
}


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


class Canvas:
    """SVG 조각을 모은다. 좌표는 호출자가 정한다."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.y = 0

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, *, size=13, weight=400, fill="#212529",
             anchor="start", opacity=1.0) -> None:
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'fill-opacity="{opacity}">{_esc(s)}</text>')

    def rect(self, x, y, w, h, *, fill, rx=6, opacity=1.0, stroke="none") -> None:
        self.add(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{rx}" fill="{fill}" fill-opacity="{opacity}" '
            f'stroke="{stroke}"/>')

    def section(self, title: str, note: str) -> None:
        self.y += 30
        self.text(PAD, self.y, title, size=21, weight=700)
        self.y += 21
        self.text(PAD, self.y, note, size=12.5, fill="#5c6670")
        self.y += 22


def _pipeline_row(c: Canvas, lin, blk) -> None:
    """1절. 전체 배치. 산출이 지나는 다섯 단계와 각 단계의 실측 규모."""
    produces = collections.Counter()
    for e in lin.edges:
        if e.kind == "produces":
            produces[e.src.split("::")[0].split("/")[-1]] += 1
    n_screen = len(lin.screens)
    n_dedicated = sum(1 for s in lin.screens.values() if not s["generic"])

    stages = [
        ("원천 생성", f"{len(produces)}개 모듈", "합성 포트폴리오·관측이력·지표",
         "#4c6ef5"),
        ("산출 엔진", "RWA·자본·ECL·ALM·한도",
         f"생산 함수 {sum(produces.values())}건", "#1c7ed6"),
        ("원장", f"TableSpec {len(lin.specs)}장",
         f"블록 {len(set(blk.values()))}개", "#0ca678"),
        ("자체검증", "정합성·규제기준·통계", "FAIL 0 이어야 결재", "#f08c00"),
        ("화면·서식", f"화면 {n_screen} (전용 {n_dedicated})",
         f"감독서식 모듈 {len(lin.forms)}", "#c2255c"),
    ]
    bw, gap, bh = 276, 26, 92
    x0 = PAD
    for i, (name, l1, l2, col) in enumerate(stages):
        x = x0 + i * (bw + gap)
        c.rect(x, c.y, bw, bh, fill=col, opacity=0.10)
        c.rect(x, c.y, 4, bh, fill=col, rx=2)
        c.text(x + 16, c.y + 27, name, size=15, weight=700, fill=col)
        c.text(x + 16, c.y + 50, l1, size=12.5, fill="#343a40")
        c.text(x + 16, c.y + 70, l2, size=12, fill="#6b7378")
        if i < len(stages) - 1:
            ax = x + bw + gap / 2
            c.add(f'<path d="M{ax - 7:.1f},{c.y + bh / 2:.1f} '
                  f'L{ax + 7:.1f},{c.y + bh / 2:.1f}" stroke="#adb5bd" '
                  f'stroke-width="2" marker-end="url(#ar)"/>')
    c.y += bh + 8


def _table_flow(c: Canvas, lin, blk) -> None:
    """2절. 테이블 흐름. 블록 간 feeds·fk 엣지를 행렬로 그린다.

    곡선 화살표로 그리면 8x8 에서 선이 서로를 넘어 어느 쪽이 어디로 가는지
    눈으로 따라갈 수 없다. 행이 재료, 열이 결과이며 칸의 진하기와 숫자가
    엣지 수다. 대각선은 블록 안쪽 흐름이라 세지 않는다.
    """
    counts = collections.Counter(blk.values())
    flow = collections.Counter()
    for e in lin.edges:
        if e.kind in ("feeds", "fk") and e.src in blk and e.dst in blk:
            a, b = blk[e.src], blk[e.dst]
            if a != b:
                flow[(a, b)] += 1

    order = [b for b in BLOCK_ORDER if b in counts]
    cw, ch = 122, 34
    lx = PAD + 176                      # 행 이름이 차지하는 폭
    top = c.y + 46                      # 열 제목 아래
    peak = max(flow.values()) if flow else 1

    for j, b in enumerate(order):       # 열 제목
        x = lx + j * cw + cw / 2
        col = BLOCK_HUE.get(b, "#495057")
        c.add(f'<text x="{x:.1f}" y="{c.y + 36:.1f}" font-size="11.5" '
              f'font-weight="700" fill="{col}" text-anchor="middle" '
              f'transform="rotate(-18 {x:.1f} {c.y + 36:.1f})">{_esc(b)}</text>')
    c.text(lx - 12, c.y + 36, "재료 → 결과", size=11.5, fill="#868e96",
           anchor="end")

    for i, a in enumerate(order):
        y = top + i * ch
        col = BLOCK_HUE.get(a, "#495057")
        c.text(lx - 12, y + 22, a, size=12.5, weight=700, fill=col,
               anchor="end")
        c.text(lx - 12, y + 22, "", size=1)
        for j, b in enumerate(order):
            x = lx + j * cw
            n = flow.get((a, b), 0)
            if a == b:
                c.rect(x + 1, y + 3, cw - 2, ch - 6, fill="#f1f3f5", rx=4)
                continue
            if not n:
                c.rect(x + 1, y + 3, cw - 2, ch - 6, fill="#fafbfc", rx=4)
                continue
            c.rect(x + 1, y + 3, cw - 2, ch - 6, fill=col, rx=4,
                   opacity=0.14 + 0.72 * (n / peak))
            dark = n / peak > 0.5
            c.text(x + cw / 2, y + 23, str(n), size=13, weight=700,
                   fill="#ffffff" if dark else col, anchor="middle")

    c.y = top + len(order) * ch + 10
    c.text(PAD, c.y + 14,
           f"블록 간 엣지 {sum(flow.values())}건. 가장 굵은 줄기는 "
           f"원천·리스크데이터에서 신용으로 가는 {flow[('원천·리스크데이터', '신용')]}건이며, "
           "회색 칸은 블록 안쪽 흐름이라 세지 않았다.", size=12.5, fill="#5c6670")
    c.y += 24


def _screen_flow(c: Canvas, lin, blk) -> None:
    """3절. 화면 흐름. 전용 화면이 어느 블록의 원장을 그리는지."""
    rend = collections.Counter()
    for s in lin.screens.values():
        if s["generic"]:
            continue
        for t in s["tables"]:
            if t in blk:
                rend[blk[t]] += 1
    total = sum(rend.values()) or 1
    order = [b for b in BLOCK_ORDER if b in rend]

    bar_x, bar_w, row_h = PAD + 178, W - PAD * 2 - 178 - 120, 30
    for i, b in enumerate(order):
        y = c.y + i * row_h
        col = BLOCK_HUE.get(b, "#495057")
        c.text(PAD + 168, y + 19, b, size=13, anchor="end", fill="#343a40")
        wdt = bar_w * rend[b] / max(rend.values())
        c.rect(bar_x, y + 6, bar_w, 18, fill="#e9ecef", rx=4)
        c.rect(bar_x, y + 6, wdt, 18, fill=col, rx=4, opacity=0.85)
        c.text(bar_x + wdt + 10, y + 19,
               f"{rend[b]}건 · {rend[b] / total * 100:.0f}%", size=12,
               fill="#6b7378")
    c.y += len(order) * row_h + 6

    unwired, orphans = lin.unwired(), lin.orphans()
    c.text(PAD, c.y + 16,
           f"전용 화면이 그리지 않는 원장 {len(unwired)}장. 그중 하류 원장도 "
           f"감독서식도 없는 고아 {len(orphans)}장.", size=12.5, fill="#c92a2a")
    c.y += 26


def build_svg() -> str:
    from risk_lib.datamodel import lineage as L

    lin = L.build_lineage()
    blk = {s.name: L.block_of(s) for s in lin.specs}

    c = Canvas()
    c.y = PAD
    c.text(PAD, c.y + 10, "리스크관리 하네스 · 배치와 흐름", size=27, weight=700)
    c.y += 40
    c.text(PAD, c.y,
           "이 그림은 손으로 그린 것이 아니라 lineage.build_lineage() 가 "
           "소스에서 읽어낸 값으로 그렸다. 배선이 바뀌면 다시 돌려 갱신한다.",
           size=12.5, fill="#5c6670")
    c.y += 16

    c.section("1. 전체 배치",
              "산출이 지나는 다섯 단계. 각 단계의 수는 실측이다.")
    _pipeline_row(c, lin, blk)

    c.section("2. 테이블 흐름",
              "행이 재료, 열이 결과다. 칸의 숫자와 진하기가 블록 사이의 feeds·fk "
              "엣지 수이며 회색 대각선은 블록 안쪽 흐름이라 세지 않는다.")
    _table_flow(c, lin, blk)

    c.section("3. 화면 흐름",
              "전용 화면이 어느 블록의 원장을 그리는지. 범용 조회기는 세지 않는다.")
    _screen_flow(c, lin, blk)

    h = c.y + PAD
    body = "\n".join(c.parts)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" \
height="{h:.0f}" viewBox="0 0 {W} {h:.0f}" font-family="Noto Sans KR, \
Malgun Gothic, Apple SD Gothic Neo, sans-serif">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"
markerHeight="5" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="#adb5bd"/></marker></defs>
<rect width="{W}" height="{h:.0f}" fill="#ffffff"/>
{body}
</svg>'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/flow.svg")
    a = ap.parse_args()
    svg = build_svg()
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg, encoding="utf-8")
    print(f"작성 완료 {p} ({len(svg) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
