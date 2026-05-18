# Policy — Operational Risk (SMA)

Basel OPE25 SMA. ORC = BIC × ILM. 임계 SSoT: `harness/operational_risk_thresholds.json`.

## 1. 구성 요소
- **BI (Business Indicator)**: ILDC + Services + Financial 의 3-yr 평균 (EUR 기준)
- **BIC (BI Component)**: BI 구간(1/2/3)별 marginal coefficient 누진 합산
- **ILM (Internal Loss Multiplier)**: 손실이력 기반 multiplier (BCBS 권고는 ILM=1 단순 사용)

## 2. 검증 항목
| 항목 | 점검 방법 |
|---|---|
| BI 구성 요소 (ILDC, Services, Financial) | 회계 시스템 매핑 확인 |
| BI 3-yr 평균 산식 | 도구 `tools.risk_checks.operational.business_indicator_average` |
| BIC bucket marginal 누진 합산 | 도구 `tools.risk_checks.operational.compute_bic` |
| ILM 손실이력 최소 10년 | 수기 검토 |

## 3. 금지
- BI 구성 요소의 임의 제외
- 손실 이력의 임의 절단
- ILM 정책의 임의 변경 (감독원 사전 협의 필수)

## 4. 국내 적용 (감독시행세칙)
- 감독원은 ILM = 1 (loss component 미반영) default 적용. ORC = BIC.
- 손실 이력은 보고용으로만 사용 (감독원 정기 보고서).
- `domestic_default_ilm` 임계는 `harness/operational_risk_thresholds.json` 에서 관리.
- 도구: `tools.risk_checks.operational.compute_orc_domestic`.
