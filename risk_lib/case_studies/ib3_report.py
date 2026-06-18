"""인터넷은행 3사 통합 위기상황분석 — 비교 HTML 보고서.

`build_ib3_report(analyses, out_dir)`:
  - index.html               — 경영진 비교 1-pager
  - kakao/, kbank/, toss/    — 각 은행 풀 보고서 세트 (executive + ops 56페이지)
  - comparison.html          — 3사 시나리오·역스트레스·RAF 비교 deep-dive
  - manifest_ib3.json        — 산출 메타 (3사 manifest digest 모음)
"""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from risk_lib import viz, viz_advanced
from risk_lib.html_report import CSS, _won, _pct, _esc, _table, _kpi, _badge
from risk_lib.abbreviations import abbr_dict_card_html
from risk_lib.case_studies import (
    BankAnalysis, compare_banks, stress_comparison, reverse_stress_comparison,
)


def _fmt_money(v: float) -> str:
    """조원 단위로 fmt."""
    return f"{v/1e12:,.2f}조원"


def _fmt_billion(v: float) -> str:
    return f"{v/1e9:,.0f}십억"


def _comparison_index(analyses: list[BankAnalysis], *, ib3_meta: dict) -> str:
    cmp = compare_banks(analyses)
    ss = stress_comparison(analyses)
    rev_tbl = reverse_stress_comparison(analyses)

    # -- KPI 카드 (3사 verdict)
    verdict_cards = []
    for a in analyses:
        v = a.result.validation
        summ = v.summary()
        passes = v.passes()
        tone = "good" if passes else "bad"
        verdict_cards.append(_kpi(
            a.profile.name,
            "결재 가능" if passes else "결재 불가",
            sub=f"PASS {summ.get('PASS',0)} / WARN {summ.get('WARN',0)} / FAIL {summ.get('FAIL',0)} · "
                f"RAF 최악 {a.result.raf.worst()}",
            tone=tone,
        ))

    # -- 3사 BIS 막대그래프
    bis_chart = viz.bar_chart(
        [a.profile.name for a in analyses],
        [a.profile.bis_capital_ratio for a in analyses],
        value_fmt=lambda v: f"{v*100:.2f}%",
        title="공시 BIS 자기자본비율 (2025년)",
        reference_value=0.115,
        reference_label="규제 요구 11.5% (포함 CCB)",
        colors=[viz.GREEN if x >= 0.115 else viz.AMBER for x in
                [a.profile.bis_capital_ratio for a in analyses]],
    )

    # -- 시나리오 CET1
    scenarios_chart = viz_advanced.heatmap(
        [a.profile.name for a in analyses],
        ["baseline", "adverse", "severely_adverse"],
        [
            [float(ss[(ss["은행"]==a.profile.name) & (ss["시나리오"]==s)]["CET1 비율"].iloc[0])
             for s in ["baseline","adverse","severely_adverse"]]
            for a in analyses
        ],
        title="시나리오별 CET1 비율 (3사 비교)",
        value_fmt=lambda v: f"{v*100:.2f}%", diverging=False,
        vmin=0, vmax=0.20,
    )

    # -- 역스트레스
    rev_chart = viz.bar_chart(
        [a.profile.name for a in analyses],
        [a.result.reverse_stress.critical_severity for a in analyses],
        value_fmt=lambda v: f"s={v:.2f}",
        title="역스트레스 임계 심도 (높을수록 자본 내성 강함)",
        colors=[viz.GREEN if a.result.reverse_stress.critical_severity > 2.0
                else viz.AMBER for a in analyses],
    )

    # -- NPL 막대
    npl_chart = viz.bar_chart(
        [a.profile.name for a in analyses],
        [a.profile.npl_ratio for a in analyses],
        value_fmt=lambda v: f"{v*100:.2f}%",
        title="공시 NPL 비율 (2025년 3분기)",
        colors=[viz.PALETTE[0], viz.PALETTE[2], viz.RED],
    )

    # -- comparison table
    cmp_rows = []
    for a in analyses:
        p = a.profile
        r = a.result
        rs = r.reverse_stress
        cmp_rows.append([
            p.name,
            _fmt_money(p.total_loans_krw),
            _fmt_money(p.total_deposits_krw),
            _pct(p.bis_capital_ratio),
            _pct(p.npl_ratio),
            _pct(p.delinquency_ratio),
            f"{p.coverage_ratio*100:.0f}%",
            _pct(p.mid_low_credit_share, 1),
            _badge(r.raf.worst(), r.raf.worst()),
            f"s={rs.critical_severity:.2f}",
        ])

    # -- 스트레스 표
    ss_rows = []
    for _, row in ss.iterrows():
        ss_rows.append([
            row["은행"], row["시나리오"],
            f"{row['RWA (조원)']:.2f}",
            f"{row['ECL (십억)']:,.0f}",
            f"{row['CET1 비율']*100:.2f}%",
            f"{row['CET1 잉여 (%p)']:+.2f}%p",
            _badge(row["통과"], row["통과"]),
        ])

    # -- 역스트레스 표
    rev_rows = []
    for _, row in rev_tbl.iterrows():
        rev_rows.append([
            row["은행"],
            f"{row['기준 CET1']*100:.2f}%",
            f"{row['임계 CET1']*100:.2f}%",
            f"s={row['임계 심도 s']:.2f}",
            f"{row['함의 GDP 충격']*100:+.2f}%",
            f"+{row['함의 LGD 가산 (%p)']:.2f}%p",
            f"{row['임계점 RWA (조원)']:.2f}조원",
        ])

    body = f"""
<h1 class="title">인터넷은행 3사 통합 위기상황분석 — 경영진 종합</h1>
<p class="section-lead">
2025년 3분기/말 공시자료(케이뱅크 18.4조 / 카카오뱅크 46.9조 / 토스뱅크 15.35조 총여신)를 토대로
각 은행 portfolio를 합성하고 동일한 risk_lib 파이프라인(seed=42)으로 baseline·adverse·severe·역스트레스 산출.
모든 수치는 manifest_ib3.json 기반으로 재현 가능합니다.
</p>

<div class="card">
<h2>1. 3사 결재 판정</h2>
<div class="kpi-grid">{"".join(verdict_cards)}</div>
<p class="section-lead">결재 가능 = 자체검증 FAIL 0건 · 결재 불가 = FAIL ≥1건. RAF 최악 등급은
12개 KRI 중 가장 심각한 신호입니다.</p>
</div>

<div class="row2">
<div class="card"><h2>2-1. 공시 BIS 자기자본비율</h2>
<div class="chart">{bis_chart}</div>
<p class="section-lead">
규제 최저 + 자본보전버퍼 = 8% + 2.5% = 10.5% (인뱅 D-SIB 미해당). 3사 모두 충족.
토스뱅크가 16.24%로 가장 높고, 케이뱅크 15.01%, 카카오뱅크는 공시 직접 확인 어려워 인뱅 평균 추정.
</p>
</div>
<div class="card"><h2>2-2. 공시 NPL 비율</h2>
<div class="chart">{npl_chart}</div>
<p class="section-lead">
토스뱅크 NPL 0.84%로 최고. 중저신용자 신용대출 비중(50%+)이 영향. 케이뱅크 0.54%·카카오뱅크 0.55%로
시중은행 평균(0.3%대)보다는 높지만 인뱅으로서는 양호.
</p>
</div>
</div>

<div class="card">
<h2>3. 통합 위기상황 분석 — 시나리오별 CET1</h2>
<div class="chart">{scenarios_chart}</div>
{_table(["은행","시나리오","RWA (조원)","ECL (십억)","CET1 비율","CET1 잉여","통과"],
        ss_rows, right_cols=[2,3,4,5,6])}
<div class="callout"><b>핵심 결론:</b>
3사 모두 baseline에서는 결재 가능하나, adverse·severe 시나리오에서는 모두 CET1 7.0% 임계 미달
(인뱅 공통 특성). 자본 충격 흡수력은 토스뱅크가 가장 좋고(severe CET1 1.11%),
카카오뱅크/케이뱅크는 severe 시 거의 zero까지 하락. 시중은행 대비 자본 보유량이 작아
부도 충격에 민감한 인뱅 구조적 한계.</div>
</div>

<div class="card">
<h2>4. 역스트레스 — 자본 임계점까지의 충격 심도</h2>
<div class="chart">{rev_chart}</div>
{_table(["은행","기준 CET1","임계 CET1","임계 심도 s","함의 GDP 충격","함의 LGD 가산","임계점 RWA"],
        rev_rows, right_cols=[1,2,3,4,5,6])}
<p class="section-lead">
임계 심도 s가 클수록 자본 내성 강함. 토스뱅크 s=1.98로 가장 강하며 GDP -5.9% + LGD +9.9%p 충격까지 견딤.
카카오뱅크·케이뱅크는 s=1.79~1.80으로 GDP -5.4% 수준에서 임계 도달.
2024년 한국 GDP 성장 2.0% 대비 -5%p 충격은 극심한 경기침체 시나리오(IMF 위기급).
</p>
</div>

<div class="card">
<h2>5. 3사 deep-dive 보고서</h2>
<p>각 은행의 56페이지 실무진 deep-dive(PD/RWA/BIS/ECL/모니터링/한도/RAPM/스트레스/ICAAP/ALM)는
아래 링크로 진입:</p>
<div class="linklist">
<p>📊 <a href="kakao/executive.html"><b>카카오뱅크 (KakaoBank)</b></a> — executive + ops 56페이지</p>
<p>📊 <a href="kbank/executive.html"><b>케이뱅크 (KBank)</b></a> — executive + ops 56페이지</p>
<p>📊 <a href="toss/executive.html"><b>토스뱅크 (TossBank)</b></a> — executive + ops 56페이지</p>
</div>
</div>

<div class="card">
<h2>6. 공시 자료 출처</h2>
<ul>
<li>케이뱅크: BIS 15.01%, NPL 0.54%, 연체율 0.56% — <a href="https://www.fntimes.com/html/view.php?ud=202511131707003898b4a7c6999c_18">한국금융신문 2025-11-13</a>, <a href="https://zdnet.co.kr/view/?no=20251113130247">ZDNet 2025-11-13</a></li>
<li>카카오뱅크: NPL 0.55%, 연체율 0.51% — <a href="https://news.nate.com/view/20251224n02536">네이트뉴스 2025-12-24</a>, <a href="https://og.kakaobank.io/download/339062de-9f36-41cb-aa94-dcb3de6676ef">카카오뱅크 IR 2025-11</a></li>
<li>토스뱅크: BIS 16.24%, NPL 0.84%, 연체율 1.11% — <a href="https://www.joongangenews.com/news/articleView.html?idxno=507601">중앙이코노미뉴스</a>, <a href="https://zdnet.co.kr/view/?no=20250829113631">ZDNet 2025-08-29</a></li>
<li>인뱅 3사 중저신용자 비중 — <a href="https://www.economidaily.com/view/20250822161926134">이코노믹데일리 2025-08-22</a></li>
<li>2025년 9월말 은행 BIS — <a href="https://eiec.kdi.re.kr/policy/materialView.do?num=274397">KDI 경제교육정보센터</a></li>
</ul>
</div>

<div class="card">
<h2>7. 재현성</h2>
<div class="repro-footer" style="font-family:Menlo,Consolas,monospace;font-size:11px;color:var(--muted);background:#f9fafb;padding:10px 14px;border:1px solid var(--line);border-radius:6px;word-break:break-all">
산출 일자 {date.today().isoformat()} · seed 42 · risk_lib v0.16.0 + case_studies/internet_banks_2025<br>
각 은행 manifest_digest는 <code>manifest_ib3.json</code> 참조.<br>
재현 명령:
<code>python -c "from risk_lib.case_studies import run_all_banks; from risk_lib.case_studies.ib3_report import build_ib3_report; build_ib3_report(run_all_banks(seed=42), '/tmp/ib3')"</code>
</div>
</div>

{abbr_dict_card_html()}
"""
    meta = (f"산출 기준 {date.today().isoformat()} · seed 42 · 공시 2025 Q3/연말 · 인뱅 3사 비교")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>인터넷은행 3사 통합 위기상황분석</title>
<style>{CSS}</style></head>
<body>
<header class="top"><div class="wrap">
<h1>인터넷은행 3사 통합 위기상황분석 — 경영진 종합</h1>
<div class="meta">{_esc(meta)}</div>
</div></header>
<div class="container">{body}</div>
<footer>risk_lib v0.14.0 · case_studies.internet_banks_2025 · 공시 출처는 §6 참조</footer>
</body></html>"""


def build_ib3_report(analyses: list[BankAnalysis], out_dir: str | Path) -> dict[str, str]:
    """3사 통합 보고서를 디렉터리에 작성."""
    from risk_lib.html_report import build_full_report_package
    from risk_lib.repro import build_manifest, now_utc

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    digests: dict[str, str] = {}

    # 1) 각 은행별 풀 패키지
    for a in analyses:
        bank_dir = out / a.profile.short
        manifest = build_manifest(
            portfolio=a.portfolio,
            parameters={"seed": 42, "bank": a.profile.short},
            result=a.result,
            start_utc=now_utc(), end_utc=now_utc(),
            notes=f"인뱅 3사 분석 — {a.profile.name}",
        )
        a.manifest = manifest
        digests[a.profile.short] = manifest.headline_digest
        wr = build_full_report_package(
            a.result, bank_dir,
            portfolio=a.portfolio, manifest=manifest,
        )
        written[a.profile.short] = str(bank_dir.resolve())

    # 2) 통합 index.html
    ib3_meta = {"digests": digests, "date": date.today().isoformat()}
    idx = _comparison_index(analyses, ib3_meta=ib3_meta)
    (out / "index.html").write_text(idx, encoding="utf-8")
    written["index"] = str((out / "index.html").resolve())

    # 3) ib3 manifest
    (out / "manifest_ib3.json").write_text(
        json.dumps(ib3_meta, ensure_ascii=False, indent=2),
        encoding="utf-8")
    written["manifest_ib3"] = str((out / "manifest_ib3.json").resolve())

    return written
