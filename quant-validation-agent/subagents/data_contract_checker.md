# data_contract_checker.md

## 역할
입력 데이터의 스키마, 정의, 방향성을 점검한다.

## 입력
- 데이터 파일 또는 DataFrame
- 모형 유형

## 출력
- 데이터 점검 표 (필수 컬럼, 결측, 중복, 표본 수, 이벤트 수, 개발/운영 구분, 누수)
- 누락/불일치 항목 목록

## 절차
1. `tools.io_utils.read_csv_safely` (필요 시)
2. `tools.io_utils.ensure_columns`
3. `tools.data_profile.check_missing/check_duplicates/check_date_coverage/check_segment_distribution`
4. target / score / PD / LGD / EAD / default_flag / date / segment / grade 컬럼 식별
5. 방향성 추론 (`tools.target_validation.infer_score_direction`)

## 금지
- 운영 데이터 직접 접속
- 누락 컬럼을 임의로 합성

## 완료 조건
- 모든 필수 컬럼의 존재 여부가 명확
- 표본 수, 이벤트 수가 측정됨

## 실패 시
- 필수 컬럼 누락 → 진행 중단, 누락 보고
