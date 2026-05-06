# challenger_model_validation.md

## 목적
챔피언 모형과 챌린저 모형의 정량 비교.

## 입력
- 두 모형의 score 또는 예측 PD
- 동일 표본의 target / default_flag

## 절차
1. 동일 표본·기간에서 KS/AUROC/AR 비교
2. PSI 비교 (개발 vs 운영, 시점별)
3. Calibration 비교 (PD인 경우)
4. 회귀모형이면 회귀진단 비교
5. 안정성 비교 (rank ordering, 등급 분포)

## 산출물
- 모형별 지표 비교 표
- 차이 해석 (단정 금지)
- 이상 징후 / 한계

## 금지
- 단일 지표만으로 챌린저 채택 권고
- 동일 조건 비교가 보장되지 않은 상태에서 결과 비교
