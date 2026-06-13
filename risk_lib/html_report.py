"""HTML report system: 1 executive summary + N deep-dive sections, all linked.

`build_report_set(result, out_dir)` writes a coherent set of HTML files:
  index.html              — executive summary with links into each section
  01_portfolio.html       — portfolio composition
  02_pd.html              — PD model discrimination & calibration
  03_rwa.html             — RWA composition + output floor
  04_capital.html         — BIS + leverage
  05_ecl.html             — IFRS9 ECL (TTC/PIT/path)
  06_monitoring.html      — delinquency / default / recovery
  07_limits.html          — limits + concentration
  08_rapm.html            — RAPM
  09_stress.html          — stress + reverse + quarterly path
  10_icaap.html           — internal capital (Pillar 2)
  11_alm.html             — ALM hub
  11a_irrbb.html          — IRRBB (ΔEVE/ΔNII, six scenarios)
  11b_lcr.html            — LCR (HQLA caps, run-off)
  11c_nsfr.html           — NSFR (ASF/RSF)
  12_validation.html      — self-verification + references

Each page shares the same chrome (CSS + nav) and embeds inline SVG charts so
nothing depends on external assets — open `index.html` directly or attach the
whole directory to an email.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib.references import (
    ALL_CITATIONS, BIS_MIN_CET1, BIS_MIN_TIER1, BIS_MIN_TOTAL,
    CAPITAL_CONSERVATION_BUFFER, LEVERAGE_MIN_RATIO,
    LCR_MIN, NSFR_MIN, IRRBB_OUTLIER_EVE_PCT_TIER1,
    GINI_MIN_GOOD, HHI_HIGH,
)
from risk_lib import viz


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

# Files in render order; links in nav appear in this sequence.
NAV = [
    ("index.html",        "0. 요약"),
    ("01_portfolio.html", "1. 포트폴리오"),
    ("02_pd.html",        "2. PD모형"),
    ("03_rwa.html",       "3. RWA"),
    ("04_capital.html",   "4. BIS·레버리지"),
    ("05_ecl.html",       "5. ECL"),
    ("06_monitoring.html","6. 모니터링"),
    ("07_limits.html",    "7. 한도"),
    ("08_rapm.html",      "8. RAPM"),
    ("09_stress.html",    "9. 스트레스"),
    ("10_icaap.html",     "10. 내부자본"),
    ("11_alm.html",       "11. ALM"),
    ("12_validation.html","12. 검증"),
    ("13_climate.html",   "13. 기후"),
    ("14_ccr.html",       "14. CCR/CVA"),
    ("15_op_loss.html",   "15. 운영손실"),
    ("16_sensitivity.html","16. 민감도"),
    ("17_model_risk.html","17. 모형"),
    ("18_concentration_deep.html","18. 집중 D-D"),
    ("19_raf.html",       "19. RAF"),
    ("20_pillar3.html",   "20. Pillar 3"),
    ("21_mda.html",       "21. MDA"),
    ("22_kri_trends.html","22. KRI 트렌드"),
    ("23_attribution.html","23. 귀속분석"),
    ("24_vintage.html",   "24. Vintage"),
    ("25_data_quality.html","25. DQ·정합성"),
]
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


# ============================================================================
# Page renderers
# ============================================================================


def _page_summary(r: PipelineResult) -> str:
    v = r.validation
    summ = v.summary()
    passes = v.passes()
    verdict_tone = "PASS" if passes else "FAIL"
    verdict_text = "결재 가능 (PASS)" if passes else "결재 불가 (FAIL)"
    bis = r.bis; lev = r.leverage
    alm = r.alm; ic = r.icaap

    # KPI ribbon
    bis_tone = "good" if bis.passes() else "bad"
    lev_tone = "good" if lev.passes() else "bad"
    lcr = alm["lcr"]; nsfr = alm["nsfr"]; irrbb = alm["irrbb"]
    lcr_tone  = "good" if lcr.passes() else "bad"
    nsfr_tone = "good" if nsfr.passes() else "bad"
    irrbb_tone = "good" if not irrbb.outlier() else ("warn" if irrbb.early_warning() else "bad")
    icaap_tone = {"GREEN":"good","AMBER":"warn","RED":"bad"}[ic.grade]

    kpis = "".join([
        _kpi("종합 판정", verdict_text,
             sub=f"PASS {summ.get('PASS',0)} / WARN {summ.get('WARN',0)} / FAIL {summ.get('FAIL',0)}",
             tone=("good" if passes else "bad")),
        _kpi("CET1 비율", _pct(bis.cet1_ratio),
             sub=f"요구 {_pct(bis.required['cet1'])} · 잉여 {bis.surplus_shortfall['cet1']*100:+.2f}%p",
             tone=bis_tone),
        _kpi("레버리지 비율", _pct(lev.leverage_ratio),
             sub=f"요구 {_pct(LEVERAGE_MIN_RATIO)}",
             tone=lev_tone),
        _kpi("LCR", _pct(lcr.lcr, 1),
             sub=f"기준 {_pct(LCR_MIN, 0)}", tone=lcr_tone),
        _kpi("NSFR", _pct(nsfr.nsfr, 1),
             sub=f"기준 {_pct(NSFR_MIN, 0)}", tone=nsfr_tone),
        _kpi("IRRBB ΔEVE / Tier1", _pct(irrbb.worst_pct_tier1),
             sub=f"기준 ≤{_pct(IRRBB_OUTLIER_EVE_PCT_TIER1, 0)} · {irrbb.worst_eve_scenario}",
             tone=irrbb_tone),
        _kpi("ICAAP 사용률", _pct(ic.utilisation, 1),
             sub=f"{ic.grade} · 잉여 {_won(ic.buffer)}",
             tone=icaap_tone),
        _kpi("최종 RWA", _won(r.rwa["final_total"]),
             sub="output floor " + ("구속적" if r.rwa["output_floor"].is_binding else "비구속"),
             tone=""),
    ])

    # Section deep-link cards
    deep_links = [
        ("01_portfolio.html", "1. 포트폴리오 개요",
         f"{int(r.portfolio_summary['n'].sum()):,}건 · EAD {_won(r.portfolio_summary['ead'].sum())}"),
        ("02_pd.html", "2. PD모형 변별력·캘리브레이션",
         f"세그먼트 {len(r.pd_metrics)} · HL p={r.backtest['hosmer_lemeshow']['p_value']:.3f}"),
        ("03_rwa.html", "3. RWA 구성 & output floor",
         f"SA {_won(r.rwa['sa'])} · IRB {_won(r.rwa['irb'])} · Mkt {_won(r.rwa['market'])} · Op {_won(r.rwa['op'])}"),
        ("04_capital.html", "4. BIS·레버리지",
         f"CET1 {_pct(bis.cet1_ratio)} · Tier1 {_pct(bis.tier1_ratio)} · Total {_pct(bis.total_ratio)}"),
        ("05_ecl.html", "5. IFRS9 ECL — TTC + PIT 경로",
         f"TTC {_won(r.ecl['total'])} · PIT 가중 {_won(r.macro_ecl.weighted_total)}"),
        ("06_monitoring.html", "6. 연체율 · 부도율 · 회수율",
         f"부도율(EW) {_pct(r.monitoring['default_rate_ew'])} · 회수율 {_pct(r.monitoring['recovery_rate'])}"),
        ("07_limits.html", "7. 한도 · 집중리스크",
         f"경보 {len(r.limits)}건 · sector HHI {r.concentration[r.concentration['dimension']=='sector']['hhi'].iloc[0]:.3f}"),
        ("08_rapm.html", "8. RAPM (RAROC)",
         f"자산군 {len(r.rapm)} · hurdle {_pct(r.meta['hurdle_rate'])}"),
        ("09_stress.html", "9. 스트레스 (정방향·역방향·분기 경로)",
         f"역스트레스 임계심도 s={r.reverse_stress.critical_severity:.2f}"),
        ("10_icaap.html", "10. 내부자본 (ICAAP) — Pillar 2",
         f"통합 EC {_won(ic.ec_diversified)} · 가용 {_won(ic.available_capital)} · {ic.grade}"),
        ("11_alm.html", "11. ALM (IRRBB / LCR / NSFR)",
         f"LCR {_pct(lcr.lcr,1)} · NSFR {_pct(nsfr.nsfr,1)} · IRRBB worst {_pct(irrbb.worst_pct_tier1)}"),
        ("12_validation.html", "12. 자체검증 + 출처",
         f"{summ.get('PASS',0)} PASS / {summ.get('WARN',0)} WARN / {summ.get('FAIL',0)} FAIL"),
    ]
    card_html = ['<div class="card"><h2>부문별 상세 보고서</h2><div class="linklist">']
    for href, name, sub in deep_links:
        card_html.append(
            f'<div style="padding:6px 0;border-bottom:1px solid var(--line)">'
            f'<a href="{href}"><b>{_esc(name)}</b></a>'
            f'<div style="font-size:12px;color:var(--muted)">{_esc(sub)}</div></div>')
    card_html.append("</div></div>")

    # Headline charts
    bis_chart = viz.bar_chart(
        ["CET1", "Tier1", "Total"],
        [bis.cet1_ratio, bis.tier1_ratio, bis.total_ratio],
        value_fmt=_pct, title="BIS 자본비율 vs 규제최저",
        reference_value=bis.required["cet1"],
        reference_label=f"CET1 요구 {_pct(bis.required['cet1'])}",
        colors=[viz.GREEN if bis.cet1_ratio >= bis.required["cet1"] else viz.RED,
                viz.PALETTE[0], viz.PALETTE[2]],
    )
    rwa_donut = viz.donut_chart(
        ["신용 IRB","신용 SA","시장","운영"],
        [r.rwa["irb"], r.rwa["sa"], r.rwa["market"], r.rwa["op"]],
        title="RWA 구성", center_label=f"{r.rwa['final_total']/1e12:,.0f}\n조원",
    )
    alm_chart = viz.bar_chart(
        ["LCR","NSFR","CET1","Leverage"],
        [lcr.lcr, nsfr.nsfr, bis.cet1_ratio, lev.leverage_ratio],
        value_fmt=_pct, title="핵심 건전성 지표",
        colors=[
            viz.GREEN if lcr.passes()  else viz.RED,
            viz.GREEN if nsfr.passes() else viz.RED,
            viz.GREEN if bis.passes()  else viz.RED,
            viz.GREEN if lev.passes()  else viz.RED,
        ],
    )

    summary_body = f"""
<h1 class="title">0. 종합 판정 — {_badge(verdict_tone, verdict_tone)}</h1>
<p class="section-lead">시드 {r.meta.get('seed')} 기준 합성 포트폴리오, 전 부문 산출 결과 요약.
각 카드 클릭 시 부문별 상세 보고서로 이동합니다.</p>
<div class="card"><h2>핵심 지표</h2>
<div class="kpi-grid">{kpis}</div></div>

<div class="row2">
<div class="card"><h2>BIS 자본비율</h2><div class="chart">{bis_chart}</div></div>
<div class="card"><h2>RWA 구성</h2><div class="chart">{rwa_donut}</div></div>
</div>

<div class="card"><h2>건전성 종합 (자본 + 유동성)</h2><div class="chart">{alm_chart}</div>
<p class="section-lead" style="margin-top:6px">
LCR · NSFR 100% 기준, CET1 · Leverage는 규제 최저 + 자본보전버퍼 기준. 모두 충족 시 결재 가능 판정.</p>
</div>

{"".join(card_html)}

<div class="card"><h2>주의 / 위반 사항</h2>
{"".join(f'<div class="callout {("bad" if c.status=="FAIL" else "")}">' + _esc(f"[{c.status}] {c.name}: {c.detail}") + '</div>'
         for c in v.checks if c.status != "PASS") or '<div class="callout good">자체검증 전 항목 통과</div>'}
</div>
"""
    meta = (f"산출 시드 {r.meta.get('seed')} · 포트폴리오 {int(r.portfolio_summary['n'].sum()):,}건 · "
            f"준거 Basel III + 금감원 감독세칙")
    return _page("요약", summary_body, "index.html", meta_line=meta)


def _page_portfolio(r: PipelineResult) -> str:
    ps = r.portfolio_summary.copy()
    ps["share"] = ps["ead"] / ps["ead"].sum()
    by_ead = viz.donut_chart(
        ps["asset_class"].tolist(), ps["ead"].tolist(),
        title="EAD 자산군 구성", center_label=f"{ps['ead'].sum()/1e12:,.0f}\n조원",
    )
    by_dr = viz.bar_chart(
        ps["asset_class"].tolist(), ps["default_rate"].tolist(),
        value_fmt=_pct, title="자산군별 12개월 부도율",
        colors=[viz.PALETTE[i] for i in range(len(ps))],
    )
    rows = [[row["asset_class"], f"{int(row['n']):,}",
             _won(row["ead"]), _pct(row["share"]),
             _pct(row["default_rate"])] for _, row in ps.iterrows()]
    body = f"""
<h1 class="title">1. 포트폴리오 개요</h1>
<p class="section-lead">합성 obligor-level 데이터의 자산군별 익스포저, 비중, 실현 부도율.</p>
<div class="row2">
<div class="card"><div class="chart">{by_ead}</div></div>
<div class="card"><div class="chart">{by_dr}</div></div>
</div>
<div class="card"><h2>자산군별 요약</h2>
{_table(["자산군","건수","EAD","비중","12M 부도율"], rows, right_cols=[1,2,3,4])}
<p class="section-lead">
부도율은 실현 default_12m 평균. 합성 데이터이므로 자산군 간 비중·부도율은 시드(=42)와 데이터 생성기 모수에 의해 결정.</p>
</div>
"""
    return _page("포트폴리오", body, "01_portfolio.html")


def _page_pd(r: PipelineResult) -> str:
    pm = r.pd_metrics
    segs = list(pm.keys())
    gini = [pm[s]["gini"] for s in segs]
    ks = [pm[s]["ks"] for s in segs]
    chart = viz.bar_chart(segs, gini, value_fmt=lambda v: f"{v:.3f}",
                          title="세그먼트별 Gini 변별력",
                          reference_value=GINI_MIN_GOOD,
                          reference_label=f"양호 기준 {GINI_MIN_GOOD:.2f}",
                          colors=[viz.GREEN if g >= GINI_MIN_GOOD else viz.AMBER for g in gini])
    bt = r.backtest
    hl = bt["hosmer_lemeshow"]
    pg = bt["per_grade"].copy()
    zone_counts = pg["zone"].value_counts().to_dict()
    zones_chart = viz.bar_chart(
        list(zone_counts.keys()), list(zone_counts.values()),
        value_fmt=lambda v: f"{int(v)}",
        title="등급별 백테스트 존",
        colors=[{"GREEN":viz.GREEN,"YELLOW":viz.AMBER,"RED":viz.RED}.get(z, viz.PALETTE[0])
                for z in zone_counts.keys()],
    )

    rows = [[s, f"{pm[s]['gini']:.3f}", f"{pm[s]['ks']:.3f}",
             f"{int(pm[s]['n_train']):,}/{int(pm[s]['n_test']):,}"] for s in segs]
    pg_rows = []
    for _, row in pg.iterrows():
        pg_rows.append([row.get("grade", "-"),
                        f"{int(row.get('n', 0)):,}",
                        f"{row.get('mean_pd', 0):.4f}",
                        f"{row.get('default_rate', 0):.4f}",
                        _badge(row["zone"], {"GREEN":"GREEN","YELLOW":"WARN","RED":"FAIL"}.get(row["zone"], "NEUTRAL"))])

    body = f"""
<h1 class="title">2. 신용평가모형(PD) 변별력 & 캘리브레이션</h1>
<p class="section-lead">세그먼트별 Gini/KS, Hosmer-Lemeshow, 등급별 신호등 백테스트.</p>
<div class="row2">
<div class="card"><h2>세그먼트별 변별력</h2><div class="chart">{chart}</div>
{_table(["세그먼트","Gini","KS","학습/검증"], rows, right_cols=[1,2,3])}
</div>
<div class="card"><h2>백테스트 존 (전체 등급)</h2><div class="chart">{zones_chart}</div>
<p class="section-lead">RED 0건이어야 결재 가능. YELLOW 잔존 시 WARN.</p>
</div>
</div>
<div class="card"><h2>Hosmer-Lemeshow 캘리브레이션</h2>
<div class="kpi-grid">
{_kpi("χ²", f"{hl['chi_square']:.2f}")}
{_kpi("p-value", f"{hl['p_value']:.3f}",
       tone=("good" if hl['p_value'] >= 0.05 else "warn"))}
{_kpi("판정", "양호" if hl['p_value']>=0.05 else "주의",
       sub="p ≥ 0.05 시 캘리브레이션 양호")}
</div>
</div>
<div class="card"><h2>등급별 백테스트 (코퍼레이트)</h2>
{_table(["등급","건수","평균 PD","실현 부도율","존"], pg_rows, right_cols=[1,2,3])}
</div>
"""
    return _page("PD모형", body, "02_pd.html")


def _page_rwa(r: PipelineResult) -> str:
    rwa = r.rwa; of = rwa["output_floor"]
    composition = viz.donut_chart(
        ["신용 IRB","신용 SA","시장","운영"],
        [rwa["irb"], rwa["sa"], rwa["market"], rwa["op"]],
        title="최종 RWA 구성", center_label=f"{rwa['final_total']/1e12:,.0f}\n조원",
    )
    cmp_chart = viz.bar_chart(
        ["내부모형 합계", "전부표준방법", "Output floor 적용"],
        [rwa["internal_total"], rwa["standardised_total"], of.floor_amount],
        title="내부모형 vs 표준방법 (output floor)",
        reference_value=rwa["final_total"], reference_label="최종 RWA",
        colors=[viz.PALETTE[0], viz.PALETTE[1], viz.PALETTE[2]],
    )
    floor_text = (
        "Output floor가 <b>구속적</b>으로 적용되어 내부모형 대비 "
        f"+{_won(of.add_on)} 가산됩니다."
        if of.is_binding else
        "Output floor는 <b>비구속적</b>이며, 내부모형 RWA가 표준방법의 72.5%를 상회합니다."
    )
    rows = [
        ["신용 RWA — SA", _won(rwa["sa"])],
        ["신용 RWA — IRB", _won(rwa["irb"])],
        ["시장리스크 RWA", _won(rwa["market"])],
        ["운영리스크 RWA", _won(rwa["op"])],
        ["내부모형 합계", _won(rwa["internal_total"])],
        ["전부표준방법 합계 (output floor 분모)", _won(rwa["standardised_total"])],
        [f"Output floor ({of.floor:.1%}) 적용액", _won(of.floor_amount)],
        ["<b>최종 RWA</b>", f"<b>{_won(rwa['final_total'])}</b>"],
    ]
    body = f"""
<h1 class="title">3. 위험가중자산(RWA) — Pillar 1</h1>
<p class="section-lead">신용·시장·운영 RWA, 표준방법 산출액, output floor 적용 결과.</p>
<div class="row2">
<div class="card"><div class="chart">{composition}</div></div>
<div class="card"><div class="chart">{cmp_chart}</div>
<div class="callout">{floor_text}</div></div>
</div>
<div class="card"><h2>구성 상세</h2>{_table(["구분","금액"], rows, right_cols=[1])}</div>
"""
    return _page("RWA", body, "03_rwa.html")


def _page_capital(r: PipelineResult) -> str:
    bis = r.bis; lev = r.leverage
    cet1_chart = viz.bar_chart(
        ["CET1","Tier1","Total"],
        [bis.cet1_ratio, bis.tier1_ratio, bis.total_ratio],
        value_fmt=_pct, title="BIS 비율 vs 요구치",
        reference_value=bis.required["total"],
        reference_label=f"Total 요구 {_pct(bis.required['total'])}",
        colors=[viz.GREEN if (bis.cet1_ratio>=bis.required['cet1']) else viz.RED,
                viz.PALETTE[0], viz.PALETTE[2]],
    )
    surplus = [bis.surplus_shortfall[k] for k in ("cet1","tier1","total")]
    surplus_chart = viz.bar_chart(
        ["CET1 잉여","Tier1 잉여","Total 잉여"], surplus,
        value_fmt=lambda v: f"{v*100:+.2f}%p", title="규제 대비 잉여/부족",
        colors=[viz.GREEN if v >= 0 else viz.RED for v in surplus],
    )
    rows = []
    for key, label in [("cet1","CET1 (보통주자본)"), ("tier1","Tier1 (기본자본)"), ("total","Total (총자본)")]:
        actual = getattr(bis, f"{key}_ratio")
        rows.append([label, _pct(actual), _pct(bis.required[key]),
                     f"{bis.surplus_shortfall[key]*100:+.2f}%p"])
    lev_chart = viz.bar_chart(
        ["레버리지 비율"], [lev.leverage_ratio], value_fmt=_pct,
        title="레버리지 비율", reference_value=LEVERAGE_MIN_RATIO,
        reference_label=f"최저 {_pct(LEVERAGE_MIN_RATIO)}",
        colors=[viz.GREEN if lev.passes() else viz.RED],
    )
    body = f"""
<h1 class="title">4. BIS 자본적정성 & 레버리지</h1>
<p class="section-lead">Basel III CRE10.4 + RBC20.1 (자본보전버퍼 2.5%) 기준 비교.</p>
<div class="row2">
<div class="card"><h2>BIS 비율</h2><div class="chart">{cet1_chart}</div>
{_table(["비율","실측","요구","잉여/부족"], rows, right_cols=[1,2,3])}
판정: {_badge("PASS" if bis.passes() else "FAIL", "PASS" if bis.passes() else "FAIL")}
</div>
<div class="card"><h2>잉여 자본</h2><div class="chart">{surplus_chart}</div></div>
</div>
<div class="card"><h2>레버리지 비율 (LEV10.6)</h2>
<div class="chart">{lev_chart}</div>
<div class="kpi-grid">
{_kpi("레버리지 비율", _pct(lev.leverage_ratio),
       sub=f"요구 {_pct(LEVERAGE_MIN_RATIO)}",
       tone="good" if lev.passes() else "bad")}
{_kpi("익스포저 측정치", _won(lev.exposure_measure))}
{_kpi("Tier1", _won(r.meta['capital'].tier1))}
</div>
</div>
"""
    return _page("BIS·레버리지", body, "04_capital.html")


def _page_ecl(r: PipelineResult) -> str:
    by_stage = r.ecl["by_stage"]
    stages = [f"Stage {int(s)}" for s in by_stage.index]
    ecl_vals = by_stage["ecl"].tolist()
    coverage = by_stage["coverage"].tolist()
    stage_chart = viz.bar_chart(stages, ecl_vals, title="Stage별 ECL")
    cov_chart = viz.bar_chart(stages, coverage, value_fmt=_pct,
                              title="Stage별 커버리지율 (ECL/EAD)")

    macro = r.macro_ecl
    macro_rows = [[row["scenario"], _pct(row["probability"], 0), _won(row["ecl"])]
                  for _, row in macro.by_scenario.iterrows()]
    macro_chart = viz.bar_chart(
        macro.by_scenario["scenario"].tolist(),
        macro.by_scenario["ecl"].tolist(),
        title="시나리오별 PIT ECL",
        colors=[viz.PALETTE[0], viz.AMBER, viz.RED],
    )

    qs = r.meta["quarters"]
    mp = r.macro_ecl_path
    series_q = {}
    for name in ["baseline", "downside", "severe", "weighted"]:
        g = mp[mp["scenario"] == name].sort_values("q_index")
        if not g.empty:
            series_q[("확률가중" if name == "weighted" else name)] = g["ecl"].tolist()
    path_chart = viz.line_chart(
        qs, series_q, value_fmt=lambda v: f"{v/1e9:,.0f}십억",
        title="분기별 ECL 충당금 경로",
    )

    stage_rows = [[f"Stage {int(s)}", f"{int(row['n']):,}",
                   _won(row["ead"]), _won(row["ecl"]), _pct(row["coverage"])]
                  for s, row in by_stage.iterrows()]
    body = f"""
<h1 class="title">5. IFRS9 기대신용손실(ECL) 충당금</h1>
<p class="section-lead">시점추정(TTC) + 거시연계 PIT(확률가중) + 분기별 충당금 경로.</p>
<div class="kpi-grid">
{_kpi("TTC ECL", _won(r.ecl['total']))}
{_kpi("PIT 확률가중 ECL", _won(macro.weighted_total),
       sub=f"forward-looking uplift {(macro.weighted_total - r.ecl['total'])/1e9:+,.0f}십억", tone="warn")}
{_kpi("Stage 3 커버리지",
       f"{by_stage.loc[3, 'coverage']:.1%}" if 3 in by_stage.index else "—")}
</div>
<div class="row2">
<div class="card"><h2>Stage별 ECL</h2><div class="chart">{stage_chart}</div>
{_table(["Stage","건수","EAD","ECL","커버리지"], stage_rows, right_cols=[1,2,3,4])}
</div>
<div class="card"><h2>Stage별 커버리지</h2><div class="chart">{cov_chart}</div></div>
</div>
<div class="card"><h2>거시연계 PIT 시나리오</h2>
<div class="row2">
<div><div class="chart">{macro_chart}</div></div>
<div>{_table(["시나리오","확률","ECL"], macro_rows, right_cols=[1,2])}</div>
</div>
</div>
<div class="card"><h2>분기별 ECL 충당금 경로 (IFRS9 forward-looking)</h2>
<div class="chart">{path_chart}</div></div>
"""
    return _page("ECL", body, "05_ecl.html")


def _page_monitoring(r: PipelineResult) -> str:
    m = r.monitoring
    delq = m["delinquency"]
    body = f"""
<h1 class="title">6. 연체율 / 부도율 / 회수율</h1>
<p class="section-lead">DPD 버킷, 12M 부도율(가중·건수), 워크아웃 누적 회수율.</p>
<div class="kpi-grid">
{_kpi("부도율 (노출액 가중)", _pct(m['default_rate_ew']))}
{_kpi("부도율 (건수)", _pct(m['default_rate_count']))}
{_kpi("누적 회수율 (LGD = 1 − 회수율)", _pct(m['recovery_rate']))}
</div>
<div class="card"><h2>자산군별 연체 분포</h2>
{_table(list(delq.columns),
        [[(_won(v) if isinstance(v, (int, float)) and abs(v) > 1e5 else _esc(v)) for v in row]
         for row in delq.to_numpy().tolist()],
        right_cols=list(range(1, len(delq.columns))))}
</div>
"""
    return _page("모니터링", body, "06_monitoring.html")


def _page_limits(r: PipelineResult) -> str:
    limits = r.limits.copy() if r.limits is not None else pd.DataFrame()
    conc = r.concentration

    conc_chart = viz.bar_chart(
        conc["dimension"].tolist(), conc["hhi"].tolist(),
        value_fmt=lambda v: f"{v:.3f}",
        title="차원별 HHI",
        reference_value=HHI_HIGH, reference_label=f"고집중 기준 {HHI_HIGH:.2f}",
        colors=[viz.RED if v >= HHI_HIGH else (viz.AMBER if v >= 0.10 else viz.GREEN)
                for v in conc["hhi"]],
    )
    top_lim = limits.head(15)
    if not top_lim.empty:
        util_chart = viz.horizontal_bar(
            [f"{row['dimension']}:{row['bucket']}" for _, row in top_lim.iterrows()],
            top_lim["utilisation"].tolist(),
            value_fmt=_pct, title="한도 사용률 상위 15", color=viz.RED,
            reference_value=1.0, reference_label="100%",
        )
    else:
        util_chart = "<p>모든 한도 정상.</p>"

    lim_rows = [[row["limit"], row["dimension"], str(row["bucket"]),
                 _won(row["exposure"]), _won(row["threshold"]),
                 _pct(row["utilisation"], 1),
                 _badge(row["severity"], {"OK":"GREEN","WARN":"WARN","BREACH":"FAIL","CRITICAL":"FAIL"}.get(row["severity"],"NEUTRAL"))]
                for _, row in top_lim.iterrows()]
    conc_rows = [[row["dimension"], f"{int(row['n_buckets']):,}",
                  f"{row['hhi']:.4f}", f"{row['normalised_hhi']:.4f}",
                  _pct(row["top1_share"])] for _, row in conc.iterrows()]
    body = f"""
<h1 class="title">7. 한도관리 & 집중리스크</h1>
<p class="section-lead">한도 사용률 (동일차주 / 섹터 / 국가) + HHI 집중도.</p>
<div class="row2">
<div class="card"><h2>한도 사용률</h2><div class="chart">{util_chart}</div></div>
<div class="card"><h2>HHI 집중도</h2><div class="chart">{conc_chart}</div></div>
</div>
<div class="card"><h2>한도 경보 상세 (상위 15)</h2>
{_table(["한도","차원","버킷","노출","한도","사용률","등급"], lim_rows, right_cols=[3,4,5])}
</div>
<div class="card"><h2>HHI 차원별</h2>
{_table(["차원","버킷수","HHI","정규화 HHI","최대비중"], conc_rows, right_cols=[1,2,3,4])}
</div>
"""
    return _page("한도·집중도", body, "07_limits.html")


def _page_rapm(r: PipelineResult) -> str:
    rapm = r.rapm.copy()
    raroc_chart = viz.bar_chart(
        rapm["asset_class"].tolist(), rapm["raroc_mean"].tolist(),
        value_fmt=_pct, title="자산군별 평균 RAROC",
        reference_value=r.meta["hurdle_rate"],
        reference_label=f"hurdle {_pct(r.meta['hurdle_rate'])}",
        colors=[viz.GREEN if v >= r.meta["hurdle_rate"] else viz.RED
                for v in rapm["raroc_mean"]],
    )
    pass_chart = viz.bar_chart(
        rapm["asset_class"].tolist(), rapm["pass_hurdle_pct"].tolist(),
        value_fmt=_pct, title="hurdle 충족 비율",
    )
    rows = [[row["asset_class"], f"{int(row['n']):,}",
             _won(row["ec"]), _won(row["el"]), _won(row["revenue"]),
             _pct(row["raroc_mean"]), _pct(row["pass_hurdle_pct"])]
            for _, row in rapm.iterrows()]
    body = f"""
<h1 class="title">8. RAPM (RAROC)</h1>
<p class="section-lead">자산군별 위험조정수익률과 hurdle rate({_pct(r.meta['hurdle_rate'])}) 충족 비율.</p>
<div class="row2">
<div class="card"><h2>평균 RAROC</h2><div class="chart">{raroc_chart}</div></div>
<div class="card"><h2>hurdle 충족 비율</h2><div class="chart">{pass_chart}</div></div>
</div>
<div class="card"><h2>자산군별 상세</h2>
{_table(["자산군","건수","경제자본","EL","수익","평균 RAROC","Hurdle 충족"], rows,
        right_cols=[1,2,3,4,5,6])}
</div>
"""
    return _page("RAPM", body, "08_rapm.html")


def _page_stress(r: PipelineResult) -> str:
    s = r.stress.copy(); rev = r.reverse_stress
    sp = r.stress_path; troughs = r.stress_path_trough
    qs = r.meta["quarters"]

    cet1_chart = viz.bar_chart(
        s["scenario"].tolist(), s["cet1_ratio"].tolist(),
        value_fmt=_pct, title="단년 시나리오별 스트레스 CET1 비율",
        reference_value=r.bis.required["cet1"],
        reference_label=f"요구 {_pct(r.bis.required['cet1'])}",
        colors=[viz.GREEN if x >= r.bis.required["cet1"] else viz.RED
                for x in s["cet1_ratio"]],
    )
    path_series = {}
    for sc in sp["scenario"].unique():
        g = sp[sp["scenario"] == sc].sort_values("q_index")
        path_series[sc] = g["cet1_ratio"].tolist()
    path_chart = viz.line_chart(
        qs, path_series, value_fmt=_pct,
        title="분기별 CET1 경로",
        reference_value=r.bis.required["cet1"],
        reference_label=f"요구 {_pct(r.bis.required['cet1'])}",
    )
    s_rows = [[row["scenario"], _won(row["rwa_total"]),
               _won(row["ecl"]), _pct(row["cet1_ratio"]),
               f"{row['cet1_surplus']*100:+.2f}%p",
               _badge("PASS" if row["passes"] else "FAIL",
                      "PASS" if row["passes"] else "FAIL")]
              for _, row in s.iterrows()]
    t_rows = [[row["scenario"], _pct(row["trough_cet1"]),
               row["trough_quarter"], _pct(row["end_cet1"]),
               str(row["first_breach"]) if isinstance(row["first_breach"], str) else "—",
               _badge("PASS" if row["passes_all"] else "FAIL",
                      "PASS" if row["passes_all"] else "FAIL")]
              for _, row in troughs.iterrows()]
    rev_block = ""
    if rev.resilient:
        rev_block = (f'<div class="callout good">최대 심도(s={rev.critical_severity:.1f})에서도 '
                     f'CET1 {_pct(rev.ratio_at_break)} > 임계 — 자본 내성 확보.</div>')
    elif rev.already_breached:
        rev_block = (f'<div class="callout bad">무충격 상태에서 이미 임계 미달 '
                     f'(CET1 {_pct(rev.base_ratio)} ≤ 임계 {_pct(rev.target_ratio)}). '
                     f'즉시 자본확충 필요.</div>')
    else:
        rev_block = (f'<div class="callout"><b>임계 심도 s={rev.critical_severity:.2f}</b> · '
                     f'함의 거시충격 GDP <b>{rev.implied_gdp_shock:+.1%}</b>, '
                     f'LGD <b>+{rev.implied_lgd_addon:.1%}p</b><br>'
                     f'임계점: RWA {_won(rev.rwa_total_at_break)}, '
                     f'ECL {_won(rev.ecl_at_break)}, CET1 {_pct(rev.ratio_at_break)}</div>')

    body = f"""
<h1 class="title">9. 스트레스테스트</h1>
<p class="section-lead">단년 시나리오(정방향) · 역스트레스(임계 심도) · 분기별 자본 경로.</p>
<div class="row2">
<div class="card"><h2>시나리오별 CET1</h2><div class="chart">{cet1_chart}</div>
{_table(["시나리오","RWA","ECL","CET1","잉여","판정"], s_rows, right_cols=[1,2,3,4])}
</div>
<div class="card"><h2>분기별 CET1 경로</h2><div class="chart">{path_chart}</div>
{_table(["시나리오","최저 CET1","최저 시점","기말 CET1","최초 위반","전구간"], t_rows, right_cols=[1,3])}
</div>
</div>
<div class="card"><h2>역스트레스테스트 (CET1 임계 시나리오)</h2>
<div class="kpi-grid">
{_kpi("기준 CET1", _pct(rev.base_ratio))}
{_kpi("임계(버퍼포함 요구)", _pct(rev.target_ratio))}
{_kpi("임계 심도 s", f"{rev.critical_severity:.2f}")}
</div>
{rev_block}
</div>
"""
    return _page("스트레스", body, "09_stress.html")


def _page_icaap(r: PipelineResult) -> str:
    ic = r.icaap
    ec_chart = viz.bar_chart(
        ic.ec_by_type["risk_type"].tolist(),
        ic.ec_by_type["ec"].tolist(),
        title="위험유형별 경제자본 (Standalone)",
        colors=viz.PALETTE[:len(ic.ec_by_type)],
    )
    div_chart = viz.waterfall(
        ["단순합 EC","분산효과","집중 add-on (이미 포함)","통합 EC"],
        [ic.ec_standalone_sum, -ic.diversification_benefit,
         0.0, ic.ec_diversified],
        title="Standalone → 통합 EC", value_fmt=_won,
    )
    util_gauge = viz.gauge(
        ic.utilisation, vmin=0, vmax=1.5,
        title="내부자본 사용률",
        thresholds=[(0.8, viz.GREEN), (1.0, viz.AMBER), (1.5, viz.RED)],
        value_fmt=lambda v: f"{v*100:.1f}%",
    )
    cmp_chart = viz.bar_chart(
        ["통합 EC","가용자본(AFR)"],
        [ic.ec_diversified, ic.available_capital],
        title="통합 EC vs 가용자본",
        colors=[viz.PALETTE[2], viz.GREEN],
    )
    ec_rows = [[row["risk_type"], _won(row["ec"])]
               for _, row in ic.ec_by_type.iterrows()]
    body = f"""
<h1 class="title">10. 내부자본 (ICAAP) — Pillar 2</h1>
<p class="section-lead">위험유형별 경제자본 + 집중리스크 add-on → 분산-공분산 통합 → 가용자본 비교.</p>
<div class="kpi-grid">
{_kpi("판정", ic.grade,
       sub="GREEN ≤80%, AMBER 80~100%, RED >100%",
       tone={"GREEN":"good","AMBER":"warn","RED":"bad"}[ic.grade])}
{_kpi("사용률", _pct(ic.utilisation, 1))}
{_kpi("통합 EC (분산 후)", _won(ic.ec_diversified))}
{_kpi("가용자본 (AFR)", _won(ic.available_capital))}
{_kpi("잉여 내부자본", _won(ic.buffer),
       tone="good" if ic.buffer > 0 else "bad")}
{_kpi("분산효과", _won(ic.diversification_benefit), sub="단순합 − 통합 EC")}
{_kpi("집중 add-on (P2)", _won(ic.concentration_addon))}
</div>
<div class="row2">
<div class="card"><h2>위험유형별 경제자본</h2><div class="chart">{ec_chart}</div>
{_table(["위험유형","경제자본"], ec_rows, right_cols=[1])}</div>
<div class="card"><h2>분산-공분산 통합</h2><div class="chart">{div_chart}</div>
<p class="section-lead">상관행렬: credit-market 0.5, credit-irrbb 0.4, market-irrbb 0.5, others 0.2~0.3.</p>
</div>
</div>
<div class="row2">
<div class="card"><h2>사용률 게이지</h2><div class="chart">{util_gauge}</div></div>
<div class="card"><h2>통합 EC vs 가용자본</h2><div class="chart">{cmp_chart}</div></div>
</div>
"""
    return _page("내부자본", body, "10_icaap.html")


def _page_alm_hub(r: PipelineResult) -> str:
    alm = r.alm
    bs = alm["balance_sheet"]; lcr = alm["lcr"]; nsfr = alm["nsfr"]; irrbb = alm["irrbb"]
    by_asset = {
        "여신": [bs.loans],
        "HQLA": [sum(bs.hqla.values())],
        "기타": [bs.other_assets],
    }
    by_liab = {
        "리테일 안정": [bs.funding["retail_stable"]],
        "리테일 비안정": [bs.funding["retail_less_stable"]],
        "기업 운영성": [bs.funding["corporate_operational"]],
        "기업 비운영성": [bs.funding["corporate_non_operational"]],
        "FI 단기": [bs.funding["wholesale_fi_lt6m"]],
        "FI 6-12M": [bs.funding["wholesale_fi_6to12m"]],
        "장기 조달": [bs.funding["funding_gt1y"]],
        "자본": [bs.equity],
    }
    bs_chart = viz.stacked_bar(["자산"], by_asset, title="자산 구성") + \
               viz.stacked_bar(["조달"], by_liab, title="조달 구성")
    body = f"""
<h1 class="title">11. ALM — 자산부채관리 허브</h1>
<p class="section-lead">합성 재무상태표 → IRRBB · LCR · NSFR. 각 상세 보고서는 하위 탭(또는 아래 카드)로 이동.</p>
<div class="kpi-grid">
{_kpi("총자산", _won(bs.total_assets))}
{_kpi("여신", _won(bs.loans), sub=f"총자산의 {bs.loans/bs.total_assets:.1%}")}
{_kpi("HQLA", _won(sum(bs.hqla.values())),
       sub=f"L1 {bs.hqla['level_1']/sum(bs.hqla.values()):.0%} / L2A {bs.hqla['level_2a']/sum(bs.hqla.values()):.0%} / L2B {bs.hqla['level_2b']/sum(bs.hqla.values()):.0%}")}
{_kpi("자본", _won(bs.equity))}
</div>
<div class="card">{bs_chart}</div>
<div class="row2">
<div class="card"><h2><a href="11a_irrbb.html">11-1. IRRBB</a></h2>
<div class="kpi-grid">
{_kpi("최악 ΔEVE / Tier1", _pct(irrbb.worst_pct_tier1),
       sub=f"기준 ≤{_pct(IRRBB_OUTLIER_EVE_PCT_TIER1, 0)} · {irrbb.worst_eve_scenario}",
       tone="good" if not irrbb.outlier() else "bad")}
{_kpi("최악 ΔEVE 금액", _won(irrbb.worst_eve_decline))}
</div></div>
<div class="card"><h2><a href="11b_lcr.html">11-2. LCR</a></h2>
<div class="kpi-grid">
{_kpi("LCR", _pct(lcr.lcr, 1),
       sub=f"기준 {_pct(LCR_MIN, 0)}",
       tone="good" if lcr.passes() else "bad")}
{_kpi("HQLA (캡 적용)", _won(lcr.hqla_total))}
{_kpi("순현금유출", _won(lcr.net_outflow))}
</div></div>
</div>
<div class="card"><h2><a href="11c_nsfr.html">11-3. NSFR</a></h2>
<div class="kpi-grid">
{_kpi("NSFR", _pct(nsfr.nsfr, 1),
       sub=f"기준 {_pct(NSFR_MIN, 0)}",
       tone="good" if nsfr.passes() else "bad")}
{_kpi("ASF (가용안정조달)", _won(nsfr.asf_total))}
{_kpi("RSF (필요안정조달)", _won(nsfr.rsf_total))}
</div></div>
"""
    return _page("ALM", body, "11_alm.html", alm_active=True)


def _page_irrbb(r: PipelineResult) -> str:
    irrbb = r.alm["irrbb"]
    eve_rows = [[row["scenario"], _won(row["delta_eve"]),
                 f"{row['pct_tier1']*100:+.2f}%"]
                for _, row in irrbb.delta_eve.iterrows()]
    nii_rows = [[row["scenario"], _won(row["delta_nii"])]
                for _, row in irrbb.delta_nii.iterrows()]
    eve_chart = viz.bar_chart(
        irrbb.delta_eve["scenario"].tolist(),
        irrbb.delta_eve["delta_eve"].tolist(),
        title="6대 표준 충격별 ΔEVE",
        colors=[viz.RED if v < 0 else viz.GREEN for v in irrbb.delta_eve["delta_eve"]],
    )
    pct_chart = viz.bar_chart(
        irrbb.delta_eve["scenario"].tolist(),
        irrbb.delta_eve["pct_tier1"].tolist(),
        value_fmt=lambda v: f"{v*100:+.2f}%",
        title="ΔEVE / Tier1",
        reference_value=-IRRBB_OUTLIER_EVE_PCT_TIER1,
        reference_label=f"outlier {-IRRBB_OUTLIER_EVE_PCT_TIER1*100:.0f}%",
        colors=[viz.RED if v < 0 else viz.GREEN for v in irrbb.delta_eve["pct_tier1"]],
    )
    rep = irrbb.repricing
    ladder = viz.bar_chart(
        rep["bucket"].tolist(), rep["gap"].tolist(),
        title="만기 재가격 갭 (자산-부채)",
        colors=[viz.GREEN if g >= 0 else viz.RED for g in rep["gap"]],
    )
    pv_effect = viz.bar_chart(
        rep["bucket"].tolist(), rep["pv_effect_worst"].tolist(),
        title=f"버킷별 PV 효과 (최악 시나리오: {irrbb.worst_eve_scenario})",
        colors=[viz.RED if v < 0 else viz.GREEN for v in rep["pv_effect_worst"]],
    )
    outlier_block = ('<div class="callout bad"><b>Outlier test 위반:</b> '
                     f'최악 ΔEVE 감소 {_pct(irrbb.worst_pct_tier1)} > 15% of Tier1 (SRP31.92).</div>'
                     if irrbb.outlier() else
                     '<div class="callout warn">조기경보 12% 초과 — 모니터링 강화.</div>'
                     if irrbb.early_warning() else
                     '<div class="callout good">Outlier test 통과: 최악 ΔEVE ≤ 15% of Tier1.</div>')
    body = f"""
<h1 class="title">11-1. IRRBB — 은행계정 금리리스크</h1>
<p class="section-lead">BCBS IRRBB 표준(2016) 6대 시나리오: parallel up/down, short up/down, steepener, flattener.
ΔEVE는 만기갭 현금흐름의 현가 변화, ΔNII는 12개월 이내 갭에 대한 평행충격 영향.</p>

<div class="kpi-grid">
{_kpi("최악 시나리오", irrbb.worst_eve_scenario)}
{_kpi("ΔEVE (최악)", _won(-irrbb.worst_eve_decline),
       sub=f"{_pct(irrbb.worst_pct_tier1)} of Tier1",
       tone="good" if not irrbb.outlier() else ("warn" if irrbb.early_warning() else "bad"))}
{_kpi("Tier1", _won(irrbb.tier1))}
{_kpi("기준 금리", f"{irrbb.base_rate*100:.1f}%")}
</div>
{outlier_block}

<div class="row2">
<div class="card"><h2>ΔEVE 절대값</h2><div class="chart">{eve_chart}</div></div>
<div class="card"><h2>ΔEVE / Tier1</h2><div class="chart">{pct_chart}</div></div>
</div>
<div class="card"><h2>시나리오별 결과</h2>
{_table(["시나리오","ΔEVE","Tier1 대비"], eve_rows, right_cols=[1,2])}
{_table(["시나리오","ΔNII (12M)"], nii_rows, right_cols=[1])}
</div>

<div class="row2">
<div class="card"><h2>만기 재가격 갭 사다리</h2><div class="chart">{ladder}</div></div>
<div class="card"><h2>버킷별 PV 효과 (최악 시나리오)</h2><div class="chart">{pv_effect}</div></div>
</div>
"""
    return _page("IRRBB", body, "11a_irrbb.html", alm_active=True)


def _page_lcr(r: PipelineResult) -> str:
    lcr = r.alm["lcr"]
    hqla_chart = viz.stacked_bar(
        ["HQLA (시장가)", "HQLA (Haircut 적용)", "HQLA (Cap 적용 최종)"],
        {
            "Level 1": [lcr.hqla_detail.loc[0,"market_value"],
                        lcr.hqla_detail.loc[0,"post_haircut"],
                        lcr.hqla_detail.loc[0,"included"]],
            "Level 2A": [lcr.hqla_detail.loc[1,"market_value"],
                         lcr.hqla_detail.loc[1,"post_haircut"],
                         lcr.hqla_detail.loc[1,"included"]],
            "Level 2B": [lcr.hqla_detail.loc[2,"market_value"],
                         lcr.hqla_detail.loc[2,"post_haircut"],
                         lcr.hqla_detail.loc[2,"included"]],
        }, title="HQLA 적용 단계",
    )
    outflow_chart = viz.horizontal_bar(
        lcr.outflows["category"].tolist(),
        lcr.outflows["outflow"].tolist(),
        title="유출 (30일 가중)",
        color=viz.RED,
    )
    gauge = viz.gauge(
        lcr.lcr, vmin=0, vmax=2.5, title="LCR",
        thresholds=[(0.8, viz.RED), (1.0, viz.AMBER), (2.5, viz.GREEN)],
        value_fmt=lambda v: f"{v*100:.1f}%",
    )
    hqla_rows = [[row["component"], _won(row["market_value"]),
                  _pct(row["haircut"]), _won(row["post_haircut"]),
                  _won(row["included"])]
                 for _, row in lcr.hqla_detail.iterrows()]
    out_rows = [[row["category"], _won(row["amount"]),
                 _pct(row["runoff"]), _won(row["outflow"])]
                for _, row in lcr.outflows.iterrows()]
    in_rows = [[row["category"], _won(row["amount"]),
                _pct(row["rate"]), _won(row["inflow"])]
               for _, row in lcr.inflows.iterrows()]
    body = f"""
<h1 class="title">11-2. LCR — 유동성커버리지비율</h1>
<p class="section-lead">LCR = HQLA(haircut · 캡 적용) / 30일 순현금유출(유입은 유출의 75% 한도).
캡 적용은 LCR30.47 공식(adj15 → adj40)에 따름.</p>

<div class="row2">
<div class="card"><h2>LCR 게이지</h2><div class="chart">{gauge}</div>
<div class="kpi-grid">
{_kpi("LCR", _pct(lcr.lcr, 1), tone="good" if lcr.passes() else "bad",
       sub=f"기준 {_pct(LCR_MIN, 0)}")}
</div>
</div>
<div class="card"><h2>HQLA 단계별 흐름</h2><div class="chart">{hqla_chart}</div>
</div>
</div>

<div class="card"><h2>HQLA 상세 (캡 적용 결과)</h2>
{_table(["등급","시장가","Haircut","Haircut 후","최종 (캡 적용)"], hqla_rows, right_cols=[1,2,3,4])}
</div>

<div class="row2">
<div class="card"><h2>30일 가중 유출</h2><div class="chart">{outflow_chart}</div>
{_table(["카테고리","잔액","Run-off","유출"], out_rows, right_cols=[1,2,3])}
</div>
<div class="card"><h2>30일 가중 유입</h2>
{_table(["카테고리","잔액","유입률","유입"], in_rows, right_cols=[1,2,3])}
<div class="kpi-grid" style="margin-top:8px">
{_kpi("총유출", _won(lcr.gross_outflow))}
{_kpi("유입(캡 적용)", _won(lcr.inflow_capped),
       sub=f"≤ {_pct(0.75, 0)} × 유출")}
{_kpi("순유출", _won(lcr.net_outflow))}
</div>
</div>
</div>
"""
    return _page("LCR", body, "11b_lcr.html", alm_active=True)


def _page_nsfr(r: PipelineResult) -> str:
    nsfr = r.alm["nsfr"]
    asf_chart = viz.horizontal_bar(
        nsfr.asf["category"].tolist(),
        nsfr.asf["weighted"].tolist(),
        title="가용안정자금조달 (ASF, 가중 후)", color=viz.GREEN,
    )
    rsf_chart = viz.horizontal_bar(
        nsfr.rsf["category"].tolist(),
        nsfr.rsf["weighted"].tolist(),
        title="필요안정자금조달 (RSF, 가중 후)", color=viz.AMBER,
    )
    gauge = viz.gauge(
        nsfr.nsfr, vmin=0, vmax=2.0, title="NSFR",
        thresholds=[(0.8, viz.RED), (1.0, viz.AMBER), (2.0, viz.GREEN)],
        value_fmt=lambda v: f"{v*100:.1f}%",
    )
    asf_rows = [[row["category"], _won(row["amount"]),
                 f"{row['factor']:.2f}", _won(row["weighted"])]
                for _, row in nsfr.asf.iterrows()]
    rsf_rows = [[row["category"], _won(row["amount"]),
                 f"{row['factor']:.2f}", _won(row["weighted"])]
                for _, row in nsfr.rsf.iterrows()]
    body = f"""
<h1 class="title">11-3. NSFR — 순안정조달비율</h1>
<p class="section-lead">NSFR = ASF(자본 + 안정조달성 부채) / RSF(만기/유동성에 따라 가중된 자산).
기준 100% 상시 충족.</p>

<div class="row2">
<div class="card"><h2>NSFR 게이지</h2><div class="chart">{gauge}</div>
<div class="kpi-grid">
{_kpi("NSFR", _pct(nsfr.nsfr, 1), tone="good" if nsfr.passes() else "bad",
       sub=f"기준 {_pct(NSFR_MIN, 0)}")}
{_kpi("ASF", _won(nsfr.asf_total))}
{_kpi("RSF", _won(nsfr.rsf_total))}
</div>
</div>
<div class="card"><h2>차변 (ASF, 조달측)</h2><div class="chart">{asf_chart}</div></div>
</div>

<div class="row2">
<div class="card"><h2>ASF 상세</h2>
{_table(["카테고리","잔액","Factor","가중 ASF"], asf_rows, right_cols=[1,2,3])}
</div>
<div class="card"><h2>RSF 상세</h2>
{_table(["카테고리","잔액","Factor","가중 RSF"], rsf_rows, right_cols=[1,2,3])}
</div>
</div>

<div class="card"><h2>RSF — 자산 측</h2><div class="chart">{rsf_chart}</div></div>
"""
    return _page("NSFR", body, "11c_nsfr.html", alm_active=True)


def _page_validation(r: PipelineResult) -> str:
    v = r.validation
    summ = v.summary()
    # rows
    rows = [[c.name, _badge(c.status, c.status), c.detail] for c in v.checks]
    cite_rows = [[section, c.standard, c.section, c.note]
                 for section, c in ALL_CITATIONS]
    body = f"""
<h1 class="title">12. 자체검증 + 출처/준거</h1>
<p class="section-lead">정합성 체크 (SA/IRB, BIS, ECL, ALM, ICAAP 등) — FAIL이 0건이어야 결재 가능.</p>
<div class="kpi-grid">
{_kpi("PASS", f"{summ.get('PASS',0)}", tone="good")}
{_kpi("WARN", f"{summ.get('WARN',0)}", tone="warn")}
{_kpi("FAIL", f"{summ.get('FAIL',0)}", tone="bad")}
</div>
<div class="card"><h2>전 체크 상세 ({len(v.checks)}건)</h2>
{_table(["체크","상태","상세"], rows)}
</div>
<div class="card"><h2>출처 및 준거</h2>
{_table(["섹션","표준","항목","비고"], cite_rows)}
</div>
"""
    return _page("자체검증", body, "12_validation.html")


# ============================================================================
# Builder
# ============================================================================


def build_report_set(result: PipelineResult, out_dir: str | Path,
                     portfolio=None) -> dict[str, str]:
    """Write the whole report set to out_dir; return {filename: absolute path}.

    `portfolio` is required for Pillar 3 (CR1) — pass the original DataFrame.
    Falls back to summary-only if omitted.
    """
    from risk_lib.html_ops_pages import (
        page_climate, page_ccr, page_op_loss, page_sensitivity,
        page_model_risk, page_concentration_deep, page_raf, page_pillar3,
        page_mda, page_kri_trends, page_attribution, page_vintage,
        page_data_quality,
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pages = {
        "index.html":         _page_summary(result),
        "01_portfolio.html":  _page_portfolio(result),
        "02_pd.html":         _page_pd(result),
        "03_rwa.html":        _page_rwa(result),
        "04_capital.html":    _page_capital(result),
        "05_ecl.html":        _page_ecl(result),
        "06_monitoring.html": _page_monitoring(result),
        "07_limits.html":     _page_limits(result),
        "08_rapm.html":       _page_rapm(result),
        "09_stress.html":     _page_stress(result),
        "10_icaap.html":      _page_icaap(result),
        "11_alm.html":        _page_alm_hub(result),
        "11a_irrbb.html":     _page_irrbb(result),
        "11b_lcr.html":       _page_lcr(result),
        "11c_nsfr.html":      _page_nsfr(result),
        "12_validation.html": _page_validation(result),
        "13_climate.html":    page_climate(result),
        "14_ccr.html":        page_ccr(result),
        "15_op_loss.html":    page_op_loss(result),
        "16_sensitivity.html": page_sensitivity(result),
        "17_model_risk.html": page_model_risk(result),
        "18_concentration_deep.html": page_concentration_deep(result),
        "19_raf.html":        page_raf(result),
        "21_mda.html":        page_mda(result),
        "22_kri_trends.html": page_kri_trends(result),
        "23_attribution.html":page_attribution(result),
    }
    if portfolio is not None:
        pages["20_pillar3.html"] = page_pillar3(result, portfolio)
        pages["24_vintage.html"] = page_vintage(result, portfolio)
        pages["25_data_quality.html"] = page_data_quality(result, portfolio)
    written = {}
    for name, content in pages.items():
        p = out / name
        p.write_text(content, encoding="utf-8")
        written[name] = str(p.resolve())
    return written


def build_full_report_package(
    result: PipelineResult,
    out_dir: str | Path,
    *,
    portfolio=None,
    manifest=None,
) -> dict[str, str]:
    """Two-tier package: executive.html (root) + ops/ (operational deep-dive)
    plus manifest.json. Returns {label: absolute_path}.

    The CRO opens executive.html; analysts use ops/index.html. All cross-links
    are relative so the directory is portable.
    """
    from risk_lib.html_exec import build_executive
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    ops_dir = out / "ops"
    written_ops = build_report_set(result, ops_dir, portfolio=portfolio)
    exec_path = build_executive(result, out,
                                manifest_digest=getattr(manifest, "headline_digest", ""))
    manifest_path = None
    if manifest is not None:
        manifest_path = out / "manifest.json"
        manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    return {
        "executive": str(exec_path.resolve()),
        "ops_dir": str(ops_dir.resolve()),
        **{f"ops/{k}": v for k, v in written_ops.items()},
        **({"manifest": str(manifest_path.resolve())} if manifest_path else {}),
    }
