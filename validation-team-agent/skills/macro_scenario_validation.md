# Skill — Macro Scenario / Forward-Looking Model Validation

## 목적
거시경제 시나리오 기반 예측모형의 변수 선택·통계적 가정·예측 적정성을 점검한다.

## 입력
- 거시 변수 시계열 (GDP 성장률, 실업률, 금리, 환율, 부동산가격 등)
- 모형 명세 (선형/비선형, 시차, 변환)
- 추정 결과 (계수, 표준오차, R², 잔차)
- 시나리오 정의 (base / adverse / severe)

## 절차
1. 시계열 점검
   - 단위근 검정 (ADF) 등 정상성
   - 결측·이상치
2. 변수 점검
   - 다중공선성 (`tools/regression_diagnostics.calculate_vif`)
   - 변환·시차 변수의 사용 사유 문서화
3. 모형 진단
   - 잔차의 자기상관·이분산·정규성 (`tools/regression_diagnostics.check_residual_basic`)
4. 시나리오 정합성
   - base ≤ adverse ≤ severe (`tools/scenario_order_check.check_scenario_order`)
   - 시나리오 변수의 동시 변동 합리성 (예: 실업률 상승 vs 금리 하락 정합)
5. 표본 외 검증
   - hold-out / 시계열 cross-validation 결과

## 산출물
- 시계열 점검표
- 변수 점검표
- 모형 진단표
- 시나리오 정합성 점검표
- 한계 (ex. 표본 기간이 한 사이클 미만)와 추가 확인사항

## 금지
- 시나리오 정의의 임의 변경
- 거시 변수 정상성 가정의 임의 완화

## 완료 기준
- 모든 절차의 결과가 보고되었는가
- 모형 한계와 표본 외 일반화 가능성이 명시되었는가
