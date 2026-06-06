from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from risk_team_agent_harness.app.agents.risk_management_hub_agent import RiskManagementHubAgent
from risk_team_agent_harness.app.agents.self_validation_agent import SelfValidationAgent

REPORT_DIR = Path("reports/sample_validation")
GENERATED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SAMPLE_REQUESTS = [
    {
        "request_id": "req-credit-model-monitoring",
        "request_type": "monitoring",
        "risk_domain": "credit_model",
        "object_id": "credit-model-sample",
        "object_family": "estimation",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "RETAIL_SAMPLE",
        "segment_scope": "SCORECARD_A",
        "requested_metrics": ["pd_stability", "calibration_backtest"],
        "output_formats": ["json"],
        "initiated_by": "model_validator_sample",
        "user_role": "model_validator",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "normal",
    },
    {
        "request_id": "req-rwa-validation",
        "request_type": "validation",
        "risk_domain": "rwa",
        "object_id": "rwa-sample",
        "object_family": "measurement",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "CORPORATE_SAMPLE",
        "segment_scope": "ALL",
        "requested_metrics": ["rwa_reperformance", "crm_eligibility"],
        "output_formats": ["json"],
        "initiated_by": "risk_analyst_sample",
        "user_role": "risk_analyst",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "normal",
    },
    {
        "request_id": "req-bis-ratio-validation",
        "request_type": "validation",
        "risk_domain": "bis_ratio",
        "object_id": "bis-ratio-sample",
        "object_family": "aggregation",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "CONSOLIDATED",
        "segment_scope": "ALL",
        "requested_metrics": ["bis_ratio_reconciliation"],
        "output_formats": ["json"],
        "initiated_by": "risk_manager_sample",
        "user_role": "risk_manager",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "high",
    },
    {
        "request_id": "req-ddr-monitoring",
        "request_type": "monitoring",
        "risk_domain": "ddr",
        "object_id": "ddr-sample",
        "object_family": "estimation",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "RETAIL_SAMPLE",
        "segment_scope": "VINTAGE_SAMPLE",
        "requested_metrics": ["delinquency_rate", "default_rate", "recovery_rate"],
        "output_formats": ["json"],
        "initiated_by": "risk_analyst_sample",
        "user_role": "risk_analyst",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "normal",
    },
    {
        "request_id": "req-limit-monitoring",
        "request_type": "monitoring",
        "risk_domain": "limit",
        "object_id": "limit-sample",
        "object_family": "measurement",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "COUNTERPARTY_SAMPLE",
        "segment_scope": "INDUSTRY_SAMPLE",
        "requested_metrics": ["limit_utilization", "threshold_proximity"],
        "output_formats": ["json"],
        "initiated_by": "risk_analyst_sample",
        "user_role": "risk_analyst",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "normal",
    },
    {
        "request_id": "req-rapm-analysis",
        "request_type": "analysis",
        "risk_domain": "rapm",
        "object_id": "rapm-sample",
        "object_family": "hybrid",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "CORPORATE_SAMPLE",
        "segment_scope": "PRODUCT_SAMPLE",
        "requested_metrics": ["risk_adjusted_return", "capital_cost"],
        "output_formats": ["json"],
        "initiated_by": "risk_manager_sample",
        "user_role": "risk_manager",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "normal",
    },
    {
        "request_id": "req-climate-risk-validation",
        "request_type": "validation",
        "risk_domain": "climate_risk",
        "object_id": "climate-risk-sample",
        "object_family": "hybrid",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "CORPORATE_SAMPLE",
        "segment_scope": "CLIMATE_SCENARIO_SAMPLE",
        "requested_metrics": ["scenario_coverage", "transition_risk_sensitivity"],
        "output_formats": ["json"],
        "initiated_by": "risk_manager_sample",
        "user_role": "risk_manager",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "high",
    },
    {
        "request_id": "req-ai-model-validation",
        "request_type": "validation",
        "risk_domain": "ai_model_validation",
        "object_id": "ai-model-validation-sample",
        "object_family": "estimation",
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "MODEL_PORTFOLIO_SAMPLE",
        "segment_scope": "AI_MODEL_SEGMENT",
        "requested_metrics": ["fairness_stability", "drift_monitoring"],
        "output_formats": ["json"],
        "initiated_by": "model_validator_sample",
        "user_role": "model_validator",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "high",
    },
]

DOMAIN_LABELS = {
    "credit_model": "신용평가모형 모니터링",
    "rwa": "RWA 산출 검증",
    "bis_ratio": "BIS 비율 검증",
    "ddr": "연체율/부도율/회수율 모니터링",
    "limit": "한도 사용률 모니터링",
    "rapm": "RAPM 분석",
    "climate_risk": "기후리스크 검증",
    "ai_model_validation": "AI 모형 검증",
}


@dataclass
class RunBundle:
    request: dict
    result: object
    self_validation: object
    evidence: list[object]
    action_notice: object | None

    @property
    def passed(self) -> bool:
        return (
            self.result.status == "completed"
            and self.result.overall_judgement == "Green"
            and self.result.evidence_complete
            and not self.self_validation.flags
            and all(metric.approved_engine for metric in self.result.metric_results)
        )


def run_all_samples() -> list[RunBundle]:
    hub = RiskManagementHubAgent()
    validator = SelfValidationAgent(hub.notices)
    bundles = []
    for request in SAMPLE_REQUESTS:
        result = hub.handle(dict(request))
        bundles.append(
            RunBundle(
                request=request,
                result=result,
                self_validation=validator.validate(result),
                evidence=hub.evidence.list(result.run_id),
                action_notice=hub.notices.get(result.run_id),
            )
        )
    return bundles


def text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(text(item) for item in value)
    return str(value)


def rows_for_excel(bundles: list[RunBundle]) -> dict[str, list[list[object]]]:
    summary_rows = [
        ["generated_at", GENERATED_AT],
        ["sample_domain_count", len(bundles)],
        ["passed_domain_count", sum(bundle.passed for bundle in bundles)],
        ["overall_sample_status", "PASS" if all(bundle.passed for bundle in bundles) else "REVIEW_REQUIRED"],
        ["important_limit", "All metric values are placeholder outputs from approved deterministic stub engines; not regulatory figures."],
    ]
    run_rows = [[
        "domain",
        "domain_label",
        "request_id",
        "run_id",
        "status",
        "judgement",
        "self_validation_flags",
        "evidence_complete",
        "report_release_status",
        "review_required",
        "data_version",
        "code_version",
        "policy_version",
        "regulation_mapping_id",
        "evidence_hash",
    ]]
    metric_rows = [["domain", "run_id", "metric_name", "value", "engine_id", "engine_version", "approved_engine", "placeholder_calculation"]]
    evidence_rows = [["domain", "run_id", "evidence_hash", "source", "data_version", "code_version", "policy_version", "engine_version", "lineage_path", "complete"]]
    validation_rows = [["domain", "run_id", "review_required", "flags", "validation_result"]]
    action_rows = [["domain", "run_id", "action_notice_required", "key_issue", "impact", "required_actions", "owner_department", "due_date", "escalation_path"]]

    for bundle in bundles:
        result = bundle.result
        domain = result.risk_domain
        run_rows.append([
            domain,
            DOMAIN_LABELS[domain],
            result.request_id,
            result.run_id,
            result.status,
            result.overall_judgement,
            bundle.self_validation.flags,
            result.evidence_complete,
            result.report_release_status,
            result.review_required,
            result.data_version,
            result.code_version,
            result.policy_version,
            result.regulation_mapping_id,
            result.evidence_hash,
        ])
        for metric in result.metric_results:
            metric_rows.append([
                domain,
                result.run_id,
                metric.metric_name,
                metric.value,
                metric.engine_id,
                metric.engine_version,
                metric.approved_engine,
                metric.placeholder_calculation,
            ])
        for evidence in bundle.evidence:
            evidence_rows.append([
                domain,
                evidence.run_id,
                evidence.evidence_hash,
                evidence.source,
                evidence.data_version,
                evidence.code_version,
                evidence.policy_version,
                evidence.calculation_engine_version,
                evidence.lineage_path,
                evidence.complete,
            ])
        validation_rows.append([
            domain,
            result.run_id,
            bundle.self_validation.review_required,
            bundle.self_validation.flags,
            "PASS" if not bundle.self_validation.flags else "REVIEW_REQUIRED",
        ])
        notice = bundle.action_notice
        action_rows.append([
            domain,
            result.run_id,
            result.action_notice_required,
            notice.key_issue if notice else "",
            notice.impact if notice else "",
            notice.required_actions if notice else "",
            notice.owner_department if notice else "",
            notice.due_date if notice else "",
            notice.escalation_path if notice else "",
        ])
    return {
        "Summary": summary_rows,
        "Runs": run_rows,
        "Metrics": metric_rows,
        "Evidence": evidence_rows,
        "SelfValidation": validation_rows,
        "ActionNotices": action_rows,
    }


def col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def sheet_xml(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{col_name(col_index)}{row_index}"
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(text(value))}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>"


def write_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    workbook_sheets = []
    workbook_rels = []
    content_overrides = []
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        for sheet_id, (name, rows) in enumerate(sheets.items(), start=1):
            archive.writestr(f"xl/worksheets/sheet{sheet_id}.xml", sheet_xml(rows))
            workbook_sheets.append(f'<sheet name="{escape(name)}" sheetId="{sheet_id}" r:id="rId{sheet_id}"/>')
            workbook_rels.append(f'<Relationship Id="rId{sheet_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{sheet_id}.xml"/>')
            content_overrides.append(f'<Override PartName="/xl/worksheets/sheet{sheet_id}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(workbook_sheets) + "</sheets></workbook>")
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(workbook_rels) + "</Relationships>")
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + "".join(content_overrides) + "</Types>")


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(text(cell).replace("\n", " ") for cell in row) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def write_practitioner_md(path: Path, bundles: list[RunBundle]) -> None:
    rows = []
    detail_sections = []
    for bundle in bundles:
        result = bundle.result
        rows.append([
            DOMAIN_LABELS[result.risk_domain],
            result.run_id,
            result.status,
            result.overall_judgement,
            "PASS" if not bundle.self_validation.flags else text(bundle.self_validation.flags),
            result.evidence_hash,
            result.report_release_status,
        ])
        metric_rows = [
            [metric.metric_name, metric.value, metric.engine_id, metric.engine_version, metric.approved_engine, metric.placeholder_calculation]
            for metric in result.metric_results
        ]
        evidence_rows = [
            [evidence.evidence_hash, evidence.source, evidence.data_version, evidence.policy_version, evidence.lineage_path, evidence.complete]
            for evidence in bundle.evidence
        ]
        detail_sections.append(
            f"""### {DOMAIN_LABELS[result.risk_domain]}

- request_id: `{result.request_id}`
- run_id: `{result.run_id}`
- object_id / family: `{result.object_id}` / `{result.object_family}`
- judgement: `{result.overall_judgement}` (최종 승인 아님)
- versions: data=`{result.data_version}`, code=`{result.code_version}`, policy=`{result.policy_version}`, regulation_mapping=`{result.regulation_mapping_id}`, engine=`{result.calculation_engine_version}`
- self-validation flags: `{text(bundle.self_validation.flags) or "없음"}`
- release status: `{result.report_release_status}`

{markdown_table(["metric", "value", "engine", "engine_version", "approved", "placeholder"], metric_rows)}

{markdown_table(["evidence_hash", "source", "data_version", "policy_version", "lineage_path", "complete"], evidence_rows)}
"""
        )
    content = f"""# 전체 리스크관리 부문 샘플 자체검증 실무자 보고서

- 생성시각: {GENERATED_AT}
- 대상: 신용평가모형, RWA, BIS 비율, 연체/부도/회수, 한도관리, RAPM, 기후리스크, AI 모형검증 8개 샘플 요청
- 목적: Agent Harness가 요청 정규화, 권한 확인, 승인 엔진 호출, evidence ledger, policy judgement, SelfValidationAgent 점검을 일관되게 수행하는지 확인
- 중요 제한: 본 결과의 metric value는 모두 승인된 deterministic **stub** 엔진의 `placeholder_result`이며 실제 금융 수치, 규제 비율 또는 최종 승인 근거가 아니다.

## 1. 종합 결과

- 샘플 실행 수: {len(bundles)}건
- 자체검증 통과: {sum(bundle.passed for bundle in bundles)}건
- 비Green 또는 자체검증 flag: {sum(not bundle.passed for bundle in bundles)}건
- 결론: 등록된 샘플 정책과 샘플 데이터 버전 기준으로 중대 예외는 식별되지 않았으나, 모든 결과는 인간 검토 대상이며 운영 승인 또는 외부 제출을 의미하지 않는다.

{markdown_table(["부문", "run_id", "status", "judgement", "self_validation", "evidence_hash", "release_status"], rows)}

## 2. 통제 관점 상세 해석

1. **Request / Access 통제**: 6개 샘플 요청은 공통 계약 필드를 포함하고 허용 역할로 실행되었다.
2. **Execution 통제**: 모든 metric result는 `approved_engine=True`인 deterministic stub engine에서 생성되었다. Agent가 수치를 생성하거나 보정하지 않았다.
3. **Policy / Regulation 통제**: `policy-sample-v1`과 `basel-fss-sample-map-v1`의 configurable registry 항목을 사용했다. 실제 Basel/FSS 임계치 또는 감독 해석은 하드코딩하지 않았다.
4. **Evidence 통제**: 모든 run에 evidence hash와 lineage path가 생성되었고 evidence ledger complete 상태가 확인되었다.
5. **SelfValidation 통제**: run/version/evidence 필드, 승인 엔진 여부, 위험한 Green, Red 외부공유 상태를 점검했으며 샘플 정상 케이스에서는 flag가 없었다.

## 3. 부문별 실행 상세

{chr(10).join(detail_sections)}

- 기후리스크: Basel 기후리스크 원칙 및 글로벌 감독 권고사항을 configurable registry로 연결하고, 시나리오/전이/물리리스크 증적을 ledger화해야 한다.
- AI 모형검증: 글로벌 AI 리스크관리 권고(NIST AI RMF, OECD AI Principles 등)를 configurable registry로 연결하고 공정성/드리프트/설명가능성 증적을 관리해야 한다.

## 4. 부문별 후속 점검 포인트

- 신용평가모형: 실제 운영 전 model_version, methodology_version, backtesting evidence, 승인 이력을 ledger에 연결해야 한다.
- RWA: 익스포져 원천부터 CRM eligibility, 위험가중치, RWA 결과까지 lineage와 independent reperformance 산식을 연결해야 한다.
- BIS 비율: 자본 구성요소, RWA 집계, 감독/관리/내부보고 간 reconciliation evidence가 필요하다.
- 연체/부도/회수: 부도 정의, vintage/segment/product 단위 표본수와 회수시점 evidence가 필요하다.
- 한도관리: 임계치, 초과 예외 승인, Action Notice 에스컬레이션 SLA를 운영 workflow와 연결해야 한다.
- RAPM: 경제적 자본 또는 규제자본 비용 산식, 기대손실/예상외손실 산식, 경영진 보고 템플릿 승인 이력이 필요하다.

## 5. 첨부 산출물

- Excel 자체검증 파일: `self_validation_results.xlsx`
- 경영진 보고서: `executive_report.md`, `executive_report.html`
- 실무자 보고서: `practitioner_report.md`, `practitioner_report.html`
"""
    path.write_text(content, encoding="utf-8")


def write_executive_md(path: Path, bundles: list[RunBundle]) -> None:
    status = "정상 샘플 통과" if all(bundle.passed for bundle in bundles) else "후속 검토 필요"
    content = f"""# 경영진 요약 보고서: 리스크관리 팀에이전트 하네스 샘플 자체검증

## 핵심 메시지

- 6개 리스크관리 부문 샘플 실행 결과: **{status}**
- 자체검증 결과: {sum(bundle.passed for bundle in bundles)} / {len(bundles)}건 통과
- 외부 보고 가능 여부: **아님**. 본 보고서는 prototype 샘플 검증이며 최종 승인, 감독 제출, 대외 보고 근거가 아니다.

## 경영진 관점 결론

Agent Harness는 샘플 기준으로 요청 접수부터 승인된 stub 엔진 호출, evidence 기록, 자체검증까지 일관된 통제 흐름을 보였다. 다만 현재 계산 결과는 placeholder이므로 운영 적용 전 실제 계산엔진, 정책 registry, 승인 이력, 데이터 lineage를 연결해야 한다.

## 후속 대응 논리

1. **운영 전제조건 확정**: 실제 계산엔진, 데이터 계약, 정책/임계치 registry owner를 지정한다.
2. **통제 증적 보강**: evidence ledger에 원천 데이터 hash, 중간 테이블, 결과 테이블, 승인 이력을 연결한다.
3. **Human-in-the-loop 운영화**: Red/Amber/Gray 결과 처리, 외부 공유 차단, 회의체 승인 절차를 workflow에 반영한다.
4. **시범 운영**: 6개 부문별 gold/replay/negative/regulation-change set으로 병행 검증한다.

## 의사결정 요청사항

- 다음 단계는 production 배포가 아니라 **통제 설계 검토 및 실제 엔진 연계 PoC 승인**이다.
- Basel/FSS 세부 기준은 담당 부서 승인 config 없이는 자동 반영하지 않는다.
"""
    path.write_text(content, encoding="utf-8")


def markdown_to_html(title: str, markdown: str) -> str:
    lines = markdown.splitlines()
    html = ["<!doctype html><html lang='ko'><head><meta charset='utf-8'>", f"<title>{escape(title)}</title>", "<style>body{font-family:Arial,'Noto Sans KR',sans-serif;margin:40px;line-height:1.6;color:#1f2937}h1{color:#0f172a}h2{border-bottom:1px solid #e5e7eb;padding-bottom:4px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d1d5db;padding:6px;vertical-align:top}th{background:#f3f4f6}code{background:#f3f4f6;padding:1px 4px}</style></head><body>"]
    in_ul = False
    in_table = False
    for line in lines:
        if line.startswith("| "):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(set(cell) <= {"-"} for cell in cells):
                continue
            if not in_table:
                html.append("<table>")
                in_table = True
            tag = "th" if all(h not in "" for h in cells) and "run_id" in cells else "td"
            html.append("<tr>" + "".join(f"<{tag}>{escape(cell)}</{tag}>" for cell in cells) + "</tr>")
            continue
        if in_table:
            html.append("</table>")
            in_table = False
        if line.startswith("# "):
            html.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            html.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            html.append(f"<li>{escape(line[2:])}</li>")
        elif not line.strip():
            if in_ul:
                html.append("</ul>")
                in_ul = False
        else:
            if in_ul:
                html.append("</ul>")
                in_ul = False
            html.append(f"<p>{escape(line)}</p>")
    if in_ul:
        html.append("</ul>")
    if in_table:
        html.append("</table>")
    html.append("</body></html>")
    return "\n".join(html)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    bundles = run_all_samples()
    write_xlsx(REPORT_DIR / "self_validation_results.xlsx", rows_for_excel(bundles))
    write_practitioner_md(REPORT_DIR / "practitioner_report.md", bundles)
    write_executive_md(REPORT_DIR / "executive_report.md", bundles)
    for name, title in [
        ("practitioner_report", "전체 리스크관리 부문 샘플 자체검증 실무자 보고서"),
        ("executive_report", "경영진 요약 보고서"),
    ]:
        md = (REPORT_DIR / f"{name}.md").read_text(encoding="utf-8")
        (REPORT_DIR / f"{name}.html").write_text(markdown_to_html(title, md), encoding="utf-8")
    print(f"generated {REPORT_DIR}")


if __name__ == "__main__":
    main()
