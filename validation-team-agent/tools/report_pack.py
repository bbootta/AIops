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

from tools.svg_charts import PALETTE, gauge, hbar, status_donut

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
"""

_STATUS_KO = {"ok": "정상", "warning": "주의", "fail": "위반", "skipped": "생략",
              "simulated": "시뮬레이션"}


def _esc(s: object) -> str:
    return _html.escape(str(s))


def _badge(status: str) -> str:
    return (f'<span class="badge" style="background:{PALETTE.get(status, "#888")}">'
            f"{_esc(status)} · {_STATUS_KO.get(status, status)}</span>")


def _page(title: str, body: str, *, crumb: bool = True) -> str:
    nav = '<div class="crumb"><a href="index.html">← 요약 보고서</a></div>' if crumb else ""
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>{_esc(title)}</title>
<style>{_CSS}</style></head><body>
{DRAFT_BANNER}
{nav}<h1>{_esc(title)}</h1>
{body}
<footer>생성: tools/report_pack.py — 합성 데이터 / 외부 호출 없음.
본 보고서는 검증 보조 산출물 초안이며 최종 검증 의견과 외부 제출은 인간
검증자의 검토와 승인을 거쳐야 합니다.</footer>
</body></html>"""


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
{charts}
<h2>안정성 (PSI)</h2>{psi_g}
<p>기준: &lt; 0.10 안정 · 0.10~0.25 주의 · ≥ 0.25 불안정 (참고 임계).</p>
<h2>캘리브레이션 요약</h2>
{_kv_table([("등급 수", cal['outputs'].get('n_grades', '-')),
            ("reject 등급 수 (binomial, Holm)", cal['outputs'].get('n_reject', '-')),
            ("상세", '<a href="credit_calibration.html">등급별 심화 보고서 →</a>')])}
<h2>표본 적정성</h2>
{_kv_table([("표본 수", f"{demo['n_rows']:,}"),
            ("판정", _step_row(demo, '2.sample')['detail'])])}
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
            ("alpha", ccr['outputs'].get('alpha', '-'))])}
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
"""
    return _page("신용집중리스크 상세 보고서", body)


def _data_quality_page(demo: dict) -> str:
    rows = ""
    for sid in ("2.schema", "2.safety", "2.leakage", "2.date", "2.dup", "2.sample"):
        r = _step_row(demo, sid)
        rows += (f"<tr><td><code>{sid}</code></td><td>{_badge(r['status'])}</td>"
                 f"<td>{_esc(r['detail'])}</td></tr>")
    body = f"""
<p>입력 데이터 사전점검 6종 — 스키마 / 민감정보 / 누수 / 일자 / 중복 / 표본.</p>
<table><tr><th>Step</th><th>판정</th><th>상세</th></tr>{rows}</table>
"""
    return _page("데이터 품질 상세 보고서", body)


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
{status_donut(s["status_counts"], title="step 판정 분포")}
{_kv_table([("표본 수 (합성)", f"{demo['n_rows']:,}"),
            ("모드", "stress" if demo['stress_mode'] else "정상"),
            ("plan / 실행 step", f"{s['n_planned']} / {s['n_executed']}"),
            ("escalation", "발생" if s['escalated'] else "없음"),
            ("실행 시간", f"{demo['elapsed_sec']}초")])}
{esc_html}
<h2>부문별 상세 보고서</h2>
<div class="cards">{cards}</div>
<h2>심화 보고서</h2>
<ul>
<li><a href="credit_calibration.html">등급별 캘리브레이션</a></li>
<li><a href="alm_gap.html">만기 bucket 누적 갭</a></li>
<li><a href="alm_irrbb.html">IRRBB 시나리오별 ΔEVE</a></li>
</ul>
"""
    title = ("검증 요약 보고서 — stress / escalation"
             if demo["stress_mode"] else "검증 요약 보고서 — 정상 case")
    return _page(title, body, crumb=False)


# ---------------- 빌더 / CLI ----------------

def build_pack(demo: dict, request: dict, out_dir: str | Path) -> list[Path]:
    """보고서 팩을 생성하고 생성 파일 목록을 반환한다."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pages: dict[str, str] = {"index.html": _index_page(demo)}
    pages.update(_credit_pages(demo, request))
    pages["capital_icaap.html"] = _capital_icaap_page(demo)
    pages.update(_alm_pages(demo, request))
    pages["market_ops.html"] = _market_ops_page(demo)
    pages["concentration.html"] = _concentration_page(demo)
    pages["data_quality.html"] = _data_quality_page(demo)

    written = []
    for name, content_html in pages.items():
        assert "[DRAFT" in content_html, f"{name}: DRAFT 워터마크 누락"
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

    from tools.run_workflow_demo import build_request, run_demo

    log_dir = args.log_dir or (Path(__file__).resolve().parent.parent / "logs")
    demo = run_demo(args.n, args.stress, args.seed, log_dir)
    request = build_request(args.n, stress=args.stress, seed=args.seed)
    written = build_pack(demo, request, args.out)
    for p in written:
        sys.stdout.write(f"{p}\n")
    sys.stdout.write(f"보고서 팩 {len(written)}개 페이지 생성: {args.out}/index.html\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
