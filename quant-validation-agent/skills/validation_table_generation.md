# validation_table_generation.md

## 목적
검증 리포트용 표만 표준 양식으로 생성.

## 입력
- 계산 결과 dict / DataFrame

## 절차
1. `tools.validation_summary.build_metric_summary`
2. `tools.validation_summary.build_issue_table`
3. `tools.validation_summary.assign_rag_status` (지표별 RAG)
4. `tools.validation_summary.build_validation_commentary` (단정 금지 초안)

## 산출물
- 표 (markdown)
- RAG 표
- 코멘터리 초안

## 금지
- 자체 생성 텍스트로 단정형 의견 추가
- 임계값을 함수 외부에서 임의로 변경
