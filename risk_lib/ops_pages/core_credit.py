"""Core pages — 신용 (PD/LGD 모형, 챔피언·챌린저, ECL, 모니터링, 한도, RAPM).

Chrome (CSS/NAV)은 report_chrome에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib.references import (
    GINI_MIN_GOOD, HHI_HIGH,
)
from risk_lib import viz
from risk_lib.report_chrome import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)


def _page_pd(r: PipelineResult) -> str:
    pm = r.pd_metrics
    segs = list(pm.keys())
    bt = r.backtest
    hl = bt["hosmer_lemeshow"]
    disc = bt.get("discrimination", {})
    pof = bt.get("kupiec_pof", {})
    ccc = bt.get("christoffersen_cc", {})
    cal_curve = bt.get("calibration_curve", pd.DataFrame())

    # --- 변별력 4지표 차트
    g_vals = [pm[s]["gini"] for s in segs]
    disc_chart = viz.bar_chart(
        segs, g_vals, value_fmt=lambda v: f"{v:.3f}",
        title="세그먼트별 Gini",
        reference_value=GINI_MIN_GOOD,
        reference_label=f"양호 ≥ {GINI_MIN_GOOD:.2f}",
        colors=[viz.GREEN if g >= GINI_MIN_GOOD else viz.AMBER for g in g_vals],
    )
    auc_vals = [pm[s].get("auc_roc", 0.5) for s in segs]
    auc_chart = viz.bar_chart(
        segs, auc_vals, value_fmt=lambda v: f"{v:.3f}",
        title="세그먼트별 AUC-ROC",
        reference_value=0.75, reference_label="양호 ≥ 0.75",
        colors=[viz.GREEN if a >= 0.75 else viz.AMBER for a in auc_vals],
    )

    # --- ROC 곡선 (전체)  — 다시 계산: 정렬 + 누적
    import numpy as np
    # corporate 표본 기준 (backtest는 corporate에서 계산)
    cal_fpr, cal_tpr = [0.0], [0.0]
    if not cal_curve.empty:
        # cum_pos/cum_neg from grade-ordered defaults — 이미 cal_curve의 정렬은
        # 예측 PD 오름차순. ROC용으로는 내림차순으로 누적.
        # 백테스트 단계에서 raw 데이터가 없으므로 cal_curve로 근사한다.
        pass

    # --- 캘리브레이션 plot
    if not cal_curve.empty:
        cal_plot = viz.calibration_plot(
            cal_curve["mean_pd"].tolist(),
            cal_curve["realised_dr"].tolist(),
            counts=cal_curve["n"].tolist(),
            title="캘리브레이션 — 코퍼레이트",
        )
    else:
        cal_plot = "<p class='section-lead'>캘리브레이션 데이터 없음</p>"

    # --- 등급 백테스트
    pg = bt["per_grade"].copy()
    zone_counts = pg["zone"].value_counts().to_dict()
    zones_chart = viz.bar_chart(
        list(zone_counts.keys()), list(zone_counts.values()),
        value_fmt=lambda v: f"{int(v)}",
        title="등급별 백테스트 존",
        colors=[{"GREEN": viz.GREEN, "YELLOW": viz.AMBER,
                 "RED": viz.RED}.get(z, viz.PALETTE[0])
                for z in zone_counts.keys()],
    )

    # --- 세그먼트별 변별력 표
    rows = [[s, f"{pm[s]['gini']:.3f}", f"{pm[s].get('auc_roc', 0):.3f}",
             f"{pm[s]['ks']:.3f}", f"{pm[s].get('auprc', 0):.3f}",
             f"{pm[s].get('brier', 0):.4f}",
             f"{pm[s].get('brier_skill', 0):.3f}",
             f"{int(pm[s]['n_train']):,}/{int(pm[s]['n_test']):,}"]
            for s in segs]

    # --- 등급별 백테스트 디테일
    pg_rows = []
    for _, row in pg.iterrows():
        pg_rows.append([row.get("grade", "-"),
                        f"{int(row.get('n', 0)):,}",
                        f"{row.get('calibrated_pd', 0):.4f}",
                        f"{row.get('realised_dr', 0):.4f}",
                        f"{row.get('p_value', 1):.3f}",
                        _badge(row["zone"],
                               {"GREEN": "GREEN", "YELLOW": "WARN",
                                "RED": "FAIL"}.get(row["zone"], "NEUTRAL"))])

    # --- 변수 중요도 (코퍼레이트, permutation importance)
    var_imp_html = ""
    if "corporate" in r.explain:
        imp = r.explain["corporate"]["permutation"]
        var_imp_html = viz.horizontal_bar(
            imp["feature"].tolist(),
            imp["gini_drop_mean"].tolist(),
            title="코퍼레이트 PD — 변수 중요도 (Gini drop)",
            value_fmt=lambda v: f"{v:.3f}",
            color=viz.PALETTE[0],
        )

    # --- 계수 표
    coef_html = ""
    if "corporate" in r.explain:
        ct = r.explain["corporate"]["coefficients"]
        coef_rows = [[row["feature"], f"{row['coef']:+.3f}",
                      f"{row['odds_ratio']:.3f}",
                      f"{row['contribution_pct']*100:.1f}%",
                      row["direction"]]
                     for _, row in ct.iterrows()]
        coef_html = _table(
            ["변수", "계수β", "Odds ratio", "기여율", "방향"], coef_rows,
            right_cols=[1, 2, 3],
        )

    # --- 마스터 스케일 캘리브레이션 (코퍼레이트 세그먼트)
    ms_html = ""
    if "corporate" in r.calibration:
        ms = r.calibration["corporate"]
        ms_rows = [[row["grade"], f"{row['pd_midpoint']:.4f}",
                    f"{row['mean_pd_predicted']:.4f}",
                    f"{row['realised_dr']:.4f}",
                    f"{row['bias']:+.4f}", f"{int(row['n']):,}"]
                   for _, row in ms.iterrows()]
        ms_html = _table(
            ["등급", "마스터 PD", "평균 모형 PD", "실현 DR", "편차", "건수"],
            ms_rows, right_cols=[1, 2, 3, 4, 5],
        )

    # --- 등급 migration PSI
    mig_rows = []
    for seg, res in r.grade_migration.items():
        mig_rows.append([seg, f"{res['psi']:.4f}",
                         _badge(res["zone"],
                                {"GREEN": "GREEN", "AMBER": "WARN",
                                 "RED": "FAIL"}.get(res["zone"], "NEUTRAL"))])
    mig_html = _table(["세그먼트", "Grade PSI", "Zone"], mig_rows,
                      right_cols=[1]) if mig_rows else ""

    pof_tone = "good" if pof.get("p_value", 0) >= 0.05 else "warn"
    cc_tone = "good" if ccc.get("p_value", 0) >= 0.05 else "warn"

    body = f"""
<h1 class="title">2. 신용평가모형(PD) 변별력 · 캘리브레이션 · XAI</h1>
<p class="section-lead">세그먼트별 Gini/KS/AUC/AUPRC/Brier, Hosmer-Lemeshow,
Kupiec POF, Christoffersen 조건부 coverage, 캘리브레이션 곡선, 변수 중요도,
등급 PSI까지 통합. 준거: Basel CRE36, BCBS WP 14, 금감원 모형리스크 모범규준.</p>

<div class="card"><h2>2-1. 변별력 헤드라인 (전체 corporate 백테스트)</h2>
<div class="kpi-grid">
{_kpi("AUC-ROC", f"{disc.get('auc_roc', 0):.3f}",
       sub="양호 ≥ 0.75",
       tone=("good" if disc.get('auc_roc', 0) >= 0.75 else "warn"))}
{_kpi("Gini", f"{disc.get('gini', 0):.3f}",
       sub=f"양호 ≥ {GINI_MIN_GOOD:.2f}",
       tone=("good" if disc.get('gini', 0) >= GINI_MIN_GOOD else "warn"))}
{_kpi("AUPRC", f"{disc.get('auprc', 0):.3f}",
       sub=f"base rate {disc.get('base_rate', 0)*100:.1f}%")}
{_kpi("Brier", f"{disc.get('brier', 0):.4f}",
       sub=f"skill {disc.get('brier_skill', 0)*100:+.1f}%")}
{_kpi("Kupiec POF p", f"{pof.get('p_value', 0):.3f}",
       sub="≥ 0.05 캘리브레이션 양호", tone=pof_tone)}
{_kpi("Christoffersen CC p", f"{ccc.get('p_value', 0):.3f}",
       sub="≥ 0.05 unconditional+독립 양호", tone=cc_tone)}
</div>
</div>

<div class="row2">
<div class="card"><h2>2-2. 세그먼트별 Gini</h2><div class="chart">{disc_chart}</div></div>
<div class="card"><h2>2-3. 세그먼트별 AUC-ROC</h2><div class="chart">{auc_chart}</div></div>
</div>

<div class="card"><h2>2-4. 세그먼트별 변별력·캘리브레이션 지표</h2>
{_table(["세그먼트", "Gini", "AUC", "KS", "AUPRC", "Brier",
         "Brier skill", "학습/검증"], rows, right_cols=[1, 2, 3, 4, 5, 6, 7])}
</div>

<div class="row2">
<div class="card"><h2>2-5. 캘리브레이션 곡선 (Reliability)</h2>
<div class="chart">{cal_plot}</div>
<p class="section-lead">버블 크기 = bucket 표본 수. 45° 선 위 = 보수적,
아래 = 과소예측(red).</p>
</div>
<div class="card"><h2>2-6. Hosmer-Lemeshow</h2>
<div class="kpi-grid">
{_kpi("χ²", f"{hl['chi_square']:.2f}")}
{_kpi("p-value", f"{hl['p_value']:.3f}",
       tone=("good" if hl['p_value'] >= 0.05 else "warn"))}
{_kpi("판정", "양호" if hl['p_value'] >= 0.05 else "주의",
       sub="p ≥ 0.05 시 캘리브레이션 양호")}
</div>
<h3>등급별 백테스트 존</h3>
<div class="chart">{zones_chart}</div>
</div>
</div>

<div class="card"><h2>2-7. 마스터 스케일 캘리브레이션 — 코퍼레이트</h2>
{ms_html}
<p class="section-lead">등급별 (마스터 PD midpoint, 평균 모형 PD, 실현 DR).
편차가 일관되게 양수면 보수적, 음수면 PD 모형이 위반.</p>
</div>

<div class="card"><h2>2-8. 등급별 신호등 (코퍼레이트)</h2>
{_table(["등급", "건수", "캘리브 PD", "실현 DR", "p-value", "존"],
        pg_rows, right_cols=[1, 2, 3, 4])}
</div>

<div class="row2">
<div class="card"><h2>2-9. 변수 중요도 (Permutation)</h2>
<div class="chart">{var_imp_html}</div>
<p class="section-lead">Breiman(2001) permutation importance — 변수를 셔플했을
때 Gini drop의 평균(시드=42, n_repeats=3).</p>
</div>
<div class="card"><h2>2-10. 회귀 계수 · Odds Ratio</h2>
{coef_html}
</div>
</div>

<div class="card"><h2>2-11. 등급 분포 안정성 (Grade-level PSI)</h2>
{mig_html}
<p class="section-lead">train vs test 등급 분포의 PSI. &lt;0.10 GREEN,
0.10–0.25 AMBER, ≥0.25 RED.</p>
</div>
"""
    return _page("PD모형", body, "02_pd.html")


def _page_lgd_model(r: PipelineResult) -> str:
    """27. LGD 모형 — 모형 카드 + 백테스트 + 회수 곡선."""
    lgd = r.lgd_metrics
    if not lgd:
        body = ("<h1 class='title'>27. LGD모형</h1>"
                "<p>LGD 모형 데이터 없음.</p>")
        return _page("LGD모형", body, "27_lgd_model.html")

    rows = []
    bias_chart_data = []
    bias_chart_labels = []
    for seg, m in lgd.items():
        bt = m["backtest"]
        rows.append([seg, ", ".join(m["features"]),
                     f"{bt['mae']:.4f}", f"{bt['rmse']:.4f}",
                     f"{bt['r2']:+.3f}", f"{bt['brier']:.4f}",
                     f"{bt['bias']:+.4f}",
                     f"{bt['mean_realised']:.3f}",
                     f"{bt['mean_predicted']:.3f}",
                     f"{int(bt['n']):,}"])
        bias_chart_labels.append(seg)
        bias_chart_data.append(bt["bias"])

    bias_chart = viz.bar_chart(
        bias_chart_labels, bias_chart_data,
        value_fmt=lambda v: f"{v:+.3f}",
        title="세그먼트별 LGD 예측 편차(predicted - realised)",
        colors=[viz.GREEN if abs(b) < 0.05 else viz.AMBER
                for b in bias_chart_data],
    )

    # Histogram for the first segment (corporate if present)
    import numpy as np
    hist_html = ""
    hist_seg = "corporate" if "corporate" in lgd else next(iter(lgd))
    if hist_seg in lgd and "predicted_full" in lgd[hist_seg]:
        # need access to realised — pull from pd_metrics indirectly through
        # backtest's mean_realised but for distribution we re-derive
        # via the model's residual: use bucket calibration to approximate.
        m = lgd[hist_seg]
        # Use the bucket calibration to plot mean per bucket
        from risk_lib.models.lgd_model import lgd_bucket_calibration
        # We don't have raw arrays here; rebuild a histogram from
        # predicted_full only and use mean realised as overlay reference.
        preds = np.asarray(m["predicted_full"], dtype=float)
        hist_html = viz.histogram(
            preds.tolist(), bins=20,
            title=f"{hist_seg} — 예측 LGD 분포",
            color=viz.PALETTE[0],
            value_fmt=lambda v: f"{v*100:.0f}%",
        )

    body = f"""
<h1 class="title">27. LGD 모형 — 적합·백테스트·분포</h1>
<p class="section-lead">세그먼트별 beta(logit) ridge 회귀로 적합한 LGD 모형의
백테스트 결과. 산식: ŷ = floor + (1-floor)·σ(Xβ); 검증: MAE/RMSE/R²/Brier.
준거: Basel CRE36 LGD 모형 요건, BCBS WP14, 금감원 「은행업감독업무시행세칙」
별표 3-25.</p>

<div class="card"><h2>27-1. 세그먼트별 백테스트</h2>
{_table(["세그먼트", "변수", "MAE", "RMSE", "R²", "Brier", "편차",
         "실현 평균", "예측 평균", "표본 수"], rows,
        right_cols=[2, 3, 4, 5, 6, 7, 8, 9])}
</div>

<div class="row2">
<div class="card"><h2>27-2. 세그먼트별 편차</h2>
<div class="chart">{bias_chart}</div>
<p class="section-lead">|편차| &lt; 5%p 시 양호(녹색).
양수 = 보수적(과대 예측), 음수 = 과소 예측(자본 부족 위험).</p>
</div>
<div class="card"><h2>27-3. 예측 LGD 분포 — {hist_seg}</h2>
<div class="chart">{hist_html}</div>
</div>
</div>

<div class="card"><h2>27-4. 모형 카드</h2>
<p class="section-lead">현재 모형은 logit-변환 LGD에 ridge α=1을 적용한
GLM 근사. 표본이 부족하거나 LGD가 0/1에 집중되면 beta regression(GLM)으로
재학습 권고. floor=0.05.</p>
</div>
"""
    return _page("LGD모형", body, "27_lgd_model.html")


def _page_model_challenger(r: PipelineResult) -> str:
    """28. 챔피언 vs 챌린저 PD 모형 비교."""
    pm = r.pd_metrics
    ch = r.challenger_metrics
    if not ch:
        body = ("<h1 class='title'>28. 챔피언/챌린저</h1>"
                "<p>챌린저 데이터 없음.</p>")
        return _page("챔피언/챌린저", body, "28_model_challenger.html")

    rows = []
    seg_labels, champ_g, chal_g = [], [], []
    for seg, c in ch.items():
        champ = pm.get(seg, {})
        rows.append([seg,
                     f"{champ.get('gini', 0):.3f}",
                     f"{c.get('gini', 0):.3f}",
                     f"{c['delta_gini']:+.3f}",
                     f"{champ.get('auc_roc', 0):.3f}",
                     f"{c.get('auc_roc', 0):.3f}",
                     f"{champ.get('brier', 0):.4f}",
                     f"{c.get('brier', 0):.4f}",
                     ", ".join(c["features"]),
                     _badge(c["verdict"],
                            "PASS" if "CHAMPION" in c["verdict"] else
                            ("WARN" if "CHALLENGER" in c["verdict"]
                             else "NEUTRAL"))])
        seg_labels.append(seg)
        champ_g.append(champ.get("gini", 0))
        chal_g.append(c.get("gini", 0))

    # side-by-side
    deltas = [pm.get(s, {}).get("gini", 0) - ch[s]["gini"] for s in seg_labels]
    delta_chart = viz.bar_chart(
        seg_labels, deltas,
        value_fmt=lambda v: f"{v:+.3f}",
        title="ΔGini = Champion - Challenger",
        reference_value=0.01, reference_label="유의 차이 0.01",
        colors=[viz.GREEN if d > 0.01 else (viz.RED if d < -0.01 else viz.AMBER)
                for d in deltas],
    )

    # Decision recommendation
    upgrade = [s for s in seg_labels
               if "CHALLENGER" in ch[s]["verdict"]]
    keep = [s for s in seg_labels
            if "CHAMPION" in ch[s]["verdict"]]
    tie = [s for s in seg_labels
           if "동등" in ch[s]["verdict"]]

    body = f"""
<h1 class="title">28. 챔피언 vs 챌린저 — PD 모형 비교</h1>
<p class="section-lead">현재 production 모형(champion: 전체 변수)과 단순화된
benchmark(challenger: 핵심 변수 절반)를 동일 검증 표본에서 비교. ΔGini
&gt; 0.01 인 세그먼트는 챔피언 유지, 음수면 챌린저 승격 검토.</p>

<div class="card"><h2>28-1. ΔGini (Champion - Challenger)</h2>
<div class="chart">{delta_chart}</div>
</div>

<div class="card"><h2>28-2. 상세 비교표</h2>
{_table(["세그먼트", "Champ Gini", "Chal Gini", "ΔGini",
         "Champ AUC", "Chal AUC", "Champ Brier", "Chal Brier",
         "Challenger 변수", "판정"], rows,
        right_cols=[1, 2, 3, 4, 5, 6, 7])}
</div>

<div class="card"><h2>28-3. 의사결정 권고</h2>
<ul>
<li><b>챔피언 유지:</b> {", ".join(keep) if keep else "(없음)"}</li>
<li><b>챌린저 승격 검토:</b> {", ".join(upgrade) if upgrade else "(없음)"}</li>
<li><b>통계적 동등(재검토):</b> {", ".join(tie) if tie else "(없음)"}</li>
</ul>
<p class="section-lead">SR 11-7 / 금감원 모형리스크관리 모범규준에 따라 챌린저
모형은 매년 1회 이상 정기 비교 권고.</p>
</div>
"""
    return _page("챔피언/챌린저", body, "28_model_challenger.html")


def _page_ecl(r: PipelineResult) -> str:
    by_stage = r.ecl["by_stage"]
    stages = [f"Stage {int(s)}" for s in by_stage.index]
    ecl_vals = by_stage["ecl"].tolist()
    coverage = by_stage["coverage"].tolist()
    stage_chart = viz.bar_chart(stages, ecl_vals, title="Stage별 ECL")
    cov_chart = viz.bar_chart(stages, coverage, value_fmt=_pct,
                              title="Stage별 커버리지율 (ECL/EAD)")

    macro = r.macro_ecl
    macro_rows = [[row["scenario"], _pct(row["probability"], 0), _won(row["ecl"])]
                  for _, row in macro.by_scenario.iterrows()]
    macro_chart = viz.bar_chart(
        macro.by_scenario["scenario"].tolist(),
        macro.by_scenario["ecl"].tolist(),
        title="시나리오별 PIT ECL",
        colors=[viz.PALETTE[0], viz.AMBER, viz.RED],
    )

    qs = r.meta["quarters"]
    mp = r.macro_ecl_path
    series_q = {}
    for name in ["baseline", "downside", "severe", "weighted"]:
        g = mp[mp["scenario"] == name].sort_values("q_index")
        if not g.empty:
            series_q[("확률가중" if name == "weighted" else name)] = g["ecl"].tolist()
    path_chart = viz.line_chart(
        qs, series_q, value_fmt=lambda v: f"{v/1e9:,.0f}십억",
        title="분기별 ECL 충당금 경로",
    )

    stage_rows = [[f"Stage {int(s)}", f"{int(row['n']):,}",
                   _won(row["ead"]), _won(row["ecl"]), _pct(row["coverage"])]
                  for s, row in by_stage.iterrows()]

    # v0.9.0 deep-dive cross-links
    deep_block = ""
    if r.ifrs9_deep is not None:
        deep = r.ifrs9_deep
        # SICR triggers (top 3)
        s = deep.sicr.summary.sort_values("n_stage2", ascending=False).head(3)
        sicr_chart = viz.bar_chart(
            s["trigger"].tolist(), s["n_stage2"].tolist(),
            value_fmt=lambda v: f"{int(v):,}",
            title="Stage 2 진입 트리거 상위 3",
            colors=[viz.AMBER, viz.PALETTE[1], viz.PALETTE[3]],
        )
        # PD term — corporate cumulative as representative
        pdt = deep.pd_term
        corp = pdt[pdt["asset_class"] == "corporate"].sort_values("year")
        retail = pdt[pdt["asset_class"] == "retail_other"].sort_values("year")
        mort = pdt[pdt["asset_class"] == "residential_mortgage"].sort_values("year")
        pdt_series = {
            "corporate": corp["cumulative_pd"].tolist(),
            "retail_other": retail["cumulative_pd"].tolist(),
            "residential_mortgage": mort["cumulative_pd"].tolist(),
        }
        years_lbl = [str(y) for y in corp["year"].tolist()]
        pdt_chart = viz.line_chart(
            years_lbl, pdt_series, value_fmt=_pct,
            title="자산군별 누적 부도확률 (잔존기간)",
        )
        # Attribution mini waterfall
        attr = deep.attribution
        middle = attr[attr["effect"].isin(["pd", "lgd", "ead", "migration"])]
        start_v = float(attr[attr["effect"] == "start"]["value"].iloc[0])
        end_v   = float(attr[attr["effect"] == "end"]["value"].iloc[0])
        wf_chart = viz.waterfall(
            ["전기"] + middle["effect"].str.upper().tolist() + ["당기"],
            [start_v] + middle["value"].astype(float).tolist() + [end_v],
            value_fmt=_won,
            title="ECL 변화 귀속 (PD/LGD/EAD/Migration)",
        )
        deep_block = f"""
<div class="card"><h2>5-5. SICR 트리거 / PD 잔존기간 / 충당금 귀속 (요약)</h2>
<div class="row2">
<div><div class="chart">{sicr_chart}</div></div>
<div><div class="chart">{pdt_chart}</div></div>
</div>
<div class="chart">{wf_chart}</div>
<p style="font-size:12px;color:#6b7280">
상세는 35 SICR 분해 / 36 PD 잔존기간 / 37 거시 시나리오 / 38 충당금 귀속 페이지.
</p>
</div>
"""
    body = f"""
<h1 class="title">5. IFRS9 기대신용손실(ECL) 충당금</h1>
<p class="section-lead">시점추정(TTC) + 거시연계 PIT(확률가중) + 분기별 충당금 경로 + 트리거/귀속.</p>
<div class="kpi-grid">
{_kpi("TTC ECL", _won(r.ecl['total']))}
{_kpi("PIT 확률가중 ECL", _won(macro.weighted_total),
       sub=f"forward-looking uplift {(macro.weighted_total - r.ecl['total'])/1e9:+,.0f}십억", tone="warn")}
{_kpi("Stage 3 커버리지",
       f"{by_stage.loc[3, 'coverage']:.1%}" if 3 in by_stage.index else "—")}
</div>
<div class="row2">
<div class="card"><h2>5-1. Stage별 ECL</h2><div class="chart">{stage_chart}</div>
{_table(["Stage","건수","EAD","ECL","커버리지"], stage_rows, right_cols=[1,2,3,4])}
</div>
<div class="card"><h2>5-2. Stage별 커버리지</h2><div class="chart">{cov_chart}</div></div>
</div>
<div class="card"><h2>5-3. 거시연계 PIT 시나리오</h2>
<div class="row2">
<div><div class="chart">{macro_chart}</div></div>
<div>{_table(["시나리오","확률","ECL"], macro_rows, right_cols=[1,2])}</div>
</div>
</div>
<div class="card"><h2>5-4. 분기별 ECL 충당금 경로 (IFRS9 forward-looking)</h2>
<div class="chart">{path_chart}</div></div>
{deep_block}
"""
    return _page("ECL", body, "05_ecl.html")


def _page_monitoring(r: PipelineResult) -> str:
    m = r.monitoring
    delq = m["delinquency"]
    deep = r.monitoring_deep.get("delinquency") if r.monitoring_deep else None
    cure = r.monitoring_deep.get("cure") if r.monitoring_deep else None
    bucket_mx = deep.bucket_matrix if deep is not None else pd.DataFrame()
    npl = deep.npl_ratio if deep is not None else pd.DataFrame()
    dr_ts = deep.dr_timeseries if deep is not None else pd.DataFrame()
    from risk_lib import viz_advanced

    # 1) DPD bucket stacked bar (자산군 × 버킷, EAD)
    stacked_html = ""
    if not bucket_mx.empty:
        segs = sorted(bucket_mx["segment"].unique().tolist())
        from risk_lib.monitoring.deep import DEEP_DPD_LABELS
        series = {b: [float(bucket_mx[(bucket_mx["segment"] == s)
                                       & (bucket_mx["bucket"] == b)]["ead"].sum())
                       for s in segs] for b in DEEP_DPD_LABELS}
        stacked_html = viz.stacked_bar(
            segs, series, value_fmt=_won,
            title="자산군 × DPD 버킷 EAD (Basel III CRE36.69)",
        )

    # 2) DR time series chart per segment
    dr_chart = ""
    if not dr_ts.empty:
        quarters = list(pd.Categorical(dr_ts["quarter"],
                                       categories=sorted(dr_ts["quarter"].unique(),
                                                         key=lambda q: int(q.split("-")[-1]),
                                                         reverse=True)).categories)
        ser = {}
        for seg, sub in dr_ts.groupby("segment"):
            sub_sorted = sub.set_index("quarter").reindex(quarters)
            ser[seg] = sub_sorted["dr_ead"].fillna(0.0).tolist()
        dr_chart = viz.line_chart(
            quarters, ser, value_fmt=_pct,
            title="자산군별 분기 부도율 (EAD 가중, 12M rolling 합성)",
        )

    # 3) NPL ratio bar
    npl_chart = ""
    if not npl.empty:
        sub = npl[npl["segment"] != "전체"]
        npl_chart = viz.bar_chart(
            sub["segment"].tolist(), sub["npl_ratio"].tolist(),
            value_fmt=_pct, title="자산군별 NPL Ratio",
            colors=[viz.RED if v > 0.05 else (viz.AMBER if v > 0.02 else viz.GREEN)
                    for v in sub["npl_ratio"]],
        )

    # 4) Cure rate horizontal bar
    cure_chart = ""
    if cure is not None and not cure.by_segment.empty:
        c_sub = cure.by_segment[cure.by_segment["segment"] != "전체"]
        cure_chart = viz.horizontal_bar(
            c_sub["segment"].tolist(),
            c_sub["cure_rate_count"].tolist(),
            value_fmt=_pct, title="자산군별 Cure rate (건수)",
            color=viz.GREEN,
        )

    # tables
    npl_rows = []
    if not npl.empty:
        for _, row in npl.iterrows():
            npl_rows.append([row["segment"], _won(row["total_ead"]),
                             _won(row["npl_ead"]), _pct(row["npl_ratio"]),
                             f"{int(row['n_npl']):,}"])

    bucket_rows = []
    if not bucket_mx.empty:
        for _, row in bucket_mx.iterrows():
            bucket_rows.append([row["segment"], str(row["bucket"]),
                                f"{int(row['n_loans']):,}",
                                _won(row["ead"]), _pct(row["ead_share"]),
                                _pct(row["avg_pd"]) if row["avg_pd"] else "-"])

    body = f"""
<h1 class="title">6. 연체 · 부도 · 회수 모니터링 (자산건전성)</h1>
<p class="section-lead">DPD 버킷 분포 + NPL ratio + 분기 부도율 시계열 + cure rate.
기준: Basel III CRE36.69 (부도 정의), 감독세칙 자산건전성 분류, IFRS 9 5.5.5.</p>

<div class="kpi-grid">
{_kpi("부도율 (EAD 가중)", _pct(m['default_rate_ew']))}
{_kpi("부도율 (건수)", _pct(m['default_rate_count']))}
{_kpi("NPL ratio (전체)",
       _pct(float(npl[npl['segment']=='전체']['npl_ratio'].iloc[0])) if not npl.empty else "-")}
{_kpi("누적 회수율", _pct(m['recovery_rate']))}
</div>

<div class="card"><h2>6-1. 자산군 × DPD 버킷 EAD</h2>
<div class="chart">{stacked_html or "<p>데이터 없음</p>"}</div>
<p class="section-lead">버킷 정의: Current(0) · 1-29 · 30-59 · 60-89 · 90+(NPL).
90+ 는 감독세칙 상 고정/회수의문/추정손실 후보.</p>
{_table(["자산군","버킷","건수","EAD","점유율","평균 PD"], bucket_rows,
        right_cols=[2,3,4,5]) if bucket_rows else ""}
</div>

<div class="row2">
<div class="card"><h2>6-2. NPL Ratio (자산군별)</h2>
<div class="chart">{npl_chart}</div>
{_table(["자산군","총 EAD","NPL EAD","NPL ratio","NPL 건수"], npl_rows,
        right_cols=[1,2,3,4]) if npl_rows else ""}
</div>
<div class="card"><h2>6-3. 분기 부도율 시계열</h2>
<div class="chart">{dr_chart}</div>
<p class="section-lead">스냅샷 평균 기준 ±β 잡음 시뮬레이션. 시계열 회귀가 가능한
실 데이터로 교체 시 PIT vs TTC 시점 비교에도 활용.</p>
</div>
</div>

<div class="card"><h2>6-4. Cure rate — 부도 후 정상 복귀</h2>
<div class="chart">{cure_chart or "<p>데이터 없음</p>"}</div>
<p class="section-lead">window {cure.cure_window if cure else 6}개월 내 DPD 30 미만 복귀 비율.
상세는 <a href="41_cure_analysis.html">41. Cure 분석</a>.</p>
</div>

<div class="card"><h2>6-5. 자산군별 (legacy) 연체 분포</h2>
{_table(list(delq.columns),
        [[(_won(v) if isinstance(v, (int, float)) and abs(v) > 1e5 else _esc(v)) for v in row]
         for row in delq.to_numpy().tolist()],
        right_cols=list(range(1, len(delq.columns))))}
<p class="section-lead">상세 deep-dive: <a href="39_dpd_roll.html">39. DPD roll-rate</a>,
<a href="40_recovery_lgd.html">40. 회수·LGD</a>.</p>
</div>
"""
    return _page("모니터링", body, "06_monitoring.html")


def _page_limits(r: PipelineResult) -> str:
    limits = r.limits.copy() if r.limits is not None else pd.DataFrame()
    conc = r.concentration

    conc_chart = viz.bar_chart(
        conc["dimension"].tolist(), conc["hhi"].tolist(),
        value_fmt=lambda v: f"{v:.3f}",
        title="차원별 HHI",
        reference_value=HHI_HIGH, reference_label=f"고집중 기준 {HHI_HIGH:.2f}",
        colors=[viz.RED if v >= HHI_HIGH else (viz.AMBER if v >= 0.10 else viz.GREEN)
                for v in conc["hhi"]],
    )
    top_lim = limits.head(15)
    if not top_lim.empty:
        util_chart = viz.horizontal_bar(
            [f"{row['dimension']}:{row['bucket']}" for _, row in top_lim.iterrows()],
            top_lim["utilisation"].tolist(),
            value_fmt=_pct, title="한도 사용률 상위 15", color=viz.RED,
            reference_value=1.0, reference_label="100%",
        )
    else:
        util_chart = "<p>모든 한도 정상.</p>"

    lim_rows = [[row["limit"], row["dimension"], str(row["bucket"]),
                 _won(row["exposure"]), _won(row["threshold"]),
                 _pct(row["utilisation"], 1),
                 _badge(row["severity"], {"OK":"GREEN","WARN":"WARN","BREACH":"FAIL","CRITICAL":"FAIL"}.get(row["severity"],"NEUTRAL"))]
                for _, row in top_lim.iterrows()]
    conc_rows = [[row["dimension"], f"{int(row['n_buckets']):,}",
                  f"{row['hhi']:.4f}", f"{row['normalised_hhi']:.4f}",
                  _pct(row["top1_share"])] for _, row in conc.iterrows()]

    # v0.11.0 deep-dive 요약 — 다차원 한도 + escalation matrix
    deep_block = ""
    if getattr(r, "limits_deep", None) is not None:
        ld = r.limits_deep
        sev_counts = ld.dashboard["severity"].value_counts().to_dict()
        sev_chart = viz.bar_chart(
            ["OK", "WARN", "CRITICAL", "BREACH"],
            [sev_counts.get(s, 0) for s in ["OK","WARN","CRITICAL","BREACH"]],
            value_fmt=lambda v: f"{int(v):,}",
            title="severity별 한도 분포",
            colors=[viz.GREEN, viz.AMBER, "#E07A1F", viz.RED],
        )
        esc_rows = [[r2["severity"], r2["action"], r2["owner"],
                     r2["report_cycle"], r2["approval_required"]]
                    for _, r2 in ld.escalation.iterrows()]
        deep_block = f"""
<div class="row2">
<div class="card"><h2>다차원 한도 분포 (총 {len(ld.dashboard):,} 한도×버킷)</h2>
<div class="chart">{sev_chart}</div>
<p class="section-lead">상세는 <a href="42_limit_dashboard.html">42. 한도 dashboard</a>,
거대익스포저(BCBS LEX)는 <a href="43_large_exposure.html">43</a>,
스트레스 사용률은 <a href="44_concentration_stress.html">44</a>.</p>
</div>
<div class="card"><h2>escalation matrix (감독세칙 + 내규)</h2>
{_table(["severity","조치","책임자","보고주기","승인"], esc_rows)}
</div>
</div>"""

    body = f"""
<h1 class="title">7. 한도관리 & 집중리스크</h1>
<p class="section-lead">한도 사용률 (동일차주 / 섹터 / 국가) + HHI 집중도.
근거: 「은행법」 제35조, 「은행업감독규정」 제29조, BCBS 283 LEX.</p>
<div class="row2">
<div class="card"><h2>한도 사용률</h2><div class="chart">{util_chart}</div></div>
<div class="card"><h2>HHI 집중도</h2><div class="chart">{conc_chart}</div></div>
</div>
<div class="card"><h2>한도 경보 상세 (상위 15)</h2>
{_table(["한도","차원","버킷","노출","한도","사용률","등급"], lim_rows, right_cols=[3,4,5])}
</div>
<div class="card"><h2>HHI 차원별</h2>
{_table(["차원","버킷수","HHI","정규화 HHI","최대비중"], conc_rows, right_cols=[1,2,3,4])}
</div>
{deep_block}
"""
    return _page("한도·집중도", body, "07_limits.html")


def _page_rapm(r: PipelineResult) -> str:
    rapm = r.rapm.copy()
    raroc_chart = viz.bar_chart(
        rapm["asset_class"].tolist(), rapm["raroc_mean"].tolist(),
        value_fmt=_pct, title="자산군별 평균 RAROC",
        reference_value=r.meta["hurdle_rate"],
        reference_label=f"hurdle {_pct(r.meta['hurdle_rate'])}",
        colors=[viz.GREEN if v >= r.meta["hurdle_rate"] else viz.RED
                for v in rapm["raroc_mean"]],
    )
    pass_chart = viz.bar_chart(
        rapm["asset_class"].tolist(), rapm["pass_hurdle_pct"].tolist(),
        value_fmt=_pct, title="hurdle 충족 비율",
    )
    rows = [[row["asset_class"], f"{int(row['n']):,}",
             _won(row["ec"]), _won(row["el"]), _won(row["revenue"]),
             _pct(row["raroc_mean"]), _pct(row["pass_hurdle_pct"])]
            for _, row in rapm.iterrows()]
    # ---- Du Pont decomposition deep-dive --------------------------------
    deep_block = ""
    rd = getattr(r, "rapm_deep", None)
    if rd is not None:
        dupont = rd.dupont
        dupont_rows = [[row["asset_class"], f"{int(row['n']):,}",
                        _pct(row["asset_yield"], 2),
                        f"{row['capital_velocity']:.2f}x",
                        _pct(row["efficiency"], 1),
                        _pct(row["loss_ratio"], 2),
                        _pct(row["rf_benefit"], 2),
                        _pct(row["raroc_identity"], 2)]
                       for _, row in dupont.iterrows()]
        # Waterfall for the worst (lowest RAROC) asset class
        worst_idx = dupont["raroc_identity"].idxmin()
        worst = dupont.loc[worst_idx]
        from risk_lib.performance.rapm_deep import waterfall_components
        wf_items = waterfall_components(worst)
        # waterfall() treats first/last as totals; prepend a 0 baseline so
        # the gross-spread bar is rendered as a delta from zero.
        wf_labels = ["기준(0)"] + [k for k, _ in wf_items]
        wf_values = [0.0] + [v for _, v in wf_items]
        wf_chart = viz.waterfall(
            wf_labels, wf_values, value_fmt=_pct,
            title=f"RAROC 분해 (Du Pont) — {worst['asset_class']}",
        )
        # EVA by asset class
        evac = rd.eva_by_class
        eva_chart = viz.bar_chart(
            evac["asset_class"].tolist(), evac["eva"].tolist(),
            value_fmt=_won, title="자산군별 EVA (KRW)",
            colors=[viz.GREEN if v >= 0 else viz.RED for v in evac["eva"]],
        )
        bench = rd.benchmark
        deep_block = f"""
<div class="kpi-grid">
{_kpi("가중 RAROC", _pct(rd.summary['raroc_weighted'], 2),
       sub=f"hurdle {_pct(rd.summary['hurdle_rate'])}",
       tone="good" if rd.summary['raroc_weighted'] >= rd.summary['hurdle_rate']
            else "bad")}
{_kpi("EVA 총합", _won(rd.summary['eva_total']),
       tone="good" if rd.summary['eva_total'] >= 0 else "bad")}
{_kpi("가치창출 거래 비중", _pct(rd.summary['value_creating_pct'], 1))}
{_kpi("재가격 대상 건수", f"{rd.summary['n_repricing']:,}",
       sub="RAROC ∈ [0, hurdle)", tone="warn")}
{_kpi("종결 검토 건수", f"{rd.summary['n_terminate']:,}",
       sub="RAROC < -10%", tone="bad")}
{_kpi("피어 대비", bench['position'],
       sub=f"gap {bench['gap_to_median']*100:+.2f}%p (median {_pct(bench['peer_median'])})")}
</div>

<div class="row2">
<div class="card"><h2>8-1. RAROC 분해 (Du Pont) — 최저 자산군</h2>
<div class="chart">{wf_chart}</div>
<p class="section-lead">RAROC = (수익률 × 자본속도 × 효율) − EL/EC + rf.
구성요소별 기여도 분해(BCBS RAPM appendix).</p></div>
<div class="card"><h2>8-2. 자산군별 EVA</h2>
<div class="chart">{eva_chart}</div>
<p class="section-lead">EVA = (RAROC − hurdle) × EC. 양(+)이면 자기자본비용 대비 가치 창출.</p></div>
</div>

<div class="card"><h2>8-3. Du Pont 분해 — 자산군별</h2>
{_table(["자산군","건수","수익률(R/EAD)","자본속도(EAD/EC)","효율(1-C/R)","EL/EC","rf","RAROC(재구성)"],
        dupont_rows, right_cols=[1,2,3,4,5,6,7])}
</div>
"""
    body = f"""
<h1 class="title">8. RAPM (RAROC)</h1>
<p class="section-lead">자산군별 위험조정수익률과 hurdle rate({_pct(r.meta['hurdle_rate'])}) 충족 비율.
RAROC = (순이자수익 + 수수료 − 운영비 − EL + EC·rf) / EC.
EL = PD × LGD × EAD, EC = K × EAD (Basel CRE31 IRB).</p>
<div class="row2">
<div class="card"><h2>평균 RAROC</h2><div class="chart">{raroc_chart}</div></div>
<div class="card"><h2>hurdle 충족 비율</h2><div class="chart">{pass_chart}</div></div>
</div>
<div class="card"><h2>자산군별 상세</h2>
{_table(["자산군","건수","경제자본","EL","수익","평균 RAROC","Hurdle 충족"], rows,
        right_cols=[1,2,3,4,5,6])}
</div>
{deep_block}
"""
    return _page("RAPM", body, "08_rapm.html")
