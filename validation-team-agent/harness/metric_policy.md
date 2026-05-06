# Metric Policy

검증 지표의 산식·해석 기준·임계값 가이드. 임계값은 **참고용**이며, 모형별 정책에
의해 조정된다.

---

## 1. 변별력 (Discriminatory Power)

| 지표 | 산식 | 참고 임계 |
|---|---|---|
| KS | `max|F_bad(s) - F_good(s)|` | 신용평가모형 ≥ 0.30 |
| AUROC | ROC 아래 면적 | ≥ 0.70 |
| Gini / AR | `2*AUROC - 1` | ≥ 0.40 |

**주의**:
- 표본 수 < 1,000 또는 부도 수 < 50일 경우 신뢰구간을 함께 보고한다.
- 등급체계 모형은 등급별 부도율의 단조성도 함께 점검.

구현: `tools/metric_ks_auc.py`

---

## 2. 안정성 (Stability)

| 지표 | 산식 | 참고 임계 |
|---|---|---|
| PSI | `Σ (a_i - e_i) * ln(a_i / e_i)` | < 0.10 안정 / 0.10~0.25 주의 / ≥ 0.25 불안정 |

**주의**:
- 0 division 방지를 위해 모든 bin에 epsilon 적용.
- bucket 비교 시 expected와 actual의 bin 정의가 동일해야 한다.

구현: `tools/metric_psi.py`

---

## 3. 캘리브레이션 (Calibration)

| 지표 | 산식 | 참고 임계 |
|---|---|---|
| CDR | `default_count / exposure_count` | 등급별 PD 대비 비교 |
| SDR | `(exposure - default) / exposure` | CDR + SDR = 1 |

**비교 원칙**:
- CDR은 portfolio level과 등급 level을 모두 본다.
- 추정 PD와 CDR의 차이가 통계적으로 유의한지 평가한다 (binomial test).
- 표본 부족 시 신뢰구간이 매우 넓다는 점을 보고서에 명시한다.

구현: `tools/metric_cdr_sdr.py`

---

## 4. 회귀/시계열 모형 진단

| 지표 | 점검 |
|---|---|
| VIF | 변수별 VIF > 10 시 다중공선성 의심 |
| 잔차 | 자기상관 / 이분산 / 정규성 |
| 정상성 | 단위근 검정 (ADF) |

구현: `tools/regression_diagnostics.py`

---

## 5. 시나리오/스트레스

- 시나리오 서열: `base ≤ adverse ≤ severe` (PD, 손실률 등)
- PD multiplier floor: scenario별 최소 배수 정책 충족 여부
- 시나리오 가중치 합 = 1 (IFRS 9 ECL)

구현: `tools/scenario_order_check.py`

---

## 6. 임계값 변경 정책

임계값은 **고정**이다. 본 하니스는 임계값을 임의로 완화하지 않는다.
완화가 필요한 경우, 사용자에게 사유와 근거를 요청하고
`harness/change_manifest.json`에 기록한다.
