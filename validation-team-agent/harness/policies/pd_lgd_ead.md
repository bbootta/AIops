# Policy — PD / LGD / EAD

신용위험측정요소(PD, LGD, EAD)의 검증 기준.

## 1. PD
- 변별력: 신용평가모형과 동일 임계 적용 (`harness/policies/credit_scoring.md`)
- 캘리브레이션: 등급별 PD vs CDR (`tools/binomial_calibration.calibration_test_per_grade`)
- Holm-Bonferroni 다중보정 적용 권고
- 등급별 표본 < 30 시 신뢰구간 폭을 보고서에 명시

## 2. LGD
- downturn LGD vs 평상시 LGD 구분 기준 명시
- 회수 인정 시점·임계가 모형 가정과 일치하는지 확인
- 부도시점 표본 적정성 (`middleware/sample_size_guard`)
- 추정 LGD vs 실측 LGD 비교 (평균/중위/분포)

## 3. EAD
- CCF 추정 시 한도 사용률 0% / 100% 극단값 처리 기준 명시
- 한도 사용률 분포의 안정성 (PSI)
- 추정 EAD vs 실측 EAD 비교

## 4. 공통 점검
- 부도 정의 일관성
- 표본 기간 / 개발-운영 분리
- 누수 (`middleware/leakage_guard`)

## 5. 임계 변경
임계 변경은 `harness/change_manifest.json`에 사유·증거·롤백 기준과 함께 기록.
