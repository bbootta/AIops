"""계층형 HTML 검증 보고서 팩 (요약 + 부문별 상세 + 심화).

산출 구조 (모두 self-contained HTML, inline SVG 시각화, 외부 호출 없음):

    <out_dir>/
    ├── index.html                  # 요약 보고서 (KPI + status 도넛 + 부문 카드)
    ├── credit.html                 # 신용 모형 상세
    ├── credit_calibration.html     #   └ 심화: 등급별 캘리브레이션
    ├── capital_icaap.html          # 자본적정성 + 내부자본(ICAAP) 상세
    ├── alm.html                    # ALM 상세 (LCR/NSFR/만기갭/조달/예대율/IRRBB)
    ├── alm_gap.html                #   └ 심화: 만기 bucket 누적 갭
    ├── alm_irrbb.html              #   └ 심화: IRRBB 시나리오별 ΔEVE
    ├── market_ops.html             # 시장/운영/CVA/CCR 상세
    ├── concentration.html          # 신용집중 상세
    └── data_quality.html           # 데이터 품질 (2.x step) 상세

모든 페이지에 DRAFT 워터마크가 강제된다 (외부 제출 금지).

사용:
    python -m tools.report_pack --n 100000 --out reports/pack_normal
    python -m tools.report_pack --n 100000 --stress --out reports/pack_stress
"""

from __future__ import annotations

import argparse
import html as _html
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.explainability import narrate, render_attribution_block
from tools.svg_charts import (
    PALETTE,
    gauge,
    hbar,
    heatmap,
    kpi_card_strip,
    status_donut,
    trend_line,
)

DRAFT_BANNER = (
    '<div class="draft">[DRAFT — 외부 제출 금지] 본 보고서는 합성 데이터 기반 '
    "검증 보조 자료입니다. 최종 판단은 인간 검증자 책임.</div>"
)

_CSS = """
body { font-family: -apple-system, "Malgun Gothic", sans-serif; margin: 2rem;
       max-width: 920px; color: #212529; }
.draft { background: #fff3cd; border: 1px solid #ffc107; padding: .6rem 1rem;
         font-weight: 600; margin-bottom: 1rem; }
table { border-collapse: collapse; margin: .8rem 0; }
th, td { border: 1px solid #dee2e6; padding: .35rem .6rem; text-align: left;
         font-size: .9rem; }
th { background: #f8f9fa; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; }
.card { border: 1px solid #dee2e6; border-radius: 8px; padding: .8rem 1rem;
        width: 260px; }
.card h3 { margin: .2rem 0 .5rem; font-size: 1rem; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 10px;
         color: #fff; font-size: .8rem; }
code { background: #f0f0f0; padding: 1px 4px; border-radius: 3px; }
footer { margin-top: 2rem; color: #6c757d; font-size: .8rem; }
a { color: #1565c0; }
.crumb { font-size: .85rem; margin-bottom: .6rem; }
details.prov { border: 1px solid #cfd8dc; background: #f6f9fc; padding: .4rem .8rem;
               border-radius: 6px; margin: 1rem 0; font-size: .9rem; }
details.prov summary { cursor: pointer; padding: .2rem 0; }
details.prov table { width: 100%; font-size: .85rem; }
"""

_STATUS_KO = {"ok": "정상", "warning": "주의", "fail": "위반", "skipped": "생략",
              "simulated": "시뮬레이션"}


def _esc(s: object) -> str:
    return _html.escape(str(s))


def _badge(status: str) -> str:
    return (f'<span class="badge" style="background:{PALETTE.get(status, "#888")}">'
            f"{_esc(status)} · {_STATUS_KO.get(status, status)}</span>")


def _page(
    title: str,
    body: str,
    *,
    crumb: bool = True,
    provenance_card: str = "",
) -> str:
    nav = '<div class="crumb"><a href="index.html">← 요약 보고서</a></div>' if crumb else ""
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>{_esc(title)}</title>
<style>{_CSS}</style></head><body>
{DRAFT_BANNER}
{nav}<h1>{_esc(title)}</h1>
{body}
{provenance_card}
<footer>생성: tools/report_pack.py — 합성 데이터 / 외부 호출 없음.
본 보고서는 검증 보조 산출물 초안이며 최종 검증 의견과 외부 제출은 인간
검증자의 검토와 승인을 거쳐야 합니다.</footer>
</body></html>"""


def _render_provenance_card(prov: dict | None) -> str:
    """모든 페이지에 동일 삽입되는 재현가능성 카드."""
    if not prov:
        return ""
    inputs = prov["inputs"]
    fp = inputs.get("fingerprint", {})
    df = fp.get("df") or {}
    pv = prov["policy_versions"]
    git = prov["git"]
    runtime = prov["runtime"]
    pv_rows = "".join(
        f"<tr><td><code>{_esc(k)}</code></td><td>{_esc(v)}</td></tr>"
        for k, v in pv.items())
    return f"""
<details class="prov" open>
<summary><b>재현가능성 (Reproducibility)</b> — 입력 해시 · 정책 버전 · git rev</summary>
<table>
<tr><th>생성 (UTC)</th><td>{_esc(prov['generated_at_utc'])}</td></tr>
<tr><th>입력 n / seed / stress</th>
    <td>n={inputs['n']:,} · seed={inputs['seed']} · stress={inputs['stress']}</td></tr>
<tr><th>입력 df 지문 (shape / SHA-256)</th>
    <td>{df.get('shape', '-')} / <code>{_esc((df.get('sha256') or '-')[:16])}…</code></td></tr>
<tr><th>입력 스칼라 SHA-256</th>
    <td><code>{_esc(fp.get('scalar_sha256', '-')[:16])}…</code></td></tr>
<tr><th>git</th>
    <td>branch <code>{_esc(git['branch'])}</code> · rev <code>{_esc(git['rev'])}</code>
        · dirty={_esc(git['dirty'])}</td></tr>
<tr><th>runtime</th>
    <td>Python {_esc(runtime['python'])} · pandas {_esc(runtime.get('pandas','?'))}
        · numpy {_esc(runtime.get('numpy','?'))}</td></tr>
<tr><th>재실행 명령</th><td><code>{_esc(prov['reproduce'])}</code></td></tr>
</table>
<h4 style="margin:.4rem 0">정책 SSoT 버전 (산출 결과에 직접 영향)</h4>
<table style="font-size:.85rem">
<tr><th>policy</th><th>version</th></tr>
{pv_rows}
</table>
</details>"""


def _kv_table(rows: list[tuple[str, Any]]) -> str:
    body = "".join(f"<tr><th>{_esc(k)}</th><td>{v}</td></tr>" for k, v in rows)
    return f"<table>{body}</table>"


def _step_row(demo: dict, sid: str) -> dict:
    return demo["results"].get(sid, {"status": "skipped", "outputs": {}, "detail": "미실행"})


# ---------------- 부문별 상세 페이지 ----------------

def _credit_pages(demo: dict, request: dict) -> dict[str, str]:
    disc = _step_row(demo, "3.disc")
    psi = _step_row(demo, "3.psi")
    cal = _step_row(demo, "3.cal")
    o = disc["outputs"]
    charts = hbar(
        [("KS", o.get("ks", 0)), ("AUROC", o.get("auc", 0)), ("Gini", o.get("gini", 0))],
        vline=0.30, vline_label="KS 참고임계 0.30",
        title="변별력 지표", fmt="{:.4f}",
        colors=[PALETTE["ok" if o.get("ks", 0) >= 0.30 else "fail"],
                PALETTE["ok" if o.get("auc", 0) >= 0.70 else "fail"],
                PALETTE["neutral"]])
    psi_g = gauge(psi["outputs"].get("psi", 0.0), minimum=0.25, warning=0.10,
                  vmax=0.5, label="PSI (dev↔oot)", fmt="{:.4f}",
                  higher_is_better=False)
    body = f"""
<p>{_badge(disc['status'])} 변별력 / {_badge(psi['status'])} 안정성 /
{_badge(cal['status'])} 캘리브레이션</p>
<p>{narrate("3.disc", disc)}</p>
{charts}
<h2>안정성 (PSI)</h2>{psi_g}
<p>{narrate("3.psi", psi)}</p>
<p>기준: &lt; 0.10 안정 · 0.10~0.25 주의 · ≥ 0.25 불안정 (참고 임계).</p>
<h2>캘리브레이션 요약</h2>
<p>{narrate("3.cal", cal)}</p>
{_kv_table([("등급 수", cal['outputs'].get('n_grades', '-')),
            ("reject 등급 수 (binomial, Holm)", cal['outputs'].get('n_reject', '-')),
            ("등급 심화", '<a href="credit_calibration.html">등급별 심화 보고서 →</a>'),
            ("세그먼트별 변별력", '<a href="credit_segments.html">세그먼트별 + ROC + 분포 →</a>'),
            ("Vintage 분석", '<a href="credit_vintage.html">cohort별 부도율 →</a>'),
            ("챌린저 비교", '<a href="challenger.html">챔피언 vs 챌린저 →</a>')])}
<h2>표본 적정성</h2>
{_kv_table([("표본 수", f"{demo['n_rows']:,}"),
            ("판정", _step_row(demo, '2.sample')['detail'])])}
{render_attribution_block("3.disc")}
{render_attribution_block("3.psi")}
{render_attribution_block("3.cal")}
"""
    pages = {"credit.html": _page("신용평가모형 상세 보고서", body)}

    # 심화: 등급별 캘리브레이션 재산출
    deep = "<p>입력 df 미제공 — 심화 분석 불가.</p>"
    df = request.get("df")
    if df is not None and request.get("grade_col"):
        from tools.binomial_calibration import calibration_test_per_grade

        grades_input = []
        for grade, sub in df.groupby(request["grade_col"]):
            grades_input.append({
                "grade": grade,
                "pd_estimated": float(sub[request["pd_col"]].mean()),
                "default_count": int(sub[request["target_col"]].sum()),
                "exposure_count": int(len(sub)),
            })
        res = calibration_test_per_grade(grades_input, alpha=0.05, multitest="holm")
        rows = "".join(
            f"<tr><td>{_esc(r.grade)}</td><td>{r.pd_estimated:.4%}</td>"
            f"<td>{r.observed_rate:.4%}</td><td>{int(r.default_count):,}</td>"
            f"<td>{int(r.exposure_count):,}</td><td>{r.p_value_adj:.4f}</td>"
            f"<td>{'<b style=color:#c62828>reject</b>' if r.reject else 'ok'}</td></tr>"
            for r in res.itertuples())
        chart = hbar(
            [(str(r.grade), float(r.observed_rate - r.pd_estimated))
             for r in res.itertuples()],
            title="등급별 (실측 부도율 − 추정 PD)", fmt="{:+.4%}",
            colors=[PALETTE["fail"] if r.reject else PALETTE["ok"]
                    for r in res.itertuples()])
        deep = f"""
<p>등급별 추정 PD 대비 실측 부도율의 binomial 검정 (α=0.05, Holm 보정).</p>
{chart}
<table><tr><th>등급</th><th>추정 PD</th><th>실측 부도율</th><th>부도</th>
<th>건수</th><th>p (adj)</th><th>판정</th></tr>{rows}</table>
<p>reject 등급은 추정 PD 와 실측이 통계적으로 불일치 — 재캘리브레이션 검토
대상이며, 인간 검증자의 등급별 원인 분석이 필요합니다.</p>
"""
    pages["credit_calibration.html"] = _page("심화 — 등급별 캘리브레이션", deep)
    return pages


def _capital_icaap_page(demo: dict) -> str:
    cap = _step_row(demo, "3.capital")
    icaap = _step_row(demo, "3.icaap")
    co = cap["outputs"]
    parts = [f"<p>{_badge(cap['status'])} 규제자본 / {_badge(icaap['status'])} 내부자본(ICAAP)</p>",
             "<h2>규제자본 (Pillar 1 + buffer)</h2>"]
    ratios = co.get("ratios", {})
    lev = co.get("leverage", {})
    if lev:
        parts.append(gauge(lev.get("ratio", 0), minimum=lev.get("minimum", 0.03),
                           vmax=0.08, label="레버리지비율", fmt="{:.2%}"))
    if ratios:
        parts.append(_kv_table([
            ("CET1 요구 (buffer 포함)", f"{ratios.get('cet1_required', 0):.2%}"),
            ("Tier1 요구", f"{ratios.get('tier1_required', 0):.2%}"),
            ("총자본 요구", f"{ratios.get('total_required', 0):.2%}"),
            ("위반", ", ".join(v["metric"] for v in ratios.get("violations", [])) or "없음"),
        ]))
    io = icaap["outputs"]
    parts.append("<h2>내부자본 적정성 (ICAAP / Pillar 2)</h2>")
    if io:
        parts.append(gauge(io.get("ratio", 0), minimum=1.0, warning=1.2, vmax=2.0,
                           label="내부자본비율 (가용/필요)"))
        if io.get("post_stress_ratio") is not None:
            parts.append(gauge(io["post_stress_ratio"], minimum=1.0, warning=1.05,
                               vmax=2.0, label="스트레스 후 비율"))
        shares = io.get("risk_shares", {})
        if shares:
            parts.append(hbar(
                [(k, v) for k, v in sorted(shares.items(), key=lambda x: -x[1])],
                title="필요내부자본 리스크 구성", fmt="{:.1%}",
                vline=0.60, vline_label="단일리스크 경고 60%"))
        findings = io.get("findings", [])
        parts.append(_kv_table([
            ("필요내부자본 합계 (분산효과 차감 후)", f"{io.get('required_total', 0):,.0f}"),
            ("누락 리스크 유형", ", ".join(io.get("missing_risk_types", [])) or "없음"),
            ("발견 사항", "<br>".join(_esc(f) for f in findings) or "없음"),
        ]))
    else:
        parts.append("<p>ICAAP 입력 미제공.</p>")
    parts.append('<h2>심화 분석 (Drill-down)</h2>')
    parts.append('<ul>'
                 '<li><a href="capital_buffer_deep.html">자본 buffer 분해 + sensitivity →</a></li>'
                 '<li><a href="capital_rwa_deep.html">RWA 분해 + Output Floor + SREP →</a></li>'
                 '<li><a href="icaap_deep.html">ICAAP 리스크 유형 분해 + 시나리오 →</a></li>'
                 '</ul>')
    parts.append('<h2>왜 이 결과인가 (Explainability)</h2>')
    parts.append(f"<p>{narrate('3.capital', cap)}</p>")
    parts.append(f"<p>{narrate('3.icaap', icaap)}</p>")
    parts.append(render_attribution_block("3.capital"))
    parts.append(render_attribution_block("3.icaap"))
    return _page("자본적정성 + 내부자본(ICAAP) 상세 보고서", "".join(parts))


def _alm_pages(demo: dict, request: dict) -> dict[str, str]:
    liq = _step_row(demo, "3.liquidity")
    alm = _step_row(demo, "3.alm")
    irrbb = _step_row(demo, "3.irrbb")
    lo, ao = liq["outputs"], alm["outputs"]

    parts = [f"<p>{_badge(liq['status'])} 유동성 규제비율 / {_badge(alm['status'])} "
             f"ALM 관리지표 / {_badge(irrbb['status'])} IRRBB</p>",
             "<h2>유동성 규제비율</h2>"]
    if lo.get("lcr"):
        c = lo["lcr"]
        parts.append(gauge(c["ratio"], minimum=c["min_required"],
                           warning=c["warning_threshold"], vmax=2.0, label="LCR"))
    if lo.get("nsfr"):
        c = lo["nsfr"]
        parts.append(gauge(c["ratio"], minimum=c["min_required"],
                           warning=c["warning_threshold"], vmax=2.0, label="NSFR"))
    if not lo:
        parts.append("<p>LCR/NSFR 입력 미제공.</p>")

    parts.append("<h2>만기 갭</h2>")
    mg = ao.get("maturity_gap")
    if mg:
        cum = mg["cumulative"]
        parts.append(hbar(
            [(b, v["cumulative_ratio"]) for b, v in cum.items()],
            title="누적 만기갭 / 총자산", fmt="{:+.1%}",
            vline=mg["limit"], vline_label=f"한도 {mg['limit']:.0%}",
            colors=[PALETTE["fail"] if v["cumulative_ratio"] < mg["limit"]
                    else PALETTE["warning"] if v["cumulative_ratio"] < mg["warning"]
                    else PALETTE["ok"] for v in cum.values()]))
        parts.append(f'<p>worst: {mg["worst_ratio"]:+.1%} @ {mg["worst_bucket"]} '
                     f'({mg["level"]}) — <a href="alm_gap.html">bucket 심화 →</a></p>')
    else:
        parts.append("<p>만기 갭 입력 미제공.</p>")

    parts.append("<h2>자금조달 집중 / 예대율</h2>")
    rows: list[tuple[str, Any]] = []
    fc = ao.get("funding_concentration")
    if fc:
        rows += [("조달 top1 비중", f"{fc['top1_share']:.1%} ({fc['level']})"),
                 ("조달 top10 비중", f"{fc['top10_share']:.1%}"),
                 ("조달처 수", fc["n_providers"])]
    ltd = ao.get("loan_to_deposit")
    if ltd:
        rows.append(("원화 예대율 (≤ 100%)", f"{ltd['ratio']:.1%} ({ltd['level']})"))
    parts.append(_kv_table(rows) if rows else "<p>입력 미제공.</p>")

    parts.append("<h2>IRRBB (금리리스크)</h2>")
    if irrbb["outputs"]:
        io = irrbb["outputs"]
        parts.append(_kv_table([
            ("ΔEVE/Tier1 (worst)", f"{io.get('ratio', 0):.1%}"),
            ("outlier (기준 15%)", "예" if io.get("outlier") else "아니오"),
            ("worst 시나리오", io.get("worst", "-")),
            ("시나리오 심화", '<a href="alm_irrbb.html">시나리오별 ΔEVE →</a>'),
            ("통화/NII 심화", '<a href="alm_currency_deep.html">통화별 LCR + ΔNII + 일중유동성 →</a>'),
            ("Behavioral 가정", '<a href="irrbb_behavioral.html">NMD/Prepayment/Duration gap →</a>'),
        ]))
    else:
        parts.append("<p>IRRBB 입력 미제공.</p>")
    parts.append('<h2>왜 이 결과인가 (Explainability)</h2>')
    parts.append(f"<p>{narrate('3.liquidity', liq)}</p>")
    parts.append(f"<p>{narrate('3.alm', alm)}</p>")
    parts.append(f"<p>{narrate('3.irrbb', irrbb)}</p>")
    parts.append(render_attribution_block("3.liquidity"))
    parts.append(render_attribution_block("3.alm"))
    parts.append(render_attribution_block("3.irrbb"))
    pages = {"alm.html": _page("ALM 상세 보고서 (유동성 · 만기갭 · 조달 · IRRBB)",
                               "".join(parts))}

    # 심화: 만기 bucket 갭
    deep = "<p>만기 갭 입력 미제공.</p>"
    if mg:
        rows = "".join(
            f"<tr><td>{_esc(b)}</td><td>{v['gap']:+,.0f}</td>"
            f"<td>{v['cumulative_gap']:+,.0f}</td><td>{v['cumulative_ratio']:+.2%}</td></tr>"
            for b, v in mg["cumulative"].items())
        deep = f"""
{hbar([(b, v["gap"]) for b, v in mg["cumulative"].items()],
      title="bucket 별 갭 (자산 − 부채)", fmt="{:+,.0f}")}
<table><tr><th>Bucket</th><th>갭</th><th>누적 갭</th><th>누적/총자산</th></tr>{rows}</table>
<p>해석: 단기 bucket 의 음(−) 갭은 부채 만기 도래 초과 — 차환 위험.
한도 {mg['limit']:.0%} / 경고 {mg['warning']:.0%} (SSoT:
<code>harness/alm_thresholds.json</code>).</p>
"""
    pages["alm_gap.html"] = _page("심화 — 만기 bucket 누적 갭", deep)

    # 심화: IRRBB 시나리오
    deep2 = "<p>IRRBB 시나리오 입력 미제공.</p>"
    scen = request.get("irrbb_delta_eve_by_scenario")
    tier1 = request.get("irrbb_tier1")
    if scen and tier1:
        deep2 = f"""
{hbar([(k, v / float(tier1)) for k, v in scen.items()],
      title="시나리오별 ΔEVE / Tier1", fmt="{:+.1%}",
      vline=-0.15, vline_label="outlier 기준 −15%",
      colors=[PALETTE["fail"] if v / float(tier1) < -0.15 else PALETTE["ok"]
              for v in scen.values()])}
<p>Basel SRP31 표준 6개 금리 시나리오. ΔEVE 손실이 Tier1 의 15% 를 초과하면
outlier bank 로 분류되어 감독 대응이 요구됩니다 (SSoT:
<code>harness/irrbb_thresholds.json</code>).</p>
"""
    pages["alm_irrbb.html"] = _page("심화 — IRRBB 시나리오별 ΔEVE", deep2)
    return pages


def _market_ops_page(demo: dict) -> str:
    mkt = _step_row(demo, "3.market")
    op = _step_row(demo, "3.operational")
    cva = _step_row(demo, "3.cva")
    ccr = _step_row(demo, "3.ccr")
    zone = mkt["outputs"].get("zone", "-")
    zone_color = {"green": "ok", "yellow": "warning", "red": "fail"}.get(zone, "skipped")
    body = f"""
<p>{_badge(mkt['status'])} 시장 / {_badge(op['status'])} 운영 /
{_badge(cva['status'])} CVA / {_badge(ccr['status'])} CCR</p>
<h2>시장리스크 — VaR Backtest (Traffic Light)</h2>
{_kv_table([("Zone", f'<span class="badge" style="background:{PALETTE[zone_color]}">{_esc(zone)}</span>'),
            ("예외 건수 (250일)", mkt['outputs'].get('exceptions', '-')),
            ("기준", "green ≤ 4 · yellow 5~9 · red ≥ 10 (MAR99)")])}
<h2>운영리스크 — SMA</h2>
{_kv_table([("Business Indicator", f"{op['outputs'].get('bi', 0):,.2f} bn"),
            ("BIC", f"{op['outputs'].get('bic_eur_bn', 0):,.4f} bn"),
            ("ORC (ILM=1, 국내 기준)", f"{op['outputs'].get('orc_eur_bn', 0):,.4f} bn")])}
<h2>CVA</h2>
{_kv_table([("BA-CVA", f"{cva['outputs'].get('ba_cva', 0):,.2f}"),
            ("SA-CVA 적용 대상", "예" if cva['outputs'].get('sa_cva_required') else "아니오")])}
<h2>거래상대방 신용리스크 (SA-CCR)</h2>
{_kv_table([("EAD", f"{ccr['outputs'].get('ead', 0):,.2f}"),
            ("alpha", ccr['outputs'].get('alpha', '-')),
            ("심화", '<a href="ccr_deep.html">SA-CCR EAD 분해 →</a>')])}
<h2>심화 분석 (Drill-down)</h2>
<ul>
<li><a href="market_backtest_deep.html">시장 — VaR backtest P&amp;L 분해 (250일) →</a></li>
<li><a href="market_components_deep.html">시장 — VaR 구성요소 + SVaR + IRC →</a></li>
<li><a href="operational_deep.html">운영 — SMA BI 구성·BIC 구간 →</a></li>
<li><a href="operational_bi_deep.html">운영 — BI 5 component + 10년 ILDC 시계열 →</a></li>
<li><a href="op_scenario_deep.html">운영 — 손실 시나리오 (BCBS 7 event class) →</a></li>
<li><a href="cva_deep.html">CVA — counterparty 분해 →</a></li>
<li><a href="ccr_deep.html">CCR — SA-CCR EAD 분해 (RC + PFE × α) →</a></li>
<li><a href="ccr_netting_deep.html">CCR — Netting set + Wrong-Way Risk + 담보 →</a></li>
</ul>
<h2>왜 이 결과인가 (Explainability)</h2>
<p>{narrate("3.market", mkt)}</p>
<p>{narrate("3.operational", op)}</p>
<p>{narrate("3.cva", cva)}</p>
<p>{narrate("3.ccr", ccr)}</p>
{render_attribution_block("3.market")}
{render_attribution_block("3.operational")}
{render_attribution_block("3.cva")}
{render_attribution_block("3.ccr")}
"""
    return _page("시장 · 운영 · CVA · CCR 상세 보고서", body)


def _concentration_page(demo: dict) -> str:
    conc = _step_row(demo, "3.conc")
    o = conc["outputs"]
    breaches = o.get("breaches", [])
    rows = "".join(
        f"<tr><td>{_esc(b.get('group'))}</td><td>{_esc(b.get('rule'))}</td>"
        f"<td>{_esc(b.get('pct_tier1', b.get('pct_equity', b.get('aggregate', '-'))))}</td></tr>"
        for b in breaches)
    body = f"""
<p>{_badge(conc['status'])}</p>
{gauge(o.get('hhi', 0), minimum=0.18, warning=0.10, vmax=0.3,
       label="HHI 집중도", fmt="{:.4f}", higher_is_better=False)}
<p>band: <b>{_esc(o.get('hhi_band', '-'))}</b> (low &lt; 0.10 · moderate &lt; 0.18 · high ≥ 0.18)</p>
{_kv_table([("거액익스포저 (Tier1 10% 초과)", f"{o.get('n_large', 0)}건"),
            ("한도 위반", f"{o.get('n_breaches', 0)}건")])}
{"<h2>위반 내역</h2><table><tr><th>그룹</th><th>규정</th><th>수치</th></tr>" + rows + "</table>" if breaches else ""}
<p>기준: Basel LEX (Tier1 10% 보고 / 25% 한도) + 은행법 35조 (동일차주
자기자본 25%, 거액합계 자기자본 5배).</p>
<h2>심화 분석</h2>
<ul>
<li><a href="concentration_segments.html">산업/지역/통화별 집중 + Top 10 exposures →</a></li>
</ul>
<h2>왜 이 결과인가 (Explainability)</h2>
<p>{narrate("3.conc", conc)}</p>
{render_attribution_block("3.conc")}
"""
    return _page("신용집중리스크 상세 보고서", body)


def _challenger_page(request: dict) -> str:
    """챔피언 vs 챌린저 모형 변별력 비교 (KS / AUROC / Gini)."""
    df = request.get("df")
    target_col = request.get("target_col", "target")
    if df is None or "score" not in df.columns or "score_challenger" not in df.columns:
        return _page("심화 — 챔피언 vs 챌린저 비교",
                     "<p>챌린저 score 입력 미제공.</p>")

    from tools.metric_ks_auc import calculate_auc_gini, calculate_ks

    y = df[target_col].to_numpy()
    s_champ = df["score"].to_numpy()
    s_chal = df["score_challenger"].to_numpy()

    champ_ks = calculate_ks(y, s_champ)
    champ_ag = calculate_auc_gini(y, s_champ)
    chal_ks = calculate_ks(y, s_chal)
    chal_ag = calculate_auc_gini(y, s_chal)

    delta_ks = chal_ks["ks"] - champ_ks["ks"]
    delta_auc = chal_ag["auc"] - champ_ag["auc"]
    delta_gini = chal_ag["gini"] - champ_ag["gini"]

    rows = [
        ("KS", champ_ks["ks"], chal_ks["ks"], delta_ks),
        ("AUROC", champ_ag["auc"], chal_ag["auc"], delta_auc),
        ("Gini", champ_ag["gini"], chal_ag["gini"], delta_gini),
    ]
    table = "".join(
        f"<tr><td><b>{_esc(metric)}</b></td>"
        f"<td>{champ:.4f}</td><td>{chal:.4f}</td>"
        f"<td style='color:{PALETTE['ok'] if delta > 0 else PALETTE['fail']}'>"
        f"{delta:+.4f}</td></tr>"
        for metric, champ, chal, delta in rows)

    chart = hbar(
        [
            ("KS (Δ)", delta_ks),
            ("AUROC (Δ)", delta_auc),
            ("Gini (Δ)", delta_gini),
        ],
        title="챌린저 − 챔피언 (양수 = 챌린저 우세)",
        fmt="{:+.4f}",
        colors=[PALETTE["ok" if d > 0 else "fail"] for d in
                (delta_ks, delta_auc, delta_gini)])

    # 챌린저 도입 권고 임계 (참고): ΔAUROC > 0.01 안정적
    decision = (
        '<span style="color:#2e7d32"><b>챌린저 우세</b></span> — 도입 검토 대상 (MRMC 보고)'
        if delta_auc > 0.01
        else '<span style="color:#f9a825"><b>유사 수준</b></span> — 표본 변동성 범위. 추가 OOT 분기 비교 후 판단'
        if abs(delta_auc) <= 0.01
        else '<span style="color:#c62828"><b>챔피언 우세</b></span> — 챌린저 미도입 권고')

    body = f"""
<p>본 페이지는 동일 표본·동일 target 에 대해 챔피언(현재 운영) score 와 챌린저
(검토) score 의 변별력을 직접 비교한다. n = {len(df):,}.</p>
<table>
<tr><th>지표</th><th>챔피언</th><th>챌린저</th><th>Δ (챌린저 − 챔피언)</th></tr>
{table}
</table>
{chart}
<h2>결론</h2>
<p>{decision}</p>
<h2>해석 가이드 (MRMC 관점)</h2>
<ul>
<li><b>ΔAUROC &gt; 0.01</b>: 챌린저가 안정적으로 우세 — 챔피언 교체 또는 ensemble
검토. 운영 적용 전 OOT panel × 4분기 + 안정성 추세 검증 필요.</li>
<li><b>−0.01 ≤ ΔAUROC ≤ 0.01</b>: 표본 변동성 범위. 챌린저 도입 보류, 다음
검증 cycle 까지 모니터링.</li>
<li><b>ΔAUROC &lt; −0.01</b>: 챌린저 미도입. 챔피언 모형 유지.</li>
<li>본 점검은 자동 점검 한정 — 최종 운영 적용은 MRMC 검토 + 인간 검증자 +
감독원 사전 협의 영역 (CLAUDE.md §5, §7).</li>
</ul>
<h2>관련 정책 SSoT</h2>
<ul>
<li><code>skills/challenger_model_review.md</code> — 챌린저 모형 검토 절차
스킬셋.</li>
<li><code>harness/explainability_attributions.json</code> — KS/AUROC 임계
출처.</li>
</ul>
<p><a href="credit.html">← 신용평가모형 상세로 돌아가기</a></p>
"""
    return _page("심화 — 챔피언 vs 챌린저 비교", body)


def _cva_deep_page(request: dict) -> str:
    """CVA counterparty 분해 — BA-CVA 산식 + counterparty별 sCVA."""
    cps = request.get("cva_counterparty_inputs") or []
    if not cps:
        return _page("심화 — CVA counterparty 분해",
                     "<p>CVA counterparty 입력 미제공.</p>")

    # 정렬 (sCVA 큰 순)
    sorted_cps = sorted(cps, key=lambda r: -float(r.get("scva", 0)))
    top_n = min(15, len(sorted_cps))

    rows = "".join(
        f"<tr><td><code>{_esc(c['name'])}</code></td>"
        f"<td>{float(c['scva']):.4f}</td>"
        f"<td>{float(c['scva']) / sum(float(x['scva']) for x in cps):.2%}</td></tr>"
        for c in sorted_cps[:top_n])

    chart = hbar(
        [(c["name"], float(c["scva"])) for c in sorted_cps[:top_n]],
        title=f"Top {top_n} counterparty — sCVA", fmt="{:.2f}")

    # BA-CVA 합계
    total_scva = sum(float(c["scva"]) for c in cps)
    book_size = float(request.get("cva_trading_book_size_eur_bn", 0))
    sa_threshold = 100.0  # bn EUR — BCBS MAR50

    body = f"""
<p>CVA(Credit Valuation Adjustment) 의 counterparty 별 분해. BCBS MAR50.</p>

<h2>BA-CVA 산식 (단순화)</h2>
<table>
<tr><th>요소</th><th>값</th></tr>
<tr><th>n_counterparties</th><td>{len(cps)}</td></tr>
<tr><th>Σ sCVA (counterparty 별 CVA 합계)</th><td>{total_scva:.4f}</td></tr>
<tr><th>BA-CVA (단순 합)</th><td>{total_scva:.4f}</td></tr>
<tr><th>트레이딩북 규모 (bn EUR)</th><td>{book_size:,.1f}</td></tr>
<tr><th>SA-CVA 적용 임계 (BCBS MAR50)</th><td>{sa_threshold:.0f} bn</td></tr>
<tr><th>SA-CVA 적용 여부</th><td>
{'<b style=color:#c62828>적용 대상 — 모형 승인 절차 필요</b>' if book_size >= sa_threshold else '미적용 (BA-CVA 만)'}
</td></tr>
</table>

{chart}

<h2>Top {top_n} counterparty</h2>
<table>
<tr><th>Counterparty</th><th>sCVA</th><th>전체 대비 비중</th></tr>
{rows}
</table>

<h2>해석 (검증 관점)</h2>
<ul>
<li><b>BA-CVA (Basic Approach)</b>: counterparty 별 sCVA 의 단순 합. hedging
benefit 반영 가능 (BCBS MAR50 §51).</li>
<li><b>SA-CVA (Standardised Approach)</b>: 트레이딩북 100bn EUR 초과 시 모형
승인 후 적용. delta · vega · curvature risk 분해.</li>
<li><b>Wrong-Way Risk</b>: 거래상대방 신용도 악화와 시장가 손실이 동시 발생하는
구조 — 별도 식별 + α 조정. 본 자동 점검 범위 밖.</li>
<li>본 집계는 합성 input 이며 운영 적용은 트레이딩 시스템 + 모형 위원회 검토
필요.</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로 돌아가기</a></p>
"""
    return _page("심화 — CVA counterparty 분해 (BA-CVA / SA-CVA)", body)


def _market_backtest_deep_page(demo: dict) -> str:
    """VaR backtest P&L 분해 — 250일 panel + 예외 일자 표시."""
    from tools.sample_generators import market_var_pnl_panel

    mkt = _step_row(demo, "3.market")
    panel = market_var_pnl_panel()
    exceptions = [r for r in panel if r["exception"]]
    n_exc = len(exceptions)
    var_99 = panel[0]["var_99"]

    chart = trend_line(
        [(str(r["day"]), r["pnl"]) for r in panel[::5]],  # 5일 간격 sampling
        title="P&L (5일 간격, 빨간 점선 = 99% VaR)", fmt="{:+.2f}",
        minimum=var_99)

    exc_rows = "".join(
        f"<tr><td>D+{r['day']}</td><td>{r['pnl']:+.4f}</td>"
        f"<td>{r['var_99']:.2f}</td>"
        f"<td>{r['pnl'] - r['var_99']:+.4f}</td></tr>"
        for r in exceptions)

    zone = ("green" if n_exc <= 4 else "yellow" if n_exc <= 9 else "red")
    zone_color = {"green": PALETTE["ok"], "yellow": PALETTE["warning"],
                  "red": PALETTE["fail"]}[zone]

    body = f"""
<p>VaR backtest (BCBS MAR99) — 250 영업일 P&L 시계열에서 실현손실이 사전
99% VaR 한도를 초과한 일자 수. 합성 panel 기반 시연.</p>

<h2>Traffic Light 판정</h2>
<table>
<tr><th>예외 건수</th><td>{n_exc} / 250</td></tr>
<tr><th>Zone</th>
<td><span class="badge" style="background:{zone_color}">{zone.upper()}</span></td></tr>
<tr><th>기준 (BCBS MAR99)</th>
<td>green ≤ 4 · yellow 5 ~ 9 · red ≥ 10</td></tr>
<tr><th>handler 결과</th>
<td>{_esc(mkt.get('detail', '-'))}</td></tr>
</table>

{chart}

<h2>예외 일자 분해 ({n_exc} 건)</h2>
<table>
<tr><th>일자</th><th>실현 P&L</th><th>VaR_99</th><th>초과 (PnL − VaR)</th></tr>
{exc_rows or "<tr><td colspan='4'>예외 없음</td></tr>"}
</table>

<h2>해석 (시장리스크 검증)</h2>
<ul>
<li><b>yellow zone (5~9)</b>: 모형 multiplier 가산 (기본 3.0 → 최대 4.0,
BCBS MAR99 §32.9). 원인 분석 보고.</li>
<li><b>red zone (≥10)</b>: 모형 부적합 — 즉시 재검증 + 한도 일시 축소.</li>
<li><b>clustered exceptions</b>: 시간적 군집(예: 5일 내 3건 이상) 발견 시
모형 분포 가정 (정규) 부적합 신호 — SVaR + ES 보완 검토.</li>
<li>본 panel 은 합성 — 운영 backtest 는 일별 실현 P&L + 사전 VaR 한도 dataset
가 trader-level 로 산정되어야 한다.</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로 돌아가기</a></p>
"""
    return _page("심화 — 시장 VaR Backtest P&L 분해 (250일)", body)


def _op_scenario_deep_page() -> str:
    """운영리스크 손실 시나리오 표 — BCBS 7 event class 매핑."""
    from tools.sample_generators import operational_loss_scenarios

    scenarios = operational_loss_scenarios()
    rows = "".join(
        f"<tr><td>{_esc(s['scenario'])}</td>"
        f"<td><code>{_esc(s['basel_event_class'])}</code></td>"
        f"<td>{s['frequency_per_year']:.1f}</td>"
        f"<td>{s['severity_mean_bn']:,.0f}</td>"
        f"<td>{s['annual_expected_bn']:,.0f}</td>"
        f"<td>{s['severity_99_bn']:,.0f}</td></tr>"
        for s in scenarios)

    chart = hbar(
        [(s["scenario"], s["annual_expected_bn"]) for s in scenarios],
        title="Scenario 별 연간 기대 손실 (bn)", fmt="{:,.0f}",
        colors=[PALETTE["warning"]] * len(scenarios))

    chart_99 = hbar(
        [(s["scenario"], s["severity_99_bn"]) for s in scenarios],
        title="Scenario 별 99% 손실 추정 (lognormal, σ=0.8)", fmt="{:,.0f}",
        colors=[PALETTE["fail"]] * len(scenarios))

    body = f"""
<p>BCBS 7개 손실 event class 매핑 시나리오 — Internal Fraud / External Fraud
/ Business Disruption / Damage to Physical Assets / Clients & Products /
Execution & Process Management / Employment Practices.</p>
<p>본 표는 ILDC (Internal Loss Data Component) 도입 시 가정 input 의 schema
이며, 운영 시스템에서는 자체 10년 loss data 로 대체된다 (감독원 ILM=1 미적용
조건).</p>

{chart}
{chart_99}

<h2>시나리오 표</h2>
<table>
<tr><th>시나리오</th><th>BCBS Event Class</th><th>frequency/yr</th>
<th>severity mean</th><th>연간 기대</th><th>severity 99%</th></tr>
{rows}
</table>

<h2>해석 (운영리스크 검증)</h2>
<ul>
<li><b>국내 기준 ILM = 1</b>: 본 시나리오는 ILDC 도입 시 input 의 schema 시연.
운영 시스템에서는 자체 손실 데이터 (10년) 가 사용되며 ILM ≠ 1.</li>
<li><b>severity 99%</b>: lognormal(σ=0.8) 근사 — 실제 LDA 는 EVT
(extreme value theory) 또는 Mixture 분포 사용.</li>
<li><b>경계 시나리오</b>: rogue trader / 규제 제재 같은 tail 시나리오는
frequency 가 낮아도 severity 가 매우 커서 99% VaR 에 dominate 한다.</li>
<li>본 표는 합성 가정 — 운영 시스템에서는 ORX/internal LDA + 인간 검증자
검토 후 사용.</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로 돌아가기</a></p>
"""
    return _page("심화 — 운영리스크 손실 시나리오", body)


def _ifrs9_fli_page() -> str:
    """IFRS 9 FLI overlay + 시나리오 가중 ECL + management overlay."""
    from tools.sample_generators import ifrs9_fli_overlay_sample

    f = ifrs9_fli_overlay_sample()
    weighted = sum(s["ecl_bn"] * s["weight"] for s in f["scenarios"])
    final_ecl = weighted + f["management_overlay_bn"]

    sc_chart = hbar(
        [(s["name"], float(s["ecl_bn"])) for s in f["scenarios"]],
        title="시나리오별 ECL (가중 전)", fmt="{:,.0f} bn",
        colors=[PALETTE["ok"], PALETTE["warning"], PALETTE["fail"]])

    weight_chart = hbar(
        [(s["name"], float(s["weight"])) for s in f["scenarios"]],
        title="시나리오 가중치", fmt="{:.0%}",
        colors=[PALETTE["ok"], PALETTE["warning"], PALETTE["fail"]])

    waterfall = hbar(
        [
            ("Base ECL (model)", f["base_ecl_bn"]),
            ("Probability-weighted (FLI)", weighted - f["base_ecl_bn"]),
            ("Management overlay (PMA)", f["management_overlay_bn"]),
            ("Final ECL", final_ecl),
        ],
        title="ECL 산정 흐름 (waterfall)", fmt="{:+,.0f} bn",
        colors=[PALETTE["neutral"], PALETTE["warning"],
                PALETTE["warning"], PALETTE["fail"]])

    sc_rows = "".join(
        f"<tr><td>{_esc(s['name'])}</td><td>{s['weight']:.0%}</td>"
        f"<td>{s['gdp_growth']:+.1%}</td><td>{s['unemployment']:.1%}</td>"
        f"<td>{s['ecl_bn']:,.0f}</td>"
        f"<td>{s['ecl_bn']*s['weight']:,.0f}</td></tr>"
        for s in f["scenarios"])
    overlay_rows = "".join(f"<li>{_esc(r)}</li>" for r in f["overlay_rationale"])

    body = f"""
<p>IFRS 9 Forward-Looking Information (FLI) — 시나리오 가중평균 ECL +
management overlay (PMA: Post-Model Adjustment). 출처: {_esc(f['framework'])}.</p>

<h2>시나리오 가중치</h2>
{weight_chart}

<h2>시나리오별 ECL</h2>
{sc_chart}
<table>
<tr><th>시나리오</th><th>가중치</th><th>GDP</th><th>실업</th><th>ECL (bn)</th><th>가중 ECL</th></tr>
{sc_rows}
<tr><th colspan="5">Probability-weighted</th><th>{weighted:,.0f}</th></tr>
</table>

<h2>ECL 산정 흐름</h2>
{waterfall}
<table>
<tr><th>Base ECL (Stage 1/2/3 합계)</th><td>{f['base_ecl_bn']:,.2f} bn</td></tr>
<tr><th>+ Probability-weighted Δ</th><td>{weighted - f['base_ecl_bn']:+,.2f} bn</td></tr>
<tr><th>+ Management Overlay (PMA)</th><td>{f['management_overlay_bn']:+,.2f} bn</td></tr>
<tr><th><b>Final ECL</b></th><td><b>{final_ecl:,.2f} bn</b></td></tr>
</table>

<h2>Management Overlay 사유</h2>
<ul>{overlay_rows}</ul>

<h2>해석 (IFRS 9 검증)</h2>
<ul>
<li><b>FLI</b> (Forward-Looking Information): IFRS 9 §B5.5.49 — 모든 합리적
시나리오의 확률 가중 ECL. 단일 시나리오 ECL 부적합.</li>
<li><b>Management Overlay (PMA)</b>: 모형이 포착 못한 risk (예: 부동산 PF
재충격) 의 보수적 추가. <b>회계감리 대상</b> — 회계법인 검토 필수.</li>
<li><b>Severely adverse weight 20%</b>: 가중치 floor 점검 — IFRS 9 시행 초기
보수성 원칙 (시나리오 가중치 점검은 3.weights step 참조).</li>
<li><b>Final ECL</b>은 본 자동 점검의 산출이 아니며 실제 ECL 은 운영 ECL
시스템 + 회계법인 검토 + 감독원 보고 절차 (CLAUDE.md §5).</li>
</ul>
<p><a href="ifrs9_deep.html">← IFRS 9 Stage Migration 으로</a></p>
"""
    return _page("심화 — IFRS 9 FLI overlay + 가중 ECL + PMA", body)


def _ccr_netting_deep_page() -> str:
    """SA-CCR netting set 분해 + WWR identification + collateral."""
    from tools.sample_generators import ccr_netting_sample

    nsets = ccr_netting_sample()
    alpha = 1.4

    ead_by_set = [
        (ns["netting_set"], alpha * max(0.0, ns["rc"] + ns["pfe"] - ns["collateral_bn"]))
        for ns in nsets
    ]
    asset_class_totals: dict[str, float] = {}
    for ns in nsets:
        asset_class_totals.setdefault(ns["asset_class"], 0.0)
        asset_class_totals[ns["asset_class"]] += alpha * max(
            0.0, ns["rc"] + ns["pfe"] - ns["collateral_bn"])

    set_chart = hbar(
        ead_by_set, title="Netting set 별 EAD", fmt="{:,.1f} bn",
        colors=[PALETTE["fail"] if ns["wrong_way_risk"] else PALETTE["neutral"]
                for ns in nsets])

    asset_chart = hbar(
        list(asset_class_totals.items()), title="Asset class 별 EAD",
        fmt="{:,.1f} bn",
        colors=[PALETTE["neutral"]] * len(asset_class_totals))

    rows = "".join(
        f"<tr><td><code>{_esc(ns['netting_set'])}</code></td>"
        f"<td><code>{_esc(ns['counterparty'])}</code></td>"
        f"<td>{_esc(ns['asset_class'])}</td>"
        f"<td>{ns['rc']:,.1f}</td><td>{ns['pfe']:,.1f}</td>"
        f"<td>{ns['collateral_bn']:,.1f}</td>"
        f"<td>{alpha * max(0.0, ns['rc'] + ns['pfe'] - ns['collateral_bn']):,.1f}</td>"
        f"<td>{'<b style=color:#c62828>WWR</b>' if ns['wrong_way_risk'] else 'no'}</td></tr>"
        for ns in nsets)

    total_ead = sum(e for _, e in ead_by_set)
    wwr_ead = sum(e for ns, e in zip(nsets, [e for _, e in ead_by_set])
                  if ns["wrong_way_risk"])

    body = f"""
<p>SA-CCR (BCBS CRE52) netting set 단위 EAD 분해 + Wrong-Way Risk (WWR)
식별 + 담보 차감.</p>

<h2>Netting Set 별 EAD</h2>
{set_chart}
<table>
<tr><th>Netting Set</th><th>Counterparty</th><th>Asset Class</th>
<th>RC</th><th>PFE</th><th>Collateral</th><th>EAD = α(RC+PFE−Col)</th><th>WWR</th></tr>
{rows}
<tr><th colspan="6">합계 EAD</th><td><b>{total_ead:,.1f}</b></td><td></td></tr>
</table>

<h2>Asset Class 별 EAD</h2>
{asset_chart}

<h2>Wrong-Way Risk (WWR) 식별</h2>
<table>
<tr><th>WWR 식별 netting set 수</th>
<td>{sum(1 for ns in nsets if ns['wrong_way_risk'])} / {len(nsets)}</td></tr>
<tr><th>WWR 영향 EAD</th>
<td>{wwr_ead:,.1f} bn ({wwr_ead/max(total_ead,1e-9):.1%} of total)</td></tr>
<tr><th>대응</th>
<td>WWR netting set 에 α 가산 적용 + counterparty 신용도 monitoring 강화
(BCBS CRE52 §165)</td></tr>
</table>

<h2>해석 (CCR 검증)</h2>
<ul>
<li><b>EAD = α × max(0, RC + PFE − Collateral)</b>. 담보가 충분하면 EAD = 0.</li>
<li><b>Netting set</b>: 단일 master netting agreement (ISDA) 단위.
counterparty 가 여러 netting set 가질 수 있음 (예: CP-001 has NS-001, NS-002).</li>
<li><b>WWR</b>: 거래상대방 신용 악화와 동시 EAD 증가 (예: 신용보증사가 CDS
매도자). 식별 시 α 가산 또는 별도 capital.</li>
<li><b>Asset class 집중</b>: 단일 asset class (예: IR) 집중은 시장 충격에
민감.</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로</a> · <a href="ccr_deep.html">CCR EAD 분해 →</a></p>
"""
    return _page("심화 — SA-CCR Netting Set + Wrong-Way Risk", body)


def _operational_bi_deep_page() -> str:
    """SMA Business Indicator 5 component 분해 + ILDC 10년 시계열."""
    from tools.sample_generators import (
        operational_bi_components_sample,
        operational_loss_history_sample,
    )

    bi = operational_bi_components_sample()
    history = operational_loss_history_sample()

    bi_chart = hbar(
        [(k, float(v)) for k, v in bi["components"].items()],
        title="Business Indicator 5 component 분해", fmt="{:.2f} bn",
        colors=[PALETTE["neutral"]] * len(bi["components"]))

    loss_series = [(str(r["year"]), float(r["total_loss_bn"])) for r in history]
    loss_trend = trend_line(loss_series, title="10년 ILDC — 연간 총 손실 (bn)",
                            fmt="{:,.0f}")

    n_events_series = [(str(r["year"]), float(r["n_events"])) for r in history]
    events_trend = trend_line(n_events_series, title="10년 ILDC — 연간 손실 건수",
                              fmt="{:.0f}")

    history_rows = "".join(
        f"<tr><td>{r['year']}</td><td>{r['n_events']:,}</td>"
        f"<td>{r['total_loss_bn']:,.0f}</td>"
        f"<td>{r['avg_loss_bn']:.1f}</td></tr>"
        for r in history)

    avg_loss = sum(r["total_loss_bn"] for r in history) / len(history)
    bi_total = bi["total_bi"]
    # SMA 산식 (간략): BIC = α × BI (구간별)
    bic_low = min(bi_total, 1.0) * 0.12
    bic_mid = max(0, min(bi_total, 30.0) - 1.0) * 0.15
    bic_high = max(0, bi_total - 30.0) * 0.18
    bic = bic_low + bic_mid + bic_high

    body = f"""
<p>운영리스크 SMA 의 BI 5 component 분해 + ILDC 10년 손실 시계열.
출처: {_esc(bi['framework'])}.</p>

<h2>BI 5 Component 분해</h2>
{bi_chart}
<table>
<tr><th>Component</th><th>값 (bn)</th><th>BCBS OPE25 정의</th></tr>
<tr><td>Interest/Lease/Dividend</td><td>{bi['components']['Interest/Lease/Dividend']:.2f}</td>
<td>ILDC — interest income/expense + lease + dividend</td></tr>
<tr><td>Services</td><td>{bi['components']['Services']:.2f}</td>
<td>SC — fee & commission income/expense</td></tr>
<tr><td>Financial (Trading book)</td><td>{bi['components']['Financial (Trading book)']:.2f}</td>
<td>FC trading — net P&L</td></tr>
<tr><td>Financial (Banking book)</td><td>{bi['components']['Financial (Banking book)']:.2f}</td>
<td>FC banking — net P&L</td></tr>
<tr><th>BI Total</th><th>{bi_total:.2f}</th><th></th></tr>
</table>

<h2>BIC 산식 (구간별)</h2>
<table>
<tr><th>0 ~ 1bn @ 12%</th><td>{bic_low:.4f} bn</td></tr>
<tr><th>1 ~ 30bn @ 15%</th><td>{bic_mid:.4f} bn</td></tr>
<tr><th>&gt; 30bn @ 18%</th><td>{bic_high:.4f} bn</td></tr>
<tr><th>BIC 합계</th><td><b>{bic:.4f} bn</b></td></tr>
<tr><th>ORC (ILM=1, 국내)</th><td>{bic:.4f} bn</td></tr>
</table>

<h2>ILDC — 10년 손실 시계열</h2>
{loss_trend}
{events_trend}
<table>
<tr><th>연도</th><th>건수</th><th>총 손실 (bn)</th><th>평균 손실/건</th></tr>
{history_rows}
</table>
<p>10년 평균 연간 손실: <b>{avg_loss:,.0f} bn</b>. ILDC 도입 시 ILM 산식의 input
이 되며 ILM ≠ 1 적용 가능 (감독 승인 필요).</p>

<h2>해석 (운영리스크 검증)</h2>
<ul>
<li><b>ILDC 비중 높음</b>: 전통적 은행 (대출/이자 중심). 트레이딩북 비중이
크면 Financial (Trading) component 가 BI 의 dominant.</li>
<li><b>국내 ILM = 1</b>: 자체 10년 손실 데이터 사용 시 ILM &lt; 1 (이력 우수)
또는 ILM &gt; 1 (이력 열위) 적용 — 감독 승인 절차 필요.</li>
<li><b>ILDC 시계열 trend</b>: 손실 추세가 상승하면 BCBS OPE25 ILM 적용 시
capital 증가. 단년도 이상치는 평균에 큰 영향 — 6년 cutoff (BCBS OPE25 §28)
참조.</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로</a></p>
"""
    return _page("심화 — 운영 SMA BI 5 component + 10년 ILDC", body)


def _irrbb_behavioral_page() -> str:
    """IRRBB behavioral assumption + duration gap."""
    from tools.sample_generators import irrbb_behavioral_sample

    b = irrbb_behavioral_sample()
    core_bn = b["nmd_total_bn"] * b["nmd_core_ratio"]
    non_core_bn = b["nmd_total_bn"] * (1 - b["nmd_core_ratio"])

    nmd_chart = hbar(
        [("Core (안정)", core_bn), ("Non-core (변동)", non_core_bn)],
        title="NMD 분류", fmt="{:,.0f} bn",
        colors=[PALETTE["ok"], PALETTE["warning"]])

    dur_chart = hbar(
        [("자산 duration", b["duration_assets_yrs"]),
         ("부채 duration", b["duration_liabilities_yrs"]),
         ("Duration gap", b["duration_gap_yrs"])],
        title="Duration (yrs)", fmt="{:.1f} yrs",
        colors=[PALETTE["neutral"], PALETTE["neutral"],
                PALETTE["fail"] if b["duration_gap_yrs"] > 1.0 else PALETTE["ok"]])

    body = f"""
<p>IRRBB behavioral assumption (NMD core/non-core, prepayment) + duration gap.
출처: {_esc(b['framework'])}.</p>

<h2>NMD (Non-Maturity Deposits) 분류</h2>
{nmd_chart}
<table>
<tr><th>NMD 총액</th><td>{b['nmd_total_bn']:,.0f} bn</td></tr>
<tr><th>Core 비율</th><td>{b['nmd_core_ratio']:.0%} (안정 = 장기 결제계좌·예금)</td></tr>
<tr><th>Repricing lag (core)</th><td>{b['nmd_repricing_lag_months']} 개월</td></tr>
</table>
<p>BCBS SRP31 §115: NMD 의 core 비율과 repricing lag 는 모형 가정이며 자체
behavioral study 가 필요. core 비율이 너무 높으면 stress 시 deposit run 위험.</p>

<h2>Prepayment / Early Withdrawal</h2>
<table>
<tr><th>대출 prepayment rate (연간)</th>
<td>{b['loan_prepayment_rate_annual']:.1%}</td></tr>
<tr><th>정기예금 early withdrawal rate</th>
<td>{b['term_deposit_early_withdrawal_rate']:.1%}</td></tr>
</table>

<h2>Duration Gap</h2>
{dur_chart}
<table>
<tr><th>자산 duration</th><td>{b['duration_assets_yrs']:.1f} yrs</td></tr>
<tr><th>부채 duration</th><td>{b['duration_liabilities_yrs']:.1f} yrs</td></tr>
<tr><th>Duration gap</th>
<td><b>{b['duration_gap_yrs']:.1f} yrs</b> ({'asset > liab — 금리 상승 시 손실' if b['duration_gap_yrs'] > 0 else 'liab > asset — 금리 하락 시 손실'})</td></tr>
</table>

<h2>해석 (ALCO 관점)</h2>
<ul>
<li><b>NMD core 70%</b>가 IRRBB 모형의 핵심 가정. 가정 변경 시 ΔEVE 결과
대폭 변화. 자체 behavioral study (12개월 historical) 가 SREP 보고 자료.</li>
<li><b>Duration gap 1.4 yrs</b>: 자산 만기가 부채보다 길어 금리 상승 시
시가 손실. ΔEVE worst = parallel_up 와 일관.</li>
<li><b>prepayment 8%</b>: 금리 하락 시 부동산 담보대출 prepay 증가 → 자산
duration 단축. 시나리오 sensitivity 필요.</li>
</ul>
<p><a href="alm.html">← ALM 상세로</a> · <a href="alm_irrbb.html">시나리오별 ΔEVE →</a></p>
"""
    return _page("심화 — IRRBB Behavioral Assumption + Duration Gap", body)


def _concentration_segments_page() -> str:
    """산업/지역/통화별 집중 + top 10 exposures + HHI 별 분해."""
    from tools.sample_generators import concentration_segments_sample
    from vta.domains.concentration import herfindahl

    s = concentration_segments_sample()

    def _decompose(d: dict) -> tuple[str, float]:
        chart = hbar(
            sorted(d.items(), key=lambda kv: -kv[1]),
            title="", fmt="{:,.0f}", colors=[PALETTE["neutral"]] * len(d))
        hhi = herfindahl(list(d.values()))
        return chart, hhi

    ind_chart, ind_hhi = _decompose(s["industry"])
    reg_chart, reg_hhi = _decompose(s["region"])
    cur_chart, cur_hhi = _decompose(s["currency"])

    top_rows = "".join(
        f"<tr><td><code>{_esc(e['name'])}</code></td>"
        f"<td>{_esc(e['industry'])}</td>"
        f"<td>{e['exposure_bn']:,.0f}</td>"
        f"<td>{e['pct_tier1']:.2%}</td>"
        f"<td>{'<b style=color:#c62828>10%↑ 보고</b>' if e['pct_tier1'] >= 0.10 else 'ok'}</td></tr>"
        for e in s["top_exposures"])

    body = f"""
<p>신용집중 심화 — 산업/지역/통화별 분해 + top 10 그룹 exposure. HHI 는 각
segment 단위로 산정 (그룹별 HHI 와 별도).</p>

<h2>산업별 집중</h2>
<table><tr><th>합계 HHI</th><td><b>{ind_hhi:.4f}</b> ({'low' if ind_hhi<0.10 else 'moderate' if ind_hhi<0.18 else 'high'})</td></tr></table>
{ind_chart}

<h2>지역별 집중</h2>
<table><tr><th>합계 HHI</th><td><b>{reg_hhi:.4f}</b> ({'low' if reg_hhi<0.10 else 'moderate' if reg_hhi<0.18 else 'high'})</td></tr></table>
{reg_chart}

<h2>통화별 집중</h2>
<table><tr><th>합계 HHI</th><td><b>{cur_hhi:.4f}</b> ({'low' if cur_hhi<0.10 else 'moderate' if cur_hhi<0.18 else 'high'})</td></tr></table>
{cur_chart}

<h2>Top 10 그룹 exposure</h2>
<table>
<tr><th>그룹</th><th>산업</th><th>익스포저 (bn)</th><th>Tier1 대비</th><th>판정</th></tr>
{top_rows}
</table>

<h2>해석 (검증 관점)</h2>
<ul>
<li><b>산업 HHI</b>가 high band 이면 단일 산업 충격에 취약 (예: 부동산 침체).
산업 분류는 KSIC 대분류 기준.</li>
<li><b>지역 HHI</b>가 수도권 집중 시 지역 거시 충격 (부동산 가격 하락 등)에
민감.</li>
<li><b>통화 HHI</b>: 원화 외 통화 비중이 LCR 외화 80% 적용 대상과 일치 — ALM
통화별 분석과 cross-check.</li>
<li><b>거액익스포저</b>: BCBS LEX Tier1 10% 보고 / 25% 한도. 표의 마지막 컬럼
참조.</li>
</ul>
<p><a href="concentration.html">← 신용집중 상세로</a></p>
"""
    return _page("심화 — 산업/지역/통화별 집중 + Top 10 exposures", body)


def _market_components_deep_page() -> str:
    """VaR 분해 (General/Specific/Asset class) + SVaR + IRC."""
    from tools.sample_generators import var_components_sample

    v = var_components_sample()

    components_chart = hbar(
        [
            ("General Market", v["var_general_market"]),
            ("Specific", v["var_specific"]),
            ("Total VaR (99%)", v["var_99_total"]),
            ("SVaR (99%)", v["svar_99"]),
            ("IRC (99.9%)", v["irc_99_9"]),
        ],
        title="시장리스크 capital 구성요소", fmt="{:,.1f} bn",
        colors=[PALETTE["neutral"], PALETTE["warning"], PALETTE["neutral"],
                PALETTE["fail"], PALETTE["fail"]])

    asset_chart = hbar(
        [(k, v) for k, v in v["asset_classes"].items()],
        title="VaR by Asset Class", fmt="{:,.1f} bn",
        colors=[PALETTE["neutral"]] * len(v["asset_classes"]))

    total_capital = (v["var_99_total"] * v["multiplier"]
                     + v["svar_99"] * v["multiplier"]
                     + v["irc_99_9"])

    body = f"""
<p>시장리스크 capital charge 구성요소 분해 — General/Specific risk +
Stressed VaR + Incremental Risk Charge.</p>

<h2>VaR Capital Charge 분해</h2>
{components_chart}
<table>
<tr><th>구성요소</th><th>값 (bn)</th><th>의미</th></tr>
<tr><td>General Market</td><td>{v['var_general_market']:.1f}</td>
<td>금리/주가/FX/원자재의 일반 가격 변동</td></tr>
<tr><td>Specific Risk</td><td>{v['var_specific']:.1f}</td>
<td>개별 발행자/issuer specific 변동</td></tr>
<tr><th>99% VaR (Total)</th><td><b>{v['var_99_total']:.1f}</b></td>
<td>일간 99% loss 한도</td></tr>
<tr><td>Stressed VaR (99%)</td><td>{v['svar_99']:.1f}</td>
<td>2008-2009 위기 기간 calibration (BCBS MAR99 §32.5)</td></tr>
<tr><td>IRC (99.9%, 1y)</td><td>{v['irc_99_9']:.1f}</td>
<td>credit migration & default — non-securitisation</td></tr>
</table>

<h2>Asset Class 별 VaR 기여</h2>
{asset_chart}

<h2>Capital Charge 산식 (BCBS MAR99)</h2>
<table>
<tr><th>최소 capital</th>
<td><code>max(VaR_t-1, m × VaR_avg_60) + max(SVaR_t-1, ms × SVaR_avg_60) + IRC</code></td></tr>
<tr><th>기본 multiplier (m, ms)</th><td>{v['multiplier']:.1f}</td></tr>
<tr><th>Traffic light 가산</th>
<td>yellow zone (5~9 예외) +{v['yellow_multiplier_add']:.1f} 최대 +1.0</td></tr>
<tr><th>추정 Capital Charge (예시)</th>
<td><b>{total_capital:,.1f} bn</b> (VaR × {v['multiplier']:.0f} + SVaR × {v['multiplier']:.0f} + IRC)</td></tr>
</table>

<h2>해석 (시장리스크 검증)</h2>
<ul>
<li><b>SVaR > VaR</b>: 정상 시장 calibration 대비 스트레스 calibration 의
보수성. SVaR 가 VaR 의 1.5x 미만이면 stress window 재선정 검토.</li>
<li><b>IRC</b>: 1년 99.9% horizon — credit migration/default 의 cumulative
손실. 트레이딩북 채권 비중 클수록 IRC 비중 ↑.</li>
<li><b>Specific risk &gt; General</b>: 단일 issuer 집중 신호 — 분산화 검토.</li>
<li><b>출처</b>: {_esc(v['framework'])}.</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로</a></p>
"""
    return _page("심화 — 시장 VaR 구성요소 + SVaR + IRC", body)


def _alm_currency_deep_page() -> str:
    """통화별 LCR 분해 + ΔNII sensitivity + 일중유동성."""
    from tools.sample_generators import (
        intraday_liquidity_sample,
        lcr_by_currency_sample,
        nii_sensitivity_sample,
    )

    lcr = lcr_by_currency_sample()
    nii = nii_sensitivity_sample()
    intra = intraday_liquidity_sample()

    lcr_chart = hbar(
        [(c["currency"], c["hqla"] / max(c["outflow"], 1e-9)) for c in lcr],
        title="통화별 LCR (HQLA / 30d outflow)", fmt="{:.2f}",
        vline=1.0, vline_label="원화 min 1.00",
        colors=[PALETTE["ok"] if (c["hqla"]/c["outflow"]) >= c["min_required"]
                else PALETTE["fail"] for c in lcr])

    lcr_table = "".join(
        f"<tr><td><b>{_esc(c['currency'])}</b></td>"
        f"<td>{c['hqla']:,.0f}</td><td>{c['outflow']:,.0f}</td>"
        f"<td>{(c['hqla']/c['outflow']):.2f}</td>"
        f"<td>{c['min_required']:.0%}</td>"
        f"<td>{'<b style=color:#c62828>미달</b>' if (c['hqla']/c['outflow']) < c['min_required'] else 'ok'}</td>"
        f"<td>{_esc(c['note'])}</td></tr>"
        for c in lcr)

    nii_chart = hbar(
        [(s["scenario"], s["delta_nii_pct"]) for s in nii],
        title="ΔNII / NII (시나리오별, 1년 horizon)", fmt="{:+.1%}",
        colors=[PALETTE["fail" if s["delta_nii_pct"] < -0.05
                else "warning" if s["delta_nii_pct"] < 0 else "ok"]
                for s in nii])

    nii_table = "".join(
        f"<tr><td>{_esc(s['scenario'])}</td>"
        f"<td>{s['delta_nii_pct']:+.1%}</td>"
        f"<td>{s['delta_nii_bn']:+,.0f} bn</td></tr>"
        for s in nii)

    body = f"""
<p>ALM 심화: 통화별 LCR 분해 (BCBS LCR + 시행세칙 외화 LCR) + ΔNII sensitivity
(IRRBB 의 단기 수익 영향) + 일중유동성 monitoring (BCBS d423).</p>

<h2>통화별 LCR (Multi-Currency)</h2>
{lcr_chart}
<table>
<tr><th>통화</th><th>HQLA</th><th>30d Outflow</th><th>LCR</th>
<th>최소</th><th>판정</th><th>비고</th></tr>
{lcr_table}
</table>
<p>원화는 BCBS LCR 100% / 외화는 감독원 행정지도 80% 적용. 통화별 mismatch
가 있어도 총 LCR 충족 가능 — 통화 단위 점검 필수.</p>

<h2>ΔNII (Net Interest Income) Sensitivity</h2>
{nii_chart}
<table>
<tr><th>시나리오</th><th>ΔNII / NII</th><th>ΔNII (bn)</th></tr>
{nii_table}
</table>
<p>IRRBB 는 ΔEVE (자본 관점) 와 ΔNII (수익 관점) 양쪽으로 점검 (BCBS SRP31 §132).
ΔNII 음수는 단기 수익성 하락 — 변동금리 자산/고정금리 부채 mismatch 신호.</p>

<h2>일중유동성 (Intraday Liquidity)</h2>
<table>
<tr><th>일중 최대 사용 (정상일)</th><td>{intra['daily_max_intraday_usage_bn']:,.0f} bn</td></tr>
<tr><th>평균 일중 사용</th><td>{intra['average_intraday_usage_bn']:,.0f} bn</td></tr>
<tr><th>일중 신용한도</th><td>{intra['intraday_credit_lines_bn']:,.0f} bn</td></tr>
<tr><th>스트레스일 사용</th><td>{intra['stress_day_usage_bn']:,.0f} bn</td></tr>
<tr><th>피크/평균 비율</th><td>{intra['peak_to_average_ratio']:.1f}x</td></tr>
<tr><th>프레임워크</th><td>{_esc(intra['framework'])}</td></tr>
</table>

<h2>해석 (ALCO 관점)</h2>
<ul>
<li><b>통화별 LCR mismatch</b>: 총 LCR 이 충족되더라도 특정 통화 (EUR/CNY) 미달
가능. 통화 swap 시장 단절 시나리오에서 stress 보고 필요.</li>
<li><b>ΔNII vs ΔEVE</b>: ΔEVE 는 long-term capital, ΔNII 는 short-term
earnings. parallel up 에서 ΔNII +8% 면 단기 이익 증가하나 ΔEVE 손실 시 자본
잠식 — 양쪽 균형이 ALM 의 핵심.</li>
<li><b>일중유동성</b>: 분기 monitoring 보고. 스트레스일 사용이 한도의 90%
초과 시 추가 buffer 확보 (BCBS d423).</li>
</ul>
<p><a href="alm.html">← ALM 상세로</a></p>
"""
    return _page("심화 — ALM 통화별 LCR + ΔNII + 일중유동성", body)


def _capital_rwa_deep_page() -> str:
    """RWA 분해 (Pillar 1 산정 방식별) + Output Floor 72.5% sensitivity."""
    from tools.sample_generators import rwa_decomposition_sample, srep_capital_sample

    r = rwa_decomposition_sample()
    s = srep_capital_sample()

    by_internal = r["by_approach"]
    chart_internal = hbar(
        [(k, float(v)) for k, v in by_internal.items()],
        title="RWA — 산정 방식별 (내부 모형)", fmt="{:,.0f}",
        colors=[PALETTE["neutral"]] * len(by_internal))

    sa_full = r["standardised_full"]
    chart_sa = hbar(
        [(k, float(v)) for k, v in sa_full.items()],
        title="RWA — 표준방식(SA) 전면 적용 시", fmt="{:,.0f}",
        colors=[PALETTE["warning"]] * len(sa_full))

    floor_chart = hbar(
        [
            ("내부 모형 합계", float(r["total_internal"])),
            (f"표준방식 × {r['output_floor_ratio']:.0%}",
             r["output_floor_ratio"] * float(r["total_standardised"])),
            ("Floor 적용 후 RWA", float(r["rwa_after_floor"])),
        ],
        title="Output Floor 비교 (FRTB d424)", fmt="{:,.0f}",
        colors=[PALETTE["neutral"], PALETTE["warning"],
                PALETTE["fail"] if r["floor_binding"] else PALETTE["ok"]])

    p1_sum = sum(by_internal.values()) * 0.105  # 총자본 10.5% (4.5% + buffer 2.5% + +Tier2)
    p2r = float(r["rwa_after_floor"]) * s["p2r_pct"]
    p2g = float(r["rwa_after_floor"]) * s["p2g_pct"]
    stress_b = float(r["rwa_after_floor"]) * s["stress_buffer_pct"]
    stack = hbar(
        [
            ("Pillar 1 (10.5%)", p1_sum),
            (f"P2R ({s['p2r_pct']:.1%})", p2r),
            (f"P2G ({s['p2g_pct']:.1%})", p2g),
            (f"Stress buffer ({s['stress_buffer_pct']:.1%})", stress_b),
        ],
        title="Total Capital Requirement (TCR) 분해", fmt="{:,.0f}")

    rationale_html = "".join(f"<li>{_esc(r)}</li>" for r in s["rationale"])

    body = f"""
<p>Pillar 1 RWA 산정 방식별 분해 + Basel III 마지막 단계 Output Floor 72.5%
적용 효과 + Pillar 2 SREP capital add-on.</p>

<h2>RWA 산정 방식별 (내부 모형 적용)</h2>
{chart_internal}
<p>총 내부 모형 RWA: <b>{r['total_internal']:,.0f}</b></p>

<h2>표준방식 전면 적용 시 비교</h2>
{chart_sa}
<p>총 SA RWA: <b>{r['total_standardised']:,.0f}</b></p>

<h2>Output Floor 효과 (BCBS d424)</h2>
{floor_chart}
<table>
<tr><th>Output Floor 비율</th><td>{r['output_floor_ratio']:.0%}</td></tr>
<tr><th>Floor 적용 후 RWA</th><td>{r['rwa_after_floor']:,.0f}</td></tr>
<tr><th>Floor binding?</th>
<td>{'<b style="color:#c62828">예 — 내부 모형 사용 효과 일부 소멸</b>' if r['floor_binding'] else '아니오 (내부 모형 더 보수적)'}</td></tr>
</table>

<h2>SREP Capital — Total Capital Requirement</h2>
{stack}
<table>
<tr><th>P2R (binding)</th><td>{s['p2r_pct']:.2%}</td><td>{p2r:,.0f}</td></tr>
<tr><th>P2G (guidance)</th><td>{s['p2g_pct']:.2%}</td><td>{p2g:,.0f}</td></tr>
<tr><th>Stress buffer (내부)</th><td>{s['stress_buffer_pct']:.2%}</td><td>{stress_b:,.0f}</td></tr>
</table>
<p>출처: {_esc(s['framework'])}.</p>

<h2>해석 (자본계획 관점)</h2>
<ul>{rationale_html}
<li><b>Output Floor</b>는 Basel III 마지막 phase 에서 단계적으로 50% → 72.5%
까지 인상 (BCBS d424). Floor binding 시 IRBA 도입 효과 일부 소멸.</li>
<li><b>P2R</b>은 강제, <b>P2G</b>는 권고 — 그러나 P2G 미충족 시 감독 대응 강화.</li>
<li><b>본 분해는 합성</b> — 운영 RWA 는 자체 IRBA / IMM / SMA / SA-CVA 결과로
대체. 정책 변경 시 매니페스트 CHG 기록 필수.</li>
</ul>
<p><a href="capital_icaap.html">← 자본 + ICAAP 상세로</a></p>
"""
    return _page("심화 — RWA 분해 + Output Floor + SREP", body)


def _credit_segments_page(request: dict) -> str:
    """세그먼트별 변별력 + ROC curve + score 분포 (good vs bad)."""
    df = request.get("df")
    target_col = request.get("target_col", "target")
    score_col = request.get("score_col", "score")
    if df is None or score_col not in df.columns:
        return _page("심화 — 신용 세그먼트별 분석",
                     "<p>입력 df 미제공.</p>")

    from tools.metric_ks_auc import calculate_auc_gini, calculate_ks

    # 등급별 KS / AUROC
    grade_col = request.get("grade_col", "grade")
    grade_rows = []
    for grade in sorted(df[grade_col].unique()):
        sub = df[df[grade_col] == grade]
        if len(sub) < 30 or sub[target_col].nunique() < 2:
            grade_rows.append((str(grade), len(sub), float("nan"), float("nan")))
            continue
        ks = calculate_ks(sub[target_col].to_numpy(), sub[score_col].to_numpy())["ks"]
        ag = calculate_auc_gini(sub[target_col].to_numpy(), sub[score_col].to_numpy())
        grade_rows.append((str(grade), len(sub), ks, ag["auc"]))

    grade_chart = hbar(
        [(g, k) for g, _, k, _ in grade_rows if not _isnan(k)],
        title="등급별 KS", fmt="{:.4f}", vline=0.30,
        vline_label="참고 임계 0.30",
        colors=[PALETTE["ok" if k >= 0.30 else "fail"]
                for _, _, k, _ in grade_rows if not _isnan(k)])

    grade_table = "".join(
        f"<tr><td>{_esc(g)}</td><td>{n:,}</td>"
        f"<td>{('-' if _isnan(k) else f'{k:.4f}')}</td>"
        f"<td>{('-' if _isnan(a) else f'{a:.4f}')}</td></tr>"
        for g, n, k, a in grade_rows)

    # dev vs oot 변별력
    set_col = request.get("set_col", "set")
    dev = df[df[set_col] == "dev"]
    oot = df[df[set_col] == "oot"]
    set_metrics = []
    for label, sub in (("dev", dev), ("oot", oot)):
        if len(sub) < 100 or sub[target_col].nunique() < 2:
            continue
        ks = calculate_ks(sub[target_col].to_numpy(), sub[score_col].to_numpy())["ks"]
        ag = calculate_auc_gini(sub[target_col].to_numpy(), sub[score_col].to_numpy())
        set_metrics.append((label, len(sub), ks, ag["auc"], ag["gini"]))
    set_chart = hbar(
        [(f"{label} (n={n:,})", auc) for label, n, _, auc, _ in set_metrics],
        title="dev / oot AUROC 비교", fmt="{:.4f}",
        vline=0.70, vline_label="참고 임계 0.70",
        colors=[PALETTE["ok" if a >= 0.70 else "fail"]
                for _, _, _, a, _ in set_metrics])

    # ROC curve (sampled — efficient)
    import numpy as np
    y = df[target_col].to_numpy()
    s = df[score_col].to_numpy()
    # threshold grid
    sorted_s = np.sort(s)
    thresholds = sorted_s[np.linspace(0, len(sorted_s) - 1, 50).astype(int)]
    roc_pts = []
    for thr in thresholds:
        pred = s >= thr
        tp = float(((pred == 1) & (y == 1)).sum())
        fp = float(((pred == 1) & (y == 0)).sum())
        fn = float(((pred == 0) & (y == 1)).sum())
        tn = float(((pred == 0) & (y == 0)).sum())
        tpr = tp / max(tp + fn, 1)
        fpr = fp / max(fp + tn, 1)
        roc_pts.append((fpr, tpr))
    roc_svg = _roc_svg(roc_pts)

    # score 분포 (good vs bad)
    good = s[y == 0]
    bad = s[y == 1]
    hist_svg = _two_histogram_svg(good, bad, ("good (target=0)", "bad (target=1)"))

    body = f"""
<p>신용평가 모형의 세그먼트별 변별력·dev/oot 안정성·ROC·score 분포 분석.
입력 n = {len(df):,}.</p>

<h2>등급별 변별력</h2>
{grade_chart}
<table>
<tr><th>등급</th><th>건수</th><th>KS</th><th>AUROC</th></tr>
{grade_table}
</table>

<h2>dev / oot 안정성</h2>
{set_chart}
<table>
<tr><th>set</th><th>n</th><th>KS</th><th>AUROC</th><th>Gini</th></tr>
{"".join(f"<tr><td>{label}</td><td>{n:,}</td><td>{k:.4f}</td><td>{a:.4f}</td><td>{g:.4f}</td></tr>" for label, n, k, a, g in set_metrics)}
</table>

<h2>ROC Curve (전체)</h2>
{roc_svg}

<h2>Score 분포 (good vs bad)</h2>
{hist_svg}

<h2>해석 (검증 관점)</h2>
<ul>
<li><b>등급별 KS</b>가 일부 등급에서 임계 미달이면 등급 통합 또는 재캘리브레이션
검토. 표본 30건 미만 등급은 KS 계산 불가 (분산 추정 불안정).</li>
<li><b>dev/oot AUROC gap</b>이 0.05 이상이면 overfit 의심 — 변수 선정 재검토 +
out-of-time validation 추가.</li>
<li><b>ROC curve</b>이 대각선(랜덤)에 가까우면 변별 부족. 곡선이 좌상단으로
가까울수록 우수.</li>
<li><b>Score 분포 overlap</b>이 크면 cut-off 결정이 어려움 — KS 위치가 최적
threshold 후보.</li>
</ul>
<p><a href="credit.html">← 신용평가모형 상세로</a></p>
"""
    return _page("심화 — 신용 세그먼트별 변별력 + ROC + 분포", body)


def _credit_vintage_page(request: dict) -> str:
    """Vintage cohort 분석 — obs_date 별 부도율 시계열."""
    df = request.get("df")
    target_col = request.get("target_col", "target")
    date_col = request.get("date_col", "obs_date")
    if df is None or date_col not in df.columns:
        return _page("심화 — Vintage cohort 분석",
                     "<p>입력 df / 일자 컬럼 미제공.</p>")

    # Cohort = obs_date 의 분기 (24개월 → 8 분기)
    import pandas as pd

    d = df.copy()
    d["_quarter"] = pd.to_datetime(d[date_col]).dt.to_period("Q").astype(str)
    cohort = (d.groupby("_quarter")[target_col].agg(["mean", "count"])
              .reset_index())

    series = [(r["_quarter"], float(r["mean"]))
              for _, r in cohort.iterrows()]
    trend_svg = trend_line(
        series, title="분기별 cohort 부도율 (vintage)",
        fmt="{:.2%}",
        minimum=0.10)  # 10% 참고선

    rows = "".join(
        f"<tr><td>{_esc(r['_quarter'])}</td>"
        f"<td>{int(r['count']):,}</td>"
        f"<td>{float(r['mean']):.4%}</td></tr>"
        for _, r in cohort.iterrows())

    # 등급 × 분기 (heatmap-like — 표)
    grade_col = request.get("grade_col", "grade")
    if grade_col in df.columns:
        pivot = (d.groupby(["_quarter", grade_col])[target_col].mean()
                 .unstack(fill_value=float("nan")))
        grades = list(pivot.columns)
        header = "<tr><th>분기</th>" + "".join(
            f"<th>{_esc(g)}</th>" for g in grades) + "</tr>"
        body_rows = ""
        for period, row in pivot.iterrows():
            cells = ""
            for g in grades:
                v = row[g]
                if pd.isna(v):
                    cells += "<td>-</td>"
                else:
                    color = (PALETTE["fail"] if v > 0.20
                             else PALETTE["warning"] if v > 0.05
                             else PALETTE["ok"])
                    cells += (f'<td style="background:{color};color:white;'
                              f'text-align:right">{v:.2%}</td>')
            body_rows += f"<tr><th>{_esc(period)}</th>{cells}</tr>"
        grade_pivot = f"<table>{header}{body_rows}</table>"
    else:
        grade_pivot = "<p>등급 컬럼 없음.</p>"

    body = f"""
<p>관측일자(obs_date) 기준 분기 cohort 별 실측 부도율 — vintage 분석.
{len(cohort)} 분기, n = {len(df):,}.</p>

<h2>Cohort 부도율 추세</h2>
{trend_svg}

<h2>분기별 부도율 표</h2>
<table>
<tr><th>cohort</th><th>건수</th><th>부도율</th></tr>
{rows}
</table>

<h2>등급 × 분기 매트릭스</h2>
{grade_pivot}

<h2>해석 (검증 관점)</h2>
<ul>
<li><b>Vintage curve</b>: cohort 별로 같은 관찰 시점에 진입한 표본의 부도율
변화. 운영 상의 정책 변경(인수 기준)이 cohort 단절(structural break)로
드러난다.</li>
<li><b>분기별 부도율 상승</b>은 거시 악화 (실업/금리)·정책 완화·운영 표본
드리프트 신호. PSI 와 함께 보면 원인 분리 가능.</li>
<li><b>등급 × 분기 매트릭스</b>: 특정 등급에서만 부도율이 튀면 등급 정의
재검토. 모든 등급에서 동시 상승은 거시 충격.</li>
<li>본 분석은 합성 obs_date 기반 — 운영 데이터에서는 cohort 정의를 인수
시점 (origination) 또는 관찰 시점에 맞춰 사용.</li>
</ul>
<p><a href="credit.html">← 신용평가모형 상세로</a></p>
"""
    return _page("심화 — Vintage cohort 분석", body)


def _isnan(x: float) -> bool:
    import math
    try:
        return math.isnan(float(x))
    except Exception:
        return True


def _roc_svg(points: list[tuple[float, float]], *, size: int = 320) -> str:
    """ROC curve inline SVG."""
    pad = 36
    w = h = size
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'font-family="sans-serif" font-size="11">']
    # 대각선
    out.append(f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{pad}" '
               f'stroke="#90a4ae" stroke-dasharray="3 3"/>')
    # 축
    out.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#37474f"/>')
    out.append(f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#37474f"/>')

    # 점들 (FPR x, TPR y)
    pts = sorted(points)
    path = " ".join(("M" if i == 0 else "L") +
                    f"{pad + p[0]*(w-2*pad):.1f},{h-pad - p[1]*(h-2*pad):.1f}"
                    for i, p in enumerate(pts))
    out.append(f'<path d="{path}" fill="none" stroke="#1565c0" stroke-width="2"/>')

    out.append(f'<text x="{w/2}" y="{h-8}" text-anchor="middle">FPR</text>')
    out.append(f'<text x="14" y="{h/2}" transform="rotate(-90 14 {h/2})" '
               f'text-anchor="middle">TPR</text>')
    out.append(f'<text x="{w-pad}" y="{pad-6}" text-anchor="end" '
               f'fill="#1565c0" font-weight="600">ROC</text>')
    out.append('</svg>')
    return "".join(out)


def _two_histogram_svg(a, b, labels: tuple[str, str], *,
                       width: int = 560, height: int = 200) -> str:
    """두 분포 histogram overlay (good vs bad)."""
    import numpy as np

    pad_l, pad_r, pad_t, pad_b = 40, 16, 28, 30
    bins = np.linspace(min(a.min(), b.min()), max(a.max(), b.max()), 30)
    ha, _ = np.histogram(a, bins=bins, density=True)
    hb, _ = np.histogram(b, bins=bins, density=True)
    vmax = max(ha.max(), hb.max(), 1e-9)
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    bar_w = inner_w / len(bins)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
           f'height="{height}" font-family="sans-serif" font-size="11">']
    out.append('<text x="0" y="14" font-weight="bold">Score 분포 (정규화)</text>')
    out.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#37474f"/>')
    out.append(f'<line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#37474f"/>')

    for i, (va, vb) in enumerate(zip(ha, hb)):
        x = pad_l + i * bar_w
        for v, color in ((va, PALETTE["ok"]), (vb, PALETTE["fail"])):
            bar_h = inner_h * (v / vmax)
            y = (height - pad_b) - bar_h
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w-1:.1f}" '
                       f'height="{bar_h:.1f}" fill="{color}" fill-opacity="0.45"/>')

    # 범례
    out.append(f'<rect x="{width-200}" y="{pad_t-4}" width="10" height="10" fill="{PALETTE["ok"]}"/>')
    out.append(f'<text x="{width-185}" y="{pad_t+5}">{_esc(labels[0])}</text>')
    out.append(f'<rect x="{width-90}" y="{pad_t-4}" width="10" height="10" fill="{PALETTE["fail"]}"/>')
    out.append(f'<text x="{width-75}" y="{pad_t+5}">{_esc(labels[1])}</text>')
    out.append('</svg>')
    return "".join(out)


def _ifrs9_deep_page() -> str:
    """IFRS 9 stage migration matrix + ECL 분해."""
    from tools.sample_generators import ifrs9_stage_migration_sample

    m = ifrs9_stage_migration_sample()
    stages = m["stages"]

    # migration matrix 표
    mig_rows = ""
    for from_s in stages:
        row = f"<tr><th>{from_s}</th>"
        for to_s in stages:
            v = m["migration_matrix"][from_s][to_s]
            color = (PALETTE["fail"] if (from_s == "S1" and to_s == "S3") or
                                       (from_s == "S2" and to_s == "S3")
                     else PALETTE["warning"] if (from_s == "S1" and to_s == "S2")
                     else PALETTE["ok"] if from_s == to_s
                     else PALETTE["neutral"])
            row += (f'<td style="background:{color};color:white;'
                    f'text-align:center;font-weight:600">{v:.1%}</td>')
        row += "</tr>"
        mig_rows += row

    # ECL by stage
    ecl_chart = hbar(
        [(s, float(m["ecl_by_stage"][s])) for s in stages],
        title="ECL by Stage", fmt="{:,.2f}",
        colors=[PALETTE["ok"], PALETTE["warning"], PALETTE["fail"]])

    # 포트폴리오 분포
    port_chart = hbar(
        [(s, float(m["portfolio"][s]["ead"])) for s in stages],
        title="EAD by Stage", fmt="{:,.0f}",
        colors=[PALETTE["neutral"]] * 3)

    port_rows = "".join(
        f"<tr><td><b>{s}</b></td>"
        f"<td>{m['portfolio'][s]['ead']:,.0f}</td>"
        f"<td>{m['portfolio'][s].get('pd_12m', m['portfolio'][s].get('pd_lifetime', 0)):.4f}</td>"
        f"<td>{m['portfolio'][s]['lgd']:.2%}</td>"
        f"<td>{m['ecl_by_stage'][s]:,.2f}</td></tr>"
        for s in stages)

    body = f"""
<p>IFRS 9 ECL 산출의 stage 분류·migration matrix·ECL 분해. 합성 panel 기반
시연 — 운영 ECL 산출 대체 불가.</p>

<h2>Stage Migration Matrix (분기 → 분기)</h2>
<table style="text-align:center">
<tr><th></th>{"".join(f"<th>→ {s}</th>" for s in stages)}</tr>
{mig_rows}
</table>
<p>대각선 = 동일 stage 유지. S1→S2 는 SICR 경계, S1→S3 / S2→S3 는 직접 손상.</p>

<h2>포트폴리오 구성</h2>
{port_chart}
<table>
<tr><th>Stage</th><th>EAD</th><th>PD</th><th>LGD</th><th>ECL</th></tr>
{port_rows}
<tr><th>합계</th><td>—</td><td>—</td><td>—</td><td><b>{m['total_ecl']:,.2f}</b></td></tr>
</table>

<h2>ECL by Stage</h2>
{ecl_chart}

<h2>SICR (Significant Increase in Credit Risk) 정의</h2>
<table>
<tr><th>적용 기준</th><td>{_esc(m['sicr_definition'])}</td></tr>
<tr><th>프레임워크</th><td>{_esc(m['framework'])}</td></tr>
</table>

<h2>해석 (IFRS 9 검증)</h2>
<ul>
<li><b>Stage 1</b>: 12개월 기대손실 (12m EL) — PD 는 12m PD.</li>
<li><b>Stage 2</b>: SICR 충족 → lifetime EL. 30일 이상 연체는 ‘rebuttable’
presumption (IFRS 9 §B5.5.20).</li>
<li><b>Stage 3</b>: 신용 손상 — interest revenue 는 net carrying 기준
(IFRS 9 §B5.4.6).</li>
<li><b>FLI (Forward-Looking Information)</b>: 거시 시나리오 가중평균 ECL.
시나리오 가중치 점검은 <a href="alm.html">3.weights</a> 참조.</li>
<li>본 표는 합성 — 운영 ECL 은 IFRS 9 운영지침 + 회계법인 검토 후 적용.</li>
</ul>
<p><a href="index.html">← 요약으로</a></p>
"""
    return _page("심화 — IFRS 9 ECL Stage Migration", body)


def _stress_test_page() -> str:
    """스트레스 테스트 시나리오 panel (baseline / adverse / severely adverse)."""
    from tools.sample_generators import stress_test_scenarios_sample

    scenarios = stress_test_scenarios_sample()

    chart_cet1 = hbar(
        [(s["scenario"], s["cet1_post_stress"]) for s in scenarios],
        title="CET1 비율 (스트레스 후)", fmt="{:.2%}",
        vline=0.045, vline_label="규제 최소 4.5%",
        colors=[PALETTE["ok"] if s["cet1_post_stress"] >= 0.07
                else PALETTE["warning"] if s["cet1_post_stress"] >= 0.045
                else PALETTE["fail"] for s in scenarios])

    chart_lcr = hbar(
        [(s["scenario"], s["lcr_post_stress"]) for s in scenarios],
        title="LCR (스트레스 후)", fmt="{:.2f}",
        vline=1.0, vline_label="최소 1.00",
        colors=[PALETTE["ok"] if s["lcr_post_stress"] >= 1.0
                else PALETTE["fail"] for s in scenarios])

    chart_icaap = hbar(
        [(s["scenario"], s["icaap_post_stress"]) for s in scenarios],
        title="ICAAP 비율 (스트레스 후)", fmt="{:.2f}",
        vline=1.0, vline_label="최소 1.00",
        colors=[PALETTE["ok"] if s["icaap_post_stress"] >= 1.0
                else PALETTE["fail"] for s in scenarios])

    macro_rows = "".join(
        f"<tr><th>{_esc(s['scenario'])}</th>"
        f"<td>{s['gdp_growth']:+.1%}</td>"
        f"<td>{s['unemployment']:.1%}</td>"
        f"<td>{s['house_price']:+.1%}</td>"
        f"<td>{s['policy_rate']:.2%}</td>"
        f"<td>×{s['credit_loss_multiplier']:.1f}</td>"
        f"<td>{s['weight']:.0%}</td></tr>"
        for s in scenarios)

    weighted_cet1 = sum(s["cet1_post_stress"] * s["weight"] for s in scenarios)

    body = f"""
<p>스트레스 테스트 시나리오 — baseline / adverse / severely adverse. 본
panel 은 자동 점검 시연용 합성 시드이며 운영 스트레스 테스트는 자체 시나리오
설계 + 거시 모형 + 자본계획 위원회 검토 후 (CLAUDE.md §5).</p>

<h2>거시 시나리오 가정</h2>
<table>
<tr><th>시나리오</th><th>GDP</th><th>실업률</th><th>주택가격</th>
<th>정책금리</th><th>손실 multiplier</th><th>가중치</th></tr>
{macro_rows}
</table>

<h2>스트레스 후 자본/유동성/내부자본</h2>
{chart_cet1}
{chart_lcr}
{chart_icaap}

<h2>가중평균 (감독 ICAAP 보고용)</h2>
<table>
<tr><th>가중평균 CET1 (post-stress)</th>
<td>{weighted_cet1:.2%}</td></tr>
<tr><th>판정</th>
<td>{'<b style="color:#2e7d32">최소 4.5% 충족</b>' if weighted_cet1 >= 0.045 else '<b style="color:#c62828">최소 미달</b>'}</td></tr>
</table>

<h2>해석 (CRO 관점)</h2>
<ul>
<li><b>severely adverse</b> 시나리오에서 CET1 5.5% 는 규제 최소 4.5% 는
충족하나 자본보전 buffer 2.5% 미충족 → <b>이익배당 제한</b> 가능성.</li>
<li><b>LCR 0.85</b>: severely adverse 시 100% 미달 — Recovery Plan 활성화
검토 (BCBS d258 + 시행세칙 R&R).</li>
<li><b>ICAAP 0.90</b>: post-stress 비율 1.00 미달 — Pillar 2 보고 + 자본계획
재점검 필수 (BCBS SRP30).</li>
<li>본 panel 은 합성 — 운영 스트레스 테스트는 BIS Top-Down 모형 또는 자체
Bottom-Up + 회계법인 검토 + 감독원 사전 협의.</li>
</ul>
<p><a href="executive.html">← 경영진 보고서로</a> · <a href="index.html">← 요약으로</a></p>
"""
    return _page("심화 — 스트레스 테스트 시나리오 panel (baseline / adverse / severe)", body)


def _change_audit_page() -> str:
    """모형/정책 변경 영향 감사 — 매니페스트 CHG 항목 요약."""
    from tools.manifest import load as load_manifest

    try:
        m = load_manifest()
    except Exception:
        return _page("모형/정책 변경 감사",
                     "<p>매니페스트 로드 실패.</p>")

    items = m.get("changes", [])
    n_total = len(items)
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for it in items:
        by_status[it.get("status", "?")] = by_status.get(it.get("status", "?"), 0) + 1
        by_type[it.get("type", "?")] = by_type.get(it.get("type", "?"), 0) + 1

    recent = sorted(items, key=lambda x: x.get("change_id", ""), reverse=True)[:15]
    recent_rows = "".join(
        f"<tr><td><code>{_esc(it.get('change_id', '-'))}</code></td>"
        f"<td>{_esc(it.get('type', '-'))}</td>"
        f"<td>{_esc(it.get('status', '-'))}</td>"
        f"<td>{_esc(it.get('component', '-'))}</td>"
        f"<td>{_esc((it.get('targeted_fix') or '')[:120])}…</td></tr>"
        for it in recent)

    status_chart = hbar(
        [(s, n) for s, n in sorted(by_status.items())],
        title="변경 매니페스트 status 분포", fmt="{:.0f}",
        colors=[PALETTE.get(
            "ok" if s == "validated" else
            "warning" if s == "applied" else
            "fail" if s == "rolled_back" else "neutral", PALETTE["neutral"])
            for s in sorted(by_status)])

    type_chart = hbar(
        [(t, n) for t, n in sorted(by_type.items())],
        title="변경 매니페스트 type 분포", fmt="{:.0f}")

    body = f"""
<p>모형·정책·코드 변경의 매니페스트 추적 — Decision Observability (AHE §4.3).
모든 변경은 <code>harness/change_manifest.json</code> 에 기록되며 promote
(applied/validated) 는 인간 검증자 영역.</p>

<h2>요약</h2>
<table>
<tr><th>총 CHG 항목</th><td>{n_total}</td></tr>
<tr><th>status 분포</th><td>{_esc(by_status)}</td></tr>
<tr><th>type 분포</th><td>{_esc(by_type)}</td></tr>
</table>

{status_chart}
{type_chart}

<h2>최근 변경 (Top 15)</h2>
<table>
<tr><th>CHG</th><th>type</th><th>status</th><th>component</th><th>fix 요약</th></tr>
{recent_rows}
</table>

<h2>운영 가이드</h2>
<ul>
<li><b>proposed → applied</b>: 검증팀장 검토 + 영향 평가 + 회귀 테스트 통과 후
<code>python -m tools.manifest promote &lt;CHG&gt; applied</code>.</li>
<li><b>applied → validated</b>: 분기 모니터링 결과 (KPI 안정성) 확인 후
<code>promote &lt;CHG&gt; validated</code>.</li>
<li><b>rolled_back</b>: 회귀 발견 시 즉시 rollback + 사유 기록. CLAUDE.md §4.3
"효과가 검증되지 않은 변경은 성공으로 간주하지 않는다".</li>
</ul>
<p><a href="executive.html">← 경영진 보고서로</a></p>
"""
    return _page("모형/정책 변경 감사 (Change Manifest)", body)


def _macro_overlay_page() -> str:
    """Macroprudential overlay — CCyB, DSR, LTV, SyRB."""
    from tools.sample_generators import macroprudential_overlay

    m = macroprudential_overlay()
    body = f"""
<p>거시건전성 정책 overlay — 자본/대출 규제. 본 페이지는 자동 점검 시연용
합성 input 이며 운영 시스템에서는 감독원 고시·금융위 공시·시행세칙의 실제
값으로 대체된다.</p>

<h2>거시건전성 buffer / 비율</h2>
<table>
<tr><th>지표</th><th>현재</th><th>임계/경고</th><th>출처</th></tr>
<tr><th>CCyB (경기대응 buffer)</th>
<td>{m['ccyb_required_pct']:.2%}</td>
<td>0~2.5% (감독원 분기 결정)</td>
<td><code>{_esc(m['framework_versions']['ccyb'])}</code></td></tr>
<tr><th>SyRB (시스템적 위험 buffer)</th>
<td>{m['syrb_required_pct']:.2%}</td>
<td>0~3.5% (BCBS d189)</td>
<td><code>{_esc(m['framework_versions']['syrb'])}</code></td></tr>
<tr><th>가계 DSR 평균</th>
<td>{m['dti_household_ratio']:.0%}</td>
<td>40% (감독원 권고선)</td>
<td><code>{_esc(m['framework_versions']['ltv_dsr'])}</code></td></tr>
<tr><th>주담대 LTV 평균</th>
<td>{m['ltv_residential_avg']:.0%}</td>
<td>≤ {m['ltv_residential_warning']:.0%} 경고</td>
<td><code>{_esc(m['framework_versions']['ltv_dsr'])}</code></td></tr>
<tr><th>D-SIB Leverage 추가</th>
<td>{m['leverage_buffer_for_gsib']:.2%}</td>
<td>G-SIB 시 1.0~3.5%</td>
<td>BCBS d365</td></tr>
</table>

<h2>해석 (정책 overlay)</h2>
<ul>
<li><b>CCyB</b>: 신용/GDP gap 상승 시 0% → 최대 2.5% 까지 단계 적용. 감독원
분기 결정 (시행세칙). 본 buffer 는 capital_adequacy_thresholds 에 직접 반영.</li>
<li><b>DSR/LTV</b>: 가계대출 위험가중치 산정 시 입력. 본 자동 점검은 평균
수치 점검만 — segment 별 (소득·LTV bucket) 분석은 별도 영역.</li>
<li><b>D-SIB 가산</b>: 국내 D-SIB 지정 은행은 1.0% 가산 (시행세칙). 본 페이지의
0% 는 합성 가정.</li>
<li>본 overlay 는 자동 점검 보조 자료 — 실제 정책 결정·수치는 감독원 공시
+ 시행세칙 확인 (CLAUDE.md §5).</li>
</ul>
<p><a href="executive.html">← 경영진 보고서로</a></p>
"""
    return _page("Macroprudential Overlay — 거시건전성 정책 (CCyB/DSR/LTV/SyRB)", body)


def _data_quality_deep_page(request: dict) -> str:
    """데이터 품질 심화 — 컬럼 통계 / 결측 / 분포 / target rate / 등급 cardinality."""
    df = request.get("df")
    if df is None:
        return _page("심화 — 데이터 품질 분포 분석",
                     "<p>입력 df 미제공.</p>")
    from tools.data_profile import profile_dataframe

    prof = profile_dataframe(df)
    # 컬럼별 dtype / 결측 / 카디널리티
    rows = []
    for col in df.columns:
        dt = prof["dtypes"].get(col, "?")
        miss = prof["missing_ratio"].get(col, 0.0)
        nunique = int(df[col].nunique(dropna=True))
        rows.append(
            f"<tr><td><code>{_esc(col)}</code></td><td>{_esc(dt)}</td>"
            f"<td>{miss:.4%}</td><td>{nunique:,}</td></tr>")

    # 숫자 컬럼 분포 요약
    num = prof["numeric_summary"]
    num_rows = ""
    for col, stats in num.items():
        num_rows += (
            f"<tr><td><code>{_esc(col)}</code></td>"
            f"<td>{stats.get('mean', float('nan')):.4f}</td>"
            f"<td>{stats.get('std', float('nan')):.4f}</td>"
            f"<td>{stats.get('min', float('nan')):.4f}</td>"
            f"<td>{stats.get('25%', float('nan')):.4f}</td>"
            f"<td>{stats.get('50%', float('nan')):.4f}</td>"
            f"<td>{stats.get('75%', float('nan')):.4f}</td>"
            f"<td>{stats.get('max', float('nan')):.4f}</td></tr>")

    # target rate by grade (if applicable)
    grade_chart = ""
    grade_table = ""
    target_col = request.get("target_col", "target")
    grade_col = request.get("grade_col", "grade")
    if grade_col in df.columns and target_col in df.columns:
        gb = (df.groupby(grade_col)[target_col].agg(["mean", "count"])
              .sort_index().reset_index())
        bars = [(str(r[grade_col]), float(r["mean"])) for _, r in gb.iterrows()]
        grade_chart = hbar(
            bars, title="등급별 실측 부도율 (target mean)", fmt="{:.4%}",
            colors=[PALETTE["neutral"]] * len(bars))
        grade_table = (
            '<table><tr><th>등급</th><th>건수</th><th>실측 부도율</th></tr>'
            + "".join(
                f"<tr><td>{_esc(r[grade_col])}</td>"
                f"<td>{int(r['count']):,}</td>"
                f"<td>{float(r['mean']):.4%}</td></tr>"
                for _, r in gb.iterrows())
            + "</table>")

    # set (dev/oot) 분포
    set_chart = ""
    if "set" in df.columns:
        sb = df["set"].value_counts().to_dict()
        set_chart = hbar(
            [(str(k), float(v) / len(df)) for k, v in sb.items()],
            title="dev / oot 분할 비율", fmt="{:.1%}",
            colors=[PALETTE["neutral"]] * len(sb))

    # 일자 커버리지
    date_block = ""
    date_col = request.get("date_col", "obs_date")
    if date_col in df.columns:
        from tools.data_profile import check_date_coverage

        try:
            cov = check_date_coverage(df, date_col)
            date_block = _kv_table([
                ("최소 일자", cov.get("min_date", "-")),
                ("최대 일자", cov.get("max_date", "-")),
                ("관측 일자 수", cov.get("n_dates", "-")),
            ])
        except Exception:
            date_block = "<p>일자 분석 skip (입력 형식 비호환)</p>"

    body = f"""
<p>본 페이지는 입력 df 의 컬럼·결측·분포·target 분포·일자 커버리지를 분해한다.
검증 의견 작성 시 입력 데이터의 정합성 근거로 사용된다.</p>

<h2>컬럼별 dtype · 결측 · 카디널리티</h2>
<table>
<tr><th>컬럼</th><th>dtype</th><th>결측 비율</th><th>고유값 수</th></tr>
{"".join(rows)}
</table>

<h2>숫자 컬럼 분포 요약</h2>
<table>
<tr><th>컬럼</th><th>mean</th><th>std</th><th>min</th><th>q25</th>
<th>median</th><th>q75</th><th>max</th></tr>
{num_rows or "<tr><td colspan='8'>숫자 컬럼 없음</td></tr>"}
</table>

<h2>등급별 실측 부도율</h2>
{grade_chart}
{grade_table}

<h2>dev / oot 분할</h2>
{set_chart}

<h2>일자 커버리지</h2>
{date_block or "<p>일자 컬럼 없음</p>"}

<h2>해석 (검증 관점)</h2>
<ul>
<li>결측 비율이 1% 이상인 컬럼은 사유 명시 + 대체값/제외 처리 문서화 필요.</li>
<li>등급별 실측 부도율은 등급 단조성 (낮은 등급일수록 높은 부도율) 의 직관
검증 자료. binomial 검정은 <a href="credit_calibration.html">등급별 캘리브레이션</a>
참조.</li>
<li>dev / oot 비율이 운영 정책 (예: 5:3) 과 일치하는지 확인. 본 데모는 합성
이므로 fixed split.</li>
</ul>
<p><a href="data_quality.html">← 데이터 품질 요약으로 돌아가기</a></p>
"""
    return _page("심화 — 데이터 품질 분포 분석", body)


def _trends_page() -> str:
    """4분기 panel — 자본/유동성/내부자본/IRRBB/PSI/HHI 추세 (합성)."""
    from tools.sample_generators import quarterly_panel

    panel = quarterly_panel()
    periods = [r["period"] for r in panel]

    def series(key):
        return list(zip(periods, [float(r[key]) for r in panel]))

    grid = "".join([
        trend_line(series("cet1"), title="CET1 비율", fmt="{:.2%}",
                   minimum=0.07),
        trend_line(series("leverage"), title="Leverage", fmt="{:.2%}",
                   minimum=0.03),
        trend_line(series("lcr"), title="LCR", fmt="{:.2f}", minimum=1.0),
        trend_line(series("nsfr"), title="NSFR", fmt="{:.2f}", minimum=1.0),
        trend_line(series("icaap"), title="ICAAP 비율", fmt="{:.2f}", minimum=1.0),
        trend_line(series("delta_eve"), title="ΔEVE / Tier1", fmt="{:.1%}",
                   minimum=0.15),
        trend_line(series("psi"), title="신용 PSI (≥ 0.25 불안정)", fmt="{:.3f}",
                   minimum=0.25),
        trend_line(series("hhi"), title="집중 HHI (band ≥ 0.18 high)", fmt="{:.3f}",
                   minimum=0.18),
    ])
    rows = "".join(
        f"<tr><td>{_esc(r['period'])}</td>"
        f"<td>{r['cet1']:.2%}</td><td>{r['leverage']:.2%}</td>"
        f"<td>{r['lcr']:.2f}</td><td>{r['nsfr']:.2f}</td>"
        f"<td>{r['icaap']:.2f}</td><td>{r['delta_eve']:.1%}</td>"
        f"<td>{r['psi']:.3f}</td><td>{r['hhi']:.3f}</td></tr>" for r in panel)

    body = f"""
<p>본 페이지는 4분기 합성 panel 기반 추세 차트 모음이다 — 자본/유동성/
내부자본/IRRBB/신용 PSI/집중도 의 분기간 변동. 본 panel 은
<code>tools.sample_generators.quarterly_panel</code> 가 결정론적으로 생성한
시드 (seed=31) 이며 실제 운영 데이터가 아니다. 운영 데이터 연계 시 본
페이지가 동일 schema 로 분기 시계열을 표시한다.</p>

<div style="display:flex;flex-wrap:wrap;gap:1rem">
{grid}
</div>

<h2>분기별 수치 (요약 표)</h2>
<table>
<tr><th>분기</th><th>CET1</th><th>Leverage</th><th>LCR</th><th>NSFR</th>
<th>ICAAP</th><th>ΔEVE/Tier1</th><th>PSI</th><th>HHI</th></tr>
{rows}
</table>

<h2>해석 — CRO 관점</h2>
<ul>
<li><b>드리프트 식별</b>: 단일 분기 점검은 점(point) 관점, panel 은 추세
(trend) 관점. red dashed line 은 규제·정책 최소/한도.</li>
<li><b>임계 근접 분기</b>: 차트의 빨간 점은 임계 위반 (현재 값 &lt; 최소 또는
&gt; outlier 기준). 위반 직전 분기에서 원인 분석 + ALCO/MRMC 보고 트리거.</li>
<li><b>본 panel 은 합성</b>: 실제 추세 의사결정은 운영 panel + 인간 검증자
정성 판단 + MRMC 검토 후 (HITL).</li>
</ul>
<p><a href="index.html">← 요약으로</a> · <a href="executive.html">경영진 보고서로</a></p>
"""
    return _page("추세 — 4분기 panel 비교 (합성)", body)


def _capital_buffer_deep_page(demo: dict, request: dict) -> str:
    """자본 buffer 분해 deep — Pillar 1 / 자본보전 / 경기대응 / D-SIB."""
    cap = _step_row(demo, "3.capital")
    cet1_min_pillar1 = 0.045
    cap_conservation = 0.025
    ccyb = float(request.get("capital_ccyb", 0.0) or 0.0)
    dsib = float(request.get("capital_dsib", 0.0) or 0.0)
    cet1_required = cet1_min_pillar1 + cap_conservation + ccyb + dsib

    cet1 = float(request.get("capital_cet1", 0) or 0)
    tier1 = float(request.get("capital_tier1", cet1) or cet1)
    total = float(request.get("capital_total", tier1) or tier1)

    stack = hbar(
        [
            ("Pillar 1 (4.5%)", cet1_min_pillar1),
            ("자본보전 (2.5%)", cap_conservation),
            ("경기대응 (CCyB)", ccyb),
            ("D-SIB 가산", dsib),
        ],
        title="CET1 요구 buffer 구성 (합계 = 요구 비율)", fmt="{:.2%}",
        vline=cet1, vline_label=f"실제 CET1 {cet1:.2%}")

    ratios_chart = hbar(
        [("CET1", cet1), ("Tier1", tier1), ("총자본", total)],
        title="자본 비율 vs 요구", fmt="{:.2%}",
        colors=[
            PALETTE["fail" if cet1 < cet1_required else "ok"],
            PALETTE["fail" if tier1 < cet1_required + 0.015 else "ok"],
            PALETTE["fail" if total < cet1_required + 0.03 else "ok"],
        ])

    # 시나리오 sensitivity (-50/-100/-150 bps)
    sens_rows = []
    for shock_bps in (0, -50, -100, -150):
        shock = shock_bps / 10000
        new_cet1 = cet1 + shock
        ok = new_cet1 >= cet1_required
        sens_rows.append(
            f"<tr><td>{shock_bps:+d} bps</td><td>{new_cet1:.2%}</td>"
            f"<td>{'<b style=color:#c62828>fail</b>' if not ok else 'ok'}</td></tr>")

    body = f"""
<p>본 페이지는 CET1 요구비율의 buffer 구성과 실제 비율의 sensitivity 를
분해한다. 출처: BCBS d189 (Basel III) + 시행세칙 [별표 3].</p>
{stack}
<h2>비율 비교</h2>
{ratios_chart}
<h2>Sensitivity — CET1 충격</h2>
<table><tr><th>충격</th><th>충격 후 CET1</th><th>판정</th></tr>{"".join(sens_rows)}</table>
<h2>구성 요약</h2>
{_kv_table([
    ("실제 CET1", f"{cet1:.2%}"),
    ("실제 Tier1", f"{tier1:.2%}"),
    ("실제 총자본", f"{total:.2%}"),
    ("CET1 요구 (buffer 포함)", f"{cet1_required:.2%}"),
    ("buffer 여유 (CET1 − 요구)", f"{(cet1 - cet1_required):+.2%}"),
    ("판정", cap["detail"]),
])}
<p><a href="capital_icaap.html">← 자본 + ICAAP 상세로 돌아가기</a></p>
"""
    return _page("심화 — 자본 buffer 분해 + sensitivity", body)


def _icaap_deep_page(demo: dict) -> str:
    """ICAAP 리스크 유형별 분해 + 스트레스 단계."""
    icaap = _step_row(demo, "3.icaap")
    o = icaap["outputs"]
    if not o:
        return _page("심화 — ICAAP 분해",
                     "<p>ICAAP 입력 미제공.</p>")
    shares = o.get("risk_shares", {})
    chart = hbar(
        [(k, v) for k, v in sorted(shares.items(), key=lambda x: -x[1])],
        title="필요내부자본 리스크 구성 (분산효과 차감 전)", fmt="{:.1%}",
        vline=0.60, vline_label="단일 리스크 경고 60%")

    ratio = o.get("ratio", 0)
    post = o.get("post_stress_ratio")
    stages = [
        ("baseline", ratio, "ok" if ratio >= 1.20 else "warning" if ratio >= 1.0 else "fail"),
    ]
    if post is not None:
        stages.append((
            "post-stress",
            post,
            "ok" if post >= 1.05 else "warning" if post >= 1.0 else "fail"))
        # 추가: 가정적 severe 시나리오 (-15% 가용)
        severe = ratio * 0.85
        stages.append((
            "severe (−15% 가용 자본 가정)", severe,
            "ok" if severe >= 1.0 else "warning" if severe >= 0.95 else "fail"))

    stage_chart = hbar(
        [(label, v) for label, v, _ in stages],
        title="ICAAP 비율 단계", fmt="{:.3f}",
        vline=1.0, vline_label="min 1.00",
        colors=[PALETTE[c] for _, _, c in stages])

    findings = o.get("findings", [])
    findings_html = "".join(f"<li>{_esc(f)}</li>" for f in findings) or "<li>없음</li>"

    body = f"""
<p>본 페이지는 필요내부자본의 리스크 유형별 분해와, 가용내부자본의 단계별
sensitivity 를 보인다. 출처: BCBS SRP20/30 + 시행세칙 내부자본적정성.</p>
{chart}
<h2>비율 단계 sensitivity</h2>
{stage_chart}
<p>severe 시나리오는 가용 내부자본 −15% 가정 (참고 시뮬레이션). 실제 자본계획
시나리오는 ALCO/MRMC 검토 후 적용.</p>
<h2>발견 사항 (정책 SSoT 기반)</h2>
<ul>{findings_html}</ul>
<h2>구성 요약</h2>
{_kv_table([
    ("내부자본비율 (baseline)", f"{ratio:.3f}"),
    ("스트레스 후 비율", f"{post:.3f}" if post is not None else "-"),
    ("필요내부자본 합계 (분산 차감 후)", f"{o.get('required_total', 0):,.0f}"),
    ("분산효과 차감 비중", f"{o.get('diversification_share', 0):.1%}"),
    ("누락 리스크 유형", ", ".join(o.get("missing_risk_types", [])) or "없음"),
])}
<p><a href="capital_icaap.html">← 자본 + ICAAP 상세로 돌아가기</a></p>
"""
    return _page("심화 — ICAAP 리스크 유형 분해 + 시나리오", body)


def _operational_deep_page(demo: dict, request: dict) -> str:
    """운영리스크 SMA — BI 구성·BIC 구간·국내 ILM=1 가정."""
    op = _step_row(demo, "3.operational")
    o = op["outputs"]
    bi = float(o.get("bi", 0) or 0)
    bic = float(o.get("bic_eur_bn", 0) or 0)
    orc = float(o.get("orc_eur_bn", 0) or 0)

    # BIC 구간 (BCBS OPE25): BI ≤ 1 → 12%, 1~30 → 15%, > 30 → 18%
    rows = [
        ("0 ~ 1bn", "12%", min(bi, 1.0) * 0.12),
        ("1bn ~ 30bn", "15%", max(0, min(bi, 30.0) - 1.0) * 0.15),
        (">30bn", "18%", max(0, bi - 30.0) * 0.18),
    ]
    bic_chart = hbar(
        [(label, contrib) for label, _, contrib in rows],
        title="BIC 구간별 기여 (단위: bn)", fmt="{:,.4f}")

    table = "".join(
        f"<tr><td>{_esc(label)}</td><td>{_esc(rate)}</td>"
        f"<td>{contrib:,.4f} bn</td></tr>" for label, rate, contrib in rows)

    body = f"""
<p>본 페이지는 SMA (Standardized Measurement Approach, BCBS OPE25) 의
Business Indicator 와 BIC 구간 기여를 분해한다. 국내 기준 ILM=1 (감독원 기본
가정 — 자체 10년 ILDC 사용 시 ≠ 1).</p>
{bic_chart}
<h2>BIC 구간 표</h2>
<table><tr><th>구간</th><th>marginal rate</th><th>기여</th></tr>{table}</table>
<h2>SMA 산식</h2>
<table>
<tr><th>BI (Business Indicator)</th><td>{bi:,.2f} bn</td></tr>
<tr><th>BIC (Σ 구간별 기여)</th><td>{bic:,.4f} bn</td></tr>
<tr><th>ILM (국내 기준)</th><td>1.0</td></tr>
<tr><th>ORC = BIC × ILM</th><td>{orc:,.4f} bn</td></tr>
</table>
<h2>해석 (CRO 관점)</h2>
<ul>
<li>BI 구성: 이자/리스/배당 + 서비스(수수료) + 재무(트레이딩 손익). 본 페이지의
BI 값은 합성 입력이며, 운영 시스템에서는 BCBS OPE25 5조 정의대로 산출.</li>
<li>국내 ILM=1 은 보수적 기본값. 자체 ILDC 도입 시 모형 승인 + 매니페스트 기록
필요.</li>
<li>operational loss 시나리오 (rogue trader / IT 장애 / 외부 사기) 별 sensitivity 는
별도 시나리오 분석 영역.</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로 돌아가기</a></p>
"""
    return _page("심화 — 운영리스크 SMA 분해", body)


def _ccr_deep_page(demo: dict, request: dict) -> str:
    """SA-CCR EAD = α × (RC + PFE) 분해."""
    ccr = _step_row(demo, "3.ccr")
    o = ccr["outputs"]
    alpha = float(o.get("alpha", 1.4))
    ead = float(o.get("ead", 0) or 0)
    rc = float(request.get("ccr_rc", 0) or 0)
    pfe = float(request.get("ccr_pfe", 0) or 0)
    chart = hbar(
        [("RC (Replacement Cost)", rc),
         ("PFE (Potential Future Exposure)", pfe),
         ("α × (RC+PFE) = EAD", ead)],
        title="SA-CCR EAD 분해", fmt="{:,.2f}",
        colors=[PALETTE["neutral"], PALETTE["neutral"], PALETTE["ok"]])

    body = f"""
<p>SA-CCR (Basel CRE52): EAD = α × (RC + PFE). α = 1.4 (감독자 보수성).</p>
{chart}
<h2>구성 요약</h2>
{_kv_table([
    ("Replacement Cost (RC)", f"{rc:,.2f}"),
    ("Potential Future Exposure (PFE)", f"{pfe:,.2f}"),
    ("α (감독자 보수성 계수)", f"{alpha}"),
    ("EAD = α × (RC + PFE)", f"{ead:,.2f}"),
])}
<h2>해석 (검증 관점)</h2>
<ul>
<li><b>RC</b>: 거래상대방 디폴트 시 즉시 실현 손실 (현재 시장가).</li>
<li><b>PFE</b>: 미래 잠재 익스포저 — netting set · asset class · supervisory factor
기반 add-on. 실제 산정은 트레이딩 시스템에서 수행.</li>
<li><b>α = 1.4</b>: BCBS 감독자 보수성. 내부 모형(IMM) 승인 시에도 동일 적용.</li>
<li><b>Wrong-Way Risk</b>: 거래상대방 신용도 하락이 동시에 RC 증가로 이어지는
경우 — 별도 식별 + α 조정 가능 (식별/처리는 본 자동 점검 범위 밖).</li>
</ul>
<p><a href="market_ops.html">← 시장·운영·CVA·CCR 상세로 돌아가기</a></p>
"""
    return _page("심화 — SA-CCR EAD 분해", body)


def _explainability_page() -> str:
    """전 부문 임계 근거·산식·출처 모음 — 검증자/감독 검토용."""
    from tools.explainability import load_attributions

    attrs = load_attributions()
    rows = "".join(
        f'<tr><td><code>{_esc(a["step"])}</code></td>'
        f'<td><b>{_esc(a["metric"])}</b></td>'
        f'<td><code>{_esc(a["formula"])}</code></td>'
        f'<td>{_esc(a["minimum"])}</td>'
        f'<td>{_esc(a["source"])}</td>'
        f'<td>{_esc(a["interpretation"])}</td>'
        f'<td><code>{_esc(a["policy_ssot"])}</code></td></tr>'
        for a in attrs)
    body = f"""
<p>각 부문 임계의 규제 출처(BCBS / 시행세칙 / 은행법) 와 산식 모음. 본 페이지는
SSoT <code>harness/explainability_attributions.json</code> 에서 자동 생성되며
임계 자체는 임의 완화 대상이 아닙니다 (CLAUDE.md §5).</p>
<table>
<tr><th>step</th><th>지표</th><th>산식</th><th>최소/임계</th><th>출처</th>
<th>해석</th><th>정책 파일</th></tr>
{rows}
</table>
<h2>해석 가이드</h2>
<ul>
<li><b>출처(Source)</b>: BCBS d/SRP/MAR/LIQ/CRE/LEX/OPE 번호 = Bank for International
Settlements 공식 표준. 시행세칙 = 금융감독원 은행업감독업무시행세칙.</li>
<li><b>정책 SSoT</b>: 실제 수치 임계가 저장된 JSON. 변경 시 매니페스트 CHG 항목
필수 (CLAUDE.md §4.3).</li>
<li><b>임의 완화</b>: 임계를 우회/완화하는 변경은 금지. 변경이 필요하면 MRMC
승인 + 매니페스트 + 감독원 사전 협의.</li>
</ul>
"""
    return _page("Explainability — 임계 근거·산식·출처 SSoT", body)


def _data_quality_page(demo: dict) -> str:
    rows = ""
    for sid in ("2.schema", "2.safety", "2.leakage", "2.date", "2.dup", "2.sample"):
        r = _step_row(demo, sid)
        rows += (f"<tr><td><code>{sid}</code></td><td>{_badge(r['status'])}</td>"
                 f"<td>{_esc(r['detail'])}</td></tr>")
    body = f"""
<p>입력 데이터 사전점검 6종 — 스키마 / 민감정보 / 누수 / 일자 / 중복 / 표본.</p>
<table><tr><th>Step</th><th>판정</th><th>상세</th></tr>{rows}</table>
<h2>심화 분석 (Drill-down)</h2>
<ul>
<li><a href="data_quality_deep.html">컬럼별 dtype·결측·분포·등급별 부도율 →</a></li>
</ul>
"""
    return _page("데이터 품질 상세 보고서", body)


# ---------------- 경영진 보고서 (executive) ----------------

def _executive_page(demo: dict, prov: dict | None) -> str:
    from tools.executive_insights import (
        domain_rows,
        kpi_cards,
        top_risks_and_actions,
    )

    summary = demo["summary"]
    rows = domain_rows(demo)
    risks, actions = top_risks_and_actions(demo, n=3)
    cards = kpi_cards(demo)

    # 핵심 헤드라인
    n_fail = sum(1 for _, st, _, _ in rows if st == "fail")
    n_warn = sum(1 for _, st, _, _ in rows if st == "warning")
    n_ok = sum(1 for _, st, _, _ in rows if st == "ok")
    headline = (
        f"15개 부문 점검 결과: <b>fail {n_fail}</b> · "
        f"<b>warning {n_warn}</b> · ok {n_ok}. "
        + ("Escalation 발동 — 인간 검증자/MRMC 보고 필요." if summary["escalated"]
           else "Escalation 미발동 — 자동 점검 한정 위험 미식별."))

    risks_html = "".join(
        f'<li><b>{_esc(r["label"])}</b> '
        f'<span class="badge" style="background:{PALETTE[r["status"]]}">'
        f'{_esc(r["status"])}</span> — {_esc(r["detail"])} '
        f'(<a href="{r["link"]}">drill-down →</a>)</li>'
        for r in risks) or "<li>식별된 fail/warning 없음 — 표준 모니터링 유지.</li>"
    actions_html = "".join(
        f"<li><b>{_esc(a['label'])}</b> — {_esc(a['action'])}</li>"
        for a in actions) or "<li>추가 권고 없음.</li>"

    esc_block = ""
    esc = _step_row(demo, "9.escalate")
    if esc["status"] != "skipped" and esc["outputs"].get("triggered_by"):
        esc_block = (
            f'<div style="background:#ffebee;border-left:4px solid #c62828;'
            f'padding:.6rem 1rem;margin:1rem 0">'
            f'<b style="color:#c62828">⚠ Escalation 발생</b> — '
            f'trigger: {_esc(", ".join(esc["outputs"]["triggered_by"]))}<br>'
            f'대응: 인간 검증자(검증팀장) → MRMC 보고 → 매니페스트 CHG 기록 '
            f'(HITL). 본 보고서는 보조 자료이며 의견 확정은 인간 결정.</div>')

    body = f"""
<p style="font-size:1.05rem">{headline}</p>
{esc_block}
<h2>핵심 KPI</h2>
{kpi_card_strip(cards)}
<h2>부문별 위험 히트맵</h2>
{heatmap(rows, title="")}
<h2>Top 3 위험 (자동 점검 기준)</h2>
<ol>{risks_html}</ol>
<h2>Top 3 권고 (정책 SSoT 매핑, 임의 완화 금지)</h2>
<ol>{actions_html}</ol>
<h2>경영진 시야 — 의사결정 노트</h2>
<ul>
<li><b>자동 점검의 권한:</b> 본 시스템은 점검 결과만 제시한다. 모형 승인/
부적합 의견 / 자본 계획 / 감독기관 대응 문안 확정은 인간 검증자 + MRMC 영역
(CLAUDE.md §5, §7).</li>
<li><b>재현성:</b> 모든 수치는 footer 의 입력 해시·정책 버전·재실행 명령으로
재산출 가능. 정책 버전이 바뀌면 동일 입력에서도 판정이 달라질 수 있음.</li>
<li><b>합성 데이터:</b> 본 산출물은 합성 데이터 기반 데모. 운영 데이터 실행 시
매니페스트 CHG 기록 + 운영 보고 별도 절차.</li>
</ul>
<h2>인접 보고서</h2>
<ul>
<li><a href="index.html">검증자 요약 보고서 (step 단위)</a></li>
<li><a href="capital_icaap.html">자본 + 내부자본(ICAAP) 상세</a></li>
<li><a href="alm.html">ALM 상세 (유동성·만기갭·IRRBB)</a></li>
<li><a href="explainability.html">Explainability — 임계 근거·산식·출처</a></li>
<li><a href="trends.html">추세 — 4분기 panel 비교 (합성)</a></li>
<li><a href="macro_overlay.html">Macroprudential — 거시건전성 overlay</a></li>
<li><a href="stress_test.html">스트레스 테스트 시나리오 panel</a></li>
<li><a href="ifrs9_deep.html">IFRS 9 ECL Stage Migration</a></li>
<li><a href="ifrs9_fli_deep.html">IFRS 9 FLI overlay + 가중 ECL + PMA</a></li>
<li><a href="change_audit.html">변경 감사 (Change Manifest)</a></li>
</ul>
"""
    title = "경영진 보고서 — CRO 시야 (DRAFT)"
    return _page(title, body, crumb=False)


# ---------------- 요약 (index) ----------------

_DOMAINS = [
    ("credit.html", "신용평가모형", ["3.disc", "3.psi", "3.cal"]),
    ("capital_icaap.html", "자본 + 내부자본(ICAAP)", ["3.capital", "3.icaap"]),
    ("alm.html", "ALM (유동성·만기갭·IRRBB)", ["3.liquidity", "3.alm", "3.irrbb"]),
    ("market_ops.html", "시장 · 운영 · CVA · CCR",
     ["3.market", "3.operational", "3.cva", "3.ccr"]),
    ("concentration.html", "신용집중", ["3.conc"]),
    ("data_quality.html", "데이터 품질", ["2.schema", "2.safety", "2.leakage",
                                      "2.date", "2.dup", "2.sample"]),
]


def _worst(demo: dict, sids: list[str]) -> str:
    order = ["fail", "warning", "ok", "simulated", "skipped"]
    statuses = [_step_row(demo, sid)["status"] for sid in sids]
    for s in order:
        if s in statuses:
            return s
    return "skipped"


def _index_page(demo: dict) -> str:
    s = demo["summary"]
    cards = ""
    for href, name, sids in _DOMAINS:
        worst = _worst(demo, sids)
        items = "".join(
            f"<li><code>{sid}</code> {_badge(_step_row(demo, sid)['status'])}</li>"
            for sid in sids)
        cards += (f'<div class="card"><h3><a href="{href}">{_esc(name)}</a></h3>'
                  f"{_badge(worst)}<ul>{items}</ul></div>")
    esc = _step_row(demo, "9.escalate")
    esc_html = ""
    if esc["status"] != "skipped" and esc["outputs"].get("triggered_by"):
        esc_html = (
            '<h2 style="color:#c62828">Escalation 발생</h2>'
            f"<p>trigger: {_esc(', '.join(esc['outputs']['triggered_by']))} → "
            "인간 검증자 / MRMC 보고 필요.</p>")
    body = f"""
<p><b><a href="executive.html">→ 경영진 보고서 (CRO 시야)</a></b> · 본 페이지는 검증자 시야 (step 단위)</p>
{status_donut(s["status_counts"], title="step 판정 분포")}
{_kv_table([("표본 수 (합성)", f"{demo['n_rows']:,}"),
            ("모드", "stress" if demo['stress_mode'] else "정상"),
            ("plan / 실행 step", f"{s['n_planned']} / {s['n_executed']}"),
            ("escalation", "발생" if s['escalated'] else "없음"),
            ("실행 시간", f"{demo['elapsed_sec']}초")])}
{esc_html}
<h2>부문별 상세 보고서</h2>
<div class="cards">{cards}</div>
<h2>심화 보고서 (Drill-down)</h2>
<ul>
<li><a href="credit_calibration.html">신용 — 등급별 캘리브레이션</a></li>
<li><a href="credit_segments.html">신용 — 세그먼트별 변별력 + ROC + 분포</a></li>
<li><a href="credit_vintage.html">신용 — Vintage cohort 분석</a></li>
<li><a href="challenger.html">신용 — 챔피언 vs 챌린저 비교</a></li>
<li><a href="data_quality_deep.html">데이터 — 컬럼·결측·분포 분석</a></li>
<li><a href="capital_buffer_deep.html">자본 — buffer 분해 + sensitivity</a></li>
<li><a href="capital_rwa_deep.html">자본 — RWA 분해 + Output Floor + SREP</a></li>
<li><a href="icaap_deep.html">ICAAP — 리스크 유형 분해 + 시나리오</a></li>
<li><a href="alm_gap.html">ALM — 만기 bucket 누적 갭</a></li>
<li><a href="alm_irrbb.html">IRRBB — 시나리오별 ΔEVE</a></li>
<li><a href="alm_currency_deep.html">ALM — 통화별 LCR + ΔNII + 일중유동성</a></li>
<li><a href="irrbb_behavioral.html">IRRBB — Behavioral assumption (NMD/prepayment) + Duration gap</a></li>
<li><a href="market_backtest_deep.html">시장 — VaR backtest P&amp;L (250일)</a></li>
<li><a href="market_components_deep.html">시장 — VaR 구성요소 (General/Specific) + SVaR + IRC</a></li>
<li><a href="concentration_segments.html">집중 — 산업/지역/통화별 + Top 10 exposures</a></li>
<li><a href="operational_deep.html">운영 — SMA BI 구성·BIC 구간</a></li>
<li><a href="operational_bi_deep.html">운영 — BI 5 component + 10년 ILDC 시계열</a></li>
<li><a href="op_scenario_deep.html">운영 — 손실 시나리오 (BCBS 7 event class)</a></li>
<li><a href="cva_deep.html">CVA — counterparty 분해 (BA-CVA / SA-CVA)</a></li>
<li><a href="ccr_deep.html">CCR — SA-CCR EAD 분해</a></li>
<li><a href="ccr_netting_deep.html">CCR — Netting set + Wrong-Way Risk + 담보</a></li>
<li><a href="macro_overlay.html">Macroprudential — CCyB/DSR/LTV/SyRB overlay</a></li>
<li><a href="ifrs9_deep.html">IFRS 9 — Stage migration matrix + ECL 분해</a></li>
<li><a href="ifrs9_fli_deep.html">IFRS 9 — FLI overlay + 가중 ECL + PMA</a></li>
<li><a href="stress_test.html">스트레스 테스트 — baseline / adverse / severe</a></li>
<li><a href="change_audit.html">변경 감사 — 매니페스트 CHG 추적</a></li>
<li><a href="explainability.html">Explainability — 전 부문 임계 근거·산식·출처</a></li>
<li><a href="trends.html">추세 — 4분기 panel 비교 (합성)</a></li>
</ul>
"""
    title = ("검증 요약 보고서 — stress / escalation"
             if demo["stress_mode"] else "검증 요약 보고서 — 정상 case")
    return _page(title, body, crumb=False)


# ---------------- 빌더 / CLI ----------------

def build_pack(
    demo: dict,
    request: dict,
    out_dir: str | Path,
    *,
    provenance: dict | None = None,
) -> list[Path]:
    """보고서 팩을 생성하고 생성 파일 목록을 반환한다.

    ``provenance`` 가 주어지면 모든 페이지 footer 직전에 동일한 재현가능성
    카드가 삽입된다 (CRO 요구: 모든 산출값 재현·설명 가능). 카드 부재는
    빌드 시점 assert 로 차단된다 — provenance=None 이면 R37 호환 모드.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pages: dict[str, str] = {
        "executive.html": _executive_page(demo, provenance),
        "index.html": _index_page(demo),
    }
    pages.update(_credit_pages(demo, request))
    pages["capital_icaap.html"] = _capital_icaap_page(demo)
    pages.update(_alm_pages(demo, request))
    pages["market_ops.html"] = _market_ops_page(demo)
    pages["concentration.html"] = _concentration_page(demo)
    pages["data_quality.html"] = _data_quality_page(demo)
    pages["explainability.html"] = _explainability_page()
    # 부문별 심화 deep-dive (Round 41)
    pages["trends.html"] = _trends_page()
    pages["challenger.html"] = _challenger_page(request)
    pages["data_quality_deep.html"] = _data_quality_deep_page(request)
    pages["credit_segments.html"] = _credit_segments_page(request)
    pages["credit_vintage.html"] = _credit_vintage_page(request)
    pages["cva_deep.html"] = _cva_deep_page(request)
    pages["market_backtest_deep.html"] = _market_backtest_deep_page(demo)
    pages["op_scenario_deep.html"] = _op_scenario_deep_page()
    pages["macro_overlay.html"] = _macro_overlay_page()
    pages["ifrs9_deep.html"] = _ifrs9_deep_page()
    pages["stress_test.html"] = _stress_test_page()
    pages["change_audit.html"] = _change_audit_page()
    pages["capital_buffer_deep.html"] = _capital_buffer_deep_page(demo, request)
    pages["capital_rwa_deep.html"] = _capital_rwa_deep_page()
    pages["alm_currency_deep.html"] = _alm_currency_deep_page()
    pages["market_components_deep.html"] = _market_components_deep_page()
    pages["concentration_segments.html"] = _concentration_segments_page()
    pages["irrbb_behavioral.html"] = _irrbb_behavioral_page()
    pages["operational_bi_deep.html"] = _operational_bi_deep_page()
    pages["ccr_netting_deep.html"] = _ccr_netting_deep_page()
    pages["ifrs9_fli_deep.html"] = _ifrs9_fli_page()
    pages["icaap_deep.html"] = _icaap_deep_page(demo)
    pages["operational_deep.html"] = _operational_deep_page(demo, request)
    pages["ccr_deep.html"] = _ccr_deep_page(demo, request)

    prov_card = _render_provenance_card(provenance) if provenance else ""
    written = []
    for name, content_html in pages.items():
        assert "[DRAFT" in content_html, f"{name}: DRAFT 워터마크 누락"
        if prov_card:
            content_html = content_html.replace("<footer>", prov_card + "<footer>", 1)
            assert "Reproducibility" in content_html, (
                f"{name}: 재현가능성 카드 삽입 실패")
        p = out / name
        p.write_text(content_html, encoding="utf-8")
        written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="계층형 HTML 검증 보고서 팩 생성")
    parser.add_argument("--n", type=int, default=100_000)
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    from tools.provenance import build_provenance
    from tools.run_workflow_demo import build_request, run_demo

    log_dir = args.log_dir or (Path(__file__).resolve().parent.parent / "logs")
    demo = run_demo(args.n, args.stress, args.seed, log_dir)
    request = build_request(args.n, stress=args.stress, seed=args.seed)
    prov = build_provenance(request, n=args.n, seed=args.seed, stress=args.stress)
    written = build_pack(demo, request, args.out, provenance=prov)
    for p in written:
        sys.stdout.write(f"{p}\n")
    sys.stdout.write(f"보고서 팩 {len(written)}개 페이지 생성: {args.out}/index.html\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
