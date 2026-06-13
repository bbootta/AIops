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
            ("상세", '<a href="alm_irrbb.html">시나리오 심화 →</a>'),
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
<li><a href="operational_deep.html">운영리스크 SMA — BI 구성·BIC 구간 →</a></li>
<li><a href="ccr_deep.html">SA-CCR EAD 분해 (RC + PFE × α) →</a></li>
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
<li><a href="challenger.html">신용 — 챔피언 vs 챌린저 비교</a></li>
<li><a href="data_quality_deep.html">데이터 — 컬럼·결측·분포 분석</a></li>
<li><a href="capital_buffer_deep.html">자본 — buffer 분해 + sensitivity</a></li>
<li><a href="icaap_deep.html">ICAAP — 리스크 유형 분해 + 시나리오</a></li>
<li><a href="alm_gap.html">ALM — 만기 bucket 누적 갭</a></li>
<li><a href="alm_irrbb.html">IRRBB — 시나리오별 ΔEVE</a></li>
<li><a href="operational_deep.html">운영 — SMA BI 구성·BIC 구간</a></li>
<li><a href="ccr_deep.html">CCR — SA-CCR EAD 분해</a></li>
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
    pages["capital_buffer_deep.html"] = _capital_buffer_deep_page(demo, request)
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
