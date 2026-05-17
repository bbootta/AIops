# TEAM_AGENT_ROLE_MAP

## 1. 목적

양적검증 팀 에이전트를 구성하는 10개 역할의 책임, 입력, 출력, 금지사항, 후속 전달 대상을 정의한다. 모든 Agent는 직접 수치 계산을 수행하지 않으며, 승인된 계산엔진 결과와 공식 증적을 검토·요약·문서화한다.

## 2. 공통 핸드오프 포맷

| 필드 | 설명 | 필수 여부 |
|---|---|---|
| `case_id` | 검증 건 단위 식별자 | 필수 |
| `request_id` | 접수 요청 식별자 | 필수 |
| `validation_object_type` | 5개 초기 분기 코드 | 필수 |
| `business_context` | 업무 배경과 사용 목적 | 필수 |
| `scope_statement` | 검증 범위와 제외 범위 | 필수 |
| `input_documents` | 정책, 모형문서, 데이터 목록 | 필수 |
| `data_readiness_status` | 데이터 준비성 상태 | 필수 |
| `lineage_status` | lineage 확인 상태 | 필수 |
| `calculation_engine_result_reference` | 계산엔진 결과 ID, 실행일, 버전 | 조건부 필수 |
| `policy_reference` | 적용 정책문서와 버전 | 필수 |
| `evidence_gaps` | 증적 공백 목록 | 필수 |
| `provisional_judgement` | Green / Yellow / Red / Gray | 필수 |
| `required_action_notice` | Action Notice 필요 여부 | 필수 |
| `human_reviewer_required` | 인간 검증자 검토 필요 여부 | 항상 예 |
| `audit_trail_items` | 감사추적 항목 목록 | 필수 |

핸드오프 누락 시 필수 입력 누락 사유를 기록하고 다음 단계 진행을 보류한다. 정책 미정의, 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족은 Gray 후보로 전환한다.

## 3. 역할별 책임 매핑

| Agent | 주요 책임 | 입력 | 출력 | 금지사항 | 후속 전달 |
|---|---|---|---|---|---|
| Intake & Scope Agent | 요청 접수, 범위 정의, 제외범위 명시, 필요자료 목록화 | 요청서, 업무 배경, 대상 시스템 | 요청 요약, 범위, 제외범위, 필요자료 목록 | 승인 여부 판단, 수치 계산 | Validation Object Classifier |
| Validation Object Classifier Agent | 5개 초기 분기 중 하나로 분류 | 요청 요약, 대상 설명 | validation_object_type, 분류 근거, 불확실성 | 임의 정책 해석, 최종 판정 | Data Readiness & Lineage |
| Data Readiness & Lineage Agent | 데이터 기준일, 모집단, 표본, 결측, 권한, lineage 점검 | 데이터 명세, 추출조건, 증적 | 데이터 준비성 체크 결과, Gray 조건 여부 | 누락 데이터 보정 계산 | Quant Validation Method |
| Quant Validation Method Agent | 검증방법 후보와 계산엔진 필요 산출물 정의 | 분류 결과, 정책, 모형문서 | 검증방법 후보, 필요 계산엔진 산출물 | 직접 통계량 계산, 임계값 창작 | Calculation Result Reviewer |
| Calculation Result Reviewer Agent | 계산엔진 결과 존재 여부와 출처 확인, 해석상 유의점 정리 | 계산엔진 결과, 실행 로그, 버전 | 결과 참조, 품질 이슈, 해석 유의점 | 계산 재수행, 수치 수정 | Policy & Judgement |
| Policy & Judgement Agent | 정책 기준 매핑, 판정 후보 도출 | 정책문서, 결과 리뷰, 증적 공백 | Green/Yellow/Red/Gray 판정 후보, 근거 | 최종 승인, 비허용 라벨 사용 | Report & Visualization, Remediation |
| Report & Visualization Agent | 보고서 초안, 표·그림 요청사항, 제한사항 작성 | 판정 후보, 계산엔진 결과 참조 | 보고서 초안, 시각화 요청사항 | 수치 생성, 승인 문구 작성 | Governance & Audit Trail |
| Remediation & Action Notice Agent | Yellow/Red/Gray 조치안내 생성 | 판정 후보, 이슈 목록 | Action Notice, 담당·기한·증적 요구 | Green에 조치안내 생성, 최종 종결 승인 | Governance & Audit Trail |
| Regulation Monitoring Agent | 규제 변화 후보 영향분석, 후보 통제 제안 | 규제 원문, 내부 정책 매핑 | 후보 영향분석, 후보 검증통제 | 자동 정책 반영, 적용 확정 | Policy Owner, Governance |
| Governance & Audit Trail Agent | 감사추적 완결성, 재현성, 인간 검토란 확인 | 모든 중간 산출물 | 감사추적 체크 결과, 누락 증적 목록 | 증적 사후 창작, 공식 결정 대체 | 인간 검증자 및 공식 조직 |

## 4. Agent별 출력 고정 문구

- 모든 Agent 출력에는 “수치 계산 미수행”과 “인간 검증자 검토 필요”를 포함한다.
- Green 출력에는 “최종 승인 아님”을 포함한다.
- Yellow / Red / Gray 출력에는 “Action Notice 필요”를 포함한다.
- 증적 공백이 있으면 공백 종류를 `POLICY_UNDEFINED`, `DATA_INSUFFICIENT`, `SAMPLE_INSUFFICIENT`, `ACCESS_LIMITED`, `LINEAGE_UNCLEAR`, `EVIDENCE_INSUFFICIENT` 중 하나 이상으로 태깅한다.

## 5. 운영상 가정

- Agent 간 메시지는 위 공통 핸드오프 포맷을 JSON 또는 표 형식으로 전달할 수 있다.
- AVI 편입 시 상위 오케스트레이터는 `validation_object_type`, `provisional_judgement`, `required_action_notice`를 라우팅 키로 사용한다.

## 6. LLM 운영 하네스

- 모든 Agent는 LLM 기반 문서화·검토 보조 역할이며 직접 수치 계산을 수행하지 않는다.
- 계산엔진 결과가 없으면 정량 결론을 내리지 않고 Gray 후보와 증적 요청을 생성한다.
- 인간 검증자와 공식 조직의 최종 판단권은 어떤 Agent도 대체하지 않는다.
