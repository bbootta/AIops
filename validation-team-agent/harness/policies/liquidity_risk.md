# Policy — Liquidity Risk (LCR / NSFR)

Basel LIQ40 LCR + LIQ20 NSFR. 임계 SSoT: `harness/liquidity_risk_thresholds.json`.

## 1. 핵심 비율
- **LCR** = HQLA / Net Cash Outflow (30일) ≥ 100%
- **NSFR** = Available Stable Funding / Required Stable Funding ≥ 100%

## 2. 검증 항목
| 항목 | 점검 |
|---|---|
| LCR 최소 100% | `tools.risk_checks.liquidity.check_lcr` |
| NSFR 최소 100% | `tools.risk_checks.liquidity.check_nsfr` |
| HQLA Level 1/2A/2B 분류 | 수기 검토 (cap 40%/15%) |
| 통화별 LCR | 통화 매트릭스 보고 |
| 시나리오 분해 (retail, wholesale, secured funding) | 수기 검토 |

## 3. 경고선
- LCR < 110% 또는 NSFR < 105% 는 RAS 경고. 임계 SSoT 의 warning 필드 사용.

## 4. 금지
- HQLA 구성에 LCR cap 위반 항목 포함
- 비유동성 자산을 stable funding 으로 분류
- 일중 유동성(intraday) 관리는 본 정책 범위 밖 — 별도 정책 적용
