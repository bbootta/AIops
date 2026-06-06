# 검증보고서 초안 템플릿

## 1. 목적

검증 결과를 인간 검증자가 검토할 수 있는 보고서 초안으로 정리한다. 본 보고서는 조치 이행 관리 문서가 아니며, Yellow/Red/Gray는 별도 Action Notice로 관리한다.

## 2. 공통 가정 및 보고서 통제

- 본 보고서는 검증 결과 초안이며 최종 승인 문서가 아니다.
- 모든 수치는 계산엔진, 승인된 리포트, 공식 증적 출처를 표기해야 한다.
- LLM이 직접 산출한 수치처럼 보이는 표현은 금지한다.
- 계산엔진 결과 없이 정량 결론을 작성하지 않는다.
- 판정 라벨은 `Green`, `Yellow`, `Red`, `Gray`만 사용한다.
- `Amber`는 사용하지 않는다.
- `Green`은 최종 승인 또는 공식 조직의 승인 결정을 의미하지 않는다.
- `Yellow`, `Red`, `Gray` 판정 후보가 있으면 별도 Action Notice를 참조한다.

## 3. 보고서 표지

- 보고서명:
- case_id:
- request_id:
- case_fingerprint:
- case_fingerprint_status:
- 검증대상:
- validation_object_type:
- risk_output_domain:
- primary_risk_output_domain:
- secondary_risk_output_domains:
- regulatory_source_reference:
- 기준일/검증기간:
- 작성일:
- 작성 Agent:
- 인간 검증자:
- 공식 승인 조직:

## 4. Executive Summary

- 검증 목적:
- 주요 범위:
- 주요 발견사항:
- 판정 후보: Green | Yellow | Red | Gray
- Action Notice 필요 여부:
- 핵심 제한사항:
- 최종 승인 아님 고지: 본 결과는 인간 검증자 및 공식 승인 조직의 검토가 필요하다.

## 5. 검증대상 및 범위

- 대상 업무:
- 리스크 산출 영역 및 분류 근거:
- 포함 범위:
- 제외 범위:
- 관련 정책/규정:
- Basel/FSS/국내 감독기준 출처 및 기준일:
- 관련 모델/파라미터/보고서:
- 주요 이해관계자:

## 6. 사용 데이터 및 Lineage

| 항목 | 내용 | 증적 참조 |
|---|---|---|
| 데이터 소유부서 |  |  |
| 원천계 |  |  |
| 기준일 |  |  |
| 추출 조건 |  |  |
| 모집단 정의 |  |  |
| 표본 관련 산출물 |  |  |
| lineage 경로 |  |  |
| 권한 승인 |  |  |
| 재현성 정보 |  |  |

## 7. 적용 검증방법

| 방법 후보 | 목적 | 계산엔진 산출물 참조 | 정책 근거 | 제한사항 |
|---|---|---|---|---|
|  |  |  |  |  |

## 8. 계산엔진 산출물 요약

- 계산엔진명/버전:
- 결과 ID:
- 입력 데이터 ID:
- 실행일시:
- 파라미터 파일:
- 실행 로그:
- 결과 파일 위치:
- 수치 출처 고지: 아래 수치는 에이전트 계산값이 아니라 계산엔진 또는 공식 증적의 요약이다.

## 9. 주요 발견사항

| 번호 | 발견사항 | 근거 증적 | 영향 가능성 | 판정 영향 | 후속조치 |
|---:|---|---|---|---|---|
| 1 |  |  |  |  |  |

## 10. 판정 후보

- provisional_judgement:
- 판정 근거:
- 정책문서 및 버전:
- 감독기준 출처 및 적용 여부:
- 적용된 deterministic 결정 단계:
- 계산엔진 결과 참조:
- 제한사항:
- 인간 검증자 확인사항:

## 11. Action Notice 요약

| Notice ID | 판정 후보 | 사유 | 담당 부서 | 기한 | 상태 |
|---|---|---|---|---|---|
|  | Yellow/Red/Gray |  |  |  |  |

Green인 경우: Action Notice는 생성하지 않으며 제한사항은 본 보고서에 기록한다.

## 12. 첨부 증적 목록

| 증적 ID | 파일/시스템 | 설명 | 버전/해시 | 보관 위치 |
|---|---|---|---|---|
|  |  |  |  |  |

## 13. 인간 검증자 검토란

- 검토자:
- 검토일:
- 검토 의견:
- 판정 변경 여부:
- 추가 요청사항:
- 공식 조직 상정 여부:
- 최종 조직 결정 참조:

## 14. 산출물 매니페스트 생성 책임

- Report & Visualization Agent는 보고서 초안 작성 시 `artifact_manifest.json` 생성 입력을 함께 확정한다.
- Governance & Audit Trail Agent는 최종 패키징 단계에서 `artifact_manifest.json`을 생성·검증한다.
- 매니페스트는 최소한 `generated_at`, `case_id`, `request_id`, `case_fingerprint`, `sample_fingerprints`, `explainability_index`, `fingerprint_fields`, `artifacts`를 포함한다.
- `fingerprint_fields`는 `DETERMINISTIC_DECISION_PROTOCOL.md`의 `case_fingerprint_inputs`와 동일한 필드 목록을 사용한다.
- 보고서, 엑셀 검증파일, 매니페스트의 fingerprint 및 설명 인덱스가 서로 다르면 재현성 결함으로 보고하고 `Gray` 후보를 검토한다.
