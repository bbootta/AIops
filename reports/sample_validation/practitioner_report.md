# 전체 리스크관리 부문 샘플 자체검증 실무자 보고서

- 생성시각: 2026-05-19T01:03:43+00:00
- 대상: 신용평가모형, RWA, BIS 비율, 연체/부도/회수, 한도관리, RAPM, 기후리스크, AI 모형검증 8개 샘플 요청
- 목적: Agent Harness가 요청 정규화, 권한 확인, 승인 엔진 호출, evidence ledger, policy judgement, SelfValidationAgent 점검을 일관되게 수행하는지 확인
- 중요 제한: 본 결과의 metric value는 모두 승인된 deterministic **stub** 엔진의 `placeholder_result`이며 실제 금융 수치, 규제 비율 또는 최종 승인 근거가 아니다.

## 1. 종합 결과

- 샘플 실행 수: 8건
- 자체검증 통과: 8건
- 비Green 또는 자체검증 flag: 0건
- 결론: 등록된 샘플 정책과 샘플 데이터 버전 기준으로 중대 예외는 식별되지 않았으나, 모든 결과는 인간 검토 대상이며 운영 승인 또는 외부 제출을 의미하지 않는다.

| 부문 | run_id | status | judgement | self_validation | evidence_hash | release_status |
| --- | --- | --- | --- | --- | --- | --- |
| 신용평가모형 모니터링 | run-aed3168d70ec4b11921b0a0f249d2b43 | completed | Green | PASS | 55224fbffe94c2e78ccb68c3826a1606ff6d35ee2e491e70454c6a56f4320543 | draft_ready_for_human_review |
| RWA 산출 검증 | run-0ec7d847b91d4262b1d10715e3da018a | completed | Green | PASS | bacf8e5b824056c8351ff5ce6857335ab45dbda7292045a4c813e894451027e8 | draft_ready_for_human_review |
| BIS 비율 검증 | run-c5a931cdc8f84bf09101548050838272 | completed | Green | PASS | b32bad3bbe9f72a618298cb41e65dcd8a7d49a4a0a545c2602ab7bcc5e8b7d58 | draft_ready_for_human_review |
| 연체율/부도율/회수율 모니터링 | run-e5abd720eaf6455b969a57762ea62cde | completed | Green | PASS | ea182e0a676b3343a243f9eca7e85a7ca75eed4ee79f96782941fc9f6511b001 | draft_ready_for_human_review |
| 한도 사용률 모니터링 | run-c18bd18455794d07a3639bd199cb78e3 | completed | Green | PASS | 5fe88d90a08fccf6e620f1e3b4fd9ca1da15e89d9ce53157f82fb2769830931a | draft_ready_for_human_review |
| RAPM 분석 | run-da17f28bb8ce4003ad8392a7f986eef8 | completed | Green | PASS | 36b1c27b77cfb0495195f8908481b7fe4d5f6f16e1db00c7b663d1e1684c31d3 | draft_ready_for_human_review |
| 기후리스크 검증 | run-907a565c3ba74c1284e629234e61d6e6 | completed | Green | PASS | b80ef6cf87133a1f5d82c3a6e16f6b4d8aae0dec3b7cd6048756b02dfd6fd42b | draft_ready_for_human_review |
| AI 모형 검증 | run-558714742c16416c96e1d91a120b556a | completed | Green | PASS | 00ac55b5eee59c753bd9c69592683f248b783ae9b1f14ea737a1cdbdb5b20035 | draft_ready_for_human_review |

## 2. 통제 관점 상세 해석

1. **Request / Access 통제**: 6개 샘플 요청은 공통 계약 필드를 포함하고 허용 역할로 실행되었다.
2. **Execution 통제**: 모든 metric result는 `approved_engine=True`인 deterministic stub engine에서 생성되었다. Agent가 수치를 생성하거나 보정하지 않았다.
3. **Policy / Regulation 통제**: `policy-sample-v1`과 `basel-fss-sample-map-v1`의 configurable registry 항목을 사용했다. 실제 Basel/FSS 임계치 또는 감독 해석은 하드코딩하지 않았다.
4. **Evidence 통제**: 모든 run에 evidence hash와 lineage path가 생성되었고 evidence ledger complete 상태가 확인되었다.
5. **SelfValidation 통제**: run/version/evidence 필드, 승인 엔진 여부, 위험한 Green, Red 외부공유 상태를 점검했으며 샘플 정상 케이스에서는 flag가 없었다.

## 3. 부문별 실행 상세

### 신용평가모형 모니터링

- request_id: `req-credit-model-monitoring`
- run_id: `run-aed3168d70ec4b11921b0a0f249d2b43`
- object_id / family: `credit-model-sample` / `estimation`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| pd_stability | placeholder_result | credit_model_engine | 0.1.0 | True | True |
| calibration_backtest | placeholder_result | credit_model_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| 55224fbffe94c2e78ccb68c3826a1606ff6d35ee2e491e70454c6a56f4320543 | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |

### RWA 산출 검증

- request_id: `req-rwa-validation`
- run_id: `run-0ec7d847b91d4262b1d10715e3da018a`
- object_id / family: `rwa-sample` / `measurement`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| rwa_reperformance | placeholder_result | rwa_engine | 0.1.0 | True | True |
| crm_eligibility | placeholder_result | rwa_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| bacf8e5b824056c8351ff5ce6857335ab45dbda7292045a4c813e894451027e8 | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |

### BIS 비율 검증

- request_id: `req-bis-ratio-validation`
- run_id: `run-c5a931cdc8f84bf09101548050838272`
- object_id / family: `bis-ratio-sample` / `aggregation`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| bis_ratio_reconciliation | placeholder_result | bis_ratio_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| b32bad3bbe9f72a618298cb41e65dcd8a7d49a4a0a545c2602ab7bcc5e8b7d58 | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |

### 연체율/부도율/회수율 모니터링

- request_id: `req-ddr-monitoring`
- run_id: `run-e5abd720eaf6455b969a57762ea62cde`
- object_id / family: `ddr-sample` / `estimation`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| delinquency_rate | placeholder_result | delinquency_default_recovery_engine | 0.1.0 | True | True |
| default_rate | placeholder_result | delinquency_default_recovery_engine | 0.1.0 | True | True |
| recovery_rate | placeholder_result | delinquency_default_recovery_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| ea182e0a676b3343a243f9eca7e85a7ca75eed4ee79f96782941fc9f6511b001 | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |

### 한도 사용률 모니터링

- request_id: `req-limit-monitoring`
- run_id: `run-c18bd18455794d07a3639bd199cb78e3`
- object_id / family: `limit-sample` / `measurement`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| limit_utilization | placeholder_result | limit_engine | 0.1.0 | True | True |
| threshold_proximity | placeholder_result | limit_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| 5fe88d90a08fccf6e620f1e3b4fd9ca1da15e89d9ce53157f82fb2769830931a | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |

### RAPM 분석

- request_id: `req-rapm-analysis`
- run_id: `run-da17f28bb8ce4003ad8392a7f986eef8`
- object_id / family: `rapm-sample` / `hybrid`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| risk_adjusted_return | placeholder_result | rapm_engine | 0.1.0 | True | True |
| capital_cost | placeholder_result | rapm_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| 36b1c27b77cfb0495195f8908481b7fe4d5f6f16e1db00c7b663d1e1684c31d3 | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |

### 기후리스크 검증

- request_id: `req-climate-risk-validation`
- run_id: `run-907a565c3ba74c1284e629234e61d6e6`
- object_id / family: `climate-risk-sample` / `hybrid`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| scenario_coverage | placeholder_result | climate_risk_engine | 0.1.0 | True | True |
| transition_risk_sensitivity | placeholder_result | climate_risk_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| b80ef6cf87133a1f5d82c3a6e16f6b4d8aae0dec3b7cd6048756b02dfd6fd42b | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |

### AI 모형 검증

- request_id: `req-ai-model-validation`
- run_id: `run-558714742c16416c96e1d91a120b556a`
- object_id / family: `ai-model-validation-sample` / `estimation`
- judgement: `Green` (최종 승인 아님)
- versions: data=`data-sample-v1`, code=`0.1.0`, policy=`policy-sample-v1`, regulation_mapping=`basel-fss-sample-map-v1`, engine=`0.1.0`
- self-validation flags: `없음`
- release status: `draft_ready_for_human_review`

| metric | value | engine | engine_version | approved | placeholder |
| --- | --- | --- | --- | --- | --- |
| fairness_stability | placeholder_result | ai_model_validation_engine | 0.1.0 | True | True |
| drift_monitoring | placeholder_result | ai_model_validation_engine | 0.1.0 | True | True |

| evidence_hash | source | data_version | policy_version | lineage_path | complete |
| --- | --- | --- | --- | --- | --- |
| 00ac55b5eee59c753bd9c69592683f248b783ae9b1f14ea737a1cdbdb5b20035 | prototype_lineage | data-sample-v1 | policy-sample-v1 | source_data; intermediate_result; metric_result | True |


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
