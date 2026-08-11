# Policy — IFRS 9 ECL

IFRS 9 ECL 산출의 검증 기준.

## 1. 스테이지 분류
- 1 / 2 / 3 분류 일관성 (단방향 전이 vs 회복 사유의 명시)
- SICR 트리거의 정의·일관 적용
- 정성/정량 기준의 문서화 여부

## 2. 시나리오 가중치
- `sum(weights) == 1.0`
- 가중치 변동 시 사유의 문서화
- 변동 이력은 `harness/change_manifest.json`에 기록

## 3. 시나리오 서열
- PD/손실의 base ≤ adverse ≤ severe
  (`tools/scenario_order_check.check_scenario_order`)
- PD multiplier floor (`tools/scenario_order_check.check_pd_multiplier_floor`,
  정책 파일: `harness/scenario_floors.json`)

## 4. Forward-Looking 변수 (FLI)
- 변수 정의·예측 모형 검증 여부
- 다중공선성 (`tools/regression_diagnostics.calculate_vif`)
- 정상성 (`tools/regression_diagnostics.stationarity_summary`)

## 5. ECL 합계 정합성
- 스테이지별 합산 vs 총계 일치
- PD/LGD/EAD 입력값 vs ECL 산출의 정합성

## 6. 문서화
- 스테이지 정의·SICR 기준·시나리오 가중치 사유의 문서화
- 변경 이력의 매니페스트 기록

## 7. 금지
- 스테이지 분류 정책 자동 확정
- 시나리오 가중치 자동 변경
- IFRS 9 회계기준 유권해석
