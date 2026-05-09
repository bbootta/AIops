# 은행 리스크감리팀 양적검증 팀 에이전트 운영 패키지

## 1. 목적

본 패키지는 은행 리스크감리팀의 **양적검증 팀 에이전트**를 운영하기 위한 역할, 프로세스, 체크리스트, 프롬프트, 보고서 및 조치안내 템플릿을 제공한다. 목표는 코드베이스 구현이 아니라 실무자가 즉시 사용할 수 있는 팀 에이전트 운영 기준을 만드는 것이다.

본 팀 에이전트는 향후 AVI 상위 오케스트레이터의 하위 서브에이전트로 편입될 수 있도록 고정된 역할, 입력·출력, 판단 통제, 감사추적 항목을 갖는다.

## 2. 적용 업무

- 신용평가모형 검증
- 신용위험측정요소 PD/LGD/EAD 검증
- 위험요소 및 거시변수 검증
- 정기 모니터링
- 수시 검증
- 보고서 초안 작성
- 비Green 조치안내 작성
- 규제 변화 후보 영향분석 및 후보 검증통제 제안

## 3. 핵심 운영 원칙

1. LLM은 직접 수치 계산, 재계산, 추정 계산, 임계값 산출을 수행하지 않는다.
2. 계산엔진 결과, 승인된 리포트, 공식 데이터 증적 없이 정량 결론을 내리지 않는다.
3. 판정 라벨은 **Green / Yellow / Red / Gray**만 사용한다.
4. Amber라는 용어는 입력에 등장해도 출력 판정으로 사용하지 않는다.
5. 정책 미정의, 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족은 **Gray**로 분류한다.
6. Green은 최종 승인, 무결성 보증, 규제 적합성 보증이 아니다.
7. Yellow / Red / Gray는 반드시 Action Notice를 생성한다.
8. 최종 판단과 공식 승인은 인간 검증자 및 공식 조직에 남긴다.
9. 규제 변화는 후보 검증통제 제안까지만 수행하고 자동 반영하지 않는다.

## 4. 운영상 가정

- 은행 내부 정책문서, 승인된 모형문서, 계산엔진 산출물, 데이터 lineage 증적이 공식 판단의 기준이다.
- 본 팀 에이전트는 검증업무 보조, 문서화, 점검 누락 방지, 감사추적 보강을 목적으로 한다.
- 수치 계산과 최종 승인 판단은 에이전트의 역할이 아니다.
- AVI 편입을 고려해 각 문서는 독립적으로도 읽히고, 상위 오케스트레이터가 참조하기 쉬운 고정 섹션 구조를 사용한다.
- 내부 정책 임계값, 규제 해석, 승인권자 명칭은 기관별 정책에 맞게 보완한다.

## 5. 초기 검증대상 분기

| 분기 코드 | 대상 | 대표 업무 |
|---|---|---|
| `credit_rating_model` | 신용평가모형 | 등급모형 개발·변경·정기검증, 성능 모니터링 |
| `credit_risk_parameter` | PD/LGD/EAD | 위험측정요소 산출·보정·사후검증 |
| `risk_factor_validation` | 위험요소·거시변수 | 변수 정의, 시계열 안정성, 시나리오 적합성 |
| `aggregation_reporting` | 집계·보고 | 포트폴리오 집계, 리스크 보고서, 대시보드 |
| `hybrid_risk_output` | ST/ICAAP/IRRBB 등 | 스트레스테스트, 자본적정성, 금리리스크 산출물 |

## 6. 팀 에이전트 구성

1. Intake & Scope Agent
2. Validation Object Classifier Agent
3. Data Readiness & Lineage Agent
4. Quant Validation Method Agent
5. Calculation Result Reviewer Agent
6. Policy & Judgement Agent
7. Report & Visualization Agent
8. Remediation & Action Notice Agent
9. Regulation Monitoring Agent
10. Governance & Audit Trail Agent

## 7. 산출물 사용 순서

1. `TEAM_AGENT_SYSTEM_PROMPT.md`를 에이전트 최상위 지침으로 설정한다.
2. `TEAM_AGENT_ROLE_MAP.md`로 역할별 책임과 핸드오프를 확인한다.
3. `VALIDATION_OBJECT_CLASSIFICATION.md`로 검증대상 유형을 분류한다.
4. `TEAM_AGENT_WORKFLOW.md`에 따라 접수부터 감사추적까지 진행한다.
5. `DATA_READINESS_CHECKLIST.md`로 데이터, 권한, lineage, 증적을 점검한다.
6. `QUANT_VALIDATION_METHOD_GUIDE.md`로 계산엔진에 요청할 검증방법 후보를 정한다.
7. `JUDGEMENT_POLICY_TEMPLATE.md`로 Green / Yellow / Red / Gray 후보 판정을 문서화한다.
8. `REPORT_TEMPLATE.md`로 검증보고서 초안을 작성한다.
9. Yellow / Red / Gray인 경우 `ACTION_NOTICE_TEMPLATE.md`로 조치안내를 발행한다.
10. 규제 변화 요청은 `REG_CHANGE_CANDIDATE_CONTROL.md`로 후보 통제 제안까지만 수행한다.
11. `AUDIT_TRAIL_CHECKLIST.md`로 증적 완결성을 점검한다.
12. `UAT_EVALUATION_CHECKLIST.md`와 `GO_NO_GO_CHECKLIST.md`로 운영 전 검증을 수행한다.

## 8. 완료 기준

- 모든 요청은 case_id와 request_id를 가진다.
- 검증대상 유형이 5개 분기 중 하나로 분류되거나, 분류 불가 사유가 Gray로 기록된다.
- 계산엔진 결과가 없는 정량 결론은 생성되지 않는다.
- Yellow / Red / Gray 판정 후보에는 Action Notice가 연결된다.
- 모든 산출물은 인간 검증자 검토란과 공식 조직 최종 결정란을 남긴다.
