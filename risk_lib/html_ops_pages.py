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

def page_attribution(r: PipelineResult) -> str:
    """CET1 / RWA single-snapshot decomposition + worked-example bridge."""
    attr = r.attribution
    cet1_h = attr["cet1_headroom"]
    rwa_d = attr["rwa_components"]
    rows_h = [[r2["layer"], _pct(r2["required"]), _pct(r2["actual"]),
               f"{r2['headroom']*100:+.2f}%p"]
              for _, r2 in cet1_h.iterrows()]
    rows_r = [[r2["component"], _won(r2["rwa"]), _pct(r2["share"])]
              for _, r2 in rwa_d.iterrows()]

    rwa_chart = viz_advanced.treemap(
        rwa_d["component"].tolist(), rwa_d["rwa"].tolist(),
        title="최종 RWA 구성 — 비중 시각화", value_fmt=_won,
    )
    headroom_chart = viz.bar_chart(
        cet1_h["layer"].tolist(),
        cet1_h["headroom"].tolist(),
        value_fmt=_pct,
        title="CET1 잉여 — 규제 layer별",
        colors=[viz.GREEN if x >= 0 else viz.RED for x in cet1_h["headroom"]],
    )

    # Worked example bridge: simulate a stressed scenario (+20% EAD) and show the bridge
    from risk_lib.attribution import capital_bridge, rwa_bridge
    from copy import copy
    class _S:
        pass
    stressed = _S()
    stressed.rwa = {k: v for k, v in r.rwa.items()}
    stressed.rwa["sa"] = r.rwa["sa"] * 1.2
    stressed.rwa["irb"] = r.rwa["irb"] * 1.2
    stressed.rwa["final_total"] = (stressed.rwa["sa"] + stressed.rwa["irb"]
                                    + r.rwa["market"] + r.rwa["op"])
    stressed.bis = _S()
    stressed.bis.rwa = stressed.rwa["final_total"]
    stressed.meta = {"capital": r.meta["capital"]}

    base_obj = _S()
    base_obj.rwa = r.rwa
    base_obj.bis = r.bis
    base_obj.meta = r.meta

    cb = capital_bridge(base_obj, stressed)
    rb = rwa_bridge(base_obj, stressed)
    cb_waterfall = viz_advanced.attribution_waterfall(
        [s.label for s in cb.steps], [s.value for s in cb.steps],
        start_value=cb.start_value, end_value=cb.end_value,
        value_fmt=_pct, title="CET1 변동 분해 (EAD +20% 예시)",
    )
    rb_waterfall = viz_advanced.attribution_waterfall(
        [s.label for s in rb.steps], [s.value for s in rb.steps],
        start_value=rb.start_value, end_value=rb.end_value,
        value_fmt=_won, title="RWA 변동 분해 (EAD +20% 예시)",
    )

    body = f"""
<h1 class="title">23. 귀속분석 (Attribution / Bridge)</h1>
<p class="section-lead">단일 시점 분해 + 두 시점 간 변동 driver 분해.
"CET1 비율이 왜 이 수준인가" + "변동의 원인은 무엇인가"를 설명.</p>

<div class="row2">
<div class="card"><h2>23-1. RWA 구성 분해</h2>
<div class="chart">{rwa_chart}</div>
{_table(["부문","RWA","비중"], rows_r, right_cols=[1,2])}
</div>
<div class="card"><h2>23-2. CET1 잉여 layer 분해</h2>
<div class="chart">{headroom_chart}</div>
{_table(["층","요구","실측","잉여"], rows_h, right_cols=[1,2,3])}
</div>
</div>

<div class="card"><h2>23-3. 예시 Bridge — EAD +20% 충격이 CET1·RWA에 미치는 영향</h2>
<p class="section-lead">실제 두 시점 분석 시 동일한 driver 분해를 적용. 자본 변화는 절대값이 작아서 RWA 효과가 dominant.</p>
<div class="row2">
<div><div class="chart">{cb_waterfall}</div></div>
<div><div class="chart">{rb_waterfall}</div></div>
</div>
</div>
"""
    return _page("귀속분석", body, "23_attribution.html")


def page_mda(r: PipelineResult) -> str:
    from risk_lib.mda import compute_mda, mda_ladder
    bis = r.bis
    cet1_amount = r.meta["capital"].cet1
    rwa = bis.rwa
    buf = {"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}
    m = compute_mda(bis.cet1_ratio, cet1_amount, rwa, buffers=buf)
    ladder = mda_ladder(cet1_amount, rwa, buffers=buf)

    # ladder chart: retention_ratio at each CET1 grid point
    chart = viz.bar_chart(
        [_pct(r) for r in ladder["cet1_ratio"]],
        ladder["retention_ratio"].tolist(),
        value_fmt=_pct, title="CET1 비율별 분배제한 (retention ratio)",
        colors=[viz.RED if x > 0.6 else viz.AMBER if x > 0 else viz.GREEN
                for x in ladder["retention_ratio"]],
        reference_value=m.retention_ratio,
        reference_label=f"현재 {_pct(m.retention_ratio)}",
    )

    verdict_text = ("자본보전버퍼 침범 — 배당·성과보수·AT1 쿠폰 분배제한 발생" if m.in_breach
                    else "버퍼 이상 — 분배 제한 없음")
    verdict_tone = "bad" if m.in_breach else "good"

    rows = [["CBR (CCB+CCyB+DSIB)", _pct(m.cbr_total)],
            ["CET1 비율", _pct(m.cet1_ratio)],
            ["버퍼 부족", _won(m.buffer_shortfall) if m.in_breach else "—"],
            ["버퍼 분위", str(m.buffer_quartile) if m.in_breach else "—"],
            ["요구 보유율", _pct(m.retention_ratio)],
            ["분배가능 비율", _pct(m.distributable_pct)],
            ["CBR 초과 (자본 KRW)", _won(m.excess_above_cbr) if not m.in_breach else "—"]]

    body = f"""
<h1 class="title">21. MDA — 자본보전버퍼 분배제한</h1>
<p class="section-lead">Basel III RBC30 / 감독세칙 자본보전버퍼 침범 시 분기별 분배가능이익
보유율 4분위 적용. CET1 비율이 CCB+CCyB+DSIB 합계 위에 있어야 분배 제한 없음.</p>

<div class="kpi-grid">
{_kpi("판정", verdict_text, tone=verdict_tone)}
{_kpi("현재 CET1", _pct(m.cet1_ratio))}
{_kpi("CBR 임계 (4.5%+CBR)",
       _pct(0.045 + m.cbr_total))}
{_kpi("분배가능 비율", _pct(m.distributable_pct),
       tone="good" if m.distributable_pct >= 1 else "bad")}
</div>

<div class="card"><h2>21-1. 분배제한 사다리</h2>
<div class="chart">{chart}</div>
<p class="section-lead">x축이 좌측(빨강)일수록 CET1이 낮아 보유율이 높아짐 = 분배 가능액 감소. 현재 위치는 차트 점선.</p>
</div>

<div class="card"><h2>21-2. MDA 산출 상세</h2>
{_table(["항목","값"], rows, right_cols=[1])}
</div>
"""
    return _page("MDA", body, "21_mda.html")


def page_kri_trends(r: PipelineResult) -> str:
    from risk_lib.timeseries import synth_history
    series = synth_history(r.raf, months=12, seed=r.meta.get("seed", 42))
    # group by category for sub-section presentation
    by_cat = {}
    for k, ts in zip(r.raf.kris, series):
        by_cat.setdefault(k.category, []).append((k, ts))

    sections = []
    for cat, items in by_cat.items():
        charts = []
        for k, ts in items:
            ref = ts.threshold_min if ts.direction == "min" else ts.threshold_max
            ref_label = f"board {ts.threshold_min if ts.direction=='min' else ts.threshold_max}"
            chart = viz.line_chart(
                ts.months, {k.name: ts.values},
                value_fmt=(_pct if k.fmt == "pct"
                           else (lambda v: f"{v:.3f}") if k.fmt == "ratio"
                           else _won),
                title=f"{k.name} — {ts.trend()}",
                reference_value=ref, reference_label=ref_label,
            )
            charts.append(f'<div class="card"><div class="chart">{chart}</div></div>')
        sections.append(f'<h2 style="margin:18px 0 6px">{_esc(cat).upper()} ({len(items)}개 KRI)</h2>'
                        + f'<div class="row2">{"".join(charts)}</div>')

    body = f"""
<h1 class="title">22. KRI 트렌드 (12개월)</h1>
<p class="section-lead">현 시점 KRI를 기반으로 plausible AR(1) 12개월 백히스토리를 합성 — board 한계와의
거리 변화 추이를 확인. 모든 시계열은 현 시점 실측값에 정확히 맞춰 도착.</p>

{"".join(sections)}

<p class="section-lead">단, 위 시계열은 본 산출의 단일 시점 결과를 기반으로 한 합성 백히스토리입니다.
실제 운영 시 월별 산출 manifest를 누적해 실측 트렌드로 교체 가능.</p>
"""
    return _page("KRI 트렌드", body, "22_kri_trends.html")


def page_comparison(r: PipelineResult) -> str:
    """Two-snapshot example: base vs. a stressed clone (PD +20%, LGD +5%).

    Shows what the live comparison page would look like when fed two real
    PipelineResults (e.g. Q1 → Q2).  Uses a synthetic 'b' clone of the
    current result with PD/LGD shocks so the bridge is non-zero.
    """
    from copy import copy
    from risk_lib.comparison import compare_results
    base = r
    class _Cl:
        pass
    b = _Cl()
    # clone with bumped RWA + reduced CET1 + bigger ECL to show the bridge
    b.rwa = dict(r.rwa)
    b.rwa["irb"] = r.rwa["irb"] * 1.08
    b.rwa["sa"] = r.rwa["sa"] * 1.05
    b.rwa["market"] = r.rwa["market"]
    b.rwa["op"] = r.rwa["op"]
    b.rwa["final_total"] = (b.rwa["sa"] + b.rwa["irb"]
                             + b.rwa["market"] + b.rwa["op"])
    b.bis = _Cl()
    b.bis.cet1_ratio = r.meta["capital"].cet1 / b.rwa["final_total"]
    b.bis.tier1_ratio = r.meta["capital"].tier1 / b.rwa["final_total"]
    b.bis.total_ratio = r.meta["capital"].total / b.rwa["final_total"]
    b.bis.rwa = b.rwa["final_total"]
    b.ecl = {"total": r.ecl["total"] * 1.15,
             "by_stage": r.ecl["by_stage"]}
    b.macro_ecl = r.macro_ecl
    b.alm = {"lcr": _Cl(), "nsfr": _Cl(), "irrbb": _Cl()}
    b.alm["lcr"].lcr = r.alm["lcr"].lcr * 0.97
    b.alm["lcr"].hqla_total = r.alm["lcr"].hqla_total
    b.alm["lcr"].net_outflow = r.alm["lcr"].net_outflow / 0.97
    b.alm["lcr"].gross_outflow = r.alm["lcr"].gross_outflow * 1.05
    b.alm["lcr"].inflow_capped = r.alm["lcr"].inflow_capped
    b.alm["nsfr"].nsfr = r.alm["nsfr"].nsfr * 0.98
    b.alm["irrbb"].worst_pct_tier1 = r.alm["irrbb"].worst_pct_tier1 * 1.10
    b.meta = {"capital": r.meta["capital"]}

    diff = compare_results(base, b, a_label="기준 시점", b_label="비교 시점")

    cb = diff.capital_bridge
    rb = diff.rwa_bridge
    eb = diff.ecl_bridge

    # waterfall for CET1 bridge
    cet1_wf = viz_advanced.attribution_waterfall(
        [s.label for s in cb.steps], [s.value for s in cb.steps],
        start_value=cb.start_value, end_value=cb.end_value,
        value_fmt=_pct, title="CET1 비율 변동 분해",
    )
    rwa_wf = viz_advanced.attribution_waterfall(
        [s.label for s in rb.steps], [s.value for s in rb.steps],
        start_value=rb.start_value, end_value=rb.end_value,
        value_fmt=_won, title="RWA 변동 분해",
    )
    ecl_wf = viz_advanced.attribution_waterfall(
        [s.label for s in eb.steps], [s.value for s in eb.steps],
        start_value=eb.start_value, end_value=eb.end_value,
        value_fmt=_won, title="ECL 변동 분해",
    )

    delta_rows = [
        ["CET1 비율", _pct(base.bis.cet1_ratio), _pct(b.bis.cet1_ratio),
         f"{diff.bis_change_pp:+.2f}%p"],
        ["최종 RWA", _won(base.rwa["final_total"]),
         _won(b.rwa["final_total"]), _won(diff.rwa_change_krw)],
        ["TTC ECL", _won(base.ecl["total"]),
         _won(b.ecl["total"]), _won(diff.ecl_change_krw)],
        ["LCR", _pct(base.alm["lcr"].lcr), _pct(b.alm["lcr"].lcr),
         f"{diff.lcr_change_pp:+.2f}%p"],
        ["NSFR", _pct(base.alm["nsfr"].nsfr), _pct(b.alm["nsfr"].nsfr),
         f"{diff.nsfr_change_pp:+.2f}%p"],
    ]

    body = f"""
<h1 class="title">26. 시점 간 비교 (Snapshot Comparison)</h1>
<p class="section-lead">두 시점의 PipelineResult를 받아 헤드라인 변동을 driver별로 분해.
실제 운영 시 Q1 → Q2, YoY 비교 등에 사용. 본 페이지는 시연용으로 현 시점 + 합성
충격(IRB +8%, SA +5%, ECL +15%, LCR -3%) 가상 시나리오와 비교.</p>

<div class="card"><h2>26-1. 헤드라인 변동표</h2>
{_table(["지표","기준","비교","변동"], delta_rows, right_cols=[1,2,3])}
</div>

<div class="card"><h2>26-2. CET1 변동 분해</h2>
<div class="chart">{cet1_wf}</div>
<p class="section-lead">자본 효과 + RWA 효과로 분해. RWA가 증가하면 CET1 비율은 하락 — 부호 직관과 일치.</p>
</div>

<div class="card"><h2>26-3. RWA 변동 분해</h2>
<div class="chart">{rwa_wf}</div>
<p class="section-lead">4부문(SA / IRB / 시장 / 운영) + Output floor 가산 변화로 분해.</p>
</div>

<div class="card"><h2>26-4. ECL 변동 분해</h2>
<div class="chart">{ecl_wf}</div>
<p class="section-lead">Marshall-Edgeworth 가중 평균으로 EAD 효과 + PD·LGD 효과 분해.</p>
</div>
"""
    return _page("시점 비교", body, "26_comparison.html")


def page_data_quality(r: PipelineResult, portfolio: pd.DataFrame) -> str:
    from risk_lib.data_quality import dq_report, reconcile
    dq = dq_report(portfolio)
    rec = reconcile(r, portfolio)

    flag_html = "".join(
        f'<div class="callout {"bad" if f.startswith("FAIL") else ""}">{_esc(f)}</div>'
        for f in dq.flags) or '<div class="callout good">기초 DQ 모든 항목 정상</div>'

    schema_rows = [[r2["column"], r2["dtype"], f"{r2['n_null']:,}",
                    f"{r2['pct_null']*100:.2f}%"]
                   for _, r2 in dq.schema.iterrows()]
    num_rows = [[r2["column"], f"{r2['min']:,.3g}", f"{r2['p5']:,.3g}",
                 f"{r2['median']:,.3g}", f"{r2['p95']:,.3g}",
                 f"{r2['max']:,.3g}", f"{r2['n_outliers']:,}"]
                for _, r2 in dq.numeric.iterrows()]
    cat_rows = [[r2["column"], f"{r2['n_unique']:,}", _esc(r2["top"]),
                 f"{r2['top_count']:,}"]
                for _, r2 in dq.categorical.iterrows()]
    rec_rows = [[c.item, c.source,
                 _won(c.computed) if abs(c.computed) > 1 else f"{c.computed:.6g}",
                 _won(c.reported) if abs(c.reported) > 1 else f"{c.reported:.6g}",
                 f"{c.diff:+.3g}",
                 _badge("PASS" if c.passes else "FAIL", "PASS" if c.passes else "FAIL")]
                for c in rec]

    body = f"""
<h1 class="title">25. 데이터품질 + 정합성 reconciliation</h1>
<p class="section-lead">CRO가 "이 숫자 어디서 나왔어?" 물을 때 답하는 페이지.
입력 데이터 품질 진단 + 보고 헤드라인을 raw 합계로 환원 검증.</p>

<div class="card"><h2>25-1. DQ 플래그</h2>
{flag_html}
</div>

<div class="card"><h2>25-2. Reconciliation — 헤드라인 vs raw 합계</h2>
{_table(["항목","출처","계산값","보고값","차이","상태"], rec_rows, right_cols=[2,3,4])}
<p class="section-lead">모든 행이 PASS여야 결재 가능. FAIL은 산식 또는 분류 정합성에 문제가 있는 것.</p>
</div>

<div class="card"><h2>25-3. 스키마 (컬럼 × 결측)</h2>
{_table(["컬럼","dtype","결측 수","결측 %"], schema_rows, right_cols=[2,3])}
</div>

<div class="card"><h2>25-4. 수치 컬럼 분포</h2>
{_table(["컬럼","min","P5","median","P95","max","outlier 수 (±3σ)"], num_rows,
        right_cols=[1,2,3,4,5,6])}
</div>

<div class="card"><h2>25-5. 범주 컬럼</h2>
{_table(["컬럼","고유값 수","최빈값","최빈값 빈도"], cat_rows, right_cols=[1,3])}
</div>
"""
    return _page("DQ·정합성", body, "25_data_quality.html")


def page_vintage(r: PipelineResult, portfolio: pd.DataFrame) -> str:
    from risk_lib.vintage import build_vintage, transition_matrix
    from risk_lib.models.rating import pd_to_rating
    vin = build_vintage(portfolio, n_cohorts=12, seed=r.meta.get("seed", 42))
    if vin.cohorts.empty:
        body = "<h1 class='title'>24. Vintage / Migration</h1><p>데이터 없음.</p>"
        return _page("Vintage", body, "24_vintage.html")

    # vintage line chart: 4 cohorts overlaid
    sample_cohorts = vin.summary["cohort_month"].tolist()[:6]
    series = {}
    qs = sorted(vin.cohorts["mob"].unique())
    for cm in sample_cohorts:
        sub = vin.cohorts[vin.cohorts["cohort_month"] == cm].sort_values("mob")
        if len(sub) >= 3:
            # pad to qs length with NaN-equivalent (last value held)
            v = [float(sub[sub["mob"] == m]["cum_default_rate"].iloc[0])
                 if m in sub["mob"].values else float(sub["cum_default_rate"].iloc[-1])
                 for m in qs]
            series[cm] = v
    vint_chart = viz.line_chart(
        [str(m) for m in qs], series, value_fmt=_pct,
        title="Cohort × MOB 누적 부도율 (vintage curve)",
    )

    # transition heatmap — only top-N rated grades to keep readable
    p_grade = portfolio.copy()
    p_grade["grade"] = [pd_to_rating(x).grade if x == x else None
                        for x in p_grade["pd"]]
    tm = transition_matrix(p_grade, seed=r.meta.get("seed", 42))
    if tm.matrix.empty:
        heat = "<p>전이행렬 데이터 부족.</p>"
        sum_rows = []
    else:
        # restrict to grades with at least 5 observations for clean readability
        rated = tm.matrix.index.tolist()
        cols = tm.matrix.columns.tolist()
        heat = viz_advanced.heatmap(
            rated, cols,
            tm.matrix.values.tolist(),
            title="1년 등급 이동행렬 (row %)",
            value_fmt=lambda v: f"{v*100:.0f}" if v >= 0.01 else "",
            vmin=0, vmax=1, cell_label=True,
        )
        sum_rows = [[k, _pct(v)] for k, v in tm.summary.items()]

    body = f"""
<h1 class="title">24. Vintage 분석 + 등급 이동행렬 (Migration)</h1>
<p class="section-lead">코호트(origination 시점)별 누적 부도율 곡선 +
1년 horizon 등급 이동행렬. 신용 portfolio의 시간 차원 진단.</p>

<div class="card"><h2>24-1. Vintage curves — 코호트별 누적 부도율</h2>
<div class="chart">{vint_chart}</div>
<p class="section-lead">X축은 months-on-book(MOB), 각 라인은 origination month. 오래된 코호트는
이미 부도가 발현됐고, 신규 코호트는 아직 risk가 드러나지 않은 모습 — 코호트 간 quality 차이를 진단.</p>
</div>

<div class="card"><h2>24-2. 등급 이동행렬 (1년)</h2>
{heat}
<div class="kpi-grid" style="margin-top:8px">
{"".join(_kpi(k, v) for k, v in sum_rows)}
</div>
<p class="section-lead">대각선 = stable, 좌측 상삼각 = upgrade, 우측 하삼각 + D열 = downgrade/부도.
정상 portfolio는 stable 60%+, upgrade ≈ downgrade, default &lt; 5% 정도.</p>
</div>
"""
    return _page("Vintage", body, "24_vintage.html")


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


# ============================================================================
# v0.7.0 — RWA deep-dive pages (CRO-grade)
# ============================================================================


def _placeholder_page(title: str, msg: str, active: str) -> str:
    body = f'<h1 class="title">{_esc(title)}</h1><p class="section-lead">{_esc(msg)}</p>'
    return _page(title, body, active)


def page_irb_deep(r: PipelineResult) -> str:
    """29. IRB Deep-Dive — K/PD/LGD/M/ρ 분포, LGD downturn, AIRB vs FIRB."""
    deep = getattr(r, "rwa_deep", None)
    if deep is None or deep.irb_summary.empty:
        return _placeholder_page(
            "29. IRB Deep-Dive", "IRB 자산이 없어 분석을 생성할 수 없습니다.",
            "29_irb_deep.html",
        )

    isum = deep.irb_summary
    # asset-class K and RWA bars
    k_chart = viz.bar_chart(
        isum["asset_class"].tolist(),
        (isum["k_w"] * 100).tolist(),
        title="자산군별 가중평균 K (%) — CRE31",
        value_fmt=lambda v: f"{v:.2f}%",
        colors=[viz.PALETTE[i] for i in range(len(isum))],
    )
    rho_vals = []
    for _, row in isum.iterrows():
        # use per-class median ρ from per-exposure frame
        sub = deep.irb_per_exposure[
            deep.irb_per_exposure["asset_class"] == row["asset_class"]
        ]
        rho_vals.append(float(sub["rho"].mean()) if len(sub) else 0.0)
    rho_chart = viz.bar_chart(
        isum["asset_class"].tolist(),
        [v * 100 for v in rho_vals],
        title="자산군별 평균 자산상관 ρ (%) — CRE31",
        value_fmt=lambda v: f"{v:.1f}%",
        colors=[viz.PALETTE[i+3] for i in range(len(isum))],
    )

    irb_rows = [[row["asset_class"], int(row["n"]), _won(row["ead"]),
                 f"{row['pd_w']*100:.2f}%", f"{row['lgd_w']*100:.1f}%",
                 f"{row['m_w']:.2f}y" if not pd.isna(row['m_w']) else "—",
                 f"{rho_vals[i]*100:.1f}%",
                 f"{row['k_w']*100:.2f}%", _won(row["rwa"])]
                for i, (_, row) in enumerate(isum.iterrows())]

    # K histogram
    kh = deep.irb_k_hist
    if not kh.empty:
        k_hist_chart = viz.bar_chart(
            [f"{lo*100:.1f}~{hi*100:.1f}%" for lo, hi in
             zip(kh["bin_lo"], kh["bin_hi"])],
            kh["rwa"].tolist(),
            title="K 분포 — 자본요구계수 분포 (RWA 가중)",
            value_fmt=_won,
            colors=[viz.PALETTE[0]] * len(kh),
        )
    else:
        k_hist_chart = ""

    # LGD downturn
    ld = deep.lgd_downturn
    ld_rows = []
    if isinstance(ld, dict) and "by_class" in ld and not ld["by_class"].empty:
        for _, row in ld["by_class"].iterrows():
            ld_rows.append([row["asset_class"], _won(row["rwa_base"]),
                            _won(row["rwa_down"]),
                            f"+{_won(row['uplift'])}",
                            f"+{row['uplift_pct']*100:.2f}%"])
    ld_msg = (
        f"LGD downturn (max(LGD, 1.06·LGD)) 적용 시 IRB RWA = "
        f"<b>{_won(ld.get('rwa_base', 0))}</b> → "
        f"<b>{_won(ld.get('rwa_downturn', 0))}</b> "
        f"(+{ld.get('uplift_pct', 0)*100:.2f}%). CRE32.41 anchor multiplier 기준."
    )

    # AIRB vs FIRB
    fi = deep.firb
    fi_rows = []
    if isinstance(fi, dict) and "by_class" in fi and not fi["by_class"].empty:
        for _, row in fi["by_class"].iterrows():
            fi_rows.append([row["asset_class"],
                            f"{row['lgd_airb']*100:.1f}%",
                            f"{row['lgd_firb']*100:.1f}%",
                            _won(row["rwa_airb"]),
                            _won(row["rwa_firb"]),
                            f"{(row['rwa_firb']-row['rwa_airb'])/(row['rwa_airb'] or 1)*100:+.1f}%"])
    fi_msg = (
        f"AIRB(자체 LGD) → FIRB(고정 LGD 45%/75%) 전환 시 IRB RWA = "
        f"<b>{_won(fi.get('rwa_airb', 0))}</b> → "
        f"<b>{_won(fi.get('rwa_firb', 0))}</b> "
        f"({fi.get('delta_pct', 0)*100:+.2f}%). 코퍼레이트는 통상 +방향."
    )

    body = f"""
<h1 class="title">29. IRB Deep-Dive — CRE31/CRE32</h1>
<p class="section-lead">자산군별 PD/LGD/M/ρ/K 분포와 LGD downturn 시나리오 + AIRB↔FIRB 시뮬레이션.</p>

<div class="row2">
<div class="card"><h2>29-1. 가중평균 K</h2><div class="chart">{k_chart}</div></div>
<div class="card"><h2>29-2. 평균 자산상관 ρ</h2><div class="chart">{rho_chart}</div></div>
</div>

<div class="card"><h2>29-3. 자산군별 IRB 분해</h2>
{_table(["자산군","건수","EAD","평균 PD","평균 LGD","평균 M","평균 ρ","평균 K","RWA"],
        irb_rows, right_cols=[1,2,3,4,5,6,7,8])}
<p style="font-size:12px;color:#6b7280">
ρ = 0.12·w + 0.24·(1−w) (corporate), 0.15 (mortgage), 0.04 (revolving),
0.03·w + 0.16·(1−w) (retail_other). M floor 1y, cap 5y (CRE31.6).
</p>
</div>

<div class="card"><h2>29-4. K(자본요구계수) 분포</h2>
<div class="chart">{k_hist_chart}</div>
</div>

<div class="card"><h2>29-5. LGD downturn 시나리오 (CRE32.41)</h2>
{_table(["자산군","RWA(기준)","RWA(downturn)","증가분","증가율"], ld_rows,
        right_cols=[1,2,3,4])}
<div class="callout">{ld_msg}</div>
</div>

<div class="card"><h2>29-6. AIRB vs FIRB 시뮬레이션 (CRE32.13)</h2>
{_table(["자산군","LGD(AIRB)","LGD(FIRB)","RWA(AIRB)","RWA(FIRB)","Δ"],
        fi_rows, right_cols=[1,2,3,4,5])}
<div class="callout">{fi_msg}</div>
</div>
"""
    return _page("IRB Deep-Dive", body, "29_irb_deep.html")


def page_market_risk_deep(r: PipelineResult) -> str:
    """30. 시장리스크 Deep-Dive — VaR/SVaR + Delta/Vega/Curvature."""
    deep = getattr(r, "rwa_deep", None)
    if deep is None or deep.market is None:
        return _placeholder_page(
            "30. 시장리스크 Deep-Dive", "시장리스크 데이터가 없습니다.",
            "30_market_risk_deep.html",
        )
    m = deep.market
    bc = m.by_class
    bc_chart = viz.bar_chart(
        bc["risk_class"].tolist(),
        bc["rwa"].tolist(),
        title="시장리스크 RWA — 위험클래스별 (MAR40)",
        value_fmt=_won,
        colors=[viz.PALETTE[i % len(viz.PALETTE)] for i in range(len(bc))],
    )
    bc_rows = [[row["risk_class"], _won(row["capital_charge"]),
                _won(row["rwa"]), f"{row['share']*100:.1f}%"]
               for _, row in bc.iterrows()]

    # VaR / SVaR table
    vt = m.var_table
    vt_rows = [[row["risk_class"], _won(row["abs_position"]),
                f"{row['sigma']*100:.1f}%", _won(row["var_99"]),
                _won(row["es_975"]), _won(row["svar_99"])]
               for _, row in vt.iterrows()]
    var_block = ""
    if not vt.empty:
        var_chart = viz.bar_chart(
            vt["risk_class"].tolist(),
            vt["var_99"].tolist(),
            title="VaR 99% (10일) — 위험클래스별",
            value_fmt=_won,
            colors=[viz.PALETTE[0]] * len(vt),
        )
        svar_chart = viz.bar_chart(
            vt["risk_class"].tolist(),
            vt["svar_99"].tolist(),
            title="Stressed VaR 99% — 위험클래스별",
            value_fmt=_won,
            colors=[viz.RED] * len(vt),
        )
        var_block = f"""
<div class="row2">
<div class="card"><div class="chart">{var_chart}</div></div>
<div class="card"><div class="chart">{svar_chart}</div></div>
</div>
"""

    # Capital comparison
    cc = m.capital_compare
    cc_chart = viz.horizontal_bar(
        cc["approach"].tolist(),
        cc["capital"].tolist(),
        title="자본요구액 비교 — 접근법별",
        value_fmt=_won,
    )

    # Sensitivities (Delta/Vega/Curvature)
    sens = m.sensitivities
    sens_block = ""
    if not sens.empty:
        sens_chart = viz.stacked_bar(
            sens["risk_class"].tolist(),
            {"Delta": sens["delta"].tolist(),
             "Vega": sens["vega"].tolist(),
             "Curvature": sens["curvature"].tolist()},
            title="Sensitivities-based 자본요구액 (FRTB SA, MAR21)",
            value_fmt=_won,
        )
        sens_rows = [[row["risk_class"], _won(row["delta"]),
                      _won(row["vega"]), _won(row["curvature"]),
                      _won(row["total"])]
                     for _, row in sens.iterrows()]
        sens_block = f"""
<div class="card"><h2>30-4. Sensitivities (Delta·Vega·Curvature)</h2>
<div class="chart">{sens_chart}</div>
{_table(["위험클래스","Delta","Vega","Curvature","합계"], sens_rows,
        right_cols=[1,2,3,4])}
</div>"""

    body = f"""
<h1 class="title">30. 시장리스크 Deep-Dive — MAR20/MAR21</h1>
<p class="section-lead">SA(MAR40) + 파라메트릭 VaR/ES/SVaR + Delta·Vega·Curvature 분해.</p>

<div class="kpi-grid">
{_kpi("VaR 99% (10일)", _won(m.var_total))}
{_kpi("ES 97.5%", _won(m.es_total))}
{_kpi("Stressed VaR 99%", _won(m.svar_total))}
{_kpi("VaR + SVaR (IMA 가산)", _won(m.var_total + m.svar_total))}
</div>

<div class="card"><h2>30-1. 위험클래스별 RWA (MAR40)</h2>
<div class="chart">{bc_chart}</div>
{_table(["위험클래스","자본요구액","RWA","비중"], bc_rows, right_cols=[1,2,3])}
</div>

<div class="card"><h2>30-2. 파라메트릭 VaR · ES · SVaR</h2>
{_table(["위험클래스","|순포지션|","σ(연환산)","VaR 99% (10일)","ES 97.5%","SVaR 99%"],
        vt_rows, right_cols=[1,2,3,4,5])}
{var_block}
<p style="font-size:12px;color:#6b7280">VaR = z(0.99)·σ·√(10/250)·|포지션|.
ES = σ·φ(z(0.975))/(1−0.975)·√(10/250)·|포지션|. SVaR = 2.5×VaR (스트레스 윈도우).</p>
</div>

<div class="card"><h2>30-3. 접근법별 자본요구액 비교</h2>
<div class="chart">{cc_chart}</div>
</div>

{sens_block}
"""
    return _page("시장 D-D", body, "30_market_risk_deep.html")


def page_op_risk_deep(r: PipelineResult) -> str:
    """31. 운영리스크 Deep-Dive — BI 분해 + ILM + SMA vs LDA."""
    deep = getattr(r, "rwa_deep", None)
    if deep is None or deep.op is None:
        return _placeholder_page(
            "31. 운영리스크 Deep-Dive", "운영리스크 데이터가 없습니다.",
            "31_op_risk_deep.html",
        )
    op_d = deep.op

    bi_dec = op_d.bi_decomp
    components = bi_dec.iloc[:3]  # exclude total row
    bi_chart = viz.donut_chart(
        components["component"].tolist(),
        components["value"].tolist(),
        title="Business Indicator 구성 (OPE25)",
        center_label=f"BI={components['value'].sum()/1e12:.1f}\n조원",
    )
    bi_rows = [[row["component"], _won(row["value"]),
                f"{row['share']*100:.1f}%"]
               for _, row in bi_dec.iterrows()]

    bk = op_d.bucket_decomp
    bk_chart = viz.bar_chart(
        bk["bucket"].tolist(),
        bk["marginal_bic"].tolist(),
        title="BIC 버킷별 한계 기여액 (OPE25.2)",
        value_fmt=_won,
        colors=[viz.GREEN, viz.AMBER, viz.RED],
    )
    bk_rows = [[row["bucket"],
                _won(row["lower"]) if row["lower"] != float("inf") else "∞",
                _won(row["upper"]) if row["upper"] != float("inf") else "∞",
                f"{row['coefficient']*100:.0f}%",
                _won(row["applied"]),
                _won(row["marginal_bic"])]
               for _, row in bk.iterrows()]

    # SMA vs LDA
    sma_lda_chart = viz.bar_chart(
        ["SMA 자본 (ORC)", "LDA VaR 99.9%"],
        [op_d.sma_capital, op_d.lda_var_999],
        title="SMA vs LDA 자본요구액 비교",
        value_fmt=_won,
        colors=[viz.PALETTE[0], viz.PALETTE[2]],
    )

    ratio_text = (f"SMA / LDA = <b>{op_d.ratio_sma_lda:.2f}x</b>"
                  if not pd.isna(op_d.ratio_sma_lda) else "LDA 미산출")

    body = f"""
<h1 class="title">31. 운영리스크 Deep-Dive — OPE25</h1>
<p class="section-lead">Business Indicator 분해, BIC 버킷별 한계 기여, SMA vs LDA 비교.</p>

<div class="kpi-grid">
{_kpi("BI (Business Indicator)", _won(bi_dec.iloc[-1]['value']))}
{_kpi("BIC (Component)", _won(op_d.sma_capital))}
{_kpi("LDA VaR 99.9%", _won(op_d.lda_var_999))}
{_kpi("SMA / LDA 비율", ratio_text)}
</div>

<div class="row2">
<div class="card"><h2>31-1. BI 구성 (ILDC·SC·FC)</h2>
<div class="chart">{bi_chart}</div>
{_table(["구성","금액","비중"], bi_rows, right_cols=[1,2])}
</div>
<div class="card"><h2>31-2. BIC 버킷별 한계계수 (12% / 15% / 18%)</h2>
<div class="chart">{bk_chart}</div>
{_table(["버킷","하한","상한","계수","적용액","한계 BIC"], bk_rows,
        right_cols=[1,2,3,4,5])}
</div>
</div>

<div class="card"><h2>31-3. SMA vs LDA 비교</h2>
<div class="chart">{sma_lda_chart}</div>
<p>SMA(표준방법)은 BI 버킷 + ILM(국가재량 시 1.0) 기반의 일정량 자본,
LDA는 손실 분포로부터 99.9% VaR로 산출. 두 수치의 격차는 ICAAP의 Pillar 2 가산 판단 근거가 됩니다.</p>
</div>
"""
    return _page("운영 D-D", body, "31_op_risk_deep.html")


# ============================================================================
# 32. 자본 스택 분해 — CRE40
# ============================================================================


def _fmt_signed_won(v: float) -> str:
    if v >= 0:
        return _won(v)
    return f"({_won(-v)})"


def page_capital_stack(r: PipelineResult) -> str:
    """32. 자본 스택 항목별 분해 — CET1 / AT1 / Tier2 + recognition limits."""
    deep = getattr(r, "bis_deep", None)
    if deep is None:
        return _placeholder_page(
            "32. 자본 스택", "BIS deep 데이터가 없습니다.", "32_capital_stack.html")
    cet1 = deep.cet1; at1 = deep.at1; t2 = deep.tier2

    # CET1 waterfall: gross items plus deductions
    cet1_df = deep.cet1_table
    cet1_chart = viz.waterfall(
        cet1_df["item"].tolist() + ["CET1 (차감 후)"],
        cet1_df["amount"].tolist() + [cet1.net - cet1_df["amount"].sum() + cet1.net],
        title="CET1 waterfall — 항목별 가감 (CRE40)",
        value_fmt=_won,
    )
    cet1_rows = [[row["item"], _fmt_signed_won(row["amount"]),
                  row["ref"]] for _, row in cet1_df.iterrows()]
    cet1_rows.append(["<b>CET1 합계 (차감 후)</b>", f"<b>{_won(cet1.net)}</b>", ""])

    at1_rows = [[row["item"], _fmt_signed_won(row["amount"]), row["ref"]]
                for _, row in deep.at1_table.iterrows()]
    at1_rows.append(["<b>AT1 합계</b>", f"<b>{_won(at1.net)}</b>", ""])

    t2_rows = [[row["item"], _fmt_signed_won(row["amount"]), row["ref"]]
               for _, row in deep.tier2_table.iterrows()]
    t2_rows.append(["<b>Tier2 합계</b>", f"<b>{_won(t2.net)}</b>", ""])

    # Stacked composition chart
    stack_chart = viz.stacked_bar(
        ["자본 구성"],
        {"CET1": [cet1.net], "AT1": [at1.net], "Tier2": [t2.net]},
        title="총자본 구성 (CET1 + AT1 + Tier2)",
        value_fmt=_won,
    )

    # Threshold (15%) test
    th = deep.threshold_test
    th_rows = []
    for item in th["individual"]:
        th_rows.append([item.item, _won(item.amount), _won(item.threshold),
                        _won(item.recognised), _won(item.deducted)])
    th_msg = (
        f"개별 한도 (CET1의 10%) = <b>{_won(th['individual_limit'])}</b>, "
        f"3항목 합산 한도 (15%) = <b>{_won(th['combined_limit'])}</b>. "
        f"합산 인정액 <b>{_won(th['recognised_aggregate'])}</b>, "
        f"합산 초과 차감 <b>{_won(th['combined_excess_deducted'])}</b>, "
        f"총 차감 <b>{_won(th['total_deducted'])}</b>."
    )

    # AT1 / T2 recognition limits
    rec = deep.recognition
    rec_rows = [
        ["AT1", _won(at1.net), _won(rec["at1_cap"]),
         _won(rec["at1_recognised"]), _won(rec["at1_excess"])],
        ["Tier2", _won(t2.net), _won(rec["t2_cap"]),
         _won(rec["t2_recognised"]), _won(rec["t2_excess"])],
    ]

    body = f"""
<h1 class="title">32. 자본 스택 분해 — CRE40</h1>
<p class="section-lead">감독목적 자본 (CET1 / AT1 / Tier2) 항목별 분해와 인정 한도 점검.
Basel III CRE40 / 금감원 감독세칙 §2-1 자본의 정의.</p>

<div class="kpi-grid">
{_kpi("CET1 (차감 후)", _won(cet1.net),
       sub=f"gross {_won(cet1.gross)} − 차감 {_won(cet1.total_deductions)}")}
{_kpi("AT1", _won(at1.net))}
{_kpi("Tier2", _won(t2.net))}
{_kpi("Total Capital", _won(cet1.net + at1.net + t2.net))}
</div>

<div class="card"><h2>32-1. 총자본 구성</h2>
<div class="chart">{stack_chart}</div>
</div>

<div class="card"><h2>32-2. CET1 waterfall — 항목별 가감</h2>
<div class="chart">{cet1_chart}</div>
{_table(["항목","금액","규정 출처"], cet1_rows, right_cols=[1])}
<p style="font-size:12px;color:#6b7280">차감 항목은 괄호 표기.
영업권/무형자산/DTA 한도초과 등은 CET1에서 직접 차감 (CRE40.5~CRE40.11).</p>
</div>

<div class="card"><h2>32-3. AT1 — 기타기본자본 (CRE40.27)</h2>
{_table(["항목","금액","규정 출처"], at1_rows, right_cols=[1])}
</div>

<div class="card"><h2>32-4. Tier2 — 보완자본 (CRE40.42)</h2>
{_table(["항목","금액","규정 출처"], t2_rows, right_cols=[1])}
<p style="font-size:12px;color:#6b7280">후순위채 잔존만기 < 5y 부분은 매년 20%씩 인정금액 차감.
일반대손충당금은 IRB RWA의 1.25% 한도 내에서만 인정 (CRE40.45).</p>
</div>

<div class="card"><h2>32-5. 15% Threshold Test — DTA / MSR / 중요투자 (CRE40.10)</h2>
{_table(["항목","총 잔액","개별 한도","인정","차감"], th_rows, right_cols=[1,2,3,4])}
<div class="callout">{th_msg}</div>
</div>

<div class="card"><h2>32-6. AT1 · Tier2 인정 한도 (감독세칙 §2-1-2/3)</h2>
{_table(["계층","순 보유","인정 한도","인정","초과(미인정)"], rec_rows, right_cols=[1,2,3,4])}
<p style="font-size:12px;color:#6b7280">
AT1 인정 한도 = CET1 × 1.5/4.5 (Tier1 6% 도달 시점).
Tier2 인정 한도 = (CET1 + 인정 AT1) × 2/6 (Total 8% 도달 시점).</p>
</div>
"""
    return _page("자본 스택", body, "32_capital_stack.html")


# ============================================================================
# 33. Buffer layering — P1 → CBR → P2R → P2G → OCR
# ============================================================================


def page_buffer_layering(r: PipelineResult) -> str:
    """33. Buffer layering — 자본 요구의 layer + 국가 CCyB + DSIB 등급."""
    deep = getattr(r, "bis_deep", None)
    if deep is None:
        return _placeholder_page(
            "33. 버퍼 layering", "BIS deep 데이터가 없습니다.",
            "33_buffer_layering.html")

    layer = deep.layering
    layer_df = deep.layering_table
    srep = deep.srep

    # Waterfall — cumulative layer build-up
    layer_chart = viz.waterfall(
        ["기준 0%"] + layer_df["layer"].tolist() + ["OCR 합계"],
        [0.0] + layer_df["increment"].tolist() + [layer.ocr_cet1],
        title="CET1 요구 layering — Pillar 1 → CBR → P2R → P2G → OCR",
        value_fmt=_pct,
    )

    # Comparison vs. actual CET1
    cmp_chart = viz.bar_chart(
        ["P1", "P1+CBR (MDA)", "+P2R (SREP)", "+P2G (OCR)", "실측 CET1"],
        [layer.p1_cet1, layer.mda_threshold_cet1,
         layer.srep_cet1, layer.ocr_cet1, srep.cet1_ratio],
        value_fmt=_pct,
        title="요구 layer 별 vs 실측 CET1",
        colors=[viz.PALETTE[0], viz.PALETTE[1], viz.AMBER,
                viz.RED, viz.GREEN if srep.ocr_pass else viz.RED],
        reference_value=srep.cet1_ratio,
        reference_label=f"실측 {_pct(srep.cet1_ratio)}",
    )

    layer_rows = []
    cum = 0.0
    for _, row in layer_df.iterrows():
        cum = row["cumulative"]
        layer_rows.append([row["layer"], _pct(row["increment"]),
                           _pct(cum), row["ref"]])

    # Country CCyB
    cc = deep.country_ccyb
    cc_df = cc["by_country"]
    cc_rows = [[row["country"], _won(row["exposure"]),
                f"{row['share']*100:.1f}%",
                _pct(row["ccyb"]),
                f"{row['weighted']*100:.3f}%p"]
               for _, row in cc_df.iterrows()]
    cc_msg = (f"가중평균 CCyB = <b>{_pct(cc['weighted_ccyb'])}</b> "
              f"(국가별 CCyB율 × 익스포저 가중치).")

    # DSIB buckets table — show all 5
    from risk_lib.capital.bis_deep import DSIB_BUCKETS
    dsib_rows = [[str(b), _pct(rate),
                  ("<b>현재 적용</b>" if abs(rate - layer.dsib) < 1e-9 else "")]
                 for b, rate in DSIB_BUCKETS.items()]

    # SREP status badges
    status_tone = "good" if srep.ocr_pass else ("warn" if srep.srep_pass else "bad")
    status_text = srep.overall_status()

    # Surplus vs SREP / OCR
    surplus_chart = viz.bar_chart(
        ["P1 잉여", "MDA 잉여", "SREP 잉여", "OCR 잉여"],
        [srep.cet1_ratio - layer.p1_cet1,
         srep.cet1_ratio - layer.mda_threshold_cet1,
         srep.surplus_to_srep, srep.surplus_to_ocr],
        value_fmt=lambda v: f"{v*100:+.2f}%p",
        title="요구 layer 대비 CET1 잉여 / 부족",
        colors=[viz.GREEN if v >= 0 else viz.RED
                for v in [srep.cet1_ratio - layer.p1_cet1,
                          srep.cet1_ratio - layer.mda_threshold_cet1,
                          srep.surplus_to_srep, srep.surplus_to_ocr]],
    )

    body = f"""
<h1 class="title">33. Buffer Layering — RBC20 / RBC40 / SRP20</h1>
<p class="section-lead">자본 요구의 5단 layering — Pillar 1 (4.5%) → CBR (CCB + CCyB + DSIB)
→ P2R (감독요구) → P2G (감독가이드). SREP 미달은 결재 불가 / P2G 미달은 supervisory dialog.</p>

<div class="kpi-grid">
{_kpi("종합 판정", status_text, tone=status_tone)}
{_kpi("실측 CET1", _pct(srep.cet1_ratio))}
{_kpi("MDA 임계 (P1+CBR)", _pct(layer.mda_threshold_cet1))}
{_kpi("SREP 요구 (P1+CBR+P2R)", _pct(layer.srep_cet1),
       tone="good" if srep.srep_pass else "bad")}
{_kpi("OCR 요구 (P1+CBR+P2R+P2G)", _pct(layer.ocr_cet1),
       tone="good" if srep.ocr_pass else "warn")}
</div>

<div class="card"><h2>33-1. Layer waterfall — 요구 자본의 layer</h2>
<div class="chart">{layer_chart}</div>
{_table(["Layer","증분","누적 요구","규정 출처"], layer_rows, right_cols=[1,2])}
</div>

<div class="card"><h2>33-2. Layer별 요구 vs 실측 CET1</h2>
<div class="chart">{cmp_chart}</div>
<div class="chart">{surplus_chart}</div>
</div>

<div class="card"><h2>33-3. 국가별 CCyB 가중평균 (RBC20 jurisdictional reciprocity)</h2>
{_table(["국가","익스포저","비중","국가 CCyB율","가중기여"],
        cc_rows, right_cols=[1,2,3,4])}
<div class="callout">{cc_msg}</div>
</div>

<div class="card"><h2>33-4. D-SIB 등급별 가산자본률 (RBC40 / 감독세칙)</h2>
{_table(["등급","가산률","비고"], dsib_rows, right_cols=[1])}
<p style="font-size:12px;color:#6b7280">
D-SIB 등급은 금감원 시스템적 중요성 평가(규모/상호연계성/대체가능성/복잡성) 결과에 따라 결정됨.
현 산출은 2등급 가정 (1.5% 가산).</p>
</div>
"""
    return _page("버퍼 layering", body, "33_buffer_layering.html")


# ============================================================================
# 34. Leverage deep — exposure decomposition + G-SIB buffer + AT1 lock
# ============================================================================


def page_leverage_deep(r: PipelineResult) -> str:
    """34. 레버리지 비율 Deep-Dive — 익스포저 측정치 분해 + G-SIB buffer."""
    deep = getattr(r, "leverage_deep", None)
    if deep is None:
        return _placeholder_page(
            "34. 레버리지 Deep-Dive", "leverage deep 데이터가 없습니다.",
            "34_leverage_deep.html")

    br = deep.breakdown
    df = br.to_frame()

    # Horizontal bar chart of exposure components
    comp_chart = viz.horizontal_bar(
        df["component"].tolist(),
        df["exposure"].tolist(),
        title=f"익스포저 측정치 분해 (총 {_won(br.total_exposure)})",
        value_fmt=_won,
    )
    comp_rows = [[row["component"], _won(row["notional"]),
                  f"{row['factor']:.2f}",
                  _won(row["exposure"]),
                  f"{row['share']*100:.1f}%"]
                 for _, row in df.iterrows()]
    comp_rows.append(["<b>합계</b>", "—", "—",
                      f"<b>{_won(br.total_exposure)}</b>", "100.0%"])

    # Donut composition
    donut = viz.donut_chart(
        df["component"].tolist(),
        df["exposure"].tolist(),
        title="익스포저 구성",
        center_label=f"{br.total_exposure/1e12:.1f}\n조원",
    )

    # Leverage ratio vs requirements bar
    lr_chart = viz.bar_chart(
        ["최저 3%", "+G-SIB buffer", "실측 LR"],
        [deep.minimum, deep.requirement_total, deep.leverage_ratio],
        value_fmt=_pct,
        title="레버리지 비율 — 최저 + G-SIB buffer",
        colors=[viz.PALETTE[0], viz.AMBER,
                viz.GREEN if deep.passes_with_buffer else viz.RED],
        reference_value=deep.requirement_total,
        reference_label=f"요구 {_pct(deep.requirement_total)}",
    )

    # MDA-equivalent gauge
    m = deep.mda
    mda_text = ("정상 — 분배 제한 없음" if not m.in_breach
                else f"buffer 침범 {m.buffer_quartile}분위 — 분배 {m.distributable_pct*100:.0f}% 허용")
    mda_tone = "good" if not m.in_breach else "bad"

    surplus_pp = deep.surplus_shortfall * 100
    surplus_text = f"{surplus_pp:+.2f}%p vs 요구 {_pct(deep.requirement_total)}"
    surplus_tone = "good" if surplus_pp >= 0 else "bad"

    body = f"""
<h1 class="title">34. 레버리지 비율 Deep-Dive — LEV10 / LEV30 / LEV40</h1>
<p class="section-lead">위험기반 비율의 backstop. 익스포저 측정치(EM) = 대차대조표 + 파생(SA-CCR) + SFT
+ 부외(CCF). 최저 3% + G-SIB leverage buffer (LEV40, 위험기반 G-SIB 버퍼의 50%).</p>

<div class="kpi-grid">
{_kpi("레버리지 비율", _pct(deep.leverage_ratio),
       sub=surplus_text, tone=surplus_tone)}
{_kpi("Tier1 자본", _won(deep.tier1))}
{_kpi("익스포저 측정치", _won(deep.breakdown.total_exposure))}
{_kpi("G-SIB leverage buffer", _pct(deep.gsib_buffer),
       sub="= 위험기반 G-SIB buffer의 50%")}
{_kpi("MDA 상태", mda_text, tone=mda_tone)}
</div>

<div class="row2">
<div class="card"><h2>34-1. 익스포저 측정치 구성</h2>
<div class="chart">{donut}</div>
</div>
<div class="card"><h2>34-2. 익스포저 구성 항목 (LEV30)</h2>
<div class="chart">{comp_chart}</div>
</div>
</div>

<div class="card"><h2>34-3. 익스포저 분해 표</h2>
{_table(["구성","notional","factor","익스포저","비중"],
        comp_rows, right_cols=[1,2,3,4])}
<p style="font-size:12px;color:#6b7280">
파생: RC + α·PFE (α=1.4, SA-CCR LEV30.20).
SFT: gross − 담보offset (단순화).
부외: notional × CCF, 최저 10% (LEV30.11).</p>
</div>

<div class="card"><h2>34-4. 레버리지 비율 vs 요구</h2>
<div class="chart">{lr_chart}</div>
<p>최저 3% (LEV10.6) + G-SIB leverage buffer (LEV40.5).
KR 국내 시중은행은 통상 G-SIB 미지정이므로 가산 0% 적용.</p>
</div>

<div class="card"><h2>34-5. AT1 쿠폰 분배제한 (LEV40 analogue)</h2>
{_table(["항목","값"],
        [["요구 합계 (최저 + G-SIB buffer)", _pct(deep.requirement_total)],
         ["실측 LR", _pct(deep.leverage_ratio)],
         ["buffer 부족", _pct(m.buffer_shortfall) if m.in_breach else "—"],
         ["buffer 분위", str(m.buffer_quartile) if m.in_breach else "—"],
         ["요구 보유율", _pct(m.retention_ratio)],
         ["분배가능 비율", _pct(m.distributable_pct)]],
        right_cols=[1])}
<p style="font-size:12px;color:#6b7280">
레버리지 buffer 침범 시 risk-based MDA와 동일한 4분위 분배제한 적용.</p>
</div>
"""
    return _page("레버리지 D-D", body, "34_leverage_deep.html")
