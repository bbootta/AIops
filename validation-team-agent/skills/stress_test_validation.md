# Skill — Stress Test Validation

## 목적
스트레스 테스트의 시나리오 정합성·서열 조건·이탈 케이스·결과 해석을 점검한다.

## 입력
- 시나리오 (base / adverse / severe)별 거시 가정
- 시나리오별 PD/LGD/EAD/ECL 결과
- 시나리오 가중치 (적용되는 경우)
- 정책 floor (PD multiplier 등)

## 절차
1. 시나리오 정의 점검
   - base / adverse / severe 정의의 명확성
   - 거시 변수 가정의 합리성
2. 결과 서열 조건
   - PD: `tools/scenario_order_check.check_scenario_order(base_pd, adverse_pd, severe_pd)`
   - 손실: 동일 점검
3. PD multiplier floor
   - `tools/scenario_order_check.check_pd_multiplier_floor`
4. 이탈 케이스 점검
   - 일부 segment에서 서열 위반 / floor 미달 시 사유 분석
5. 자본 / 수익 영향 점검 (수치만 산출, 정책 판단은 인간 검증자)

## 산출물
- 시나리오 정의 점검표
- 서열 / floor 점검표
- 이탈 케이스 목록과 잠정 원인
- 한계와 추가 확인사항

## 금지
- 시나리오 변경의 자동 확정
- 자본 영향 결과의 외부 보고용 확정

## 완료 기준
- 시나리오 정의·서열·floor·이탈이 모두 보고되었는가
