"""Print-optimised single-file HTML — for browser "Print to PDF".

Rationale: Korean PDF generation without fonttools is fragile. Every modern
browser's print-to-PDF supports Korean perfectly using system fonts, and
that's the workflow real banks use for board-pack distribution.

build_printable_html(result, manifest) writes one HTML file with:
  - inline CSS @page rules (A4 portrait, 15mm margins)
  - page-break-inside: avoid on each card / chart
  - the executive layout (cover, RAF scorecard, top actions, capital +
    liquidity KPIs, sector x country heatmap, stress fan, MDA gauge)
  - the full reproducibility footer

To produce a PDF the user opens this file in any browser and chooses
"Print -> Save as PDF" (or "Print to PDF"). Korean renders perfectly via
the OS font stack (e.g. Apple SD Gothic Neo / Malgun Gothic / Noto CJK).
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import _won, _pct, _esc, _table
from risk_lib.html_exec import _kri_card_data, _top_actions
from risk_lib.references import (
    LCR_MIN, NSFR_MIN, IRRBB_OUTLIER_EVE_PCT_TIER1, LEVERAGE_MIN_RATIO,
)


PRINT_CSS = """
@page { size: A4 portrait; margin: 12mm 15mm; }
html, body { background: white; margin: 0; padding: 0; color: #1a202c;
  font-family: "Apple SD Gothic Neo","Malgun Gothic","Noto Sans CJK KR",
               "Segoe UI", sans-serif; font-size: 11pt; }
.container { max-width: 720px; margin: 0 auto; padding: 0; }
h1 { font-size: 20pt; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin: 12pt 0 4pt; padding-bottom: 4pt;
  border-bottom: 1pt solid #cbd5e0; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 8pt 0 4pt; page-break-after: avoid; }
p, li { line-height: 1.5; margin: 4pt 0; }
.meta { color: #6b7280; font-size: 9pt; margin: 0 0 12pt; }
.verdict-pass { background: #d3eedd; color: #1f7437; padding: 4pt 8pt;
  border-radius: 4pt; display: inline-block; font-weight: 700; }
.verdict-fail { background: #fbd7d5; color: #a3160d; padding: 4pt 8pt;
  border-radius: 4pt; display: inline-block; font-weight: 700; }
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr 1fr;
  gap: 6pt; margin: 6pt 0 10pt; page-break-inside: avoid; }
.kpi { background: #f9fafb; border: 0.5pt solid #cbd5e0; padding: 6pt 8pt;
  border-radius: 4pt; }
.kpi .lbl { font-size: 8pt; color: #6b7280; text-transform: uppercase;
  letter-spacing: 0.05em; }
.kpi .val { font-size: 13pt; font-weight: 700; margin-top: 2pt; }
.kpi .sub { font-size: 8pt; color: #6b7280; margin-top: 1pt; }
.kpi.good .val { color: #1f7437; }
.kpi.warn .val { color: #8a5b00; }
.kpi.bad  .val { color: #a3160d; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt;
  margin: 4pt 0 10pt; page-break-inside: auto; }
table th, table td { border: 0.5pt solid #cbd5e0; padding: 3pt 6pt;
  vertical-align: top; text-align: left; }
table th { background: #f3f4f6; font-weight: 600; font-size: 8.5pt;
  text-transform: uppercase; letter-spacing: 0.03em; }
table td.r, table th.r { text-align: right; font-variant-numeric: tabular-nums; }
.card { page-break-inside: avoid; margin: 8pt 0; }
.action { background: white; border-left: 3pt solid #c5221f; padding: 4pt 10pt;
  margin: 3pt 0; font-size: 10pt; page-break-inside: avoid; }
.action.amber { border-left-color: #e8a33d; }
.action.watch { border-left-color: #88a4c2; }
.badge { display: inline-block; padding: 1pt 7pt; border-radius: 8pt;
  font-size: 8pt; font-weight: 600; letter-spacing: 0.04em; }
.badge.GREEN, .badge.PASS { background: #d3eedd; color: #1f7437; }
.badge.WATCH, .badge.WARN, .badge.AMBER { background: #fdebcb; color: #8a5b00; }
.badge.RED, .badge.FAIL { background: #fbd7d5; color: #a3160d; }
.cite { font-size: 8pt; color: #6b7280; }
.chart { margin: 4pt 0 8pt; page-break-inside: avoid; }
.footer-repro { font-family: Menlo, Consolas, monospace; font-size: 8pt;
  color: #6b7280; background: #f9fafb; padding: 6pt 10pt;
  border: 0.5pt solid #e5e7eb; border-radius: 4pt; word-break: break-all;
  margin-top: 14pt; page-break-inside: avoid; }
.print-tip { background: #e7eef6; border: 0.5pt solid #88a4c2; padding: 6pt 10pt;
  border-radius: 4pt; font-size: 9.5pt; margin: 8pt 0; }
@media print { .print-tip { display: none; } }
"""


def _kpi(lbl, val, sub="", tone=""):
    cls = f" {tone}" if tone else ""
    sub_html = f'<div class="sub">{_esc(sub)}</div>' if sub else ""
    return (f'<div class="kpi{cls}"><div class="lbl">{_esc(lbl)}</div>'
            f'<div class="val">{_esc(val)}</div>{sub_html}</div>')


def build_printable_html(result: PipelineResult, out_path,
                          *, manifest=None) -> str:
    v = result.validation; summ = v.summary()
    passes = v.passes()
    verdict_class = "verdict-pass" if passes else "verdict-fail"
    verdict_text = "결재 가능 (PASS)" if passes else "결재 불가 (FAIL)"
    raf = result.raf
    raf_summ = raf.summary(); raf_worst = raf.worst()

    bis = result.bis; lev = result.leverage
    lcr = result.alm["lcr"]; nsfr = result.alm["nsfr"]; irrbb = result.alm["irrbb"]

    # ---- KRI scorecard (SVG inline)
    scorecard = viz_advanced.kri_scorecard(_kri_card_data(raf))

    # ---- top actions
    actions = _top_actions(result, max_actions=8)
    actions_html = "".join(
        f'<div class="action{" amber" if "[AMBER]" in a else (" watch" if "[WATCH]" in a else "")}">{a}</div>'
        for a in actions) or '<div class="action" style="border-left-color:#1f7437">조치 필요 항목 없음 — 모든 KRI 정상</div>'

    # ---- MDA card
    from risk_lib.mda import compute_mda
    mda = compute_mda(
        bis.cet1_ratio, result.meta["capital"].cet1, bis.rwa,
        buffers={"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01},
    )
    mda_tone = "good" if not mda.in_breach else "bad"
    mda_text = ("자유로운 분배 가능" if not mda.in_breach
                else f"분배제한 q{mda.buffer_quartile} ({_pct(mda.distributable_pct)})")

    # ---- sector x country heatmap
    sc = result.concentration_deep["sector_country"]
    sectors = list(sc.index); countries = list(sc.columns)
    matrix = [[float(sc.loc[s, c]) for c in countries] for s in sectors]
    heat = viz_advanced.heatmap(
        sectors, countries, matrix,
        title="섹터 x 국가 EAD 노출 (조원)",
        value_fmt=lambda x: f"{x/1e12:.1f}", cell_label=True,
        width=680, height=240,
    )

    # ---- stress fan
    qs = result.meta["quarters"]
    sp = result.stress_path
    base_path = sp[sp["scenario"] == "baseline"].sort_values("q_index")["cet1_ratio"].tolist()
    adv_path  = sp[sp["scenario"] == "adverse"].sort_values("q_index")["cet1_ratio"].tolist()
    sev_path  = sp[sp["scenario"] == "severely_adverse"].sort_values("q_index")["cet1_ratio"].tolist()
    fan = ""
    if len(base_path) and len(adv_path) and len(sev_path):
        lower = [min(a, s) for a, s in zip(adv_path, sev_path)]
        upper = [max(b, a) for b, a in zip(base_path, adv_path)]
        fan = viz_advanced.fan_chart(
            qs, base_path, lower, upper,
            extra_series={"adverse": adv_path, "severely_adverse": sev_path},
            value_fmt=_pct, title="분기별 CET1 경로 — fan chart",
            reference_value=bis.required["cet1"],
            reference_label=f"요구 {_pct(bis.required['cet1'])}",
            width=680, height=240,
        )

    # ---- KRI table (compact, for printed page)
    kri_rows = []
    for k in raf.kris:
        actual = (_pct(k.actual) if k.fmt == "pct" else
                  f"{k.actual:.3f}" if k.fmt == "ratio" else _won(k.actual))
        board = (_pct(k.threshold.board) if k.fmt == "pct" else
                 f"{k.threshold.board:.3f}")
        kri_rows.append([k.category, k.name, actual, board,
                         f'<span class="badge {k.grade}">{k.grade}</span>'])

    # ---- KM1-style summary
    km1_rows = [
        ["CET1 비율", _pct(bis.cet1_ratio), _pct(bis.required["cet1"]),
         f"{bis.surplus_shortfall['cet1']*100:+.2f}%p"],
        ["Tier1 비율", _pct(bis.tier1_ratio), _pct(bis.required["tier1"]),
         f"{bis.surplus_shortfall['tier1']*100:+.2f}%p"],
        ["총자본 비율", _pct(bis.total_ratio), _pct(bis.required["total"]),
         f"{bis.surplus_shortfall['total']*100:+.2f}%p"],
        ["레버리지 비율", _pct(lev.leverage_ratio), _pct(LEVERAGE_MIN_RATIO),
         f"{(lev.leverage_ratio - LEVERAGE_MIN_RATIO)*100:+.2f}%p"],
        ["LCR", _pct(lcr.lcr, 1), _pct(LCR_MIN, 0),
         f"{(lcr.lcr - LCR_MIN)*100:+.2f}%p"],
        ["NSFR", _pct(nsfr.nsfr, 1), _pct(NSFR_MIN, 0),
         f"{(nsfr.nsfr - NSFR_MIN)*100:+.2f}%p"],
        ["IRRBB ΔEVE/Tier1", _pct(irrbb.worst_pct_tier1),
         f"≤ {_pct(IRRBB_OUTLIER_EVE_PCT_TIER1, 0)}",
         f"{(IRRBB_OUTLIER_EVE_PCT_TIER1 - irrbb.worst_pct_tier1)*100:+.2f}%p 잉여"],
    ]

    repro = (f"산출시각 {result.meta.get('asof', '-')} · seed {result.meta.get('seed')} · "
             f"포트폴리오 {int(result.portfolio_summary['n'].sum()):,}건 · "
             f"manifest digest {manifest.headline_digest[:24] if manifest else '-'}...")

    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>리스크관리 종합 보고서 — 경영진 요약 (인쇄용)</title>
<style>{PRINT_CSS}</style>
</head>
<body>
<div class="container">

<div class="print-tip">
<b>📄 PDF로 저장하려면:</b> 브라우저 메뉴에서
<b>인쇄 (Ctrl/⌘+P)</b> &rarr; <b>대상: PDF로 저장</b> &rarr;
용지 A4, 여백 기본값으로 저장.
한국어 폰트가 OS에서 자동으로 사용되어 깨지지 않습니다.
</div>

<h1>리스크관리 종합 보고서 — 경영진 요약</h1>
<div class="meta">
산출 기준 {_esc(result.meta.get('asof', '-'))} ·
seed {_esc(result.meta.get('seed'))} ·
준거 Basel III + IFRS9 + 금감원 감독세칙
</div>

<h2>0. 최종 판정</h2>
<p><span class="{verdict_class}">{_esc(verdict_text)}</span>
&nbsp; — 자체검증 PASS {summ.get('PASS',0)} / WARN {summ.get('WARN',0)} / FAIL {summ.get('FAIL',0)},
RAF 최악 등급 <span class="badge {raf_worst}">{_esc(raf_worst)}</span>
(GREEN {raf_summ.get('GREEN',0)} · WATCH {raf_summ.get('WATCH',0)} ·
AMBER {raf_summ.get('AMBER',0)} · RED {raf_summ.get('RED',0)})</p>

<h2>1. 자본·유동성 핵심 지표</h2>
<div class="kpi-grid">
{_kpi("CET1 비율", _pct(bis.cet1_ratio), sub=f"요구 {_pct(bis.required['cet1'])}", tone="good" if bis.passes() else "bad")}
{_kpi("Tier1", _pct(bis.tier1_ratio))}
{_kpi("Total", _pct(bis.total_ratio))}
{_kpi("레버리지", _pct(lev.leverage_ratio), sub=f"요구 {_pct(LEVERAGE_MIN_RATIO)}", tone="good" if lev.passes() else "bad")}
{_kpi("ICAAP 사용률", _pct(result.icaap.utilisation,1), sub=result.icaap.grade, tone={"GREEN":"good","AMBER":"warn","RED":"bad"}[result.icaap.grade])}
{_kpi("MDA 분배", mda_text, tone=mda_tone)}
{_kpi("LCR", _pct(lcr.lcr,1), sub=f"기준 {_pct(LCR_MIN,0)}", tone="good" if lcr.passes() else "bad")}
{_kpi("NSFR", _pct(nsfr.nsfr,1), sub=f"기준 {_pct(NSFR_MIN,0)}", tone="good" if nsfr.passes() else "bad")}
{_kpi("IRRBB ΔEVE/Tier1", _pct(irrbb.worst_pct_tier1), sub=f"기준 ≤{_pct(IRRBB_OUTLIER_EVE_PCT_TIER1,0)}", tone="good" if not irrbb.outlier() else "bad")}
</div>

<div class="card">
{_table(["지표","실측","요구","잉여/부족"], km1_rows, right_cols=[1,2,3])}
</div>

<h2>2. RAF KRI 스코어카드</h2>
<div class="card">{scorecard}</div>
<div class="card">
{_table(["분류","KRI","실측","board 한계","등급"], kri_rows, right_cols=[2,3])}
</div>

<h2>3. CRO 액션 (상위 {len(actions)}건)</h2>
{actions_html}

<h2>4. 리스크 프로파일 — 섹터 × 국가 노출</h2>
<div class="chart">{heat}</div>
<p class="cite">색이 진할수록 노출 규모가 큽니다. 단일 셀이 전체의 8% 이상이면 집중리스크 deep-dive 점검 필요.</p>

<h2>5. 스트레스 시나리오 — 자본경로</h2>
<div class="chart">{fan}</div>
<p>역스트레스 임계심도 s = <b>{result.reverse_stress.critical_severity:.2f}</b>
(함의 GDP <b>{result.reverse_stress.implied_gdp_shock:+.1%}</b>,
LGD <b>+{result.reverse_stress.implied_lgd_addon:.1%}p</b>)</p>

<h2>6. 비신용 리스크 요약</h2>
<div class="kpi-grid">
{_kpi("CCR EAD", _won(result.ccr.ead_total) if result.ccr else "-")}
{_kpi("CVA 자본", _won(result.ccr.cva_charge) if result.ccr else "-")}
{_kpi("운영손실 99.9% VaR", _won(result.op_loss.var_99_9))}
{_kpi("기후 최악 ECL uplift",
       _won(max(l.uplift for l in result.climate.transition + result.climate.physical)))}
</div>

<h2>7. 재현성 (감사 추적)</h2>
<div class="footer-repro">
{_esc(repro)}<br>
재현 명령: <code>python -m risk_lib.cli reproduce --manifest manifest.json</code><br>
실무진 deep-dive 30+ 페이지는 동봉 HTML 보고서(executive.html / ops/) 참조.
</div>

</div>
</body></html>"""

    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return str(p.resolve())
