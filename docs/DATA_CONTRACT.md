# 데이터 계약

## Request schema
표준 요청은 `request_id`, `request_type`, `risk_domain`, `object_id`, `object_family`, `as_of_period`, `entity_scope`, `portfolio_scope`, `segment_scope`, `requested_metrics`, `output_formats`, `initiated_by`, `user_role`, `policy_version`, `data_version`, `urgency`를 포함한다.

## Result schema
표준 결과는 `run_id`, `request_id`, `status`, `object_id`, `object_family`, `risk_domain`, `overall_judgement`, `metric_results`, data quality/reconciliation/policy findings, exceptions, action notice flag, review flag, version fields, `regulation_mapping_id`, `evidence_hash`, timestamps를 포함한다.

## Evidence schema
Evidence는 `run_id`, `evidence_hash`, `source`, `data_version`, `code_version`, `policy_version`, `calculation_engine_version`, `lineage_path`, `complete`, `created_at`을 포함한다.

## Action notice schema
Action Notice는 `run_id`, `object_id`, 기준시점, 핵심 이슈, 영향도, 원인 후보, 필요 조치, 담당 조직, 기한, 에스컬레이션 경로, 첨부 증적을 포함한다.

## Registry schema
Registry는 validation object, metric, policy version, threshold, regulation mapping, calculation engine approval metadata를 설정형 항목으로 관리한다. 실제 Basel/FSS 임계치가 제공되지 않으면 값을 비워두고 Gray fail-safe를 우선한다.
