# Policy — 자본적정성 (Capital Adequacy)

근거: 은행업감독업무시행세칙 (자본적정성 편) + Basel III/IV.
임계 SSoT: `harness/capital_adequacy_thresholds.json`.

## 1. 최소 자본비율 (Basel III + 국내 채택)

| 항목 | 최소 |
|---|---|
| 보통주자본비율 (CET1) | 4.5% |
| 기본자본비율 (Tier 1) | 6.0% |
| 총자기자본비율 (BIS) | 8.0% |
| 레버리지비율 | 3.0% |

## 2. 추가 자본 버퍼 (감독원 적용)

| 버퍼 | 임계 |
|---|---|
| 자본보전버퍼 (conservation) | +2.5% (CET1) |
| 경기대응완충자본 | 0% ~ +2.5% (한은+감독원 공동 결정) |
| D-SIB 부과 | +1.0% (시중 5대 은행 등) |
| (G-SIB) | 한국 G-SIB 미지정 — 글로벌 모니터링용 |

D-SIB 명단·부과율은 감독원 별도 고시. `capital_adequacy_thresholds.json` 의
`dsib_surcharge_typical` 은 참고값이며 실제 적용률은 은행별로 다르다.

## 3. 검증 항목

| 항목 | 도구 |
|---|---|
| CET1/T1/BIS 최소 충족 | `tools.risk_checks.capital.check_ratios` |
| 보전버퍼 미충족 시 배당 제한 | 수기 검토 (이사회 의결문) |
| 레버리지비율 ≥ 3% | `tools.risk_checks.capital.check_leverage` |
| RWA 산출 접근법(SA/FIRB/AIRB) 일관성 | 수기 검토 + 매니페스트 |

## 4. 감독시행세칙 참조 조항

- 자본의 정의 및 차감 항목: 시행세칙 별표 / 별표서식
- 분기 보고 의무: 시행세칙 정기 보고서 제출
- 위반 시 적기시정조치(PCA): 은행법 + 감독규정

## 5. 금지

- 자본 미충족 상태에서 배당·성과급 결의의 자동 승인
- D-SIB 부과율의 임의 적용 (감독원 고시값만 사용)
- 자본비율 산출에서 차감 항목(영업권 등)의 임의 제외
