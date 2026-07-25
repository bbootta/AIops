"""업무보고서 생성 — 10라운드 작업의 산출·검증·미결 사항 (R10).

경영진보고서(executive)가 **리스크 결과**를 말한다면, 업무보고서는 **작업
자체**를 말한다: 무엇을 설계·개발·테스트했고, 무엇이 검증됐으며, 무엇이
아직 열려 있는가.

미결 사항을 빼면 보고서가 아니라 홍보물이 된다 — backlog·gap·미배정을
수치로 그대로 싣는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Round:
    no: int
    title: str
    scope: str
    artifacts: str
    findings: str          # 이 라운드에서 발견·수정한 결함 (없으면 "—")


ROUNDS: tuple[Round, ...] = (
    Round(1, "RDM · 정규 데이터모델",
          "테이블 스펙 엔진 · 카탈로그 · 분해 · DDL 생성",
          "risk_lib/datamodel/{spec,catalog,decompose}.py · ops/68 · 27 tests",
          "DDL 쉼표가 주석에 삼켜져 유효하지 않은 SQL 생성 · "
          "pandas 3.0 str dtype 미지원 · 업종 도메인을 추정으로 작성(실측과 불일치)"),
    Round(2, "CRM · 신용평가모형",
          "모형 인벤토리 · 등급/PD 이력 · 성능 지표 테이블",
          "catalog.CRM_TABLES · materialize_crm · 4 tests",
          "성능 지표에 None 혼입으로 object dtype화(수치연산 무력화) · "
          "pd_to_rating 스칼라 API에 벡터 전달"),
    Round(3, "RWA · 위험가중자산",
          "RWA 산출 결과 · CRM 배분 테이블",
          "catalog.RWA_TABLES · materialize_rwa · 5 tests",
          "파이프라인이 apply_crm을 호출하지 않아 공표 RWA에 담보효과 미반영 — "
          "데이터모델이 임의 적용하면 보고서에 RWA가 둘 생기므로 격차를 노출"),
    Round(4, "ECL · IFRS9 충당금",
          "ECL 산출 · 거시 시나리오 테이블",
          "catalog.ECL_TABLES · materialize_ecl · 5 tests",
          "입력 포트폴리오로 재계산 시 공표값과 12% 차이 — run_pipeline이 "
          "PD를 재적합해 덮어쓰기 때문(fitted_portfolio로 명시)"),
    Round(5, "ST/CAP · 스트레스·자본",
          "자본경로 · 자본 스택 테이블",
          "catalog.ST_TABLES · materialize_stress_capital · 5 tests", "—"),
    Round(6, "ALM · 유동성·금리",
          "LCR/NSFR/IRRBB 지표 · 충격 시나리오 테이블",
          "catalog.ALM_TABLES · materialize_alm · 4 tests", "—"),
    Round(7, "MKT/NCR · 시장·건전성",
          "트레이딩북 · IPV 결과 · NCR 구성요소 테이블",
          "catalog.MKT_TABLES · materialize_market · 5 tests", "—"),
    Round(8, "OPR · 운영리스크",
          "손실사건 원장 · 운영자본 테이블",
          "catalog.OPR_TABLES · materialize_operational · 3 tests", "—"),
    Round(9, "AIG/VAL · 거버넌스·검증",
          "자체검증 결과 · 산출근거 원장 · 수동조정 원장 테이블",
          "catalog.VAL_TABLES · materialize_governance · 6 tests",
          "자체검증 체크명 중복(ead_nonneg가 SA·IRB에 동일 이름) — "
          "이름 조회 시 한쪽이 가려져 실패가 통과로 보일 수 있었음"),
    Round(10, "통합 · 업무보고서 · 패키징",
          "CSV/DDL 내보내기 · 업무보고서 · ZIP + 무결성 매니페스트",
          "risk_lib/{deliverables,work_report}.py · ZIP 자가검증", "—"),
)


def build_context(result, portfolio, tables: dict[str, pd.DataFrame]) -> dict:
    """보고서에 들어갈 사실을 한 곳에서 수집한다 (수치의 단일 출처)."""
    from risk_lib import rynta
    from risk_lib.datamodel import catalog as cat
    from risk_lib import datamodel as dm
    from risk_lib.page_registry import PAGES

    cov = rynta.coverage_frame()
    scoped = cov[cov["status"] != "platform"]
    viol = dm.validate_all(tables)
    return {
        "asof": result.meta.get("asof", date.today().isoformat()),
        "seed": result.meta.get("seed"),
        "n_tables": len(cat.ALL_TABLES),
        "n_columns": sum(len(s.columns) for s in cat.ALL_TABLES),
        "n_materialized": len(tables),
        "n_rows": sum(len(v) for v in tables.values()),
        "schema_violations": len(viol),
        "n_pages": len(PAGES),
        "coverage": rynta.coverage_summary(),
        "in_scope_ratio": rynta.in_scope_ratio(),
        "n_unassigned": int((scoped["owner"] == "").sum()),
        "backlog": cov[cov["status"] == "backlog"][["id", "title", "gap"]],
        "partial": cov[cov["status"] == "partial"][["id", "title", "gap"]],
        "validation": result.validation.summary(),
        "verdict": "결재 가능 (PASS)" if result.validation.passes()
                   else "결재 불가 (FAIL)",
    }


def render_markdown(ctx: dict) -> str:
    """업무보고서 (Markdown)."""
    cov = ctx["coverage"]
    lines = [
        "# 리스크관리 에이전트 하니스 — 업무보고서",
        "",
        f"- 산출 기준일: **{ctx['asof']}** · seed **{ctx['seed']}**",
        f"- 자체검증: {ctx['validation']} → **{ctx['verdict']}**",
        "",
        "## 1. 작업 개요 (10라운드)",
        "",
        "| # | 라운드 | 범위 | 산출물 | 발견·수정 결함 |",
        "|---|---|---|---|---|",
    ]
    for r in ROUNDS:
        lines.append(f"| {r.no} | {r.title} | {r.scope} | `{r.artifacts}` | {r.findings} |")

    lines += [
        "",
        "## 2. 산출 규모",
        "",
        f"- 정규 테이블 **{ctx['n_tables']}개** · 컬럼 **{ctx['n_columns']}개**",
        f"- 실체화 테이블 **{ctx['n_materialized']}개** · 총 **{ctx['n_rows']:,}행**",
        f"- 스키마 검증 위반 **{ctx['schema_violations']}건**",
        f"- 보고서 페이지 **{ctx['n_pages']}개**",
        "",
        "## 3. 요건 커버리지 (RYNTA BRD 126건)",
        "",
        "| 상태 | 건수 |",
        "|---|---:|",
        f"| 구현·증빙 (covered) | {cov.get('covered', 0)} |",
        f"| 부분구현 (partial) | {cov.get('partial', 0)} |",
        f"| 미구현 (backlog) | {cov.get('backlog', 0)} |",
        f"| 플랫폼 계층 (범위 밖) | {cov.get('platform', 0)} |",
        "",
        f"산출 하니스 책임 범위 내 구현율 **{ctx['in_scope_ratio']*100:.1f}%** · "
        f"미배정 요건 **{ctx['n_unassigned']}건**",
        "",
        "## 4. 미결 사항",
        "",
        "### 4-1. 미구현 (backlog)",
        "",
    ]
    if len(ctx["backlog"]):
        lines += ["| 요건 | 내용 | 사유 |", "|---|---|---|"]
        for _, r in ctx["backlog"].iterrows():
            lines.append(f"| `{r['id']}` | {r['title']} | {r['gap']} |")
    else:
        lines.append("해당 없음.")

    lines += ["", "### 4-2. 부분구현 (gap 명시)", ""]
    lines += ["| 요건 | 내용 | 미구현 부분 |", "|---|---|---|"]
    for _, r in ctx["partial"].head(40).iterrows():
        lines.append(f"| `{r['id']}` | {r['title']} | {r['gap']} |")

    lines += [
        "",
        "## 5. 검증 방식",
        "",
        "- **대사(reconciliation)**: 테이블 합계가 공표 수치와 정확히 일치하는지 "
        "테스트로 고정 (SA·IRB RWA, ECL, LCR/NSFR, NCR 구성요소).",
        "- **위반 발동 검증**: 모든 스키마 규칙에 위반 케이스를 만들어 실제로 "
        "잡히는지 확인 — 발동하지 않는 규칙은 통제가 아니라 장식이다.",
        "- **오염 주입**: 음수 EAD·고아 참조를 주입해 검증이 실패하는지 확인.",
        "",
        "## 6. 한계",
        "",
        "- 합성 데이터 기반이므로 수치 자체는 예시이며 규제 제출용이 아니다.",
        "- 허용오차·임계값(IPV 게이트, staleness, 중요성)은 내부 관리값이며 "
        "기관 승인 사양으로 교체가 전제다.",
        "- NCR·시장데이터는 구조를 구현한 것이고, 인가 내역·실제 피드 연결은 "
        "고객 환경에서 수행해야 한다.",
        "",
    ]
    return "\n".join(lines)


def render_html(ctx: dict) -> str:
    """업무보고서 (HTML) — 인쇄·공유용."""
    from risk_lib.report_chrome import CSS, _esc
    md = render_markdown(ctx)
    # 간이 Markdown → HTML (표·헤딩·목록만 — 외부 의존 없이)
    html_parts, in_table = [], False
    for line in md.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                html_parts.append('<table class="t"><thead><tr>')
            elif in_table == "body_start":
                html_parts.append("<tr>")
            else:
                html_parts.append("<tr>")
            html_parts.append("".join(f"<{tag}>{c}</{tag}>" for c in cells))
            html_parts.append("</tr>")
            if not in_table:
                html_parts.append("</thead><tbody>")
                in_table = True
            continue
        if in_table:
            html_parts.append("</tbody></table>")
            in_table = False
        if line.startswith("### "):
            html_parts.append(f"<h3>{_esc(line[4:])}</h3>")
        elif line.startswith("## "):
            html_parts.append(f'<div class="card"><h2>{_esc(line[3:])}</h2>')
        elif line.startswith("# "):
            html_parts.append(f'<h1 class="title">{_esc(line[2:])}</h1>')
        elif line.startswith("- "):
            html_parts.append(f"<p>• {line[2:]}</p>")
        elif line.strip():
            html_parts.append(f"<p>{line}</p>")
    if in_table:
        html_parts.append("</tbody></table>")
    body = "\n".join(html_parts).replace("`", "")
    # 카드 닫기 보정
    body += "</div>" * body.count('<div class="card">')
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>업무보고서 — 리스크관리 에이전트 하니스</title>
<style>{CSS}</style></head>
<body><div class="container">{body}
<footer>산출 기준일 {_esc(ctx['asof'])} · seed {_esc(ctx['seed'])}</footer>
</div></body></html>"""


def write_work_report(result, portfolio, tables, out_dir) -> dict[str, str]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    ctx = build_context(result, portfolio, tables)
    md = out / "업무보고서.md"
    html = out / "업무보고서.html"
    md.write_text(render_markdown(ctx), encoding="utf-8")
    html.write_text(render_html(ctx), encoding="utf-8")
    return {"markdown": str(md), "html": str(html)}
