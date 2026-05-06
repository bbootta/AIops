# calibration_checker.md

## 역할
predicted vs realized 괴리를 점검한다.

## 입력
- PD: `pred_pd`, `default_flag`, `bucket`/`grade`
- LGD: `predicted_lgd`, `realized_lgd`
- EAD: `predicted_ead`, `realized_ead`

## 출력
- Calibration table (bucket별)
- Brier score (PD)
- bias (PD/LGD/EAD)
- 과소/과대추정 구간

## 절차
1. `tools.metric_calibration.build_calibration_table`
2. `tools.metric_calibration.calculate_brier_score`
3. `tools.metric_calibration.calculate_pd_bias`
4. `tools.metric_calibration.summarize_observed_vs_predicted`

## 금지
- LDP에서 일반 임계값 무비판 적용
- bucket 수의 임의 조정으로 결과 왜곡
