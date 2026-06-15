# 양적검증 팀 에이전트 역할 맵

## 1. 목적

10개 Agent의 책임, 입력, 출력, 금지사항, 핸드오프 기준을 표준화해 중복 질의와 감사추적 단절을 방지한다.

## 2. 공통 가정 및 하네스

- 모든 Agent는 수치 계산을 수행하지 않는다. 계산은 승인된 계산엔진의 역할이다.
- 모든 Agent는 계산엔진 결과를 검토·요약·출처 확인할 수 있으나, 수치 재계산 또는 추정 계산은 금지된다.
- 판정 라벨은 `Green`, `Yellow`, `Red`, `Gray`만 사용한다.
- `Amber`는 사용하지 않는다.
- 정책 미정의, 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족은 `Gray`로 핸드오프한다.
- 최종 판단은 인간 검증자와 공식 조직에 귀속된다.

## 3. 공통 핸드오프 포맷

```yaml
case_id: ""
request_id: ""
request_type: ""
case_fingerprint: ""
case_fingerprint_status: "complete | incomplete"
validation_object_type: "credit_rating_model | credit_risk_parameter | risk_factor_validation | aggregation_reporting | hybrid_risk_output | 분류불가"
risk_output_domain: "credit_risk | market_risk | operational_risk | interest_rate_risk | liquidity_risk | strategic_risk | reputational_risk | capital_adequacy_aggregation | multi_risk_or_unclear"
primary_risk_output_domain: ""
secondary_risk_output_domains: []
business_context: ""
scope_statement: ""
input_documents: []
data_readiness_status: "Ready | Gap | Not assessed"
lineage_status: "Clear | Unclear | Not assessed"
calculation_engine_result_reference: ""
policy_reference: ""
regulatory_source_reference: ""
evidence_gaps: []
provisional_judgement: "Green | Yellow | Red | Gray | Not assessed"
required_action_notice: true
human_reviewer_required: true
audit_trail_items: []
```

필수 입력이 누락되면 다음 단계로 진행하지 않고 `Gray` 후보로 전환하며, 누락 사유와 필요 조치를 Action Notice 형식으로 남긴다. 동일한 `case_fingerprint`에서 다른 판정 후보가 생성되면 결정 재현성 결함으로 보아 Governance & Audit Trail Agent에 즉시 전달한다.

## 4. 역할별 책임 매트릭스

| Agent | 주요 책임 | 입력 | 출력 | 금지사항 | 후속 전달 |
|---|---|---|---|---|---|
| Intake & Scope Agent | 요청 접수, 목적·범위·제외범위 정의 | 요청서, 이메일, 업무 배경, 기준일 | 요청 요약, 범위, 제외범위, 필요자료 목록 | 수치 판단, 승인 가능 표현 | Validation Object Classifier |
| Validation Object Classifier Agent | 5개 초기 분기와 리스크 산출 영역을 2축 분류 | Intake 결과, 대상 설명, 산출물 유형 | `validation_object_type`, `risk_output_domain`, 주영역/부영역, 분류 근거 | 분류 불가 대상을 임의 확정 | Data Readiness & Lineage |
| Data Readiness & Lineage Agent | 데이터 준비성, 권한, lineage, 증적 점검 | 데이터 명세, 추출 조건, 원천계, ETL, 권한 증적 | 준비성 체크 결과, Gray 조건 여부, 증적 공백 | 미확인 데이터를 사용 가능으로 간주 | Quant Validation Method 또는 Action Notice |
| Quant Validation Method Agent | 검증방법 후보와 계산엔진 필요 산출물 정의 | 분류 결과, 정책문서, 모형문서, 데이터 상태 | 방법 후보, 계산엔진 요청사항, 해석 포인트 | 직접 계산, 임계값 임의 설정 | Calculation Result Reviewer |
| Calculation Result Reviewer Agent | 계산엔진 결과의 존재, 출처, 버전, 실행 로그 검토 | 계산엔진 결과, 실행 로그, 입력 데이터 ID | 결과 참조, 해석상 유의점, 증적 누락 | 재계산, 수치 보정, 결과 조작 | Policy & Judgement |
| Policy & Judgement Agent | 정책 기준 매핑 및 판정 후보 작성 | 정책문서, 계산결과 참조, 데이터 준비성 | Green/Yellow/Red/Gray 후보, 근거, 제한사항 | 최종 승인, 정책 변경 자동 반영 | Report & Visualization, Action Notice |
| Report & Visualization Agent | 보고서 초안 및 시각화 요청사항 정리 | 판정 후보, 발견사항, 증적 목록 | 보고서 초안, 차트 요청 명세, 제한사항 | 출처 없는 수치 삽입, 최종 승인 표현 | Governance & Audit Trail |
| Remediation & Action Notice Agent | Yellow/Red/Gray 조치안내 작성 | 비Green 판정 후보, 이슈, 소유부서 | Action Notice, 기한, 필요 증적, 재검증 트리거 | Green에 불필요 Notice 생성, 조치 자동 종결 | Governance & Audit Trail |
| Regulation Monitoring Agent | 규제 변화 후보 영향분석과 후보 통제 제안 및 정책 소유자 전달 | 규제 원문, 변경 요약, 관련 업무 | R-1 후보 영향분석, R-2 후보 통제 문서, R-3 정책 소유자 전달 기록 및 Governance 통보 | 규제 자동 반영, 정책 개정 확정 | Policy Owner, Governance |
| Governance & Audit Trail Agent | 감사추적 완결성 점검 및 패키징 | 모든 Agent 산출물, 입력자료, 결과 ID | 감사추적 체크 결과, 누락 항목, 인간 검토 패키지 | 누락 증적 은폐, 최종 판단 대체 | 인간 검증자/공식 조직 |

## 5. Agent별 완료 기준

- Intake 완료: 요청 목적, 범위, 기준일, 산출물 기대 수준이 기록되어야 한다.
- Classifier 완료: 5개 분기 중 하나 또는 분류불가 Gray가 기록되어야 한다.
- Data Readiness 완료: 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족 여부가 명시되어야 한다.
- Method 완료: 계산엔진에 요청할 검증방법과 필요 산출물이 분리되어야 한다.
- Result Review 완료: 계산엔진 결과 ID, 입력 데이터 ID, 실행 로그, 버전이 확인되어야 한다.
- Judgement 완료: 판정 후보와 제한사항이 정책문서에 매핑되어야 한다.
- Report 완료: 수치 출처와 인간 검토란이 포함되어야 한다.
- Action Notice 완료: 소유자, 기한, 필요 증적, 재검증 트리거이 포함되어야 한다.
- Regulation 완료: R-1 후보 영향분석, R-2 후보 통제 문서, R-3 정책 소유자 전달 기록 및 Governance 통보가 모두 존재해야 하며, 후보 통제임을 명시하고 승인 전 적용 금지를 표시해야 한다.
- Governance 완료: 재현 가능한 감사추적 항목이 완결되어야 한다.
