"""블록별 ERD 를 외래키에서 그린다.

`gen_flow_html.py` 의 흐름 행렬이 "블록끼리 얼마나 이어졌나" 를 세는 그림이라면
이쪽은 "어느 표의 어느 칸이 어느 표를 가리키나" 를 그린다. 축은 TableSpec 의
``foreign_keys`` 이고, 그것이 ERD 에서 선이 될 수 있는 유일한 근거다.

266장을 한 장에 그리지 않는다. FK 에 참여하는 122장만 블록별로 나눠 그린다.
FK 가 없는 표는 ERD 에 선이 없어 상자만 흩어지므로 목록으로 따로 적는다.

배치는 FK 방향을 따른 계층 배치다. 참조되는 쪽(부모)이 왼쪽, 참조하는 쪽이
오른쪽에 온다. 순환이 있으면 남은 것을 마지막 열에 몰고 그 사실을 적는다.

    python tools/gen_erd.py --out docs/erd.html
"""

from __future__ import annotations

import argparse
import collections
import html
from pathlib import Path

BLOCK_ORDER = (
    "원천·리스크데이터", "신용", "시장", "운영", "ALM",
    "위기상황", "규제서식", "거버넌스·통제",
)
HUE = {
    "원천·리스크데이터": "#4c6ef5", "신용": "#1c7ed6", "시장": "#0ca678",
    "운영": "#f08c00", "ALM": "#7048e8", "위기상황": "#e8590c",
    "규제서식": "#5f6b76", "거버넌스·통제": "#c2255c",
}

BOX_W = 236
ROW_H = 17          # 컬럼 한 줄
HEAD_H = 38         # 표 이름 + 한글명
COL_GAP = 108       # 계층 사이 가로 간격
SUB_GAP = 26        # 한 계층 안에서 접힌 열 사이 간격
ROW_GAP = 22        # 상자 사이 세로 간격
MAX_COLS = 7        # 상자에 적는 컬럼 수 상한
TARGET_H = 1020     # 이 높이를 넘으면 계층을 옆으로 접는다


def E(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _layers(names: set[str],
            edges: list[tuple[str, str]]) -> tuple[list[list[str]], bool]:
    """FK 방향을 따라 계층을 나눈다. 부모가 왼쪽이다.

    순환이 있으면 위상정렬이 끝나지 않으므로 남은 것을 한 계층에 몰아 넣고
    호출자가 그 사실을 적을 수 있게 그대로 돌려준다. 순환을 조용히 끊으면
    그림이 그럴듯해지고 그 표들이 서로를 참조한다는 사실이 사라진다.
    """
    indeg = {n: 0 for n in names}
    out: dict[str, set[str]] = {n: set() for n in names}
    for a, b in edges:
        if a in names and b in names and b not in out[a]:
            out[a].add(b)
            indeg[b] += 1
    layers, left, cyc = [], set(names), False
    while left:
        cur = sorted(n for n in left if indeg[n] == 0)
        if not cur:                      # 순환. 남은 것을 한 계층에 둔다
            layers.append(sorted(left))
            cyc = True
            break
        layers.append(cur)
        left -= set(cur)
        for n in cur:
            for m in out[n]:
                if m in left:
                    indeg[m] -= 1
    return layers, cyc


def _box_cols(spec, fk_cols: set[str]) -> list[tuple[str, bool, bool]]:
    """상자에 적을 컬럼. PK 와 FK 를 우선하고 나머지는 자른다."""
    pk = set(spec.primary_key or ())
    picked = [c for c in spec.columns if c.name in pk or c.name in fk_cols]
    rest = [c for c in spec.columns if c.name not in pk and c.name not in fk_cols]
    picked += rest[: max(0, MAX_COLS - len(picked))]
    return [(c.name, c.name in pk, c.name in fk_cols) for c in picked[:MAX_COLS]]


def block_erd(block, specs, fks, col_hue, mid) -> tuple[str, int, bool]:
    """블록 하나의 ERD SVG, 계층 수, 순환 여부."""
    by_name = {s.name: s for s in specs}
    names = set(by_name)
    edges = [(e.src, e.dst) for e in fks
             if e.src in names and e.dst in names]
    fk_cols: dict[str, set[str]] = collections.defaultdict(set)
    for s in specs:
        for fk in (s.foreign_keys or ()):
            fk_cols[s.name] |= set(fk.columns)

    layers, cyc = _layers(names, edges)

    # 상자 높이. 자른 칸이 있으면 "외 N칸" 줄이 한 줄 더 들어가므로 그만큼 더
    # 잡는다. 이 줄을 안 세면 마지막 컬럼명 위에 겹쳐 찍힌다.
    box_h = {}
    for n in names:
        cols = _box_cols(by_name[n], fk_cols.get(n, set()))
        more = len(by_name[n].columns) > len(cols)
        box_h[n] = HEAD_H + len(cols) * ROW_H + (ROW_H if more else 0) + 10
    parents: dict[str, list[str]] = collections.defaultdict(list)
    for a, b in edges:
        parents[b].append(a)

    # 좌표. 한 계층이 TARGET_H 를 넘으면 옆으로 접는다. 접지 않으면 신용 블록이
    # 폭 708 에 높이 3682 인 세로 기둥이 되어 ERD 로 읽히지 않는다. 접힌 열도
    # 같은 계층이므로 계층 사이 간격보다 좁게 붙여 한 덩어리로 보이게 한다.
    pos: dict[str, tuple[float, float, float]] = {}   # x, y, height
    rank: dict[str, int] = {}                         # 배치 순서. 무게중심용
    x, max_h = 10.0, 0.0
    for layer in layers:
        # 부모가 놓인 순서의 평균으로 자식을 줄 세운다. 알파벳 순으로 두면
        # 부모와 자식이 무관하게 흩어져 선이 그림 전체를 가로지른다.
        layer = sorted(layer, key=lambda n: (
            sum(rank[p] for p in parents[n] if p in rank)
            / len([p for p in parents[n] if p in rank])
            if any(p in rank for p in parents[n]) else 1e9, n))
        tall = sum(box_h[n] + ROW_GAP for n in layer)
        nsub = max(1, -(-tall // TARGET_H))           # 올림
        per = -(-len(layer) // nsub)
        for k in range(nsub):
            chunk = layer[k * per:(k + 1) * per]
            y = 10.0
            for n in chunk:
                pos[n] = (x, y, box_h[n])
                rank[n] = len(rank)
                y += box_h[n] + ROW_GAP
            max_h = max(max_h, y - ROW_GAP)
            if chunk:
                x += BOX_W + SUB_GAP
        x += COL_GAP - SUB_GAP
    w, hgt = x - COL_GAP + 10, max_h + 10
    # 뒤로 도는 선이 있으면 왼쪽으로 46 만큼 나가므로 도화지를 그만큼 넓힌다.
    vx = -60 if any(pos[b][0] <= pos[a][0] for a, b in edges) else 0
    w -= vx

    p = [f'<svg viewBox="{vx} 0 {w:.0f} {hgt:.0f}" width="100%" '
         f'style="max-width:{w:.0f}px" role="img" '
         f'aria-label="{E(block)} 블록 ERD">'
         f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
         f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{col_hue}" fill-opacity=".6"/>'
         f'</marker></defs>']
    # 화살표. 상자 뒤에 그려 상자가 선을 덮게 한다.
    for a, b in edges:
        xa, ya, ha = pos[a]
        xb, yb, hb = pos[b]
        if xb > xa:                        # 앞으로 간다. 오른쪽 → 왼쪽 변
            x1, y1, x2, y2 = xa + BOX_W, ya + ha / 2, xb, yb + hb / 2
            c = (x1 + x2) / 2
            d = (f'M{x1:.0f},{y1:.0f} C{c:.0f},{y1:.0f} '
                 f'{c:.0f},{y2:.0f} {x2:.0f},{y2:.0f}')
        else:                              # 같은 열이거나 뒤로 간다. 왼쪽으로 돈다
            x1, y1, x2, y2 = xa, ya + ha / 2, xb, yb + hb / 2
            c = min(x1, x2) - 46
            d = (f'M{x1:.0f},{y1:.0f} C{c:.0f},{y1:.0f} '
                 f'{c:.0f},{y2:.0f} {x2:.0f},{y2:.0f}')
        p.append(f'<path d="{d}" fill="none" stroke="{col_hue}" '
                 f'stroke-width="1.4" stroke-opacity="0.5" '
                 f'marker-end="url(#{mid})"/>')
    for n, (bx, by, h) in pos.items():
        sp = by_name[n]
        cols = _box_cols(sp, fk_cols.get(n, set()))
        p.append(f'<rect x="{bx:.0f}" y="{by:.0f}" width="{BOX_W}" '
                 f'height="{h:.0f}" rx="7" fill="var(--panel)" '
                 f'stroke="{col_hue}" stroke-opacity="0.45"/>')
        p.append(f'<path d="M{bx:.0f},{by + 7:.0f} a7,7 0 0 1 7,-7 '
                 f'h{BOX_W - 14} a7,7 0 0 1 7,7 v{HEAD_H - 7} h-{BOX_W} z" '
                 f'fill="{col_hue}" fill-opacity="0.14"/>')
        p.append(f'<text x="{bx + 10:.0f}" y="{by + 16:.0f}" font-size="11.5" '
                 f'font-weight="700" fill="{col_hue}" '
                 f'font-family="ui-monospace,monospace">{E(n)}</text>')
        p.append(f'<text x="{bx + 10:.0f}" y="{by + 31:.0f}" font-size="10.5" '
                 f'fill="var(--muted)">{E(sp.korean[:26])}</text>')
        for i, (cn, is_pk, is_fk) in enumerate(cols):
            cy = by + HEAD_H + 12 + i * ROW_H
            mark = "PK" if is_pk else ("FK" if is_fk else "")
            if mark:
                p.append(f'<text x="{bx + 10:.0f}" y="{cy:.0f}" font-size="8.5" '
                         f'font-weight="700" fill="{col_hue}">{mark}</text>')
            p.append(f'<text x="{bx + 32:.0f}" y="{cy:.0f}" font-size="10.5" '
                     f'fill="var(--text)" fill-opacity="{1 if mark else 0.62}" '
                     f'font-family="ui-monospace,monospace">{E(cn[:24])}</text>')
        if len(sp.columns) > len(cols):
            p.append(f'<text x="{bx + 32:.0f}" y="'
                     f'{by + HEAD_H + 12 + len(cols) * ROW_H:.0f}" '
                     f'font-size="9.5" fill="var(--muted)">'
                     f'외 {len(sp.columns) - len(cols)}칸</text>')
    p.append("</svg>")
    return "".join(p), len(layers), cyc


CSS = """
:root{--bg:#f7f9fb;--panel:#fff;--line:#e3e8ee;--text:#1a2129;--muted:#6b7681;
--dim:#eef1f4;--bad:#c2255c}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#0d1218;--panel:#141c25;--line:#26313d;--text:#e8eef4;--muted:#8d9aa7;
--dim:#1b242e;--bad:#fb6472}}
:root[data-theme="dark"]{--bg:#0d1218;--panel:#141c25;--line:#26313d;
--text:#e8eef4;--muted:#8d9aa7;--dim:#1b242e;--bad:#fb6472}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.6 "Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",
ui-sans-serif,system-ui,sans-serif}
.wrap{max-width:1560px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:27px;margin:0 0 8px;letter-spacing:-.01em}
h3{font-size:16px;margin:0 0 6px;color:var(--c,var(--text))}
.lead{color:var(--muted);margin:0 0 18px;max-width:80ch}
.note{color:var(--muted);font-size:12.5px;margin:0 0 12px;max-width:90ch}
code{font-family:ui-monospace,monospace;font-size:12.5px;background:var(--dim);
padding:1px 5px;border-radius:4px}
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 22px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:11px 15px;min-width:110px}
.kpi b{display:block;font-size:21px;font-variant-numeric:tabular-nums}
.kpi span{color:var(--muted);font-size:12px}
article{background:var(--panel);border:1px solid var(--line);border-radius:12px;
padding:16px 18px;margin:16px 0;border-left:4px solid var(--c)}
.scroll{overflow-x:auto;max-width:100%}
.tags{margin-top:10px;font-size:11.5px;color:var(--muted)}
.tag{display:inline-block;margin:2px 4px 2px 0;padding:1px 7px;border-radius:20px;
background:var(--dim);font-family:ui-monospace,monospace}
"""


def diagrams(lin, blk, tag: str = "tag") -> str:
    """블록별 ERD 본문. 단독 페이지와 흐름도 페이지가 같이 쓴다.

    ``tag`` 는 낱말 조각에 붙일 CSS 클래스다. 흐름도 페이지에는 이미 같은
    모양의 ``chip`` 이 있어 그쪽 이름을 넘겨 쓰고, 단독 페이지는 제 것을 쓴다.
    """
    fks = lin.edges_of("fk")
    joined = {e.src for e in fks} | {e.dst for e in fks}
    cross = [e for e in fks if blk.get(e.src) != blk.get(e.dst)]
    parts: list[str] = []

    for b in [x for x in BLOCK_ORDER if x in set(blk.values())]:
        names = {n for n, v in blk.items() if v == b}
        inb = sorted(names & joined)
        if not inb:
            continue
        specs = [s for s in lin.specs if s.name in inb]
        svg, n_layers, cyc = block_erd(
            b, specs, fks, HUE[b], f"ar{BLOCK_ORDER.index(b)}")
        lone = sorted(names - joined)
        x_out = [e for e in cross if blk.get(e.src) == b]
        x_in = [e for e in cross if blk.get(e.dst) == b]
        parts.append(f'''<article style="--c:{HUE[b]}"><h3>{E(b)}</h3>
<p class="note">FK 로 이어진 원장 {len(inb)}장 · 계층 {n_layers}단 ·
블록 밖으로 나가는 FK {len(x_out)}건 · 들어오는 FK {len(x_in)}건{
    " · 순환이 있어 마지막 계층은 위상정렬이 끝나지 않은 나머지다" if cyc else ""}</p>
<div class="scroll">{svg}</div>''')
        if lone:
            parts.append(
                f'<div class="tags">FK 없는 원장 {len(lone)}장 '
                + "".join(f'<span class="{tag}">{E(n)}</span>' for n in lone)
                + "</div>")
        parts.append("</article>")

    if cross:
        parts.append('<article style="--c:var(--bad)"><h3>블록 간 FK '
                     f'{len(cross)}건</h3>'
                     '<p class="note">블록 경계를 넘는 참조다. 위 블록별 그림에는 '
                     '선이 나타나지 않으므로 여기 적는다.</p><div class="tags">')
        for e in cross:
            parts.append(
                f'<span class="{tag}">{E(e.src)} → {E(e.dst)}'
                f'<span style="opacity:.6"> · {E(e.via)}</span></span> ')
        parts.append("</div></article>")
    return "\n".join(parts)


def lead(lin, blk) -> str:
    """ERD 절의 머리말. 두 페이지가 같은 문장과 같은 수를 쓰게 한다."""
    fks = lin.edges_of("fk")
    joined = {e.src for e in fks} | {e.dst for e in fks}
    return (
        '<p class="note">선은 TableSpec 의 <code>foreign_keys</code> 다. 그것이 '
        'ERD 에서 선을 그을 수 있는 유일한 근거이며 손으로 이은 선은 없다. '
        f'상자 안 <b>PK</b>·<b>FK</b> 표시와 컬럼명도 스펙에서 그대로 온다. '
        f'FK 엣지 {len(fks)}개에 원장 {len(joined)}장이 참여하고, 나머지 '
        f'{len(lin.specs) - len(joined)}장은 선이 없어 상자만 흩어지므로 각 블록 '
        '아래 목록으로 적었다. 배치는 FK 방향을 따른 계층이며 참조되는 쪽(부모)이 '
        '왼쪽이다.</p>')


def build() -> str:
    from risk_lib.datamodel import lineage as L

    lin = L.build_lineage()
    blk = {s.name: L.block_of(s) for s in lin.specs}
    fks = lin.edges_of("fk")
    joined = {e.src for e in fks} | {e.dst for e in fks}
    cross = [e for e in fks if blk.get(e.src) != blk.get(e.dst)]
    kpis = "".join(
        f'<div class="kpi"><b>{v}</b><span>{k}</span></div>' for k, v in [
            ("원장", len(lin.specs)), ("FK 엣지", len(fks)),
            ("FK 에 참여", len(joined)),
            ("FK 없는 원장", len(lin.specs) - len(joined)),
            ("블록 간 FK", len(cross))])
    return (f'<title>리스크관리 하네스 ERD</title><style>{CSS}</style>'
            '<div class="wrap"><h1>리스크관리 하네스 · 블록별 ERD</h1>'
            f'<div class="kpis">{kpis}</div>{lead(lin, blk)}'
            f'{diagrams(lin, blk)}</div>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/erd.html")
    a = ap.parse_args()
    doc = build()
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    print(f"작성 완료 {p} ({len(doc) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
