# monitoring_validation.md

## 목적
운영 단계의 정기 모니터링 지표 산출.

## 입력
- 시점별 등급 분포, default 건수, 노출 건수
- 기준(baseline) 분포

## 절차
1. 시점별 PSI (`tools.metric_psi`)
2. 등급 분포 변화 (`tools.binning_stability.compare_grade_distribution`)
3. CDR / SDR 추이 (`tools.metric_cdr_sdr`)
4. observed vs predicted 추이 (`tools.metric_calibration.summarize_observed_vs_predicted`)
5. RAG 부여 (`tools.validation_summary.assign_rag_status`)

## 산출물
- 시점별 지표 표
- 분포 이동 요약
- 이상 징후 / 한계

## 금지
- 분모 변화(포트폴리오 구성 변화)와 분자 변화(실제 부도 증가) 혼동
- 단일 시점 이상치 만으로 모형 부적합 결론
