"""Core pages — 종합 요약/검증/결재 (index, 포트폴리오, 자체검증, 최종 attestation).

Chrome (CSS/NAV)은 report_chrome에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

from __future__ import annotations

from datetime import date

from risk_lib.pipeline import PipelineResult
from risk_lib.references import (
    ALL_CITATIONS, LEVERAGE_MIN_RATIO, LCR_MIN, NSFR_MIN, IRRBB_OUTLIER_EVE_PCT_TIER1,
)
from risk_lib import viz
from risk_lib.report_chrome import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)


# ============================================================================
# Page renderers
# ============================================================================


_DOMAIN_LABEL = {
    "core_overview": "핵심 — 요약/검증/결재",
    "core_credit": "핵심 — 신용",
    "core_capital_alm": "핵심 — 자본/ALM",
    "credit": "신용/충당금 심층",
    "capital_stress": "자본/스트레스 심층",
    "market_trading": "시장/트레이딩 심층",
    "concentration_limits": "집중/한도 심층",
    "performance": "성과 심층",
    "nonfinancial": "비재무 심층",
    "governance": "거버넌스/공시 심층",
}


def _page_catalog() -> str:
    """도메인별 전체 페이지 링크 — page_registry에서 파생 (같은 디렉터리 기준)."""
    from risk_lib.page_registry import PAGES
    groups: dict[str, list] = {}
    for spec in PAGES:
        groups.setdefault(spec.module.rsplit(".", 1)[-1], []).append(spec)
    parts = []
    for dom, specs in groups.items():
        links = " · ".join(f'<a href="{s.filename}">{_esc(s.label)}</a>'
                           for s in specs)
        parts.append(
            f'<p style="margin:6px 0;" class="linklist">'
            f'<b>{_esc(_DOMAIN_LABEL.get(dom, dom))}</b> — {links}</p>')
    return "".join(parts)


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

<div class="card"><h2>전 부문 페이지 카탈로그</h2>
<p class="section-lead">도메인별 전체 심층 페이지 — 상단 NAV와 동일하나 도메인
단위로 묶어 탐색하기 쉽게 정리했습니다 (page_registry에서 자동 파생).</p>
{_page_catalog()}
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
    # 부적합(FAIL만) — ISO/IEC 42001 조항 10 부적합·시정조치 섹션용
    fail_rows = [[c.name, _badge(c.status, c.status),
                  f"{c.detail} → 원인 부문 시정조치 후 재검증 필요"]
                 for c in v.checks if c.status == "FAIL"]

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

<div class="card"><h2>부적합·시정조치 (ISO/IEC 42001 조항 10)</h2>
{_table(["부적합(FAIL 체크)","상태","상세 / 시정조치"], fail_rows) if fail_rows else
 f"<p>해당 없음 — 본 산출 주기에서 기록된 부적합(FAIL) 없음. "
 f"WARN {summ.get('WARN', 0)}건은 상단 WARN/FAIL 상세의 사유 설명으로 갈음.</p>"}
<p style="color:var(--muted); font-size:12px;">
부적합 발생 시 AIMS_POLICY.md §6 절차(부적합 기록 → 원인 에이전트 시정조치 →
재검증)를 따르며, 시정 완료 전 결재 상신이 불가합니다.</p>
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
