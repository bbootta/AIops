# Skill — Data Quality Review

## 목적
검증 대상 데이터의 정의·결측·이상치·중복·기간 누락·표본 분포·누수 가능성을
일관된 절차로 점검한다.

## 입력
- 데이터 파일 (DataFrame 형태로 로드 가능)
- 컬럼 정의 (이름, 타입, 단위, 결측 표기)
- 표본 기간 (개발/운영 구분)
- 목표변수 정의

## 절차
1. `tools/data_profile.profile_dataframe(df)`로 기초 프로파일 산출.
2. `tools/data_profile.check_missing(df)`로 결측 컬럼·비율 산출.
3. 키 컬럼이 정의되어 있으면 `check_duplicates(df, key_cols)`로 중복 점검.
4. `check_date_coverage(df, date_col)`로 기간 누락 점검.
5. `middleware/data_safety_guard`로 민감정보 패턴 탐지.
6. `middleware/sample_size_guard`로 표본 적정성 점검.
7. `middleware/leakage_guard`로 누수 변수 점검.

## 산출물
- 결측 / 이상치 / 중복 / 기간 누락 요약표
- 표본 적정성 평가
- 민감정보·누수 위반 사항
- 추가 확인 필요 컬럼 목록

## 금지
- 원천 데이터를 보고서에 그대로 기록 (요약·통계만 허용)
- 결측·이상치 처리 기준을 임의로 확정

## 완료 기준
- 모든 컬럼에 대해 점검 결과가 산출되었는가
- 위반 사항이 명시되었는가
- 표본 부족 여부가 명시되었는가
