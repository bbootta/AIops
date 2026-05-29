"""Render a PipelineResult as a markdown 결재용 리포트."""

from __future__ import annotations

from datetime import date

from risk_lib.pipeline import PipelineResult


def _won(x: float) -> str:
    return f"{x:,.0f}"


def render_markdown(result: PipelineResult) -> str:
    r = result
    lines: list[str] = []
    add = lines.append

    add("# 리스크관리 종합 리포트")
    add("")
    add(f"- 생성일: {date.today().isoformat()}")
    add(f"- 시드(재현성): {r.meta.get('seed')}")
    add(f"- 준거: Basel III (CRE/MAR/OPE/LEV) + 금감원 은행업감독업무시행세칙")
    add("")

    # ---- 종합 판정 ----
    v = r.validation
    summ = v.summary()
    verdict = "결재 가능 (PASS)" if v.passes() else "결재 불가 (FAIL 존재)"
    add("## 0. 종합 판정")
    add("")
    add(f"**{verdict}** — 검증 체크 결과: {summ}")
    add("")

    # ---- 포트폴리오 ----
    add("## 1. 포트폴리오 개요")
    add("")
    add("| 자산군 | 건수 | EAD | 부도율 |")
    add("|---|---:|---:|---:|")
    for _, row in r.portfolio_summary.iterrows():
        add(f"| {row['asset_class']} | {int(row['n'])} | {_won(row['ead'])} "
            f"| {row['default_rate']:.2%} |")
    add("")

    # ---- PD 모형 ----
    add("## 2. 신용평가모형(PD) 변별력")
    add("")
    add("| 세그먼트 | Gini | KS | 학습/검증 |")
    add("|---|---:|---:|---:|")
    for seg, m in r.pd_metrics.items():
        add(f"| {seg} | {m['gini']:.3f} | {m['ks']:.3f} "
            f"| {int(m['n_train'])}/{int(m['n_test'])} |")
    add("")

    # ---- RWA ----
    rwa = r.rwa
    of = rwa["output_floor"]
    add("## 3. 위험가중자산(RWA)")
    add("")
    add("| 구분 | 금액 |")
    add("|---|---:|")
    add(f"| 신용 RWA (SA) | {_won(rwa['sa'])} |")
    add(f"| 신용 RWA (IRB) | {_won(rwa['irb'])} |")
    add(f"| 시장리스크 RWA | {_won(rwa['market'])} |")
    add(f"| 운영리스크 RWA | {_won(rwa['op'])} |")
    add(f"| 내부모형 합계 | {_won(rwa['internal_total'])} |")
    add(f"| 전부표준방법 합계 | {_won(rwa['standardised_total'])} |")
    add(f"| Output floor ({of.floor:.1%}) 적용액 | {_won(of.floor_amount)} |")
    add(f"| **최종 RWA** | **{_won(rwa['final_total'])}** |")
    add("")
    if of.is_binding:
        add(f"> Output floor가 **구속적**입니다. 내부모형 대비 +{_won(of.add_on)} 가산.")
    else:
        add("> Output floor는 비구속적 (내부모형 RWA가 하한 초과).")
    add("")

    # ---- BIS ----
    bis = r.bis
    add("## 4. BIS 자본적정성")
    add("")
    add("| 비율 | 실측 | 요구 | 잉여/부족 |")
    add("|---|---:|---:|---:|")
    for key, label in [("cet1", "CET1"), ("tier1", "Tier1"), ("total", "Total")]:
        actual = getattr(bis, f"{key}_ratio")
        add(f"| {label} | {actual:.2%} | {bis.required[key]:.2%} "
            f"| {bis.surplus_shortfall[key]:+.2%} |")
    add("")
    add(f"판정: **{'PASS' if bis.passes() else 'FAIL'}**")
    add("")

    # ---- 레버리지 ----
    lev = r.leverage
    add("## 5. 레버리지비율")
    add("")
    add(f"- 레버리지비율: **{lev.leverage_ratio:.2%}** "
        f"(요구 {lev.required:.2%}, {'충족' if lev.passes() else '미달'})")
    add(f"- 익스포저 측정치: {_won(lev.exposure_measure)}")
    add("")

    # ---- ECL ----
    add("## 6. IFRS9 기대신용손실(ECL) 충당금")
    add("")
    add(f"- 총 ECL: **{_won(r.ecl['total'])}**")
    add("")
    add("| Stage | 건수 | EAD | ECL | 커버리지 |")
    add("|---|---:|---:|---:|---:|")
    for stage, row in r.ecl["by_stage"].iterrows():
        add(f"| Stage {int(stage)} | {int(row['n'])} | {_won(row['ead'])} "
            f"| {_won(row['ecl'])} | {row['coverage']:.2%} |")
    add("")

    macro = r.macro_ecl
    uplift = macro.weighted_total - r.ecl["total"]
    add("### 6-1. 거시연계 PIT ECL (확률가중, IFRS9 forward-looking)")
    add("")
    add(f"- TTC(시점추정) ECL: {_won(r.ecl['total'])}")
    add(f"- PIT 확률가중 ECL: **{_won(macro.weighted_total)}** "
        f"(forward-looking uplift {uplift:+,.0f})")
    add("")
    add("| 시나리오 | 확률 | ECL |")
    add("|---|---:|---:|")
    for _, row in macro.by_scenario.iterrows():
        add(f"| {row['scenario']} | {row['probability']:.0%} | {_won(row['ecl'])} |")
    add("")

    # ---- 모니터링 ----
    m = r.monitoring
    add("## 7. 연체율 / 부도율 / 회수율")
    add("")
    add(f"- 연간 부도율 (노출액 가중): **{m['default_rate_ew']:.2%}**")
    add(f"- 연간 부도율 (건수): {m['default_rate_count']:.2%}")
    add(f"- 누적 회수율: **{m['recovery_rate']:.2%}**")
    add("")

    # ---- 한도 ----
    add("## 8. 한도관리")
    add("")
    if r.limits.empty:
        add("모든 한도 정상 (경보 없음).")
    else:
        add("| 한도 | 차원 | 버킷 | 노출 | 한도 | 사용률 | 등급 |")
        add("|---|---|---|---:|---:|---:|---|")
        for _, row in r.limits.head(15).iterrows():
            add(f"| {row['limit']} | {row['dimension']} | {row['bucket']} "
                f"| {_won(row['exposure'])} | {_won(row['threshold'])} "
                f"| {row['utilisation']:.1%} | {row['severity']} |")
    add("")

    # ---- 집중도 ----
    add("## 9. 집중리스크 (HHI)")
    add("")
    add("| 차원 | 버킷수 | HHI | 정규화 HHI | 최대비중 |")
    add("|---|---:|---:|---:|---:|")
    for _, row in r.concentration.iterrows():
        add(f"| {row['dimension']} | {int(row['n_buckets'])} | {row['hhi']:.4f} "
            f"| {row['normalised_hhi']:.4f} | {row['top1_share']:.2%} |")
    add("")

    # ---- RAPM ----
    add("## 10. RAPM (RAROC)")
    add("")
    add("| 자산군 | 건수 | 경제자본 | EL | 수익 | 평균 RAROC | Hurdle충족 |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for _, row in r.rapm.iterrows():
        add(f"| {row['asset_class']} | {int(row['n'])} | {_won(row['ec'])} "
            f"| {_won(row['el'])} | {_won(row['revenue'])} "
            f"| {row['raroc_mean']:.2%} | {row['pass_hurdle_pct']:.1%} |")
    add("")

    # ---- 스트레스 ----
    add("## 11. 스트레스테스트")
    add("")
    add("| 시나리오 | RWA합계 | ECL | CET1비율 | CET1잉여 | 통과 |")
    add("|---|---:|---:|---:|---:|---:|")
    for _, row in r.stress.iterrows():
        add(f"| {row['scenario']} | {_won(row['rwa_total'])} | {_won(row['ecl'])} "
            f"| {row['cet1_ratio']:.2%} | {row['cet1_surplus']:+.2%} "
            f"| {'O' if row['passes'] else 'X'} |")
    add("")

    rev = r.reverse_stress
    add("### 11-1. 역스트레스테스트 (CET1 임계 시나리오)")
    add("")
    add(f"- 기준 CET1: {rev.base_ratio:.2%} / 임계(버퍼포함 요구): {rev.target_ratio:.2%}")
    if rev.already_breached:
        add(f"- **무충격 상태에서 이미 임계 미달** (CET1 {rev.base_ratio:.2%} "
            f"≤ 임계 {rev.target_ratio:.2%}) — 역스트레스 해 없음, 즉시 자본확충 필요.")
    elif rev.resilient:
        add(f"- 최대 심도(s={rev.critical_severity:.1f})에서도 CET1 "
            f"{rev.ratio_at_break:.2%} > 임계 — **자본 내성 확보**.")
    else:
        add(f"- CET1을 임계까지 끌어내리는 **임계 심도 s={rev.critical_severity:.2f}**")
        add(f"- 함의 거시충격: GDP **{rev.implied_gdp_shock:+.1%}**, "
            f"LGD **+{rev.implied_lgd_addon:.1%}p**")
        add(f"- 임계점: RWA합계 {_won(rev.rwa_total_at_break)}, "
            f"ECL {_won(rev.ecl_at_break)}, CET1 {rev.ratio_at_break:.2%}")
    add("")

    # ---- 분기별 다기간 스트레스 경로 ----
    qs = r.meta.get("quarters", [])
    horizon = f"{qs[0]}~{qs[-1]}" if qs else ""
    add(f"### 11-2. 분기별 자본 스트레스 경로 ({horizon})")
    add("")
    add("| 시나리오 | 최저 CET1 | 최저시점 | 기말 CET1 | 최초위반 | 전구간통과 |")
    add("|---|---:|---|---:|---|---:|")
    for _, row in r.stress_path_trough.iterrows():
        fb = row["first_breach"] if isinstance(row["first_breach"], str) else "-"
        add(f"| {row['scenario']} | {row['trough_cet1']:.2%} | {row['trough_quarter']} "
            f"| {row['end_cet1']:.2%} | {fb} | {'O' if row['passes_all'] else 'X'} |")
    add("")
    # severe trajectory quarter-by-quarter
    sev = r.stress_path[r.stress_path["scenario"] == "severely_adverse"]
    if not sev.empty:
        add("심각(severely_adverse) 분기 CET1 추이:")
        add("")
        add("| 분기 | " + " | ".join(sev["quarter"]) + " |")
        add("|---|" + "---:|" * len(sev))
        add("| CET1 | " + " | ".join(f"{v:.2%}" for v in sev["cet1_ratio"]) + " |")
        add("")

    # ---- 검증 ----
    add("## 12. 자체검증 (정합성 + 백테스트)")
    add("")
    add("| 체크 | 상태 | 상세 |")
    add("|---|---|---|")
    for c in v.checks:
        add(f"| {c.name} | {c.status} | {c.detail} |")
    add("")
    hl = r.backtest["hosmer_lemeshow"]
    add(f"- Hosmer-Lemeshow: chi2={hl['chi_square']:.2f}, p={hl['p_value']:.3f} "
        f"({'캘리브레이션 양호' if hl['p_value'] >= 0.05 else '캘리브레이션 주의'})")
    zones = r.backtest["per_grade"]["zone"].value_counts().to_dict()
    add(f"- 등급별 백테스트 존: {zones}")
    add("")

    return "\n".join(lines)
