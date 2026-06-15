from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import csv
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from risk_team_agent_harness.app.agents.risk_management_hub_agent import RiskManagementHubAgent
from risk_team_agent_harness.app.agents.self_validation_agent import SelfValidationAgent
from scripts.generate_sample_validation_reports import DOMAIN_LABELS, SAMPLE_REQUESTS, markdown_to_html, text

REPORT_DIR = Path("reports/sample_validation")
ROUND_COUNT = 10
GENERATED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_rounds(round_count: int = ROUND_COUNT) -> list[dict[str, object]]:
    rows = []
    for round_number in range(1, round_count + 1):
        hub = RiskManagementHubAgent()
        validator = SelfValidationAgent(hub.notices)
        for request in SAMPLE_REQUESTS:
            result = hub.handle(dict(request))
            validation = validator.validate(result)
            metrics_approved = all(metric.approved_engine for metric in result.metric_results)
            passed = (
                result.status == "completed"
                and result.overall_judgement == "Green"
                and result.evidence_complete
                and metrics_approved
                and not validation.flags
            )
            rows.append(
                {
                    "round": round_number,
                    "domain": result.risk_domain,
                    "domain_label": DOMAIN_LABELS[result.risk_domain],
                    "request_id": result.request_id,
                    "run_id": result.run_id,
                    "status": result.status,
                    "judgement": result.overall_judgement,
                    "evidence_complete": result.evidence_complete,
                    "metrics_approved": metrics_approved,
                    "self_validation_flags": validation.flags,
                    "report_release_status": result.report_release_status,
                    "passed": passed,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "round",
        "domain",
        "domain_label",
        "request_id",
        "run_id",
        "status",
        "judgement",
        "evidence_complete",
        "metrics_approved",
        "self_validation_flags",
        "report_release_status",
        "passed",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: text(row[key]) for key in fieldnames})


def write_markdown(path: Path, rows: list[dict[str, object]]) -> None:
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    round_rows = []
    for round_number in range(1, ROUND_COUNT + 1):
        round_items = [row for row in rows if row["round"] == round_number]
        round_passed = sum(1 for row in round_items if row["passed"])
        round_rows.append(f"| {round_number} | {round_passed}/{len(round_items)} | {'PASS' if round_passed == len(round_items) else 'REVIEW_REQUIRED'} |")
    domain_rows = []
    for domain, label in DOMAIN_LABELS.items():
        domain_items = [row for row in rows if row["domain"] == domain]
        domain_passed = sum(1 for row in domain_items if row["passed"])
        domain_rows.append(f"| {label} | {domain_passed}/{len(domain_items)} | {'PASS' if domain_passed == len(domain_items) else 'REVIEW_REQUIRED'} |")
    detail_rows = [
        f"| {row['round']} | {row['domain_label']} | {row['status']} | {row['judgement']} | {row['evidence_complete']} | {row['metrics_approved']} | {text(row['self_validation_flags']) or '없음'} | {row['passed']} |"
        for row in rows
    ]
    content = f"""# 샘플 테스트 10라운드 실행 결과

- 생성시각: {GENERATED_AT}
- 실행 범위: 6개 리스크관리 부문 샘플 요청 × {ROUND_COUNT}라운드 = {total}건
- 통과 건수: {passed}/{total}
- 종합 상태: {'PASS' if passed == total else 'REVIEW_REQUIRED'}
- 중요 제한: 본 테스트는 prototype stub engine 기반 반복 검증이며 실제 금융 수치, 최종 승인, 감독 제출 또는 대외 보고 근거가 아니다.

## 라운드별 요약

| 라운드 | 통과 | 상태 |
| --- | --- | --- |
{chr(10).join(round_rows)}

## 부문별 요약

| 부문 | 통과 | 상태 |
| --- | --- | --- |
{chr(10).join(domain_rows)}

## 상세 결과

| 라운드 | 부문 | status | judgement | evidence_complete | metrics_approved | self_validation_flags | passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(detail_rows)}

## 해석 및 후속 대응

- 모든 라운드가 PASS인 경우 샘플 계약, 권한, 승인 엔진 provenance, evidence complete, 자체검증 flag 부재가 반복적으로 확인된 것이다.
- Green은 최종 승인과 동일하지 않으며, 운영 적용 전 실제 계산엔진, 데이터 lineage, 정책/임계치 registry, 승인 이력 연결이 필요하다.
- 비통과 항목이 발생하면 해당 라운드의 `run_id`, `self_validation_flags`, `report_release_status`를 기준으로 원인 분석과 Action Notice 후속 조치를 수행한다.
"""
    path.write_text(content, encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = run_rounds()
    write_csv(REPORT_DIR / "ten_round_sample_test.csv", rows)
    write_markdown(REPORT_DIR / "ten_round_sample_test.md", rows)
    markdown = (REPORT_DIR / "ten_round_sample_test.md").read_text(encoding="utf-8")
    (REPORT_DIR / "ten_round_sample_test.html").write_text(
        markdown_to_html("샘플 테스트 10라운드 실행 결과", markdown), encoding="utf-8"
    )
    passed = sum(1 for row in rows if row["passed"])
    print(f"10-round sample test: {passed}/{len(rows)} passed")


if __name__ == "__main__":
    main()
