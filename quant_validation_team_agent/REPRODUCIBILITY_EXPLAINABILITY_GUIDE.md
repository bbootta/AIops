# 검증결과 재현가능성·설명가능성 가이드

## 1. 목적

본 문서는 양적검증 팀 에이전트가 동일한 입력에 대해 동일한 검증결과를 재생산하고, 판정 후보가 어떤 근거와 결정경로로 생성되었는지 실무자와 감사인이 추적할 수 있도록 하는 운영 기준이다.

## 2. 재현가능성 원칙

- 모든 케이스는 `case_fingerprint`를 가진다.
- fingerprint 입력 필드는 고정되어야 하며, 입력 순서가 바뀌어도 동일한 fingerprint가 생성되어야 한다.
- 정책 버전, 감독기준 출처, 계산엔진 결과 ID, 1축/2축 분류가 바뀌면 다른 fingerprint로 처리한다.
- 동일 fingerprint에서 판정 후보, Gray 사유코드, Action Notice 필요 여부가 달라지면 재현성 결함으로 기록하고 `Gray`로 전환한다.

## 3. Fingerprint 필드

현재 산출물 생성기와 테스트는 다음 필드를 fingerprint 입력으로 사용한다.

| 필드 | 설명 |
|---|---|
| `request_type` | 정기검증, 수시검증, 모니터링 등 요청 유형 |
| `validation_object_type` | 1축 검증대상 유형 |
| `risk_output_domain` | 2축 리스크 산출 영역 |
| `primary_risk_output_domain` | 복합 산출물의 주영역 |
| `secondary_risk_output_domains` | 복합 산출물의 부영역 목록 |
| `scope_statement` | 검증 범위와 제외 범위 |
| `policy_reference` | 내부 정책문서 ID/버전 |
| `regulatory_source_reference` | Basel/FSS/국내 감독기준 출처 |
| `calculation_engine_result_reference` | 승인된 계산엔진 결과 ID |

## 4. 설명가능성 원칙

- 설명은 수치 재계산이 아니라 증적 상태, 정책 참조, 계산엔진 결과 참조의 존재 여부를 근거로 작성한다.
- 각 케이스는 `decision_stage`와 `explanation_summary`를 가진다.
- `decision_stage`는 deterministic decision protocol의 게이트명과 일치해야 한다.
- `explanation_summary`는 판정 후보가 왜 Green/Yellow/Red/Gray인지 사람이 검토 가능한 문장으로 요약한다.

## 5. Decision Stage 표준값

| decision_stage | 사용 조건 |
|---|---|
| 금지 요청 게이트 | LLM 직접 계산, Amber 강제, 규제 자동 반영, 권한 없는 접근 요청 |
| 리스크 영역 게이트 | `risk_output_domain`이 불명확하거나 복수 영역 주영역 근거가 없음 |
| 공식 기준 게이트 | 정책 또는 감독기준 출처가 미정의/불명확 |
| 데이터·증적 게이트 | 데이터 부족, 표본 부족, lineage 불명확, 증적 부족 |
| 계산엔진 게이트 | 계산엔진 결과 ID, 버전, 로그, 파라미터 파일 부재 |
| 명시적 위반 게이트 | 공식 증적으로 중대 정책 위반 또는 신뢰성 훼손 후보 확인 |
| 보완 가능 이슈 게이트 | 중대성은 확정되지 않았으나 보완자료 또는 조치 추적 필요 |
| 중대 이슈 미발견 게이트 | 필수 증적과 계산결과가 있고 중대 이슈 후보 미발견 |

## 6. 산출물 반영 위치

| 산출물 | 반영 내용 |
|---|---|
| `validation_workbook.xlsx` | `Case_Register`, `Reproducibility`, `Explainability` 시트에 fingerprint, 결정경로, 설명요약 기록 |
| `practitioner_report.*` | 케이스별 표에 fingerprint 축약값과 결정경로 기록, 재현가능성·설명가능성 섹션 포함 |
| `executive_report.*` | 경영진용 요약에 재현가능성 및 설명가능성 통제 문구 포함 |
| `artifact_manifest.json` | `sample_fingerprints`, `explainability_index`, `fingerprint_fields` 기록 |

## 7. 테스트 기준

- `tests/validate_risk_domain_samples.py`는 fingerprint가 64자리 SHA-256 hex 형식이고 입력 순서와 무관하게 안정적인지 확인한다.
- `tests/validate_output_artifacts.py`는 엑셀에 `Reproducibility`와 `Explainability` 시트가 있는지, 매니페스트에 fingerprint와 설명 인덱스가 있는지 확인한다.
- 생성기를 두 번 실행한 뒤 XLSX/HWPX 해시가 동일해야 한다.
