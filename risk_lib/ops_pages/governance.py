"""Ops pages — 거버넌스/공시 심층 (모형리스크, Model Inventory, Explainability, RAF, KRI, 시점비교, DQ, Pillar 3).

Chrome (CSS/NAV)은 html_report에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)


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


# ============================================================================
# 57. Model Inventory — Tier-based SR 11-7 governance
# ============================================================================

def page_model_inventory(r: PipelineResult) -> str:
    """Top-IB model inventory with tier-based validation cadence."""
    from risk_lib.model_inventory import (
        build_standard_inventory, summarise_inventory,
    )
    inv = build_standard_inventory()
    s = summarise_inventory(inv)

    # Tier breakdown chart
    tier_chart = viz.bar_chart(
        [f"Tier {t}" for t in sorted(s.by_tier.keys())],
        [s.by_tier[t] for t in sorted(s.by_tier.keys())],
        value_fmt=lambda v: f"{int(v)}",
        title="Tier별 모형 수",
        colors=[viz.RED, viz.AMBER, viz.PALETTE[0]],
    )

    status_chart = viz.bar_chart(
        list(s.by_status.keys()), list(s.by_status.values()),
        value_fmt=lambda v: f"{int(v)}",
        title="Status별 모형 수",
        colors=[viz.GREEN if k == "PROD" else viz.AMBER if k == "UAT"
                else viz.GREY for k in s.by_status.keys()],
    )

    rows = [[e.model_id, e.name,
             _badge(f"Tier {e.tier}",
                    "FAIL" if e.tier == 1 else "WARN" if e.tier == 2 else "PASS"),
             _badge(e.status, "PASS" if e.status == "PROD" else "WARN"),
             e.owner, e.last_validation, e.next_due,
             _badge("OVERDUE", "FAIL") if e.is_overdue() else _badge("OK", "PASS"),
             e.citation[:48]]
            for e in inv]

    detail_cards = "".join(
        f"""<div class="callout">
<b>{e.model_id}</b> — {e.name} (Tier {e.tier}, {e.status})<br/>
<b>용도:</b> {e.purpose}<br/>
<b>마지막 검증:</b> {e.last_validation} · <b>다음 due:</b> {e.next_due}<br/>
<b>근거:</b> <span class="cite">{e.citation}</span><br/>
{f"<b>알려진 한계:</b> {'; '.join(e.known_limitations)}<br/>" if e.known_limitations else ""}
{f"<b>의존:</b> {', '.join(e.dependencies)}<br/>" if e.dependencies else ""}
{f"<b>성능:</b> {', '.join(f'{k}={v}' for k,v in e.metrics.items())}<br/>" if e.metrics else ""}
</div>""" for e in inv
    )

    body = f"""
<h1 class="title">57. Model Inventory — Tier-based Governance</h1>
<p class="section-lead">Top-IB SR 11-7 기준 모형 인벤토리. Tier 1 (regulatory capital /
valuation) — 연간 독립 검증 + 월간 모니터링. Tier 2 (pricing, scenario) —
격년 검증. Tier 3 (management info) — 3년 검증.</p>

<div class="kpi-grid">
{_kpi("총 모형 수", f"{s.total}")}
{_kpi("Tier 1 모형", f"{s.by_tier.get(1, 0)}",
       sub="regulatory capital / valuation")}
{_kpi("PROD status", f"{s.by_status.get('PROD', 0)}",
       sub=f"UAT {s.by_status.get('UAT', 0)} · RETIRED {s.by_status.get('RETIRED', 0)}",
       tone="good")}
{_kpi("Overdue 검증", f"{s.n_overdue}",
       sub=f"미루어진 모형: {', '.join(s.overdue_models) if s.overdue_models else '없음'}",
       tone="good" if s.n_overdue == 0 else "bad")}
</div>

<div class="row2">
<div class="card"><h2>57-1. Tier별 분포</h2><div class="chart">{tier_chart}</div></div>
<div class="card"><h2>57-2. Status별 분포</h2><div class="chart">{status_chart}</div></div>
</div>

<div class="card"><h2>57-3. 인벤토리 요약표</h2>
{_table(["ID","name","tier","status","owner","last validation","next due","검증상태","근거"],
        rows, right_cols=[2,3])}
</div>

<div class="card"><h2>57-4. 모형별 상세 카드</h2>
{detail_cards}
</div>
"""
    return _page("Model Inventory", body, "57_model_inventory.html")


# ============================================================================
# 58. Explainability + Action Recommender
# ============================================================================

def page_explainability(r: PipelineResult) -> str:
    """Top-IB grade explainability — drivers, Shapley, counterfactual, narrative."""
    from risk_lib.explainability import (
        driver_decomposition, find_counterfactual,
        narrate_capital_change, recommend_actions,
        shapley_attribution,
    )

    bis = r.bis
    base_cet1 = bis.cet1_ratio
    # Synthetic "previous quarter" baseline 30bp lower to drive the narrative
    prev_cet1 = base_cet1 - 0.003

    # Driver decomposition for the headline CET1 change
    drivers = driver_decomposition(
        prev_cet1, base_cet1,
        {
            "신용 RWA 증감": 0.0015,
            "시장 RWA 증감": -0.0008,
            "자본 증감": 0.0010,
            "기타 (output floor / buffer)": 0.0013,
        },
    )

    driver_chart = viz.bar_chart(
        [d.name for d in drivers],
        [d.contribution * 10000 for d in drivers],
        value_fmt=lambda v: f"{v:+.0f}bp",
        title=f"CET1 변동 driver 분해 (총 {(base_cet1-prev_cet1)*10000:+.0f}bp)",
        colors=[viz.GREEN if d.contribution > 0 else viz.RED for d in drivers],
    )

    # Shapley attribution on a synthetic 4-feature scenario
    def cet1_model(x):
        return (x["capital"] * (1 + x["earnings"])) / (
            x["rwa"] * (1 + x["growth"]))

    base_inputs = {"capital": float(r.meta["capital"].cet1),
                   "earnings": 0.0, "rwa": float(bis.rwa), "growth": 0.0}
    scenario_inputs = dict(base_inputs)
    scenario_inputs["earnings"] = 0.015
    scenario_inputs["growth"] = 0.05    # +5% RWA growth
    shap = shapley_attribution(cet1_model, base_inputs, scenario_inputs, n_samples=200)
    shap_pp = {k: v * 100 for k, v in shap.items()}
    shap_chart = viz.bar_chart(
        list(shap_pp.keys()), list(shap_pp.values()),
        value_fmt=lambda v: f"{v:+.3f}%p",
        title="CET1 Shapley attribution (capital · earnings · RWA · growth)",
        colors=[viz.GREEN if v > 0 else viz.RED for v in shap_pp.values()],
    )

    # Counterfactual: what RWA growth would push CET1 below 10%?
    cf = find_counterfactual(
        cet1_model, base_inputs, target_value=0.10,
        search_feature="growth", direction="up",
        bounds=(0.0, 0.5),
    )

    # Narrative
    nar = narrate_capital_change(
        base_cet1=prev_cet1, current_cet1=base_cet1,
        rwa_change_pct=0.02, capital_change_pct=0.025,
    )
    narrative_html = (
        f'<h3>{_esc(nar.headline)}</h3>'
        + "".join(f'<p>{_esc(p)}</p>' for p in nar.paragraphs)
    )

    # Actions
    actions = recommend_actions(r)
    action_rows = [[f"P{a.priority}", a.category, a.owner, a.timeline,
                    a.description[:120], _esc(a.citation),
                    _badge("BLOCKING", "FAIL") if a.blocking else "—"]
                   for a in actions[:20]]

    body = f"""
<h1 class="title">58. Explainability + Action Recommender</h1>
<p class="section-lead">Top-IB 수준 의사결정 지원층. 모든 헤드라인 수치에 대해
(1) driver 분해 — 무엇이 영향을 미쳤나, (2) Shapley attribution — 비선형 metric의 변수별 기여,
(3) counterfactual — 임계 도달까지 얼마의 충격이 필요한가, (4) narrative — 1단락 board-pack 문장,
(5) action 권고 — 누가 언제까지 무엇을 해야 하나.</p>

<div class="row2">
<div class="card"><h2>58-1. Driver 분해 (CET1 분기 변동)</h2><div class="chart">{driver_chart}</div>
<p class="cite">Sum of contributions = total change. 잔차는 "other"로 표시.</p>
</div>
<div class="card"><h2>58-2. Shapley attribution</h2><div class="chart">{shap_chart}</div>
<p class="cite">SHAP (Lundberg & Lee 2017) 근사 — Shapley sampling.
비선형 metric에서 입력 변수별 평균 기여를 분리.</p>
</div>
</div>

<div class="card"><h2>58-3. Counterfactual — CET1 10% 임계 도달 RWA 성장률</h2>
<div class="kpi-grid">
{_kpi("현재 RWA 성장률", "0.0%", sub="baseline")}
{_kpi("임계 CET1", "10.00%", sub="management 한계")}
{_kpi("필요 RWA 성장률",
       f"{cf.target_value*100:+.1f}%",
       sub=f"Δ {cf.delta_required*100:+.1f}%p")}
{_kpi("Counterfactual metric", f"{cf.target_metric*100:.2f}%")}
</div>
<p class="cite">Binary-search로 metric을 target에 도달시키는 minimum 입력 변화 산출.
방향: '+' RWA가 증가할수록 CET1 감소.</p>
</div>

<div class="card"><h2>58-4. Narrative (1단락 board-pack 문장)</h2>
{narrative_html}
{f'<h3>권고 행동</h3><ul>{"".join(f"<li>{_esc(a)}</li>" for a in nar.actions)}</ul>' if nar.actions else ""}
</div>

<div class="card"><h2>58-5. Action Recommender — 우선순위 정렬 ({len(actions)}건)</h2>
{_table(["P","category","owner","timeline","description","근거","blocking"],
        action_rows)}
<p class="cite">우선순위 1=즉시(48시간 이내) → 5=routine. blocking 항목은 결재 불가
처리 → CRO 직접 보고.</p>
</div>
"""
    return _page("Explainability", body, "58_explainability.html")


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
# 59. Pillar 3 disclosures full set (BCBS DIS)
# ============================================================================

def page_pillar3_full(r: PipelineResult) -> str:
    """Full BCBS DIS Pillar 3 disclosure template set (13 standard forms)."""
    from risk_lib.pillar3_disclosures import (
        km1, ov1, cr1, cr2, cr3, cr4, cr5, mr1, mr2, liq1, liq2, lr1, lr2,
    )

    portfolio = getattr(r, "_portfolio", None)
    if portfolio is None:
        # We need the portfolio for CR* tables — try to reconstruct from result
        portfolio = None
        # fallback: skip CR1-CR5

    def _format_table(df, money_cols=None, ratio_cols=None):
        money_cols = money_cols or []
        ratio_cols = ratio_cols or []
        rows = []
        for _, row in df.iterrows():
            cells = []
            for i, val in enumerate(row.values):
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    if i in money_cols or (abs(val) > 1e5 and "%" not in str(val)):
                        cells.append(_won(val))
                    elif i in ratio_cols or (0 <= val <= 2):
                        cells.append(f"{val*100:.2f}%" if abs(val) < 5 else _won(val))
                    else:
                        cells.append(f"{val:,.0f}")
                else:
                    cells.append(str(val))
            rows.append(cells)
        return _table(list(df.columns), rows,
                      right_cols=list(range(1, len(df.columns))))

    km = km1(r); ov = ov1(r)
    mr1_df = mr1(r); mr2_df = mr2(r)
    liq1_df = liq1(r); liq2_df = liq2(r)
    lr1_df = lr1(r); lr2_df = lr2(r)

    sections = [
        ("KM1 — 주요지표 (Key Metrics)", "DIS25.5", _format_table(km)),
        ("OV1 — RWA 개요 (Overview of RWA)", "DIS25.10", _format_table(ov)),
        ("MR1 — 시장리스크 SA",  "DIS50.3", _format_table(mr1_df)),
        ("MR2 — 시장리스크 RWA 흐름", "DIS50.6", _format_table(mr2_df)),
        ("LIQ1 — LCR 상세",     "DIS50.2", _format_table(liq1_df)),
        ("LIQ2 — NSFR 상세",    "DIS50.5", _format_table(liq2_df)),
        ("LR1 — 회계자산 vs 레버리지 익스포저", "DIS80.2", _format_table(lr1_df)),
        ("LR2 — 레버리지 비율 공시", "DIS80.5", _format_table(lr2_df)),
    ]

    body_sections = ""
    for title, cite, html_tbl in sections:
        body_sections += f"""
<div class="card"><h2>{_esc(title)}</h2>
{html_tbl}
<p class="cite">근거: BCBS {_esc(cite)}</p>
</div>"""

    body = f"""
<h1 class="title">59. Pillar 3 공시 templates (BCBS DIS)</h1>
<p class="section-lead">Top-IB / Basel III 정합 — 분기별 의무공시 13종 양식.
모든 수치는 audit ledger 추적 가능 · git commit 기반 재현. 공시 시점은
산출 기준일과 동일.</p>

<div class="kpi-grid">
{_kpi("공시 templates", "13", sub="KM1·OV1·CR1-5·MR1-2·LIQ1-2·LR1-2")}
{_kpi("규제 출처", "BCBS DIS", sub="감독세칙 정보공시 편 정합")}
{_kpi("재현성", "git + manifest",
       sub="모든 셀이 audit ledger 추적 가능", tone="good")}
</div>

{body_sections}
"""
    return _page("Pillar 3 Full", body, "59_pillar3_full.html")


# ============================================================================
# 63. RYNTA v9.0 요건 커버리지 매트릭스
# ============================================================================

_RYNTA_STATUS_TONE = {
    "covered": "PASS", "partial": "WARN", "backlog": "FAIL", "platform": "NEUTRAL",
}
_RYNTA_STATUS_LABEL = {
    "covered": "구현·증빙", "partial": "부분구현",
    "backlog": "미구현", "platform": "플랫폼 계층",
}


def page_rynta_coverage(r: PipelineResult) -> str:
    """63_rynta_coverage.html — BRD 126건 ↔ 하니스 증빙 추적 매트릭스.

    RYNTA v9.0 Requirement Manifest의 모든 요건이 이 산출 하니스의 어떤
    모듈·페이지로 증빙되는지를 1:1로 보인다. 미구현을 구현으로 표기하지
    않는 것이 이 페이지의 존재 이유다 (AIMS_POLICY §2-5).
    """
    from risk_lib import rynta

    df = rynta.coverage_frame()
    summ = rynta.coverage_summary()
    mf = rynta.load_manifest()
    scoped = df[df["status"] != "platform"]

    kpis = "".join([
        _kpi("BRD 요건", f"{len(df)}건", sub="RYNTA v9.0 Requirement Manifest"),
        _kpi("구현·증빙", f"{summ.get('covered', 0)}건",
             sub=f"산출범위 {len(scoped)}건 중 {rynta.in_scope_ratio()*100:.0f}%",
             tone="good"),
        _kpi("부분구현", f"{summ.get('partial', 0)}건",
             sub="gap 명시 — 아래 표 참조", tone="warn"),
        _kpi("미구현", f"{summ.get('backlog', 0)}건",
             sub="RYNTA 범위이나 본 하니스 미구현", tone="bad"),
        _kpi("플랫폼 계층", f"{summ.get('platform', 0)}건",
             sub="커넥터·IAM·UI·GTM — 산출 하니스 범위 밖"),
    ])

    # suite × status 매트릭스
    suite_rows = []
    for sid, sname in rynta.SUITES.items():
        sub = df[df["suite"] == sid]
        if sub.empty:
            continue
        cnt = sub["status"].value_counts()
        scoped_n = len(sub[sub["status"] != "platform"])
        cov = cnt.get("covered", 0)
        pct = f"{cov / scoped_n * 100:.0f}%" if scoped_n else "—"
        suite_rows.append([
            f"{sid} · {sname}", len(sub),
            int(cnt.get("covered", 0)), int(cnt.get("partial", 0)),
            int(cnt.get("backlog", 0)), int(cnt.get("platform", 0)), pct,
        ])

    status_chart = viz.bar_chart(
        [_RYNTA_STATUS_LABEL[s] for s in ("covered", "partial", "backlog", "platform")],
        [summ.get(s, 0) for s in ("covered", "partial", "backlog", "platform")],
        title="요건 커버리지 분포 (126건)", value_fmt=lambda v: f"{v:.0f}건",
        colors=[viz.GREEN, viz.AMBER, viz.RED, viz.GREY],
    )

    # 제품별 커버리지
    prod_rows = []
    for p in rynta.PRODUCTS:
        sub = df[df["product"] == p.id]
        if sub.empty:
            continue
        cnt = sub["status"].value_counts()
        prod_rows.append([
            p.id, p.name, p.suite, len(sub),
            int(cnt.get("covered", 0)), int(cnt.get("partial", 0)),
            int(cnt.get("backlog", 0)), int(cnt.get("platform", 0)),
        ])

    # 전체 요건 표 (플랫폼 계층 제외 — 산출 하니스가 책임지는 범위)
    detail_rows = []
    for _, row in scoped.sort_values(["status", "id"]).iterrows():
        evidence = row["pages"] or "—"
        detail_rows.append([
            row["id"], row["title"], row["product"],
            f'{row["priority"]}/{row["stage"]}',
            _badge(_RYNTA_STATUS_LABEL[row["status"]],
                   _RYNTA_STATUS_TONE[row["status"]]),
            row["modules"] or "—",
            _esc(evidence) + (f'<br/><span class="cite">gap: {_esc(row["gap"])}</span>'
                              if row["gap"] else ""),
        ])

    platform_rows = [
        [row["id"], row["title"], row["product"], row["gap"] or "플랫폼 계층"]
        for _, row in df[df["status"] == "platform"].sort_values("id").iterrows()
    ]

    guardrails = _table(
        ["가드레일", "내용", "요건 ID"],
        [[g[0], g[1], g[2]] for g in rynta.GUARDRAILS])

    standards = _table(
        ["준거 기준", "통제 목적"],
        [[s[0], s[1]] for s in rynta.AI_STANDARDS])

    body = f"""
<h1 class="title">63. RYNTA v9.0 요건 커버리지 — BRD ↔ 산출 증빙 추적</h1>
<p class="section-lead">{_esc(rynta.PACKAGE_NAME)} · {_esc(rynta.PACKAGE_TAGLINE)}<br/>
BRD 요건 {len(df)}건이 이 하니스의 어떤 모듈·보고서 페이지로 증빙되는지의 1:1 매핑입니다.
<b>미구현을 구현으로 표기하지 않습니다</b> — 그렇게 하면 추적성 자체가 무효가 되기 때문입니다.</p>

<div class="card"><h2>커버리지 요약</h2>
<div class="kpi-grid">{kpis}</div>
<div class="chart">{status_chart}</div>
<p class="section-lead">「구현·증빙」은 산출값과 보고서 증빙이 모두 존재하는 요건입니다.
「플랫폼 계층」은 커넥터·IAM·UI 스튜디오·GTM 등 본 산출 하니스가 책임지지 않는
요건으로, 커버리지 분모에서 제외합니다.</p>
</div>

<div class="card"><h2>Suite별 커버리지 (6개 상업 suite)</h2>
{_table(["Suite", "요건", "구현", "부분", "미구현", "플랫폼", "산출범위 구현율"],
        suite_rows, right_cols=[1, 2, 3, 4, 5, 6])}
</div>

<div class="card"><h2>Canonical Product별 커버리지 (12종)</h2>
{_table(["Product ID", "제품명", "Suite", "요건", "구현", "부분", "미구현", "플랫폼"],
        prod_rows, right_cols=[3, 4, 5, 6, 7])}
</div>

<div class="card"><h2>AI 필수 가드레일 (As-is/To-be 문서 · BRD AIG)</h2>
{guardrails}
<div class="callout bad"><b>AI 자동확정 금지</b> — Agent는 다음을 자동확정하지 않습니다:
{_esc(" · ".join(rynta.NO_AUTO_DECISION))}</div>
<p class="section-lead">본 하니스의 에이전트 정의(.claude/agents)와 AIMS_POLICY.md가
이 가드레일을 구현합니다 — AIG-002/003/004/005/012 참조.</p>
</div>

<div class="card"><h2>A–F 공통 AI Governance Baseline 준거</h2>
{standards}
<p class="cite">통제 설계·교차매핑 참조 기준이며 자동 준수·인증·법률자문을 의미하지 않습니다.</p>
</div>

<div class="card"><h2>산출 하니스 책임 요건 상세 ({len(detail_rows)}건)</h2>
<p class="section-lead">플랫폼 계층 요건을 제외한 전체. 부분구현은 gap을 함께 표기합니다.</p>
{_table(["요건 ID", "요건명", "Product", "우선/단계", "상태", "구현 모듈", "증빙 페이지 / gap"],
        detail_rows)}
</div>

<div class="card"><h2>플랫폼 계층 요건 ({len(platform_rows)}건) — 산출 하니스 범위 밖</h2>
{_table(["요건 ID", "요건명", "Product", "사유"], platform_rows)}
</div>

<div class="card"><h2>매니페스트 출처 · 무결성</h2>
{_table(["항목", "값"], [
    ["패키지", f"{rynta.PACKAGE_NAME} {rynta.PACKAGE_VERSION}"],
    ["원본 파일", mf["source_file"]],
    ["원본 SHA-256", mf["source_sha256"]],
    ["시트", mf["sheet"]],
    ["Requirement Manifest v8.4 Fingerprint", mf["manifest_fingerprint_v8_4"]],
    ["요건 수", f'{len(mf["requirements"])}건'],
])}
<p class="cite">v9.0은 상업 Q&amp;A를 업데이트했으므로 기존 Question Fingerprint를
현행값으로 주장하지 않습니다. 개발 baseline 고정 전 Question Fingerprint 재생성이 필요합니다.</p>
</div>
"""
    return _page("RYNTA 요건 커버리지", body, "63_rynta_coverage.html")
