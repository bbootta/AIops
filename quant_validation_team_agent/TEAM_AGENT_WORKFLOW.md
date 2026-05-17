# TEAM_AGENT_WORKFLOW

## 1. 목적

양적검증 팀 에이전트의 End-to-End 업무 흐름을 정의한다. 본 워크플로우는 요청 접수부터 보고서 초안, Action Notice, 감사추적, 인간 검증자 검토까지 연결한다.

## 2. 공통 통제

- LLM은 직접 수치 계산, 재계산, 추정 계산, 임계값 산출을 수행하지 않는다.
- 계산엔진 결과, 승인된 리포트, 공식 데이터 증적 없이 정량 결론을 내리지 않는다.
- 판정 라벨은 Green, Yellow, Red, Gray만 허용한다.
- Amber라는 용어는 입력에 등장해도 출력 판정으로 사용하지 않는다.
- 정책 미정의, 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족은 Gray로 분류한다.
- Green은 최종 승인이나 무결성 보증이 아니라 현재 제공된 증적 기준 중대 이슈 후보 미발견 상태다.
- Yellow, Red, Gray는 반드시 Action Notice를 생성한다.
- 최종 판단과 공식 승인은 인간 검증자 및 승인 조직에 귀속된다.
- 규제 변화는 후보 검증통제 제안까지만 수행하고 자동 반영하지 않는다.

## 3. 단계별 워크플로우

| 단계 | 수행 Agent | 진입조건 | 주요 활동 | 종료조건 | 산출물 | Gray 전환조건 |
|---|---|---|---|---|---|---|
| 1. Intake 접수 | Intake & Scope | 요청서 수신 | 요청 목적, 대상, 기한, 범위, 제외범위 확인 | case_id/request_id 부여 | Intake Summary | 요청 목적 또는 대상 불명확 |
| 2. 검증대상 분류 | Classifier | Intake Summary 존재 | 5개 분기 중 분류 | validation_object_type 기록 | Classification Memo | 분류정보 부족 |
| 3. 데이터 준비성 및 lineage 점검 | Data Readiness | 분류 완료 | 데이터 소유, 기준일, 모집단, 표본, 결측, 권한, lineage 확인 | 체크리스트 완료 | Data Readiness Result | 데이터/표본/권한/lineage/증적 부족 |
| 4. 검증방법 후보 선정 | Method | 데이터 점검 결과 | 검증방법 후보와 계산엔진 필요 산출물 정의 | 계산엔진 요청 목록 확정 | Method Plan | 정책상 방법 미정의 |
| 5. 계산엔진 결과 수신 여부 확인 | Calculation Reviewer | Method Plan 존재 | 결과 ID, 실행 로그, 버전, 파라미터 확인 | 결과 참조 기록 | Calculation Evidence Log | 결과 미제공, 실행 로그 부재 |
| 6. 결과 리뷰 | Calculation Reviewer | 계산엔진 결과 존재 | 결과 출처와 해석 유의점 정리 | 수치 결론 없이 리뷰 완료 | Result Review Memo | 재현성 증적 부족 |
| 7. 정책 기준 매핑 | Policy & Judgement | 결과 리뷰, 정책문서 존재 | 정책 기준과 증적 매핑 | 정책 근거 기록 | Policy Mapping | 정책 미정의 |
| 8. 판정 후보 도출 | Policy & Judgement | 정책 매핑 완료 | Green/Yellow/Red/Gray 후보 선택 | 판정 후보와 근거 기록 | Judgement Memo | 판단 불가 사유 존재 |
| 9. 보고서 초안 작성 | Report | 판정 후보 존재 | 보고서 본문, 제한사항, 증적 목록 작성 | 인간 검토 가능한 초안 | Draft Report | 필수 섹션 누락 |
| 10. Action Notice 작성 | Remediation | 판정 후보가 Yellow/Red/Gray | 사유, 조치, 담당, 기한, 증적 요구 작성 | Notice ID 발급 | Action Notice | 담당/조치 미정 |
| 11. 감사추적 패키징 | Governance | 모든 중간 산출물 존재 | 입력, 버전, 결과 ID, 정책, 판정, 인간 검토란 확인 | Audit Pack 완성 | Audit Trail Checklist | 재현성 부족 |
| 12. 인간 검증자 검토 | 인간 검증자/공식 조직 | Audit Pack 완성 | 최종 검토, 질의, 승인 또는 반려 | 공식 결정 기록 | Final Decision Record | 조직 결정 보류 |

## 4. 핸드오프 기준

각 단계는 다음 필드를 최소한으로 다음 단계에 전달한다.

```yaml
case_id:
request_id:
validation_object_type:
business_context:
scope_statement:
input_documents:
data_readiness_status:
lineage_status:
calculation_engine_result_reference:
policy_reference:
evidence_gaps:
provisional_judgement:
required_action_notice:
human_reviewer_required: true
audit_trail_items:
```

필수 필드 누락 시 다음 단계로 진행하지 않고 누락 사유를 Action Notice 후보로 기록한다.

## 5. 예외 처리

- 긴급 수시 검증: 기한 압박이 있어도 수치 계산 금지와 증적 기반 원칙은 완화하지 않는다.
- 규제 변화 요청: 규제 변화 후보 영향분석은 가능하나 정책 반영·자동 적용은 금지한다.
- 자료 접근 제한: 권한 승인 또는 공식 대체 증적을 요청하고 Gray 후보로 기록한다.
- 결과 불일치: 계산엔진 결과와 보고서 수치가 불일치하면 수치를 수정하지 않고 reconciliation 요청을 발행한다.

## 6. 운영상 가정

- 공식 workflow owner는 리스크감리팀이며, 시스템 owner와 데이터 owner는 별도일 수 있다.
- 단계별 산출물은 전자결재 또는 GRC 시스템에 첨부 가능해야 한다.
