# credit_score_validation.md

## 목적
신용평가 / 스코어링 모형의 변별력, 안정성, 등급 분포, 누수 점검.

## 입력
- `customer_id`, `score`, `target` (0/1), `obs_date`, `dataset`
- (선택) `grade`, `segment`, `exposure`

## 절차
1. 데이터 계약 확인 (`data_contract_checker`)
2. score 방향성 추정/검증 (`tools.target_validation.infer_score_direction`)
3. KS, AUROC, AR 계산 (`tools.metric_ks_auc_ar`)
4. decile / 등급 테이블 (`tools.metric_ks_auc_ar.build_decile_table`)
5. PSI 계산 (개발 vs 운영) (`tools.metric_psi`)
6. rank ordering 점검 (`tools.binning_stability.check_rank_ordering`)
7. 표본 적정성 (`tools.sample_size_check`)
8. 결과 요약 (`tools.validation_summary`)

## 산출물
- 검증 요약 (RAG 포함)
- 지표 표 (KS/AUROC/AR/PSI)
- 등급별 분포·bad rate 표
- 이상 징후 / 한계

## 금지
- score 방향성 임의 가정
- 임계값 임의 완화
- 적합/부적합 단정
