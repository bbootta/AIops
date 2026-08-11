# Policy — Credit Valuation Adjustment (CVA)

Basel MAR50. 임계 SSoT: `harness/cva_thresholds.json`.

## 1. 두 가지 접근
- **BA-CVA** (Basic Approach): 단순 BCBS 식. ρ=0.5, α=1.4.
- **SA-CVA** (Standardised Approach): counterparty / risk factor 별 RW. SA-CCR 결과를 입력으로 사용.

대규모 트레이딩북 (감독원 기준 EUR 100bn 이상) 은 SA-CVA 의무.

## 2. 검증 항목
| 항목 | 도구 |
|---|---|
| BA-CVA 산식 정합성 | `tools.risk_checks.cva.compute_ba_cva` |
| ρ / α 정책 일관 | 임계 SSoT 사용 (변경 시 매니페스트) |
| Hedge eligibility (single-name CDS, index CDS) | 수기 검토 |
| SA-CVA 의무 여부 | 트레이딩북 EUR 규모 점검 |

## 3. 금지
- ρ 또는 α 의 임의 완화
- 부적격 hedge 의 BA-CVA 차감
- SA-CCR EAD 와 일관되지 않은 입력 사용
