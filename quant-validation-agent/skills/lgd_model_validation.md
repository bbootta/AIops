# lgd_model_validation.md

## 목적
LGD 모형의 예측-실현 비교, 오차, segment 분석, downturn 점검.

## 입력
- `customer_id`, `predicted_lgd`, `realized_lgd`, `default_date`, `recovery_completed_flag`
- (선택) `collateral_type`, `segment`, `recovery_period_days`, `discount_rate`

## 절차
1. LGD 범위 검증 (`tools.metric_lgd_ead.validate_lgd_range`)
2. MAE / RMSE / Bias 계산 (`tools.metric_lgd_ead`)
3. segment / 담보유형별 오차 (`tools.metric_lgd_ead.summarize_error_by_segment`)
4. 미완료 회수건 처리 점검 (recovery_completed_flag 분포)
5. downturn 식별 가능성 (`default_date` 기준 경기 국면 분포)
6. 표본 적정성

## 산출물
- 검증 요약 (RAG)
- 오차 표 (전체 / segment / 담보유형)
- 미완료 회수 비중 / 정책 일관성
- 이상 징후 / 한계

## 금지
- 음수/100% 초과 LGD를 무단 절단하여 보고
- 미완료 회수건을 무단 제외/포함하여 결과 왜곡
