"""기초데이터에서 업무보고서까지, 원장 이름만으로 그리는 흐름도.

블록별 ERD 가 "어느 칸이 어느 표를 가리키나" 를 그린다면 이쪽은 "산출이 어느
단계를 지나 어디로 나가나" 를 그린다. 상자에는 표 이름만 적고, 컬럼은 이름을
눌렀을 때만 펼친다. 266장을 컬럼까지 펴서 한 장에 그리면 아무것도 안 읽힌다.

선의 근거는 세 가지이고 전부 소스에서 읽은 것이다.

    feeds·fk   원장 → 원장. 같은 함수가 A를 읽고 B를 쓰거나, B가 A를 FK 로
               가리킨다. 403건.
    produces   함수 → 원장. 그 원장을 실제로 만드는 함수다. 262장에 붙는다.
    reports    원장 → 감독서식 모듈. 서식이 그 원장을 읽는다. 129건.

엔진 마디를 넣는 이유가 있다. 자본·비율 단계로 들어오는 원장 간 엣지는 3건뿐이고
`rwa_market_component`·`rwa_operational_bi` 는 상류 원장이 아예 없다. 둘은
`materialize_rwa_detail` 이 `result.rwa["market_detail"]` 같은 엔진 객체에서
만들기 때문이다. 원장에서 원장으로 가는 선을 그으면 없는 선을 그리는 것이라,
그 자리에는 실제 생산 함수를 마디로 세운다.

    python tools/gen_pipeline_flow.py --out docs/pipeline_flow.html
"""

from __future__ import annotations

import argparse
import collections
import html
import json
from pathlib import Path

# 단계와 그 안의 묶음. 접두어로 가른다. 이것은 측정이 아니라 선언이며,
# 새 접두어가 생기면 어디에도 안 걸려 tests/test_pipeline_flow.py 가 운다.
STAGES: tuple[tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...]], ...] = (
    ("기초데이터·연계", "#4c6ef5", (
        ("수집·품질", ("int",)),
        ("보존·폐기", ("dat",)),
    )),
    ("RDM 원장", "#3b5bdb", (
        ("리스크데이터마트", ("rdm",)),
        ("거시지표", ("macro",)),
        ("집계", ("agg",)),
        ("국내 특화", ("kr",)),
    )),
    ("리스크 산출", "#1c7ed6", (
        ("신용", ("crm",)),
        ("충당금", ("ecl",)),
        ("시장·거래상대방", ("mkt", "ccr")),
        ("운영", ("opr",)),
        ("ALM·유동성", ("alm", "liq", "icaap")),
        ("위기상황", ("st",)),
        ("한도", ("lim",)),
    )),
    ("자본·비율", "#0ca678", (
        ("위험가중자산", ("rwa",)),
        ("자본", ("cap",)),
        ("건전성", ("pru", "ncr")),
    )),
    ("검증·거버넌스", "#c2255c", (
        ("통제·거버넌스", ("gov",)),
        ("검증", ("val",)),
        ("법규·인용", ("lex", "reg")),
        ("AI 거버넌스", ("aig", "agent")),
        ("변경·공시", ("chg", "disc")),
        ("화면", ("ui",)),
    )),
)
FORM_STAGE = ("업무보고서·감독서식", "#f08c00")

# 가장 긴 원장 이름(alm_early_redemption_observation)이 10.5px 모노스페이스로
# 202.3px 다. 안쪽 여백 14 를 더하고 8 을 남긴다. 폭이 모자라면 이름이 말줄임표로
# 잘리고, 잘린 이름은 다른 표와 구별되지 않는다.
BOX_W = 226
ROW_H = 21
GRP_H = 24          # 묶음 이름 줄
SUB_GAP = 16        # 같은 단계 안 접힌 열 사이
COL_GAP = 96        # 단계 사이
TARGET_H = 1000     # 이 높이를 넘으면 단계를 옆으로 접는다
PAD = 12


def E(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _assign(name: str) -> tuple[str, str] | None:
    """원장 이름 → (단계, 묶음). 접두어가 어디에도 없으면 None."""
    pre = name.split("_")[0]
    for stage, _hue, groups in STAGES:
        for grp, pres in groups:
            if pre in pres:
                return stage, grp
    return None


def layout(lin, blk):
    """상자 좌표. 단계가 열이고, 안에서 묶음 단위로 접는다.

    묶음을 쪼개 두 열에 걸치지 않는다. 쪼개면 같은 묶음이 두 군데 나타나고
    묶음 이름도 두 번 찍혀 어느 쪽이 진짜인지 알 수 없다.
    """
    members: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for s in lin.specs:
        a = _assign(s.name)
        if a:
            members[a].append(s.name)

    nodes: dict[str, tuple[float, float]] = {}
    cols: list[tuple[float, str, str]] = []      # x, 단계, 색
    x = float(PAD)
    for stage, hue, groups in STAGES:
        blocks = [(g, sorted(members[(stage, g)]))
                  for g, _ in groups if members[(stage, g)]]
        y, started = float(PAD), False
        for grp, names in blocks:
            need = GRP_H + len(names) * ROW_H
            if started and y + need > TARGET_H:   # 다음 열로 넘긴다
                x += BOX_W + SUB_GAP
                y = float(PAD)
            if not started or y == PAD:
                cols.append((x, stage, hue))
            started = True
            y += GRP_H
            for n in names:
                nodes[n] = (x, y)
                y += ROW_H
            y += 10
        x += BOX_W + COL_GAP

    # 마지막 열. 감독서식 모듈이며 원장이 아니다.
    form_x = x
    fy = float(PAD) + GRP_H
    forms: dict[str, tuple[float, float]] = {}
    for m in sorted(lin.forms):
        forms[m] = (form_x, fy)
        fy += ROW_H
    cols.append((form_x, FORM_STAGE[0], FORM_STAGE[1]))

    w = form_x + BOX_W + PAD
    h = max([y for _, y in nodes.values()] + [fy]) + ROW_H + PAD
    return members, nodes, forms, cols, w, h


def build(lin, blk) -> tuple[str, dict]:
    members, nodes, forms, cols, w, h = layout(lin, blk)
    stage_of = {n: _assign(n)[0] for n in nodes}
    order = [s for s, _, _ in STAGES] + [FORM_STAGE[0]]

    # ---- 선 ----
    edges: list[tuple[str, str, str]] = []
    for e in lin.edges:
        if e.kind in ("feeds", "fk") and e.src in nodes and e.dst in nodes:
            edges.append((e.src, e.dst, e.kind))
    for mod, ts in lin.forms.items():
        for t in ts:
            if t in nodes:
                edges.append((t, mod, "reports"))
    edges = sorted(set(edges))

    def sx(n):
        return nodes[n] if n in nodes else forms[n]

    def stg(n):
        return stage_of.get(n, FORM_STAGE[0])

    hues = {s_: h for s_, h, _ in STAGES}
    hues[FORM_STAGE[0]] = FORM_STAGE[1]

    def hue_of(s_):
        return hues[s_]

    back = sum(1 for a, b, _ in edges
               if order.index(stg(a)) > order.index(stg(b)))

    paths = []
    for i, (a, b, kind) in enumerate(edges):
        xa, ya = sx(a)
        xb, yb = sx(b)
        y1, y2 = ya + ROW_H / 2 - 4, yb + ROW_H / 2 - 4
        if xb > xa:
            x1, x2 = xa + BOX_W, xb
            c1, c2 = x1 + (x2 - x1) * .45, x2 - (x2 - x1) * .45
        else:                                    # 뒤로 도는 선. 왼쪽으로 돈다
            x1, x2 = xa, xb + BOX_W
            c1 = c2 = min(x1, x2) - 40
        rev = order.index(stg(a)) > order.index(stg(b))
        cls = "e back" if rev else "e"
        paths.append(
            f'<path id="e{i}" class="{cls} k-{kind}" '
            f'style="--c:{hue_of(stg(a))}" d="M{x1:.0f},{y1:.0f} '
            f'C{c1:.0f},{y1:.0f} {c2:.0f},{y2:.0f} {x2:.0f},{y2:.0f}"/>')

    # ---- 상자 ----
    idx = {n: i for i, n in enumerate(sorted(nodes) + sorted(forms))}
    boxes = []
    for stage, hue, groups in STAGES:
        for grp, _ in groups:
            ns = sorted(members[(stage, grp)])
            if not ns:
                continue
            gx, gy = nodes[ns[0]]
            boxes.append(
                f'<div class="grp" style="left:{gx:.0f}px;'
                f'top:{gy - GRP_H:.0f}px;--c:{hue}">{E(grp)} '
                f'<b>{len(ns)}</b></div>')
            for n in ns:
                nx, ny = nodes[n]
                boxes.append(
                    f'<button class="nd" id="n{idx[n]}" data-n="{E(n)}" '
                    f'style="left:{nx:.0f}px;top:{ny:.0f}px;--c:{hue}">'
                    f'{E(n)}</button>')
    fx = cols[-1][0]
    boxes.append(f'<div class="grp" style="left:{fx:.0f}px;top:{PAD}px;'
                 f'--c:{FORM_STAGE[1]}">감독서식 모듈 <b>{len(forms)}</b></div>')
    for m, (mx, my) in forms.items():
        boxes.append(
            f'<button class="nd form" id="n{idx[m]}" data-n="{E(m)}" '
            f'style="left:{mx:.0f}px;top:{my:.0f}px;--c:{FORM_STAGE[1]}">'
            f'{E(m)}</button>')

    # ---- 단계 머리 ----
    heads, seen = [], set()
    for cx, stage, hue in cols:
        if stage in seen:
            continue
        seen.add(stage)
        heads.append(f'<div class="hd" style="left:{cx:.0f}px;--c:{hue}">'
                     f'{E(stage)}</div>')

    # ---- 컬럼 자료. 이름을 눌렀을 때만 쓴다 ----
    spec_by = lin.spec_by_name
    cols_json = {}
    for n in nodes:
        sp = spec_by[n]
        pk = set(sp.primary_key or ())
        fk = {c for f in (sp.foreign_keys or ()) for c in f.columns}
        cols_json[n] = {
            "k": sp.korean,
            "c": [[c.name, c.dtype, c.korean or "",
                   "PK" if c.name in pk else ("FK" if c.name in fk else "")]
                  for c in sp.columns]}
    for m, ts in lin.forms.items():
        cols_json[m] = {"k": f"감독서식 모듈. 원장 {len(ts)}장을 읽는다",
                        "c": [[t, "", "", ""] for t in sorted(ts)]}

    data = {"cols": cols_json,
            "edges": [[idx[a], idx[b], k] for a, b, k in edges]}
    stats = {"tables": len(nodes), "forms": len(forms), "edges": len(edges),
             "back": back, "w": w, "h": h}
    body = (f'<div class="stagehd" style="height:26px">{"".join(heads)}</div>'
            f'<div class="cv" style="width:{w:.0f}px;height:{h:.0f}px">'
            f'<svg class="wires" width="{w:.0f}" height="{h:.0f}" '
            f'aria-hidden="true">{"".join(paths)}</svg>'
            f'{"".join(boxes)}</div>')
    return body, {"data": data, "stats": stats}


CSS = """
.pf{position:relative}
.pf .scroll{overflow-x:auto;max-width:100%;padding-bottom:8px}
.pf .stagehd{position:relative;margin-bottom:2px}
.pf .hd{position:absolute;top:0;font-size:12.5px;font-weight:700;color:var(--c);
white-space:nowrap}
.pf .cv{position:relative}
.pf .wires{position:absolute;inset:0;pointer-events:none}
.pf .e{fill:none;stroke:var(--c);stroke-width:1;stroke-opacity:.26}
.pf .e.back{stroke:var(--bad);stroke-opacity:.3;stroke-dasharray:3 3}
.pf.sel .e{stroke-opacity:.05}
.pf .e.on{stroke-opacity:.85;stroke-width:1.6}
.pf .grp{position:absolute;width:226px;font-size:10.5px;color:var(--c);
font-weight:700;letter-spacing:.02em}
.pf .grp b{color:var(--muted);font-weight:400}
.pf .nd{position:absolute;width:226px;height:19px;padding:0 7px;text-align:left;
font:10.5px/19px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--text);
background:var(--panel);border:1px solid var(--line);border-left:3px solid
var(--c);border-radius:4px;cursor:pointer;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.pf .nd.form{font-style:italic}
.pf .nd:hover{border-color:var(--c);background:var(--dim)}
.pf.sel .nd{opacity:.28}
.pf .nd.on{opacity:1;border-color:var(--c);box-shadow:0 0 0 2px
color-mix(in srgb,var(--c) 26%,transparent)}
.pf .nd.pick{opacity:1;background:var(--c);color:#fff;border-color:var(--c)}
.pf .drop{position:absolute;z-index:9;width:290px;max-height:340px;
overflow:auto;background:var(--panel);border:1px solid var(--c);
border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.22);padding:8px 10px}
.pf .drop h4{margin:0 0 2px;font-size:12px;font-family:ui-monospace,monospace}
.pf .drop p{margin:0 0 7px;font-size:11px;color:var(--muted)}
.pf .drop table{width:100%;border-collapse:collapse;font-size:11px;min-width:0}
.pf .drop td{padding:2px 4px;border-bottom:1px solid var(--line)}
.pf .drop td.m{width:22px;font-size:8.5px;font-weight:700;color:var(--c)}
.pf .drop td.t{color:var(--muted);font-size:10px;text-align:right}
.pf .drop code{background:none;padding:0;font-size:11px}
.pf .bar{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
font-size:11.5px;color:var(--muted);margin:0 0 10px}
.pf .lg{display:inline-flex;align-items:center;gap:5px}
.pf .lg i{width:20px;height:0;border-top:2px solid var(--muted);opacity:.5}
.pf .lg i.b{border-top-style:dashed;border-color:var(--bad)}
"""

JS = """
(function(){
 var root=document.getElementById('pf'); if(!root) return;
 var D=JSON.parse(document.getElementById('pf-data').textContent);
 var inc={},out={};
 D.edges.forEach(function(e,i){(out[e[0]]=out[e[0]]||[]).push([i,e[1]]);
   (inc[e[1]]=inc[e[1]]||[]).push([i,e[0]]);});
 var drop=null, cur=null;
 function clear(){root.classList.remove('sel');
   root.querySelectorAll('.on,.pick').forEach(function(x){
     x.classList.remove('on');x.classList.remove('pick');});
   if(drop){drop.remove();drop=null;} cur=null;}
 function show(btn){
  var id=+btn.id.slice(1), name=btn.dataset.n, d=D.cols[name];
  root.classList.add('sel'); btn.classList.add('pick');
  (out[id]||[]).concat(inc[id]||[]).forEach(function(p){
    var e=document.getElementById('e'+p[0]); if(e)e.classList.add('on');
    var n=document.getElementById('n'+p[1]); if(n)n.classList.add('on');});
  var rows=d.c.map(function(c){
    return '<tr><td class="m">'+c[3]+'</td><td><code>'+c[0]+'</code></td>'+
           '<td>'+c[2]+'</td><td class="t">'+c[1]+'</td></tr>';}).join('');
  drop=document.createElement('div'); drop.className='drop';
  /* 도화지 밖으로 나가면 잘려서 컬럼을 못 읽는다. 오른쪽·아래에서 뒤집는다. */
  var cv=btn.parentNode, DW=290, DH=Math.min(340,44+d.c.length*20);
  var L=parseFloat(btn.style.left)+8, T=parseFloat(btn.style.top)+22;
  if(L+DW>cv.offsetWidth) L=parseFloat(btn.style.left)+226-DW;
  if(T+DH>cv.offsetHeight) T=parseFloat(btn.style.top)-DH-2;
  drop.style.left=Math.max(0,L)+'px'; drop.style.top=Math.max(0,T)+'px';
  drop.style.setProperty('--c',getComputedStyle(btn).getPropertyValue('--c'));
  drop.innerHTML='<h4>'+name+'</h4><p>'+d.k+' · '+d.c.length+'칸 · '+
    ((out[id]||[]).length)+' 하류 · '+((inc[id]||[]).length)+' 상류</p>'+
    '<table>'+rows+'</table>';
  btn.parentNode.appendChild(drop);
 }
 root.addEventListener('click',function(ev){
  var b=ev.target.closest('.nd');
  if(!b){ if(!ev.target.closest('.drop')) clear(); return; }
  ev.stopPropagation();
  var same=(cur===b.id); clear(); if(same) return; cur=b.id; show(b);
 });
 document.addEventListener('click',function(ev){
  if(!ev.target.closest('#pf')) clear();});
 document.addEventListener('keydown',function(ev){
  if(ev.key==='Escape') clear();});
})();
"""


def section(lin, blk, heading: str = "") -> str:
    body, meta = build(lin, blk)
    s = meta["stats"]
    return (
        f'{heading}'
        f'<p class="note">상자는 원장 이름만 적는다. 이름을 누르면 그 원장의 '
        f'컬럼과 상하류 수가 펼쳐지고, 이어진 선과 원장만 남고 나머지는 흐려진다. '
        f'원장 {s["tables"]}장과 감독서식 모듈 {s["forms"]}개를 선 '
        f'{s["edges"]}개로 이었다. 그중 {s["back"]}개는 단계 순서를 거슬러 '
        f'되돌아가는 선이라 붉은 점선으로 둔다. 감추면 흐름이 한 방향으로만 '
        f'흐르는 것처럼 보인다.</p>'
        '<p class="note">자본·비율 단계로 들어오는 원장 간 선은 3개뿐이고 '
        '<code>rwa_market_component</code>·<code>rwa_operational_bi</code> 는 '
        '상류 원장이 하나도 없다. 둘은 <code>materialize_rwa_detail</code> 이 '
        '<code>result.rwa["market_detail"]</code> 같은 엔진 객체에서 만들기 '
        '때문이다. 원장에서 원장으로 가는 선을 그으면 없는 선을 그리는 것이라 '
        '긋지 않았다.</p>'
        f'<div class="pf" id="pf"><div class="bar">'
        f'<span class="lg"><i></i>원장 → 원장 (feeds·fk)</span>'
        f'<span class="lg"><i></i>원장 → 감독서식 (reports)</span>'
        f'<span class="lg"><i class="b"></i>되돌아가는 선 {s["back"]}</span>'
        f'<span>이름을 누르면 컬럼이 열린다. Esc 로 닫는다.</span></div>'
        f'<div class="scroll">{body}</div></div>'
        f'<script type="application/json" id="pf-data">'
        f'{json.dumps(meta["data"], ensure_ascii=False, separators=(",", ":"))}'
        f'</script><script>{JS}</script>')


def build_page() -> str:
    from risk_lib.datamodel import lineage as L

    lin = L.build_lineage()
    blk = {s.name: L.block_of(s) for s in lin.specs}
    base = """
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
.wrap{max-width:none;margin:0;padding:30px 20px 70px}
h1{font-size:26px;margin:0 0 10px}
.note{color:var(--muted);font-size:12.5px;margin:0 0 10px;max-width:92ch}
code{font-family:ui-monospace,monospace;font-size:12px;background:var(--dim);
padding:1px 5px;border-radius:4px}
"""
    return (f'<title>원장 흐름 · 기초데이터에서 업무보고서까지</title>'
            f'<style>{base}{CSS}</style><div class="wrap">'
            f'<h1>원장 흐름 · 기초데이터에서 업무보고서까지</h1>'
            f'{section(lin, blk)}</div>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/pipeline_flow.html")
    a = ap.parse_args()
    doc = build_page()
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    print(f"작성 완료 {p} ({len(doc) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
