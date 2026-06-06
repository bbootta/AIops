# 양적검증 팀 에이전트 End-to-End 워크플로우

## 1. 목적

요청 접수부터 인간 검증자 및 공식 조직 판단까지의 절차를 표준화하고, 비Green 조치와 감사추적을 자동 누락 없이 관리한다.

## 2. 공통 가정 및 하네스

- LLM은 직접 수치 계산, 재계산, 추정 계산, 임계값 산출을 수행하지 않는다.
- 계산엔진 결과, 승인된 리포트, 공식 데이터 증적 없이 정량 결론을 내리지 않는다.
- 판정 라벨은 `Green`, `Yellow`, `Red`, `Gray`만 사용한다.
- `Amber`는 사용하지 않는다.
- 정책 미정의, 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족은 `Gray`로 분류한다.
- `Green`은 최종 승인이나 무결성 보증이 아니다.
- `Yellow`, `Red`, `Gray`는 Action Notice를 생성한다.
- 최종 판단은 인간 검증자 및 공식 승인 조직에 남긴다.

## 3. 공통 핸드오프 필드

모든 단계는 다음 필드를 유지한다.

- `case_id`
- `request_id`
- `request_type`
- `case_fingerprint`
- `case_fingerprint_status`
- `validation_object_type`
- `risk_output_domain`
- `primary_risk_output_domain`
- `secondary_risk_output_domains`
- `business_context`
- `scope_statement`
- `input_documents`
- `data_readiness_status`
- `lineage_status`
- `calculation_engine_result_reference`
- `policy_reference`
- `regulatory_source_reference`
- `evidence_gaps`
- `provisional_judgement`
- `required_action_notice`
- `human_reviewer_required`
- `audit_trail_items`

## 4. 단계별 절차

| 단계 | 진입조건 | 주요 활동 | 종료조건 | 산출물 | Gray 전환조건 |
|---:|---|---|---|---|---|
| 1. Intake 접수 | 검증 요청 수신 | 요청자, 목적, 대상, 기준일, 기대 산출물 확인 | 범위와 제외범위 기록 | Intake 요약 | 요청 목적 또는 대상 불명확 |
| 2. 검증대상·리스크영역 분류 | Intake 완료 | 5개 초기 분기와 리스크 산출 영역을 2축으로 분류 | 분류 근거와 불확실성 기록 | `validation_object_type`, `risk_output_domain` | 유형 또는 리스크 영역 분류 불가 |
| 3. 데이터 준비성 및 lineage 점검 | 분류 완료 | 데이터 소유부서, 기준일, 표본, 권한, lineage, 증적 확인 | Ready/Gap 판정 | 데이터 체크리스트 | 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족 |
| 4. 검증방법 후보 선정 | 데이터 상태 확인 | 업무유형별 계산엔진 요청사항 정의 | 필요 산출물 목록 확정 | 방법 후보 | 정책 미정의 또는 산출물 요구사항 불명확 |
| 5. 계산엔진 결과 수신 확인 | 방법 후보 확정 | 계산결과 ID, 버전, 로그, 입력 데이터 ID 확인 | 결과 참조 가능 여부 기록 | 결과 수신 확인 | 계산엔진 결과 미제공 또는 재현성 부족 |
| 6. 결과 리뷰 | 계산결과 존재 | 출처, 정책 기준, 해석상 유의점 검토 | 발견사항 초안 기록 | 결과 리뷰 메모 | 수치 출처 불명확 또는 로그 부족 |
| 7. 감독기준·정책 기준 매핑 | 결과 리뷰 완료 | Basel/FSS/국내 감독기준, 내부 정책, 승인문서, 임계값 출처 매핑 | 기준 출처와 정책 근거 기록 | 기준 매핑표 | 공식 출처, 국내 적용 여부, 정책 버전 불명확 |
| 8. 판정 후보 작성 | 정책 매핑 완료 | deterministic 우선순위와 tie-break에 따라 Green/Yellow/Red/Gray 중 후보 판정 | 근거, 적용 규칙, 제한사항 명시 | 판정 후보 | 판단 불가 사유 또는 동일 fingerprint 결과 불일치 |
| 9. 보고서 초안 작성 | 판정 후보 존재 | 보고서 템플릿에 결과 정리 | 인간 검토 가능한 초안 완성 | 보고서 초안 | 핵심 증적 누락 |
| 10. Action Notice 작성 (Remediation & Action Notice Agent) | 판정 후보가 Yellow/Red/Gray | 사유, 소유자, 기한, 필요 증적, 재검증 조건 정의 | Notice ID 생성 | Action Notice | 비Green인데 Notice 정보 부족 |
| 11. 감사추적 패키징 | 보고서/Notice 작성 | 입력, 결과, 정책, Agent 산출물, 인간 검토 항목을 묶고 `artifact_manifest.json`을 생성한다. 매니페스트에는 `sample_fingerprints`, `explainability_index`, `fingerprint_fields`를 포함한다. | 감사추적 체크 및 산출물 매니페스트 생성 완료 | Audit Trail Package, `artifact_manifest.json` | 재현성 항목 또는 매니페스트 필수 필드 누락 |
| 12. 인간 검증자 검토 및 공식 조직 판단 | 감사추적 완료 | 인간 검증자가 사실관계, 정책 적용, 최종 의견 확인 | 공식 조직 결정 기록 | 최종 검토 기록 | 인간 검토 미완료 → Gray 전환 및 Action Notice 생성 |

## 4-R. 규제 변화 병렬 트랙 (Regulation Monitoring Agent)

규제 변화 탐지는 표준 12단계와 독립적으로 운영되는 병렬 트랙이다.

| 단계 | 진입조건 | 주요 활동 | 종료조건 | 산출물 | Gray 전환조건 |
|---:|---|---|---|---|---|
| R-1. 규제 변화 탐지 | 새 Basel/FSS/국내 법규 수신 | 관련 업무 범위, 영향 모형/파라미터 목록 | 영향 대상 확정 | 영향분석 초안 | 영향 범위 불명확 |
| R-2. 후보 통제 제안 | 영향분석 완료 | 후보 통제 내용 기술, 승인 전 적용 금지 명시 | 후보 통제 초안 생성 | 후보 통제 문서 | 기준 해석 불명확 |
| R-3. 정책 소유자 전달 | 후보 통제 초안 | 정책 담당부서에 후보 검토 요청 전달 | 전달 기록 생성 | 전달 기록 및 Governance 통보 | 전달 대상 불명확 |

**제약:** Regulation Monitoring Agent는 후보 영향분석과 후보 통제 제안까지만 수행한다. 정책 개정, 자동 반영, 최종 적용 결정은 정책 소유자 및 공식 조직이 한다.

## 5. 동일 요청-동일 결과 통제

- 모든 건은 `DETERMINISTIC_DECISION_PROTOCOL.md`의 `case_fingerprint` 필드를 생성하거나 누락 사유를 기록한다. `risk_output_domain`은 fingerprint 필수 입력이다.
- 입력 문서 순서, 표현 차이, 요청 문구 차이는 정규화하되, 정책 버전·데이터 해시·계산엔진 결과 ID가 다르면 다른 건으로 처리한다.
- 판정 후보는 금지 요청 → 리스크 영역 게이트 → 공식 기준 → 데이터·증적 → 계산엔진 → 명시적 위반 → 보완 가능 이슈 → 중대 이슈 미발견 순서로만 결정한다.
- 동일 fingerprint의 과거 결과와 현재 결과가 다르면 재현성 결함으로 기록하고 `Gray` 및 Action Notice를 생성한다.
- 규제 변화 병렬 트랙의 완료 기준에는 R-3 정책 소유자 전달 기록 및 Governance 통보가 포함되어야 하며, R-2 후보 통제 문서만으로 완료 처리하지 않는다.

## 6. 비Green 자동 분기

- `Yellow`: 보완 필요 또는 제한적 이슈. Action Notice를 생성하고 재검증 조건을 지정한다.
- `Red`: 중대한 결함, 정책 위반, 결과 신뢰성 훼손 가능성. Action Notice와 에스컬레이션 후보를 생성한다.
- `Gray`: 판단 불가. 사유코드와 필요 증적을 Action Notice에 기록한다.
- `Green`: Action Notice는 생성하지 않지만 제한사항과 최종 승인 아님 문구를 보고서에 기록한다.

## 7. 중지 조건

- 사용자가 수치 계산을 LLM에 요구하는 경우.
- 계산엔진 결과 없이 정량 결론을 요구하는 경우.
- Amber 판정을 강제하는 경우.
- 규제 변화 자동 반영 또는 정책 자동 개정을 요구하는 경우.
- 권한 없는 데이터 접근 또는 증적 은폐를 요구하는 경우.

중지 시에는 거절 사유, 허용 가능한 대안, 필요한 공식 증적을 기록하고 `Gray` 후보 또는 인간 검토 필요 상태로 넘긴다.
