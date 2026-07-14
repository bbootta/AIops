"""Risk Committee Board Pack — Top-IB style monthly/quarterly meeting dossier.

A 12-page formal dossier formatted for the Risk Committee meeting:
  Page 1: Cover + verdict
  Page 2: Executive summary + top 5 issues
  Page 3: KRI traffic light dashboard
  Page 4: Capital position + buffer status
  Page 5: Liquidity position + LCR/NSFR drilldown
  Page 6: Credit risk — portfolio, NPL, ECL allowance
  Page 7: Market risk — VaR, Greeks, FRTB readiness
  Page 8: Operational risk — incidents, LDA, SMA
  Page 9: Stress test results — base/adverse/severe
  Page 10: Scenario library status + new scenarios
  Page 11: Action items — owner / deadline / status
  Page 12: Audit trail + reproducibility certificate

Designed for printed A4 distribution + electronic signing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from risk_lib import viz, viz_advanced
from risk_lib.html_report import CSS, _won, _pct, _esc, _table, _kpi, _badge
from risk_lib.abbreviations import abbr_dict_card_html


_BOARD_CSS = """
@page { size: A4; margin: 12mm 15mm; }
body { font-family: 'Apple SD Gothic Neo','Malgun Gothic','Noto Sans CJK KR','Segoe UI',sans-serif;
  font-size: 11pt; color: #1a202c; background: #fff; margin: 0; }
.page { page-break-after: always; padding: 8mm 0; min-height: 240mm; }
.page:last-child { page-break-after: auto; }
.cover { background: linear-gradient(180deg,#1a2236 0%,#2d3a5a 100%); color: #fff;
  padding: 50mm 20mm; min-height: 240mm; page-break-after: always; }
.cover h1 { font-size: 28pt; margin: 0 0 20pt; }
.cover .meta { font-size: 12pt; opacity: 0.9; }
.cover .verdict { display: inline-block; padding: 10pt 22pt; border-radius: 8pt;
  background: rgba(255,255,255,0.15); font-weight: 700; font-size: 16pt; margin-top: 20pt; }
.section-num { color: #6b7280; font-size: 10pt; font-weight: 600;
  letter-spacing: 0.1em; text-transform: uppercase; }
h2 { font-size: 18pt; margin: 4pt 0 12pt; color: #1f2937; }
h3 { font-size: 13pt; margin: 12pt 0 6pt; color: #374151; }
.kpi-row { display: flex; gap: 8pt; margin: 6pt 0 10pt; }
.kpi-box { flex: 1; background: #f9fafb; border: 0.5pt solid #cbd5e0;
  padding: 8pt 10pt; border-radius: 4pt; }
.kpi-lbl { font-size: 8pt; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-val { font-size: 14pt; font-weight: 700; margin-top: 2pt; }
.kpi-val.good { color: #1f7437; }
.kpi-val.bad  { color: #a3160d; }
.kpi-val.warn { color: #8a5b00; }
.kpi-sub { font-size: 9pt; color: #6b7280; margin-top: 2pt; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 4pt 0 10pt; }
table th, table td { border: 0.5pt solid #cbd5e0; padding: 3pt 6pt;
  vertical-align: top; text-align: left; }
table th { background: #f3f4f6; font-weight: 600; font-size: 8.5pt;
  text-transform: uppercase; letter-spacing: 0.03em; }
.action-card { background: #fffbea; border-left: 3pt solid #e8a33d;
  padding: 6pt 12pt; margin: 5pt 0; border-radius: 0 4pt 4pt 0; }
.action-card.bad { background: #fdecea; border-left-color: #a3160d; }
.action-card.good { background: #eef9f1; border-left-color: #1f7437; }
.sign-box { display: inline-block; border: 0.5pt solid #6b7280;
  padding: 8pt 16pt; margin: 6pt; min-width: 28%; }
.sign-box .role { font-size: 8pt; color: #6b7280; text-transform: uppercase; }
.sign-box .name { font-weight: 700; margin-top: 2pt; }
.sign-box .sig-line { border-bottom: 0.5pt solid #1a202c; margin-top: 16pt; }
.cite { font-size: 8pt; color: #6b7280; }
"""


def _cover(result, *, meeting_date: str) -> str:
    v = result.validation
    summ = v.summary()
    passes = v.passes()
    raf_worst = result.raf.worst() if result.raf else "—"
    verdict_text = "결재 가능 (PASS)" if passes else "결재 불가 (FAIL 존재)"

    return f"""<div class="cover">
<div class="section-num">RISK COMMITTEE MEETING DOSSIER</div>
<h1>리스크 위원회 자료<br/>{_esc(meeting_date)}</h1>
<div class="meta">
산출 기준 {date.today().isoformat()} · seed {result.meta.get('seed', '-')} ·
규제 준거 Basel III + IFRS9 + 금감원 감독세칙<br/>
포트폴리오 {int(result.portfolio_summary['n'].sum()):,}건 ·
EAD {_won(result.portfolio_summary['ead'].sum())}
</div>
<div class="verdict">{_esc(verdict_text)}</div>
<div class="meta" style="margin-top:30pt;font-size:10pt">
검증 결과: PASS {summ.get('PASS',0)} · WARN {summ.get('WARN',0)} ·
FAIL {summ.get('FAIL',0)}<br/>
RAF 최악 등급: {_esc(raf_worst)} ·
ICAAP 등급: {_esc(result.icaap.grade if result.icaap else '-')}
</div>
</div>"""


def _section(num: str, title: str, body: str) -> str:
    return f"""<div class="page">
<div class="section-num">PAGE {_esc(num)}</div>
<h2>{_esc(title)}</h2>
{body}
</div>"""


def _page_exec_summary(result) -> str:
    """Page 2 — top 5 issues + key narrative."""
    actions = []
    if result.raf:
        for grade in ("RED", "AMBER"):
            for k in result.raf.kris:
                if k.grade != grade:
                    continue
                actions.append((grade, k.name, k.category, k.actual,
                                k.threshold.board, k.citation))
                if len(actions) >= 5:
                    break
            if len(actions) >= 5:
                break
    for c in result.validation.checks:
        if c.status in ("FAIL", "WARN") and len(actions) < 5:
            actions.append((c.status, c.name, "검증", None, None, c.detail))

    cards = "".join(
        f'<div class="action-card {"bad" if g in ("RED","FAIL") else ""}">'
        f'<b>[{g}] {nm}</b> ({cat}) — '
        f'{"실측 " + str(round(a,4)) + " / board " + str(round(b,4)) if a is not None else cit}'
        f'<br/><span class="cite">{cit if a is not None else ""}</span></div>'
        for g, nm, cat, a, b, cit in actions
    ) or '<div class="action-card good">조치 필요 항목 없음.</div>'

    bis = result.bis
    return _section("2 / 12", "Executive Summary — Top 5 issues", f"""
<div class="kpi-row">
<div class="kpi-box"><div class="kpi-lbl">총자산 risk</div>
  <div class="kpi-val">{_won(result.rwa['final_total'])}</div>
  <div class="kpi-sub">최종 RWA (output floor 적용)</div></div>
<div class="kpi-box"><div class="kpi-lbl">자본 잉여</div>
  <div class="kpi-val good">{bis.surplus_shortfall['cet1']*100:+.2f}%p</div>
  <div class="kpi-sub">CET1 잉여 / Basel III + CCB</div></div>
<div class="kpi-box"><div class="kpi-lbl">유동성</div>
  <div class="kpi-val">{result.alm['lcr'].lcr*100:.0f}%</div>
  <div class="kpi-sub">LCR (기준 100%)</div></div>
</div>

<h3>주요 조치 사항</h3>
{cards}

<h3>CRO 브리핑</h3>
{_briefing_block(result)}
""")


def _briefing_block(result) -> str:
    """경영진 브리핑 내러티브 — html_exec와 동일 유도식, 링크 제거판."""
    import re as _re
    from risk_lib.html_exec import _cro_briefing
    return "".join(
        f'<p style="margin:5pt 0; line-height:1.55; font-size:10.5pt;">'
        f'{_re.sub(r"<a [^>]*>.*?</a>", "", b).rstrip(" ·")}</p>'
        for b in _cro_briefing(result))


def _page_kri_traffic_light(result) -> str:
    """Page 3 — KRI scorecard."""
    if not result.raf:
        return _section("3 / 12", "KRI Traffic-Light Dashboard",
                        "<p>RAF 데이터 없음.</p>")
    raf_summ = result.raf.summary()
    kris = result.raf.kris
    rows = []
    for k in kris:
        fmt = (lambda v: f"{v*100:.2f}%") if k.fmt == "pct" else \
              (lambda v: f"{v:.3f}") if k.fmt == "ratio" else \
              (lambda v: _won(v))
        rows.append([k.category, k.name,
                     fmt(k.actual), fmt(k.threshold.management),
                     fmt(k.threshold.board),
                     _badge(k.grade, k.grade), _esc(k.citation)])

    return _section("3 / 12", "KRI Traffic-Light Dashboard", f"""
<div class="kpi-row">
<div class="kpi-box"><div class="kpi-lbl">GREEN</div>
  <div class="kpi-val good">{raf_summ.get('GREEN',0)}</div></div>
<div class="kpi-box"><div class="kpi-lbl">WATCH</div>
  <div class="kpi-val">{raf_summ.get('WATCH',0)}</div></div>
<div class="kpi-box"><div class="kpi-lbl">AMBER</div>
  <div class="kpi-val warn">{raf_summ.get('AMBER',0)}</div></div>
<div class="kpi-box"><div class="kpi-lbl">RED</div>
  <div class="kpi-val bad">{raf_summ.get('RED',0)}</div></div>
</div>
{_table(['분류','KRI','실측','mgmt 한계','board 한계','grade','근거'], rows,
        right_cols=[2,3,4])}
""")


def _page_capital(result) -> str:
    """Page 4 — Capital position."""
    bis = result.bis
    rows = [["CET1", f"{bis.cet1_ratio*100:.2f}%",
             f"{bis.required['cet1']*100:.2f}%",
             f"{bis.surplus_shortfall['cet1']*100:+.2f}%p"],
            ["Tier 1", f"{bis.tier1_ratio*100:.2f}%",
             f"{bis.required['tier1']*100:.2f}%",
             f"{bis.surplus_shortfall['tier1']*100:+.2f}%p"],
            ["Total", f"{bis.total_ratio*100:.2f}%",
             f"{bis.required['total']*100:.2f}%",
             f"{bis.surplus_shortfall['total']*100:+.2f}%p"],
            ["Leverage", f"{result.leverage.leverage_ratio*100:.2f}%",
             "3.00%",
             f"{(result.leverage.leverage_ratio - 0.03)*100:+.2f}%p"]]
    return _section("4 / 12", "Capital Position + Buffer Status", f"""
{_table(['비율','실측','요구치(P1+CBR)','잉여/부족'], rows, right_cols=[1,2,3])}
<h3>RWA 구성</h3>
{_table(['구분','금액','비중'],
        [['신용 SA', _won(result.rwa['sa']),
          f"{result.rwa['sa']/result.rwa['final_total']*100:.1f}%"],
         ['신용 IRB', _won(result.rwa['irb']),
          f"{result.rwa['irb']/result.rwa['final_total']*100:.1f}%"],
         ['시장리스크', _won(result.rwa['market']),
          f"{result.rwa['market']/result.rwa['final_total']*100:.1f}%"],
         ['운영리스크', _won(result.rwa['op']),
          f"{result.rwa['op']/result.rwa['final_total']*100:.1f}%"],
         ['<b>최종 합계</b>',
          f"<b>{_won(result.rwa['final_total'])}</b>", "100%"]],
        right_cols=[1, 2])}
<p class="cite">근거: Basel III CRE10.4 · RBC20.1 (CCB 2.5%) · 감독세칙
자본적정성 편</p>
""")


def _page_liquidity(result) -> str:
    """Page 5 — Liquidity."""
    lcr = result.alm["lcr"]
    nsfr = result.alm["nsfr"]
    return _section("5 / 12", "Liquidity Position + LCR/NSFR", f"""
<div class="kpi-row">
<div class="kpi-box"><div class="kpi-lbl">LCR</div>
  <div class="kpi-val {'good' if lcr.lcr >= 1 else 'bad'}">{lcr.lcr*100:.0f}%</div>
  <div class="kpi-sub">기준 100% (LCR20.1)</div></div>
<div class="kpi-box"><div class="kpi-lbl">NSFR</div>
  <div class="kpi-val {'good' if nsfr.nsfr >= 1 else 'bad'}">{nsfr.nsfr*100:.0f}%</div>
  <div class="kpi-sub">기준 100% (NSF20.1)</div></div>
<div class="kpi-box"><div class="kpi-lbl">IRRBB</div>
  <div class="kpi-val {'good' if not result.alm['irrbb'].outlier() else 'bad'}">{result.alm['irrbb'].worst_pct_tier1*100:.2f}%</div>
  <div class="kpi-sub">최악 ΔEVE / Tier1 (≤15%)</div></div>
</div>
<h3>LCR 분해</h3>
{_table(['항목','금액'],
        [['HQLA (cap 적용 후)', _won(lcr.hqla_total)],
         ['총 가중유출 (30d)', _won(lcr.gross_outflow)],
         ['유입 (75% cap 적용)', _won(lcr.inflow_capped)],
         ['<b>순현금유출</b>', f"<b>{_won(lcr.net_outflow)}</b>"]],
        right_cols=[1])}
<h3>NSFR 분해</h3>
{_table(['항목','금액'],
        [['ASF', _won(nsfr.asf_total)],
         ['RSF', _won(nsfr.rsf_total)],
         ['<b>NSFR</b>',
          f"<b>{nsfr.nsfr*100:.0f}%</b>"]], right_cols=[1])}
<p class="cite">근거: Basel III LCR20.1 / LCR30.47 (cap formula) / NSF20.1 /
SRP31.92 (IRRBB outlier)</p>
""")


def _page_credit(result) -> str:
    by_stage = result.ecl["by_stage"]
    stage_rows = [[f"Stage {int(s)}",
                   f"{int(row['n']):,}", _won(row["ead"]),
                   _won(row["ecl"]), f"{row['coverage']*100:.2f}%"]
                  for s, row in by_stage.iterrows()]
    return _section("6 / 12", "Credit Risk — Portfolio, NPL, ECL", f"""
<div class="kpi-row">
<div class="kpi-box"><div class="kpi-lbl">총 ECL (TTC)</div>
  <div class="kpi-val">{_won(result.ecl['total'])}</div></div>
<div class="kpi-box"><div class="kpi-lbl">PIT 확률가중</div>
  <div class="kpi-val">{_won(result.macro_ecl.weighted_total)}</div>
  <div class="kpi-sub">forward-looking uplift {_won(result.macro_ecl.weighted_total - result.ecl['total'])}</div></div>
<div class="kpi-box"><div class="kpi-lbl">부도율 (EW)</div>
  <div class="kpi-val">{result.monitoring['default_rate_ew']*100:.2f}%</div></div>
</div>
{_table(['Stage','건수','EAD','ECL','커버리지'], stage_rows, right_cols=[1,2,3,4])}
<p class="cite">근거: IFRS 9 5.5.3 / 5.5.5 / 5.5.11 (SICR) / B5.5.42 (multiple scenarios)</p>
""")


def _page_market(result) -> str:
    return _section("7 / 12", "Market Risk — VaR + Greeks + FRTB", f"""
<div class="kpi-row">
<div class="kpi-box"><div class="kpi-lbl">시장 RWA</div>
  <div class="kpi-val">{_won(result.rwa['market'])}</div></div>
<div class="kpi-box"><div class="kpi-lbl">CVA 자본</div>
  <div class="kpi-val">{_won(result.ccr.cva_charge) if result.ccr else '-'}</div>
  <div class="kpi-sub">BA-CVA (κ=5%)</div></div>
<div class="kpi-box"><div class="kpi-lbl">FRTB 준비</div>
  <div class="kpi-val warn">진행 중</div>
  <div class="kpi-sub">IMA PLAT/RFET 평가 필요</div></div>
</div>
<h3>XVA suite (참고)</h3>
<p>현재 CCR/CVA만 자본 산입. 전체 XVA(DVA/FVA/ColVA/MVA) 평가 결과는
실무진 보고서 page 53 참조. CDS hedge ratio 결정에 활용.</p>
<p class="cite">근거: BCBS MAR (FRTB 2019) · CRE52 SA-CCR · BA-CVA d325</p>
""")


def _page_op_risk(result) -> str:
    op = result.op_loss
    by_et_rows = [[r["event_type"], f"{int(r['n_5y']):,}",
                   _won(r["total_5y"]), _won(r["annual"])]
                  for _, r in op.by_event_type.head(5).iterrows()] if op else []
    return _section("8 / 12", "Operational Risk — Incidents + LDA + SMA", f"""
<div class="kpi-row">
<div class="kpi-box"><div class="kpi-lbl">운영 RWA (SMA)</div>
  <div class="kpi-val">{_won(result.rwa['op'])}</div></div>
<div class="kpi-box"><div class="kpi-lbl">LDA 99.9% VaR</div>
  <div class="kpi-val">{_won(op.var_99_9) if op else '-'}</div></div>
<div class="kpi-box"><div class="kpi-lbl">연환산 손실</div>
  <div class="kpi-val">{_won(op.annual_total) if op else '-'}</div></div>
</div>
<h3>이벤트 유형별 손실 (5년 등록)</h3>
{_table(['이벤트','5년 건수','5년 누적','연환산'], by_et_rows, right_cols=[1,2,3])
  if by_et_rows else '<p>등록 데이터 없음.</p>'}
<p class="cite">근거: Basel III OPE25 (SMA) · Loss Distribution Approach (BCBS WP24)</p>
""")


def _page_stress(result) -> str:
    s = result.stress
    rows = [[r["scenario"], _won(r["rwa_total"]), _won(r["ecl"]),
             f"{r['cet1_ratio']*100:.2f}%", f"{r['cet1_surplus']*100:+.2f}%p",
             _badge("PASS" if r["passes"] else "FAIL",
                    "PASS" if r["passes"] else "FAIL")]
            for _, r in s.iterrows()]
    rev = result.reverse_stress
    return _section("9 / 12", "Stress Test Results — Forward + Reverse", f"""
{_table(['시나리오','RWA','ECL','CET1','잉여','판정'], rows, right_cols=[1,2,3,4])}
<h3>역스트레스</h3>
<p>임계 심도 <b>s = {rev.critical_severity:.2f}</b> ·
함의 거시충격 GDP <b>{rev.implied_gdp_shock*100:+.1f}%</b>,
LGD <b>+{rev.implied_lgd_addon*100:.1f}%p</b></p>
<p class="cite">근거: 감독세칙 스트레스테스트 가이드라인 · Fed CCAR 2025 SR
methodology · EBA EU-wide ST 2025</p>
""")


def _page_scenarios() -> str:
    from risk_lib.scenario_library import SCENARIO_LIBRARY, by_family
    rows = [[fam.capitalize(), str(len(by_family(fam)))]
            for fam in ("historic","hypothetical","regulatory","climate")]
    return _section("10 / 12", "Scenario Library Status", f"""
<p>현재 등록된 named scenarios: <b>{len(SCENARIO_LIBRARY)}개</b></p>
{_table(['Family','count'], rows, right_cols=[1])}
<h3>최근 추가</h3>
<ul>
<li>NGFS Phase 4 (Disorderly / Hot House / Orderly) — 30y horizon</li>
<li>Fed CCAR 2025 severely adverse — GDP -7.5%, equity -55%</li>
<li>EBA EU-wide ST 2025 — 3y horizon adverse</li>
<li>2023 미국 지역은행 위기 — 유동성·금리 동시 발현</li>
</ul>
<p class="cite">실무진 보고서 page 55 (Scenario Library)에 전체 narrative + 출처 수록</p>
""")


def _page_actions(result) -> str:
    items = []
    if result.raf:
        for k in result.raf.kris:
            if k.grade in ("RED", "AMBER"):
                items.append(("[" + k.grade + "] " + k.name,
                              "Limit Owner", "30일 이내",
                              "한계 침범 - 익스포저 조정 또는 자본 보충"))
    for c in result.validation.checks:
        if c.status == "FAIL":
            items.append((c.name, "산출 담당자", "즉시", c.detail))

    rows = [[a, o, d, s] for a, o, d, s in items[:8]] or [["없음", "-", "-", "-"]]
    return _section("11 / 12", "Action Items — Owner / Deadline / Status",
                    _table(["조치 사항", "담당", "기한", "비고"], rows))


def _page_audit_signoff(result, *, ledger_path: str | None = None) -> str:
    """Page 12 — audit trail + sign-off."""
    return _section("12 / 12", "Audit Trail + Sign-off Certificate", f"""
<p>본 보고서는 <b>risk_lib v0.18</b>로 산출되었으며 모든 헤드라인 수치는
audit ledger를 통해 source data → code → parameters → 규제 인용까지 추적 가능합니다.</p>

<p><b>재현 명령:</b><br/>
<code>python -m risk_lib.cli reproduce --manifest manifest.json</code></p>

<p><b>Ledger 위치:</b> {_esc(ledger_path or "ops/audit_ledger.json")}</p>

<h3>Sign-off chain</h3>
<div>
<div class="sign-box"><div class="role">1st Line — Owner</div>
<div class="name">산출 담당자</div>
<div class="sig-line"></div></div>
<div class="sign-box"><div class="role">2nd Line — Risk</div>
<div class="name">리스크 2선</div>
<div class="sig-line"></div></div>
<div class="sign-box"><div class="role">CRO</div>
<div class="name">최고리스크관리책임자</div>
<div class="sig-line"></div></div>
</div>

<p class="cite" style="margin-top:20pt">근거: BCBS 239 (Risk data aggregation
and reporting) · SR 11-7 (model documentation) · 감독세칙 자체검증
+ 결재 절차</p>
""")


def build_board_pack(result, out_path,
                     *, meeting_date: str = "", ledger_path: str | None = None) -> str:
    """Generate the 12-page board pack HTML."""
    if not meeting_date:
        meeting_date = date.today().isoformat()

    pages = [
        _cover(result, meeting_date=meeting_date),
        _page_exec_summary(result),
        _page_kri_traffic_light(result),
        _page_capital(result),
        _page_liquidity(result),
        _page_credit(result),
        _page_market(result),
        _page_op_risk(result),
        _page_stress(result),
        _page_scenarios(),
        _page_actions(result),
        _page_audit_signoff(result, ledger_path=ledger_path),
    ]

    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>Risk Committee Board Pack — {_esc(meeting_date)}</title>
<style>{_BOARD_CSS}</style></head>
<body>
{"".join(pages)}
{abbr_dict_card_html()}
</body></html>"""

    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return str(p.resolve())
