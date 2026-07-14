"""CRO digest — 분기 검증 요약 이메일 초안 생성기 (HITL 발송).

보고서 팩과 동일한 결정론적 demo 실행 (동일 n/seed/stress → 동일 수치) 에서
경영진 KPI · 부문 신호등 · Top 리스크를 뽑아 **이메일용 자체완결 HTML** 과
플레인 텍스트 초안을 만든다.

발송 통제 (CLAUDE.md §5/§7):
- 본 모듈은 **초안 파일만 생성**한다. 메일 발송 기능은 없다.
- 실제 발송은 인간이 초안을 검토·승인한 뒤 수행한다 (HITL).
- 본문에 DRAFT 표기와 HITL 고지가 강제 삽입된다 (테스트로 검증).

이메일 클라이언트 호환을 위해 외부 리소스 (script/link/img src) 없이
인라인 스타일 테이블만 사용한다.

사용:
    python -m tools.cro_digest --out reports/cro_digest.html
    python -m tools.cro_digest --stress --n 100000 --seed 42 \\
        --out reports/cro_digest_stress.html --text-out reports/cro_digest.txt
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.svg_charts import PALETTE

_STATUS_LABEL = {
    "ok": "정상",
    "warning": "주의",
    "fail": "미달",
    "skipped": "미실행",
    "simulated": "모의",
}

#: QoQ 지표 — (한글 라벨, 표시 형식, 높을수록 좋은지)
_QOQ_METRICS = {
    "cet1": ("CET1 비율", "{:.2%}", True),
    "leverage": ("Leverage 비율", "{:.2%}", True),
    "lcr": ("LCR", "{:.2f}", True),
    "nsfr": ("NSFR", "{:.2f}", True),
    "icaap": ("내부자본비율", "{:.2f}", True),
    "delta_eve": ("ΔEVE/Tier1", "{:.1%}", False),
    "psi": ("PSI", "{:.3f}", False),
    "hhi": ("HHI", "{:.3f}", False),
}


def _esc(v: object) -> str:
    return html.escape(str(v), quote=True)


def _status_chip(status: str) -> str:
    color = PALETTE.get(status, PALETTE["neutral"])
    label = _STATUS_LABEL.get(status, status)
    return (
        f'<span style="display:inline-block;padding:1px 8px;border-radius:10px;'
        f'background:{color};color:#ffffff;font-size:12px">{_esc(label)}</span>')


def build_digest(demo: dict, *, stress: bool, seed: int, n: int,
                 generated_at: str = "(생성 시각 미기록)") -> dict:
    """demo 결과 → {subject, html, text} 이메일 초안.

    ``generated_at`` 을 호출자가 주입한다 — 동일 입력이면 산출도 동일
    (결정론, CRO 재현가능성 요구).
    """
    from tools.executive_insights import (
        domain_rows,
        kpi_cards,
        top_risks_and_actions,
    )
    from tools.provenance import git_info
    from tools.report_export import _qoq_table

    mode = "스트레스" if stress else "정상"
    subject = f"[DRAFT] 분기 적합성검증 요약 — {mode} (n={n:,}, seed={seed})"
    cards = kpi_cards(demo)
    domains = domain_rows(demo)
    risks, actions = top_risks_and_actions(demo, n=5)
    git = git_info()
    reproduce = (f"python -m tools.cro_digest --n {n} --seed {seed} "
                 f"{'--stress ' if stress else ''}--out <html>")
    n_fail = sum(1 for _, s, _, _ in domains if s == "fail")
    n_warn = sum(1 for _, s, _, _ in domains if s == "warning")
    headline = (f"부문 {len(domains)}개 중 미달 {n_fail} · 주의 {n_warn}"
                if (n_fail or n_warn) else
                f"부문 {len(domains)}개 전체 정상 범위")

    kpi_rows = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">'
        f"{_esc(label)}</td>"
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;'
        f'text-align:right;font-variant-numeric:tabular-nums"><b>{_esc(value)}'
        f"</b></td>"
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">'
        f"{_status_chip(status)}</td></tr>"
        for label, value, status in cards)

    domain_cells = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">'
        f"{_esc(label)}</td>"
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">'
        f"{_status_chip(status)}</td>"
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;'
        f'color:#475569;font-size:13px">{_esc(detail)}</td></tr>'
        for label, status, detail, _link in domains)

    # QoQ — 합성 분기 panel (delta 방향에 지표별 개선/악화 판정 적용)
    qoq = _qoq_table()
    qoq_rows = []
    qoq_text = []
    for row in qoq:
        label, fmt, higher_better = _QOQ_METRICS.get(
            row["metric"], (row["metric"], "{:.4f}", True))
        delta = row["delta"]
        improved = (delta >= 0) if higher_better else (delta <= 0)
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
        color = PALETTE["ok"] if improved else PALETTE["fail"]
        word = "개선" if improved else "악화"
        if delta == 0:
            color, word = PALETTE["neutral"], "동일"
        qoq_rows.append(
            f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">'
            f"{_esc(label)}</td>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;'
            f'text-align:right;font-variant-numeric:tabular-nums">'
            f"{_esc(fmt.format(row['previous_value']))}</td>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;'
            f'text-align:right;font-variant-numeric:tabular-nums"><b>'
            f"{_esc(fmt.format(row['current_value']))}</b></td>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;'
            f'color:{color};font-weight:600">{arrow} '
            f"{_esc(fmt.format(abs(delta)))} {word}</td></tr>")
        qoq_text.append(
            f"- {label}: {fmt.format(row['previous_value'])} → "
            f"{fmt.format(row['current_value'])} ({arrow} {word})")
    qoq_block = (
        f"""<h3 style="margin:18px 0 6px">전분기 대비 (QoQ) — {_esc(qoq[0]['previous_quarter'])} → {_esc(qoq[0]['current_quarter'])}</h3>
<p style="font-size:12px;color:#475569;margin:0 0 6px">합성 분기 panel 기준 —
운영 시계열 연계 전 예시 (delta 방향은 지표별 개선/악화 정의 적용).</p>
<table style="border-collapse:collapse;width:100%">
<tr><th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">지표</th>
<th style="text-align:right;padding:6px 10px;border-bottom:2px solid #334155">전분기</th>
<th style="text-align:right;padding:6px 10px;border-bottom:2px solid #334155">당분기</th>
<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">변화</th></tr>
{''.join(qoq_rows)}</table>""" if qoq else "")

    risk_rows = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">'
        f"{_esc(r['label'])} {_status_chip(r['status'])}</td>"
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;'
        f'color:#475569;font-size:13px">{_esc(a["action"])}</td></tr>'
        for r, a in zip(risks, actions))
    risk_block = (
        f"""<h3 style="margin:18px 0 6px">Top 리스크 및 표준 조치</h3>
<table style="border-collapse:collapse;width:100%">
<tr><th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">리스크</th>
<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">표준 조치</th></tr>
{risk_rows}</table>""" if risk_rows else
        '<p style="color:#475569">에스컬레이션 대상 리스크 없음.</p>')

    html_body = f"""<div style="max-width:760px;margin:0 auto;font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#0f172a">
<div style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">
<div style="background:#0f2a4a;color:#ffffff;padding:14px 18px">
  <div style="font-size:12px;letter-spacing:.12em;opacity:.85">VALIDATION TEAM · [DRAFT — 내부 검토용]</div>
  <div style="font-size:18px;font-weight:700;margin-top:2px">분기 적합성검증 요약 ({_esc(mode)} 시나리오)</div>
</div>
<div style="padding:16px 18px">
<p style="margin:0 0 10px"><b>{_esc(headline)}</b></p>
<div style="background:#fef9c3;border:1px solid #ca8a04;border-radius:6px;padding:8px 12px;font-size:13px">
본 메일은 자동 생성된 <b>초안 (DRAFT)</b> 입니다. 발송·대외 공유는 검증 책임자
승인 후에만 가능합니다 (HITL). 모든 수치는 아래 재실행 명령으로 재현 가능합니다.
</div>

<h3 style="margin:18px 0 6px">경영진 KPI</h3>
<table style="border-collapse:collapse;width:100%">
<tr><th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">지표</th>
<th style="text-align:right;padding:6px 10px;border-bottom:2px solid #334155">값</th>
<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">판정</th></tr>
{kpi_rows}</table>

<h3 style="margin:18px 0 6px">부문 신호등</h3>
<table style="border-collapse:collapse;width:100%">
<tr><th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">부문</th>
<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">판정</th>
<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #334155">비고</th></tr>
{domain_cells}</table>

{qoq_block}

{risk_block}

<p style="font-size:13px;color:#475569;margin-top:14px">상세 분석·심화 페이지는
첨부 보고서 팩 (47 페이지, deep-dive 포함) 을 참조하십시오.</p>
</div>
<div style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:10px 18px;font-size:12px;color:#475569">
생성 {_esc(generated_at)} · git <code>{_esc(git['branch'])}@{_esc(git['rev'])}</code>
· 재실행 <code>{_esc(reproduce)}</code><br>
본 산출물은 검증 보조 자료입니다. 판정 확정·발송은 인간 검증자 권한입니다.
</div>
</div>
</div>"""

    text_lines = [
        f"[DRAFT] 분기 적합성검증 요약 ({mode} 시나리오)",
        f"헤드라인: {headline}",
        "",
        "== 경영진 KPI ==",
        *[f"- {label}: {value} [{_STATUS_LABEL.get(s, s)}]"
          for label, value, s in cards],
        "",
        "== 부문 신호등 ==",
        *[f"- {label}: {_STATUS_LABEL.get(s, s)} — {detail}"
          for label, s, detail, _ in domains],
        "",
        f"== 전분기 대비 (QoQ, {qoq[0]['previous_quarter']} → "
        f"{qoq[0]['current_quarter']}) — 합성 panel 예시 =="
        if qoq else "",
        *qoq_text,
        "",
        "== Top 리스크 / 표준 조치 ==",
        *([f"- {r['label']} [{_STATUS_LABEL.get(r['status'], r['status'])}]: "
           f"{a['action']}" for r, a in zip(risks, actions)]
          or ["- 에스컬레이션 대상 없음"]),
        "",
        f"생성 {generated_at} · git {git['branch']}@{git['rev']}",
        f"재실행: {reproduce}",
        "본 메일은 자동 생성 초안 (DRAFT) — 발송은 인간 승인 필요 (HITL).",
    ]
    return {"subject": subject, "html": html_body,
            "text": "\n".join(text_lines)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CRO 분기 요약 이메일 초안 생성 (발송 기능 없음 — HITL)")
    parser.add_argument("--n", type=int, default=100_000)
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True,
                        help="HTML 초안 출력 경로")
    parser.add_argument("--text-out", type=Path, default=None,
                        help="플레인 텍스트 초안 출력 경로 (선택)")
    parser.add_argument("--log-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    from datetime import datetime, timezone

    from tools.run_workflow_demo import run_demo

    log_dir = args.log_dir or (Path(__file__).resolve().parent.parent / "logs")
    demo = run_demo(args.n, args.stress, args.seed, log_dir)
    digest = build_digest(
        demo, stress=args.stress, seed=args.seed, n=args.n,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(digest["html"], encoding="utf-8")
    sys.stdout.write(f"제목: {digest['subject']}\n")
    sys.stdout.write(f"HTML 초안: {args.out}\n")
    if args.text_out:
        args.text_out.parent.mkdir(parents=True, exist_ok=True)
        args.text_out.write_text(digest["text"], encoding="utf-8")
        sys.stdout.write(f"텍스트 초안: {args.text_out}\n")
    sys.stdout.write("주의: 초안만 생성했습니다 — 발송은 인간 승인 필요 (HITL).\n")
    return 0


__all__ = ["build_digest"]


if __name__ == "__main__":
    raise SystemExit(main())
