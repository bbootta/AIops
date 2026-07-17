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
from risk_lib.abbreviations import abbr_dict_card_html
from risk_lib.page_registry import PAGES
from risk_lib.references import (
    LCR_MIN, NSFR_MIN, IRRBB_OUTLIER_EVE_PCT_TIER1, LEVERAGE_MIN_RATIO,
)


# ---------------------------------------------------------------- helpers

def _fmt(value, fmt: str) -> str:
    if fmt == "pct":   return _pct(value, 2)
    if fmt == "ratio": return f"{value:.3f}"
    if fmt == "money": return _won(value)
    return str(value)


def _kri_card_data(raf, *, seed: int | None = None) -> list[dict]:
    """Translate RAFReport.kris into the kri_scorecard input shape.

    `seed`를 주면 12개월 합성 back-history(현재값에 정합)를 스파크라인과
    추세 라벨로 붙인다 — seed 고정이므로 재현 가능.
    """
    spark_by_name: dict[str, Any] = {}
    if seed is not None:
        from risk_lib.timeseries import synth_history
        spark_by_name = {s.name: s for s in synth_history(raf, months=12, seed=seed)}
    out = []
    for k in raf.kris:
        thresh_text = (f"board {_fmt(k.threshold.board, k.fmt)} · "
                       f"mgmt {_fmt(k.threshold.management, k.fmt)}")
        row = {
            "name": k.name,
            "category": k.category,
            "actual_text": _fmt(k.actual, k.fmt),
            "grade": k.grade,
            "threshold_text": thresh_text,
        }
        s = spark_by_name.get(k.name)
        if s is not None:
            row["spark"] = list(s.values)
            row["trend"] = s.trend()
        out.append(row)
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


def briefing_facts(result: PipelineResult) -> dict:
    """CRO 브리핑의 원천 값 — 한/영 템플릿이 같은 유도값을 쓰도록 단일화.

    localization.build_english_board_pack의 영문 브리핑도 이 dict를 사용한다.
    """
    bis = result.bis
    comp = result.attribution["rwa_components"]
    topc = comp.loc[comp["share"].idxmax()]
    pit, ttc = float(result.macro_ecl.weighted_total), float(result.ecl["total"])
    conc = result.concentration
    top = conc.loc[conc["normalised_hhi"].idxmax()]
    sp = result.stress_path_trough
    sev_rows = sp[sp["scenario"] == "severely_adverse"]
    sev = None
    if len(sev_rows):
        s = sev_rows.iloc[0]
        sev = {
            "trough": float(s["trough_cet1"]),
            "trough_q": str(s["trough_quarter"]),
            "first_breach": (str(s["first_breach"])
                             if isinstance(s.get("first_breach"), str) else None),
            "end": float(s["end_cet1"]),
        }
    return {
        "cet1": float(bis.cet1_ratio),
        "cet1_surplus_pp": float(bis.surplus_shortfall["cet1"]) * 100,
        "top_rwa_component": str(topc["component"]),
        "top_rwa_share": float(topc["share"]),
        "pit": pit, "ttc": ttc,
        "gap_pct": (pit / ttc - 1) * 100 if ttc else 0.0,
        "conc_dim": str(top["dimension"]),
        "conc_hhi": float(top["hhi"]),
        "conc_top1": float(top["top1_share"]),
        "raf_red": [k.name for k in result.raf.kris if k.grade == "RED"],
        "raf_amber": [(k.name, _fmt(k.actual, k.fmt))
                      for k in result.raf.kris if k.grade == "AMBER"],
        "sev": sev,
        "rev_severity": float(result.reverse_stress.critical_severity),
        "rev_gdp": float(result.reverse_stress.implied_gdp_shock),
        "lcr": float(result.alm["lcr"].lcr),
        "nsfr": float(result.alm["nsfr"].nsfr),
    }


def _cro_briefing(result: PipelineResult) -> list[str]:
    """Deterministic CRO briefing — every sentence derives from briefing_facts
    (reproducible/explainable), each with a deep-dive link."""
    f = briefing_facts(result)
    out = []

    out.append(
        f"<b>자본</b> — CET1 {_pct(f['cet1'])}로 요구치 대비 "
        f"{f['cet1_surplus_pp']:+.2f}%p 여유. RWA의 최대 구성은 "
        f"<b>{_esc(f['top_rwa_component'])}</b>({f['top_rwa_share']*100:.0f}%)로, 자본비율 "
        f"방어의 1차 레버는 이 부문의 한도·성장 관리다. "
        f'<a href="ops/32_capital_stack.html">→ 자본 스택</a> · '
        f'<a href="ops/23_attribution.html">→ 귀속분석</a>')

    out.append(
        f"<b>충당금</b> — 확률가중 PIT ECL {_won(f['pit'])}은 TTC {_won(f['ttc'])} 대비 "
        f"<b>{f['gap_pct']:+.0f}%</b>. 거시 하방 시나리오 가중이 충당금을 끌어올리는 "
        f"국면으로, 분기 적립 계획에 선반영 필요. "
        f'<a href="ops/37_macro_scenario.html">→ 거시 시나리오</a> · '
        f'<a href="ops/38_provisioning_attribution.html">→ 충당금 귀속</a>')

    red_txt = (" RAF RED: " + ", ".join(_esc(n) for n in f["raf_red"]) + "."
               if f["raf_red"] else "")
    out.append(
        f"<b>집중리스크</b> — 최대 집중 차원은 <b>{_esc(f['conc_dim'])}</b> "
        f"(HHI {f['conc_hhi']:.3f}, 최대 버킷 점유 {f['conc_top1']*100:.0f}%)."
        f"{red_txt} 분산 없이는 스트레스 손실이 이 차원에 눌려 비선형으로 커진다. "
        f'<a href="ops/18_concentration_deep.html">→ 집중 deep-dive</a>')

    if f["sev"]:
        s = f["sev"]
        breach = (f"요구치 최초 침범 <b>{_esc(s['first_breach'])}</b>, "
                  if s["first_breach"] else "요구치 침범 없음, ")
        out.append(
            f"<b>스트레스 회복력</b> — severe 시나리오에서 CET1 저점 "
            f"<b>{_pct(s['trough'])}</b> ({_esc(s['trough_q'])}), "
            f"{breach}기말 {_pct(s['end'])}로 회복. 역스트레스 임계 "
            f"심도 s={f['rev_severity']:.2f} — 현 여력의 "
            f"소진에는 GDP {f['rev_gdp']:+.1%} 급 충격 필요. "
            f'<a href="ops/49_ccar_path.html">→ CCAR 경로</a> · '
            f'<a href="ops/48_reverse_stress_multi.html">→ 역스트레스</a>')

    out.append(
        f"<b>유동성</b> — LCR {_pct(f['lcr'],1)} / NSFR {_pct(f['nsfr'],1)} "
        f"(기준 각 {_pct(LCR_MIN,0)}). 기준 대비 여유는 있으나 LCR은 조기경보 "
        f"구간이므로 고유동성자산 buffer 소진 속도를 intraday로 모니터링. "
        f'<a href="ops/11b_lcr.html">→ LCR</a> · '
        f'<a href="ops/61_intraday.html">→ Intraday</a>')

    if f["raf_amber"]:
        out.append(
            f"<b>모형·기타 AMBER</b> — " +
            ", ".join(f"{_esc(n)} ({v})" for n, v in f["raf_amber"]) +
            ". 관리 한계 위반으로 에스컬레이션 대상. "
            f'<a href="ops/17_model_risk.html">→ 모형 리스크</a> · '
            f'<a href="ops/19_raf.html">→ RAF 상세</a>')
    return out


# 지표별 악화 방향 — 토네이도에서 "나쁜 쪽" 충격만 집계하기 위한 규약
_ADVERSE_SIGN = {"ECL": 1, "RWA": 1, "CET1": -1, "LCR": -1, "ΔEVE": -1}


def _sensitivity_tornado(result: PipelineResult) -> str:
    """One-factor 민감도에서 factor별 최악(악화) 충격의 상대 영향을 랭킹."""
    of = result.sensitivity["one_factor"]
    rows = []
    for (factor, metric), g in of.groupby(["factor", "metric"]):
        sign = _ADVERSE_SIGN.get(metric, 1)
        bad = g["delta"] * sign
        w = g.loc[bad.idxmax()]
        worst = float(bad.max())
        base = float(w["base"])
        if worst <= 0 or base == 0:
            continue
        shock = float(w["shock"])
        if "bp" in factor:
            shock_txt = f"{shock:+.0f}bp"
        elif "abs" in factor:
            shock_txt = f"{shock*100:+.0f}%p"
        else:
            shock_txt = f"{shock:+.0%}"
        rows.append((f"{factor} {shock_txt} → {metric}",
                     worst / abs(base) * 100))
    rows.sort(key=lambda t: -t[1])
    rows = rows[:8]
    return viz.horizontal_bar(
        [r[0] for r in rows], [r[1] for r in rows],
        title="민감도 토네이도 — 최악 방향 충격의 상대 악화율 (base 대비 %)",
        value_fmt=lambda v: f"{v:.1f}%", color=viz.AMBER,
    )


_DOMAIN_LABEL = {
    "core_overview": "핵심 — 요약/검증/결재",
    "core_credit": "핵심 — 신용",
    "core_capital_alm": "핵심 — 자본/ALM",
    "credit": "신용/충당금 심층",
    "capital_stress": "자본/스트레스 심층",
    "market_trading": "시장/트레이딩 심층",
    "concentration_limits": "집중/한도 심층",
    "performance": "성과 심층",
    "nonfinancial": "비재무 심층",
    "governance": "거버넌스/공시 심층",
}


def _deep_dive_nav() -> str:
    """전체 ops 페이지로의 진입점 — page_registry에서 파생하므로 새 페이지가
    추가되면 자동으로 여기에도 나타난다 (전 부문 deep-dive 보장)."""
    groups: dict[str, list] = {}
    for spec in PAGES:
        groups.setdefault(spec.module.rsplit(".", 1)[-1], []).append(spec)
    parts = []
    for dom, specs in groups.items():
        label = _DOMAIN_LABEL.get(dom, dom)
        links = " ".join(f'<a href="ops/{s.filename}">{_esc(s.label)}</a>'
                         for s in specs)
        parts.append(
            f'<div class="nav-foot" style="margin-bottom:8px">'
            f'<b style="margin-right:10px">{_esc(label)}</b>{links}</div>')
    return "".join(parts)


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

def _qoq_section(trend_flags) -> str:
    """전기 대비(QoQ) 카드 — timeseries_ledger.trend_flags() DataFrame 입력."""
    def fmt_val(v, fmt):
        if fmt == "pct": return f"{v*100:.2f}%"
        if fmt == "won": return _won(v)
        return f"{v:.2f}"

    def fmt_qoq(v, fmt):
        if fmt == "pct": return f"{v*100:+.2f}%p"
        if fmt == "won": return ("+" if v >= 0 else "−") + _won(abs(v))
        return f"{v:+.2f}"

    tone = {"개선": "GREEN", "악화": "RED"}
    rows = []
    for _, r in trend_flags.iterrows():
        breach = (f' · 연속 위반 {int(r["consecutive_breaches"])}분기'
                  if r["consecutive_breaches"] else "")
        rows.append([
            r["label"], fmt_val(r["latest"], r["fmt"]),
            fmt_qoq(r["qoq"], r["fmt"]),
            _badge(r["trend"], tone.get(r["trend"], "NEUTRAL")) + _esc(breach),
        ])
    return f"""
<div class="card">
<h2>0-c. 전기 대비 추이 (QoQ) — 축적 원장 기준</h2>
<p class="section-lead">분기 축적 원장(headline digest 단위)에서 유도한 실측
전기 대비. 합성 back-history가 아닌 <b>실제 산출 이력</b>입니다.
<a href="trend_history.html">→ 시계열 상세</a></p>
{_table(["지표", "최근", "QoQ", "추세"], rows, right_cols=[1, 2])}
</div>"""


def build_executive(result: PipelineResult,
                    out_dir: str | Path,
                    *, manifest_digest: str = "",
                    trend_flags=None) -> Path:
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
    scorecard = viz_advanced.kri_scorecard(
        _kri_card_data(raf, seed=result.meta.get("seed")))

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

    # --- CRO briefing (deterministic narrative)
    briefing = _cro_briefing(result)

    # --- sensitivity tornado
    tornado = _sensitivity_tornado(result)

    # --- CET1 buffer ladder (headroom above each requirement layer)
    hr = result.attribution["cet1_headroom"]
    ladder = viz.horizontal_bar(
        [f"{row['layer']} (요구 {_pct(row['required'],1)})" for _, row in hr.iterrows()],
        [float(row["headroom"]) * 100 for _, row in hr.iterrows()],
        title="CET1 버퍼 사다리 — 요구 단계별 여유 (%p)",
        value_fmt=lambda v: f"{v:+.2f}%p",
    )

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
<h2>0-b. CRO 브리핑 — 이번 산출이 말하는 것</h2>
<p class="section-lead">아래 문장은 전부 본 산출값에서 자동 유도됩니다 (재현가능).
각 문장 끝 링크로 해당 부문 deep-dive에 진입하세요.</p>
{"".join(f'<p style="margin:10px 0; line-height:1.7;">{b}</p>' for b in briefing)}
</div>
{_qoq_section(trend_flags) if trend_flags is not None and len(trend_flags) else ""}

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
{ladder}
<p class="section-lead">막대는 각 요구 단계(최저 → 감독요구) 대비 실측 CET1의 여유 폭 —
가장 짧은 막대(감독요구 대비)가 실질 분배·성장 여력을 결정합니다.</p>
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
<h2>4-b. 민감도 토네이도 — 무엇이 가장 크게 흔드는가</h2>
{tornado}
<p class="section-lead">factor별 최악 방향 충격이 해당 지표를 base 대비 몇 %
악화시키는지의 랭킹. 상위 막대가 헤지·한도의 우선순위다.
<a href="ops/16_sensitivity.html">→ 민감도 grid 전체</a></p>
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
<h2>7. 실무진 deep-dive 진입점 — 전 부문 ({len(PAGES)}페이지)</h2>
<p>아래는 본 요약을 뒷받침하는 실무진 보고서(부문별 상세 + 모델 카드 + 출처)
전체 진입점입니다. <a href="ops/index.html"><b>실무진 통합 인덱스</b></a> ·
<a href="ops/52_final_attestation.html"><b>최종 결재 attestation</b></a></p>
{_deep_dive_nav()}
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

{abbr_dict_card_html()}
"""
    meta = (f"산출 기준 {result.meta.get('asof','-')} · seed {result.meta.get('seed')} · "
            f"규제 준거 Basel III + IFRS9 + 금감원 감독세칙")
    out_path = out / "executive.html"
    out_path.write_text(_exec_page("경영진 요약", body, meta), encoding="utf-8")
    return out_path
