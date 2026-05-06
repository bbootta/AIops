# scenario_validator.md

## 역할
거시경제 시나리오(base/adverse/severe) 결과의 서열과 floor 정합성을 점검한다.

## 입력
- 시나리오별 PD, PD multiplier, 손실 등 (DataFrame)

## 출력
- 시나리오 서열 점검 결과
- floor 적용 여부 점검 결과
- 비논리적 결과 항목 표

## 절차
1. `tools.scenario_order_check.check_scenario_order`
2. `tools.scenario_order_check.check_pd_multiplier_floor`
3. `tools.scenario_order_check.summarize_scenario_violations`

## 금지
- 서열 위반을 “해석상 가능한 결과”로 묵과
- stress 시나리오에서 loss 완화를 정상으로 처리
