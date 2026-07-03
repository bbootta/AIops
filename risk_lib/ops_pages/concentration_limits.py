"""Ops pages — 집중리스크/한도 심층 (집중 D-D, 한도 dashboard, 거대익스포저, 집중 스트레스).

Chrome (CSS/NAV)은 html_report에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)


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
