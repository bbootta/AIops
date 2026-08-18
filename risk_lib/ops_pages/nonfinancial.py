"""Ops pages — 비재무리스크 심층 (기후, 운영손실, 운영리스크 D-D, 민감도).

Chrome (CSS/NAV)은 html_report에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _won, _pct, _esc,
)
from risk_lib.ops_pages._shared import _placeholder_page


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
