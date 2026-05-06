# ead_model_validation.md

## 목적
EAD/CCF 모형의 예측-실현 비교, CCF 오차, 한도사용률 구간 분석.

## 입력
- `customer_id`, `predicted_ead`, `realized_ead`, `limit`, `drawn_amount`, `default_date`
- (선택) `product_type`, `ccf_predicted`, `ccf_realized`, `off_balance_flag`

## 절차
1. EAD 값 검증 (`tools.metric_lgd_ead.validate_ead_values`)
2. MAE / RMSE / Bias
3. CCF 오차 (예측 CCF vs 실현 CCF)
4. 상품군별 오차 (`tools.metric_lgd_ead.summarize_error_by_segment`)
5. 한도사용률 (`drawn_amount / limit`) 구간별 오차
6. 부도시점 EAD 산정 기준 일관성 점검
7. off-balance exposure 처리 점검

## 산출물
- 검증 요약 (RAG)
- 오차 표 (전체 / 상품군 / 한도사용률 구간)
- CCF 오차 표
- 이상 징후 / 한계

## 금지
- 음수/과도한 CCF의 무단 처리
- off-balance exposure 처리 변경의 임의 적용
