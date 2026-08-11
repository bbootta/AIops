# Policy — Market Risk (FRTB)

Basel MAR10–MAR33 기준. 본 정책은 검증팀 점검용이며 산정 자체는 트레이딩북
시스템이 수행한다. 임계 SSoT: `harness/market_risk_thresholds.json`.

## 1. 검증 범위
- 표준방법 (SBA): Sensitivity 합산 / Risk Charge / Curvature
- 내부모형 (IMA): Expected Shortfall 97.5% / Non-Modellable Risk Factor / Default Risk Charge
- 백테스트: 1일 99% VaR exceptions 250 영업일
- Stress VaR / P&L attribution

## 2. 점검 항목 (자동 / 수동)
| 항목 | 도구 |
|---|---|
| Backtest traffic light | `tools.risk_checks.market.var_backtest_traffic_light` |
| ES horizon / liquidity adjustment | 수기 검토 |
| NMRF 분류 일관성 | 수기 검토 |
| DRC (default risk charge) 가산 | 수기 검토 + 신용 SA 정책 일관 |

## 3. 참고 임계
- VaR backtest: green 0–4 / yellow 5–9 / red ≥ 10 exceptions (BCBS 표준)
- VaR multiplier ≥ 3.0 (yellow 구간 시 +0.4 ~ +1.0)

## 4. 금지
- Backtest yellow/red 구간에서 multiplier 임의 완화
- ES horizon 의 임의 단축
- NMRF 분류 자의적 적용
