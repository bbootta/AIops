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
    ("26_comparison.html", "26. 시점 비교"),
    ("27_lgd_model.html",  "27. LGD모형"),
    ("28_model_challenger.html", "28. 챔피언/챌린저"),
    ("29_irb_deep.html",   "29. IRB D-D"),
    ("30_market_risk_deep.html", "30. 시장 D-D"),
    ("31_op_risk_deep.html", "31. 운영 D-D"),
    ("32_capital_stack.html", "32. 자본 스택"),
    ("33_buffer_layering.html", "33. 버퍼 layer"),
    ("34_leverage_deep.html", "34. 레버리지 D-D"),
    ("35_sicr_detail.html",   "35. SICR 분해"),
    ("36_pd_term_structure.html","36. PD 잔존기간"),
    ("37_macro_scenario.html","37. 거시 시나리오"),
    ("38_provisioning_attribution.html","38. 충당금 귀속"),
    ("39_dpd_roll.html",   "39. DPD roll-rate"),
    ("40_recovery_lgd.html","40. 회수·LGD"),
    ("41_cure_analysis.html","41. Cure 분석"),
    ("42_limit_dashboard.html", "42. 한도 dashboard"),
    ("43_large_exposure.html", "43. 거대익스포저"),
    ("44_concentration_stress.html","44. 집중 스트레스"),
    ("45_eva_sva.html",    "45. EVA/SVA"),
    ("46_pricing_breakeven.html", "46. Pricing"),
    ("47_rapm_scenario.html", "47. RAPM 시나리오"),
    ("48_reverse_stress_multi.html", "48. Multi-역스트레스"),
    ("49_ccar_path.html",    "49. CCAR 경로"),
    ("50_climate_capital.html", "50. 기후 자본"),
    ("51_liquidity_stress.html", "51. 유동성 stress"),
    ("52_final_attestation.html", "52. 최종 결재"),
    ("53_xva_full.html",          "53. XVA 전체"),
    ("54_trading_sensitivities.html", "54. Trading Greeks"),
    ("55_scenario_library.html",  "55. Scenario Library"),
    ("56_frtb_ima.html",          "56. FRTB IMA"),
    ("57_model_inventory.html",   "57. Model Inventory"),
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
    bt = r.backtest
    hl = bt["hosmer_lemeshow"]
    disc = bt.get("discrimination", {})
    pof = bt.get("kupiec_pof", {})
    ccc = bt.get("christoffersen_cc", {})
    cal_curve = bt.get("calibration_curve", pd.DataFrame())

    # --- 변별력 4지표 차트
    g_vals = [pm[s]["gini"] for s in segs]
    disc_chart = viz.bar_chart(
        segs, g_vals, value_fmt=lambda v: f"{v:.3f}",
        title="세그먼트별 Gini",
        reference_value=GINI_MIN_GOOD,
        reference_label=f"양호 ≥ {GINI_MIN_GOOD:.2f}",
        colors=[viz.GREEN if g >= GINI_MIN_GOOD else viz.AMBER for g in g_vals],
    )
    auc_vals = [pm[s].get("auc_roc", 0.5) for s in segs]
    auc_chart = viz.bar_chart(
        segs, auc_vals, value_fmt=lambda v: f"{v:.3f}",
        title="세그먼트별 AUC-ROC",
        reference_value=0.75, reference_label="양호 ≥ 0.75",
        colors=[viz.GREEN if a >= 0.75 else viz.AMBER for a in auc_vals],
    )

    # --- ROC 곡선 (전체)  — 다시 계산: 정렬 + 누적
    import numpy as np
    # corporate 표본 기준 (backtest는 corporate에서 계산)
    cal_fpr, cal_tpr = [0.0], [0.0]
    if not cal_curve.empty:
        # cum_pos/cum_neg from grade-ordered defaults — 이미 cal_curve의 정렬은
        # 예측 PD 오름차순. ROC용으로는 내림차순으로 누적.
        # 백테스트 단계에서 raw 데이터가 없으므로 cal_curve로 근사한다.
        pass

    # --- 캘리브레이션 plot
    if not cal_curve.empty:
        cal_plot = viz.calibration_plot(
            cal_curve["mean_pd"].tolist(),
            cal_curve["realised_dr"].tolist(),
            counts=cal_curve["n"].tolist(),
            title="캘리브레이션 — 코퍼레이트",
        )
    else:
        cal_plot = "<p class='section-lead'>캘리브레이션 데이터 없음</p>"

    # --- 등급 백테스트
    pg = bt["per_grade"].copy()
    zone_counts = pg["zone"].value_counts().to_dict()
    zones_chart = viz.bar_chart(
        list(zone_counts.keys()), list(zone_counts.values()),
        value_fmt=lambda v: f"{int(v)}",
        title="등급별 백테스트 존",
        colors=[{"GREEN": viz.GREEN, "YELLOW": viz.AMBER,
                 "RED": viz.RED}.get(z, viz.PALETTE[0])
                for z in zone_counts.keys()],
    )

    # --- 세그먼트별 변별력 표
    rows = [[s, f"{pm[s]['gini']:.3f}", f"{pm[s].get('auc_roc', 0):.3f}",
             f"{pm[s]['ks']:.3f}", f"{pm[s].get('auprc', 0):.3f}",
             f"{pm[s].get('brier', 0):.4f}",
             f"{pm[s].get('brier_skill', 0):.3f}",
             f"{int(pm[s]['n_train']):,}/{int(pm[s]['n_test']):,}"]
            for s in segs]

    # --- 등급별 백테스트 디테일
    pg_rows = []
    for _, row in pg.iterrows():
        pg_rows.append([row.get("grade", "-"),
                        f"{int(row.get('n', 0)):,}",
                        f"{row.get('calibrated_pd', 0):.4f}",
                        f"{row.get('realised_dr', 0):.4f}",
                        f"{row.get('p_value', 1):.3f}",
                        _badge(row["zone"],
                               {"GREEN": "GREEN", "YELLOW": "WARN",
                                "RED": "FAIL"}.get(row["zone"], "NEUTRAL"))])

    # --- 변수 중요도 (코퍼레이트, permutation importance)
    var_imp_html = ""
    if "corporate" in r.explain:
        imp = r.explain["corporate"]["permutation"]
        var_imp_html = viz.horizontal_bar(
            imp["feature"].tolist(),
            imp["gini_drop_mean"].tolist(),
            title="코퍼레이트 PD — 변수 중요도 (Gini drop)",
            value_fmt=lambda v: f"{v:.3f}",
            color=viz.PALETTE[0],
        )

    # --- 계수 표
    coef_html = ""
    if "corporate" in r.explain:
        ct = r.explain["corporate"]["coefficients"]
        coef_rows = [[row["feature"], f"{row['coef']:+.3f}",
                      f"{row['odds_ratio']:.3f}",
                      f"{row['contribution_pct']*100:.1f}%",
                      row["direction"]]
                     for _, row in ct.iterrows()]
        coef_html = _table(
            ["변수", "계수β", "Odds ratio", "기여율", "방향"], coef_rows,
            right_cols=[1, 2, 3],
        )

    # --- 마스터 스케일 캘리브레이션 (코퍼레이트 세그먼트)
    ms_html = ""
    if "corporate" in r.calibration:
        ms = r.calibration["corporate"]
        ms_rows = [[row["grade"], f"{row['pd_midpoint']:.4f}",
                    f"{row['mean_pd_predicted']:.4f}",
                    f"{row['realised_dr']:.4f}",
                    f"{row['bias']:+.4f}", f"{int(row['n']):,}"]
                   for _, row in ms.iterrows()]
        ms_html = _table(
            ["등급", "마스터 PD", "평균 모형 PD", "실현 DR", "편차", "건수"],
            ms_rows, right_cols=[1, 2, 3, 4, 5],
        )

    # --- 등급 migration PSI
    mig_rows = []
    for seg, res in r.grade_migration.items():
        mig_rows.append([seg, f"{res['psi']:.4f}",
                         _badge(res["zone"],
                                {"GREEN": "GREEN", "AMBER": "WARN",
                                 "RED": "FAIL"}.get(res["zone"], "NEUTRAL"))])
    mig_html = _table(["세그먼트", "Grade PSI", "Zone"], mig_rows,
                      right_cols=[1]) if mig_rows else ""

    pof_tone = "good" if pof.get("p_value", 0) >= 0.05 else "warn"
    cc_tone = "good" if ccc.get("p_value", 0) >= 0.05 else "warn"

    body = f"""
<h1 class="title">2. 신용평가모형(PD) 변별력 · 캘리브레이션 · XAI</h1>
<p class="section-lead">세그먼트별 Gini/KS/AUC/AUPRC/Brier, Hosmer-Lemeshow,
Kupiec POF, Christoffersen 조건부 coverage, 캘리브레이션 곡선, 변수 중요도,
등급 PSI까지 통합. 준거: Basel CRE36, BCBS WP 14, 금감원 모형리스크 모범규준.</p>

<div class="card"><h2>2-1. 변별력 헤드라인 (전체 corporate 백테스트)</h2>
<div class="kpi-grid">
{_kpi("AUC-ROC", f"{disc.get('auc_roc', 0):.3f}",
       sub="양호 ≥ 0.75",
       tone=("good" if disc.get('auc_roc', 0) >= 0.75 else "warn"))}
{_kpi("Gini", f"{disc.get('gini', 0):.3f}",
       sub=f"양호 ≥ {GINI_MIN_GOOD:.2f}",
       tone=("good" if disc.get('gini', 0) >= GINI_MIN_GOOD else "warn"))}
{_kpi("AUPRC", f"{disc.get('auprc', 0):.3f}",
       sub=f"base rate {disc.get('base_rate', 0)*100:.1f}%")}
{_kpi("Brier", f"{disc.get('brier', 0):.4f}",
       sub=f"skill {disc.get('brier_skill', 0)*100:+.1f}%")}
{_kpi("Kupiec POF p", f"{pof.get('p_value', 0):.3f}",
       sub="≥ 0.05 캘리브레이션 양호", tone=pof_tone)}
{_kpi("Christoffersen CC p", f"{ccc.get('p_value', 0):.3f}",
       sub="≥ 0.05 unconditional+독립 양호", tone=cc_tone)}
</div>
</div>

<div class="row2">
<div class="card"><h2>2-2. 세그먼트별 Gini</h2><div class="chart">{disc_chart}</div></div>
<div class="card"><h2>2-3. 세그먼트별 AUC-ROC</h2><div class="chart">{auc_chart}</div></div>
</div>

<div class="card"><h2>2-4. 세그먼트별 변별력·캘리브레이션 지표</h2>
{_table(["세그먼트", "Gini", "AUC", "KS", "AUPRC", "Brier",
         "Brier skill", "학습/검증"], rows, right_cols=[1, 2, 3, 4, 5, 6, 7])}
</div>

<div class="row2">
<div class="card"><h2>2-5. 캘리브레이션 곡선 (Reliability)</h2>
<div class="chart">{cal_plot}</div>
<p class="section-lead">버블 크기 = bucket 표본 수. 45° 선 위 = 보수적,
아래 = 과소예측(red).</p>
</div>
<div class="card"><h2>2-6. Hosmer-Lemeshow</h2>
<div class="kpi-grid">
{_kpi("χ²", f"{hl['chi_square']:.2f}")}
{_kpi("p-value", f"{hl['p_value']:.3f}",
       tone=("good" if hl['p_value'] >= 0.05 else "warn"))}
{_kpi("판정", "양호" if hl['p_value'] >= 0.05 else "주의",
       sub="p ≥ 0.05 시 캘리브레이션 양호")}
</div>
<h3>등급별 백테스트 존</h3>
<div class="chart">{zones_chart}</div>
</div>
</div>

<div class="card"><h2>2-7. 마스터 스케일 캘리브레이션 — 코퍼레이트</h2>
{ms_html}
<p class="section-lead">등급별 (마스터 PD midpoint, 평균 모형 PD, 실현 DR).
편차가 일관되게 양수면 보수적, 음수면 PD 모형이 위반.</p>
</div>

<div class="card"><h2>2-8. 등급별 신호등 (코퍼레이트)</h2>
{_table(["등급", "건수", "캘리브 PD", "실현 DR", "p-value", "존"],
        pg_rows, right_cols=[1, 2, 3, 4])}
</div>

<div class="row2">
<div class="card"><h2>2-9. 변수 중요도 (Permutation)</h2>
<div class="chart">{var_imp_html}</div>
<p class="section-lead">Breiman(2001) permutation importance — 변수를 셔플했을
때 Gini drop의 평균(시드=42, n_repeats=3).</p>
</div>
<div class="card"><h2>2-10. 회귀 계수 · Odds Ratio</h2>
{coef_html}
</div>
</div>

<div class="card"><h2>2-11. 등급 분포 안정성 (Grade-level PSI)</h2>
{mig_html}
<p class="section-lead">train vs test 등급 분포의 PSI. &lt;0.10 GREEN,
0.10–0.25 AMBER, ≥0.25 RED.</p>
</div>
"""
    return _page("PD모형", body, "02_pd.html")


def _page_lgd_model(r: PipelineResult) -> str:
    """27. LGD 모형 — 모형 카드 + 백테스트 + 회수 곡선."""
    lgd = r.lgd_metrics
    if not lgd:
        body = ("<h1 class='title'>27. LGD모형</h1>"
                "<p>LGD 모형 데이터 없음.</p>")
        return _page("LGD모형", body, "27_lgd_model.html")

    rows = []
    bias_chart_data = []
    bias_chart_labels = []
    for seg, m in lgd.items():
        bt = m["backtest"]
        rows.append([seg, ", ".join(m["features"]),
                     f"{bt['mae']:.4f}", f"{bt['rmse']:.4f}",
                     f"{bt['r2']:+.3f}", f"{bt['brier']:.4f}",
                     f"{bt['bias']:+.4f}",
                     f"{bt['mean_realised']:.3f}",
                     f"{bt['mean_predicted']:.3f}",
                     f"{int(bt['n']):,}"])
        bias_chart_labels.append(seg)
        bias_chart_data.append(bt["bias"])

    bias_chart = viz.bar_chart(
        bias_chart_labels, bias_chart_data,
        value_fmt=lambda v: f"{v:+.3f}",
        title="세그먼트별 LGD 예측 편차(predicted - realised)",
        colors=[viz.GREEN if abs(b) < 0.05 else viz.AMBER
                for b in bias_chart_data],
    )

    # Histogram for the first segment (corporate if present)
    import numpy as np
    hist_html = ""
    hist_seg = "corporate" if "corporate" in lgd else next(iter(lgd))
    if hist_seg in lgd and "predicted_full" in lgd[hist_seg]:
        # need access to realised — pull from pd_metrics indirectly through
        # backtest's mean_realised but for distribution we re-derive
        # via the model's residual: use bucket calibration to approximate.
        m = lgd[hist_seg]
        # Use the bucket calibration to plot mean per bucket
        from risk_lib.models.lgd_model import lgd_bucket_calibration
        # We don't have raw arrays here; rebuild a histogram from
        # predicted_full only and use mean realised as overlay reference.
        preds = np.asarray(m["predicted_full"], dtype=float)
        hist_html = viz.histogram(
            preds.tolist(), bins=20,
            title=f"{hist_seg} — 예측 LGD 분포",
            color=viz.PALETTE[0],
            value_fmt=lambda v: f"{v*100:.0f}%",
        )

    body = f"""
<h1 class="title">27. LGD 모형 — 적합·백테스트·분포</h1>
<p class="section-lead">세그먼트별 beta(logit) ridge 회귀로 적합한 LGD 모형의
백테스트 결과. 산식: ŷ = floor + (1-floor)·σ(Xβ); 검증: MAE/RMSE/R²/Brier.
준거: Basel CRE36 LGD 모형 요건, BCBS WP14, 금감원 「은행업감독업무시행세칙」
별표 3-25.</p>

<div class="card"><h2>27-1. 세그먼트별 백테스트</h2>
{_table(["세그먼트", "변수", "MAE", "RMSE", "R²", "Brier", "편차",
         "실현 평균", "예측 평균", "표본 수"], rows,
        right_cols=[2, 3, 4, 5, 6, 7, 8, 9])}
</div>

<div class="row2">
<div class="card"><h2>27-2. 세그먼트별 편차</h2>
<div class="chart">{bias_chart}</div>
<p class="section-lead">|편차| &lt; 5%p 시 양호(녹색).
양수 = 보수적(과대 예측), 음수 = 과소 예측(자본 부족 위험).</p>
</div>
<div class="card"><h2>27-3. 예측 LGD 분포 — {hist_seg}</h2>
<div class="chart">{hist_html}</div>
</div>
</div>

<div class="card"><h2>27-4. 모형 카드</h2>
<p class="section-lead">현재 모형은 logit-변환 LGD에 ridge α=1을 적용한
GLM 근사. 표본이 부족하거나 LGD가 0/1에 집중되면 beta regression(GLM)으로
재학습 권고. floor=0.05.</p>
</div>
"""
    return _page("LGD모형", body, "27_lgd_model.html")


def _page_model_challenger(r: PipelineResult) -> str:
    """28. 챔피언 vs 챌린저 PD 모형 비교."""
    pm = r.pd_metrics
    ch = r.challenger_metrics
    if not ch:
        body = ("<h1 class='title'>28. 챔피언/챌린저</h1>"
                "<p>챌린저 데이터 없음.</p>")
        return _page("챔피언/챌린저", body, "28_model_challenger.html")

    rows = []
    seg_labels, champ_g, chal_g = [], [], []
    for seg, c in ch.items():
        champ = pm.get(seg, {})
        rows.append([seg,
                     f"{champ.get('gini', 0):.3f}",
                     f"{c.get('gini', 0):.3f}",
                     f"{c['delta_gini']:+.3f}",
                     f"{champ.get('auc_roc', 0):.3f}",
                     f"{c.get('auc_roc', 0):.3f}",
                     f"{champ.get('brier', 0):.4f}",
                     f"{c.get('brier', 0):.4f}",
                     ", ".join(c["features"]),
                     _badge(c["verdict"],
                            "PASS" if "CHAMPION" in c["verdict"] else
                            ("WARN" if "CHALLENGER" in c["verdict"]
                             else "NEUTRAL"))])
        seg_labels.append(seg)
        champ_g.append(champ.get("gini", 0))
        chal_g.append(c.get("gini", 0))

    # side-by-side
    deltas = [pm.get(s, {}).get("gini", 0) - ch[s]["gini"] for s in seg_labels]
    delta_chart = viz.bar_chart(
        seg_labels, deltas,
        value_fmt=lambda v: f"{v:+.3f}",
        title="ΔGini = Champion - Challenger",
        reference_value=0.01, reference_label="유의 차이 0.01",
        colors=[viz.GREEN if d > 0.01 else (viz.RED if d < -0.01 else viz.AMBER)
                for d in deltas],
    )

    # Decision recommendation
    upgrade = [s for s in seg_labels
               if "CHALLENGER" in ch[s]["verdict"]]
    keep = [s for s in seg_labels
            if "CHAMPION" in ch[s]["verdict"]]
    tie = [s for s in seg_labels
           if "동등" in ch[s]["verdict"]]

    body = f"""
<h1 class="title">28. 챔피언 vs 챌린저 — PD 모형 비교</h1>
<p class="section-lead">현재 production 모형(champion: 전체 변수)과 단순화된
benchmark(challenger: 핵심 변수 절반)를 동일 검증 표본에서 비교. ΔGini
&gt; 0.01 인 세그먼트는 챔피언 유지, 음수면 챌린저 승격 검토.</p>

<div class="card"><h2>28-1. ΔGini (Champion - Challenger)</h2>
<div class="chart">{delta_chart}</div>
</div>

<div class="card"><h2>28-2. 상세 비교표</h2>
{_table(["세그먼트", "Champ Gini", "Chal Gini", "ΔGini",
         "Champ AUC", "Chal AUC", "Champ Brier", "Chal Brier",
         "Challenger 변수", "판정"], rows,
        right_cols=[1, 2, 3, 4, 5, 6, 7])}
</div>

<div class="card"><h2>28-3. 의사결정 권고</h2>
<ul>
<li><b>챔피언 유지:</b> {", ".join(keep) if keep else "(없음)"}</li>
<li><b>챌린저 승격 검토:</b> {", ".join(upgrade) if upgrade else "(없음)"}</li>
<li><b>통계적 동등(재검토):</b> {", ".join(tie) if tie else "(없음)"}</li>
</ul>
<p class="section-lead">SR 11-7 / 금감원 모형리스크관리 모범규준에 따라 챌린저
모형은 매년 1회 이상 정기 비교 권고.</p>
</div>
"""
    return _page("챔피언/챌린저", body, "28_model_challenger.html")


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

    # ---- v0.7.0 deep-dive sections (CRO grade) -----------------------------
    deep_html = ""
    deep = getattr(r, "rwa_deep", None)
    if deep is not None:
        from risk_lib import viz_advanced
        # SA asset-class breakdown
        sd = deep.sa_decomposition
        if not sd.empty:
            sa_chart = viz.bar_chart(
                sd["asset_class"].tolist(),
                sd["rwa"].tolist(),
                title="SA RWA — 자산군별 (CRE20)",
                value_fmt=_won,
                colors=[viz.PALETTE[i % len(viz.PALETTE)] for i in range(len(sd))],
            )
            sa_rows = [[row["asset_class"], int(row["n"]), _won(row["ead"]),
                        _won(row["rwa"]), _pct(row["avg_rw"], 0),
                        _pct(row["rwa_share"], 1)]
                       for _, row in sd.iterrows()]
            sa_block = f"""
<div class="card"><h2>3-1. SA 자산군별 분해 (CRE20)</h2>
<div class="chart">{sa_chart}</div>
{_table(["자산군","건수","EAD","RWA","평균 RW","RWA 비중"], sa_rows, right_cols=[1,2,3,4,5])}
</div>"""
        else:
            sa_block = ""

        # Rating × asset_class RW heatmap (avg RW)
        rm = deep.sa_rating_matrix
        if not rm.empty:
            # build matrix
            ratings = ["AAA-AA","A","BBB","BB","B","CCC-","UNRATED","N/A"]
            classes = sorted(rm["asset_class"].unique().tolist())
            ratings = [x for x in ratings if x in rm["rating"].unique()]
            mat = []
            for rt in ratings:
                row = []
                for c in classes:
                    sub = rm[(rm["rating"] == rt) & (rm["asset_class"] == c)]
                    row.append(float(sub["rwa"].sum()))
                mat.append(row)
            heat = viz_advanced.heatmap(
                ratings, classes, mat, title="등급 × 자산군 RWA (CRE20)",
                value_fmt=lambda v: f"{v/1e9:.0f}B" if v else "·",
            )
            heat_block = f'<div class="card"><h2>3-2. 등급 × 자산군 RWA 매트릭스</h2><div class="chart">{heat}</div></div>'
        else:
            heat_block = ""

        # IRB summary by class
        isum = deep.irb_summary
        if not isum.empty:
            irb_rows = [[row["asset_class"], int(row["n"]), _won(row["ead"]),
                         f"{row['pd_w']*100:.2f}%", f"{row['lgd_w']*100:.1f}%",
                         f"{row['m_w']:.2f}y" if not pd.isna(row['m_w']) else "—",
                         f"{row['k_w']*100:.2f}%", _won(row["rwa"])]
                        for _, row in isum.iterrows()]
            irb_block = f"""
<div class="card"><h2>3-3. IRB 자산군별 분해 (CRE31)</h2>
<p>가중평균 PD/LGD/M, 자본요구계수 K, RWA 요약. K = LGD·[N(·) − PD]·MA, RWA = 12.5·K·EAD.</p>
{_table(["자산군","건수","EAD","평균 PD","평균 LGD","평균 M","평균 K","RWA"], irb_rows, right_cols=[1,2,3,4,5,6,7])}
<p style="font-size:12px;color:#6b7280">상세 분포는 <a href="29_irb_deep.html">29. IRB Deep-Dive</a> 참조</p>
</div>"""
        else:
            irb_block = ""

        # Market risk by class
        mkt_d = deep.market
        if mkt_d is not None and not mkt_d.by_class.empty:
            bc = mkt_d.by_class
            mkt_chart = viz.bar_chart(
                bc["risk_class"].tolist(),
                bc["rwa"].tolist(),
                title="시장리스크 RWA — 위험클래스별 (MAR40)",
                value_fmt=_won,
                colors=[viz.PALETTE[i % len(viz.PALETTE)] for i in range(len(bc))],
            )
            mkt_block = f"""
<div class="card"><h2>3-4. 시장리스크 위험클래스 분해 (MAR40)</h2>
<div class="chart">{mkt_chart}</div>
<p style="font-size:12px;color:#6b7280">VaR/SVaR + Delta·Vega·Curvature는 <a href="30_market_risk_deep.html">30. 시장 Deep-Dive</a> 참조</p>
</div>"""
        else:
            mkt_block = ""

        # Op risk BI decomposition
        op_d = deep.op
        if op_d is not None and not op_d.bi_decomp.empty:
            bi_d = op_d.bi_decomp.iloc[:3]   # exclude total row
            op_chart = viz.bar_chart(
                bi_d["component"].tolist(),
                bi_d["value"].tolist(),
                title="Business Indicator 구성 (OPE25)",
                value_fmt=_won, colors=[viz.PALETTE[0], viz.PALETTE[1], viz.PALETTE[2]],
            )
            op_block = f"""
<div class="card"><h2>3-5. 운영리스크 BI 분해 (OPE25)</h2>
<div class="chart">{op_chart}</div>
<p style="font-size:12px;color:#6b7280">SMA vs LDA 비교는 <a href="31_op_risk_deep.html">31. 운영 Deep-Dive</a> 참조</p>
</div>"""
        else:
            op_block = ""

        # Output floor phase-in
        fs = deep.floor_schedule
        if not fs.empty:
            floor_chart = viz.line_chart(
                [str(int(y)) for y in fs["year"]],
                {"최종 RWA": fs["rwa_final"].tolist(),
                 "Floor 적용액": fs["floor_amount"].tolist()},
                title="Output floor 단계 도입 (RBC30.5)",
                value_fmt=_won,
            )
            be = deep.floor_breakeven.get("breakeven_floor", 0.0)
            floor_msg = (
                f"내부모형/표준방법 비율 = <b>{be*100:.1f}%</b>. "
                f"바젤 최종안 72.5%까지의 여유 = "
                f"<b>{(be-0.725)*100:+.1f}%p</b>. "
                "이 비율이 floor 수준 이하로 떨어지면 floor가 구속 적용됩니다."
            )
            floor_block = f"""
<div class="card"><h2>3-6. Output floor 단계 도입 (RBC30.5)</h2>
<div class="chart">{floor_chart}</div>
<div class="callout">{floor_msg}</div>
</div>"""
        else:
            floor_block = ""

        deep_html = sa_block + heat_block + irb_block + mkt_block + op_block + floor_block

    body = f"""
<h1 class="title">3. 위험가중자산(RWA) — Pillar 1</h1>
<p class="section-lead">신용·시장·운영 RWA, 표준방법 산출액, output floor 적용 결과.</p>
<div class="row2">
<div class="card"><div class="chart">{composition}</div></div>
<div class="card"><div class="chart">{cmp_chart}</div>
<div class="callout">{floor_text}</div></div>
</div>
<div class="card"><h2>구성 상세</h2>{_table(["구분","금액"], rows, right_cols=[1])}</div>
{deep_html}
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

    # Deep-dive sections (v0.8.0) — only if bis_deep is populated.
    deep = getattr(r, "bis_deep", None)
    lev_deep = getattr(r, "leverage_deep", None)
    deep_section = ""
    if deep is not None:
        layer = deep.layering; srep = deep.srep
        cet1_stack_chart = viz.stacked_bar(
            ["자본 구성"],
            {"CET1": [deep.cet1.net],
             "AT1":  [deep.at1.net],
             "Tier2":[deep.tier2.net]},
            title="총자본 구성 (CET1 + AT1 + Tier2)", value_fmt=_won,
        )
        layer_chart = viz.bar_chart(
            ["P1 (4.5%)","P1+CBR (MDA)","P1+CBR+P2R (SREP)","OCR (+P2G)","실측 CET1"],
            [layer.p1_cet1, layer.mda_threshold_cet1,
             layer.srep_cet1, layer.ocr_cet1, srep.cet1_ratio],
            value_fmt=_pct, title="요구 layer 별 vs 실측 CET1",
            colors=[viz.PALETTE[0], viz.PALETTE[1], viz.AMBER,
                    viz.RED, viz.GREEN if srep.ocr_pass else viz.RED],
            reference_value=srep.cet1_ratio,
            reference_label=f"실측 {_pct(srep.cet1_ratio)}",
        )
        srep_tone = ("good" if srep.ocr_pass
                     else ("warn" if srep.srep_pass else "bad"))
        cc_msg = (f"국가 가중 CCyB = {_pct(deep.country_ccyb['weighted_ccyb'])}"
                  if not deep.country_ccyb["by_country"].empty else "—")
        layer_rows = [
            ["Pillar 1 최저",       _pct(layer.p1_cet1),        "CRE10.4"],
            ["+ 자본보전버퍼 (CCB)", _pct(layer.capital_conservation), "RBC20.1"],
            ["+ 경기대응버퍼 (CCyB)", _pct(layer.countercyclical), "RBC20"],
            ["+ D-SIB 가산",        _pct(layer.dsib),           "RBC40"],
            ["+ P2R (감독요구)",    _pct(layer.p2r),            "SRP20"],
            ["+ P2G (감독가이드)",  _pct(layer.p2g),            "SRP20"],
            ["<b>OCR (Overall Capital Requirement)</b>",
             f"<b>{_pct(layer.ocr_cet1)}</b>", "RBC20+SRP20"],
        ]
        # Quarterly path table (5 rows: q=0..4)
        qp = deep.quarterly_path
        qp_rows = [[f"Q+{int(row['quarter'])}", _pct(row["cet1_ratio"]),
                    _pct(row["srep_threshold"]) if row["srep_threshold"] is not None else "—",
                    "<b>침범</b>" if row["breach"] else "정상",
                    row["supervisory_action"]]
                   for _, row in qp.iterrows()]

        deep_section = f"""
<div class="card"><h2>4-4. 자본 스택 구성 (CRE40) — 자세히는 § 32</h2>
<div class="chart">{cet1_stack_chart}</div>
<div class="kpi-grid">
{_kpi("CET1 (차감 후)", _won(deep.cet1.net),
       sub=f"gross {_won(deep.cet1.gross)} − 차감 {_won(deep.cet1.total_deductions)}")}
{_kpi("AT1", _won(deep.at1.net))}
{_kpi("Tier2", _won(deep.tier2.net))}
</div>
<p><a href="32_capital_stack.html">자본 스택 분해 페이지 →</a></p>
</div>

<div class="card"><h2>4-5. 자본 요구 Layering — Pillar 1 → CBR → P2R → P2G (SRP20)</h2>
<div class="chart">{layer_chart}</div>
{_table(["Layer","요구치","출처"], layer_rows, right_cols=[1])}
<div class="kpi-grid">
{_kpi("판정", srep.overall_status(), tone=srep_tone)}
{_kpi("SREP 잉여 (vs P1+CBR+P2R)",
       f"{srep.surplus_to_srep*100:+.2f}%p",
       tone="good" if srep.srep_pass else "bad")}
{_kpi("OCR 잉여 (vs OCR)",
       f"{srep.surplus_to_ocr*100:+.2f}%p",
       tone="good" if srep.ocr_pass else "warn")}
{_kpi("D-SIB 가산", _pct(layer.dsib), sub="등급 2 가정 (1.5%)")}
{_kpi("경기대응버퍼", _pct(layer.countercyclical), sub=cc_msg)}
</div>
<p><a href="33_buffer_layering.html">버퍼 layering 페이지 →</a></p>
</div>

<div class="card"><h2>4-6. CET1 분기별 시뮬레이션 (4Q forward)</h2>
{_table(["분기","CET1 비율","SREP 임계","상태","supervisory action"],
        qp_rows, right_cols=[1,2])}
<p style="font-size:12px;color:#6b7280">
이익 누적 + 배당 + 자사주 + RWA 성장 가정 하에 분기별 CET1 경로.
SREP 임계 연속 침범 시 단계별 supervisory action 표시.</p>
</div>
"""
    lev_deep_section = ""
    if lev_deep is not None:
        br = lev_deep.breakdown
        lev_comp_chart = viz.donut_chart(
            [c.name for c in br.components],
            [c.exposure for c in br.components],
            title="익스포저 측정치 분해 (LEV30)",
            center_label=f"{br.total_exposure/1e12:.1f}\n조원",
        )
        lev_deep_section = f"""
<div class="card"><h2>4-7. 익스포저 측정치 분해 + G-SIB buffer</h2>
<div class="chart">{lev_comp_chart}</div>
<div class="kpi-grid">
{_kpi("G-SIB leverage buffer", _pct(lev_deep.gsib_buffer),
       sub="= 위험기반 G-SIB buffer의 50%")}
{_kpi("최저 + G-SIB", _pct(lev_deep.requirement_total),
       tone="good" if lev_deep.passes_with_buffer else "bad")}
{_kpi("MDA 상태",
       "정상" if not lev_deep.mda.in_breach else f"{lev_deep.mda.buffer_quartile}분위 침범",
       tone="good" if not lev_deep.mda.in_breach else "bad")}
</div>
<p><a href="34_leverage_deep.html">레버리지 deep-dive 페이지 →</a></p>
</div>
"""

    body = f"""
<h1 class="title">4. BIS 자본적정성 & 레버리지</h1>
<p class="section-lead">Basel III CRE10.4 + RBC20.1 (자본보전버퍼 2.5%) 기준 비교.
v0.8.0: 자본 스택 분해 (CRE40) + buffer layering (RBC20/RBC40) + SREP/Pillar 2 + 레버리지 분해 (LEV30).</p>
<div class="row2">
<div class="card"><h2>4-1. BIS 비율</h2><div class="chart">{cet1_chart}</div>
{_table(["비율","실측","요구","잉여/부족"], rows, right_cols=[1,2,3])}
판정: {_badge("PASS" if bis.passes() else "FAIL", "PASS" if bis.passes() else "FAIL")}
</div>
<div class="card"><h2>4-2. 잉여 자본</h2><div class="chart">{surplus_chart}</div></div>
</div>
<div class="card"><h2>4-3. 레버리지 비율 (LEV10.6)</h2>
<div class="chart">{lev_chart}</div>
<div class="kpi-grid">
{_kpi("레버리지 비율", _pct(lev.leverage_ratio),
       sub=f"요구 {_pct(LEVERAGE_MIN_RATIO)}",
       tone="good" if lev.passes() else "bad")}
{_kpi("익스포저 측정치", _won(lev.exposure_measure))}
{_kpi("Tier1", _won(r.meta['capital'].tier1))}
</div>
</div>
{deep_section}
{lev_deep_section}
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

    # v0.9.0 deep-dive cross-links
    deep_block = ""
    if r.ifrs9_deep is not None:
        deep = r.ifrs9_deep
        # SICR triggers (top 3)
        s = deep.sicr.summary.sort_values("n_stage2", ascending=False).head(3)
        sicr_chart = viz.bar_chart(
            s["trigger"].tolist(), s["n_stage2"].tolist(),
            value_fmt=lambda v: f"{int(v):,}",
            title="Stage 2 진입 트리거 상위 3",
            colors=[viz.AMBER, viz.PALETTE[1], viz.PALETTE[3]],
        )
        # PD term — corporate cumulative as representative
        pdt = deep.pd_term
        corp = pdt[pdt["asset_class"] == "corporate"].sort_values("year")
        retail = pdt[pdt["asset_class"] == "retail_other"].sort_values("year")
        mort = pdt[pdt["asset_class"] == "residential_mortgage"].sort_values("year")
        pdt_series = {
            "corporate": corp["cumulative_pd"].tolist(),
            "retail_other": retail["cumulative_pd"].tolist(),
            "residential_mortgage": mort["cumulative_pd"].tolist(),
        }
        years_lbl = [str(y) for y in corp["year"].tolist()]
        pdt_chart = viz.line_chart(
            years_lbl, pdt_series, value_fmt=_pct,
            title="자산군별 누적 부도확률 (잔존기간)",
        )
        # Attribution mini waterfall
        attr = deep.attribution
        middle = attr[attr["effect"].isin(["pd", "lgd", "ead", "migration"])]
        start_v = float(attr[attr["effect"] == "start"]["value"].iloc[0])
        end_v   = float(attr[attr["effect"] == "end"]["value"].iloc[0])
        wf_chart = viz.waterfall(
            ["전기"] + middle["effect"].str.upper().tolist() + ["당기"],
            [start_v] + middle["value"].astype(float).tolist() + [end_v],
            value_fmt=_won,
            title="ECL 변화 귀속 (PD/LGD/EAD/Migration)",
        )
        deep_block = f"""
<div class="card"><h2>5-5. SICR 트리거 / PD 잔존기간 / 충당금 귀속 (요약)</h2>
<div class="row2">
<div><div class="chart">{sicr_chart}</div></div>
<div><div class="chart">{pdt_chart}</div></div>
</div>
<div class="chart">{wf_chart}</div>
<p style="font-size:12px;color:#6b7280">
상세는 35 SICR 분해 / 36 PD 잔존기간 / 37 거시 시나리오 / 38 충당금 귀속 페이지.
</p>
</div>
"""
    body = f"""
<h1 class="title">5. IFRS9 기대신용손실(ECL) 충당금</h1>
<p class="section-lead">시점추정(TTC) + 거시연계 PIT(확률가중) + 분기별 충당금 경로 + 트리거/귀속.</p>
<div class="kpi-grid">
{_kpi("TTC ECL", _won(r.ecl['total']))}
{_kpi("PIT 확률가중 ECL", _won(macro.weighted_total),
       sub=f"forward-looking uplift {(macro.weighted_total - r.ecl['total'])/1e9:+,.0f}십억", tone="warn")}
{_kpi("Stage 3 커버리지",
       f"{by_stage.loc[3, 'coverage']:.1%}" if 3 in by_stage.index else "—")}
</div>
<div class="row2">
<div class="card"><h2>5-1. Stage별 ECL</h2><div class="chart">{stage_chart}</div>
{_table(["Stage","건수","EAD","ECL","커버리지"], stage_rows, right_cols=[1,2,3,4])}
</div>
<div class="card"><h2>5-2. Stage별 커버리지</h2><div class="chart">{cov_chart}</div></div>
</div>
<div class="card"><h2>5-3. 거시연계 PIT 시나리오</h2>
<div class="row2">
<div><div class="chart">{macro_chart}</div></div>
<div>{_table(["시나리오","확률","ECL"], macro_rows, right_cols=[1,2])}</div>
</div>
</div>
<div class="card"><h2>5-4. 분기별 ECL 충당금 경로 (IFRS9 forward-looking)</h2>
<div class="chart">{path_chart}</div></div>
{deep_block}
"""
    return _page("ECL", body, "05_ecl.html")


def _page_monitoring(r: PipelineResult) -> str:
    m = r.monitoring
    delq = m["delinquency"]
    deep = r.monitoring_deep.get("delinquency") if r.monitoring_deep else None
    cure = r.monitoring_deep.get("cure") if r.monitoring_deep else None
    bucket_mx = deep.bucket_matrix if deep is not None else pd.DataFrame()
    npl = deep.npl_ratio if deep is not None else pd.DataFrame()
    dr_ts = deep.dr_timeseries if deep is not None else pd.DataFrame()
    from risk_lib import viz_advanced

    # 1) DPD bucket stacked bar (자산군 × 버킷, EAD)
    stacked_html = ""
    if not bucket_mx.empty:
        segs = sorted(bucket_mx["segment"].unique().tolist())
        from risk_lib.monitoring.deep import DEEP_DPD_LABELS
        series = {b: [float(bucket_mx[(bucket_mx["segment"] == s)
                                       & (bucket_mx["bucket"] == b)]["ead"].sum())
                       for s in segs] for b in DEEP_DPD_LABELS}
        stacked_html = viz.stacked_bar(
            segs, series, value_fmt=_won,
            title="자산군 × DPD 버킷 EAD (Basel III CRE36.69)",
        )

    # 2) DR time series chart per segment
    dr_chart = ""
    if not dr_ts.empty:
        quarters = list(pd.Categorical(dr_ts["quarter"],
                                       categories=sorted(dr_ts["quarter"].unique(),
                                                         key=lambda q: int(q.split("-")[-1]),
                                                         reverse=True)).categories)
        ser = {}
        for seg, sub in dr_ts.groupby("segment"):
            sub_sorted = sub.set_index("quarter").reindex(quarters)
            ser[seg] = sub_sorted["dr_ead"].fillna(0.0).tolist()
        dr_chart = viz.line_chart(
            quarters, ser, value_fmt=_pct,
            title="자산군별 분기 부도율 (EAD 가중, 12M rolling 합성)",
        )

    # 3) NPL ratio bar
    npl_chart = ""
    if not npl.empty:
        sub = npl[npl["segment"] != "전체"]
        npl_chart = viz.bar_chart(
            sub["segment"].tolist(), sub["npl_ratio"].tolist(),
            value_fmt=_pct, title="자산군별 NPL Ratio",
            colors=[viz.RED if v > 0.05 else (viz.AMBER if v > 0.02 else viz.GREEN)
                    for v in sub["npl_ratio"]],
        )

    # 4) Cure rate horizontal bar
    cure_chart = ""
    if cure is not None and not cure.by_segment.empty:
        c_sub = cure.by_segment[cure.by_segment["segment"] != "전체"]
        cure_chart = viz.horizontal_bar(
            c_sub["segment"].tolist(),
            c_sub["cure_rate_count"].tolist(),
            value_fmt=_pct, title="자산군별 Cure rate (건수)",
            color=viz.GREEN,
        )

    # tables
    npl_rows = []
    if not npl.empty:
        for _, row in npl.iterrows():
            npl_rows.append([row["segment"], _won(row["total_ead"]),
                             _won(row["npl_ead"]), _pct(row["npl_ratio"]),
                             f"{int(row['n_npl']):,}"])

    bucket_rows = []
    if not bucket_mx.empty:
        for _, row in bucket_mx.iterrows():
            bucket_rows.append([row["segment"], str(row["bucket"]),
                                f"{int(row['n_loans']):,}",
                                _won(row["ead"]), _pct(row["ead_share"]),
                                _pct(row["avg_pd"]) if row["avg_pd"] else "-"])

    body = f"""
<h1 class="title">6. 연체 · 부도 · 회수 모니터링 (자산건전성)</h1>
<p class="section-lead">DPD 버킷 분포 + NPL ratio + 분기 부도율 시계열 + cure rate.
기준: Basel III CRE36.69 (부도 정의), 감독세칙 자산건전성 분류, IFRS 9 5.5.5.</p>

<div class="kpi-grid">
{_kpi("부도율 (EAD 가중)", _pct(m['default_rate_ew']))}
{_kpi("부도율 (건수)", _pct(m['default_rate_count']))}
{_kpi("NPL ratio (전체)",
       _pct(float(npl[npl['segment']=='전체']['npl_ratio'].iloc[0])) if not npl.empty else "-")}
{_kpi("누적 회수율", _pct(m['recovery_rate']))}
</div>

<div class="card"><h2>6-1. 자산군 × DPD 버킷 EAD</h2>
<div class="chart">{stacked_html or "<p>데이터 없음</p>"}</div>
<p class="section-lead">버킷 정의: Current(0) · 1-29 · 30-59 · 60-89 · 90+(NPL).
90+ 는 감독세칙 상 고정/회수의문/추정손실 후보.</p>
{_table(["자산군","버킷","건수","EAD","점유율","평균 PD"], bucket_rows,
        right_cols=[2,3,4,5]) if bucket_rows else ""}
</div>

<div class="row2">
<div class="card"><h2>6-2. NPL Ratio (자산군별)</h2>
<div class="chart">{npl_chart}</div>
{_table(["자산군","총 EAD","NPL EAD","NPL ratio","NPL 건수"], npl_rows,
        right_cols=[1,2,3,4]) if npl_rows else ""}
</div>
<div class="card"><h2>6-3. 분기 부도율 시계열</h2>
<div class="chart">{dr_chart}</div>
<p class="section-lead">스냅샷 평균 기준 ±β 잡음 시뮬레이션. 시계열 회귀가 가능한
실 데이터로 교체 시 PIT vs TTC 시점 비교에도 활용.</p>
</div>
</div>

<div class="card"><h2>6-4. Cure rate — 부도 후 정상 복귀</h2>
<div class="chart">{cure_chart or "<p>데이터 없음</p>"}</div>
<p class="section-lead">window {cure.cure_window if cure else 6}개월 내 DPD 30 미만 복귀 비율.
상세는 <a href="41_cure_analysis.html">41. Cure 분석</a>.</p>
</div>

<div class="card"><h2>6-5. 자산군별 (legacy) 연체 분포</h2>
{_table(list(delq.columns),
        [[(_won(v) if isinstance(v, (int, float)) and abs(v) > 1e5 else _esc(v)) for v in row]
         for row in delq.to_numpy().tolist()],
        right_cols=list(range(1, len(delq.columns))))}
<p class="section-lead">상세 deep-dive: <a href="39_dpd_roll.html">39. DPD roll-rate</a>,
<a href="40_recovery_lgd.html">40. 회수·LGD</a>.</p>
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

    # v0.11.0 deep-dive 요약 — 다차원 한도 + escalation matrix
    deep_block = ""
    if getattr(r, "limits_deep", None) is not None:
        ld = r.limits_deep
        sev_counts = ld.dashboard["severity"].value_counts().to_dict()
        sev_chart = viz.bar_chart(
            ["OK", "WARN", "CRITICAL", "BREACH"],
            [sev_counts.get(s, 0) for s in ["OK","WARN","CRITICAL","BREACH"]],
            value_fmt=lambda v: f"{int(v):,}",
            title="severity별 한도 분포",
            colors=[viz.GREEN, viz.AMBER, "#E07A1F", viz.RED],
        )
        esc_rows = [[r2["severity"], r2["action"], r2["owner"],
                     r2["report_cycle"], r2["approval_required"]]
                    for _, r2 in ld.escalation.iterrows()]
        deep_block = f"""
<div class="row2">
<div class="card"><h2>다차원 한도 분포 (총 {len(ld.dashboard):,} 한도×버킷)</h2>
<div class="chart">{sev_chart}</div>
<p class="section-lead">상세는 <a href="42_limit_dashboard.html">42. 한도 dashboard</a>,
거대익스포저(BCBS LEX)는 <a href="43_large_exposure.html">43</a>,
스트레스 사용률은 <a href="44_concentration_stress.html">44</a>.</p>
</div>
<div class="card"><h2>escalation matrix (감독세칙 + 내규)</h2>
{_table(["severity","조치","책임자","보고주기","승인"], esc_rows)}
</div>
</div>"""

    body = f"""
<h1 class="title">7. 한도관리 & 집중리스크</h1>
<p class="section-lead">한도 사용률 (동일차주 / 섹터 / 국가) + HHI 집중도.
근거: 「은행법」 제35조, 「은행업감독규정」 제29조, BCBS 283 LEX.</p>
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
{deep_block}
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
    # ---- Du Pont decomposition deep-dive --------------------------------
    deep_block = ""
    rd = getattr(r, "rapm_deep", None)
    if rd is not None:
        dupont = rd.dupont
        dupont_rows = [[row["asset_class"], f"{int(row['n']):,}",
                        _pct(row["asset_yield"], 2),
                        f"{row['capital_velocity']:.2f}x",
                        _pct(row["efficiency"], 1),
                        _pct(row["loss_ratio"], 2),
                        _pct(row["rf_benefit"], 2),
                        _pct(row["raroc_identity"], 2)]
                       for _, row in dupont.iterrows()]
        # Waterfall for the worst (lowest RAROC) asset class
        worst_idx = dupont["raroc_identity"].idxmin()
        worst = dupont.loc[worst_idx]
        from risk_lib.performance.rapm_deep import waterfall_components
        wf_items = waterfall_components(worst)
        # waterfall() treats first/last as totals; prepend a 0 baseline so
        # the gross-spread bar is rendered as a delta from zero.
        wf_labels = ["기준(0)"] + [k for k, _ in wf_items]
        wf_values = [0.0] + [v for _, v in wf_items]
        wf_chart = viz.waterfall(
            wf_labels, wf_values, value_fmt=_pct,
            title=f"RAROC 분해 (Du Pont) — {worst['asset_class']}",
        )
        # EVA by asset class
        evac = rd.eva_by_class
        eva_chart = viz.bar_chart(
            evac["asset_class"].tolist(), evac["eva"].tolist(),
            value_fmt=_won, title="자산군별 EVA (KRW)",
            colors=[viz.GREEN if v >= 0 else viz.RED for v in evac["eva"]],
        )
        bench = rd.benchmark
        deep_block = f"""
<div class="kpi-grid">
{_kpi("가중 RAROC", _pct(rd.summary['raroc_weighted'], 2),
       sub=f"hurdle {_pct(rd.summary['hurdle_rate'])}",
       tone="good" if rd.summary['raroc_weighted'] >= rd.summary['hurdle_rate']
            else "bad")}
{_kpi("EVA 총합", _won(rd.summary['eva_total']),
       tone="good" if rd.summary['eva_total'] >= 0 else "bad")}
{_kpi("가치창출 거래 비중", _pct(rd.summary['value_creating_pct'], 1))}
{_kpi("재가격 대상 건수", f"{rd.summary['n_repricing']:,}",
       sub="RAROC ∈ [0, hurdle)", tone="warn")}
{_kpi("종결 검토 건수", f"{rd.summary['n_terminate']:,}",
       sub="RAROC < -10%", tone="bad")}
{_kpi("피어 대비", bench['position'],
       sub=f"gap {bench['gap_to_median']*100:+.2f}%p (median {_pct(bench['peer_median'])})")}
</div>

<div class="row2">
<div class="card"><h2>8-1. RAROC 분해 (Du Pont) — 최저 자산군</h2>
<div class="chart">{wf_chart}</div>
<p class="section-lead">RAROC = (수익률 × 자본속도 × 효율) − EL/EC + rf.
구성요소별 기여도 분해(BCBS RAPM appendix).</p></div>
<div class="card"><h2>8-2. 자산군별 EVA</h2>
<div class="chart">{eva_chart}</div>
<p class="section-lead">EVA = (RAROC − hurdle) × EC. 양(+)이면 자기자본비용 대비 가치 창출.</p></div>
</div>

<div class="card"><h2>8-3. Du Pont 분해 — 자산군별</h2>
{_table(["자산군","건수","수익률(R/EAD)","자본속도(EAD/EC)","효율(1-C/R)","EL/EC","rf","RAROC(재구성)"],
        dupont_rows, right_cols=[1,2,3,4,5,6,7])}
</div>
"""
    body = f"""
<h1 class="title">8. RAPM (RAROC)</h1>
<p class="section-lead">자산군별 위험조정수익률과 hurdle rate({_pct(r.meta['hurdle_rate'])}) 충족 비율.
RAROC = (순이자수익 + 수수료 − 운영비 − EL + EC·rf) / EC.
EL = PD × LGD × EAD, EC = K × EAD (Basel CRE31 IRB).</p>
<div class="row2">
<div class="card"><h2>평균 RAROC</h2><div class="chart">{raroc_chart}</div></div>
<div class="card"><h2>hurdle 충족 비율</h2><div class="chart">{pass_chart}</div></div>
</div>
<div class="card"><h2>자산군별 상세</h2>
{_table(["자산군","건수","경제자본","EL","수익","평균 RAROC","Hurdle 충족"], rows,
        right_cols=[1,2,3,4,5,6])}
</div>
{deep_block}
"""
    return _page("RAPM", body, "08_rapm.html")


def _page_stress(r: PipelineResult) -> str:
    s = r.stress.copy(); rev = r.reverse_stress
    sp = r.stress_path; troughs = r.stress_path_trough
    qs = r.meta["quarters"]
    deep = getattr(r, "stress_deep", {}) or {}

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

    # ---- v0.13.0: macro narrative table (3 시나리오 × 7 지표 × 3 horizon)
    narrative_block = ""
    if "narrative_table" in deep:
        nt = deep["narrative_table"]
        nsum = deep["narrative_summary"]
        # 시나리오별 narrative carrousel
        story_rows = "".join(
            f'<div class="callout"><b>{_esc(row["scenario"])}</b> · '
            f'peak {row["peak_year"]}Y: GDP {row["peak_gdp"]:+.1f}%, '
            f'실업률 {row["peak_unemployment"]:.1f}%, '
            f'HPI {row["peak_hpi"]:+.1f}%, BBB spread {int(row["peak_bbb_spread"])}bp'
            f'<br><span style="color:var(--muted)">{_esc(row["narrative"])}</span>'
            f'</div>'
            for _, row in nsum.iterrows()
        )
        # 시나리오별 macro 표
        macro_headers = ["시나리오", "연도", "GDP(%)", "실업률(%)", "HPI YoY(%)",
                          "정책금리(%)", "BBB(bp)", "KOSPI(%)", "USD/KRW(%)"]
        macro_rows = [[row["scenario"], row["year"],
                       f"{row['gdp_growth']:+.1f}",
                       f"{row['unemployment']:.1f}",
                       f"{row['hpi_change']:+.1f}",
                       f"{row['policy_rate']:.2f}",
                       f"{int(row['bbb_spread'])}",
                       f"{row['kospi_change']:+.1f}",
                       f"{row['fx_krw_usd']:+.1f}"]
                      for _, row in nt.iterrows()]
        narrative_block = f"""
<div class="card"><h2>9-1. 시나리오 narrative + 거시변수 path</h2>
<p class="section-lead">CCAR/DFAST 스타일 시나리오 설계서 — narrative storytelling +
1Y/2Y/3Y 거시변수 가정 (BCBS Stress testing principles §5).</p>
{story_rows}
{_table(macro_headers, macro_rows, right_cols=list(range(2,9)))}
</div>
"""

    # ---- factor decomposition (adverse + severe)
    factor_block = ""
    if "factor_decomp_adverse" in deep:
        fa = deep["factor_decomp_adverse"]
        fs = deep["factor_decomp_severe"]
        # waterfall: base → +pd → +lgd → +gdp → interaction → combined
        # For each scenario create a waterfall of CET1 deltas
        def _waterfall_rows(df):
            base_r = float(df[df["factor"]=="base"]["cet1_ratio"].iloc[0])
            comb_r = float(df[df["factor"]=="combined"]["cet1_ratio"].iloc[0])
            labels = ["base"]
            values = [base_r * 100]
            for f in ["pd", "lgd", "gdp"]:
                d = float(df[df["factor"]==f]["delta_cet1_pp"].iloc[0])
                labels.append(f"+{f.upper()}")
                values.append(d)
            inter = float(df[df["factor"]=="interaction"]["delta_cet1_pp"].iloc[0])
            labels.append("interaction")
            values.append(inter)
            labels.append("combined")
            values.append(comb_r * 100)
            return labels, values
        la_a, va_a = _waterfall_rows(fa)
        la_s, vs_s = _waterfall_rows(fs)
        # use bar_chart since waterfall has specific semantics
        chart_a = viz.bar_chart(
            la_a, va_a,
            title="adverse: factor별 CET1(%) 기여",
            value_fmt=lambda v: f"{v:+.2f}%",
            colors=[viz.PALETTE[i % len(viz.PALETTE)] for i in range(len(la_a))],
        )
        chart_s = viz.bar_chart(
            la_s, vs_s,
            title="severely_adverse: factor별 CET1(%) 기여",
            value_fmt=lambda v: f"{v:+.2f}%",
            colors=[viz.RED if "combined" in x or "interaction" in x else viz.AMBER
                    for x in la_s],
        )
        # tables
        def _fac_rows(df):
            return [[row["factor"],
                     "—" if pd.isna(row["cet1_ratio"]) else _pct(row["cet1_ratio"]),
                     f"{row['delta_cet1_pp']:+.2f}%p",
                     _won(row["ecl_uplift"])]
                    for _, row in df.iterrows()]
        factor_block = f"""
<div class="card"><h2>9-2. Factor-by-factor 분해 (PD / LGD / GDP 단독 기여)</h2>
<p class="section-lead">결합 시나리오 = PD 단독 + LGD 단독 + GDP 단독 + interaction.
어떤 factor가 자본 잠식의 marginal contribution을 주도하는지 식별.</p>
<div class="row2">
<div class="card"><h3>adverse</h3>
<div class="chart">{chart_a}</div>
{_table(["factor","CET1","Δ CET1(%p)","ECL uplift"], _fac_rows(fa), right_cols=[1,2,3])}
</div>
<div class="card"><h3>severely_adverse</h3>
<div class="chart">{chart_s}</div>
{_table(["factor","CET1","Δ CET1(%p)","ECL uplift"], _fac_rows(fs), right_cols=[1,2,3])}
</div>
</div>
</div>
"""

    # ---- asset-class sensitivity (severe)
    ac_block = ""
    if "asset_class_sens_severe" in deep:
        acs = deep["asset_class_sens_severe"]
        aca = deep["asset_class_sens_adverse"]
        chart_acs = viz.horizontal_bar(
            acs["asset_class"].tolist(),
            (acs["delta_cet1_pp"].abs() * 100).tolist(),  # bp scale
            title="severely_adverse — 자산군별 CET1 잠식 (bp)",
            value_fmt=lambda v: f"{v:.0f}bp",
            color=viz.RED,
        )
        ac_rows = [[row["asset_class"], _won(row["ead"]),
                     _pct(row["cet1_ratio"]),
                     f"{row['delta_cet1_pp']:+.2f}%p",
                     _won(row["ecl_uplift"]),
                     f"{row['share_of_total_drop_pp']*100:.1f}%"]
                    for _, row in acs.iterrows()]
        aca_rows = [[row["asset_class"], f"{row['delta_cet1_pp']:+.2f}%p",
                      f"{row['share_of_total_drop_pp']*100:.1f}%"]
                     for _, row in aca.iterrows()]
        ac_block = f"""
<div class="card"><h2>9-3. 자산군별 시나리오 sensitivity</h2>
<p class="section-lead">각 자산군 단독 충격 시 portfolio 전체 CET1 영향 — 어느 자산군이
스트레스에 가장 취약한지 식별.</p>
<div class="row2">
<div class="card"><h3>severely_adverse (자산군 단독 적용)</h3>
<div class="chart">{chart_acs}</div>
{_table(["자산군","EAD","CET1","ΔCET1","ECL uplift","총하락 기여"],
        ac_rows, right_cols=[1,2,3,4,5])}
</div>
<div class="card"><h3>adverse (자산군 단독 적용)</h3>
{_table(["자산군","ΔCET1","총하락 기여"], aca_rows, right_cols=[1,2])}
</div>
</div>
</div>
"""

    body = f"""
<h1 class="title">9. 스트레스테스트 — CRO 종합</h1>
<p class="section-lead">시나리오 narrative + factor 분해 + 자산군 sensitivity +
역스트레스 + 3년 분기 경로. 상세 multi-target 역스트레스/CCAR/기후/유동성은
<a href="48_reverse_stress_multi.html">48</a>·<a href="49_ccar_path.html">49</a>·<a href="50_climate_capital.html">50</a>·<a href="51_liquidity_stress.html">51</a>.</p>

{narrative_block}

<div class="row2">
<div class="card"><h2>9-4. 시나리오별 CET1 (단년)</h2><div class="chart">{cet1_chart}</div>
{_table(["시나리오","RWA","ECL","CET1","잉여","판정"], s_rows, right_cols=[1,2,3,4])}
</div>
<div class="card"><h2>9-5. 분기별 CET1 경로 (2Y)</h2><div class="chart">{path_chart}</div>
{_table(["시나리오","최저 CET1","최저 시점","기말 CET1","최초 위반","전구간"], t_rows, right_cols=[1,3])}
</div>
</div>

{factor_block}
{ac_block}

<div class="card"><h2>9-6. 역스트레스테스트 (CET1 임계 시나리오)</h2>
<div class="kpi-grid">
{_kpi("기준 CET1", _pct(rev.base_ratio))}
{_kpi("임계(버퍼포함 요구)", _pct(rev.target_ratio))}
{_kpi("임계 심도 s", f"{rev.critical_severity:.2f}")}
</div>
{rev_block}
<p class="section-lead">multi-target (CET1/Tier1/LCR/NSFR) 역스트레스는
<a href="48_reverse_stress_multi.html">48번 페이지</a> 참조.</p>
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
    from risk_lib.validation.cross_domain import domain_status, DOMAINS
    v = r.validation
    summ = v.summary()
    # rows
    rows = [[c.name, _badge(c.status, c.status), c.detail] for c in v.checks]
    cite_rows = [[section, c.standard, c.section, c.note]
                 for section, c in ALL_CITATIONS]
    # 8-부문 정합성 매트릭스 (BCBS 239 — 위험 집계의 완전성 · 정확성)
    dom_st = domain_status(v.checks)
    matrix_rows = [
        [dom_st[k]["label"], _badge(dom_st[k]["status"], dom_st[k]["status"]),
         f"{dom_st[k]['n_pass']}/{dom_st[k]['n_warn']}/{dom_st[k]['n_fail']}",
         "·".join(dom_st[k]["details"][:2]) or "—"]
        for k, _ in DOMAINS
    ]
    # cross-domain 만 분리해서 표시
    xd_rows = [[c.name, _badge(c.status, c.status), c.detail]
               for c in v.checks if c.name.startswith("xd_")]
    body = f"""
<h1 class="title">12. 자체검증 + 출처/준거</h1>
<p class="section-lead">감독세칙 자체검증 + BCBS 239 (Principles for Effective
Risk Data Aggregation) — FAIL 0건이어야 결재 가능.</p>
<div class="kpi-grid">
{_kpi("PASS", f"{summ.get('PASS',0)}", tone="good")}
{_kpi("WARN", f"{summ.get('WARN',0)}", tone="warn")}
{_kpi("FAIL", f"{summ.get('FAIL',0)}", tone="bad")}
{_kpi("종합", "결재 가능" if v.passes() else "결재 불가",
       tone=("good" if v.passes() else "bad"))}
</div>
<div class="card"><h2>8 부문 정합성 매트릭스</h2>
<p class="section-lead">부문별 PASS/WARN/FAIL 카운트 · 한 부문이라도 FAIL이면 종합 FAIL.</p>
{_table(["부문","상태","P/W/F","주요 지적"], matrix_rows)}
</div>
<div class="card"><h2>Cross-domain 정합성 ({len(xd_rows)}건)</h2>
<p class="section-lead">PD↔RWA · RWA↔BIS · ECL↔RWA · 한도↔집중 · RAPM↔EC · 스트레스↔BIS</p>
{_table(["체크","상태","상세"], xd_rows) if xd_rows else "<p>해당 없음</p>"}
</div>
<div class="card"><h2>전 체크 상세 ({len(v.checks)}건)</h2>
{_table(["체크","상태","상세"], rows)}
</div>
<div class="card"><h2>출처 및 준거</h2>
{_table(["섹션","표준","항목","비고"], cite_rows)}
</div>
"""
    return _page("자체검증", body, "12_validation.html")


def _page_final_attestation(r: PipelineResult) -> str:
    """52. CRO 결재용 최종 attestation (v0.14.0).

    8 부문 카드 · cross-domain 매트릭스 · 결재 가능/불가 verdict · 서명란.
    """
    from risk_lib.validation.cross_domain import domain_status, DOMAINS
    v = r.validation
    summ = v.summary()
    dom_st = domain_status(v.checks)
    passes = v.passes()

    # Each domain card surfaces a headline metric + status.
    headline_by_dom = {
        "pd": f"세그먼트 {len(r.pd_metrics)} · HL p={r.backtest['hosmer_lemeshow']['p_value']:.3f}",
        "rwa": f"최종 RWA {_won(r.rwa['final_total'])} · "
               f"SA {_won(r.rwa['sa'])} · IRB {_won(r.rwa['irb'])}",
        "bis": f"CET1 {_pct(r.bis.cet1_ratio)} · 레버리지 {_pct(r.leverage.leverage_ratio)}",
        "ecl": f"TTC {_won(r.ecl['total'])} · PIT 가중 {_won(r.macro_ecl.weighted_total)}",
        "monitoring": f"부도율(EW) {_pct(r.monitoring['default_rate_ew'])} · "
                      f"회수율 {_pct(r.monitoring['recovery_rate'])}",
        "limits": f"경보 {len(r.limits)}건 · sector HHI "
                  f"{r.concentration[r.concentration['dimension']=='sector']['hhi'].iloc[0]:.3f}",
        "rapm": f"가중 RAROC {_pct(r.rapm_deep.summary['raroc_weighted'])} · "
                f"hurdle 통과 {_pct(r.rapm_deep.summary['pass_hurdle_pct'])}",
        "stress": f"baseline CET1 {_pct(r.stress.iloc[0]['cet1_ratio'])} · "
                  f"severe CET1 {_pct(r.stress.iloc[-1]['cet1_ratio'])}",
    }

    dom_cards = []
    for key, label in DOMAINS:
        st = dom_st[key]
        tone = {"PASS": "good", "WARN": "warn", "FAIL": "bad"}[st["status"]]
        head = headline_by_dom.get(key, "—")
        dom_cards.append(
            _kpi(label, st["status"],
                 sub=f"{head} · P/W/F={st['n_pass']}/{st['n_warn']}/{st['n_fail']}",
                 tone=tone)
        )

    # cross-domain validation matrix
    xd_rows = [[c.name, _badge(c.status, c.status), c.detail]
               for c in v.checks if c.name.startswith("xd_")]

    # FAIL/WARN 상세
    issue_rows = [[c.name, _badge(c.status, c.status), c.detail]
                  for c in v.checks if c.status != "PASS"]

    verdict_tone = "good" if passes else "bad"
    verdict_text = "결재 가능 (PASS)" if passes else "결재 불가 (FAIL)"
    verdict_lead = ("FAIL 0건 — 모든 부문 정합성 충족, CRO 결재 가능."
                    if passes else
                    "FAIL 발생 — 결재 불가, 원인 부문 재산출 필요.")

    seed = r.meta.get("seed", "—")
    asof = r.meta.get("asof", date.today().isoformat())

    body = f"""
<h1 class="title">52. 최종 결재 attestation — v0.14.0</h1>
<p class="section-lead">감독세칙 자체검증 + BCBS 239 (Principles for Effective
Risk Data Aggregation) 기반 8 부문 통합 결재 페이지.</p>

<div class="card {'good' if passes else 'bad'}">
<h2>종합 판정</h2>
<div class="kpi-grid">
{_kpi("종합 판정", verdict_text, tone=verdict_tone)}
{_kpi("PASS", f"{summ.get('PASS',0)}건", tone="good")}
{_kpi("WARN", f"{summ.get('WARN',0)}건", tone="warn")}
{_kpi("FAIL", f"{summ.get('FAIL',0)}건", tone="bad")}
</div>
<p>{_esc(verdict_lead)}</p>
<p><b>산출 기준일</b> {_esc(asof)} · <b>seed</b> {_esc(seed)} ·
<b>검증 체크 수</b> {len(v.checks)}건</p>
</div>

<div class="card"><h2>8 부문 결재 카드</h2>
<div class="kpi-grid">
{''.join(dom_cards)}
</div>
</div>

<div class="card"><h2>Cross-domain 정합성 매트릭스 ({len(xd_rows)}건)</h2>
<p class="section-lead">부문 경계를 가로지르는 정합성:
PD↔RWA · RWA↔BIS · ECL↔RWA · 한도↔집중 · RAPM↔EC · 스트레스↔BIS · 재현성.</p>
{_table(["체크","상태","상세"], xd_rows) if xd_rows else "<p>해당 없음</p>"}
</div>

<div class="card"><h2>WARN/FAIL 상세 ({len(issue_rows)}건)</h2>
{_table(["체크","상태","상세"], issue_rows) if issue_rows else "<p>해당 없음 — 전 체크 PASS</p>"}
</div>

<div class="card"><h2>결재 서명란</h2>
<table class="t">
<thead><tr><th>역할</th><th>성명</th><th>일자</th><th>서명</th></tr></thead>
<tbody>
<tr><td>산출 책임자 (리스크 분석부장)</td><td>____________________</td>
<td>{_esc(asof)}</td><td>____________________</td></tr>
<tr><td>검증 책임자 (모형검증실장)</td><td>____________________</td>
<td>{_esc(asof)}</td><td>____________________</td></tr>
<tr><td>최종 결재 (CRO)</td><td>____________________</td>
<td>{_esc(asof)}</td><td>____________________</td></tr>
</tbody>
</table>
<p style="color:var(--muted); font-size:12px; margin-top:14px;">
본 attestation 페이지는 감독세칙 자체검증 + BCBS 239 원칙에 따라 자동 생성되었으며,
CRO 서명 전 산출/검증 책임자의 사전 결재가 요구됩니다.</p>
</div>
"""
    return _page("최종 attestation", body, "52_final_attestation.html")


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
        page_data_quality, page_comparison,
        page_irb_deep, page_market_risk_deep, page_op_risk_deep,
        page_capital_stack, page_buffer_layering, page_leverage_deep,
        page_sicr_detail, page_pd_term_structure,
        page_macro_scenario, page_provisioning_attribution,
        page_dpd_roll, page_recovery_lgd, page_cure_analysis,
        page_limit_dashboard, page_large_exposure, page_concentration_stress,
        page_eva_sva, page_pricing_breakeven, page_rapm_scenario,
        page_reverse_stress_multi, page_ccar_path,
        page_climate_capital, page_liquidity_stress,
        page_xva_full, page_trading_sensitivities, page_scenario_library,
        page_frtb_ima, page_model_inventory,
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
        "26_comparison.html": page_comparison(result),
        "27_lgd_model.html":  _page_lgd_model(result),
        "28_model_challenger.html": _page_model_challenger(result),
        "29_irb_deep.html":   page_irb_deep(result),
        "30_market_risk_deep.html": page_market_risk_deep(result),
        "31_op_risk_deep.html": page_op_risk_deep(result),
        "32_capital_stack.html": page_capital_stack(result),
        "33_buffer_layering.html": page_buffer_layering(result),
        "34_leverage_deep.html": page_leverage_deep(result),
        "35_sicr_detail.html":   page_sicr_detail(result),
        "36_pd_term_structure.html": page_pd_term_structure(result),
        "37_macro_scenario.html":    page_macro_scenario(result),
        "38_provisioning_attribution.html": page_provisioning_attribution(result),
        "39_dpd_roll.html":            page_dpd_roll(result),
        "40_recovery_lgd.html":        page_recovery_lgd(result),
        "41_cure_analysis.html":       page_cure_analysis(result),
        "42_limit_dashboard.html":     page_limit_dashboard(result),
        "43_large_exposure.html":      page_large_exposure(result),
        "44_concentration_stress.html": page_concentration_stress(result),
        "45_eva_sva.html":             page_eva_sva(result),
        "46_pricing_breakeven.html":   page_pricing_breakeven(result),
        "47_rapm_scenario.html":       page_rapm_scenario(result),
        "48_reverse_stress_multi.html": page_reverse_stress_multi(result),
        "49_ccar_path.html":            page_ccar_path(result),
        "50_climate_capital.html":      page_climate_capital(result),
        "51_liquidity_stress.html":     page_liquidity_stress(result),
        "52_final_attestation.html":    _page_final_attestation(result),
        "53_xva_full.html":             page_xva_full(result),
        "54_trading_sensitivities.html": page_trading_sensitivities(result),
        "55_scenario_library.html":      page_scenario_library(result),
        "56_frtb_ima.html":              page_frtb_ima(result),
        "57_model_inventory.html":       page_model_inventory(result),
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
    from risk_lib.printable import build_printable_html
    from risk_lib.audit_trail import build_ledger_from_result
    from risk_lib.board_pack import build_board_pack
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    ops_dir = out / "ops"
    written_ops = build_report_set(result, ops_dir, portfolio=portfolio)
    exec_path = build_executive(result, out,
                                manifest_digest=getattr(manifest, "headline_digest", ""))
    # printable HTML is the recommended PDF route — browser Print-to-PDF
    printable_path = build_printable_html(result, out / "printable.html",
                                           manifest=manifest)
    manifest_path = None
    if manifest is not None:
        manifest_path = out / "manifest.json"
        manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    # Audit ledger + Risk Committee board pack (Top-IB style)
    git_commit = (manifest.code.get("git_commit", "")
                  if manifest is not None else "")
    ledger = build_ledger_from_result(result, git_commit=git_commit or "")
    ledger_path = ledger.export_json(out / "audit_ledger.json")
    board_pack_path = build_board_pack(
        result, out / "board_pack.html",
        ledger_path=str(out / "audit_ledger.json"),
    )
    return {
        "executive": str(exec_path.resolve()),
        "printable": str(printable_path),
        "board_pack": board_pack_path,
        "audit_ledger": ledger_path,
        "ops_dir": str(ops_dir.resolve()),
        **{f"ops/{k}": v for k, v in written_ops.items()},
        **({"manifest": str(manifest_path.resolve())} if manifest_path else {}),
    }
