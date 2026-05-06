# Policy — Credit Scoring Model

신용평가모형(개인/기업/소호) 정기 검증 기준. 본 임계값은 참고용 default이며,
모형/포트폴리오 정책에 의해 조정될 수 있다. 임계 변경은 `harness/change_manifest.json`에
기록한다.

## 1. 검증 범위
- 변별력 (KS, AUROC, Gini)
- 안정성 (PSI: 개발 vs 운영, 시점간)
- 등급분포 단조성
- 캘리브레이션 (등급별 추정 PD vs CDR)
- 챌린저 비교 (필요시)

## 2. 참고 임계
| 지표 | 통과 | 주의 | 불안정 |
|---|---|---|---|
| KS | ≥ 0.30 | 0.20 ~ 0.30 | < 0.20 |
| AUROC | ≥ 0.70 | 0.65 ~ 0.70 | < 0.65 |
| Gini | ≥ 0.40 | 0.30 ~ 0.40 | < 0.30 |
| PSI | < 0.10 | 0.10 ~ 0.25 | ≥ 0.25 |

## 3. 표본 적정성 (default)
- 총 표본 ≥ 1,000
- 부도 건수 ≥ 50
- 등급별 표본 ≥ 30

부족 시 결과 산출은 하되 강한 결론을 회피하고 신뢰구간을 명시한다.

## 4. 점검 절차
1. `tools/data_profile.*` 로 결측·중복·기간 누락 점검
2. `tools/metric_ks_auc.*` 로 변별력
3. `tools/metric_psi.*` 로 안정성
4. `tools/binomial_calibration.calibration_test_per_grade` 로 등급별 캘리브레이션
5. `tools/run_validation.run` 으로 end-to-end 보고서 초안 생성

## 5. 금지
- 임계 임의 완화
- score 부호 규약 미명시
- 등급 cutoff 자동 변경
