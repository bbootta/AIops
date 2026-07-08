"""HTML report chrome: CSS, nav, page frame, table/KPI/badge helpers.

모든 보고서 페이지(핵심 + ops 심층)가 공유하는 표현 계층 기반.
NAV는 page_registry.PAGES에서 파생된다.
"""

from __future__ import annotations

import html
from datetime import date

from risk_lib.page_registry import nav_items


# ---------------------------------------------------------------- formatting

def _won(x: float) -> str:
    """Human-readable KRW magnitudes."""
    ax = abs(x)
    if ax >= 1e12: return f"{x/1e12:,.2f}조원"
    if ax >= 1e9:  return f"{x/1e9:,.1f}십억원"
    if ax >= 1e6:  return f"{x/1e6:,.0f}백만원"
    return f"{x:,.0f}원"


def _pct(x: float, places: int = 2) -> str:
    return f"{x*100:.{places}f}%"


def _esc(s) -> str:
    return html.escape(str(s))


# ---------------------------------------------------------------- HTML chrome

# Page set (filenames, labels, builders) lives in page_registry.PAGES —
# the single source of truth. NAV is derived: main-nav pages in render order.
NAV = nav_items()


ALM_SUB = [
    ("11a_irrbb.html", "IRRBB"),
    ("11b_lcr.html",   "LCR"),
    ("11c_nsfr.html",  "NSFR"),
]


CSS = """
:root {
  --bg:#f7f8fa; --card:#fff; --ink:#111827; --muted:#6b7280;
  --line:#e5e7eb; --accent:#2b6cb0; --good:#2e8540; --warn:#e8a33d; --bad:#c5221f;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family: 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  font-size:14px; line-height:1.55; }
.container { max-width:1180px; margin:0 auto; padding:24px 28px 80px; }
header.top { background:#1f2937; color:#f9fafb; padding:18px 28px; }
header.top .wrap { max-width:1180px; margin:0 auto;
  display:flex; align-items:baseline; justify-content:space-between; flex-wrap:wrap; gap:8px; }
header.top h1 { margin:0; font-size:18px; }
header.top .meta { font-size:12px; color:#d1d5db; }
nav.tabs { background:#fff; border-bottom:1px solid var(--line); padding:0 16px; }
nav.tabs .inner { max-width:1180px; margin:0 auto; display:flex; flex-wrap:wrap; gap:2px; }
nav.tabs a { padding:10px 12px; color:#374151; text-decoration:none;
  border-bottom:2px solid transparent; font-weight:500; font-size:13px; }
nav.tabs a:hover { color:var(--accent); }
nav.tabs a.active { color:var(--accent); border-bottom-color:var(--accent); }
nav.tabs a.sub { padding:8px 10px; font-size:12px; color:#6b7280; background:#f9fafb; }
nav.tabs a.sub.active { color:var(--accent); background:#eef4fb; border-bottom-color:transparent; }
h1.title { margin:18px 0 6px; font-size:22px; }
.section-lead { color:var(--muted); margin:0 0 18px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px;
  padding:18px 20px; margin:0 0 18px; box-shadow:0 1px 2px rgba(0,0,0,0.03); }
.card h2 { margin:0 0 12px; font-size:16px; border-bottom:1px solid var(--line);
  padding-bottom:8px; }
.card h3 { margin:14px 0 6px; font-size:14px; color:#1f2937; }
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:12px; margin:8px 0 16px; }
.kpi { background:#f9fafb; border:1px solid var(--line); border-radius:6px;
  padding:12px 14px; }
.kpi .lbl { font-size:11px; color:var(--muted); text-transform:uppercase;
  letter-spacing:.04em; }
.kpi .val { font-size:18px; font-weight:700; margin-top:4px; }
.kpi .sub { font-size:12px; color:var(--muted); margin-top:2px; }
.kpi.good .val { color:var(--good); }
.kpi.warn .val { color:var(--warn); }
.kpi.bad  .val { color:var(--bad); }
.badge { display:inline-block; padding:3px 9px; border-radius:11px; font-size:11px;
  font-weight:600; letter-spacing:.04em; }
.badge.PASS, .badge.GREEN { background:#d3eedd; color:#1f7437; }
.badge.WARN, .badge.AMBER { background:#fdebcb; color:#8a5b00; }
.badge.FAIL, .badge.RED   { background:#fbd7d5; color:#a3160d; }
.badge.NEUTRAL            { background:#e5e7eb; color:#374151; }
table.t { border-collapse:collapse; width:100%; font-size:13px; margin:8px 0 14px; }
table.t th, table.t td { border-bottom:1px solid var(--line); padding:6px 9px;
  text-align:left; vertical-align:top; }
table.t th { background:#f3f4f6; font-weight:600; font-size:12px;
  text-transform:uppercase; letter-spacing:.04em; color:#374151; }
table.t td.r, table.t th.r { text-align:right; font-variant-numeric:tabular-nums; }
.callout { background:#fffbea; border-left:3px solid var(--warn); padding:10px 14px;
  margin:8px 0; border-radius:0 6px 6px 0; }
.callout.good { background:#eef9f1; border-left-color:var(--good); }
.callout.bad  { background:#fdecea; border-left-color:var(--bad); }
.chart { margin:6px 0 10px; }
.row2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
@media (max-width:780px) { .row2 { grid-template-columns:1fr; } }
.linklist a { color:var(--accent); text-decoration:none; }
.linklist a:hover { text-decoration:underline; }
footer { text-align:center; color:var(--muted); font-size:12px; padding:20px 0 0; }
"""


def _nav_html(active: str, alm_active: bool = False) -> str:
    items = []
    for href, label in NAV:
        cls = " active" if href == active else ""
        items.append(f'<a class="{cls.strip()}" href="{href}">{_esc(label)}</a>')
    main_nav = "".join(items)
    sub = ""
    if alm_active or active in {h for h, _ in ALM_SUB}:
        sub_items = []
        for href, label in ALM_SUB:
            cls = " active" if href == active else ""
            sub_items.append(f'<a class="sub{cls}" href="{href}">{_esc(label)}</a>')
        sub = '<div class="inner" style="border-top:1px solid var(--line)">' + \
              "".join(sub_items) + '</div>'
    return f'<nav class="tabs"><div class="inner">{main_nav}</div>{sub}</nav>'


def _page(title: str, body: str, active: str, *, meta_line: str = "",
          alm_active: bool = False) -> str:
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>{_esc(title)}</title>
<style>{CSS}</style></head>
<body>
<header class="top"><div class="wrap">
<h1>리스크관리 통합 보고서 — {_esc(title)}</h1>
<div class="meta">{_esc(meta_line)}</div>
</div></header>
{_nav_html(active, alm_active=alm_active)}
<div class="container">{body}</div>
<footer>risk_lib v0.3 · 산출 기준일 {date.today().isoformat()}</footer>
</body></html>"""


# ---------------------------------------------------------------- table helper

def _table(headers, rows, *, right_cols: list[int] | None = None) -> str:
    right_cols = set(right_cols or [])
    th = "".join(f'<th class="r">{_esc(h)}</th>' if i in right_cols
                 else f'<th>{_esc(h)}</th>' for i, h in enumerate(headers))
    body = []
    for row in rows:
        cells = []
        for i, v in enumerate(row):
            cls = " class=\"r\"" if i in right_cols else ""
            cells.append(f"<td{cls}>{v if isinstance(v, str) and ('<' in v) else _esc(v)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="t"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _kpi(lbl: str, val: str, *, sub: str = "", tone: str = "") -> str:
    cls = f" {tone}" if tone else ""
    sub_html = f'<div class="sub">{_esc(sub)}</div>' if sub else ""
    return (f'<div class="kpi{cls}"><div class="lbl">{_esc(lbl)}</div>'
            f'<div class="val">{_esc(val)}</div>{sub_html}</div>')


def _badge(text: str, tone: str) -> str:
    return f'<span class="badge {tone}">{_esc(text)}</span>'
