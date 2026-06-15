# 동일 요청-동일 결과 결정 프로토콜

## 1. 목적

동일한 검증 요청사항, 동일한 입력 증적, 동일한 정책 버전, 동일한 계산엔진 결과가 제공되면 양적검증 팀 에이전트가 항상 동일한 분류, 동일한 Gray 사유, 동일한 판정 후보, 동일한 Action Notice 생성 여부를 산출하도록 결정 절차를 고정한다.

## 2. 공통 가정 및 금지사항

- LLM은 수치 계산, 임계값 추정, 임의 가중치 부여, 확률적 샘플링을 수행하지 않는다.
- 동일성 판단은 `case_fingerprint`로 수행한다.
- 기준·증적·계산결과 버전이 하나라도 다르면 동일 요청으로 보지 않는다.
- 불확실성은 창의적으로 보완하지 않고 정해진 우선순위에 따라 `Gray` 또는 인간 검토로 보낸다.

## 3. Case Fingerprint

동일 요청 여부는 다음 필드를 정규화한 뒤 해시 또는 고정 문자열로 기록한다.

```yaml
case_fingerprint_inputs:
  request_type: ""
  validation_object_type: ""
  risk_output_domain: ""
  primary_risk_output_domain: ""
  secondary_risk_output_domains: []
  business_context: ""
  scope_statement: ""
  obligor_or_portfolio_scope: ""
  product_scope: ""
  model_or_parameter_id: ""
  model_or_parameter_version: ""
  policy_reference_id: ""
  policy_reference_version: ""
  data_reference_id: ""
  data_as_of_date: ""
  data_extract_version_or_hash: ""
  calculation_engine_name: ""
  calculation_engine_version: ""
  calculation_engine_result_id: ""
  calculation_parameter_file_hash: ""
  regulatory_source_reference: ""
  regulatory_source_version: ""
```

필드 누락 시 `case_fingerprint_status = incomplete`로 두고 `Gray` 후보를 생성한다.

## 4. 입력 정규화 규칙

| 항목 | 정규화 규칙 |
|---|---|
| 판정 라벨 | `Green`, `Yellow`, `Red`, `Gray`만 허용. 입력의 `Amber`는 금지어로 표기하고 판정값으로 저장하지 않음 |
| 날짜 | ISO-8601 `YYYY-MM-DD` 형식으로 기록 |
| 정책 버전 | 문서명, 승인일, 버전, 적용일을 결합 |
| 계산결과 | 엔진명, 엔진버전, 결과 ID, 입력 데이터 ID, 파라미터 해시를 결합 |
| 리스크 산출 영역 | `risk_output_domain`, `primary_risk_output_domain`, `secondary_risk_output_domains` 모두 `RISK_OUTPUT_TAXONOMY.md`의 표준 코드로 기록하고 복합 영역은 주영역과 부영역을 분리 |
| 데이터 범위 | 기준일, 관측기간, 모집단, 제외조건을 결합 |
| 결측/표본/권한/lineage | 충족, 미충족, 확인불가 중 하나로 기록 |

리스크 산출 영역 세부 정규화:

- `risk_output_domain`은 단일 표준 코드만 허용한다. 불명확하거나 복수 영역의 주영역 근거가 없으면 `multi_risk_or_unclear`로 기록하고 `Gray` 후보를 생성한다.
- `primary_risk_output_domain`은 `risk_output_domain`과 동일한 표준 코드 집합을 사용하며, 복합 산출물에서도 하나의 주영역 코드만 기록한다. 주영역을 정할 공식 보고 목적 또는 산출물 소유부서 근거가 없으면 비워 두지 말고 `multi_risk_or_unclear`로 기록한다.
- `secondary_risk_output_domains`는 표준 코드 배열만 허용한다. 자유 텍스트, 별칭, 한글 설명은 저장하지 않는다. 값은 중복 제거 후 사전순으로 정렬하고, 부영역이 없으면 빈 배열 `[]`로 기록한다.
- 사용자가 `신용리스크`, `Credit Risk`, `IRRBB`, `금리리스크`처럼 표준 코드가 아닌 텍스트를 입력하면 먼저 `RISK_OUTPUT_TAXONOMY.md`의 표준 코드/명칭/대표 산출물 alias로 정규화한다. 정규화 가능한 텍스트 입력은 fingerprint 불일치 사유나 Gray 사유가 아니다.
- 정규화 전 원문은 감사추적의 원문 입력에만 보관하고, `case_fingerprint`에는 정규화 후 표준 코드만 사용한다. 표준 코드로 매핑할 수 없는 텍스트이거나 주영역 근거가 없는 경우에만 `multi_risk_or_unclear` 및 `Gray` 후보로 처리한다.
- `regulatory_source_reference`는 `BASEL_FSS_CONTROL_MAPPING.md` 공식 출처 레지스터의 `ID` 값만 허용한다. 자유 텍스트 출처명은 정규화 전 원문에만 보관하고 fingerprint 입력값에는 표준 ID를 사용한다.

## 5. 결정 우선순위

판정 후보는 아래 순서로만 결정한다. 앞 단계 조건이 충족되면 뒤 단계에서 완화하지 않는다.

1. **금지 요청 게이트**: LLM 직접 계산, 계산엔진 없는 수치 결론, Amber 강제, 규제 자동 반영, 권한 없는 데이터 접근 요청은 중지하고 `Gray` 또는 인간 검토로 전환한다.
2. **리스크 영역 게이트**: `risk_output_domain`이 불명확하거나 복수 영역 영향의 주영역 근거가 없으면 `Gray`다.
3. **공식 기준 게이트**: 공식 기준 출처, 국내 적용 여부, 내부 정책 버전이 불명확하면 `Gray`다.
4. **데이터·증적 게이트**: 정책 미정의, 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족은 `Gray`다.
5. **계산엔진 게이트**: 계산엔진 결과 ID, 버전, 입력 데이터 ID, 실행 로그, 파라미터 파일이 없으면 정량 결론 금지 및 `Gray`다.
6. **명시적 위반 게이트**: 공식 정책 위반 또는 결과 신뢰성 훼손 가능성이 공식 증적으로 확인되면 `Red` 후보를 검토한다.
7. **보완 가능 이슈 게이트**: 중대성은 확정되지 않았으나 보완자료, 설명, 제한적 조치가 필요하면 `Yellow` 후보를 검토한다.
8. **중대 이슈 미발견 게이트**: 모든 필수 증적과 계산결과가 있고 중대 이슈 후보가 없을 때만 `Green` 후보를 작성한다.

## 6. Tie-break 규칙

| 충돌 상황 | 결정 |
|---|---|
| Gray 조건과 Yellow/Red 조건이 동시에 존재 | 정량 결론은 보류하고 `Gray`를 우선 기록하되, 잠재 Yellow/Red 이슈를 Action Notice에 보조 이슈로 기록 |
| Yellow와 Red가 동시에 가능 | 공식 정책 위반 또는 신뢰성 훼손 가능성이 명시 증적으로 뒷받침되면 Red, 아니면 Yellow |
| Green과 다른 판정이 동시에 가능 | Green 금지, 비Green 우선 |
| 리스크 산출 영역이 복수로 가능 | 공식 보고 목적과 산출물 소유부서를 기준으로 주영역을 정하고, 근거가 없으면 `multi_risk_or_unclear` 및 Gray |
| 국내 기준과 Basel 원칙 적용 해석이 불일치 | 국내 시행 기준과 감독당국 승인조건을 우선 확인하고, 해석 불명확 시 Gray |
| 동일 fingerprint에서 이전 결과와 현재 결과 불일치 | 결정 재현성 결함으로 기록하고 Governance 검토 전까지 Gray |

## 7. Action Notice 결정표

| 판정 후보 | Action Notice | 필수 내용 |
|---|---|---|
| Green | 생성하지 않음 | 제한사항과 최종 승인 아님 문구를 보고서에 기록 |
| Yellow | 생성 | 보완 필요 사유, 소유자, 기한, 필요 증적, 재검증 트리거 |
| Red | 생성 | 중대 이슈 후보, 영향 범위, 에스컬레이션 대상, 재검증 트리거 |
| Gray | 생성 | Gray 사유코드, 부족 증적, 판단 보류 사유, 인간 검토 필요사항 |

## 8. 재현성 감사 항목

- `case_fingerprint`
- `case_fingerprint_status`
- `risk_output_domain` 및 주영역/부영역 분류 근거
- 정규화 전 입력 원문
- 정규화 후 입력 값
- 적용된 결정 우선순위 단계
- `decision_stage`
- `explanation_summary`
- 적용된 tie-break 규칙
- 판정 후보
- Action Notice 생성 여부
- 이전 동일 fingerprint 결과와 비교 결과
- 인간 검증자 변경 여부 및 변경 사유

## 9. UAT 필수 재현성 테스트

| 테스트 | 절차 | 기대결과 |
|---|---|---|
| 동일 입력 반복 | 동일 입력 패키지를 3회 실행 | `validation_object_type`, `risk_output_domain`, 판정 후보, Gray 사유코드, Notice 필요 여부가 동일 |
| 입력 순서 변경 | 동일 파일을 다른 순서로 제출 | 정규화 후 동일 fingerprint와 동일 결과 |
| 정책 버전 변경 | 정책 버전만 변경 | 다른 fingerprint로 기록하고 재판정 |
| 계산결과 ID 변경 | 계산엔진 결과 ID만 변경 | 다른 fingerprint로 기록하고 결과 출처 재검토 |
| Amber 입력 반복 | Amber 판정 요청 반복 | Amber 미사용, 동일한 거절/재분류 결과 |

## 10. 운영 중 재현성 결함 처리

- 동일 fingerprint에서 결과가 달라지면 즉시 `Gray`로 전환한다.
- 차이 원인이 정책 또는 증적 버전 변경이면 fingerprint를 갱신하고 신규 건으로 처리한다.
- 차이 원인이 프롬프트 변동, Agent 임의 해석, 누락된 tie-break라면 UAT 결함으로 등록한다.
- 결함 종결 전까지 해당 유형의 자동 초안 결과는 인간 검증자 전수 검토 대상으로 지정한다.

## 11. 설명가능성 산출 기준

- 모든 판정 후보는 `decision_stage`와 `explanation_summary`를 함께 기록한다.
- `decision_stage`는 본 문서의 결정 우선순위 게이트 중 하나여야 한다.
- `explanation_summary`는 수치 계산이 아니라 정책 참조, 감독기준 출처, 계산엔진 결과 ID, 데이터·증적 공백의 존재 여부를 설명한다.
- 실무자용 보고서, 엑셀 검증파일, 산출물 매니페스트는 동일한 fingerprint와 설명 인덱스를 공유해야 한다.

