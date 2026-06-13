"""New deep-dive pages for the operational (실무진) report.

Adds: 13 climate, 14 CCR/CVA, 15 op loss, 16 sensitivity, 17 model risk,
18 concentration deep-dive, 19 RAF, 20 Pillar 3.

Imports the chrome and helpers from html_report so the new pages share look
and navigation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)
from risk_lib.references import HHI_HIGH


# ---------------------------------------------------------------- 13 climate

def page_climate(r: PipelineResult) -> str:
    cl = r.climate
    rows_t = [[l.scenario, l.narrative, _won(l.total_ear),
               _won(l.base_ecl), _won(l.climate_ecl), _won(l.uplift)]
              for l in cl.transition]
    rows_p = [[l.scenario, l.narrative, _won(l.total_ear),
               _won(l.base_ecl), _won(l.climate_ecl), _won(l.uplift)]
              for l in cl.physical]
    chart_t = viz.bar_chart(
        [l.scenario for l in cl.transition],
        [l.uplift for l in cl.transition],
        title="전환리스크 시나리오별 ECL 증가분",
        value_fmt=_won, colors=[viz.AMBER]*len(cl.transition),
    )
    chart_p = viz.bar_chart(
        [l.scenario for l in cl.physical],
        [l.uplift for l in cl.physical],
        title="물리리스크 시나리오별 ECL 증가분",
        value_fmt=_won, colors=[viz.RED]*len(cl.physical),
    )
    # Worst transition by sector heatmap (uplift_ecl)
    worst = next(l for l in cl.transition if l.scenario == cl.worst_transition)
    sec_chart = viz.horizontal_bar(
        worst.by_sector["sector"].tolist()[:10],
        worst.by_sector["uplift_ecl"].tolist()[:10],
        title=f"섹터별 ECL 증가분 — {cl.worst_transition}",
        value_fmt=_won, color=viz.AMBER,
    )
    body = f"""
<h1 class="title">13. 기후리스크 (Climate Risk)</h1>
<p class="section-lead">NGFS-aligned 전환·물리 시나리오를 포트폴리오에 매핑.
전환리스크는 탄소가격 → PD uplift, 물리리스크는 자연재해 강도 → LGD uplift로 변환.</p>

<div class="kpi-grid">
{_kpi("최악 전환 시나리오", _esc(cl.worst_transition),
       sub=_won(max(l.uplift for l in cl.transition)))}
{_kpi("최악 물리 시나리오", _esc(cl.worst_physical),
       sub=_won(max(l.uplift for l in cl.physical)))}
{_kpi("기준 ECL", _won(cl.transition[0].base_ecl))}
{_kpi("전환 ECL uplift 합", _won(sum(l.uplift for l in cl.transition)))}
</div>

<div class="row2">
<div class="card"><h2>13-1. 전환리스크 (탄소가격)</h2>
<div class="chart">{chart_t}</div>
{_table(["시나리오","narrative","EAR","기준 ECL","기후 ECL","증가분"], rows_t,
        right_cols=[2,3,4,5])}
</div>
<div class="card"><h2>13-2. 물리리스크 (자연재해)</h2>
<div class="chart">{chart_p}</div>
{_table(["시나리오","narrative","EAR","기준 ECL","기후 ECL","증가분"], rows_p,
        right_cols=[2,3,4,5])}
</div>
</div>

<div class="card"><h2>13-3. 섹터별 노출 — 최악 전환 시나리오</h2>
<div class="chart">{sec_chart}</div>
</div>
"""
    return _page("기후리스크", body, "13_climate.html")


# ---------------------------------------------------------------- 14 CCR / CVA

def page_ccr(r: PipelineResult) -> str:
    if r.ccr is None or r.ccr.by_counterparty.empty:
        body = "<h1 class='title'>14. CCR / CVA</h1><p>은행 노출 없음 — CCR 산출 불가.</p>"
        return _page("CCR/CVA", body, "14_ccr.html")
    ccr = r.ccr
    top = ccr.by_counterparty.nlargest(10, "ead")
    rows = [[t["counterparty"][:18], _won(t["v"]), _won(t["c"]),
             _won(t["rc"]), _won(t["pfe"]), _won(t["ead"]),
             _pct(t["rw"], 0), _won(t["rwa"])]
            for _, t in top.iterrows()]
    chart = viz.horizontal_bar(
        [t[:14] for t in top["counterparty"].tolist()],
        top["ead"].tolist(),
        title="상위 거래상대방 SA-CCR EAD",
        value_fmt=_won, color=viz.PALETTE[0],
    )
    body = f"""
<h1 class="title">14. 거래상대방신용리스크 (CCR) + 신용평가조정 (CVA)</h1>
<p class="section-lead">SA-CCR (CRE52, α=1.4·(RC+PFE)) + 간소화 BA-CVA.
은행 노출에 합성 derivatives 북을 부착해 산출.</p>

<div class="kpi-grid">
{_kpi("거래상대방 수", f"{ccr.n_counterparties}")}
{_kpi("SA-CCR 총 EAD", _won(ccr.ead_total))}
{_kpi("CCR RWA (50% RW)", _won(ccr.rwa_total))}
{_kpi("BA-CVA 자본 (κ=5%)", _won(ccr.cva_charge))}
</div>

<div class="card"><h2>상위 거래상대방 EAD</h2>
<div class="chart">{chart}</div>
{_table(["거래상대방","MtM","담보","RC","PFE","EAD","RW","RWA"], rows,
        right_cols=[1,2,3,4,5,6,7])}
</div>

<div class="card"><h2>출처</h2>
<ul>
<li>BCBS CRE52 — SA-CCR (Standardised Approach for Counterparty Credit Risk)</li>
<li>BCBS CRE50.6 — BA-CVA (Basic Approach for CVA capital charge)</li>
<li>α (CRE52.4) = 1.4, 감독 인수: IR 0.5%, FX 4.0%, Credit IG 0.5%, Equity 32%</li>
</ul>
</div>
"""
    return _page("CCR/CVA", body, "14_ccr.html")


# ---------------------------------------------------------------- 15 op loss

def page_op_loss(r: PipelineResult) -> str:
    op = r.op_loss
    by_et = op.by_event_type
    rows_et = [[row["event_type"], f"{int(row['n_5y']):,}",
                _won(row["total_5y"]), _won(row["annual"])]
               for _, row in by_et.iterrows()]
    chart = viz.horizontal_bar(
        by_et["event_type"].tolist(), by_et["annual"].tolist(),
        title="이벤트 유형별 연환산 손실", value_fmt=_won, color=viz.RED,
    )
    top_rows = [[t["event_type"], f"{int(t['days_ago'])}일 전",
                 _won(t["gross"]), _won(t["recovery"]), _won(t["net"]),
                 _pct(t["pct_of_annual_total"])]
                for _, t in op.top_scenarios.iterrows()]
    coverage = (op.sma_capital_compare / op.var_99_9) if op.var_99_9 > 0 else 0
    body = f"""
<h1 class="title">15. 운영리스크 손실데이터 + 시나리오 분석 (LDA-lite)</h1>
<p class="section-lead">5년치 합성 손실 등록부 → Poisson-Lognormal LDA → 99.9% 1년 VaR.
Basel SMA 자본과 비교해 capital coverage 평가.</p>

<div class="kpi-grid">
{_kpi("연환산 손실 합계", _won(op.annual_total))}
{_kpi("99.9% 1Y VaR", _won(op.var_99_9))}
{_kpi("99% ES", _won(op.es_99_0))}
{_kpi("SMA 자본 vs LDA VaR",
       _pct(coverage, 1),
       sub="SMA 자본이 LDA VaR을 cover하는 비율",
       tone="good" if coverage >= 1 else "warn")}
</div>

<div class="card"><h2>15-1. 이벤트 유형별 손실</h2>
<div class="chart">{chart}</div>
{_table(["이벤트","5년 건수","5년 누적","연환산"], rows_et, right_cols=[1,2,3])}
</div>

<div class="card"><h2>15-2. Top 3 단일 손실 시나리오 (스토리텔링용)</h2>
{_table(["이벤트","발생","총손실","회수","순손실","연환산 대비"],
        top_rows, right_cols=[2,3,4,5])}
<p class="section-lead">위 top 시나리오는 ICAAP Pillar 2 시나리오 분석의 출발점 — 단일 사건 한 건이 연 손실의
{_pct(op.top_scenarios.iloc[0]['pct_of_annual_total']) if len(op.top_scenarios) else '0%'} 차지.</p>
</div>
"""
    return _page("운영손실", body, "15_op_loss.html")


# ---------------------------------------------------------------- 16 sensitivity

def page_sensitivity(r: PipelineResult) -> str:
    one_f = r.sensitivity["one_factor"]
    two_f = r.sensitivity["two_factor"]

    # split one_f by metric for cleaner charts
    metric_charts = []
    for metric in ["CET1", "RWA", "ECL", "LCR", "ΔEVE"]:
        sub = one_f[one_f["metric"] == metric].copy()
        if sub.empty: continue
        labels = [f"{r['factor']}: {r['shock']:+.3g}" for _, r in sub.iterrows()]
        deltas = sub["delta"].tolist()
        chart = viz.horizontal_bar(
            labels, deltas, title=f"{metric} 민감도", value_fmt=_won
            if metric in ("RWA", "ECL", "ΔEVE") else _pct,
            color=viz.PALETTE[0],
        )
        metric_charts.append(f'<div class="card"><div class="chart">{chart}</div></div>')

    # two-factor PD × LGD heatmap on ECL delta
    pds = sorted(two_f["pd_shock"].unique())
    lgds = sorted(two_f["lgd_shock"].unique())
    matrix = []
    for p in pds:
        row = []
        for l in lgds:
            sel = two_f[(two_f["pd_shock"] == p) & (two_f["lgd_shock"] == l)]
            row.append(float(sel["delta"].iloc[0]) if len(sel) else 0.0)
        matrix.append(row)
    heat = viz_advanced.heatmap(
        [f"PD {p:+.0%}" for p in pds],
        [f"LGD {l:+.2f}pp" for l in lgds],
        matrix, title="PD × LGD 충격 → ECL 증가분 (조원)",
        value_fmt=lambda v: f"{v/1e12:.2f}", diverging=True,
    )

    rows = [[f"{r['factor']}", f"{r['shock']:+.4g}", r["metric"],
             _won(r["base"]) if r["metric"] != "CET1" else _pct(r["base"]),
             _won(r["shocked"]) if r["metric"] != "CET1" else _pct(r["shocked"]),
             _won(r["delta"]) if r["metric"] != "CET1" else f"{r['delta']*100:+.2f}%p"]
            for _, r in one_f.iterrows()]

    body = f"""
<h1 class="title">16. 민감도 / What-if 분석</h1>
<p class="section-lead">단일 요인 1-factor 충격(PD/LGD/EAD/Capital/Rate/HQLA/Funding)을
주요 지표(CET1, RWA, ECL, LCR, ΔEVE)에 적용한 closed-form 민감도.
PD×LGD 2-factor cross는 ECL 충격 surface를 보여줌.</p>

<div class="row2">
{''.join(metric_charts[:2])}
</div>
<div class="row2">
{''.join(metric_charts[2:4])}
</div>
<div class="row2">
{''.join(metric_charts[4:])}
</div>

<div class="card"><h2>16-1. 2-Factor cross: PD × LGD → ΔECL</h2>
{heat}
<p class="section-lead">셀 값은 base ECL 대비 증가분(조원). 빨간색일수록 ECL이 크게 증가.
PD +50% × LGD +15%p 동시 발생 시 우상단 셀 값이 worst-case 충격.</p>
</div>

<div class="card"><h2>16-2. 1-Factor 민감도 전체 grid</h2>
{_table(["요인","충격","지표","기준","충격 후","증가분"], rows, right_cols=[3,4,5])}
</div>
"""
    return _page("민감도", body, "16_sensitivity.html")


# ---------------------------------------------------------------- 17 model risk

def page_model_risk(r: PipelineResult) -> str:
    cards = r.model_cards
    rows = [[m.model_id, m.segment, _badge(m.status,
              "PASS" if m.status == "PRODUCTION" else "WARN"),
             f"{m.performance.get('gini', 0):.3f}",
             f"{m.performance.get('ks', 0):.3f}",
             f"{int(m.n_train):,}/{int(m.n_test):,}",
             m.last_validation]
            for m in cards]
    cards_html = []
    for m in cards:
        perf_rows = [[k, f"{v:.4f}" if isinstance(v, (int, float)) else str(v)]
                     for k, v in m.performance.items()]
        features = "<br>".join(m.features)
        cards_html.append(f"""
<div class="card"><h3>{_esc(m.model_id)} — {_esc(m.segment)}
{_badge(m.status, "PASS" if m.status == "PRODUCTION" else "WARN")}</h3>
<div class="row2">
<div>
<p><b>용도:</b> {_esc(m.purpose)}</p>
<p><b>피처:</b><br>{features}</p>
<p><b>학습 기간:</b> {_esc(m.train_window)}</p>
<p><b>학습/검증 표본:</b> {int(m.n_train):,} / {int(m.n_test):,}</p>
<p><b>모형 소유:</b> {_esc(m.owner)} · 마지막 검증 {_esc(m.last_validation)}</p>
</div>
<div>
{_table(["지표", "값"], perf_rows, right_cols=[1])}
</div>
</div>
</div>""")

    body = f"""
<h1 class="title">17. 모형리스크관리 (SR 11-7 모형 카드)</h1>
<p class="section-lead">PD 모형 인벤토리 + 각 모형의 model card.
status가 PRODUCTION이 아닌 모형은 결재 전 모형 위원회 review 필요.</p>

<div class="card"><h2>17-1. 모형 인벤토리</h2>
{_table(["Model ID","세그먼트","Status","Gini","KS","학습/검증","마지막 검증"],
        rows, right_cols=[3,4])}
</div>

<h2 style="margin:18px 0 6px">17-2. 모형 카드 상세</h2>
{''.join(cards_html)}
"""
    return _page("모형리스크", body, "17_model_risk.html")


# ---------------------------------------------------------------- 18 concentration deep

def page_concentration_deep(r: PipelineResult) -> str:
    cd = r.concentration_deep
    top_ead = cd["top_by_ead"]
    top_risk = cd["top_by_risk"]
    le = cd["large_exposure"]
    sc = cd["sector_country"]

    rows_ead = [[t["obligor_id"], _esc(t["asset_class"]),
                 _esc(str(t["sector"])), _esc(str(t["country"])),
                 _won(t["ead"]),
                 f"{t['pd_avg']:.4f}" if not pd.isna(t.get("pd_avg")) else "-",
                 f"{t['lgd_avg']:.3f}" if not pd.isna(t.get("lgd_avg")) else "-",
                 _won(t.get("el", 0))]
                for _, t in top_ead.iterrows()]
    rows_risk = [[t["obligor_id"], _esc(t["asset_class"]),
                  _esc(str(t["sector"])), _won(t["ead"]),
                  f"{t['pd_avg']:.4f}" if not pd.isna(t.get("pd_avg")) else "-",
                  _won(t.get("risk_score", 0))]
                 for _, t in top_risk.iterrows()]

    # large exposure: only show top breaches/warnings (severity != OK)
    breaches = le[le["severity"] != "OK"]
    rows_le = [[t["obligor_id"], _won(t["ead"]), _won(t["threshold"]),
                _pct(t["utilisation"], 1),
                _badge(t["severity"], {"BREACH":"FAIL","CRITICAL":"FAIL","WARN":"WARN"}.get(t["severity"], "NEUTRAL"))]
               for _, t in breaches.head(20).iterrows()]

    # heatmap
    sectors = list(sc.index); countries = list(sc.columns)
    matrix = [[float(sc.loc[s, c]) for c in countries] for s in sectors]
    heat = viz_advanced.heatmap(
        sectors, countries, matrix,
        title="섹터 × 국가 EAD 행렬 (조원)",
        value_fmt=lambda v: f"{v/1e12:.1f}",
    )

    # treemap of top obligor EAD
    treemap = viz_advanced.treemap(
        top_ead["obligor_id"].tolist(),
        top_ead["ead"].tolist(),
        title="Top 20 차주 EAD treemap", value_fmt=_won,
    )

    body = f"""
<h1 class="title">18. 집중리스크 deep-dive</h1>
<p class="section-lead">차주별/섹터×국가/한도위반 deep-dive + Gordy granularity addon.</p>

<div class="kpi-grid">
{_kpi("Top 20 차주 EAD", _won(top_ead['ead'].sum()))}
{_kpi("동일차주 한도 위반(BREACH+CRITICAL)", f"{len(breaches[breaches['severity'].isin(['BREACH','CRITICAL'])])}")}
{_kpi("Gordy granularity addon", _pct(cd['granularity_addon_rate'], 3),
       sub="신용 EC 대비 단일차주 가산률")}
</div>

<div class="card"><h2>18-1. Top 20 차주 (EAD 기준)</h2>
<div class="chart">{treemap}</div>
{_table(["차주","자산군","섹터","국가","EAD","평균PD","평균LGD","EL"],
        rows_ead, right_cols=[4,5,6,7])}
</div>

<div class="card"><h2>18-2. Top 20 차주 (EL = PD×EAD 기준)</h2>
{_table(["차주","자산군","섹터","EAD","평균PD","EL 추정"],
        rows_risk, right_cols=[3,4,5])}
</div>

<div class="card"><h2>18-3. 섹터 × 국가 노출</h2>
{heat}
</div>

<div class="card"><h2>18-4. 동일차주 한도 (은행법 §35) — 경보 차주</h2>
{_table(["차주","EAD","한도","사용률","등급"], rows_le, right_cols=[1,2,3]) if rows_le else "<p>모든 차주 한도 이내.</p>"}
</div>
"""
    return _page("집중 deep-dive", body, "18_concentration_deep.html")


# ---------------------------------------------------------------- 19 RAF

def page_raf(r: PipelineResult) -> str:
    raf = r.raf
    summ = raf.summary()
    rows = []
    for k in raf.kris:
        fmt = (lambda v: _pct(v, 2)) if k.fmt == "pct" else \
              (lambda v: f"{v:.3f}") if k.fmt == "ratio" else _won
        rows.append([
            _esc(k.category), _esc(k.name),
            fmt(k.actual),
            fmt(k.threshold.operational),
            fmt(k.threshold.management),
            fmt(k.threshold.board),
            f"{k.distance_to_board*100:+.2f}%p" if k.fmt == "pct" else f"{k.distance_to_board:+.3f}",
            _badge(k.grade, k.grade),
            _esc(k.citation),
        ])

    scorecard = viz_advanced.kri_scorecard([
        {"name": k.name, "category": k.category,
         "actual_text": (_pct(k.actual, 2) if k.fmt == "pct"
                         else (f"{k.actual:.3f}" if k.fmt == "ratio" else _won(k.actual))),
         "grade": k.grade,
         "threshold_text": f"board {k.threshold.board}"} for k in raf.kris
    ])

    body = f"""
<h1 class="title">19. Risk Appetite Framework — KRI 상세</h1>
<p class="section-lead">12개 핵심지표(KRI)의 3단 한계 (board / management / operational) 채점.</p>

<div class="kpi-grid">
{_kpi("GREEN", f"{summ.get('GREEN', 0)}", tone="good")}
{_kpi("WATCH", f"{summ.get('WATCH', 0)}", tone="warn")}
{_kpi("AMBER", f"{summ.get('AMBER', 0)}", tone="warn")}
{_kpi("RED", f"{summ.get('RED', 0)}", tone="bad")}
</div>

<div class="card">
<h2>19-1. KRI 스코어카드</h2>
{scorecard}
</div>

<div class="card">
<h2>19-2. 상세 한계 vs 실측</h2>
{_table(["분류","KRI","실측","operational","management","board","board 잉여","grade","근거"],
        rows, right_cols=[2,3,4,5,6])}
<p class="section-lead">잉여(distance_to_board) 부호: + 이면 한계까지 여유, − 이면 한계 침범. min 방향 KRI는 실측-한계, max 방향 KRI는 한계-실측.</p>
</div>
"""
    return _page("RAF", body, "19_raf.html")


# ---------------------------------------------------------------- 20 Pillar 3

def page_pillar3(r: PipelineResult, portfolio: pd.DataFrame) -> str:
    from risk_lib.pillar3 import km1, ov1, cr1, liq1, lr1
    def _format(df: pd.DataFrame) -> str:
        out_rows = []
        for _, row in df.iterrows():
            cells = list(row.values)
            cells = [_won(c) if isinstance(c, (int, float)) and abs(c) > 1e5
                     else (_pct(c) if isinstance(c, (int, float)) and 0 <= c <= 2
                           else str(c)) for c in cells]
            out_rows.append(cells)
        return _table(list(df.columns), out_rows,
                      right_cols=list(range(1, len(df.columns))))

    body = f"""
<h1 class="title">20. Pillar 3 공시 템플릿 (BCBS DIS)</h1>
<p class="section-lead">감독공시 양식 — KM1 (주요지표), OV1 (RWA 개요), CR1 (자산건전성),
LIQ1 (LCR), LR1 (레버리지). 모든 값은 본 보고서의 산출 결과를 표준 행 번호에 매핑.</p>

<div class="card"><h2>20-1. KM1 — 주요지표</h2>
{_format(km1(r))}
</div>

<div class="card"><h2>20-2. OV1 — RWA 개요</h2>
{_format(ov1(r))}
</div>

<div class="card"><h2>20-3. CR1 — 자산건전성 (performing vs non-performing)</h2>
{_format(cr1(r, portfolio))}
</div>

<div class="card"><h2>20-4. LIQ1 — LCR 공시</h2>
{_format(liq1(r))}
</div>

<div class="card"><h2>20-5. LR1 — 레버리지 공시</h2>
{_format(lr1(r))}
</div>
"""
    return _page("Pillar 3", body, "20_pillar3.html")
