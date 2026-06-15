# 양적검증 결과 보고서(실무자용 상세본)

문서번호: 리스크감리-양검-2026-001
시행일자: 2026-05-14
공개구분: 내부검토
보존기간: 5년
수신: 리스크감리팀장
참조: 모형검증, 리스크관리, 준법감시, IT·데이터 담당부서
제목: 양적검증 결과 검토 및 조치안내(실무자용)

## 1. 검토 목적
본 문서는 리스크 산출 영역별 샘플 검증 요청에 대한 실무자 검토용 산출물이다. 본 문서는 최종 승인 문서가 아니며, 수치 계산을 수행하지 않는다.

## 2. 판정 요약
- Green: 1
- Yellow: 1
- Red: 0
- Gray: 1

## 3. 케이스별 상세 검토표
| case_id | fingerprint | risk_output_domain | validation_object_type | judgement | 결정경로 | Action Notice | Gray 사유 | 증적 공백 |
|---|---|---|---|---|---|---|---|---|
| SAMPLE-OPRISK-001 | 6a64d49f3a9c | operational_risk | aggregation_reporting | Gray | 데이터·증적 게이트 | True | LINEAGE_UNCLEAR | loss_event_boundary_definition, rcsa_to_loss_event_mapping |
| SAMPLE-LIQ-001 | c0dff39198b2 | liquidity_risk | aggregation_reporting | Green | 중대 이슈 미발견 게이트 | False | None | - |
| SAMPLE-CAPITAL-001 | e383711c77a7 | capital_adequacy_aggregation | aggregation_reporting | Yellow | 보완 가능 이슈 게이트 | True | None | - |

## 4. 재현가능성 및 설명가능성
- 각 케이스는 `case_fingerprint`로 식별되며, fingerprint 입력 필드는 request type, 1축/2축 분류, 정책·감독기준·계산엔진 참조로 고정된다.
- `decision_stage`는 deterministic decision protocol의 어느 게이트에서 판정 후보가 결정되었는지 나타낸다.
- `explanation_summary`는 계산이 아니라 증적 상태와 정책/엔진 참조의 존재 여부를 요약한다.

## 5. 조치 및 확인사항
- Yellow/Red/Gray 케이스는 Action Notice를 생성하고 담당부서, 목표기한, 필요 증적, 재검증 트리거를 지정한다.
- Green 케이스도 최종 승인 또는 무결성 보증이 아니며 인간 검증자의 검토가 필요하다.
- 모든 계산값은 공식 계산엔진 결과 ID와 원천 증적을 통해서만 확인한다.

## 6. 붙임
1. validation_workbook.xlsx
2. artifact_manifest.json
3. risk_domain_samples.json
