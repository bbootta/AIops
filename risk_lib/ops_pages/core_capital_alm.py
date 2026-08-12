"""Core pages — 자본/ALM (RWA, BIS·레버리지, 스트레스, ICAAP, ALM 허브, IRRBB/LCR/NSFR).

Chrome (CSS/NAV)은 report_chrome에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib.references import (
    LEVERAGE_MIN_RATIO, LCR_MIN, NSFR_MIN, IRRBB_OUTLIER_EVE_PCT_TIER1,
)
from risk_lib import viz, viz_advanced
from risk_lib.report_chrome import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)


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
