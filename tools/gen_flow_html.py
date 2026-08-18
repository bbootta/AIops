"""단위별 상세 흐름도를 self-contained HTML 로 그린다.

`gen_flow_diagram.py` 가 한 장 요약이라면 이쪽은 단위별 전개다. 블록 8개,
원장 266장, 화면 73개, 파이프라인 단계, 감독서식 모듈을 각각 펼친다.

여기서도 손으로 적는 값은 없다. 전부 `lineage.build_lineage()` 가 소스를
파싱해 읽어낸 것이고, 행수만 파이프라인을 한 번 돌려 채운다. 행수를 빼고
싶으면 --no-rows 를 준다 (빠르지만 '실측 행수' 칸이 빈다).

    python tools/gen_flow_html.py --out docs/flow_detail.html
"""

from __future__ import annotations

import argparse
import collections
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_erd as erd            # noqa: E402  ERD 절을 그린다
# collect() 안에 포트폴리오를 담는 지역변수 pf 가 있다. 이름을 겹치지 않게 둔다.
import gen_pipeline_flow as pflow  # noqa: E402  전체 흐름 절을 그린다

BLOCK_ORDER = (
    "원천·리스크데이터", "신용", "시장", "운영", "ALM",
    "위기상황", "규제서식", "거버넌스·통제",
)
# 블록 색은 요약 그림과 같은 값을 쓴다. 두 그림이 다른 색을 쓰면 같은 블록을
# 다른 것으로 읽게 된다.
HUE = {
    "원천·리스크데이터": "#4c6ef5", "신용": "#1c7ed6", "시장": "#0ca678",
    "운영": "#f08c00", "ALM": "#7048e8", "위기상황": "#e8590c",
    "규제서식": "#5f6b76", "거버넌스·통제": "#c2255c",
}


def E(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _slug(s: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "-", str(s)).strip("-")


# ------------------------------------------------------------------ 그림 조각

def matrix_svg(order, flow, counts) -> str:
    """블록 간 엣지 행렬. 행이 재료, 열이 결과다."""
    cw, ch, lx, ty = 116, 32, 150, 74
    w, h = lx + cw * len(order) + 16, ty + ch * len(order) + 16
    peak = max(flow.values()) if flow else 1
    p = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px" '
         f'role="img" aria-label="블록 간 원장 흐름 행렬">']
    for j, b in enumerate(order):
        x = lx + j * cw + cw / 2
        p.append(f'<text x="{x:.0f}" y="{ty - 12:.0f}" font-size="11" '
                 f'font-weight="700" fill="{HUE[b]}" text-anchor="middle" '
                 f'transform="rotate(-16 {x:.0f} {ty - 12:.0f})">{E(b)}</text>')
    for i, a in enumerate(order):
        y = ty + i * ch
        p.append(f'<text x="{lx - 10}" y="{y + 21:.0f}" font-size="12" '
                 f'font-weight="700" fill="{HUE[a]}" text-anchor="end">'
                 f'{E(a)}</text>')
        for j, b in enumerate(order):
            x, n = lx + j * cw, flow.get((a, b), 0)
            if a == b:
                p.append(f'<rect x="{x + 1}" y="{y + 3}" width="{cw - 2}" '
                         f'height="{ch - 6}" rx="4" fill="var(--dim)"/>')
                continue
            if not n:
                p.append(f'<rect x="{x + 1}" y="{y + 3}" width="{cw - 2}" '
                         f'height="{ch - 6}" rx="4" fill="var(--dim2)"/>')
                continue
            o = 0.16 + 0.74 * (n / peak)
            p.append(f'<rect x="{x + 1}" y="{y + 3}" width="{cw - 2}" '
                     f'height="{ch - 6}" rx="4" fill="{HUE[a]}" '
                     f'fill-opacity="{o:.2f}"/>')
            p.append(f'<text x="{x + cw / 2:.0f}" y="{y + 22:.0f}" '
                     f'font-size="12.5" font-weight="700" text-anchor="middle" '
                     f'fill="{"#fff" if n / peak > .5 else HUE[a]}">{n}</text>')
    p.append("</svg>")
    return "".join(p)


def block_svg(block, n_tables, upstream, downstream, screens, forms) -> str:
    """블록 하나의 입출력. 왼쪽이 재료, 가운데가 이 블록, 오른쪽이 소비처."""
    col = HUE[block]
    rows = max(len(upstream), len(downstream), 1)
    h = max(150, 46 + rows * 26)
    w = 900
    cx, bw = 330, 240
    p = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px" '
         f'role="img" aria-label="{E(block)} 블록 입출력">']
    p.append(f'<rect x="{cx}" y="24" width="{bw}" height="{h - 48}" rx="10" '
             f'fill="{col}" fill-opacity="0.13"/>')
    p.append(f'<rect x="{cx}" y="24" width="{bw}" height="4" rx="2" '
             f'fill="{col}"/>')
    p.append(f'<text x="{cx + bw / 2}" y="{h / 2 - 6}" font-size="16" '
             f'font-weight="700" fill="{col}" text-anchor="middle">'
             f'{E(block)}</text>')
    p.append(f'<text x="{cx + bw / 2}" y="{h / 2 + 16}" font-size="12.5" '
             f'fill="var(--muted)" text-anchor="middle">원장 {n_tables}장</text>')

    def side(items, x_text, x_edge, to_center, anchor):
        for k, (name, n) in enumerate(items):
            y = 46 + k * 26
            c2 = HUE.get(name, "#868e96")
            p.append(f'<text x="{x_text}" y="{y + 4}" font-size="12" '
                     f'fill="{c2}" text-anchor="{anchor}">{E(name)} '
                     f'<tspan fill="var(--muted)">{n}</tspan></text>')
            x1, x2 = (x_edge, to_center) if anchor == "end" else (to_center,
                                                                 x_edge)
            p.append(f'<path d="M{x1},{y} L{x2},{y}" stroke="{c2}" '
                     f'stroke-width="{min(4, 1 + n * 0.12):.1f}" '
                     f'stroke-opacity="0.55" marker-end="url(#a)"/>')

    side(upstream, cx - 40, cx - 34, cx - 2, "end")
    side(downstream, cx + bw + 40, cx + bw + 34, cx + bw + 2, "start")
    p.append(f'<text x="{cx + bw / 2}" y="{h - 12}" font-size="11.5" '
             f'fill="var(--muted)" text-anchor="middle">전용 화면 {screens}개 · '
             f'감독서식 모듈 {forms}개가 읽는다</text>')
    p.append("</svg>")
    return "".join(p)


# ------------------------------------------------------------------ 데이터

def nav_groups() -> list[tuple[str, list[str]]]:
    """app.py 의 NAVGROUPS 를 그대로 읽는다. 화면 묶음은 그것이 정본이다."""
    src = Path("risk_lib/ui_studio/app.py").read_text(encoding="utf-8")
    m = re.search(r"const NAVGROUPS=\[(.*?)\n\];", src, re.S)
    if not m:
        return []
    out: list[tuple[str, list[str]]] = []
    for gname, body in re.findall(r"\['([^']+)',\[(.*?)\]\],\n", m.group(1),
                                  re.S):
        out.append((gname, re.findall(r"'([^']+)'", body)))
    return out


def collect(with_rows: bool):
    from risk_lib.datamodel import lineage as L

    tables = None
    if with_rows:
        import warnings
        from risk_lib.data_gen import generate_portfolio
        from risk_lib.pipeline import run_pipeline
        from risk_lib.ui_studio.studio import build_studio
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pf = generate_portfolio(seed=42)
            res = run_pipeline(pf, seed=42, asof="2026-06-30")
            tables = build_studio(res, pf).tables
    lin = L.build_lineage(tables)
    blk = {s.name: L.block_of(s) for s in lin.specs}
    return lin, blk


# ------------------------------------------------------------------ 렌더

def render(lin, blk) -> str:
    counts = collections.Counter(blk.values())
    order = [b for b in BLOCK_ORDER if b in counts]
    flow = collections.Counter()
    for e in lin.edges:
        if e.kind in ("feeds", "fk") and e.src in blk and e.dst in blk:
            a, b = blk[e.src], blk[e.dst]
            if a != b:
                flow[(a, b)] += 1

    # 원장 → 그 원장을 그리는 전용 화면
    drawn: dict[str, list[str]] = {}
    for lab, s in lin.screens.items():
        if s["generic"]:
            continue
        for t in s["tables"]:
            drawn.setdefault(t, []).append(lab)
    # 원장 → 읽는 감독서식 모듈
    read: dict[str, list[str]] = {}
    for mod, ts in lin.forms.items():
        for t in ts:
            read.setdefault(t, []).append(mod)

    unwired, orphans = set(lin.unwired()), set(lin.orphans())
    spec_by = lin.spec_by_name
    P: list[str] = []

    # ---- 머리 ----
    P.append(f'''<header>
<h1>리스크관리 하네스 · 단위별 상세 흐름</h1>
<p class="lead">손으로 그리지 않았다. 블록·원장·화면·엣지·행수가 전부
<code>lineage.build_lineage()</code> 가 소스를 파싱해 읽어낸 값이다. 배선이
바뀌면 <code>tools/gen_flow_html.py</code> 를 다시 돌려 갱신한다.</p>
<div class="kpis">
{"".join(f'<div class="kpi"><b>{v}</b><span>{k}</span></div>' for k, v in [
    ("원장", len(lin.specs)), ("블록", len(order)),
    ("블록 간 엣지", sum(flow.values())),
    ("화면", len(lin.screens)),
    ("전용 화면", sum(1 for s in lin.screens.values() if not s["generic"])),
    ("감독서식 모듈", len(lin.forms)),
    ("미배선 원장", len(unwired)), ("고아 원장", len(orphans))])}
</div></header>''')

    # ---- 1. 블록 간 ----
    P.append('<section id="matrix"><h2>1. 블록 간 원장 흐름</h2>'
             '<p class="note">행이 재료, 열이 결과다. 칸의 숫자와 진하기가 '
             '<code>feeds</code>·<code>fk</code> 엣지 수이며, 회색 대각선은 '
             '블록 안쪽 흐름이라 세지 않는다.</p>'
             f'<div class="scroll">{matrix_svg(order, flow, counts)}</div>'
             '</section>')

    # ---- 2. 전체 흐름 ----
    # 행렬은 블록 단위라 어느 원장이 어느 단계를 지나는지 안 보인다. 이름만
    # 적은 상자로 기초데이터에서 업무보고서까지 한 줄로 편다.
    P.append('<section id="pipeline">'
             + pflow.section(lin, blk,
                          '<h2>2. 원장 흐름 (기초데이터 → 업무보고서)</h2>')
             + '</section>')

    # ---- 3. ERD ----
    # 위 행렬은 블록끼리 몇 개나 이어졌나만 센다. 어느 표의 어느 칸이 어느 표를
    # 가리키는지는 FK 를 상자와 화살표로 그려야 보이므로 gen_erd 가 그린다.
    P.append('<section id="erd"><h2>3. 원장 간 참조 (ERD)</h2>'
             + erd.lead(lin, blk) + erd.diagrams(lin, blk, tag="chip mono")
             + '</section>')

    # ---- 3. 블록별 ----
    P.append('<section id="blocks"><h2>4. 블록별 상세</h2>')
    for b in order:
        up = sorted(((a, n) for (a, t), n in flow.items() if t == b),
                    key=lambda kv: -kv[1])[:6]
        dn = sorted(((t, n) for (a, t), n in flow.items() if a == b),
                    key=lambda kv: -kv[1])[:6]
        names = sorted(n for n, x in blk.items() if x == b)
        scr = {s for n in names for s in drawn.get(n, [])}
        frm = {m for n in names for m in read.get(n, [])}
        P.append(f'<article class="blk" id="b-{_slug(b)}" '
                 f'style="--c:{HUE[b]}"><h3>{E(b)}</h3>')
        P.append(f'<div class="scroll">'
                 f'{block_svg(b, counts[b], up, dn, len(scr), len(frm))}</div>')
        P.append('<div class="scroll"><table><thead><tr><th>원장</th>'
                 '<th>한글명</th><th>grain</th><th class="n">실측 행수</th>'
                 '<th>생산 함수</th><th>그리는 화면</th><th>상태</th>'
                 '</tr></thead><tbody>')
        for n in names:
            sp = spec_by[n]
            prod = sorted(lin.producers.get(n, []))
            prod_s = "<br>".join(E(p.split("/")[-1]) for p in prod[:3]) or (
                '<span class="warn">생산 함수 없음</span>')
            sc = drawn.get(n, [])
            sc_s = ", ".join(E(x) for x in sorted(sc)[:4]) or (
                '<span class="warn">없음</span>')
            rows = lin.rows.get(n)
            state = ('<span class="bad">고아</span>' if n in orphans
                     else '<span class="warn">미배선</span>' if n in unwired
                     else '<span class="ok">배선</span>')
            P.append(f'<tr><td><code>{E(n)}</code></td><td>{E(sp.korean)}</td>'
                     f'<td class="s">{E(sp.grain)}</td>'
                     f'<td class="n">{"" if rows is None else f"{rows:,}"}</td>'
                     f'<td class="s">{prod_s}</td><td class="s">{sc_s}</td>'
                     f'<td>{state}</td></tr>')
        P.append("</tbody></table></div></article>")
    P.append("</section>")

    # ---- 3. 화면 ----
    groups = nav_groups()
    P.append('<section id="screens"><h2>5. 화면 그룹별 상세</h2>'
             '<p class="note">묶음은 <code>app.py</code> 의 '
             '<code>NAVGROUPS</code> 가 정본이다. 각 화면이 읽는 원장과 그 '
             '원장이 속한 블록을 함께 적는다.</p>')
    seen: set[str] = set()
    for gname, labels in groups:
        rows_html = []
        for lab in labels:
            s = lin.screens.get(lab)
            if not s:
                continue
            seen.add(lab)
            ts = sorted(s["tables"])
            chips = "".join(
                f'<span class="chip" style="--c:{HUE.get(blk.get(t), "#868e96")}">'
                f'{E(t)}</span>' for t in ts[:10])
            more = f' <span class="muted">외 {len(ts) - 10}장</span>' if len(
                ts) > 10 else ""
            rows_html.append(
                f'<tr><td>{E(lab)}</td><td class="s">{E(s["title"])}</td>'
                f'<td class="n">{len(ts)}</td><td>{chips}{more}</td></tr>')
        if not rows_html:
            continue
        P.append(f'<article class="grp"><h3>{E(gname)}</h3><div class="scroll">'
                 '<table><thead><tr><th>화면</th><th>제목</th>'
                 '<th class="n">원장</th><th>연결 원장</th></tr></thead><tbody>'
                 + "".join(rows_html) + "</tbody></table></div></article>")
    rest = sorted(set(lin.screens) - seen)
    if rest:
        P.append('<article class="grp"><h3>NAVGROUPS 밖</h3>'
                 '<p class="note">TABS 에는 있으나 내비 묶음에 없는 화면이다. '
                 '버튼이 만들어지지 않으므로 사람이 열 수 없다.</p><p>'
                 + ", ".join(f"<code>{E(x)}</code>" for x in rest)
                 + "</p></article>")
    P.append("</section>")

    # ---- 4. 감독서식 ----
    P.append('<section id="forms"><h2>6. 감독서식 모듈이 읽는 원장</h2>'
             '<div class="scroll"><table><thead><tr><th>모듈</th>'
             '<th class="n">원장</th><th>연결 원장</th></tr></thead><tbody>')
    for mod in sorted(lin.forms):
        ts = sorted(lin.forms[mod])
        chips = "".join(
            f'<span class="chip" style="--c:{HUE.get(blk.get(t), "#868e96")}">'
            f'{E(t)}</span>' for t in ts[:12])
        more = f' <span class="muted">외 {len(ts) - 12}장</span>' if len(
            ts) > 12 else ""
        P.append(f'<tr><td><code>{E(mod)}</code></td><td class="n">{len(ts)}'
                 f'</td><td>{chips}{more}</td></tr>')
    P.append("</tbody></table></div></section>")

    # ---- 5. 미배선 ----
    P.append('<section id="unwired"><h2>7. 미배선과 고아</h2>'
             '<p class="note">전용 화면도 감독서식도 읽지 않는 원장이 '
             f'<b>{len(unwired)}장</b>이고, 그중 하류 원장까지 없는 고아가 '
             f'<b>{len(orphans)}장</b>이다. 좋아 보이라고 빼지 않는다. '
             '흐름도의 쓸모는 무엇이 이어졌나보다 무엇이 끊겼나에 있다.</p>'
             '<div class="scroll"><table><thead><tr><th>원장</th><th>한글명</th>'
             '<th>블록</th><th>생산 함수</th><th>판정</th></tr></thead><tbody>')
    for n in sorted(unwired):
        sp = spec_by.get(n)
        prod = sorted(lin.producers.get(n, []))
        P.append(
            f'<tr><td><code>{E(n)}</code></td>'
            f'<td>{E(sp.korean if sp else "")}</td>'
            f'<td><span class="chip" style="--c:{HUE.get(blk.get(n), "#868e96")}">'
            f'{E(blk.get(n, ""))}</span></td>'
            f'<td class="s">{E(prod[0].split("/")[-1]) if prod else ""}</td>'
            f'<td>{"<span class=bad>고아</span>" if n in orphans else "<span class=warn>미배선</span>"}</td></tr>')
    P.append("</tbody></table></div></section>")
    return "\n".join(P)


CSS = """
:root{--bg:#f7f9fb;--panel:#fff;--line:#e3e8ee;--text:#1a2129;--muted:#6b7681;
--dim:#eef1f4;--dim2:#f8fafb;--ok:#177a52;--warn:#8a5a00;--bad:#c2255c;
--accent:#1c7ed6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#0d1218;--panel:#141c25;--line:#26313d;--text:#e8eef4;--muted:#8d9aa7;
--dim:#1b242e;--dim2:#121a22;--ok:#44d19d;--warn:#f6bb56;--bad:#fb6472;
--accent:#42a9ff}}
:root[data-theme="dark"]{--bg:#0d1218;--panel:#141c25;--line:#26313d;
--text:#e8eef4;--muted:#8d9aa7;--dim:#1b242e;--dim2:#121a22;--ok:#44d19d;
--warn:#f6bb56;--bad:#fb6472;--accent:#42a9ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.6 "Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",
ui-sans-serif,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1500px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:28px;margin:0 0 8px;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:20px;margin:0 0 6px;letter-spacing:-.005em}
h3{font-size:15.5px;margin:0 0 10px;color:var(--c,var(--text))}
.lead{color:var(--muted);margin:0 0 20px;max-width:78ch}
.note{color:var(--muted);margin:0 0 14px;max-width:88ch;font-size:13px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;
background:var(--dim);padding:1px 5px;border-radius:4px}
section{margin:34px 0}
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 6px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:11px 15px;min-width:112px}
.kpi b{display:block;font-size:21px;font-variant-numeric:tabular-nums;
letter-spacing:-.01em}
.kpi span{color:var(--muted);font-size:12px}
article{background:var(--panel);border:1px solid var(--line);border-radius:12px;
padding:16px 18px;margin:14px 0}
.blk{border-left:4px solid var(--c)}
.scroll{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;font-size:12.5px;min-width:760px}
th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:11.5px;white-space:nowrap;
position:sticky;top:0;background:var(--panel)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.s{color:var(--muted);font-size:11.5px}
.chip{display:inline-block;margin:1px 3px 1px 0;padding:1px 7px;
border-radius:20px;font-size:11px;background:color-mix(in srgb,var(--c) 15%,
transparent);color:var(--c);white-space:nowrap}
.tags{margin-top:10px;font-size:11.5px;color:var(--muted)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad);font-weight:700}
.muted{color:var(--muted)}
svg{display:block}
"""


def build(with_rows: bool = True) -> str:
    lin, blk = collect(with_rows)
    return f"""<title>리스크관리 하네스 흐름도</title>
<style>{CSS}{pflow.CSS}</style>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"
markerHeight="5" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="currentColor" fill-opacity=".55"/>
</marker></defs></svg>
<div class="wrap">{render(lin, blk)}</div>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/flow_detail.html")
    ap.add_argument("--no-rows", action="store_true",
                    help="파이프라인을 돌리지 않는다. 빠르지만 실측 행수가 빈다")
    a = ap.parse_args()
    doc = build(with_rows=not a.no_rows)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    print(f"작성 완료 {p} ({len(doc) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
