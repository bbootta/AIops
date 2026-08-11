# Policy — Credit Concentration (LEX + 은행법 제35조)

Basel LEX10/20/30 + 은행법 제35조 / 은행업감독규정. 임계 SSoT:
`harness/concentration_thresholds.json`.

## 1. 한도 체계

| 규칙 | 분모 | 임계 | 근거 |
|---|---|---|---|
| 거액익스포저 보고 | Tier 1 | > 10% | LEX10 |
| 단일 거래상대방 한도 | Tier 1 | ≤ 25% | LEX20 |
| G-SIB 간 한도 | Tier 1 | ≤ 15% | LEX20 |
| 동일차주 신용공여 | 자기자본 | ≤ 25% | 은행법 35조 ① |
| 동일한 개인·법인 | 자기자본 | ≤ 20% | 은행법 35조 ③ |
| 거액신용공여 합계 | 자기자본 | ≤ 5배 | 은행법 35조 ④ |

## 2. 집중도 (HHI)

포트폴리오 HHI = Σ (익스포저 점유율)². 밴드는 임계 SSoT 의 `hhi_bands`:
low ≤ 0.10 < moderate ≤ 0.18 < high.

HHI 밴드는 **참고 지표**이며 한도 위반과 달리 단독으로 fail 을 만들지
않는다 (high 밴드 → warning).

## 3. 검증 항목

| 항목 | 도구 |
|---|---|
| 동일차주(group_id) 합산 정합 | `tools.risk_checks.concentration._group_totals` |
| 한도 위반 식별 | `tools.risk_checks.concentration.check_concentration` |
| HHI 산출 | `tools.risk_checks.concentration.herfindahl` |
| 거액 합계 총량 | `check_concentration` (aggregate) |
| 익스포저 측정 자체의 정합 | 여신 시스템 책임 — 본 하니스 범위 외 |

## 4. 워크플로우 연결

- step `3.conc` — 게이트: `concentration_exposures` 제공 시 활성.
- 한도 위반 (fail) 시 `9.escalate` 동적 활성 → MRMC 보고 권고.
- 입력: `concentration_exposures` (list), `concentration_tier1`,
  `concentration_equity` (선택, 미제공 시 tier1 사용 — 보수적).

## 5. 한계

- 익스포저 인정 기준 (CRM 차감, 신용환산율) 은 측정 시스템 책임.
- 계열 분류 (동일차주 그룹핑) 정확성은 입력 데이터 품질에 의존.
- 한도 위반 판정은 점검 보조이며 법규 유권해석이 아니다 (CLAUDE.md §2).
