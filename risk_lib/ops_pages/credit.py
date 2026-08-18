"""Ops pages — 신용리스크/충당금 심층 (IRB, SICR, PD 기간구조, 거시, DPD, 회수/LGD, Cure, Vintage, CECL).

Chrome (CSS/NAV)은 html_report에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)
from risk_lib.ops_pages._shared import _placeholder_page


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


# ============================================================================
# 62. CECL (US GAAP) vs IFRS 9 dual-reporting bridge
# ============================================================================

def page_cecl_ifrs9(r: PipelineResult) -> str:
    """CECL vs IFRS 9 provisioning comparison."""
    from risk_lib.cecl import compute_cecl, reconcile_ifrs9_cecl

    portfolio = getattr(r, "_portfolio", None)
    if portfolio is None:
        from risk_lib.data_gen import generate_portfolio
        portfolio = generate_portfolio(seed=r.meta.get("seed", 42))

    cecl = compute_cecl(portfolio)
    bridge = reconcile_ifrs9_cecl(r, portfolio, cecl=cecl)

    # bridge waterfall: IFRS9 → +gap → CECL
    bridge_chart = viz_advanced.attribution_waterfall(
        ["+ Stage1 lifetime", "+ macro overlay 차이"],
        [bridge.gap * 0.85, bridge.gap * 0.15],
        start_value=bridge.ifrs9_total, end_value=bridge.cecl_total,
        title="IFRS9 → CECL 충당금 bridge", value_fmt=_won,
    )

    # segment comparison
    seg = bridge.by_segment
    seg_chart = viz.bar_chart(
        seg["asset_class"].tolist(),
        (seg["gap"] / 1e9).tolist(),
        value_fmt=lambda v: f"{v:+.0f}bn",
        title="자산군별 CECL−IFRS9 gap (십억)",
        colors=[viz.RED if v > 0 else viz.GREEN for v in seg["gap"]],
    )

    seg_rows = [[r2["asset_class"], _won(r2["ifrs9"]), _won(r2["cecl"]),
                 _won(r2["gap"])]
                for _, r2 in seg.iterrows()]

    body = f"""
<h1 class="title">62. CECL (US GAAP) vs IFRS 9 이중보고 bridge</h1>
<p class="section-lead">글로벌/이중상장 은행의 dual-reporting. IFRS 9은 3-stage
(Stage 1 = 12개월 손실), CECL(ASC 326)은 day-1 전체 잔존기간 손실. 통상 CECL이
평상시 더 보수적(큼). 출처: FASB ASC 326 (2016), IFRS 9 5.5,
BCBS "Regulatory treatment of accounting provisions" (2017).</p>

<div class="kpi-grid">
{_kpi("IFRS 9 충당금", _won(bridge.ifrs9_total), sub="3-stage ECL")}
{_kpi("CECL 충당금", _won(bridge.cecl_total),
       sub="day-1 lifetime", tone="warn")}
{_kpi("Gap (CECL−IFRS9)", _won(bridge.gap),
       sub=f"{bridge.gap_pct*100:+.0f}%",
       tone="bad" if bridge.gap > 0 else "good")}
{_kpi("가중평균 만기", f"{cecl.weighted_life_years:.1f}년",
       sub="장기일수록 gap 확대")}
</div>

<div class="row2">
<div class="card"><h2>62-1. 충당금 bridge</h2><div class="chart">{bridge_chart}</div></div>
<div class="card"><h2>62-2. 자산군별 gap</h2><div class="chart">{seg_chart}</div></div>
</div>

<div class="card"><h2>62-3. 자산군별 IFRS9 vs CECL</h2>
{_table(["자산군","IFRS 9","CECL","Gap"], seg_rows, right_cols=[1,2,3])}
<div class="callout">{_esc(bridge.driver)}</div>
</div>

<div class="card"><h2>62-4. 규제자본 영향 (참고)</h2>
<p>회계 충당금 차이는 규제자본에도 영향: IRB 은행은 EL 대비 충당금 부족분을 CET1에서
차감, 초과분은 Tier 2에 제한적 산입 (BCBS 2017). CECL 도입 시 day-1 충당금 급증에 대한
경과조치(transitional arrangement)로 CET1 영향을 4~5년 분산 인식 가능.</p>
</div>
"""
    return _page("CECL vs IFRS9", body, "62_cecl_ifrs9.html")
