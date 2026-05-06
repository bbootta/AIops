# metric_calculator.md

## 역할
모형 유형별 정량 지표를 계산한다.

## 입력
- 모형 유형
- 데이터 (DataFrame)
- 적용 지표 목록

## 출력
- 지표 결과 dict
- 지표 표 (markdown 가능)
- 수치 범위 / 방향성 점검 결과

## 절차
1. 입력 검증 (`tools.target_validation`)
2. 변별력: `tools.metric_ks_auc_ar`
3. 안정성: `tools.metric_psi`, `tools.binning_stability`
4. 보정력: `tools.metric_calibration`
5. CDR/SDR: `tools.metric_cdr_sdr`
6. LGD/EAD: `tools.metric_lgd_ead`
7. 회귀: `tools.regression_diagnostics`
8. 시나리오: `tools.scenario_order_check`

## 금지
- 임계값 하드코딩
- 분모 0 / NaN의 무단 처리
- 방향성 임의 가정

## 완료 조건
- 결과 dict 또는 DataFrame, 메타데이터(샘플 수, 결측 수, 적용 함수) 포함
