# pd_model_validation.md

## 목적
PD 모형의 변별력, 보정력, CDR/SDR, 시계열 안정성, backtesting.

## 입력
- `customer_id`, `pd` (0~1), `default_flag` (0/1), `obs_date`, `grade` 또는 `bucket`
- (선택) `segment`, `exposure`

## 절차
1. PD 범위 검증 (`tools.target_validation.validate_probability_values`)
2. 변별력 (KS/AUROC/AR) — `pd`를 score로 사용
3. Calibration table (`tools.metric_calibration.build_calibration_table`)
4. Brier score (`tools.metric_calibration.calculate_brier_score`)
5. PD bias (`tools.metric_calibration.calculate_pd_bias`)
6. CDR / SDR (`tools.metric_cdr_sdr`)
7. 시계열 안정성: 시점별 PSI / observed-vs-predicted (`tools.metric_psi`, `tools.metric_calibration.summarize_observed_vs_predicted`)
8. 표본/부도건수 적정성 (`tools.sample_size_check`)

## 산출물
- 검증 요약 (RAG)
- 지표 표 (AUC/AR/Brier/Bias)
- Calibration 표 (bucket별)
- CDR/SDR 표 (등급별)
- 시계열 안정성 표
- 이상 징후 / 한계

## 금지
- 단기 관측치만으로 장기평균 PD를 단정하기
- LDP에서 일반 임계값을 무비판적으로 적용
