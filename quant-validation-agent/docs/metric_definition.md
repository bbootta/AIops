# metric_definition.md

본 문서는 본 프로젝트에서 사용하는 정량 지표의 **정의 / 입력 / 출력 / 해석 / 한계**를 정리한다.

---

## KS (Kolmogorov–Smirnov)
- 정의: 양호/불량 누적분포 함수 차이의 최댓값.
- 입력: `y_true ∈ {0,1}`, `score`.
- 출력: 0~1 실수.
- 해석: 클수록 변별력 강함.
- 한계: 극단 표본의 영향, 임계점 단일 값 의존.

## AUROC
- 정의: ROC curve 아래 면적.
- 입력: `y_true`, `score`.
- 출력: 0.5~1.
- 해석: 클수록 변별력 강함. 0.5는 무작위.
- 한계: 클래스 불균형에 영향, 보정력은 측정하지 않음.

## Gini / AR (Accuracy Ratio)
- 정의: `2 × AUROC − 1`.
- 입력/출력: 위와 동일.
- 해석: 클수록 변별력 강함.
- 한계: AUROC와 동일.

## PSI (Population Stability Index)
- 정의: `Σ (a − e) × ln(a / e)` (a: 기간 분포, e: 기준 분포).
- 입력: 두 분포 또는 두 표본 + bin 수.
- 출력: 0 이상 실수.
- 해석: < 0.10 안정 / 0.10~0.25 주의 / ≥ 0.25 불안정.
- 한계: bin 정의에 민감. 0 비중 처리(epsilon)에 의존.

## CDR (Cumulative Default Rate)
- 정의: `default_count / exposure_count`.
- 입력: 부도건수, 관측건수.
- 출력: 0~1.
- 한계: 분모/분자 정의에 민감.

## SDR (Survival Default Rate, 생존기반 부도율)
- 정의: 생존 표본 기준 부도율.
- 입력: 생존건수, 노출건수.
- 한계: 분모 정의가 정확해야 한다.

## Brier Score
- 정의: `mean((pred_pd − y)^2)`.
- 입력: `pred_pd ∈ [0,1]`, `y ∈ {0,1}`.
- 해석: 작을수록 좋음.
- 한계: 단독으로 변별력은 측정하지 않음.

## Calibration Table
- 정의: 예측 확률의 bucket별 평균 vs 실현 부도율 비교.
- 입력: `pred`, `actual`, bucket 정의.
- 한계: bucket 수와 분포에 민감.

## MAE / RMSE / Bias (LGD/EAD)
- MAE: `mean(|y − ŷ|)`
- RMSE: `sqrt(mean((y − ŷ)^2))`
- Bias: `mean(ŷ − y)`
- 한계: 단위/스케일에 의존, segment 분리 분석 권장.

## VIF (Variance Inflation Factor)
- 정의: 다중공선성 지표.
- 출력: 1 이상.
- 해석: > 5 주의, > 10 심각.
- 한계: 비선형 관계는 잡지 못함.

## Condition Index
- 정의: 설계행렬 X^T X 고유값의 sqrt 비율.
- 해석: ≥ 30 다중공선성 심각.

## Scenario Order Check
- 정의: `base ≤ adverse ≤ severe` (손실/PD/multiplier 기준).
- 해석: 위반은 자동 Red.
- 한계: 시나리오 정의/적용 정합성을 따라간다.
