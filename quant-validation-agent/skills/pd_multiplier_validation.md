# pd_multiplier_validation.md

## 목적
거시경제 시나리오 기반 PD multiplier / 회귀모형 검증.

## 입력
- 시계열 입력: `period`, 종속변수, 설명변수 n개
- 시나리오 입력: `scenario` (`base`/`adverse`/`severe`), `period`, 설명변수, 산출 결과 (`pd_pred` 또는 `pd_multiplier`)

## 절차
1. 변수/표본 비율 점검 (`tools.sample_size_check`)
2. 회귀 적합 (`tools.regression_diagnostics.fit_ols`)
3. 회귀 진단:
   - R² / adj R²
   - p-value (`check_pvalues`)
   - 계수 부호 (`check_coefficient_signs`)
   - VIF (`calculate_vif`)
   - condition index (`check_condition_index`)
   - 잔차 기본 (`check_residual_basic`)
4. 시나리오 서열 점검 (`tools.scenario_order_check.check_scenario_order`)
5. multiplier floor 점검 (`check_pd_multiplier_floor`)
6. 챌린저 모형 비교 (선택)

## 산출물
- 회귀 요약 표 (계수, p-value, VIF, CI)
- 시나리오 결과 표 (base/adverse/severe)
- 서열 위반 / floor 위반 표
- 이상 징후 / 한계

## 금지
- 시나리오 서열 위반을 “해석 가능하다”는 사유로 묵과
- 변수 수가 표본 수에 비해 과다할 때 경고 누락
- 정상성 변환 누락의 임의 사후 적용
