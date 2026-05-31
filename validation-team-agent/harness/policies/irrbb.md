# Policy — IRRBB (Interest Rate Risk in the Banking Book)

Basel SRP31 (BCBS d368). 임계 SSoT: `harness/irrbb_thresholds.json`.

## 1. 핵심 지표
- **ΔEVE** (Economic Value of Equity): 6개 표준 시나리오 중 최대 손실
- **ΔNII** (Net Interest Income): 12개월 NII 변동

## 2. Outlier Test
- max(ΔEVE) / Tier1 자본 > **15%** 이면 outlier bank (감독 강화 대상).
- BCBS 표준 6 시나리오: parallel up/down, steepener, flattener, short rate up/down.

## 3. 검증 항목
| 항목 | 도구 |
|---|---|
| Outlier 15% Tier1 점검 | `tools.risk_checks.irrbb.check_eve_outlier` |
| 6 시나리오 모두 산출 | `tools.risk_checks.irrbb.check_scenarios_present` |
| ΔNII 경고선 (NII 의 20%) | `tools.risk_checks.irrbb.check_nii_warning` |
| Non-maturity deposit 행동 모형 가정 | 수기 검토 (행동만기, 베타) |
| 옵션성 / prepayment 가정 | 수기 검토 |

## 4. 금지
- Outlier test 의 5/6 시나리오만 산출
- Non-maturity deposit 의 행동만기를 시장 표준 대비 과도하게 연장
- 자체 시나리오로 표준 시나리오 갈음
