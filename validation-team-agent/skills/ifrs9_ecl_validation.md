# Skill — IFRS 9 ECL Validation

## 목적
IFRS 9 ECL 산출 과정의 일관성·정합성·문서화 적정성을 점검한다.

## 입력
- 스테이지 분류 기준 (정량/정성, SICR 기준)
- 시나리오 가중치 (base / adverse / severe)
- forward-looking 변수 (FLI) 정의 및 사용 방식
- PD/LGD/EAD 산출 결과

## 절차
1. 스테이지 분류 일관성
   - 동일 차주에 대해 시점 흐름이 합리적인가 (1→2→3, 2→1 회복 사유 명시 등)
   - SICR 트리거의 정의·일관 적용 여부
2. 시나리오 가중치
   - `sum(weights) == 1.0` (`tools/scenario_order_check`로 보조 점검)
   - 가중치 변동의 사유 문서화 여부
3. 시나리오 서열
   - PD/손실 추정의 base ≤ adverse ≤ severe (`tools/scenario_order_check.check_scenario_order`)
4. FLI 변수
   - 변수 정의·예측 모형의 검증 여부
   - 다중공선성 (`tools/regression_diagnostics.calculate_vif`)
5. ECL 합계 정합성
   - 스테이지별 합산 vs 총계 일치
6. 문서화
   - 스테이지 정의·SICR 기준·시나리오 가중치 사유의 문서화 여부

## 산출물
- 스테이지 분류 일관성 점검표
- 시나리오 가중치/서열 점검표
- FLI 변수 점검표
- ECL 합계 정합성 점검표
- 한계와 추가 확인사항

## 금지
- 스테이지 정책의 자동 확정
- 시나리오 가중치 변경의 자동 확정
- IFRS 9 해석 관련 법·회계 기준 유권해석

## 완료 기준
- 위 5개 영역 모두에 대해 결과가 보고되었는가
- 미문서화 항목이 명시되었는가
