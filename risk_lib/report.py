"""Render a PipelineResult as a markdown 결재용 리포트.

Sectionising is for maintainability only — text output is intentionally
byte-identical to the prior monolithic implementation (verified against a
golden copy of the v0.1 report).  Korean labels and table formatting are not
to be touched.
"""

from __future__ import annotations

from datetime import date

from risk_lib.pipeline import PipelineResult
from risk_lib.references import ALL_CITATIONS


def _won(x: float) -> str:
    return f"{x:,.0f}"


def _md_table(headers: list[str], aligns: list[str], rows: list[list[str]]) -> list[str]:
    """Return the markdown lines for a table — header, divider, rows.

    `aligns` items are one of "l", "r", "c"; the renderer translates to
    the standard `---` / `---:` / `:---:` divider tokens.
    """
    sep = {"l": "---", "r": "---:", "c": ":---:"}
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(sep[a] for a in aligns) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return out


# ---- per-section renderers ----------------------------------------------
# Each appends to `lines` and ends with an empty separator line so callers
# can compose sections without worrying about spacing.

def _sec_header(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    add("# 리스크관리 종합 리포트")
    add("")
    add(f"- 생성일: {date.today().isoformat()}")
    add(f"- 시드(재현성): {result.meta.get('seed')}")
    add(f"- 준거: Basel III (CRE/MAR/OPE/LEV) + 금감원 은행업감독업무시행세칙")
    add("")


def _sec_verdict(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    v = result.validation
    verdict = "결재 가능 (PASS)" if v.passes() else "결재 불가 (FAIL 존재)"
    add("## 0. 종합 판정")
    add("")
    add(f"**{verdict}** — 검증 체크 결과: {v.summary()}")
    add("")


def _sec_portfolio(lines: list[str], result: PipelineResult) -> None:
    lines.append("## 1. 포트폴리오 개요")
    lines.append("")
    rows = [
        [row["asset_class"], str(int(row["n"])), _won(row["ead"]),
         f"{row['default_rate']:.2%}"]
        for _, row in result.portfolio_summary.iterrows()
    ]
    lines.extend(_md_table(
        ["자산군", "건수", "EAD", "부도율"], ["l", "r", "r", "r"], rows))
    lines.append("")


def _sec_pd(lines: list[str], result: PipelineResult) -> None:
    lines.append("## 2. 신용평가모형(PD) 변별력")
    lines.append("")
    rows = [
        [seg, f"{m['gini']:.3f}", f"{m['ks']:.3f}",
         f"{int(m['n_train'])}/{int(m['n_test'])}"]
        for seg, m in result.pd_metrics.items()
    ]
    lines.extend(_md_table(
        ["세그먼트", "Gini", "KS", "학습/검증"], ["l", "r", "r", "r"], rows))
    lines.append("")


def _sec_rwa(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    rwa = result.rwa
    of = rwa["output_floor"]
    add("## 3. 위험가중자산(RWA)")
    add("")
    rows = [
        ["신용 RWA (SA)", _won(rwa["sa"])],
        ["신용 RWA (IRB)", _won(rwa["irb"])],
        ["거래상대방신용리스크 RWA (CCR·CVA)", _won(rwa.get("ccr", 0.0))],
        ["집합투자증권 RWA (CIS)", _won(rwa.get("fund", 0.0))],
        ["유동화 RWA", _won(rwa.get("securitisation", 0.0))],
        ["시장리스크 RWA", _won(rwa["market"])],
        ["운영리스크 RWA", _won(rwa["op"])],
        ["내부모형 합계", _won(rwa["internal_total"])],
        ["전부표준방법 합계", _won(rwa["standardised_total"])],
        [f"Output floor ({of.floor:.1%}) 적용액", _won(of.floor_amount)],
        ["**최종 RWA**", f"**{_won(rwa['final_total'])}**"],
    ]
    lines.extend(_md_table(["구분", "금액"], ["l", "r"], rows))
    add("")
    if of.is_binding:
        add(f"> Output floor가 **구속적**입니다. 내부모형 대비 +{_won(of.add_on)} 가산.")
    else:
        add("> Output floor는 비구속적 (내부모형 RWA가 하한 초과).")
    add("")


def _sec_bis(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    bis = result.bis
    add("## 4. BIS 자본적정성")
    add("")
    rows = []
    for key, label in [("cet1", "CET1"), ("tier1", "Tier1"), ("total", "Total")]:
        actual = getattr(bis, f"{key}_ratio")
        rows.append([label, f"{actual:.2%}", f"{bis.required[key]:.2%}",
                     f"{bis.surplus_shortfall[key]:+.2%}"])
    lines.extend(_md_table(
        ["비율", "실측", "요구", "잉여/부족"],
        ["l", "r", "r", "r"], rows))
    add("")
    add(f"판정: **{'PASS' if bis.passes() else 'FAIL'}**")
    add("")


def _sec_leverage(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    lev = result.leverage
    add("## 5. 레버리지비율")
    add("")
    add(f"- 레버리지비율: **{lev.leverage_ratio:.2%}** "
        f"(요구 {lev.required:.2%}, {'충족' if lev.passes() else '미달'})")
    add(f"- 익스포저 측정치: {_won(lev.exposure_measure)}")
    add("")


def _sec_ecl(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    r = result
    add("## 6. IFRS9 기대신용손실(ECL) 충당금")
    add("")
    add(f"- 총 ECL: **{_won(r.ecl['total'])}**")
    add("")
    rows = [
        [f"Stage {int(stage)}", str(int(row["n"])), _won(row["ead"]),
         _won(row["ecl"]), f"{row['coverage']:.2%}"]
        for stage, row in r.ecl["by_stage"].iterrows()
    ]
    lines.extend(_md_table(
        ["Stage", "건수", "EAD", "ECL", "커버리지"],
        ["l", "r", "r", "r", "r"], rows))
    add("")

    macro = r.macro_ecl
    uplift = macro.weighted_total - r.ecl["total"]
    add("### 6-1. 거시연계 PIT ECL (확률가중, IFRS9 forward-looking)")
    add("")
    add(f"- TTC(시점추정) ECL: {_won(r.ecl['total'])}")
    add(f"- PIT 확률가중 ECL: **{_won(macro.weighted_total)}** "
        f"(forward-looking uplift {uplift:+,.0f})")
    add("")
    rows = [
        [row["scenario"], f"{row['probability']:.0%}", _won(row["ecl"])]
        for _, row in macro.by_scenario.iterrows()
    ]
    lines.extend(_md_table(["시나리오", "확률", "ECL"], ["l", "r", "r"], rows))
    add("")

    mp = r.macro_ecl_path
    wq = mp[mp["scenario"] == "weighted"]
    if not wq.empty:
        qs = list(wq["quarter"])
        add(f"### 6-2. 분기별 ECL 충당금 경로 ({qs[0]}~{qs[-1]}, IFRS9 forward-looking)")
        add("")
        add("| 시나리오 | " + " | ".join(qs) + " |")
        add("|---|" + "---:|" * len(qs))
        for name in ["baseline", "downside", "severe", "weighted"]:
            g = mp[mp["scenario"] == name]
            if g.empty:
                continue
            label = "확률가중" if name == "weighted" else name
            add(f"| {label} | "
                + " | ".join(f"{v/1e9:,.1f}" for v in g["ecl"]) + " |")
        add("")
        add("> 단위: 십억원. 확률가중 행이 분기별 IFRS9 충당금 추정치.")
        add("")


def _sec_monitoring(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    m = result.monitoring
    add("## 7. 연체율 / 부도율 / 회수율")
    add("")
    add(f"- 연간 부도율 (노출액 가중): **{m['default_rate_ew']:.2%}**")
    add(f"- 연간 부도율 (건수): {m['default_rate_count']:.2%}")
    add(f"- 누적 회수율: **{m['recovery_rate']:.2%}**")
    add("")


def _sec_limits(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    add("## 8. 한도관리")
    add("")
    if result.limits.empty:
        add("모든 한도 정상 (경보 없음).")
        add("")
        return
    rows = [
        [row["limit"], row["dimension"], str(row["bucket"]),
         _won(row["exposure"]), _won(row["threshold"]),
         f"{row['utilisation']:.1%}", row["severity"]]
        for _, row in result.limits.head(15).iterrows()
    ]
    lines.extend(_md_table(
        ["한도", "차원", "버킷", "노출", "한도", "사용률", "등급"],
        ["l", "l", "l", "r", "r", "r", "l"], rows))
    add("")


def _sec_concentration(lines: list[str], result: PipelineResult) -> None:
    lines.append("## 9. 집중리스크 (HHI)")
    lines.append("")
    rows = [
        [row["dimension"], str(int(row["n_buckets"])),
         f"{row['hhi']:.4f}", f"{row['normalised_hhi']:.4f}",
         f"{row['top1_share']:.2%}"]
        for _, row in result.concentration.iterrows()
    ]
    lines.extend(_md_table(
        ["차원", "버킷수", "HHI", "정규화 HHI", "최대비중"],
        ["l", "r", "r", "r", "r"], rows))
    lines.append("")


def _sec_rapm(lines: list[str], result: PipelineResult) -> None:
    lines.append("## 10. RAPM (RAROC)")
    lines.append("")
    rows = [
        [row["asset_class"], str(int(row["n"])), _won(row["ec"]),
         _won(row["el"]), _won(row["revenue"]),
         f"{row['raroc_mean']:.2%}", f"{row['pass_hurdle_pct']:.1%}"]
        for _, row in result.rapm.iterrows()
    ]
    lines.extend(_md_table(
        ["자산군", "건수", "경제자본", "EL", "수익", "평균 RAROC", "Hurdle충족"],
        ["l", "r", "r", "r", "r", "r", "r"], rows))
    lines.append("")


def _sec_stress(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    add("## 11. 스트레스테스트")
    add("")
    rows = [
        [row["scenario"], _won(row["rwa_total"]), _won(row["ecl"]),
         f"{row['cet1_ratio']:.2%}", f"{row['cet1_surplus']:+.2%}",
         "O" if row["passes"] else "X"]
        for _, row in result.stress.iterrows()
    ]
    lines.extend(_md_table(
        ["시나리오", "RWA합계", "ECL", "CET1비율", "CET1잉여", "통과"],
        ["l", "r", "r", "r", "r", "r"], rows))
    add("")

    rev = result.reverse_stress
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

    qs = result.meta.get("quarters", [])
    horizon = f"{qs[0]}~{qs[-1]}" if qs else ""
    add(f"### 11-2. 분기별 자본 스트레스 경로 ({horizon})")
    add("")
    rows = [
        [row["scenario"], f"{row['trough_cet1']:.2%}", row["trough_quarter"],
         f"{row['end_cet1']:.2%}",
         row["first_breach"] if isinstance(row["first_breach"], str) else "-",
         "O" if row["passes_all"] else "X"]
        for _, row in result.stress_path_trough.iterrows()
    ]
    lines.extend(_md_table(
        ["시나리오", "최저 CET1", "최저시점", "기말 CET1", "최초위반", "전구간통과"],
        ["l", "r", "l", "r", "l", "r"], rows))
    add("")
    sev = result.stress_path[result.stress_path["scenario"] == "severely_adverse"]
    if not sev.empty:
        add("심각(severely_adverse) 분기 CET1 추이:")
        add("")
        add("| 분기 | " + " | ".join(sev["quarter"]) + " |")
        add("|---|" + "---:|" * len(sev))
        add("| CET1 | " + " | ".join(f"{v:.2%}" for v in sev["cet1_ratio"]) + " |")
        add("")


def _sec_validation(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    v = result.validation
    add("## 12. 자체검증 (정합성 + 백테스트)")
    add("")
    rows = [[c.name, c.status, c.detail] for c in v.checks]
    lines.extend(_md_table(["체크", "상태", "상세"], ["l", "l", "l"], rows))
    add("")
    hl = result.backtest["hosmer_lemeshow"]
    add(f"- Hosmer-Lemeshow: chi2={hl['chi_square']:.2f}, p={hl['p_value']:.3f} "
        f"({'캘리브레이션 양호' if hl['p_value'] >= 0.05 else '캘리브레이션 주의'})")
    zones = result.backtest["per_grade"]["zone"].value_counts().to_dict()
    add(f"- 등급별 백테스트 존: {zones}")
    add("")


def _sec_icaap(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    ic = result.icaap
    add("## 13. 내부자본 (ICAAP)")
    add("")
    if ic is None:
        add("내부자본 산출 결과 없음.")
        add("")
        return
    add(f"- 가용자본(AFR, 총자본): **{_won(ic.available_capital)}**")
    add(f"- 통합 경제자본(분산 후): **{_won(ic.ec_diversified)}** "
        f"(단순합 {_won(ic.ec_standalone_sum)}, "
        f"분산효과 -{_won(ic.diversification_benefit)})")
    add(f"- 집중리스크 add-on (Pillar 2): {_won(ic.concentration_addon)}")
    add(f"- 사용률: **{ic.utilisation:.1%}** / 잉여 내부자본: {_won(ic.buffer)} "
        f"→ 판정 **{ic.grade}**")
    add("")
    rows = [[row["risk_type"], _won(row["ec"])]
            for _, row in ic.ec_by_type.iterrows()]
    lines.extend(_md_table(["위험유형", "경제자본(EC)"], ["l", "r"], rows))
    add("")


def _sec_alm(lines: list[str], result: PipelineResult) -> None:
    add = lines.append
    alm = result.alm
    add("## 14. ALM (IRRBB / LCR / NSFR)")
    add("")
    if not alm:
        add("ALM 산출 결과 없음.")
        add("")
        return
    bs = alm["balance_sheet"]
    add(f"- 총자산 {_won(bs.total_assets)} = 여신 {_won(bs.loans)} "
        f"+ HQLA {_won(sum(bs.hqla.values()))} + 기타 {_won(bs.other_assets)}")
    add("")

    irrbb = alm["irrbb"]
    add("### 14-1. IRRBB (ΔEVE / ΔNII)")
    add("")
    rows = [[row["scenario"], _won(row["delta_eve"]),
             f"{row['pct_tier1']:+.2%}"]
            for _, row in irrbb.delta_eve.iterrows()]
    lines.extend(_md_table(["시나리오", "ΔEVE", "Tier1 대비"],
                           ["l", "r", "r"], rows))
    add("")
    add(f"- 최대 ΔEVE 감소: **{_won(irrbb.worst_eve_decline)}** "
        f"({irrbb.worst_eve_scenario}, Tier1의 {irrbb.worst_pct_tier1:.2%}) — "
        f"{'**outlier (15% 초과)**' if irrbb.outlier() else 'outlier 기준(15%) 이내'}")
    for _, row in irrbb.delta_nii.iterrows():
        add(f"- ΔNII({row['scenario']}): {_won(row['delta_nii'])}")
    add("")

    lcr = alm["lcr"]
    add("### 14-2. LCR")
    add("")
    add(f"- HQLA(캡 적용 후): {_won(lcr.hqla_total)}")
    add(f"- 30일 순현금유출: {_won(lcr.net_outflow)} "
        f"(총유출 {_won(lcr.gross_outflow)} − 유입(캡) {_won(lcr.inflow_capped)})")
    add(f"- **LCR: {lcr.lcr:.1%}** ({'충족' if lcr.passes() else '미달'}, 기준 100%)")
    add("")

    nsfr = alm["nsfr"]
    add("### 14-3. NSFR")
    add("")
    add(f"- 가용안정자금조달(ASF): {_won(nsfr.asf_total)}")
    add(f"- 필요안정자금조달(RSF): {_won(nsfr.rsf_total)}")
    add(f"- **NSFR: {nsfr.nsfr:.1%}** ({'충족' if nsfr.passes() else '미달'}, 기준 100%)")
    add("")


def _sec_references(lines: list[str], _result: PipelineResult) -> None:
    add = lines.append
    add("## 15. 출처 및 준거")
    add("")
    add("각 수치·기준의 근거 표준 문헌 (모든 상수는 `risk_lib/references.py`에 집약).")
    add("")
    rows = [[section, cite.standard, cite.section, cite.note]
            for section, cite in ALL_CITATIONS]
    lines.extend(_md_table(
        ["리포트 섹션", "표준", "항목", "비고"],
        ["l", "l", "l", "l"], rows))
    add("")


_SECTIONS = (
    _sec_header,
    _sec_verdict,
    _sec_portfolio,
    _sec_pd,
    _sec_rwa,
    _sec_bis,
    _sec_leverage,
    _sec_ecl,
    _sec_monitoring,
    _sec_limits,
    _sec_concentration,
    _sec_rapm,
    _sec_stress,
    _sec_validation,
    _sec_icaap,
    _sec_alm,
    _sec_references,
)


def render_markdown(result: PipelineResult) -> str:
    lines: list[str] = []
    for section in _SECTIONS:
        section(lines, result)
    return "\n".join(lines)
