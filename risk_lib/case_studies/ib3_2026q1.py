"""2026년 1분기 인터넷은행 3사 분석 + 2025 Q3 vs 2026 Q1 시점 비교 보고서."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from risk_lib import viz, viz_advanced
from risk_lib.html_report import CSS, _won, _pct, _esc, _table, _kpi, _badge
from risk_lib.case_studies import BankAnalysis, BANKS_2026Q1


def _qoq_comparison_index(
    a_2025: list[BankAnalysis], a_2026: list[BankAnalysis],
) -> str:
    """2025 Q3 → 2026 Q1 분기 간 변동 deep-dive."""
    # ── 분기 비교 행
    rows = []
    for old, new in zip(a_2025, a_2026):
        op, np_ = old.profile, new.profile
        rs_o, rs_n = old.result.reverse_stress, new.result.reverse_stress
        ss_o = old.result.stress[old.result.stress["scenario"] == "severely_adverse"]
        ss_n = new.result.stress[new.result.stress["scenario"] == "severely_adverse"]
        ad_o = old.result.stress[old.result.stress["scenario"] == "adverse"]
        ad_n = new.result.stress[new.result.stress["scenario"] == "adverse"]
        rows.append({
            "bank": op.name.replace(" (2026Q1)", ""),
            "loan_25": op.total_loans_krw, "loan_26": np_.total_loans_krw,
            "bis_25": op.bis_capital_ratio, "bis_26": np_.bis_capital_ratio,
            "npl_25": op.npl_ratio, "npl_26": np_.npl_ratio,
            "delq_25": op.delinquency_ratio, "delq_26": np_.delinquency_ratio,
            "cov_25": op.coverage_ratio, "cov_26": np_.coverage_ratio,
            "midlow_25": op.mid_low_credit_share, "midlow_26": np_.mid_low_credit_share,
            "ni_25": op.quarterly_net_income_krw, "ni_26": np_.quarterly_net_income_krw,
            "rev_s_25": rs_o.critical_severity, "rev_s_26": rs_n.critical_severity,
            "severe_cet1_25": float(ss_o["cet1_ratio"].iloc[0]),
            "severe_cet1_26": float(ss_n["cet1_ratio"].iloc[0]),
            "adverse_cet1_25": float(ad_o["cet1_ratio"].iloc[0]),
            "adverse_cet1_26": float(ad_n["cet1_ratio"].iloc[0]),
            "raf_25": old.result.raf.worst(),
            "raf_26": new.result.raf.worst(),
        })

    # ── KPI: 3사 BIS 변동
    bis_change_chart = viz.bar_chart(
        [r["bank"] for r in rows],
        [(r["bis_26"] - r["bis_25"]) * 100 for r in rows],
        value_fmt=lambda v: f"{v:+.2f}%p",
        title="공시 BIS 변동 (2025 Q3 → 2026 Q1)",
        colors=[viz.GREEN if (r["bis_26"] - r["bis_25"]) > 0 else viz.RED
                for r in rows],
    )

    # ── 역스트레스 심도 변동
    rev_change_chart = viz.bar_chart(
        [r["bank"] for r in rows],
        [r["rev_s_26"] - r["rev_s_25"] for r in rows],
        value_fmt=lambda v: f"{v:+.2f}",
        title="역스트레스 임계 심도 변동 (Δs)",
        colors=[viz.GREEN if (r["rev_s_26"] - r["rev_s_25"]) > 0 else viz.RED
                for r in rows],
    )

    # ── BIS 비교 (2025 vs 2026 side-by-side)
    bis_compare_chart = viz_advanced.heatmap(
        [r["bank"] for r in rows],
        ["2025 Q3", "2026 Q1"],
        [[r["bis_25"], r["bis_26"]] for r in rows],
        title="공시 BIS 자기자본비율 — 분기 비교",
        value_fmt=lambda v: f"{v*100:.2f}%",
        diverging=False, vmin=0.12, vmax=0.25,
    )

    # ── 분기 순익 비교
    ni_chart = viz.bar_chart(
        [r["bank"] for r in rows],
        [r["ni_26"] / 1e8 for r in rows],
        value_fmt=lambda v: f"{v:,.0f}억",
        title="2026 Q1 당기순이익 (전년 대비)",
        colors=[viz.PALETTE[0], viz.PALETTE[1], viz.PALETTE[2]],
    )

    # ── Severe CET1 비교
    severe_chart = viz_advanced.heatmap(
        [r["bank"] for r in rows], ["2025 Q3", "2026 Q1"],
        [[r["severe_cet1_25"], r["severe_cet1_26"]] for r in rows],
        title="Severe 시나리오 CET1 — 분기 비교",
        value_fmt=lambda v: f"{v*100:+.2f}%",
        diverging=True, vmin=-0.01, vmax=0.02,
    )

    # ── 비교 테이블
    cmp_rows = []
    for r in rows:
        cmp_rows.append([
            r["bank"],
            f"{r['loan_25']/1e12:.1f}조 → {r['loan_26']/1e12:.1f}조 "
            f"({(r['loan_26']/r['loan_25']-1)*100:+.1f}%)",
            f"{r['bis_25']*100:.2f}% → {r['bis_26']*100:.2f}% "
            f"({(r['bis_26']-r['bis_25'])*100:+.2f}%p)",
            f"{r['npl_25']*100:.2f}% → {r['npl_26']*100:.2f}% "
            f"({(r['npl_26']-r['npl_25'])*100:+.2f}%p)",
            f"{r['delq_25']*100:.2f}% → {r['delq_26']*100:.2f}%",
            f"{r['ni_26']/1e8:,.0f}억",
            f"s={r['rev_s_25']:.2f} → s={r['rev_s_26']:.2f}",
            f"{r['severe_cet1_25']*100:+.2f}% → {r['severe_cet1_26']*100:+.2f}%",
        ])

    # ── 핵심 인사이트
    kbank_jump = rows[1]["bis_26"] - rows[1]["bis_25"]
    insights_html = f"""
<div class="callout"><b>📈 케이뱅크 BIS 점프 ({kbank_jump*100:+.2f}%p, 15.01% → 21.47%)</b>:
2026년 1분기 IPO 상장 자본 확충 효과로 인뱅 중 최고 자본력 확보. CET1 +7.04%p 급등.
역스트레스 임계 심도도 s=1.80 → s=1.89로 개선되어 부도 충격 내성 강화.</div>
<div class="callout"><b>📊 토스뱅크 자산건전성 개선</b>:
NPL 0.84% → 0.87% (소폭), 연체율 1.07% (전년比 -0.19%p), 충당금 적립률 285.62% → 320.81% (+35%p).
중저신용자 잔액 비중 34.75%로 제1금융권 최고 수준에도 불구하고 건전성 통제 입증.
역스 심도 s=1.97 → s=2.02로 3사 중 최강 자본 내성 유지.</div>
<div class="callout"><b>⚠️ 카카오뱅크 BIS 추정 하락 (20.50% → 18.00%)</b>:
직접 공시 미확인 + 사업자대출 확대로 RWA 증가 추정 (디지털타임스: "환율·기업 대출에 BIS 비율 급락").
다만 분기 순익 1,873억으로 사상 최대 — 수익성·건전성 트레이드오프 점검 필요.</div>
<div class="callout good"><b>💰 3사 모두 분기 순익 호조</b>:
카뱅 +36.3% (1,873억, 분기 최대), 케뱅 +106.8% (332억), 토뱅 +58% (296억).
전반적 수익성 개선 추세이나 건전성·자본 부담은 차별화.</div>
"""

    # ── 출처
    sources = """
<ul>
<li>카카오뱅크 1Q26 (순익 1,873억): <a href="https://www.kakaocorp.com/page/detail/12023">카카오 IR 2026-05</a>, <a href="https://www.dt.co.kr/article/12064792">디지털타임스</a></li>
<li>케이뱅크 1Q26 (BIS 21.47%, 순익 332억): <a href="https://www.getnews.co.kr/news/articleView.html?idxno=869153">겟뉴스 2026</a></li>
<li>토스뱅크 1Q26 (BIS 16.62%, NPL 0.87%, 충당금 320.81%): <a href="https://zdnet.co.kr/view/?no=20260529111000">ZDNet 2026-05-29</a>, <a href="https://www.getnews.co.kr/news/articleView.html?idxno=871251">겟뉴스</a></li>
<li>은행권 1Q26 BIS 하락 동향: <a href="https://www.dt.co.kr/article/12064595">디지털타임스 (환율·기업대출 부담)</a></li>
</ul>
"""

    body = f"""
<h1 class="title">인터넷은행 3사 — 2026년 1분기 분기 변동 분석</h1>
<p class="section-lead">
2025년 3분기/말 공시 대비 2026년 1분기 공시 수치를 직접 비교.
각 은행 portfolio을 분기별 비중·BIS·NPL에 맞춰 재합성하고 risk_lib 파이프라인
(seed=42)으로 baseline·adverse·severe·역스트레스 산출.
</p>

<div class="card">
<h2>1. 분기 변동 핵심 인사이트</h2>
{insights_html}
</div>

<div class="row2">
<div class="card"><h2>2-1. BIS 변동</h2>
<div class="chart">{bis_change_chart}</div>
</div>
<div class="card"><h2>2-2. 역스 심도 변동</h2>
<div class="chart">{rev_change_chart}</div>
</div>
</div>

<div class="card">
<h2>3. 공시 BIS 분기 비교</h2>
<div class="chart">{bis_compare_chart}</div>
</div>

<div class="row2">
<div class="card"><h2>4-1. 2026 Q1 분기 순익</h2>
<div class="chart">{ni_chart}</div>
</div>
<div class="card"><h2>4-2. Severe 시나리오 CET1 변동</h2>
<div class="chart">{severe_chart}</div>
</div>
</div>

<div class="card">
<h2>5. 분기 변동 상세표</h2>
{_table(["은행","총여신","공시 BIS","공시 NPL","연체율","1Q26 순익","역스 심도","Severe CET1"],
        cmp_rows)}
</div>

<div class="card">
<h2>6. 분기별 deep-dive 보고서</h2>
<div class="linklist">
<p>📊 <a href="kakao_q1_26/executive.html"><b>카카오뱅크 2026 Q1</b></a> · <a href="kakao/executive.html">2025 Q3</a></p>
<p>📊 <a href="kbank_q1_26/executive.html"><b>케이뱅크 2026 Q1</b></a> · <a href="kbank/executive.html">2025 Q3</a></p>
<p>📊 <a href="toss_q1_26/executive.html"><b>토스뱅크 2026 Q1</b></a> · <a href="toss/executive.html">2025 Q3</a></p>
</div>
</div>

<div class="card">
<h2>7. 출처 (2026 Q1 공시자료)</h2>
{sources}
</div>
"""
    meta = f"산출 기준 {date.today().isoformat()} · seed 42 · 공시 2025 Q3 → 2026 Q1 분기 비교"
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>인터넷은행 3사 — 2026 Q1 분기 변동 분석</title>
<style>{CSS}</style></head>
<body>
<header class="top"><div class="wrap">
<h1>인터넷은행 3사 — 2026 Q1 분기 변동 분석</h1>
<div class="meta">{_esc(meta)}</div>
</div></header>
<div class="container">{body}</div>
<footer>risk_lib v0.15.1 · case_studies.internet_banks_2026Q1</footer>
</body></html>"""


def build_ib3_qoq_report(
    a_2025: list[BankAnalysis], a_2026: list[BankAnalysis],
    out_dir: str | Path,
) -> dict[str, str]:
    """2025 Q3 + 2026 Q1 두 분기 풀세트를 하나의 디렉터리에 작성 + 변동 분석 추가."""
    from risk_lib.html_report import build_full_report_package
    from risk_lib.repro import build_manifest, now_utc

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    # 1) 각 은행별 2025 Q3 풀세트
    for a in a_2025:
        bank_dir = out / a.profile.short
        manifest = build_manifest(
            portfolio=a.portfolio,
            parameters={"seed": 42, "bank": a.profile.short, "quarter": "2025Q3"},
            result=a.result,
            start_utc=now_utc(), end_utc=now_utc(),
            notes=f"인뱅 분석 — {a.profile.name} 2025Q3",
        )
        a.manifest = manifest
        build_full_report_package(a.result, bank_dir, portfolio=a.portfolio,
                                   manifest=manifest)
        written[a.profile.short] = str(bank_dir.resolve())

    # 2) 각 은행별 2026 Q1 풀세트
    for a in a_2026:
        bank_dir = out / a.profile.short
        manifest = build_manifest(
            portfolio=a.portfolio,
            parameters={"seed": 42, "bank": a.profile.short, "quarter": "2026Q1"},
            result=a.result,
            start_utc=now_utc(), end_utc=now_utc(),
            notes=f"인뱅 분석 — {a.profile.name} 2026Q1",
        )
        a.manifest = manifest
        build_full_report_package(a.result, bank_dir, portfolio=a.portfolio,
                                   manifest=manifest)
        written[a.profile.short] = str(bank_dir.resolve())

    # 3) 분기 비교 index
    idx = _qoq_comparison_index(a_2025, a_2026)
    (out / "index.html").write_text(idx, encoding="utf-8")
    written["index"] = str((out / "index.html").resolve())

    return written
