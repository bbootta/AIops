# 저장소 전수 코드 리뷰 (2026-08-31, 45주차 연속)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `60bda57`
**직전 리뷰**: PR #80 (2026-08-30), 리뷰 파일 참조 `reports/code_review/2026-08-30_full_repo_review.md` (해당 브랜치 미머지)
**델타 창**: 2026-08-30 21:18 → 2026-08-31 (약 24 시간), **0 커밋**
**리뷰 방식**: 서브에이전트 2 개 병렬. (A) PR #80 BLOCKER 1~5 (게이트 무결성) 재점검, (B) PR #80 BLOCKER 6~12 (자본·유동성·CCR 공식) 재점검. 델타가 0 이므로 신규 리뷰는 스팟 체크로 축소.

## 0. 총평 (한 문장)

**24 시간 델타 0 커밋. PR #80 의 12 개 BLOCKER 전량 LIVE, 하나도 손대지 않았다.** PR #79 의 델타 P2 3 건도 그대로. em/en dash 는 다시 오름 (9,524 → 9,690, +166 회 · 625 → 635 파일, +10). 어제의 리뷰가 결재 라인에 닿지 않았다.

| 층위 | PR #79 (직전 델타) | PR #80 (어제) | 오늘 (2026-08-31) | 24h 변화 |
|---|---|---|---|---|
| tracked BLOCKER (PR #80 §1) | , | 12 신규 | **12 LIVE** | 0 해소 |
| tracked BLOCKER (PR #79 §2 delta P2) | 5 신규 | 5 LIVE | **5 LIVE (샘플 3/3 확인)** | 0 해소 |
| 델타 신규 P1 | 0 | , | 0 (0 커밋) | 0 |
| em/en dash (chars / files) | 9,524 / 625 | (측정없음) | **9,690 / 635** | +166 / +10 (**회귀**) |
| 벽시계 리크 (`date.today`/`datetime.now`) | 25+ | 25+ | **30 회 (risk_lib + tools)** | 실질 무변동 |

**최대 위험**: 리뷰 산출은 매일 나오는데 tracked BLOCKER 는 매일 그대로다. PR #80 이 지적한 3 선 게이트 우회 4 건 (`cli.py`, `consistency.py`, `independent_recalc.py`, `independent.py`) 은 결재 라인의 뿌리 통제인데 24 시간 안에 아무도 열지 않았다. 자본·유동성 공식 오류 6 건은 headline 수치를 직접 왜곡한다.

## 1. Tracked BLOCKER 재점검 결과

### 1-1. 3선 게이트 무결성 (PR #80 §1-1): **전건 LIVE (5/5)**

| # | 앵커 | 상태 | 증거 요지 |
|---|---|---|---|
| 1 | `risk_lib/cli.py:57-61, :97` | LIVE | `_cmd_run` / `_cmd_report_set` 모두 자체검증만 호출 (`result.validation.passes()`), `check_gate().require()` 미호출. 게이트 호출은 `_cmd_iv` (:290/:294) 에만 존재 |
| 2 | `risk_lib/validation/consistency.py:883-891` | LIVE | 두 분기 모두 `ConsistencyCheck("lcr_inflow_cap", "PASS", ...)`: FAIL/WARN 경로 자체 부재 |
| 3 | `risk_lib/validation/consistency.py:41-42` | LIVE | `return all(c.status != "FAIL" for c in self.checks)` → 빈 리스트 `True`. fail-closed 반전 |
| 4 | `validation-team-agent/tools/independent_recalc.py:140-153` | LIVE | `RECALCULATORS` = {lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate} 6 개. `RECALC_SCOPE` 21 개 대비 실제 헤드라인 교집합은 4 개 (17 개 metric 여전히 재계산 없음) |
| 5 | `risk_lib/validation/independent.py:206-213` | LIVE | `require_complete()` 가 `findings_accepted` 를 검사하지 않음. `findings_accepted=()` 또는 존재하지 않는 ID 로도 조건부 승인 통과 |

### 1-2. 자본 규정 공식 오류 (PR #80 §1-2): **전건 LIVE (3/3)**

| # | 앵커 | 상태 | 증거 요지 |
|---|---|---|---|
| 6 | `risk_lib/capital/bis_deep.py:117, 122, 791` | LIVE | 세 지점 모두 `0.0125` 상수. 필드명이 `irb_rwa_for_gp_cap` 임에도 SA rate (1.25 %) 적용, CRE40.45 IRB 0.6 % 위반 |
| 7 | `risk_lib/capital/rwa_sa.py:236-285` | LIVE | `standardised_rwa_total` 이 `sa_risk_weight_vector`(:190, past-due 150 % 처리 있음) 를 우회. RW 는 asset_class/rating/LTV 만으로 결정 |
| 8 | `risk_lib/capital/rwa_sa.py:236-285` | LIVE | :285 `return float((ead * rw).sum())`: `crm_factor` 부재. 같은 파일 `compute_rwa_sa` (:214-228) 은 `ead * rw * crm`. 비대칭 |

### 1-3. 유동성·CCR 공식 오류 (PR #80 §1-3): **전건 LIVE (4/4)**

| # | 앵커 | 상태 | 증거 요지 |
|---|---|---|---|
| 9 | `risk_lib/alm/balance_sheet.py:166-168` | LIVE | FI 대출 ≥1Y 를 `other_loans_ge1y` (RSF 0.85, `references.py:358`) 로 매핑. Basel NSF30.13 은 100 % 요구. `loans_fi_ge1y` 버킷 자체 부재 |
| 10 | `risk_lib/alm/lcr.py:344, 360-361` | LIVE | :343-344 `amount = float(r["notional"])`: 30 일 분할 없이 전액 계상. :360-361 자산 유입 전부 `wholesale_inflows` 단일 버킷으로 (retail/wholesale/FI 세분 상실) |
| 11 | `risk_lib/ccr.py:60-76` | LIVE | :75 `grouped["ead"] = 1.4 * (grouped["rc"] + grouped["pfe"])`. PFE multiplier `min(1, floor + (1-floor)·exp((V-C)/(2·(1-floor)·AddOn)))` (CRE52.35) 누락. 코드 docstring 조차 `α · (RC + PFE)` 로 서술 |
| 12 | `risk_lib/ccr.py:94-102` | LIVE | `return float(kappa * np.sqrt((ead["ead"] ** 2).sum()))`: 단일 κ × EAD L2-norm. BCBS d507 의 `√((ρ·Σ SCVA)² + (1-ρ²)·Σ SCVA²)`, sector RW, 유효만기 M, DF, 헤지항 전부 부재 |

### 1-4. PR #79 델타 P2 재확인: **샘플 3/3 LIVE**

| 앵커 | 상태 | 증거 요지 |
|---|---|---|
| `risk_lib/datamodel/materialize.py:407` | LIVE | :409 `assert trade.empty or trade["portfolio_id"].notna().all(), ...` bare assert. `python -O` 실행 시 FK 게이트 소멸 |
| `risk_lib/validation/consistency.py:490` | LIVE | :493-495 `market_positions is None or market_rwa is None` → WARN 반환. fail-closed 계약(§6) 위반 |
| `risk_lib/market_portfolio.py:190~206` | LIVE | `split_positions` 이 위험군 × 포트폴리오 로우를 만들 때 중복 제거·집계 없음. PK `(asof, portfolio_id, risk_class)` 로 쓰기에는 취약 |

PR #79 델타 P2 4 번 (`_by_period` 렉시코 정렬) 은 이번 라운드에서 미검, PR #79 §2 그대로 유지.

## 2. 신규 리뷰

**신규 델타 리뷰 없음.** `origin/main` HEAD 는 PR #80 base 와 동일한 `60bda57` 에 정지. 새 커밋이 없으므로 신규 결함이 발굴될 표면이 없다.

부수 스팟 체크:
- `risk_lib/**` bare assert 총 47 회 (§1-4 첫 앵커 포함). `python -O` 스트립 시 무력화되는 게이트가 더 있는지 45주차 다음 라운드에서 전수화 필요.
- em/en dash 파일 수가 PR #79 대비 +10. 사전 커밋 훅은 여전히 도입 없음 (43주차 §5-1 부터 지금까지 미실행).

## 3. 우선순위 (변화 없음)

- **D+1 (결재 상신 전, 어제와 동일)**: §1-1 게이트 무결성 5 건. 자체·독립 두 층 모두 통과 시늉만 있는 상태로 결재 라인이 fail-closed 아님.
- **W+1 (자본·유동성 산출 정정)**: §1-2, §1-3 총 7 건. 6 번 (Tier 2 GP cap) 과 11 번 (SA-CCR PFE multiplier) 은 headline 수치 (BIS 비율, CCR EAD) 를 직접 왜곡.
- **M+1**: PR #80 §M+1 그대로 (3 선 재계산 커버리지 21 완비, `risk_lib/` CI workflow 신설, 의존성 lock, 사전 커밋 훅 도입).

## 4. 게이트 상태 (CLAUDE.md §6)

```
자체검증 (2선)      해당 없음 (이번 라운드는 리뷰 산출, 리스크 headline 미갱신)
상시 독립검증 (3선) 해당 없음 (동일 사유)
```

이번 리뷰는 리스크 산출이 아니므로 3 선 요청을 생성하지 않는다. 다만 리뷰 결과가 지적하는 3 선 게이트 자체의 무결성 결함 4 건 (§1-1 #1, #3, #4, #5) 은 향후 어떤 리스크 산출이든 결재 라인의 유효성을 훼손한다.

## 5. 자동화 검증 상태

- `pytest tests/` : 이번 라운드에서 재실행하지 않음 (0 커밋 델타, 어제 PR #80 라운드에서 백그라운드 실행 진행 중이었으며 그 결과는 다음 회차 회수 대상).
- `.github/workflows/` : `validation-team-agent-ci.yml` 만 존재. `risk_lib/` 는 여전히 CI 게이트 부재 (PR #80 §M+1 유지).
