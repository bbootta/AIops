"""Executive (CRO/board) report — concise, insights-first, action-oriented.

One ~6-page HTML document with:
  1. Cover + verdict + RAF KRI scorecard
  2. Capital & liquidity at a glance (BIS · LCR · NSFR · IRRBB · ICAAP)
  3. Top 5 actions (auto-derived from non-GREEN KRIs + WARN/FAIL checks)
  4. Risk profile heatmap (sector × country) + concentration narrative
  5. Stress narrative — single-year + quarterly fan + reverse stress
  6. Climate & emerging risks summary
  7. Reproducibility footer (portfolio hash + manifest digest)

All numbers are clickable links into the operational report.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from risk_lib.pipeline import PipelineResult
from risk_lib import viz, viz_advanced
from risk_lib.html_report import (
    CSS, _won, _pct, _esc, _kpi, _badge, _table,
)
from risk_lib.references import (
    LCR_MIN, NSFR_MIN, IRRBB_OUTLIER_EVE_PCT_TIER1, LEVERAGE_MIN_RATIO,
)


# ---------------------------------------------------------------- helpers

def _fmt(value, fmt: str) -> str:
    if fmt == "pct":   return _pct(value, 2)
    if fmt == "ratio": return f"{value:.3f}"
    if fmt == "money": return _won(value)
    return str(value)


def _kri_card_data(raf) -> list[dict]:
    """Translate RAFReport.kris into the kri_scorecard input shape."""
    out = []
    for k in raf.kris:
        thresh_text = (f"board {_fmt(k.threshold.board, k.fmt)} · "
                       f"mgmt {_fmt(k.threshold.management, k.fmt)}")
        out.append({
            "name": k.name,
            "category": k.category,
            "actual_text": _fmt(k.actual, k.fmt),
            "grade": k.grade,
            "threshold_text": thresh_text,
        })
    return out


def _top_actions(result: PipelineResult, *, max_actions: int = 5) -> list[str]:
    """Auto-derive top action items from RAF breaches + WARN/FAIL checks +
    obviously stressed metrics."""
    actions = []
    # RAF — RED first, then AMBER
    for grade_target in ("RED", "AMBER", "WATCH"):
        for k in result.raf.kris:
            if k.grade != grade_target: continue
            verb = {"RED": "즉시 대응", "AMBER": "에스컬레이션",
                    "WATCH": "조기경보 모니터링"}[grade_target]
            actions.append(
                f"[{grade_target}] <b>{html.escape(k.name)}</b> {verb} — "
                f"실측 {_fmt(k.actual, k.fmt)} vs board 한계 "
                f"{_fmt(k.threshold.board, k.fmt)} "
                f"({_esc(k.category)}, {_esc(k.citation)})")
            if len(actions) >= max_actions: return actions
    # WARN / FAIL checks not already covered
    for c in result.validation.checks:
        if c.status == "PASS": continue
        actions.append(
            f"[{c.status}] <b>{html.escape(c.name)}</b> — {html.escape(c.detail)}")
        if len(actions) >= max_actions: return actions
    # If still room, mention sensitivity tail
    return actions


# ---------------------------------------------------------------- chrome

def _exec_page(title: str, body: str, meta_line: str) -> str:
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>{_esc(title)}</title><style>{CSS}
.cover-hero {{ padding:40px 28px 28px; background:linear-gradient(180deg,#1a2236 0%,#2d3a5a 100%); color:#f8fafc; }}
.cover-hero h1 {{ font-size:30px; margin:0 0 12px; letter-spacing:-0.01em; }}
.cover-hero p {{ margin:0; opacity:0.85; font-size:14px; }}
.verdict-banner {{ display:inline-block; padding:8px 18px; border-radius:8px;
  background:rgba(255,255,255,0.12); margin-top:14px; font-weight:600; font-size:16px; }}
.action-card {{ background:#fff; border:1px solid var(--line); border-left:4px solid var(--bad);
  padding:12px 16px; margin:8px 0; border-radius:0 6px 6px 0; }}
.action-card.amber {{ border-left-color: var(--warn); }}
.action-card.watch {{ border-left-color: #88a4c2; }}
.section-divider {{ height:2px; background:linear-gradient(90deg,var(--accent),transparent); margin:24px 0; }}
.nav-foot {{ background:#f3f4f6; padding:14px 20px; border-radius:8px; font-size:13px; }}
.nav-foot a {{ color:var(--accent); margin-right:14px; text-decoration:none; font-weight:600; }}
.nav-foot a:hover {{ text-decoration:underline; }}
.repro-footer {{ font-family:Menlo,Consolas,monospace; font-size:11px; color:var(--muted);
  background:#f9fafb; padding:10px 14px; border:1px solid var(--line); border-radius:6px; word-break:break-all; }}
</style></head>
<body>
<header class="cover-hero">
<h1>리스크관리 종합 보고서 — 경영진 요약</h1>
<p>{_esc(meta_line)}</p>
</header>
<div class="container">{body}</div>
<footer>risk_lib v0.4 · 경영진 보고서 (1-page exec) · 실무진 전체 보고서는 <a href="ops/index.html">ops/index.html</a></footer>
</body></html>"""


# ---------------------------------------------------------------- main builder

def build_executive(result: PipelineResult,
                    out_dir: str | Path,
                    *, manifest_digest: str = "") -> Path:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)

    v = result.validation; summ = v.summary()
    passes = v.passes()
    verdict_tone = "PASS" if passes else "FAIL"
    verdict_text = "결재 가능 (PASS)" if passes else "결재 불가 (FAIL 존재)"
    raf = result.raf
    raf_summ = raf.summary()
    raf_worst = raf.worst()

    bis = result.bis; lev = result.leverage
    lcr = result.alm["lcr"]; nsfr = result.alm["nsfr"]; irrbb = result.alm["irrbb"]

    # --- KRI scorecard
    scorecard = viz_advanced.kri_scorecard(_kri_card_data(raf))

    # --- top actions
    actions = _top_actions(result, max_actions=6)
    actions_html = "".join(
        f'<div class="action-card{" amber" if "[AMBER]" in a else (" watch" if "[WATCH]" in a else "")}">{a}</div>'
        for a in actions) or '<div class="callout good">조치 필요 항목 없음.</div>'

    # --- sector × country heatmap
    sc = result.concentration_deep["sector_country"]
    sectors = list(sc.index)
    countries = list(sc.columns)
    matrix = [[float(sc.loc[s, c]) for c in countries] for s in sectors]
    heat = viz_advanced.heatmap(
        sectors, countries, matrix,
        title="섹터 × 국가 EAD 노출 (조원)",
        value_fmt=lambda v: f"{v/1e12:.1f}", cell_label=True,
    )

    # --- stress fan
    qs = result.meta["quarters"]
    sp = result.stress_path
    base_path = sp[sp["scenario"] == "baseline"].sort_values("q_index")["cet1_ratio"].tolist()
    adv_path  = sp[sp["scenario"] == "adverse"].sort_values("q_index")["cet1_ratio"].tolist()
    sev_path  = sp[sp["scenario"] == "severely_adverse"].sort_values("q_index")["cet1_ratio"].tolist()
    if len(base_path) and len(adv_path) and len(sev_path):
        lower = [min(a, s) for a, s in zip(adv_path, sev_path)]
        upper = [max(b, a) for b, a in zip(base_path, adv_path)]
        fan = viz_advanced.fan_chart(
            qs, base_path, lower, upper,
            extra_series={"adverse": adv_path, "severely_adverse": sev_path},
            value_fmt=_pct, title="분기별 CET1 경로 — fan chart",
            reference_value=bis.required["cet1"],
            reference_label=f"요구 {_pct(bis.required['cet1'])}",
        )
    else:
        fan = "<p>경로 데이터 없음.</p>"

    # --- climate risk summary
    cl = result.climate
    cl_chart = viz.bar_chart(
        [l.scenario for l in cl.transition + cl.physical],
        [l.uplift for l in cl.transition + cl.physical],
        title="기후 시나리오별 ECL 증가분", value_fmt=_won,
        colors=[viz.AMBER]*len(cl.transition) + [viz.RED]*len(cl.physical),
    )

    # --- MDA card data
    from risk_lib.mda import compute_mda
    mda_result = compute_mda(
        bis.cet1_ratio, result.meta["capital"].cet1, bis.rwa,
        buffers={"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01},
    )
    mda_tone = "good" if not mda_result.in_breach else "bad"
    mda_text = ("자유로운 분배" if not mda_result.in_breach
                else f"분배제한 q{mda_result.buffer_quartile} ({_pct(mda_result.distributable_pct)})")

    # --- repro
    repro = (f"산출시각 {result.meta.get('asof', '-')} · seed {result.meta.get('seed')} · "
             f"포트폴리오 {int(result.portfolio_summary['n'].sum()):,}건 · "
             f"manifest digest {manifest_digest[:16] if manifest_digest else '-'}...")

    body = f"""
<h1 class="title">0. 최종 판정 {_badge(verdict_tone, verdict_tone)}</h1>
<p class="section-lead">{_esc(verdict_text)} — 자체검증 {summ.get('PASS',0)} PASS / {summ.get('WARN',0)} WARN / {summ.get('FAIL',0)} FAIL.
리스크 어페타이트(RAF) 최악 등급 <b>{_badge(raf_worst, raf_worst)}</b>
(분포: {", ".join(f"{k} {v}" for k, v in raf_summ.items())})</p>

<div class="card">
<h2>1. KRI 스코어카드 (Risk Appetite Framework)</h2>
<p class="section-lead">12개 핵심 지표를 board/management/operational 3단 한계로 채점.
RED는 board 한계 위반(즉시 대응), AMBER는 management 한계(에스컬레이션),
WATCH는 operational 조기경보, GREEN은 한계 이내.</p>
{scorecard}
</div>

<div class="card">
<h2>2. CRO 액션 — 즉시/단기 조치 사항 (상위 {len(actions)}건)</h2>
{actions_html}
</div>

<div class="row2">
<div class="card">
<h2>3-1. 자본적정성 한눈에</h2>
<div class="kpi-grid">
{_kpi("CET1", _pct(bis.cet1_ratio), sub=f"요구 {_pct(bis.required['cet1'])} · 잉여 {bis.surplus_shortfall['cet1']*100:+.2f}%p", tone="good" if bis.passes() else "bad")}
{_kpi("Tier1", _pct(bis.tier1_ratio))}
{_kpi("Total", _pct(bis.total_ratio))}
{_kpi("레버리지", _pct(lev.leverage_ratio), sub=f"요구 {_pct(LEVERAGE_MIN_RATIO)}", tone="good" if lev.passes() else "bad")}
{_kpi("ICAAP 사용률", _pct(result.icaap.utilisation,1), sub=result.icaap.grade, tone={"GREEN":"good","AMBER":"warn","RED":"bad"}[result.icaap.grade])}
{_kpi("MDA 분배 여력", mda_text, sub=f"CBR 초과 {_won(mda_result.excess_above_cbr)}" if not mda_result.in_breach else f"버퍼 부족 {_won(mda_result.buffer_shortfall)}", tone=mda_tone)}
</div>
</div>
<div class="card">
<h2>3-2. 유동성 한눈에</h2>
<div class="kpi-grid">
{_kpi("LCR", _pct(lcr.lcr,1), sub=f"기준 {_pct(LCR_MIN,0)}", tone="good" if lcr.passes() else "bad")}
{_kpi("NSFR", _pct(nsfr.nsfr,1), sub=f"기준 {_pct(NSFR_MIN,0)}", tone="good" if nsfr.passes() else "bad")}
{_kpi("IRRBB ΔEVE/Tier1", _pct(irrbb.worst_pct_tier1), sub=f"기준 ≤{_pct(IRRBB_OUTLIER_EVE_PCT_TIER1,0)} · {irrbb.worst_eve_scenario}", tone="good" if not irrbb.outlier() else "bad")}
{_kpi("LCR HQLA", _won(lcr.hqla_total))}
</div>
</div>
</div>

<div class="card">
<h2>4. 리스크 프로파일 — 섹터 × 국가 노출 매트릭스</h2>
{heat}
<p class="section-lead">색이 진할수록 노출 규모가 큽니다. 단일 셀이 전체의 8% 이상이면 집중리스크 부문 점검 필요.</p>
</div>

<div class="card">
<h2>5. 스트레스 시나리오 — 자본경로 narrative</h2>
{fan}
<p class="section-lead">기준선은 평상시 자본 진로, 음영 밴드는 adverse–severely adverse 시나리오의 자본 변동 폭.
점선이 요구 CET1 임계 — 침범 시 자본보전 트리거.</p>
<p class="section-lead">역스트레스: 현 자본구조가 임계 CET1까지 떨어지려면 심도 s=<b>{result.reverse_stress.critical_severity:.2f}</b>,
즉 GDP {result.reverse_stress.implied_gdp_shock:+.1%} + LGD +{result.reverse_stress.implied_lgd_addon:.1%}p 수준 충격.</p>
</div>

<div class="row2">
<div class="card">
<h2>6-1. 기후리스크 (전환 + 물리)</h2>
{cl_chart}
<p class="section-lead">최악 전환 시나리오: {_esc(cl.worst_transition)} ({_won(max(l.uplift for l in cl.transition))} ECL 증가).
최악 물리 시나리오: {_esc(cl.worst_physical)} ({_won(max(l.uplift for l in cl.physical))} ECL 증가).</p>
</div>
<div class="card">
<h2>6-2. 비신용 리스크 spotlight</h2>
<div class="kpi-grid">
{_kpi("CCR EAD (SA-CCR)", _won(result.ccr.ead_total) if result.ccr else "-",
       sub=f"{result.ccr.n_counterparties}개 거래상대방" if result.ccr else "")}
{_kpi("CVA 자본 (BA-CVA)", _won(result.ccr.cva_charge) if result.ccr else "-")}
{_kpi("운영손실 99.9% VaR (LDA)", _won(result.op_loss.var_99_9), sub=f"5년 등록 손실 연환산 {_won(result.op_loss.annual_total)}")}
{_kpi("기후 ECL uplift (최악)", _won(max(l.uplift for l in cl.transition + cl.physical)))}
</div>
</div>
</div>

<div class="card">
<h2>7. 실무진 deep-dive 진입점</h2>
<p>아래는 본 요약을 뒷받침하는 실무진 보고서(부문별 상세 + 모델 카드 + 출처) 진입점입니다.</p>
<div class="nav-foot">
<a href="ops/index.html">실무진 통합 인덱스</a>
<a href="ops/03_rwa.html">RWA 분해</a>
<a href="ops/04_capital.html">BIS·레버리지</a>
<a href="ops/05_ecl.html">IFRS9 ECL</a>
<a href="ops/35_sicr_detail.html">SICR 분해</a>
<a href="ops/36_pd_term_structure.html">PD 잔존기간</a>
<a href="ops/37_macro_scenario.html">거시 시나리오</a>
<a href="ops/38_provisioning_attribution.html">충당금 귀속</a>
<a href="ops/09_stress.html">스트레스</a>
<a href="ops/10_icaap.html">내부자본</a>
<a href="ops/11a_irrbb.html">IRRBB</a>
<a href="ops/11b_lcr.html">LCR</a>
<a href="ops/13_climate.html">기후리스크</a>
<a href="ops/14_ccr.html">CCR/CVA</a>
<a href="ops/15_op_loss.html">운영손실</a>
<a href="ops/16_sensitivity.html">민감도</a>
<a href="ops/17_model_risk.html">모형 카드</a>
<a href="ops/18_concentration_deep.html">집중리스크 deep-dive</a>
<a href="ops/19_raf.html">RAF 상세</a>
<a href="ops/20_pillar3.html">Pillar 3 공시</a>
<a href="ops/12_validation.html">자체검증</a>
<a href="ops/52_final_attestation.html"><b>최종 결재 attestation</b></a>
</div>
</div>

<div class="card">
<h2>8. 인쇄 / PDF 출력</h2>
<p class="section-lead">결재용 PDF 파일이 필요한 경우, <a href="printable.html"><b>printable.html</b></a>
을 브라우저에서 열고 <b>인쇄 (Ctrl/⌘+P)</b> → 대상 <b>PDF로 저장</b>을 선택하세요.
A4 1-pager 형태로 한글이 완벽히 렌더링됩니다.</p>
</div>

<div class="card">
<h2>9. 재현성 정보 (감사 추적)</h2>
<div class="repro-footer">{_esc(repro)}<br>
포트폴리오 SHA-256 / 파라미터·규제상수 스냅샷·코드 커밋 hash 는 ops/manifest.json 참조.<br>
재현 명령: <code>python -m risk_lib.cli reproduce --manifest manifest.json</code></div>
</div>
"""
    meta = (f"산출 기준 {result.meta.get('asof','-')} · seed {result.meta.get('seed')} · "
            f"규제 준거 Basel III + IFRS9 + 금감원 감독세칙")
    out_path = out / "executive.html"
    out_path.write_text(_exec_page("경영진 요약", body, meta), encoding="utf-8")
    return out_path
