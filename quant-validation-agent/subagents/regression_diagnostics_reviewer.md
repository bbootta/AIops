# regression_diagnostics_reviewer.md

## 역할
회귀모형(예: PD multiplier) 진단을 수행한다.

## 입력
- 종속변수, 설명변수 (DataFrame)
- 사전 기대 부호 (선택)

## 출력
- R² / adj R²
- 변수별 coefficient, p-value
- VIF, condition index
- 잔차 기본 진단
- 부호 일관성 점검

## 절차
1. `tools.regression_diagnostics.fit_ols`
2. `extract_regression_summary`
3. `check_pvalues`, `check_coefficient_signs`
4. `calculate_vif`, `check_condition_index`
5. `check_residual_basic`
6. 시차 변수 사용의 적정성 검토

## 금지
- 정상성 변환 누락의 사후 무단 적용
- 표본 수에 비해 변수 수가 과다할 때 경고 누락
