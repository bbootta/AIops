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

    # v0.11.0 — 계층 HHI, Top-N, Gini, wrong-way, 섹터간 상관
    hier_block = ""
    ch = getattr(r, "concentration_hier", None) or {}
    if ch:
        hier = ch.get("hierarchical_hhi", pd.DataFrame())
        top_n = ch.get("top_n", pd.DataFrame())
        gini = float(ch.get("gini_obligor", 0.0))
        lorenz = ch.get("lorenz_obligor", pd.DataFrame())
        ww = ch.get("wrong_way", pd.DataFrame())
        scorr = ch.get("sector_correlation", pd.DataFrame())

        hier_chart = viz.bar_chart(
            hier["label"].tolist(), hier["hhi"].tolist(),
            value_fmt=lambda v: f"{v:.3f}",
            title="계층별 HHI (차주→그룹→섹터→KSIC→국가→상품→만기)",
            reference_value=0.18, reference_label="고집중 0.18",
            colors=[viz.RED if v >= 0.18 else (viz.AMBER if v >= 0.10 else viz.GREEN)
                    for v in hier["hhi"]],
        )
        hier_rows = [[r2["label"], r2["dimension"],
                      f"{int(r2['n_buckets']):,}",
                      f"{r2['hhi']:.4f}",
                      f"{r2['normalised_hhi']:.4f}",
                      _pct(r2["top1_share"])]
                     for _, r2 in hier.iterrows()]
        # Top-N (5/10/20) stacked bar
        top_n_series: dict[str, list[float]] = {
            "상위5": [], "상위6-10": [], "상위11-20": [], "그외": [],
        }
        for _, r2 in top_n.iterrows():
            t5 = float(r2.get("top_5_share", 0))
            t10 = float(r2.get("top_10_share", 0))
            t20 = float(r2.get("top_20_share", 0))
            top_n_series["상위5"].append(t5)
            top_n_series["상위6-10"].append(max(0, t10 - t5))
            top_n_series["상위11-20"].append(max(0, t20 - t10))
            top_n_series["그외"].append(max(0, 1 - t20))
        topn_chart = viz.stacked_bar(
            top_n["dimension"].tolist(), top_n_series,
            title="Top-N 집중도 (점유율)", value_fmt=_pct,
        )
        topn_rows = [[r2["dimension"], f"{int(r2['n_total']):,}",
                      _pct(r2["top_5_share"]), _pct(r2["top_10_share"]),
                      _pct(r2["top_20_share"])]
                     for _, r2 in top_n.iterrows()]

        # Lorenz curve
        lorenz_chart = ""
        if not lorenz.empty:
            lorenz_chart = viz.line_chart(
                [f"{v*100:.0f}%" for v in lorenz["cum_pop"]],
                {"누적 EAD 비중": lorenz["cum_value"].tolist(),
                 "완전평등": lorenz["cum_pop"].tolist()},
                title=f"Lorenz curve · Gini={gini:.3f}",
                value_fmt=lambda v: f"{v*100:.0f}%",
            )

        # Wrong-way risk bar
        ww_chart = ""
        if not ww.empty:
            ww_chart = viz.horizontal_bar(
                ww["sector"].tolist()[:10],
                ww["ead_weighted_uplift"].tolist()[:10],
                title="섹터별 wrong-way 가산 (EAD × LGD downturn)",
                value_fmt=_won, color=viz.RED,
            )

        # Sector systemic correlation heatmap
        scorr_chart = ""
        if not scorr.empty:
            secs = list(scorr.index)
            mat = [[float(scorr.loc[a, b]) for b in secs] for a in secs]
            scorr_chart = viz_advanced.heatmap(
                secs, secs, mat,
                title="섹터간 자산상관 (synthetic)",
                value_fmt=lambda v: f"{v:.2f}",
            )

        ww_rows = [[r2["sector"], f"{r2['rho_pd_lgd']:.2f}",
                    _won(r2["ead"]), _pct(r2["downturn_lgd_uplift"], 1),
                    _won(r2["ead_weighted_uplift"])]
                   for _, r2 in ww.head(10).iterrows()]

        hier_block = f"""
<div class="kpi-grid">
{_kpi("계층 HHI 최고", hier.loc[hier['hhi'].idxmax(), 'label'] if not hier.empty else '-',
       sub=f"HHI {hier['hhi'].max():.3f}" if not hier.empty else "")}
{_kpi("차주 EAD Gini", f"{gini:.3f}",
       sub="0=평등, 1=완전집중")}
{_kpi("상위 10 차주 점유율",
       _pct(top_n[top_n['dimension']=='obligor_id']['top_10_share'].iloc[0]) if not top_n.empty else "-")}
{_kpi("wrong-way 합산", _won(ww['ead_weighted_uplift'].sum() if not ww.empty else 0),
       sub="섹터별 EAD × LGD downturn")}
</div>

<div class="card"><h2>18-5. 계층 HHI</h2>
<div class="chart">{hier_chart}</div>
{_table(["라벨","차원","버킷수","HHI","정규화 HHI","최대비중"],
        hier_rows, right_cols=[2,3,4,5])}
</div>

<div class="card"><h2>18-6. Top-N 차주/그룹/섹터 집중도</h2>
<div class="chart">{topn_chart}</div>
{_table(["차원","전체","상위5","상위10","상위20"], topn_rows, right_cols=[1,2,3,4])}
</div>

<div class="row2">
<div class="card"><h2>18-7. Lorenz curve & Gini</h2>
<div class="chart">{lorenz_chart}</div>
<p class="section-lead">Gini = {gini:.3f} (0=완전평등, 1=완전집중)</p>
</div>
<div class="card"><h2>18-8. 섹터간 자산상관 (Wrong-way)</h2>
<div class="chart">{scorr_chart}</div>
</div>
</div>

<div class="card"><h2>18-9. Wrong-way risk — 섹터별 LGD downturn</h2>
<div class="chart">{ww_chart}</div>
{_table(["섹터","ρ(PD,LGD)","EAD","downturn 가산률","EAD×가산"],
        ww_rows, right_cols=[1,2,3,4])}
<p class="section-lead">차주 부도 시 담보가치 동조 하락 — BCBS LGD downturn (Article 181) 가정.</p>
</div>
"""

    body = f"""
<h1 class="title">18. 집중리스크 deep-dive</h1>
<p class="section-lead">차주별/섹터×국가/한도위반 deep-dive + Gordy granularity addon
+ 계층 HHI + Top-N + Gini + Wrong-way (v0.11.0).</p>

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

{hier_block}
"""
    return _page("집중 deep-dive", body, "18_concentration_deep.html")


# ---------------------------------------------------------------- 42 limit dashboard

def page_limit_dashboard(r: PipelineResult) -> str:
    """다차원 한도(동일차주/그룹/섹터/국가/상품/만기) 실시간 사용률 grid."""
    if getattr(r, "limits_deep", None) is None:
        body = "<h1 class='title'>42. 한도 dashboard</h1><p>한도 deep-dive 미가용.</p>"
        return _page("한도 dashboard", body, "42_limit_dashboard.html")
    ld = r.limits_deep
    dash = ld.dashboard
    actions = ld.actions
    trend = ld.utilisation_trend
    breach_log = ld.breach_log
    summary = ld.summary

    # 상위 20 사용률 horizontal bar (등급 색상)
    top20 = dash.head(20)
    sev_colors = {"BREACH": viz.RED, "CRITICAL": "#E07A1F",
                  "WARN": viz.AMBER, "OK": viz.GREEN}
    # use single color for horizontal_bar; use stacked? Keep simple - per-row not supported.
    util_chart = viz.horizontal_bar(
        [f"{row['dimension']}:{str(row['bucket'])[:12]}" for _, row in top20.iterrows()],
        top20["utilisation"].tolist(),
        value_fmt=_pct, title="한도 사용률 상위 20", color=viz.RED,
        reference_value=1.0, reference_label="100%",
    )

    # severity 분포 도넛
    sev_counts = dash["severity"].value_counts().to_dict()
    sev_chart = viz.donut_chart(
        ["OK", "WARN", "CRITICAL", "BREACH"],
        [sev_counts.get(s, 0) for s in ["OK","WARN","CRITICAL","BREACH"]],
        title=f"severity 분포 (총 {len(dash):,})",
    )

    # 차원별 한도 수 + 위반/경보 표
    dim_summary = (dash.groupby("dimension")
                       .agg(n_rows=("limit", "size"),
                            max_util=("utilisation", "max"),
                            n_warn=("severity", lambda s: (s=="WARN").sum()),
                            n_crit=("severity", lambda s: (s=="CRITICAL").sum()),
                            n_breach=("severity", lambda s: (s=="BREACH").sum()))
                       .reset_index().sort_values("max_util", ascending=False))
    dim_rows = [[r2["dimension"], f"{int(r2['n_rows']):,}",
                 _pct(r2["max_util"], 1), f"{int(r2['n_warn']):,}",
                 f"{int(r2['n_crit']):,}", f"{int(r2['n_breach']):,}"]
                for _, r2 in dim_summary.iterrows()]

    # 분기별 위반 건수 trend (stacked)
    breach_trend = ""
    if not breach_log.empty:
        breach_trend = viz.stacked_bar(
            breach_log["quarter"].tolist(),
            {"WARN": breach_log["WARN"].tolist(),
             "CRITICAL": breach_log["CRITICAL"].tolist(),
             "BREACH": breach_log["BREACH"].tolist()},
            title="분기별 한도 위반 건수 추이",
            value_fmt=lambda v: f"{int(v)}",
        )

    # 상위 5 한도 사용률 trend line
    trend_chart = ""
    if not trend.empty:
        # pick 5 limits with highest current util
        top5_keys = dash.head(5).apply(
            lambda r2: f"{r2['limit']}|{r2['bucket']}", axis=1).tolist()
        series = {}
        quarters = sorted(trend["quarter"].unique().tolist())
        for key in top5_keys:
            lim_name, bucket = key.split("|", 1)
            sub = trend[(trend["limit"] == lim_name) &
                        (trend["bucket"].astype(str) == bucket)]
            if not sub.empty:
                label = f"{lim_name}:{bucket[:10]}"
                series[label] = sub.sort_values("quarter")["utilisation"].tolist()
        if series:
            trend_chart = viz.line_chart(
                quarters, series, title="상위 5 한도 사용률 추이 (합성)",
                value_fmt=_pct, reference_value=1.0, reference_label="100%",
            )

    # 권고조치 표 (상위 15)
    act_rows = [[r2["limit"], str(r2["bucket"])[:14],
                 _badge(r2["severity"],
                        {"BREACH":"FAIL","CRITICAL":"FAIL",
                         "WARN":"WARN","OK":"GREEN"}.get(r2["severity"],"NEUTRAL")),
                 _pct(r2["utilisation"], 1),
                 _esc(r2["action"]),
                 _won(r2["amount"]),
                 _esc(r2["narrative"][:60])]
                for _, r2 in actions.head(15).iterrows()]

    # 한도 grid full table (BREACH+CRITICAL only)
    crit = dash[dash["severity"].isin(["BREACH","CRITICAL","WARN"])].head(30)
    crit_rows = [[r2["limit"], r2["dimension"], str(r2["bucket"])[:14],
                  _won(r2["exposure"]), _won(r2["threshold"]),
                  _pct(r2["utilisation"], 1),
                  _won(r2["headroom"]),
                  _badge(r2["severity"],
                         {"BREACH":"FAIL","CRITICAL":"FAIL",
                          "WARN":"WARN","OK":"GREEN"}.get(r2["severity"],"NEUTRAL"))]
                 for _, r2 in crit.iterrows()]

    body = f"""
<h1 class="title">42. 다차원 한도 Dashboard</h1>
<p class="section-lead">동일차주/그룹/섹터/국가/상품/만기 한도 grid + 사용률 추이 +
권고 조치. 근거: 「은행법」 제35조, 「은행업감독규정」 제29조, BCBS 283 LEX.</p>

<div class="kpi-grid">
{_kpi("총 한도×버킷", f"{summary['n_rows']:,}", sub=f"{summary['n_limits']:,}개 한도")}
{_kpi("WARN", f"{summary['n_warn']:,}", tone="warn")}
{_kpi("CRITICAL", f"{summary['n_critical']:,}", tone="warn")}
{_kpi("BREACH", f"{summary['n_breach']:,}", tone="bad")}
{_kpi("최고 사용률", _pct(summary['max_utilisation'], 1),
       tone="bad" if summary['max_utilisation']>=1.0 else "warn")}
{_kpi("LEX(10%↑) 차주", f"{summary['n_lex_reportable']:,}",
       sub="BCBS LEX 보고대상")}
</div>

<div class="row2">
<div class="card"><h2>42-1. 사용률 상위 20</h2>
<div class="chart">{util_chart}</div></div>
<div class="card"><h2>42-2. severity 분포</h2>
<div class="chart">{sev_chart}</div></div>
</div>

<div class="card"><h2>42-3. 차원별 한도 요약</h2>
{_table(["차원","한도수","최고사용률","WARN","CRITICAL","BREACH"],
        dim_rows, right_cols=[1,2,3,4,5])}
</div>

<div class="row2">
<div class="card"><h2>42-4. 상위 5 한도 사용률 추이 (8개분기)</h2>
<div class="chart">{trend_chart}</div></div>
<div class="card"><h2>42-5. 분기별 위반 건수 추이</h2>
<div class="chart">{breach_trend}</div></div>
</div>

<div class="card"><h2>42-6. 경보 한도 상세 (WARN+CRITICAL+BREACH, 상위 30)</h2>
{_table(["한도","차원","버킷","노출","한도","사용률","여유","등급"],
        crit_rows, right_cols=[3,4,5,6])}
</div>

<div class="card"><h2>42-7. 권고 조치 (action recommendations)</h2>
{_table(["한도","버킷","등급","사용률","조치","금액","해설"],
        act_rows, right_cols=[3,5])}
<p class="section-lead">자동 권고 — CRITICAL/BREACH는 즉시 감축, WARN은
사전경보, OK는 추가가능 노출액 산출.</p>
</div>
"""
    return _page("한도 dashboard", body, "42_limit_dashboard.html")


# ---------------------------------------------------------------- 43 large exposure (LEX)

def page_large_exposure(r: PipelineResult) -> str:
    """BCBS LEX framework — Tier1 10%+ 차주 별도 보고."""
    if getattr(r, "limits_deep", None) is None:
        body = "<h1 class='title'>43. 거대익스포저</h1><p>한도 deep-dive 미가용.</p>"
        return _page("거대익스포저", body, "43_large_exposure.html")
    ld = r.limits_deep
    lex = ld.large_exposure_lex
    lex_g = ld.large_exposure_lex_group
    tier1 = float(r.meta.get("capital").tier1 if r.meta.get("capital") else 0)

    if lex.empty:
        body = f"""
<h1 class="title">43. BCBS LEX 거대익스포저</h1>
<p class="section-lead">BCBS 283 LEX framework — Tier1의 10% 이상 차주 별도 보고.
Tier1 = {_won(tier1)}.</p>
<div class="callout good">현재 Tier1 10% 이상 차주 없음 — 보고 대상 0건.</div>
"""
        return _page("거대익스포저", body, "43_large_exposure.html")

    rows = [[r2["obligor_id"], _won(r2["ead"]),
             _pct(r2["pct_tier1"], 1),
             _pct(r2["utilisation_25pct"], 1),
             _badge(r2["severity"],
                    {"BREACH":"FAIL","CRITICAL":"FAIL","WARN":"WARN","OK":"GREEN"}
                    .get(r2["severity"], "NEUTRAL"))]
            for _, r2 in lex.iterrows()]
    chart = viz.horizontal_bar(
        lex["obligor_id"].tolist()[:15],
        lex["pct_tier1"].tolist()[:15],
        value_fmt=lambda v: f"{v*100:.1f}%",
        title="Tier1 대비 거대익스포저 (상위 15)",
        reference_value=0.25, reference_label="hard limit 25%",
        color=viz.RED,
    )

    # 그룹 단위
    g_rows = [[r2["obligor_group_id"], _won(r2["ead"]),
               _pct(r2["pct_tier1"], 1),
               _pct(r2["utilisation_25pct"], 1),
               _badge(r2["severity"],
                      {"BREACH":"FAIL","CRITICAL":"FAIL","WARN":"WARN","OK":"GREEN"}
                      .get(r2["severity"], "NEUTRAL"))]
              for _, r2 in lex_g.iterrows()]

    body = f"""
<h1 class="title">43. BCBS LEX 거대익스포저</h1>
<p class="section-lead">BCBS 283 (Supervisory framework for measuring and
controlling large exposures, 2014). Tier1의 10% 이상 차주는 보고 대상,
25%는 hard limit (G-SIB간 15%).
Tier1 = {_won(tier1)} · 보고기준 10% = {_won(tier1 * 0.10)} ·
한도 25% = {_won(tier1 * 0.25)}.</p>

<div class="kpi-grid">
{_kpi("LEX 보고 대상 (≥10%)", f"{len(lex):,}건")}
{_kpi("그룹 LEX 보고 대상", f"{len(lex_g):,}건")}
{_kpi("25% 한도 위반",
       f"{int((lex['severity'].isin(['BREACH'])).sum()):,}건",
       tone="bad" if (lex['severity']=='BREACH').any() else "good")}
{_kpi("LEX 최대 비중", _pct(lex['pct_tier1'].max(), 1) if not lex.empty else "-")}
</div>

<div class="card"><h2>43-1. 차주별 거대익스포저 (≥ Tier1 10%)</h2>
<div class="chart">{chart}</div>
{_table(["차주","EAD","Tier1 대비","25%한도 사용률","등급"],
        rows, right_cols=[1,2,3])}
</div>

<div class="card"><h2>43-2. 그룹차주 거대익스포저</h2>
{_table(["그룹","EAD","Tier1 대비","25%한도 사용률","등급"],
        g_rows, right_cols=[1,2,3]) if g_rows else "<p>그룹 LEX 대상 없음.</p>"}
<p class="section-lead">BCBS 283은 connected counterparties를 그룹 단위로
합산 측정할 것을 요구.</p>
</div>
"""
    return _page("거대익스포저", body, "43_large_exposure.html")


# ---------------------------------------------------------------- 44 concentration stress

def page_concentration_stress(r: PipelineResult) -> str:
    """스트레스 시나리오에서의 한도 사용률 변화 + wrong-way."""
    if getattr(r, "limits_deep", None) is None:
        body = "<h1 class='title'>44. 집중 스트레스</h1><p>한도 deep-dive 미가용.</p>"
        return _page("집중 스트레스", body, "44_concentration_stress.html")
    ld = r.limits_deep
    stress = ld.stress_utilisation
    ch = getattr(r, "concentration_hier", None) or {}
    ww = ch.get("wrong_way", pd.DataFrame())
    scorr = ch.get("sector_correlation", pd.DataFrame())

    # 시나리오별 BREACH+CRITICAL 건수
    scen_counts = stress.groupby("scenario")["severity"].value_counts().unstack(
        fill_value=0).reindex(["baseline","adverse","severely_adverse"])
    scen_counts = scen_counts.reindex(columns=["OK","WARN","CRITICAL","BREACH"], fill_value=0)
    scen_chart = viz.stacked_bar(
        scen_counts.index.tolist(),
        {col: scen_counts[col].tolist() for col in
         ["OK","WARN","CRITICAL","BREACH"]},
        title="시나리오별 severity 분포 (한도×버킷)",
        value_fmt=lambda v: f"{int(v):,}",
    )

    # 시나리오별 (baseline → severely_adverse) 사용률 비교: 동일 한도-버킷 매칭
    pivot = stress.pivot_table(
        index=["limit", "bucket"], columns="scenario", values="utilisation"
    ).reset_index()
    pivot["delta_severe"] = pivot.get("severely_adverse", 0) - pivot.get("baseline", 0)
    top_delta = pivot.sort_values("delta_severe", ascending=False).head(15)
    delta_rows = [[r2["limit"], str(r2["bucket"])[:14],
                   _pct(r2.get("baseline", 0), 1),
                   _pct(r2.get("adverse", 0), 1),
                   _pct(r2.get("severely_adverse", 0), 1),
                   f"+{r2['delta_severe']*100:.1f}%p"]
                  for _, r2 in top_delta.iterrows()]

    # 시나리오 사용률 상위 15 (severely_adverse 기준)
    sev_top = stress[stress["scenario"]=="severely_adverse"].sort_values(
        "utilisation", ascending=False).head(15)
    sev_chart = viz.horizontal_bar(
        [f"{r2['limit'][:18]}:{str(r2['bucket'])[:10]}" for _, r2 in sev_top.iterrows()],
        sev_top["utilisation"].tolist(),
        value_fmt=_pct, title="severely_adverse 사용률 상위 15",
        reference_value=1.0, reference_label="100%",
        color=viz.RED,
    )

    # Wrong-way 섹터 heatmap (재사용)
    ww_chart = ""
    if not ww.empty:
        ww_chart = viz.horizontal_bar(
            ww["sector"].tolist()[:10],
            ww["ead_weighted_uplift"].tolist()[:10],
            title="섹터별 Wrong-way 가산 (EAD × LGD downturn)",
            value_fmt=_won, color="#E07A1F",
        )
    scorr_chart = ""
    if not scorr.empty:
        secs = list(scorr.index)
        mat = [[float(scorr.loc[a, b]) for b in secs] for a in secs]
        scorr_chart = viz_advanced.heatmap(
            secs, secs, mat,
            title="섹터간 자산상관 (synthetic) — 동조부도",
            value_fmt=lambda v: f"{v:.2f}",
        )

    n_baseline_breach = int((stress[stress['scenario']=='baseline']['severity'].isin(['BREACH','CRITICAL'])).sum())
    n_severe_breach = int((stress[stress['scenario']=='severely_adverse']['severity'].isin(['BREACH','CRITICAL'])).sum())

    body = f"""
<h1 class="title">44. 집중리스크 스트레스 + Wrong-way</h1>
<p class="section-lead">adverse / severely_adverse 시 EAD multiplier 적용 후
한도 재평가 + 섹터간 동조부도 (wrong-way) 시나리오.</p>

<div class="kpi-grid">
{_kpi("baseline BREACH+CRITICAL", f"{n_baseline_breach:,}", tone="warn")}
{_kpi("severely_adverse 시", f"{n_severe_breach:,}",
       tone="bad" if n_severe_breach > n_baseline_breach else "neutral",
       sub=f"+{n_severe_breach - n_baseline_breach}건 증가")}
{_kpi("severely 시 최고 사용률",
       _pct(stress[stress['scenario']=='severely_adverse']['utilisation'].max(), 1),
       tone="bad")}
{_kpi("wrong-way 합산 가산",
       _won(ww['ead_weighted_uplift'].sum() if not ww.empty else 0))}
</div>

<div class="card"><h2>44-1. 시나리오별 severity 분포</h2>
<div class="chart">{scen_chart}</div>
<p class="section-lead">EAD multiplier: baseline 1.00 · adverse 1.10 · severely_adverse 1.25
(스트레스 시 한도 차감자본은 별도 BIS deep-dive 참조).</p>
</div>

<div class="card"><h2>44-2. severely_adverse 시 사용률 상위 15</h2>
<div class="chart">{sev_chart}</div>
</div>

<div class="card"><h2>44-3. 한도×버킷별 사용률 비교 (Δ severely-baseline 상위 15)</h2>
{_table(["한도","버킷","baseline","adverse","severely","Δsevere"],
        delta_rows, right_cols=[2,3,4,5])}
</div>

<div class="row2">
<div class="card"><h2>44-4. Wrong-way 섹터 우선순위</h2>
<div class="chart">{ww_chart}</div>
<p class="section-lead">차주 부도 시 담보가치 동조 하락 (BCBS LGD downturn).
부동산·건설·선박이 가장 민감.</p>
</div>
<div class="card"><h2>44-5. 섹터간 자산상관 (동조부도)</h2>
<div class="chart">{scorr_chart}</div>
<p class="section-lead">macro driver 공유 섹터 (real_estate-construction,
manufacturing-shipping)는 동조부도 가능성이 높음.</p>
</div>
</div>
"""
    return _page("집중 스트레스", body, "44_concentration_stress.html")


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

    # v0.10.0 — 자산군별 vintage deep + seasoning + drift
    vd = r.monitoring_deep.get("vintage") if r.monitoring_deep else None
    deep_block = ""
    if vd is not None and not vd.by_segment.empty:
        # one line chart per segment, overlaid
        seg_ids = sorted(vd.by_segment["segment"].unique())
        seg_chart_blocks = []
        for seg in seg_ids:
            sub = vd.by_segment[vd.by_segment["segment"] == seg]
            cohorts = sorted(sub["cohort"].unique())[:6]
            qs = sorted(sub["mob"].unique())
            series = {}
            for c in cohorts:
                cs = sub[sub["cohort"] == c].sort_values("mob")
                v = [float(cs[cs["mob"] == m]["cum_default_rate"].iloc[0])
                     if m in cs["mob"].values
                     else float(cs["cum_default_rate"].iloc[-1])
                     for m in qs]
                series[f"M-{c}"] = v
            ch = viz.line_chart(
                [str(m) for m in qs], series, value_fmt=_pct,
                title=f"{seg} — cohort vintage curves",
            )
            seg_chart_blocks.append(
                f'<div class="card"><h3>{_esc(seg)}</h3>'
                f'<div class="chart">{ch}</div></div>'
            )
        seg_charts_html = "<div class='row2'>" + "".join(seg_chart_blocks) + "</div>"

        # seasoning table
        s_rows = [[row["segment"], f"{int(row['peak_mob']):,}",
                   _pct(row["peak_dr"]), _pct(row["early_dr"]),
                   f"{row['seasoning_factor']:.2f}x"]
                  for _, row in vd.seasoning.iterrows()]
        # drift table
        d_rows = []
        for _, row in vd.drift.iterrows():
            tone = {"악화": "FAIL", "개선": "PASS", "안정": "NEUTRAL"}[row["verdict"]]
            d_rows.append([row["segment"], _pct(row["recent_avg_dr"]),
                           _pct(row["legacy_avg_dr"]),
                           f"{row['drift']*100:+.1f}%",
                           _badge(row["verdict"], tone)])
        deep_block = f"""
<div class="card"><h2>24-3. 자산군별 vintage curve</h2>
{seg_charts_html}
<p class="section-lead">각 자산군 내 6개 cohort를 overlay. 그래프 간격이 좁으면 vintage 안정,
바닥에 깔린 새 vintage가 위로 올라오면 신규 origination quality 악화.</p>
</div>

<div class="card"><h2>24-4. Seasoning factor (peak MOB / early MOB)</h2>
{_table(["자산군","peak MOB(개월)","peak DR","early DR","seasoning factor"],
        s_rows, right_cols=[1,2,3,4])}
<p class="section-lead">seasoning factor가 클수록 vintage가 늦게 발현 — 정상 retail 1.5~3x.
mortgage는 보통 1.0~1.5x (조기 hazard).</p>
</div>

<div class="card"><h2>24-5. Vintage drift (PSI-like)</h2>
{_table(["자산군","최근 cohort DR","과거 cohort DR","drift","판정"],
        d_rows, right_cols=[1,2,3]) if d_rows else "<p>cohort 부족.</p>"}
<p class="section-lead">최근 cohort의 동일 MOB 부도율을 legacy 평균과 비교. ±10% 이내 안정,
+10% 초과 → 신규 origination 악화 (RED).</p>
</div>
"""

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

{deep_block}
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


# ============================================================================
# 35 SICR detail (v0.9.0 IFRS9 deep-dive)
# ============================================================================

# IFRS 9 trigger labels (short → 한글 long form)
_SICR_TRIGGER_LABEL = {
    "dpd30":       "30일 연체 (5.5.11 rebuttable)",
    "watchlist":   "내부 watchlist",
    "pd_ratio":    "PD 배수(2x) 초과 (5.5.7)",
    "ext_rating":  "외부등급 2 notch 하락",
    "forbearance": "채무재조정(forbearance)",
    "abs_pd":      f"절대 PD 임계 (5% 이상)",
}


def page_sicr_detail(r: PipelineResult) -> str:
    """35_sicr_detail.html — multi-trigger Stage 2 attribution + low-credit-risk
    exemption (IFRS 9 5.5.7 / 5.5.10 / 5.5.11)."""
    deep = r.ifrs9_deep
    if deep is None:
        body = "<h1 class='title'>35. SICR 트리거 분해</h1><p>데이터 없음.</p>"
        return _page("SICR 분해", body, "35_sicr_detail.html")
    sicr = deep.sicr
    sicr_ex = deep.sicr_with_exemption

    s = sicr.summary.copy()
    s["label"] = s["trigger"].map(_SICR_TRIGGER_LABEL)
    trig_chart = viz.horizontal_bar(
        s["label"].tolist(), s["n_stage2"].tolist(),
        value_fmt=lambda v: f"{int(v):,}",
        title="SICR 트리거별 Stage 2 진입 건수",
        color=viz.AMBER,
    )
    trig_ead_chart = viz.horizontal_bar(
        s["label"].tolist(), s["ead_stage2"].tolist(),
        value_fmt=_won,
        title="SICR 트리거별 Stage 2 EAD",
        color=viz.PALETTE[1],
    )
    rows = [[lbl, f"{int(row.n_fired):,}", f"{int(row.n_stage2):,}",
             _won(row.ead_stage2), _pct(row.pct_of_stage2)]
            for lbl, row in zip(s["label"], s.itertuples())]
    matrix = deep.stage_asset
    asset_chart = viz.stacked_bar(
        list(matrix["asset_class"].unique()),
        {f"Stage {st}": matrix[matrix["stage"] == st]
         .set_index("asset_class").reindex(matrix["asset_class"].unique())
         ["ead"].tolist()
         for st in (1, 2, 3)},
        value_fmt=_won,
        title="자산군 × Stage EAD",
    )
    cov_rows = [[row.asset_class, f"Stage {int(row.stage)}", f"{int(row.n):,}",
                 _won(row.ead), _won(row.ecl), _pct(row.coverage_ratio)]
                for row in matrix.itertuples()]

    # exemption impact
    exempt_rows = [
        ["적용 전 Stage 2 건수", f"{sicr.n_stage2_pre_exemption:,}"],
        ["적용 후 Stage 2 건수 (5.5.10 carve-out)",
         f"{sicr_ex.n_stage2_post_exemption:,}"],
        ["carve-out (Stage 2→1) 건수",
         f"{int(sicr_ex.low_credit_risk_carve['carved_out'].sum()):,}"],
    ]

    body = f"""
<h1 class="title">35. SICR 트리거 분해 + Stage 분류 결과</h1>
<p class="section-lead">신용위험 유의적 증가(SICR) 다중 트리거 분해.
IFRS 9 5.5.7 / 5.5.11 / 5.5.10 (low credit risk exemption).</p>

<div class="kpi-grid">
{_kpi("Stage 2 익스포저 수", f"{sicr.n_stage2_pre_exemption:,}", tone="warn")}
{_kpi("최다 트리거",
       _esc(_SICR_TRIGGER_LABEL.get(
            s.sort_values('n_stage2', ascending=False).iloc[0]['trigger'],
            s.sort_values('n_stage2', ascending=False).iloc[0]['trigger'])))}
{_kpi("절대 PD 임계 (5%) 충족",
       f"{int(s.loc[s['trigger']=='abs_pd','n_fired'].iloc[0]):,}",
       sub="투자등급 면제 적용 가능")}
</div>

<div class="row2">
<div class="card"><h2>35-1. 트리거별 Stage 2 건수</h2>
<div class="chart">{trig_chart}</div></div>
<div class="card"><h2>35-2. 트리거별 Stage 2 EAD</h2>
<div class="chart">{trig_ead_chart}</div></div>
</div>

<div class="card"><h2>35-3. SICR 트리거 상세</h2>
{_table(["트리거","발동 건수","Stage 2 진입","Stage 2 EAD","Stage 2 내 비중"],
        rows, right_cols=[1,2,3,4])}
<p style="font-size:12px;color:#6b7280">
한 익스포저에 복수 트리거가 동시에 발동될 수 있으므로 합계 ≠ Stage 2 총수.
</p>
</div>

<div class="card"><h2>35-4. 저신용위험 면제(low credit risk exemption, 5.5.10)</h2>
{_table(["항목","값"], exempt_rows, right_cols=[1])}
<p style="font-size:12px;color:#6b7280">
투자등급(BBB- 이상)에 대해 SICR 면제 옵션 적용 시 Stage 2 분류가 축소.
IFRS 9 5.5.10은 저신용위험을 가정할 권리이며, 의무가 아님.
</p>
</div>

<div class="card"><h2>35-5. 자산군 × Stage 분포</h2>
<div class="chart">{asset_chart}</div>
{_table(["자산군","Stage","건수","EAD","ECL","커버리지"], cov_rows,
        right_cols=[2,3,4,5])}
</div>
"""
    return _page("SICR 분해", body, "35_sicr_detail.html")


# ============================================================================
# 36 PD term structure (v0.9.0 IFRS9 deep-dive)
# ============================================================================

def page_pd_term_structure(r: PipelineResult) -> str:
    """36_pd_term_structure.html — marginal/cumulative PD curves, survival
    probability, EIR sensitivity, amortising vs bullet (잔존기간 ECL inputs)."""
    deep = r.ifrs9_deep
    if deep is None:
        body = "<h1 class='title'>36. PD 잔존기간 구조</h1><p>데이터 없음.</p>"
        return _page("PD 잔존기간", body, "36_pd_term_structure.html")

    pdt = deep.pd_term
    years = sorted(pdt["year"].unique().tolist())
    marg_series = {cls: pdt[pdt["asset_class"] == cls]
                   .sort_values("year")["marginal_pd"].tolist()
                   for cls in pdt["asset_class"].unique()}
    cum_series = {cls: pdt[pdt["asset_class"] == cls]
                  .sort_values("year")["cumulative_pd"].tolist()
                  for cls in pdt["asset_class"].unique()}
    surv_series = {cls: pdt[pdt["asset_class"] == cls]
                   .sort_values("year")["survival"].tolist()
                   for cls in pdt["asset_class"].unique()}
    marg_chart = viz.line_chart([str(y) for y in years], marg_series,
                                 value_fmt=lambda v: f"{v*100:.2f}%",
                                 title="자산군별 한계 부도확률 (marginal PD)")
    cum_chart = viz.line_chart([str(y) for y in years], cum_series,
                                value_fmt=_pct,
                                title="자산군별 누적 부도확률")
    surv_chart = viz.line_chart([str(y) for y in years], surv_series,
                                 value_fmt=_pct,
                                 title="자산군별 잔존(생존) 확률")

    # EIR sensitivity
    es = deep.eir_sensitivity
    eir_pivot = es.pivot(index="eir", columns="asset_class", values="ecl")
    eir_rows = [[f"{idx*100:.1f}%"] + [_won(eir_pivot.loc[idx, c])
                                        for c in eir_pivot.columns]
                for idx in eir_pivot.index]
    eir_series = {c: eir_pivot[c].tolist() for c in eir_pivot.columns}
    eir_chart = viz.line_chart(
        [f"{e*100:.1f}%" for e in eir_pivot.index],
        eir_series,
        value_fmt=lambda v: f"{v/1e9:,.0f}십억",
        title="EIR 감소율 변화에 따른 자산군별 ECL",
    )

    # amortising vs bullet
    avb = deep.amortising_vs_bullet
    avb_chart = viz.bar_chart(
        avb["type"].tolist(), avb["ecl"].tolist(),
        value_fmt=_won,
        title="EAD 잔액구조 (분할상환 vs 만기일시) — 동일 PD/LGD/만기",
    )

    body = f"""
<h1 class="title">36. PD 잔존기간 구조 + EIR 시뮬레이션</h1>
<p class="section-lead">상수-위험률(constant-hazard) 가정 하의 자산군별 잔존기간 PD 곡선과
유효이자율(EIR) 가정 변화에 따른 ECL 민감도.</p>

<div class="kpi-grid">
{_kpi("자산군 수", f"{pdt['asset_class'].nunique()}")}
{_kpi("최대 만기 모사", f"{int(pdt['year'].max())}년")}
{_kpi("Mortgage 기본 EIR",
       _pct(0.035), sub="장기 담보부 가정")}
{_kpi("Retail 기본 EIR",
       _pct(0.08), sub="단기 무담보 가정")}
</div>

<div class="row2">
<div class="card"><h2>36-1. 자산군별 한계 PD</h2>
<div class="chart">{marg_chart}</div></div>
<div class="card"><h2>36-2. 누적 부도확률</h2>
<div class="chart">{cum_chart}</div></div>
</div>

<div class="card"><h2>36-3. 잔존(생존) 확률 곡선</h2>
<div class="chart">{surv_chart}</div>
<p style="font-size:12px;color:#6b7280">
S(t) = (1 − PD<sub>12m</sub>)<sup>t</sup>;
잔존기간 ECL = Σ marginal_PD<sub>t</sub> × LGD × EAD<sub>t</sub> × DF<sub>t</sub>.
</p>
</div>

<div class="card"><h2>36-4. 유효이자율(EIR) 민감도 — 자산군별</h2>
<div class="chart">{eir_chart}</div>
{_table(["EIR"] + list(eir_pivot.columns), eir_rows,
        right_cols=list(range(1, 1+len(eir_pivot.columns))))}
<p style="font-size:12px;color:#6b7280">
EIR 감소 → 미래손실 할인계수 상승 → ECL 증가. IFRS 9 5.5.17.
</p>
</div>

<div class="card"><h2>36-5. EAD 잔액구조 비교 (분할상환 vs 만기일시)</h2>
<div class="chart">{avb_chart}</div>
{_table(["유형","ECL","커버리지"],
        [[row["type"], _won(row["ecl"]), _pct(row["coverage_ratio"])]
         for _, row in avb.iterrows()],
        right_cols=[1,2])}
<p style="font-size:12px;color:#6b7280">
동일한 PD/LGD/만기 하에서 만기일시(bullet)는 잔액이 만기까지 유지되어
분할상환(amortising) 대비 ECL이 더 큼.
</p>
</div>
"""
    return _page("PD 잔존기간", body, "36_pd_term_structure.html")


# ============================================================================
# 37 Macro scenario sensitivity (v0.9.0 IFRS9 deep-dive)
# ============================================================================

def page_macro_scenario(r: PipelineResult) -> str:
    """37_macro_scenario.html — scenario weighting sensitivity + macro variable
    narrative + rho sensitivity (IFRS 9 B5.5.42)."""
    deep = r.ifrs9_deep
    if deep is None:
        body = "<h1 class='title'>37. 거시 시나리오 민감도</h1><p>데이터 없음.</p>"
        return _page("거시 시나리오", body, "37_macro_scenario.html")

    ws = deep.scenario_weights
    rs = deep.rho_sensitivity
    nar = deep.macro_narrative

    w_chart = viz.bar_chart(
        ws["weighting"].tolist(),
        ws["ecl_total"].tolist(),
        value_fmt=_won,
        title="시나리오 확률가중 가정별 통합 ECL",
        colors=[viz.GREEN] + [viz.PALETTE[0]] * (len(ws) - 1),
    )
    w_rows = [[row.weighting,
               f"{row.weights[0]*100:.0f}/{row.weights[1]*100:.0f}/{row.weights[2]*100:.0f}",
               _won(row.ecl_total),
               f"{row.lift_vs_base/1e9:+,.1f}십억",
               f"{row.lift_pct*100:+.2f}%"]
              for row in ws.itertuples()]

    rho_chart = viz.line_chart(
        [f"{rho:.2f}" for rho in rs["rho"]],
        {"baseline": rs["ecl_baseline"].tolist(),
         "severe":   rs["ecl_severe"].tolist(),
         "확률가중": rs["ecl_weighted"].tolist()},
        value_fmt=lambda v: f"{v/1e9:,.0f}십억",
        title="rho(자산상관) 민감도 — 시나리오별 ECL",
    )
    rho_rows = [[f"{row.rho:.2f}", _won(row.ecl_baseline),
                 _won(row.ecl_severe), _won(row.ecl_weighted)]
                for row in rs.itertuples()]

    nar_rows = [[row["scenario"], f"{row['gdp_dev_yr1_pct']:+.1f}%",
                 f"{row['unemp_dev_pp']:+.1f}pp",
                 f"{row['hpi_dev_pct']:+.1f}%",
                 f"{row['policy_rate_bp']:+d}bp",
                 f"{row['corp_spread_bp']:+d}bp",
                 row["narrative"]]
                for _, row in nar.iterrows()]

    body = f"""
<h1 class="title">37. 거시 시나리오 가중치 + 거시 변수 narrative + rho 민감도</h1>
<p class="section-lead">IFRS 9 B5.5.42 — 확률가중 다중 시나리오 가정의 민감도.
시나리오별 거시 변수(GDP, 실업률, HPI, 정책금리, 회사채 spread)와
자산상관(rho) 가정 변화에 따른 ECL 영향.</p>

<div class="kpi-grid">
{_kpi("기본 가중치 ECL", _won(ws.iloc[0]['ecl_total']))}
{_kpi("최대 보수 lift",
       f"{ws['lift_vs_base'].max()/1e9:+,.1f}십억",
       sub=f"{ws.loc[ws['lift_vs_base'].idxmax(), 'weighting']}",
       tone="warn")}
{_kpi("rho 0.10 → 0.20 ECL 증가",
       _won(rs.loc[rs['rho']==0.20,'ecl_weighted'].iloc[0]
            - rs.loc[rs['rho']==0.10,'ecl_weighted'].iloc[0]))}
</div>

<div class="card"><h2>37-1. 시나리오 확률가중 민감도</h2>
<div class="chart">{w_chart}</div>
{_table(["가중치 가정","확률 (Base/Down/Severe)","ECL","Base 대비 차이","비율"],
        w_rows, right_cols=[1,2,3,4])}
<p style="font-size:12px;color:#6b7280">
IFRS 9 B5.5.42는 단일 시나리오가 아닌 확률가중을 요구. 가중치는 reasonable &amp;
supportable한 가정이며, 본 분석은 5종 가중치 가정의 영향을 보여줌.
</p>
</div>

<div class="card"><h2>37-2. 거시 변수 narrative (시나리오별)</h2>
{_table(["시나리오","GDP 편차(1년차)","실업률 Δ","주택가격 Δ","정책금리 Δ",
         "회사채 spread Δ","서술"],
        nar_rows, right_cols=[1,2,3,4,5])}
<p style="font-size:12px;color:#6b7280">
거시 변수는 PIT PD 산출 시 z(체계적 요인)로 변환되어 PD를 conditional shift.
현재 모형은 GDP·LGD shift만 활용; 향후 실업률·HPI·spread 다요인 z 확장 가능.
</p>
</div>

<div class="card"><h2>37-3. 자산상관(rho) 민감도</h2>
<div class="chart">{rho_chart}</div>
{_table(["rho","baseline ECL","severe ECL","확률가중 ECL"], rho_rows,
        right_cols=[1,2,3])}
<p style="font-size:12px;color:#6b7280">
rho는 Vasicek 1-factor PIT transform 의 자산상관 계수. rho 상승 →
체계적 요인 민감도 상승 → severe 시나리오 ECL 가속.
</p>
</div>
"""
    return _page("거시 시나리오", body, "37_macro_scenario.html")


# ============================================================================
# 38 Provisioning attribution (v0.9.0 IFRS9 deep-dive)
# ============================================================================

def page_provisioning_attribution(r: PipelineResult) -> str:
    """38_provisioning_attribution.html — Marshall-Edgeworth ECL change
    decomposition (PD / LGD / EAD / migration) + Stage 1/2 backtest +
    NPL cure analysis."""
    deep = r.ifrs9_deep
    if deep is None:
        body = "<h1 class='title'>38. 충당금 변화 귀속</h1><p>데이터 없음.</p>"
        return _page("충당금 귀속", body, "38_provisioning_attribution.html")

    attr = deep.attribution
    bt = deep.backtest
    cure = deep.npl_cure
    cov = deep.coverage_by_asset

    # ECL change waterfall (start → effects → end)
    middle = attr[attr["effect"].isin(["pd", "lgd", "ead", "migration"])]
    start = attr[attr["effect"] == "start"]["value"].iloc[0]
    end = attr[attr["effect"] == "end"]["value"].iloc[0]
    wf_labels = ["전기 ECL"] + middle["effect"].str.upper().tolist() + ["당기 ECL"]
    wf_values = ([float(start)]
                  + middle["value"].astype(float).tolist()
                  + [float(end)])
    wf_chart = viz.waterfall(wf_labels, wf_values, value_fmt=_won,
                              title="전기 → 당기 ECL 변화 귀속 (Marshall-Edgeworth)")
    attr_rows = [[row.effect.upper(),
                  _won(row.value) if row.effect not in ("pd", "lgd", "ead", "migration")
                  else f"{row.value/1e9:+,.1f}십억"]
                 for row in attr.itertuples()]

    # Stage 1/2 backtest table
    bt_rows = [[f"Stage {int(row.opening_stage)}", f"{int(row.n_opening):,}",
                f"{int(row.n_default_realised):,}",
                f"{int(row.n_cure):,}", f"{int(row.n_remain):,}",
                _pct(row.realised_default_rate),
                _pct(row.implied_default_rate),
                f"{row.gap_pp:+.2f}%p"]
               for row in bt.itertuples()]
    bt_chart = viz.bar_chart(
        [f"Stage {int(s)}" for s in bt["opening_stage"]],
        bt["realised_default_rate"].tolist(),
        value_fmt=_pct,
        title="전기 Stage별 실현 부도율 (backtest)",
        colors=[viz.PALETTE[0]] + [viz.AMBER],
    )

    # NPL cure / coverage by asset
    cure_rows = [[row.asset_class, f"{int(row.n_npl):,}",
                  _won(row.ead), _won(row.ecl),
                  _pct(row.coverage_ratio), _pct(row.cure_rate),
                  _won(row.residual_recovery)]
                 for row in cure.by_asset.itertuples()]
    cov_rows = [[row.asset_class, f"{int(row.n):,}", _won(row.ead),
                 _won(row.ecl), _pct(row.coverage_ratio)]
                for row in cov.itertuples()]
    cov_chart = viz.bar_chart(
        cov["asset_class"].tolist(), cov["coverage_ratio"].tolist(),
        value_fmt=_pct, title="자산군별 ECL 커버리지율 (ECL / EAD)",
    )

    body = f"""
<h1 class="title">38. 충당금 변화 귀속 + Stage backtest + NPL 분석</h1>
<p class="section-lead">전기 대비 ECL 변화를 PD/LGD/EAD/Stage 마이그레이션 효과로
분해(Marshall-Edgeworth). 전기 Stage 1/2의 실현 부도율로 ECL 모형 적정성 backtest.</p>

<div class="kpi-grid">
{_kpi("ECL 변화 총액",
       f"{(end - start)/1e9:+,.1f}십억",
       sub=f"{(end/start-1)*100:+.2f}%" if start else "—",
       tone="warn" if end > start else "good")}
{_kpi("최대 기여 요인",
       middle.iloc[middle['value'].abs().argmax()]['effect'].upper(),
       sub=_won(middle['value'].abs().max()))}
{_kpi("Stage 3 NPL 비중 (EAD)",
       _pct(cure.npl_ratio_pct_ead), tone="warn")}
{_kpi("NPL 잔여 회수가치",
       _won(cure.residual_recovery_value))}
</div>

<div class="card"><h2>38-1. ECL 변화 귀속 (waterfall)</h2>
<div class="chart">{wf_chart}</div>
{_table(["효과","값"], attr_rows, right_cols=[1])}
<p style="font-size:12px;color:#6b7280">
PD 효과: 전기 LGD/EAD 고정, PD만 당기로 교체 시 ECL 변화.
순서: PD → LGD → EAD → Migration (Stage 전이). Marshall-Edgeworth 분해.
</p>
</div>

<div class="card"><h2>38-2. 전기 Stage 1/2 backtest</h2>
<div class="chart">{bt_chart}</div>
{_table(["전기 Stage","개체 수","실현 부도","cure","유지",
         "실현 부도율","모형 내재 PD","gap"],
        bt_rows, right_cols=[1,2,3,4,5,6,7])}
<p style="font-size:12px;color:#6b7280">
Stage 1 실현 부도율이 내재 PD와 큰 차이를 보이면 12m ECL 적정성 재검토 필요.
Stage 2 cure 비율이 높으면 SICR 트리거 보정 검토.
</p>
</div>

<div class="row2">
<div class="card"><h2>38-3. 자산군별 ECL 커버리지</h2>
<div class="chart">{cov_chart}</div>
{_table(["자산군","건수","EAD","ECL","커버리지율"], cov_rows,
        right_cols=[1,2,3,4])}
</div>
<div class="card"><h2>38-4. Stage 3 NPL 회수 분석</h2>
{_table(["자산군","NPL 건수","NPL EAD","ECL","커버리지",
         "cure rate","잔여 회수가치"],
        cure_rows, right_cols=[1,2,3,4,5,6])}
<p style="font-size:12px;color:#6b7280">
잔여 회수가치 = EAD × (cure rate + (1 − cure) × collateral_recovery).
충당금 적립률(coverage)과 잔여 회수가치의 보수성 비교.
</p>
</div>
</div>
"""
    return _page("충당금 귀속", body, "38_provisioning_attribution.html")


# ============================================================================
# v0.10.0 — 자산건전성 deep-dive (39 / 40 / 41)
# ============================================================================


def page_dpd_roll(r: PipelineResult) -> str:
    """39. DPD bucket roll-rate 매트릭스 + Markov 예측."""
    deep = r.monitoring_deep.get("delinquency") if r.monitoring_deep else None
    if deep is None or deep.roll_matrix.empty:
        return _placeholder_page(
            "39. DPD roll-rate", "roll-rate 데이터가 없습니다.",
            "39_dpd_roll.html",
        )
    rm = deep.roll_matrix
    labels = list(rm.index)
    # heatmap of transition probabilities
    heat = viz_advanced.heatmap(
        labels, labels, rm.values.tolist(),
        title="DPD bucket 월간 roll-rate (행=t, 열=t+1)",
        value_fmt=lambda v: f"{v*100:.0f}" if v >= 0.01 else "",
        vmin=0.0, vmax=1.0, cell_label=True,
    )
    # rows table
    rows = [[lab] + [_pct(float(rm.loc[lab, c]), 1) for c in labels]
            for lab in labels]

    # markov projection chart — stacked bar over months
    proj = deep.projection
    months = sorted(proj["month"].unique())
    series = {b: [float(proj[(proj["month"] == m) & (proj["bucket"] == b)]["share"].sum())
                  for m in months] for b in labels}
    stacked = viz.stacked_bar(
        [f"+{m}M" for m in months], series, value_fmt=lambda v: f"{v*100:.0f}%",
        title="Markov 예측 — 향후 버킷별 EAD 점유율",
    )

    # projection table (NPL share trajectory)
    npl_series = [float(proj[(proj["month"] == m) & (proj["bucket"] == "90+")]
                          ["share"].sum()) for m in months]
    npl_rows = [[f"+{m}M", _pct(s, 2)] for m, s in zip(months, npl_series)]

    # bucket time-series tabular forecast
    bm = deep.bucket_matrix
    bm_summary = bm.groupby("bucket", observed=False).agg(
        n_loans=("n_loans", "sum"), ead=("ead", "sum"),
    ).reset_index()
    bm_summary["share"] = bm_summary["ead"] / max(bm_summary["ead"].sum(), 1.0)
    cur_rows = [[row["bucket"], f"{int(row['n_loans']):,}", _won(row["ead"]),
                 _pct(row["share"])] for _, row in bm_summary.iterrows()]
    roll_header = ["from → to"] + labels
    roll_table = _table(roll_header, rows, right_cols=list(range(1, len(labels)+1)))

    body = f"""
<h1 class="title">39. DPD bucket roll-rate (Markov chain)</h1>
<p class="section-lead">월간 DPD 버킷 전이확률 (1-29 → 30-59 → 60-89 → 90+).
roll-rate × 현재 버킷 분포 = 향후 3개월 NPL 흐름 예측.
기준: Basel III CRE36.69, 감독세칙 자산건전성 분류, BCBS 2017 problem assets 보고서.</p>

<div class="row2">
<div class="card"><h2>39-1. 현재 DPD 버킷 분포</h2>
{_table(["버킷","건수","EAD","점유율"], cur_rows, right_cols=[1,2,3])}
</div>
<div class="card"><h2>39-2. NPL share 예측 (Markov)</h2>
{_table(["기간","NPL(90+) 점유율"], npl_rows, right_cols=[1])}
</div>
</div>

<div class="card"><h2>39-3. Roll-rate 행렬 (월간)</h2>
<div class="chart">{heat}</div>
{roll_table}
<p class="section-lead">대각 = 동일 버킷 유지, 우상 = 악화 (roll-forward),
좌하 = 개선 (cure/roll-back). 90+ 는 흡수상태 (write-off 전).
30-59 → 60-89 의 월간 roll rate가 분기 안정성 평가의 핵심.</p>
</div>

<div class="card"><h2>39-4. Markov 예측 — 향후 3개월 버킷 점유율</h2>
<div class="chart">{stacked}</div>
<p class="section-lead">3개월 후 NPL 점유율 증분이 현재의 1.5x 초과 시 vintage 악화 경보.
실 데이터로 교체 시 quarterly NPL flow projection으로 사용 가능.</p>
</div>
"""
    return _page("DPD roll-rate", body, "39_dpd_roll.html")


def page_recovery_lgd(r: PipelineResult) -> str:
    """40. 회수 곡선 (할인/미할인) + LGD 분포 + collateral 효과."""
    deep = r.monitoring_deep.get("recovery") if r.monitoring_deep else None
    if deep is None or deep.curve_dual.empty:
        return _placeholder_page(
            "40. 회수·LGD", "회수 데이터가 없습니다.", "40_recovery_lgd.html",
        )

    # 회수 곡선 (할인/미할인 overlay)
    curve = deep.curve_dual
    months = curve["month"].tolist()
    series = {
        "undiscounted": curve["cum_recovery_undisc"].tolist(),
        "discounted (EIR 6%)": curve["cum_recovery_disc"].tolist(),
    }
    curve_chart = viz.line_chart(
        [str(m) for m in months], series, value_fmt=_pct,
        title="누적 회수율 — workout cashflow 36개월",
    )

    final_undisc = float(curve["cum_recovery_undisc"].iloc[-1])
    final_disc = float(curve["cum_recovery_disc"].iloc[-1])
    spread = final_undisc - final_disc

    # LGD 분포 — quantile table + histogram per segment
    lq = deep.lgd_quantiles
    lh = deep.lgd_histogram
    q_rows = []
    for _, row in lq.iterrows():
        q_rows.append([row["segment"], f"{int(row['n']):,}",
                       _pct(row["p10"]), _pct(row["p25"]), _pct(row["median"]),
                       _pct(row["p75"]), _pct(row["p90"]), _pct(row["mean"])])
    # histogram chart per segment (one stacked bar per segment, optional)
    hist_blocks = []
    for seg, sub in lh.groupby("segment") if not lh.empty else []:
        labels_h = [f"{row['bin_lo']:.1f}-{row['bin_hi']:.1f}"
                    for _, row in sub.iterrows()]
        ch = viz.bar_chart(
            labels_h, sub["n"].tolist(),
            title=f"{seg} — LGD 히스토그램",
            value_fmt=lambda v: f"{int(v):,}",
            colors=[viz.PALETTE[i % len(viz.PALETTE)] for i in range(len(sub))],
        )
        hist_blocks.append(
            f'<div class="card"><h3>{_esc(seg)}</h3>'
            f'<div class="chart">{ch}</div></div>'
        )
    hist_html = "<div class='row2'>" + "".join(hist_blocks) + "</div>" \
                if hist_blocks else "<p>분포 데이터 없음</p>"

    # collateral 효과
    coll = deep.collateral
    coll_chart = viz.horizontal_bar(
        coll["collateral_type"].tolist(),
        coll["avg_recovery"].tolist(),
        value_fmt=_pct, title="담보 유형별 평균 회수율",
        color=viz.GREEN,
    )
    coll_rows = [[row["collateral_type"], f"{int(row['n']):,}",
                  _won(row["ead"]), _pct(row["avg_recovery"]),
                  _pct(row["avg_lgd"])]
                 for _, row in coll.iterrows()]

    body = f"""
<h1 class="title">40. 회수율 · LGD realised deep-dive</h1>
<p class="section-lead">워크아웃 36개월 cashflow 기반 회수 곡선 (할인/미할인) +
자산군별 실현 LGD 분위수 + 담보 유형별 회수율 비교.
기준: Basel III CRE32.46~ (downturn LGD), CRE36.83 (회수 인식),
IFRS 9 5.5.5 ECL 정의.</p>

<div class="kpi-grid">
{_kpi("36M 누적 회수율 (미할인)", _pct(final_undisc))}
{_kpi("36M 누적 회수율 (EIR 6% 할인)", _pct(final_disc))}
{_kpi("할인 효과 (gap)", f"-{_pct(spread)}")}
</div>

<div class="card"><h2>40-1. 회수 곡선 (Discounted vs Undiscounted)</h2>
<div class="chart">{curve_chart}</div>
<p class="section-lead">undiscounted 는 LGD 산출 표면값, discounted 는 EIR로 현재가치화한 값.
IFRS 9 ECL는 할인 기준 LGD를 사용 (IFRS 9 B5.5.44). 두 곡선 간 격차는 회수 long tail 의 시간가치.</p>
</div>

<div class="card"><h2>40-2. 자산군별 실현 LGD 분위수</h2>
{_table(["자산군","건수","P10","P25","중앙값","P75","P90","평균"],
        q_rows, right_cols=list(range(1, 8))) if q_rows else "<p>데이터 없음.</p>"}
<p class="section-lead">downturn LGD는 일반적으로 P75 이상에 위치 — 현재 평균 대비 P75 격차로
경기침체 LGD floor 보수성 평가.</p>
</div>

<div class="card"><h2>40-3. LGD 히스토그램 (자산군)</h2>
{hist_html}
</div>

<div class="card"><h2>40-4. 담보 유형별 회수율</h2>
<div class="chart">{coll_chart}</div>
{_table(["담보 유형","건수","EAD","평균 회수율","평균 LGD"], coll_rows,
        right_cols=[1,2,3,4])}
<p class="section-lead">담보 유형 mapping: residential_mortgage→주거용, corporate→상업/회사채,
retail_other→무담보, sovereign/bank→국채/보증. 실제 collateral master data로 교체 시 직접 산출.</p>
</div>
"""
    return _page("회수·LGD", body, "40_recovery_lgd.html")


def page_cure_analysis(r: PipelineResult) -> str:
    """41. Cure rate + time-to-cure."""
    cure = r.monitoring_deep.get("cure") if r.monitoring_deep else None
    if cure is None or cure.by_segment.empty:
        return _placeholder_page(
            "41. Cure 분석", "cure 경로 데이터가 없습니다.",
            "41_cure_analysis.html",
        )

    # cure rate horizontal bar by segment (count & EAD)
    seg = cure.by_segment[cure.by_segment["segment"] != "전체"]
    rate_chart_count = viz.horizontal_bar(
        seg["segment"].tolist(),
        seg["cure_rate_count"].tolist(),
        value_fmt=_pct, title="자산군별 cure rate (건수)",
        color=viz.GREEN,
    )
    rate_chart_ead = viz.horizontal_bar(
        seg["segment"].tolist(),
        seg["cure_rate_ead"].tolist(),
        value_fmt=_pct, title="자산군별 cure rate (EAD 가중)",
        color=viz.PALETTE[2],
    )
    # time-to-cure distribution chart
    ttc = cure.ttc_distribution
    if not ttc.empty:
        ttc_chart = viz.bar_chart(
            [f"{row['bin_lo']:.1f}-{row['bin_hi']:.1f}M" for _, row in ttc.iterrows()],
            ttc["n"].tolist(),
            value_fmt=lambda v: f"{int(v):,}",
            title=f"time-to-cure 분포 (window {cure.cure_window}M)",
            colors=[viz.PALETTE[i % len(viz.PALETTE)] for i in range(len(ttc))],
        )
    else:
        ttc_chart = "<p>cure 사례 없음.</p>"

    rows = []
    for _, row in cure.by_segment.iterrows():
        rows.append([row["segment"], f"{int(row['n_defaults']):,}",
                     f"{int(row['n_cured']):,}",
                     _pct(row["cure_rate_count"]),
                     _pct(row["cure_rate_ead"]),
                     f"{row['avg_time_to_cure']:.1f}M"])
    total = cure.by_segment[cure.by_segment["segment"] == "전체"]
    headline_rate = float(total["cure_rate_count"].iloc[0]) if not total.empty else 0.0
    headline_ttc = float(total["avg_time_to_cure"].iloc[0]) if not total.empty else 0.0

    body = f"""
<h1 class="title">41. Cure rate 분석</h1>
<p class="section-lead">부도(90+ DPD or UTP) 인식 후 {cure.cure_window}개월 내 DPD 30 미만 복귀 비율.
기준: Basel III CRE36.81 (cure window), 감독세칙 자산건전성 분류 시행세칙,
BCBS Guidelines on Prudential Treatment of Problem Assets (2017).</p>

<div class="kpi-grid">
{_kpi("전체 cure rate (건수)", _pct(headline_rate))}
{_kpi("평균 time-to-cure", f"{headline_ttc:.1f}M")}
{_kpi("관측 부도 건수", f"{int(total['n_defaults'].iloc[0]):,}" if not total.empty else "0")}
{_kpi("cure 부도 건수", f"{int(total['n_cured'].iloc[0]):,}" if not total.empty else "0")}
</div>

<div class="row2">
<div class="card"><h2>41-1. Cure rate (건수)</h2>
<div class="chart">{rate_chart_count}</div>
</div>
<div class="card"><h2>41-2. Cure rate (EAD 가중)</h2>
<div class="chart">{rate_chart_ead}</div>
</div>
</div>

<div class="card"><h2>41-3. 자산군별 cure 통계</h2>
{_table(["자산군","부도 건수","cure 건수","cure rate(건수)","cure rate(EAD)","평균 ttc"],
        rows, right_cols=[1,2,3,4,5])}
<p class="section-lead">prior: mortgage 0.42 / corporate 0.28 / retail 0.18 — 담보·worker-out 협의 가능성 차이 반영.
무담보 retail이 가장 낮고 mortgage가 가장 높은 패턴이 표준.</p>
</div>

<div class="card"><h2>41-4. time-to-cure 분포</h2>
<div class="chart">{ttc_chart}</div>
<p class="section-lead">cure window 내에서 cure 시점 분포 — 1~2개월 조기 cure 비중이 높을수록
"기술적 연체" 가능성. 본 라이브러리는 cure-policy 적용 후 default_12m 가정 — 자세한 정책은
CLAUDE.md "금지 사항" 참조.</p>
</div>
"""
    return _page("Cure 분석", body, "41_cure_analysis.html")


# ---------------------------------------------------------------- 45 EVA / SVA

def page_eva_sva(r: PipelineResult) -> str:
    """가치창출액(EVA) + 차주별 top/bottom 분해.

    EVA = (RAROC − hurdle) × EC. SVA = RAROC − hurdle (spread basis).
    가치 창출/파괴 obligor를 식별하고 대응 권고를 제시한다.
    """
    if getattr(r, "rapm_deep", None) is None:
        body = "<h1 class='title'>45. EVA/SVA</h1><p>RAPM deep-dive 미가용.</p>"
        return _page("EVA/SVA", body, "45_eva_sva.html")
    rd = r.rapm_deep
    hurdle = rd.summary["hurdle_rate"]
    # EVA by asset class chart
    eva_c = rd.eva_by_class
    eva_chart = viz.bar_chart(
        eva_c["asset_class"].tolist(), eva_c["eva"].tolist(),
        value_fmt=_won, title="자산군별 EVA (KRW)",
        colors=[viz.GREEN if v >= 0 else viz.RED for v in eva_c["eva"]],
    )
    # Top 20 obligor EVA
    top = rd.obligor_top
    top_chart = viz.horizontal_bar(
        [str(o)[:16] for o in top["obligor_id"].tolist()],
        top["eva"].tolist(),
        value_fmt=_won, title="가치창출 Top 20 차주 (EVA)", color=viz.GREEN,
    )
    bot = rd.obligor_bottom
    bot_chart = viz.horizontal_bar(
        [str(o)[:16] for o in bot["obligor_id"].tolist()],
        bot["eva"].tolist(),
        value_fmt=_won, title="가치파괴 Bottom 20 차주 (EVA)", color=viz.RED,
    )
    # Tables
    eva_rows = [[row["asset_class"], f"{int(row['n']):,}",
                  _won(row["ec"]), _won(row["eva"]),
                  _pct(row["raroc_ead_weighted"], 2)]
                 for _, row in eva_c.iterrows()]
    top_rows = [[str(row["obligor_id"]), f"{int(row['n_exposures']):,}",
                  _won(row["ec"]), _won(row["revenue"]),
                  _won(row["expected_loss"]), _pct(row["raroc"], 2),
                  _won(row["eva"]),
                  _badge(row["recommendation"],
                         "GREEN" if row["recommendation"] == "OK" else "WARN")]
                 for _, row in top.iterrows()]
    bot_rows = [[str(row["obligor_id"]), f"{int(row['n_exposures']):,}",
                  _won(row["ec"]), _won(row["revenue"]),
                  _won(row["expected_loss"]), _pct(row["raroc"], 2),
                  _won(row["eva"]),
                  _badge(row["recommendation"],
                         "FAIL" if "종결" in row["recommendation"]
                         else ("WARN" if row["recommendation"] != "OK"
                               else "GREEN"))]
                 for _, row in bot.iterrows()]
    bench = rd.benchmark
    body = f"""
<h1 class="title">45. EVA / SVA — 가치창출액 분해</h1>
<p class="section-lead">EVA = (RAROC − hurdle) × EC. 자기자본비용 차감 후 실제 가치 창출액(KRW).
근거: BCBS RAPM appendix, ICAAP 운영기준.</p>

<div class="kpi-grid">
{_kpi("EVA 총합", _won(rd.summary['eva_total']),
       tone="good" if rd.summary['eva_total'] >= 0 else "bad")}
{_kpi("가중 RAROC", _pct(rd.summary['raroc_weighted'], 2),
       sub=f"hurdle {_pct(hurdle)}",
       tone="good" if rd.summary['raroc_weighted'] >= hurdle else "bad")}
{_kpi("EC 총합", _won(rd.summary['ec_total']))}
{_kpi("가치창출 거래 비중", _pct(rd.summary['value_creating_pct'], 1))}
{_kpi("재가격 필요(거래)", f"{rd.summary['n_repricing']:,}", tone="warn")}
{_kpi("종결 검토(거래)", f"{rd.summary['n_terminate']:,}", tone="bad")}
{_kpi("피어 대비 RAROC", bench['position'],
       sub=f"gap {bench['gap_to_median']*100:+.2f}%p (median {_pct(bench['peer_median'])})")}
{_kpi("상위 사분위 GAP", f"{bench['gap_to_top_quartile']*100:+.2f}%p",
       sub=f"top quartile {_pct(bench['peer_top_quartile'])}")}
</div>

<div class="card"><h2>45-1. 자산군별 EVA</h2>
<div class="chart">{eva_chart}</div>
{_table(["자산군","건수","EC","EVA","RAROC(EC가중)"], eva_rows,
        right_cols=[1,2,3,4])}
</div>

<div class="row2">
<div class="card"><h2>45-2. 가치창출 Top 20 차주</h2>
<div class="chart">{top_chart}</div></div>
<div class="card"><h2>45-3. 가치파괴 Bottom 20 차주</h2>
<div class="chart">{bot_chart}</div></div>
</div>

<div class="card"><h2>45-4. Top 20 차주 상세 (EVA &gt; 0)</h2>
{_table(["차주","익스포저수","EC","수익","EL","RAROC","EVA","권고"],
        top_rows, right_cols=[1,2,3,4,5,6])}
</div>

<div class="card"><h2>45-5. Bottom 20 차주 상세 (EVA &lt; 0) — 즉시 조치 대상</h2>
{_table(["차주","익스포저수","EC","수익","EL","RAROC","EVA","권고"],
        bot_rows, right_cols=[1,2,3,4,5,6])}
<p class="section-lead">권고 매핑: <b>가격 재협상</b>(0≤RAROC&lt;hurdle) ·
<b>거래 축소</b>(-10%≤RAROC&lt;0) · <b>한도 조정/종결</b>(RAROC&lt;-10%).</p>
</div>
"""
    return _page("EVA/SVA", body, "45_eva_sva.html")


# ---------------------------------------------------------------- 46 breakeven pricing

def page_pricing_breakeven(r: PipelineResult) -> str:
    """위험조정 가격결정 — breakeven spread + 자산군별 cost stack 분해."""
    if getattr(r, "rapm_deep", None) is None:
        body = "<h1 class='title'>46. Pricing breakeven</h1><p>RAPM deep-dive 미가용.</p>"
        return _page("Pricing breakeven", body, "46_pricing_breakeven.html")
    rd = r.rapm_deep
    bp_class = rd.breakeven_by_class
    pricing = rd.pricing_premium
    hurdle = rd.summary["hurdle_rate"]
    # current vs breakeven side-by-side
    cur_chart = viz.bar_chart(
        bp_class["asset_class"].tolist(),
        bp_class["current_spread_bp_avg"].tolist(),
        value_fmt=lambda v: f"{v:.1f}bp",
        title="현재 평균 스프레드 (bp)",
        colors=[viz.GREEN if g >= 0 else viz.RED
                for g in bp_class["spread_gap_bp_avg"]],
    )
    be_chart = viz.bar_chart(
        bp_class["asset_class"].tolist(),
        bp_class["breakeven_spread_bp_avg"].tolist(),
        value_fmt=lambda v: f"{v:.1f}bp",
        title="Hurdle 충족 breakeven 스프레드 (bp)",
        colors=[viz.AMBER] * len(bp_class),
    )
    # Cost stack — stacked bar of (cost_of_risk, cost_of_capital, op_cost, margin)
    stack = viz.stacked_bar(
        pricing["asset_class"].tolist(),
        {
            "자본비용(EC·hurdle)": pricing["cost_of_capital_bp"].tolist(),
            "신용비용(EL)": pricing["cost_of_risk_bp"].tolist(),
            "운영비": pricing["operating_cost_bp"].tolist(),
            "목표 마진": pricing["target_margin_bp"].tolist(),
        },
        value_fmt=lambda v: f"{v:.0f}bp",
        title="자산군별 목표 스프레드 분해 (bp)",
    )
    bp_rows = [[row["asset_class"], f"{int(row['n']):,}",
                 f"{row['current_spread_bp_avg']:.1f}",
                 f"{row['breakeven_spread_bp_avg']:.1f}",
                 f"{row['spread_gap_bp_avg']:+.1f}",
                 f"{int(row['n_below_breakeven']):,}"]
                for _, row in bp_class.iterrows()]
    pp_rows = [[row["asset_class"],
                 f"{row['cost_of_risk_bp']:.1f}",
                 f"{row['cost_of_capital_bp']:.1f}",
                 f"{row['operating_cost_bp']:.1f}",
                 f"{row['target_margin_bp']:.0f}",
                 f"{row['target_spread_bp']:.1f}"]
                for _, row in pricing.iterrows()]
    # Top 20 below-breakeven exposures (largest gap)
    be = rd.breakeven.sort_values("spread_gap_bp").head(20)
    be_rows = [[row["exposure_id"],
                  f"{row['current_spread_bp']:.1f}",
                  f"{row['breakeven_spread_bp']:.1f}",
                  f"{row['spread_gap_bp']:+.1f}",
                  _pct(row["raroc"], 2),
                  _badge("재가격", "FAIL")]
                for _, row in be.iterrows()]
    body = f"""
<h1 class="title">46. 위험조정 가격결정 (Risk-Adjusted Pricing)</h1>
<p class="section-lead">Hurdle({_pct(hurdle)})을 충족하기 위한 최저 스프레드와 현재 스프레드 비교.
Breakeven spread (bp) = (hurdle·EC + 운영비 + EL − rf·EC) / EAD × 10,000.
근거: BCBS RAPM appendix, 감독세칙 자기자본관리.</p>

<div class="row2">
<div class="card"><h2>46-1. 현재 평균 스프레드</h2>
<div class="chart">{cur_chart}</div></div>
<div class="card"><h2>46-2. Breakeven 스프레드</h2>
<div class="chart">{be_chart}</div></div>
</div>

<div class="card"><h2>46-3. 자산군별 비교 (현재 vs breakeven)</h2>
{_table(["자산군","건수","현재(bp)","breakeven(bp)","gap(bp)","미달 거래"],
        bp_rows, right_cols=[1,2,3,4,5])}
</div>

<div class="card"><h2>46-4. 목표 스프레드 분해 — Cost Stack</h2>
<div class="chart">{stack}</div>
{_table(["자산군","신용비용","자본비용","운영비","목표마진","목표 스프레드(bp)"],
        pp_rows, right_cols=[1,2,3,4,5])}
<p class="section-lead">목표 스프레드 = 신용비용(EL/EAD) + 자본비용(EC·hurdle/EAD)
+ 운영비(OPEX/EAD) + 목표 마진(50bp 기본). 신규 거래 가격결정 시 참조 baseline.</p>
</div>

<div class="card"><h2>46-5. 재가격 대상 Top 20 — gap 최대</h2>
{_table(["거래","현재(bp)","breakeven(bp)","gap(bp)","RAROC","조치"],
        be_rows, right_cols=[1,2,3,4])}
<p class="section-lead">현재 스프레드가 breakeven보다 낮은 거래 — 즉시 재가격 협상 또는
RM 협의 대상. EL/EC 변동에 따라 분기마다 재평가 필요.</p>
</div>
"""
    return _page("Pricing breakeven", body, "46_pricing_breakeven.html")


# ---------------------------------------------------------------- 47 RAPM scenario

def page_rapm_scenario(r: PipelineResult) -> str:
    """금리/PD 시나리오에서의 RAROC 변동 — Pillar 2 stress."""
    if getattr(r, "rapm_deep", None) is None:
        body = "<h1 class='title'>47. RAPM scenario</h1><p>RAPM deep-dive 미가용.</p>"
        return _page("RAPM scenario", body, "47_rapm_scenario.html")
    rd = r.rapm_deep
    sc = rd.scenarios
    hurdle = rd.summary["hurdle_rate"]
    # RAROC line/bar across scenarios
    raroc_chart = viz.bar_chart(
        sc["scenario"].tolist(), sc["raroc_weighted"].tolist(),
        value_fmt=_pct, title="시나리오별 가중 RAROC",
        reference_value=hurdle, reference_label=f"hurdle {_pct(hurdle)}",
        colors=[viz.GREEN if v >= hurdle else viz.RED
                for v in sc["raroc_weighted"]],
    )
    eva_chart = viz.bar_chart(
        sc["scenario"].tolist(), sc["eva"].tolist(),
        value_fmt=_won, title="시나리오별 EVA (KRW)",
        colors=[viz.GREEN if v >= 0 else viz.RED for v in sc["eva"]],
    )
    pass_chart = viz.bar_chart(
        sc["scenario"].tolist(), sc["pass_hurdle_pct"].tolist(),
        value_fmt=_pct, title="시나리오별 hurdle 충족 거래 비중",
    )
    rows = [[row["scenario"],
              f"{row['rate_shock_bp']:+.0f}bp",
              f"{row['pd_uplift']*100:+.0f}%",
              _won(row["revenue"]),
              _won(row["expected_loss"]),
              _pct(row["raroc_weighted"], 2),
              _won(row["eva"]),
              _pct(row["pass_hurdle_pct"], 1),
              _badge("PASS" if row["raroc_weighted"] >= hurdle else "FAIL",
                     "PASS" if row["raroc_weighted"] >= hurdle else "FAIL")]
             for _, row in sc.iterrows()]
    base = sc[sc["scenario"] == "base"].iloc[0]
    worst = sc.sort_values("raroc_weighted").iloc[0]
    delta_raroc = worst["raroc_weighted"] - base["raroc_weighted"]
    delta_eva = worst["eva"] - base["eva"]
    body = f"""
<h1 class="title">47. RAPM 시나리오 분석 (금리·PD shock)</h1>
<p class="section-lead">정책금리 ±Δbp(NIM 변화) + PD 충격에서의 RAROC/EVA 변화 — Pillar 2 stress.
근거: Basel III Pillar 2 (ICAAP) 경제자본 산출, BCBS 365 IRRBB.</p>

<div class="kpi-grid">
{_kpi("기준 RAROC", _pct(base['raroc_weighted'], 2),
       sub=f"hurdle {_pct(hurdle)}",
       tone="good" if base['raroc_weighted'] >= hurdle else "bad")}
{_kpi("최악 시나리오", str(worst['scenario']),
       sub=f"RAROC {_pct(worst['raroc_weighted'], 2)}",
       tone="bad")}
{_kpi("RAROC Δ(최악)", f"{delta_raroc*100:+.2f}%p", tone="bad")}
{_kpi("EVA Δ(최악)", _won(delta_eva), tone="bad")}
{_kpi("시나리오 수", f"{len(sc):,}")}
</div>

<div class="row2">
<div class="card"><h2>47-1. 시나리오별 가중 RAROC</h2>
<div class="chart">{raroc_chart}</div></div>
<div class="card"><h2>47-2. 시나리오별 EVA</h2>
<div class="chart">{eva_chart}</div></div>
</div>

<div class="card"><h2>47-3. Hurdle 충족 비율 변화</h2>
<div class="chart">{pass_chart}</div>
</div>

<div class="card"><h2>47-4. 시나리오 상세</h2>
{_table(["시나리오","금리쇼크","PD shock","수익","EL","RAROC","EVA","hurdle 충족","판정"],
        rows, right_cols=[1,2,3,4,5,6,7])}
<p class="section-lead">금리: passthrough 50% 가정 — 정책금리 변동의 절반이 NIM에 반영.
PD shock: EL 선형 증가, EC는 시점 자본으로 보수적으로 고정 (Pillar 2 표준 관행).</p>
</div>
"""
    return _page("RAPM scenario", body, "47_rapm_scenario.html")


# ============================================================================
# 48. Multi-target reverse stress (v0.13.0)
# ============================================================================

def page_reverse_stress_multi(r: PipelineResult) -> str:
    deep = getattr(r, "stress_deep", {}) or {}
    if "multi_reverse" not in deep:
        body = "<h1 class='title'>48. Multi-target 역스트레스</h1><p>미가용.</p>"
        return _page("Multi-역스트레스", body, "48_reverse_stress_multi.html")
    mr = deep["multi_reverse"]
    tgt = mr.targets.copy()

    # binding constraint badge
    binding_kpi = _kpi(
        "Binding constraint", _esc(mr.binding_constraint),
        sub=f"s* = {mr.binding_severity:.2f}", tone="bad",
    )

    # severity bar chart
    chart = viz.horizontal_bar(
        tgt["metric"].tolist(),
        tgt["critical_severity"].tolist(),
        value_fmt=lambda v: f"{v:.2f}",
        title="metric별 임계 심도 s* (낮을수록 먼저 도달 = binding)",
        color=viz.RED,
    )

    rows = []
    for _, row in tgt.iterrows():
        status = ("이미 위반" if row["already_breached"]
                  else "최대 충격까지 견딤" if row["resilient"]
                  else f"s*={row['critical_severity']:.2f}")
        rows.append([
            _esc(row["metric"]),
            f"{row['target']*100:.2f}%" if row["target"] < 10
            else f"{row['target']*100:.0f}%",
            f"{row['base']*100:.2f}%" if row["base"] < 10
            else f"{row['base']*100:.0f}%",
            f"{row['ratio_at_break']*100:.2f}%" if row["ratio_at_break"] < 10
            else f"{row['ratio_at_break']*100:.0f}%",
            status,
            f"{row['implied_gdp_shock']*100:+.1f}%",
            f"+{row['implied_lgd_addon']*100:.1f}%p",
        ])

    pathway = mr.critical_pathway

    body = f"""
<h1 class="title">48. Multi-target 역스트레스 (CET1·Tier1·LCR·NSFR)</h1>
<p class="section-lead">BCBS Stress testing principles §7 — reverse stress test는
binding constraint(가장 먼저 도달하는 임계)와 critical pathway(도달 거시 경로)를
식별해야 한다.</p>

<div class="kpi-grid">
{binding_kpi}
{_kpi("Binding GDP 충격", f"{pathway['implied_gdp_shock']*100:+.1f}%")}
{_kpi("Binding LGD 가산", f"+{pathway['implied_lgd_addon']*100:.1f}%p")}
{_kpi("CET1 임계 심도",
      f"{mr.cet1_result.critical_severity:.2f}",
      tone="warn" if not mr.cet1_result.resilient else "good")}
</div>

<div class="card"><h2>48-1. metric별 임계 심도</h2>
<div class="chart">{chart}</div>
{_table(["metric","target","base","at break","상태","GDP 충격","LGD 가산"],
        rows, right_cols=[1,2,3,5,6])}
</div>

<div class="card"><h2>48-2. Critical pathway (binding constraint 거시 narrative)</h2>
<div class="callout bad"><b>{_esc(pathway['binding_constraint'])}</b> ·
s* = {pathway['binding_severity']:.2f}<br>
{_esc(pathway['narrative'])}</div>
<p class="section-lead">자본 임계(CET1/Tier1)는 신용손실 누적이, 유동성 임계(LCR/NSFR)는
HQLA 가치 하락 + funding runoff 가속이 주된 동인. 두 축이 동시 발현 시 더 낮은
severity에서 위기 도달.</p>
</div>
"""
    return _page("Multi-역스트레스", body, "48_reverse_stress_multi.html")


# ============================================================================
# 49. CCAR / DFAST 3년 분기 자본 경로 (v0.13.0)
# ============================================================================

def page_ccar_path(r: PipelineResult) -> str:
    deep = getattr(r, "stress_deep", {}) or {}
    if "ccar" not in deep:
        body = "<h1 class='title'>49. CCAR 3Y 경로</h1><p>미가용.</p>"
        return _page("CCAR 경로", body, "49_ccar_path.html")
    ccar = deep["ccar"]
    paths = ccar.paths
    consec = ccar.consecutive_breach
    rec = ccar.recovery_summary

    # 분기 라벨 = +1Q..+12Q (12개)
    qs = paths[paths["scenario"] == "baseline"]["quarter"].tolist()
    # CET1 path multi-line
    cet1_series = {}
    for sc in paths["scenario"].unique():
        g = paths[paths["scenario"] == sc].sort_values("q_index")
        cet1_series[sc] = g["cet1_ratio"].tolist()
    cet1_chart = viz.line_chart(
        qs, cet1_series, value_fmt=_pct,
        title="3년 (12 분기) CET1 경로",
        reference_value=r.bis.required["cet1"],
        reference_label=f"요구 {_pct(r.bis.required['cet1'])}",
    )

    # 자본 보충 action별 severely_adverse 경로
    actions_df = ccar.capital_actions
    sev = actions_df[actions_df["scenario"] == "severely_adverse"]
    action_series = {}
    for act in sev["action"].unique():
        g = sev[sev["action"] == act].sort_values("q_index")
        action_series[act] = g["cet1_ratio"].tolist()
    action_chart = viz.line_chart(
        qs, action_series, value_fmt=_pct,
        title="severely_adverse — 자본 보충 액션별 CET1 회복",
        reference_value=r.bis.required["cet1"],
        reference_label="CBR 요구선",
    )

    consec_rows = [[row["scenario"],
                    str(int(row["max_consecutive_breach"])),
                    _badge("ACTION", "FAIL") if row["supervisory_trigger"]
                    else _badge("OK", "PASS"),
                    _pct(row["min_cet1"]),
                    _pct(row["min_tier1"])]
                   for _, row in consec.iterrows()]
    rec_rows = [[row["action"], _pct(row["trough_cet1"]), row["trough_quarter"],
                  _pct(row["end_cet1"]),
                  str(row["recovery_quarter"]) if row["recovered"] else "미회복",
                  _badge("RECOVERED" if row["recovered"] else "PENDING",
                         "PASS" if row["recovered"] else "WARN")]
                for _, row in rec.iterrows()]

    n_trigger = int(consec["supervisory_trigger"].sum())

    body = f"""
<h1 class="title">49. CCAR / DFAST 3년 분기 자본 경로</h1>
<p class="section-lead">FED CCAR/DFAST 스타일 9~12 분기 horizon 자본 경로 +
자본 보충 액션 시뮬레이션 (배당중단·AT1·신주발행). 4분기 연속 CBR 침범 시
supervisory action 트리거.</p>

<div class="kpi-grid">
{_kpi("최장 연속 침범 (severe)",
      f"{int(consec[consec['scenario']=='severely_adverse']['max_consecutive_breach'].iloc[0])}Q")}
{_kpi("Supervisory trigger 시나리오 수", f"{n_trigger}",
      tone="bad" if n_trigger > 0 else "good")}
{_kpi("최저 CET1 (severe)",
      _pct(float(consec[consec['scenario']=='severely_adverse']['min_cet1'].iloc[0])))}
{_kpi("최저 Tier1 (severe)",
      _pct(float(consec[consec['scenario']=='severely_adverse']['min_tier1'].iloc[0])))}
</div>

<div class="row2">
<div class="card"><h2>49-1. 시나리오별 분기 CET1 경로 (12Q)</h2>
<div class="chart">{cet1_chart}</div>
</div>
<div class="card"><h2>49-2. 연속 침범 카운트</h2>
{_table(["시나리오","최장 연속","supervisory","최저 CET1","최저 Tier1"],
        consec_rows, right_cols=[1,3,4])}
<p class="section-lead">4Q 이상 연속 CBR 침범 시 감독당국이 추가 보고 + 시정조치
요구 (감독세칙 §3 자본 적정성 모니터링).</p>
</div>
</div>

<div class="card"><h2>49-3. severely_adverse 자본 보충 액션 시뮬레이션</h2>
<div class="chart">{action_chart}</div>
{_table(["액션","최저 CET1","최저 시점","기말 CET1","회복 시점","상태"],
        rec_rows, right_cols=[1,3])}
<p class="section-lead">passive = 무액션 / dividend_halt = 배당중단 /
at1_issuance = 1조원 AT1 / rights_issue = 2조원 신주 / full_recovery = 통합.
신주 발행이 가장 빠른 CET1 회복을 제공하나 주주가치 희석 비용 발생.</p>
</div>
"""
    return _page("CCAR 경로", body, "49_ccar_path.html")


# ============================================================================
# 50. 기후 자본 30Y horizon (NGFS) (v0.13.0)
# ============================================================================

def page_climate_capital(r: PipelineResult) -> str:
    deep = getattr(r, "stress_deep", {}) or {}
    if "climate_capital" not in deep:
        body = "<h1 class='title'>50. 기후 자본 경로</h1><p>미가용.</p>"
        return _page("기후 자본", body, "50_climate_capital.html")
    cc = deep["climate_capital"]
    p = cc.path
    worst = cc.worst_point

    years = sorted(p["year"].unique())
    cet1_series = {}
    for sc in p["scenario"].unique():
        g = p[p["scenario"] == sc].sort_values("year")
        cet1_series[sc] = g["cet1_ratio"].tolist()
    chart = viz.line_chart(
        [str(y) for y in years], cet1_series, value_fmt=_pct,
        title="NGFS 30Y horizon — CET1 비율 경로 (2030~2060)",
        reference_value=r.bis.required["cet1"],
        reference_label=f"요구 {_pct(r.bis.required['cet1'])}",
    )

    # 시나리오별 ECL 경로
    ecl_series = {}
    for sc in p["scenario"].unique():
        g = p[p["scenario"] == sc].sort_values("year")
        ecl_series[sc] = g["ecl"].tolist()
    ecl_chart = viz.line_chart(
        [str(y) for y in years], ecl_series, value_fmt=_won,
        title="NGFS 30Y horizon — ECL 경로",
    )

    p_disp = p.copy()
    rows = [[row["scenario"], str(int(row["year"])),
              f"${int(row['co2_price'])}/t",
              f"{row['hazard_intensity']:.0%}",
              _won(row["rwa_total"]),
              _won(row["ecl"]),
              _pct(row["cet1_ratio"]),
              f"{row['delta_cet1_pp']:+.2f}%p"]
             for _, row in p_disp.iterrows()]

    binding_rows = [[s, str(y),
                     _pct(float(p_disp[(p_disp['scenario']==s) &
                                        (p_disp['year']==y)]['cet1_ratio'].iloc[0]))]
                    for s, y in cc.binding_year.items()]

    body = f"""
<h1 class="title">50. 기후 자본 30Y horizon (NGFS)</h1>
<p class="section-lead">NGFS Phase IV 시나리오 (orderly / disorderly / hot_house)를
2030~2060 30Y horizon에 매핑. 섹터별 PD/LGD 충격 → RWA + ECL → CET1.</p>

<div class="kpi-grid">
{_kpi("최악 시점", f"{int(worst['year'])} {_esc(worst['scenario'])}",
      sub=_pct(worst['cet1_ratio']),
      tone="bad" if worst['cet1_ratio'] < r.bis.required['cet1'] else "warn")}
{_kpi("최악 CO2 가격", f"${int(worst['co2_price'])}/t")}
{_kpi("최악 hazard", f"{worst['hazard_intensity']:.0%}")}
{_kpi("최악 ECL", _won(worst['ecl']))}
</div>

<div class="row2">
<div class="card"><h2>50-1. CET1 30Y 경로</h2><div class="chart">{chart}</div></div>
<div class="card"><h2>50-2. ECL 30Y 경로</h2><div class="chart">{ecl_chart}</div></div>
</div>

<div class="card"><h2>50-3. 시나리오별 최저 CET1 도달 연도</h2>
{_table(["시나리오","도달 연도","CET1"], binding_rows, right_cols=[1,2])}
<p class="section-lead">disorderly 시나리오는 2030~2040 급격한 정책 강화로 transition shock
조기 발현. hot_house는 물리리스크 누적으로 후반(2050~2060) 자본 잠식 가속.</p>
</div>

<div class="card"><h2>50-4. NGFS path 상세 (전 시점)</h2>
{_table(["시나리오","연도","CO2 $/t","Hazard","RWA","ECL","CET1","Δ CET1"],
        rows, right_cols=[2,3,4,5,6,7])}
</div>
"""
    return _page("기후 자본", body, "50_climate_capital.html")


# ============================================================================
# 51. 유동성 stress + 회복 우선순위 (v0.13.0)
# ============================================================================

def page_liquidity_stress(r: PipelineResult) -> str:
    deep = getattr(r, "stress_deep", {}) or {}
    if "liquidity_stress" not in deep:
        body = "<h1 class='title'>51. 유동성 stress</h1><p>미가용.</p>"
        return _page("유동성 stress", body, "51_liquidity_stress.html")
    ls = deep["liquidity_stress"]
    ladder = deep["liquidity_recovery_ladder"]

    chart = viz.bar_chart(
        ls["scenario"].tolist(),
        ls["lcr"].tolist(),
        title="시나리오별 stressed LCR",
        value_fmt=lambda v: f"{v*100:.0f}%",
        reference_value=1.0, reference_label="100%",
        colors=[viz.GREEN if v >= 1.0 else viz.RED for v in ls["lcr"]],
    )
    nsfr_chart = viz.bar_chart(
        ls["scenario"].tolist(),
        ls["nsfr"].tolist(),
        title="시나리오별 stressed NSFR",
        value_fmt=lambda v: f"{v*100:.0f}%",
        reference_value=1.0, reference_label="100%",
        colors=[viz.GREEN if v >= 1.0 else viz.RED for v in ls["nsfr"]],
    )

    ls_rows = [[row["scenario"], row["narrative"][:38],
                 f"{row['severity']:.1f}",
                 f"{row['lcr']*100:.0f}%",
                 f"{row['nsfr']*100:.0f}%",
                 _badge("PASS" if row["lcr_passes"] else "FAIL",
                        "PASS" if row["lcr_passes"] else "FAIL"),
                 _badge("PASS" if row["nsfr_passes"] else "FAIL",
                        "PASS" if row["nsfr_passes"] else "FAIL")]
                for _, row in ls.iterrows()]

    ladder_rows = [[str(int(row["rank"])), row["action"],
                     _won(row["capacity"]),
                     _won(row["lcr_impact"]),
                     row["capital_impact"][:32],
                     row["cost"][:36],
                     _badge("COVERS" if row["covers_shortfall"] else "PARTIAL",
                            "PASS" if row["covers_shortfall"] else "WARN")]
                    for _, row in ladder.iterrows()]

    cumulative_chart = viz.bar_chart(
        ladder["action"].apply(lambda x: x[:14]).tolist(),
        ladder["cumulative_lcr_relief"].tolist(),
        title="누적 LCR 보충 capacity (조원)",
        value_fmt=_won,
        colors=[viz.GREEN if v else viz.PALETTE[0] for v in ladder["covers_shortfall"]],
    )

    n_fail = int((~ls["lcr_passes"]).sum() + (~ls["nsfr_passes"]).sum())
    body = f"""
<h1 class="title">51. 유동성 stress + 회복 우선순위</h1>
<p class="section-lead">시장충격 + funding runoff 가속 시 LCR/NSFR 영향 + 회복 액션
우선순위 사다리. HQLA 매각 → 도매자금 갱신 → CD발행 → AT1 → 신주.</p>

<div class="kpi-grid">
{_kpi("Base LCR", f"{ls.loc[0,'lcr']*100:.0f}%", tone="good")}
{_kpi("Combined severe LCR",
      f"{ls.loc[ls['scenario']=='combined_severe','lcr'].iloc[0]*100:.0f}%",
      tone="bad" if ls.loc[ls['scenario']=='combined_severe','lcr'].iloc[0] < 1.0 else "good")}
{_kpi("Base NSFR", f"{ls.loc[0,'nsfr']*100:.0f}%", tone="good")}
{_kpi("Liquidity 임계 위반 수", f"{n_fail}",
      tone="bad" if n_fail > 0 else "good")}
</div>

<div class="row2">
<div class="card"><h2>51-1. 시나리오별 LCR</h2><div class="chart">{chart}</div></div>
<div class="card"><h2>51-2. 시나리오별 NSFR</h2><div class="chart">{nsfr_chart}</div></div>
</div>

<div class="card"><h2>51-3. 유동성 stress 상세</h2>
{_table(["시나리오","narrative","s","LCR","NSFR","LCR 판정","NSFR 판정"],
        ls_rows, right_cols=[2,3,4])}
<p class="section-lead">market_shock: HQLA L2A −5pp, L2B −10pp. funding_run: 비예금 runoff +25%.
combined_severe: 두 충격 동시 발현 (severity 2.8).</p>
</div>

<div class="card"><h2>51-4. 회복 우선순위 사다리</h2>
<div class="chart">{cumulative_chart}</div>
{_table(["순위","액션","capacity","LCR 효과","자본 영향","비용","커버"],
        ladder_rows, right_cols=[2,3])}
<p class="section-lead">우선순위는 비용·자본효과 trade-off 기준. 가장 위험 없는
HQLA L2B 매각부터 시작해 신주 발행(자본 직접 보충, 희석 비용)까지 단계적 적용.</p>
</div>
"""
    return _page("유동성 stress", body, "51_liquidity_stress.html")
