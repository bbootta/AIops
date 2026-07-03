"""Ops pages — 시장/트레이딩 심층 (시장리스크, CCR/CVA, XVA, Greeks, 시나리오 라이브러리, FRTB IMA, Intraday).

Chrome (CSS/NAV)은 html_report에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

import numpy as np
import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _badge, _won, _pct,
)
from risk_lib.ops_pages._shared import _placeholder_page


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


# ============================================================================
# 53. XVA full suite (CVA / DVA / FVA / ColVA / MVA)
# ============================================================================

def page_xva_full(r: PipelineResult) -> str:
    """Top-IB style XVA decomposition deep-dive."""
    from risk_lib.xva import compute_xva_portfolio
    if r.ccr is None or r.ccr.by_counterparty.empty:
        body = "<h1 class='title'>53. XVA Full Suite</h1><p>은행 거래상대방 노출 없음.</p>"
        return _page("XVA Full", body, "53_xva_full.html")

    bank_book = r.ccr.by_counterparty.rename(columns={"counterparty": "obligor_id"}).copy()
    bank_book["ead"] = bank_book.get("ead", bank_book.get("rwa", 1e9))
    bank_book["maturity"] = 3.0
    xp = compute_xva_portfolio(bank_book, seed=r.meta.get("seed", 42))

    totals = xp.totals
    # waterfall: CVA + FVA + ColVA + MVA − DVA = Net XVA
    waterfall = viz_advanced.attribution_waterfall(
        ["CVA", "+ FVA", "+ ColVA", "+ MVA", "− DVA"],
        [totals["cva"], totals["fva"], totals["colva"], totals["mva"], -totals["dva"]],
        start_value=0, end_value=xp.net_xva_pl,
        title="XVA Waterfall — Risk-free → Adjusted P&L",
        value_fmt=_won,
    )

    comp_bar = viz.bar_chart(
        ["CVA", "DVA", "FVA", "ColVA", "MVA"],
        [totals[k] for k in ("cva", "dva", "fva", "colva", "mva")],
        value_fmt=_won, title="XVA 구성 요소 절대값",
        colors=[viz.RED, viz.GREEN, viz.AMBER, viz.PALETTE[3], viz.PALETTE[4]],
    )

    # top 10 counterparties by net XVA
    top10 = xp.by_cpty.nlargest(10, "net_xva")
    top_chart = viz.horizontal_bar(
        [str(c)[:18] for c in top10["counterparty"]],
        top10["net_xva"].tolist(),
        title="Top 10 거래상대방 Net XVA", value_fmt=_won,
        color=viz.PALETTE[0],
    )

    cpty_rows = [[t["counterparty"][:18], _won(t["notional"]),
                  f"{t['maturity']:.1f}y", f"{t['cpty_cds_bps']:.0f} bps",
                  _won(t["cva"]), _won(t["dva"]), _won(t["fva"]),
                  _won(t["colva"]), _won(t["mva"]), _won(t["net_xva"])]
                 for _, t in top10.iterrows()]

    body = f"""
<h1 class="title">53. XVA Full Suite (CVA · DVA · FVA · ColVA · MVA)</h1>
<p class="section-lead">Top-IB 수준의 5종 valuation adjustment 분해.
파생거래 가격 V_total = V_risk-free + CVA(상대방 부도) − DVA(자행 부도)
+ FVA(funding) + ColVA(담보) + MVA(initial margin). 출처: Gregory (2020) 'The XVA Challenge',
BCBS d325 BA-CVA, CRR2 Art. 381–386.</p>

<div class="kpi-grid">
{_kpi("CVA", _won(totals["cva"]), sub="상대방 부도 손실 충당", tone="bad")}
{_kpi("DVA", _won(totals["dva"]), sub="자행 부도 시 채무경감", tone="good")}
{_kpi("FVA", _won(totals["fva"]), sub="비담보 funding 비용")}
{_kpi("ColVA", _won(totals["colva"]), sub="담보 funding 비용")}
{_kpi("MVA", _won(totals["mva"]), sub="IM funding 비용")}
{_kpi("Net XVA P&L", _won(xp.net_xva_pl),
       sub="P&L 영향", tone="bad" if xp.net_xva_pl > 0 else "good")}
</div>

<div class="row2">
<div class="card"><h2>53-1. XVA Waterfall</h2><div class="chart">{waterfall}</div></div>
<div class="card"><h2>53-2. 구성 요소 절대값</h2><div class="chart">{comp_bar}</div></div>
</div>

<div class="card"><h2>53-3. XVA 민감도 (Risk-management hooks)</h2>
<div class="kpi-grid">
{_kpi("CDS +10bp 민감도", _won(xp.cds_sensitivity_per_10bps),
       sub="ΔCVA per +10bp 상대방 CDS")}
{_kpi("EPE +1% 민감도", _won(xp.epe_sensitivity_per_pct),
       sub="ΔCVA per +1% EPE")}
{_kpi("50% CDS hedge 잔여", _won(xp.hedge_residual_after_50pct),
       sub="CDS 50% 매수 헷지 후 잔여 CVA")}
</div>
<p class="section-lead">CS01 기반 헷지 결정: 잔여 CVA가 risk limit 이상이면 CDS hedge ratio 상향.
ISDA SIMM IM 가산 시 MVA는 그 funding cost 반영.</p>
</div>

<div class="card"><h2>53-4. Top 10 거래상대방</h2>
<div class="chart">{top_chart}</div>
{_table(["거래상대방","notional","만기","CDS","CVA","DVA","FVA","ColVA","MVA","Net"],
        cpty_rows, right_cols=[1,2,3,4,5,6,7,8,9])}
</div>
"""
    return _page("XVA Full", body, "53_xva_full.html")


# ============================================================================
# 54. Trading book Greeks & sensitivities
# ============================================================================

def page_trading_sensitivities(r: PipelineResult) -> str:
    """Top-IB trading desk Greeks + linear VaR + PLA test."""
    from risk_lib.sensitivities import synthesise_trading_book, desk_aggregate

    if r.ccr is None or r.ccr.by_counterparty.empty:
        body = ("<h1 class='title'>54. Trading Greeks</h1>"
                "<p>트레이딩 북 정보 없음.</p>")
        return _page("Trading Greeks", body, "54_trading_sensitivities.html")

    bank_book = r.ccr.by_counterparty.rename(columns={"counterparty":"obligor_id"}).copy()
    bank_book["ead"] = bank_book.get("ead", 1e9)
    book = synthesise_trading_book(bank_book, seed=r.meta.get("seed", 42))
    ds = desk_aggregate(book)

    # by-kind table
    kind_rows = [[r2["kind"], f"{int(r2['n']):,}",
                  _won(r2["notional"]),
                  f"{r2['delta']:,.1f}", f"{r2['gamma']:.3f}",
                  f"{r2['vega']:,.0f}", f"{r2['theta']:,.2f}",
                  _won(r2["dv01"]), _won(r2["cs01"])]
                 for _, r2 in ds.by_kind.iterrows()]

    # Greeks bar chart
    greek_chart = viz.bar_chart(
        ["Delta","Gamma","Vega","Theta","dV01","CS01"],
        [ds.total_delta, ds.total_gamma * 100, ds.total_vega / 100,
         ds.total_theta * 365, ds.total_dv01 / 1e6, ds.total_cs01 / 1e6],
        value_fmt=lambda v: f"{v:,.2f}",
        title="Desk-level Greeks (스케일 normalised)",
    )

    # VaR component decomposition
    var_chart = viz.bar_chart(
        ["Δ (equity)", "Vega (vol)", "dV01 (IR)", "CS01 (credit)"],
        [abs(ds.total_delta) * 0.012 * 100 * 2.326,
         abs(ds.total_vega) * 0.05 * 100 * 2.326,
         abs(ds.total_dv01) * 8 * 2.326,
         abs(ds.total_cs01) * 6 * 2.326],
        value_fmt=_won, title="99% 1-day VaR 분해 (component 99%)",
    )

    body = f"""
<h1 class="title">54. Trading Book Greeks & Sensitivities</h1>
<p class="section-lead">트레이딩 데스크 1차·2차 sensitivity. Black-Scholes Greeks +
dV01(IR risk) + CS01(credit risk). Linear VaR(99% 1d) → P&L Attribution Test(PLAT) →
FRTB IMA 적격성. 출처: BCBS MAR (FRTB 2019), Hull 'Options, Futures and Other Derivatives'.</p>

<div class="kpi-grid">
{_kpi("총 trades", f"{len(book.trades):,}",
       sub=f"options {book.n_options} · swaps {book.n_swaps} · cds {book.n_credit}")}
{_kpi("총 notional", _won(book.total_notional))}
{_kpi("Net Delta", f"{ds.total_delta:,.2f}",
       sub="1% spot shock 시 PV 변동")}
{_kpi("Net Vega", f"{ds.total_vega:,.0f}", sub="1% vol shock PV 변동")}
{_kpi("Net dV01", _won(ds.total_dv01), sub="1bp parallel IR shift")}
{_kpi("Net CS01", _won(ds.total_cs01), sub="1bp credit spread shift")}
{_kpi("Linear VaR 99% 1d", _won(ds.var_linear_99))}
{_kpi("PLA residual", f"{ds.pla_residual*100:.1f}%",
       sub="<10% 목표 → IMA 적격",
       tone="good" if ds.pla_residual < 0.10 else "warn")}
</div>

<div class="row2">
<div class="card"><h2>54-1. Desk-level Greeks</h2><div class="chart">{greek_chart}</div></div>
<div class="card"><h2>54-2. VaR 분해</h2><div class="chart">{var_chart}</div></div>
</div>

<div class="card"><h2>54-3. 상품군별 sensitivity</h2>
{_table(["상품","건수","notional","Δ","Γ","Vega","Theta","dV01","CS01"],
        kind_rows, right_cols=[1,2,3,4,5,6,7,8])}
</div>

<div class="card"><h2>54-4. FRTB IMA 적격성 체크</h2>
<ul>
<li><b>PLAT</b> (P&L Attribution Test): residual {ds.pla_residual*100:.1f}% — {'<b>적격</b>' if ds.pla_residual<0.10 else '<b>부적격</b>'} (목표 ≤10%)</li>
<li><b>RFET</b> (Risk Factor Eligibility Test): 충분한 시장 데이터 확보 필요</li>
<li><b>NMRF</b> (Non-Modellable Risk Factors): stressed VaR 가산 적용</li>
<li><b>Backtesting traffic light</b>: 250일 1d VaR breaches — green/yellow/red</li>
</ul>
<p class="section-lead">FRTB IMA 미충족 시 표준방법(SA) 자본 가산 적용 (보통 +30~50%).</p>
</div>
"""
    return _page("Trading Greeks", body, "54_trading_sensitivities.html")


# ============================================================================
# 55. Scenario Library — historic + hypothetical + regulatory + climate
# ============================================================================

def page_scenario_library(r: PipelineResult) -> str:
    """Top-IB grade scenario library — 17 named scenarios with macro shocks."""
    from risk_lib.scenario_library import (
        SCENARIO_LIBRARY, by_family, to_dataframe,
    )

    df = to_dataframe()
    families = sorted(df["family"].unique())

    # severity heatmap by family
    sev_chart = viz.bar_chart(
        df["short"].tolist(), df["severity"].tolist(),
        value_fmt=lambda v: f"{v:.1f}",
        title=f"시나리오 severity ({len(df)}개)",
        colors=[
            (viz.RED if s == "historic" else viz.AMBER if s == "regulatory"
             else viz.PALETTE[3] if s == "climate" else viz.PALETTE[0])
            for s in df["family"]
        ],
    )

    # GDP × Equity scatter (size = severity) — visualises shock space
    gdp_chart = viz.bar_chart(
        df["short"].tolist()[:10],
        (df["gdp"] * 100).tolist()[:10],
        value_fmt=lambda v: f"{v:.1f}%",
        title="시나리오별 GDP 충격 (top 10)",
    )

    # family-level rows
    fam_rows = []
    for fam in families:
        sub = df[df["family"] == fam]
        fam_rows.append([
            fam, f"{len(sub)}",
            f"{sub['severity'].mean():.2f}",
            f"{sub['gdp'].min()*100:.2f}%",
            f"{sub['gdp'].max()*100:.2f}%",
            f"{sub['spread'].max()*100:.0f}bp",
            f"{sub['horizon'].mean():.1f}y",
        ])

    # detail rows (10 most severe)
    top10 = df.nlargest(10, "severity")
    detail_rows = [[
        f'<b>{row["name"]}</b><br><small>{row["citation"][:60]}</small>',
        row["family"], f'{row["severity"]:.1f}',
        f'{row["gdp"]*100:+.2f}%', f'{row["unemp"]*100:+.2f}%p',
        f'{row["equity"]*100:+.2f}%', f'{row["rate_10y"]*100:+.0f}bp',
        f'{row["spread"]*100:+.0f}bp', f'{row["hpi"]*100:+.2f}%',
    ] for _, row in top10.iterrows()]

    narratives = "".join(
        f'<div class="callout"><b>{row["name"]}</b> '
        f'({row["family"]}, severity {row["severity"]:.1f}, '
        f'{row["horizon"]:.1f}y horizon)<br>'
        f'{row["narrative"]}<br>'
        f'<small style="color:#6b7280">출처: {row["citation"]}</small></div>'
        for _, row in df.iterrows()
    )

    body = f"""
<h1 class="title">55. Scenario Library — 17 named scenarios</h1>
<p class="section-lead">Top-IB risk shops가 운영하는 named scenario library.
historic + hypothetical + regulatory + climate 4 family.
모든 macro shock은 1년 horizon peak value (GDP·실업률·FX·KOSPI·10y·spread·HPI·oil·CO2).
출처: Fed CCAR, EBA EU-wide ST, 금감원 가이드라인, NGFS Phase 4, IMF WEO, BIS BCBS.</p>

<div class="kpi-grid">
{_kpi("Library 크기", f"{len(df)}", sub=f"{len(by_family('historic'))} historic / "
       f"{len(by_family('hypothetical'))} hypothetical / "
       f"{len(by_family('regulatory'))} regulatory / "
       f"{len(by_family('climate'))} climate")}
{_kpi("최악 GDP", f"{df['gdp'].min()*100:.1f}%",
       sub=f"{df.loc[df['gdp'].idxmin(),'short']}")}
{_kpi("최악 Equity", f"{df['equity'].min()*100:.1f}%",
       sub=f"{df.loc[df['equity'].idxmin(),'short']}")}
{_kpi("최고 spread shock", f"{df['spread'].max()*100:.0f}bp",
       sub=f"{df.loc[df['spread'].idxmax(),'short']}")}
</div>

<div class="row2">
<div class="card"><h2>55-1. 시나리오 severity</h2><div class="chart">{sev_chart}</div></div>
<div class="card"><h2>55-2. GDP 충격 분포</h2><div class="chart">{gdp_chart}</div></div>
</div>

<div class="card"><h2>55-3. Family 비교 통계</h2>
{_table(["family","건수","평균 severity","min GDP","max GDP","max spread","평균 horizon"],
        fam_rows, right_cols=[1,2,3,4,5,6])}
</div>

<div class="card"><h2>55-4. Top 10 severe scenarios — 상세 shocks</h2>
{_table(["시나리오","family","severity","GDP","실업","Equity","10y","Spread","HPI"],
        detail_rows, right_cols=[2,3,4,5,6,7,8])}
</div>

<div class="card"><h2>55-5. 전체 시나리오 narrative + 출처</h2>
{narratives}
</div>
"""
    return _page("Scenario Library", body, "55_scenario_library.html")


# ============================================================================
# 56. FRTB IMA — PLAT + RFET + Backtest traffic light
# ============================================================================

def page_frtb_ima(r: PipelineResult) -> str:
    """FRTB IMA capital eligibility: PLAT + RFET + Backtest."""
    import numpy as np
    from risk_lib.frtb import (
        plat_test, rfet_test, backtest_var, compute_ima_capital,
    )

    seed = r.meta.get("seed", 42)
    rng = np.random.default_rng(seed + 9091)

    # Synthetic 250-day HPL / RTPL — slightly correlated
    hpl = rng.normal(0, 10, 250)
    rtpl = hpl * 0.92 + rng.normal(0, 2.0, 250)
    plat = plat_test(hpl, rtpl, desk="market_desk")

    # Synthetic price history with some missing rows for RFET
    n_factors = 12
    history_rows = 200
    price_history = pd.DataFrame({
        f"factor_{i}": rng.normal(100, 5, history_rows) if i % 4 != 0
        else np.where(rng.random(history_rows) < 0.7,
                      rng.normal(100, 5, history_rows), np.nan)
        for i in range(n_factors)
    })
    rfet = rfet_test(price_history)

    # Backtest — 1-day VaR vs realised PnL
    pnl = rng.normal(0, 1, 250)
    var_99 = np.full(250, 2.326)
    bt = backtest_var(pnl, var_99)

    # IMA capital
    es_97_5 = 5e9     # 50억 KRW synthetic
    sa_charge = 8e9
    ima = compute_ima_capital(es_97_5, plat, rfet, bt, sa_charge=sa_charge)

    plat_color = {"green": viz.GREEN, "amber": viz.AMBER, "red": viz.RED}
    plat_chart = viz.bar_chart(
        ["Spearman ρ", "KS stat"],
        [plat.spearman, plat.ks_stat],
        value_fmt=lambda v: f"{v:.3f}",
        title="PLAT — HPL vs RTPL",
        colors=[plat_color[plat.spearman_zone], plat_color[plat.ks_zone]],
    )

    bt_chart = viz.bar_chart(
        ["Exceptions"], [bt.n_exceptions],
        value_fmt=lambda v: f"{int(v)}",
        title=f"Backtest 250d — zone {bt.zone}, multiplier {bt.multiplier:.2f}",
        colors=[plat_color.get(bt.zone, viz.GREY)],
    )

    rfet_rows = rfet.factors.head(12).copy()
    rfet_table = [[r2["risk_factor"], int(r2["n_obs"]),
                   f"{r2['max_gap_days']:.0f}d",
                   _badge("modellable", "PASS")
                   if r2["modellable"] else _badge("NMRF", "FAIL")]
                  for _, r2 in rfet_rows.iterrows()]

    body = f"""
<h1 class="title">56. FRTB IMA Suite — PLAT · RFET · Backtest</h1>
<p class="section-lead">Top-IB 수준 시장리스크 IMA 적격성 평가.
BCBS MAR Fundamental Review of the Trading Book (2019) 표준에 따라
PLAT(Spearman ρ ≥ 0.80 + KS ≤ 0.09) + RFET(24 obs/yr, gap ≤ 30d) +
250d backtest traffic light(≤ 4 exceptions green) 통과 시 IMA 사용 가능,
실패 시 SA로 강제 fallback + 30% 가산.</p>

<div class="kpi-grid">
{_kpi("PLAT 등급", plat.overall_zone.upper(),
       sub=f"ρ={plat.spearman:.3f} / KS={plat.ks_stat:.3f}",
       tone="good" if plat.overall_zone == "green" else
       "warn" if plat.overall_zone == "amber" else "bad")}
{_kpi("Backtest 등급", bt.zone.upper(),
       sub=f"{bt.n_exceptions}/{bt.n_days}d exc · mult={bt.multiplier:.2f}",
       tone="good" if bt.zone == "green" else
       "warn" if bt.zone == "yellow" else "bad")}
{_kpi("RFET — modellable", f"{rfet.n_modellable}/{rfet.n_factors}",
       sub=f"NMRF {rfet.n_nmrf}개", tone="good" if rfet.n_nmrf == 0 else "warn")}
{_kpi("IMA 자본", _won(ima.ima_capital) if ima.ima_capital > 0
       else "SA fallback",
       sub=f"status: {ima.pla_status}",
       tone="good" if ima.pla_status == "active" else "bad")}
</div>

<div class="row2">
<div class="card"><h2>56-1. PLAT (P&L Attribution Test)</h2><div class="chart">{plat_chart}</div>
<p class="cite">기준: Spearman ρ ≥ 0.80 + KS ≤ 0.09 (green) / 0.70–0.80 또는 0.09–0.12 (amber) / 그 외 (red).
red zone에서 desk는 IMA 사용 불가 → SA로 강제 fallback.</p>
</div>
<div class="card"><h2>56-2. Backtest Traffic Light</h2><div class="chart">{bt_chart}</div>
<p class="cite">기준: ≤4 (green, mult 1.5) / 5–9 (yellow, mult 1.7~1.92) /
≥10 (red, mult 2.0 + IMA 박탈). BCBS MAR99.</p>
</div>
</div>

<div class="card"><h2>56-3. RFET — Risk Factor Eligibility (12개)</h2>
{_table(["risk factor", "관측치", "최대 gap", "판정"], rfet_table, right_cols=[1,2])}
<p class="cite">기준: 1년간 ≥24개 관측 + 30d 이내 gap. NMRF는 stressed ES (SES) 가산.</p>
</div>

<div class="card"><h2>56-4. IMA 자본 산출</h2>
<p>ES(97.5%, 10d) = {_won(ima.es_97_5)} × multiplier {ima.multiplier:.2f}
+ NMRF add-on {_won(ima.nmrf_addon)} = <b>{_won(ima.ima_capital)}</b></p>
<p>현재 desk status: <b>{ima.pla_status}</b></p>
{f'<div class="callout bad">desk가 IMA 자격을 상실했습니다. SA fallback 자본 {_won(ima.sa_capital_fallback)} 적용.</div>' if ima.pla_status == "forced_SA" else ''}
</div>
"""
    return _page("FRTB IMA", body, "56_frtb_ima.html")


# ============================================================================
# 61. Intraday risk — tick-by-tick VaR / limit utilisation / alerts
# ============================================================================

def page_intraday(r: PipelineResult) -> str:
    """Realtime intraday risk session simulation."""
    from risk_lib.intraday import run_intraday_session

    seed = r.meta.get("seed", 42)
    normal = run_intraday_session(r, seed=seed)
    stress = run_intraday_session(r, seed=seed, stress_tick=40)

    times = normal.ticks["time"].tolist()
    var_series = {
        "정상 세션 VaR": (normal.ticks["var"] / 1e9).tolist(),
        "스트레스 세션 VaR": (stress.ticks["var"] / 1e9).tolist(),
    }
    var_chart = viz.line_chart(
        times, var_series, value_fmt=lambda v: f"{v:.0f}bn",
        title="Intraday VaR 경로 (5분 bar × 78틱)",
        reference_value=normal.ticks["var"].iloc[0] * 2 / 1e9,
        reference_label="VaR 한도",
    )

    util_series = {
        "정상": (normal.ticks["util"] * 100).tolist(),
        "스트레스": (stress.ticks["util"] * 100).tolist(),
    }
    util_chart = viz.line_chart(
        times, util_series, value_fmt=lambda v: f"{v:.0f}%",
        title="VaR 한도 사용률 (%)",
        reference_value=100, reference_label="한도 100%",
    )

    # P&L attribution path (normal)
    pnl_series = {
        "누적 P&L": (normal.ticks["pnl"] / 1e9).tolist(),
        "Equity Δ": (normal.ticks["delta_pnl"] / 1e9).tolist(),
        "IR": (normal.ticks["ir_pnl"] / 1e9).tolist(),
    }
    pnl_chart = viz.line_chart(
        times, pnl_series, value_fmt=lambda v: f"{v:+.1f}bn",
        title="Intraday P&L attribution (정상)",
    )

    # alert table (stress, first 15)
    alert_rows = [[str(a.tick), a.time, _badge(a.severity, a.severity),
                   a.metric, f"{a.value*100:.0f}%", a.message[:60]]
                  for a in stress.alerts[:15]]

    from collections import Counter
    sev_counts = Counter(a.severity for a in stress.alerts)

    body = f"""
<h1 class="title">61. Intraday Risk — Tick-by-tick VaR / 한도 / 알림</h1>
<p class="section-lead">Top-IB 트레이딩 플로어의 실시간 리스크 refresh 시뮬레이션.
장 개시(09:00)부터 5분 bar × 78틱, 5개 risk factor (equity·rate·FX·spread·vol) random walk.
각 틱마다 VaR 재산출 + 한도 사용률 검사 + 알림 발화. seed 고정 → 동일 tick path →
동일 알림 (감사 재현 가능).</p>

<div class="kpi-grid">
{_kpi("정상 세션 최대 VaR", _won(normal.peak_var),
       sub=f"tick {normal.peak_var_tick}, 사용률 {normal.max_util*100:.0f}%")}
{_kpi("스트레스 최대 사용률", f"{stress.max_util*100:.0f}%",
       tone="bad" if stress.max_util >= 1.0 else "warn")}
{_kpi("스트레스 알림 수", f"{stress.n_alerts}",
       sub=f"RED {sev_counts.get('RED',0)} · AMBER {sev_counts.get('AMBER',0)} · WATCH {sev_counts.get('WATCH',0)}",
       tone="bad" if sev_counts.get("RED") else "warn")}
{_kpi("정상 세션 알림 수", f"{normal.n_alerts}")}
</div>

<div class="row2">
<div class="card"><h2>61-1. Intraday VaR 경로</h2><div class="chart">{var_chart}</div></div>
<div class="card"><h2>61-2. 한도 사용률</h2><div class="chart">{util_chart}</div></div>
</div>

<div class="card"><h2>61-3. Intraday P&L attribution</h2><div class="chart">{pnl_chart}</div>
<p class="section-lead">P&L을 delta(주식)·IR·credit 요인별로 실시간 분해.
갑작스러운 P&L 이탈 시 어느 factor가 원인인지 즉시 식별.</p>
</div>

<div class="card"><h2>61-4. 스트레스 세션 알림 로그 (상위 15)</h2>
{_table(["tick","시각","등급","지표","사용률","메시지"], alert_rows, right_cols=[4])
  if alert_rows else "<p>알림 없음.</p>"}
<p class="section-lead">WATCH 75% → AMBER 90% → RED 100% (한도 침범). RED 발생 시 즉시
데스크 포지션 축소 또는 헷지 지시. tick 40에 6σ 시장 충격 주입.</p>
</div>
"""
    return _page("Intraday", body, "61_intraday.html")
