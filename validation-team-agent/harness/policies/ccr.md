# Policy — Counterparty Credit Risk (SA-CCR)

Basel CRE52. 임계 SSoT: `harness/ccr_thresholds.json`.

## 1. SA-CCR 산식
```
EAD = α × (RC + PFE)
α   = 1.4 (감독원 승인 IMM 사용 시 조정 가능)
RC  = max(V - C, 0)            # netting set replacement cost
PFE = multiplier × Σ AddOn      # potential future exposure
```

## 2. 검증 항목
| 항목 | 도구 |
|---|---|
| α = 1.4 정책 일관 | 임계 SSoT 강제 |
| Supervisory factor by asset class | `tools.risk_checks.ccr.lookup_supervisory_factor` |
| EAD 산식 (RC + α·PFE) 정합 | `tools.risk_checks.ccr.compute_ead` |
| PFE multiplier 0.05 ~ 1.0 | 임계 SSoT |
| Netting set 정의 일관 | 수기 검토 |
| Margined / unmargined 구분 | 수기 검토 (MPOR 적용) |

## 3. Asset Class 별 Supervisory Factor (요약)
임계 SSoT 의 `supervisory_factors` 사용. 변경은 매니페스트 동반.

## 4. 금지
- α 의 임의 완화 (IMM 미승인 상태에서 1.4 미만 사용 금지)
- Netting set 의 임의 통합 (담보 미보유)
- Margined trade 의 MPOR 임의 단축
