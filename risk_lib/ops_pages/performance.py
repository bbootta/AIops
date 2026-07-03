"""Ops pages — 성과/수익성 심층 (EVA/SVA, Pricing, RAPM 시나리오, 귀속분석).

Chrome (CSS/NAV)은 html_report에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _badge, _won, _pct,
)


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
