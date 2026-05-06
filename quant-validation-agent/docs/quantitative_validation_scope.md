# quantitative_validation_scope.md

본 문서는 양적검증의 적용 범위를 명시한다.

---

## 1. 개발 검증 (Development Validation)
- 학습/검증/OOT 표본 분리 점검
- 변별력 (KS/AUROC/AR), rank ordering
- 보정력 (calibration table, Brier)
- 누수 점검 (사후정보 컬럼)
- 표본 적정성
- 회귀모형의 진단 (VIF, condition index, p-value, 부호)

## 2. 운영 검증 (In-use / Ongoing Validation)
- 개발 표본 대비 운영 표본 PSI
- 등급 분포 변화
- 시점별 default rate / observed vs predicted
- backtesting
- 기간별 calibration 변화
- segment별 분포 안정성

## 3. 정기 모니터링
- 분기/연 단위 PSI, CDR/SDR 추이
- 임계 도달 모니터링
- 분포 변화 vs 실제 부도 증가 구분

## 4. 모형 변경 검증
- 변경 전/후 성능 비교
- 변경된 변수의 안정성, 상관, 누수 점검
- 변경 사유와 기대 효과의 사후 확인

## 5. 챌린저 모형 비교
- 챔피언 모형 vs 챌린저 모형 변별력/보정력
- 안정성 (PSI, rank ordering)
- 회귀모형이면 회귀진단 비교

## 6. 거시경제 시나리오 기반 검증
- 회귀계수 부호/p-value/VIF/condition index
- 시나리오 서열 (base ≤ adverse ≤ severe)
- multiplier floor 적용 정합성
- 시나리오 적용 후 PD/PD multiplier 결과의 비논리적 변화 탐지
