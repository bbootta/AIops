"""Ops pages — 자본/스트레스 심층 (자본 스택, 버퍼, 레버리지, MDA, 역스트레스, CCAR, 기후자본, 유동성 stress, 자본 시뮬레이션).

Chrome (CSS/NAV)은 html_report에서 공유하며, 페이지 등록은 page_registry.PAGES 참조.
"""

import pandas as pd

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    _page, _table, _kpi, _badge, _won, _pct, _esc,
)
from risk_lib.ops_pages._shared import _placeholder_page


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


# ============================================================================
# 60. Multi-period capital simulation (8Q forward, CCAR/DFAST grade)
# ============================================================================

def page_capital_simulation(r: PipelineResult) -> str:
    """8-quarter forward capital projection with planned actions."""
    from risk_lib.capital_simulation import (
        simulate_capital_path, projection_summary, CapitalAction,
    )

    cap = r.meta["capital"]
    actions = [
        CapitalAction(quarter=4, action="at1_issue", amount=1e12),
        CapitalAction(quarter=5, action="dividend", amount=0.5e12),
    ]
    proj = simulate_capital_path(
        base_cet1=cap.cet1, base_tier1=cap.tier1, base_total=cap.total,
        base_rwa=r.bis.rwa, n_quarters=8,
        planned_actions=actions,
    )
    summ = projection_summary(proj)

    # CET1 path per scenario
    quarters = [f"Q+{q}" for q in sorted(proj["quarter"].unique())]
    series = {}
    for scen in proj["scenario"].unique():
        sub = proj[proj["scenario"] == scen].sort_values("quarter")
        series[scen] = sub["cet1_ratio"].tolist()
    fan_chart = viz_advanced.fan_chart(
        quarters,
        series.get("baseline", series[list(series)[0]]),
        series.get("severe", series[list(series)[0]]),
        series.get("adverse", series[list(series)[0]]),
        extra_series=series,
        value_fmt=_pct, title="8분기 CET1 path — 시나리오별",
        reference_value=0.07, reference_label="CCB 침범 임계 7%",
    )

    # MDA quartile per scenario heatmap
    mda_matrix = []
    for scen in proj["scenario"].unique():
        sub = proj[proj["scenario"] == scen].sort_values("quarter")
        mda_matrix.append(sub["mda_quartile"].astype(int).tolist())
    mda_chart = viz_advanced.heatmap(
        list(proj["scenario"].unique()),
        quarters, mda_matrix,
        title="MDA 분기별 quartile (0=정상, 1-4=깊을수록 분배 제한)",
        value_fmt=lambda v: str(int(v)), diverging=False, vmin=0, vmax=4,
    )

    summ_rows = [[r2["scenario"],
                  f"{r2['min_cet1']*100:.2f}%",
                  f"{r2['end_cet1']*100:.2f}%",
                  str(int(r2['first_breach_q'])) if pd.notna(r2["first_breach_q"]) else "—",
                  "YES" if r2["at1_triggered"] else "NO",
                  _badge("PASS" if r2["passes_all"] else "FAIL",
                         "PASS" if r2["passes_all"] else "FAIL")]
                 for _, r2 in summ.iterrows()]

    detail_rows = [[r2["scenario"], f"Q+{r2['quarter']}",
                    _won(r2["cet1"]), _won(r2["rwa"]),
                    f"{r2['cet1_ratio']*100:.2f}%",
                    f"{r2['tier1_ratio']*100:.2f}%",
                    str(int(r2["mda_quartile"])),
                    "YES" if r2["at1_triggered"] else "",
                    r2["actions"][:80]]
                   for _, r2 in proj.iterrows()]

    body = f"""
<h1 class="title">60. Multi-Period Capital Simulation</h1>
<p class="section-lead">8분기 forward CET1 projection (baseline / adverse / severe) ×
계획 자본 행동(AT1 발행 Q+4, 특별배당 Q+5) overlay.
각 분기마다 RWA 성장 / ECL 흡수 / 이익 적립 / 배당 (MDA quartile constraint) /
신규 자본 행동 / AT1 trigger (CET1 ≤ 5.125% 시 자동 전환) 적용.
CCAR / DFAST methodology 표준.</p>

<div class="kpi-grid">
{_kpi("Projection horizon", "8Q", sub="Q+1 → Q+8")}
{_kpi("계획 자본 행동", f"{len(actions)}", sub=", ".join(a.action for a in actions))}
{_kpi("Baseline 종착 CET1",
       f"{float(summ.loc[summ['scenario']=='baseline','end_cet1'].iloc[0])*100:.2f}%")}
{_kpi("Severe 최저 CET1",
       f"{float(summ.loc[summ['scenario']=='severe','min_cet1'].iloc[0])*100:.2f}%",
       tone="bad")}
</div>

<div class="card"><h2>60-1. 8Q CET1 Path</h2>
<div class="chart">{fan_chart}</div>
<p class="cite">기준선 = baseline · 음영 = adverse-severe envelope.
빨강 점선 = CCB(2.5%) 침범 임계 7.0% — 침범 시 MDA 분배제한 발동.</p>
</div>

<div class="card"><h2>60-2. MDA quartile per scenario × quarter</h2>
<div class="chart">{mda_chart}</div>
<p class="cite">0 = 버퍼 위 (자유 분배). 1-4 = 버퍼 침범 quartile (1=상층 60% retain →
4=하층 100% retain). 즉시 보유율 적용 — 배당·자기주식·AT1 쿠폰 제한.</p>
</div>

<div class="card"><h2>60-3. 시나리오별 요약</h2>
{_table(["scenario", "최저 CET1", "종착 CET1", "첫 breach Q", "AT1 trigger", "전구간 통과"],
        summ_rows, right_cols=[1,2])}
</div>

<div class="card"><h2>60-4. 분기별 detail (24행 = 3 × 8)</h2>
{_table(["scenario", "quarter", "CET1 KRW", "RWA",
         "CET1 비율", "Tier1 비율", "MDA Q", "AT1", "actions"], detail_rows)}
</div>
"""
    return _page("Capital Simulation", body, "60_capital_simulation.html")
