# [2026-07-09] 전체 저장소 코드 리뷰 — 13주차

_리뷰 세션: 3개 병렬 Explore 에이전트 (신규 커밋 3개 PR 커버) · 메인 재검증_

## 요약

지난 라운드 (PR #25, 2026-07-07) 이후 **3개 PR 에 4개 신규 커밋** 발생:
- **PR #4** (validation-team-agent): `9d51bd3` — 검증의견서 초안 페이지 + 테스트 (+281 LOC)
- **PR #5** (risk-management-agent-harness): `bbd71db` — `html_report.py` 에서 chrome + core page builders 추출 (+2284/-2233), `135d144` — lookalike modules cross-reference 문서 (+18/-2)
- **PR #10** (minecraft): `e09336f` — inventory 화면에서 hotbar 커스터마이즈 (+59/-10)

세 커밋 모두 (a) refactor 또는 (b) additive 성격. **신규 P0/P1 0건**. 신규 P2 × 1 · P3 × 1 (PR #10 hotbar 미비). tracked findings 17건 (지난 15 + PR #5 refactor 로 경로 변경된 rwa_sa 확인 + PR #4 line-shift 확인 포함) 모두 **여전 LIVE** — 코드 이동은 있었지만 결함은 그대로.

## 이번 라운드 결과

### 신규 P0 0건

세 신규 커밋 모두 순수 추가 또는 순수 refactor. 규제 임계값, path/label 취급, 예외 처리, timezone 등 P0 후보 영역에서 신규 위험 없음.

### 신규 P1 0건

PR #4 새 페이지 (`_opinion_draft_page`) 는 3중 disclaimer + 빈 승인 란으로 서명 위조 소지 없음. PR #5 refactor 는 19개 페이지 빌더를 semantics-preserving 이동 (diff = 0). PR #10 hotbar 커스터마이즈 UI 는 `PLACEABLE.has(t)` 재검증 + 저장 시 `Array.isArray + every` 방어.

### 신규 P2 1건 · P3 1건 (모두 PR #10)

| PR | 위치 | 요지 |
|---|---|---|
| #10 | `minecraft/index.html:2604` (P2) | Load-time inv 복원의 `for (const k in inv)` 가 초기 `inv` (라인 2226-2232) 키만 순회. 신규 hotbar 커스터마이즈로 이제 접근 가능한 `NETHERRACK` 을 hotbar 배치 → 저장 → 재로드 시 hotbar slot 은 NETHERRACK 표시되나 `inv[NETHERRACK]` 은 0. "배치는 저장됩니다" 약속 미이행. 커밋이 만든 게 아닌 기존 버그를 이 커밋이 **도달 가능하게** 만듦. |
| #10 | `minecraft/index.html:343` (P3) | `BLOCK.SNOW` 는 자기가 아닌 `BLOCK.DIRT` 를 drop. 따라서 `inv[SNOW]` 는 절대 > 0 이 되지 않으며, 이 커밋이 `INV_ORDER`/`PLACEABLE` 에 추가한 SNOW 엔트리 (라인 2400, 330) 는 도달 불가능. Dead code · misleading UX. |

### tracked findings 재검증 (지난 15건 + line-shift 확인 2건 = 17건)

**전체 LIVE. 세 신규 커밋 어느 하나도 tracked P0/P1 를 fix 하지 않음.**

#### PR #4 tracked LIVE (line-shift 반영)

| Finding | 이전 위치 | 이번 확인 | 상태 |
|---|---|---|---|
| pack_archive path traversal (`--archive-label`) | `pack_archive.py:99,107` | 동일 | **LIVE** (P0) |
| Basel III Total-cap 임계값 `+ 0.03` (should be `+ 0.035`) | `report_pack.py:3576` | `report_pack.py:3718` (+142 shift) | **LIVE** (P1) |
| deep-page 가 SSoT `capital_adequacy_thresholds.json` 우회 | `report_pack.py:3550-3554` | `report_pack.py:3692` (+142 shift) | **LIVE** (P1) |
| 3× bare `except Exception:` 로 근본원인 은닉 | `report_pack.py:2999/3243/3439` | `report_pack.py:3141/3385/3581` (+142 shift) | **LIVE** (P2) |
| permission_guard 가 `cmd` 전체를 findings 에 append | `permission_guard.py:118` | 동일 | **LIVE** (P1, tracked) |
| scenario_weights dict(zip(...)) 중복 시 silent dedup | `scenario_weights.py:84` | 동일 | **LIVE** (P1, tracked) |

#### PR #5 tracked LIVE (일부 경로 변경)

| Finding | 이전 위치 | 이번 확인 | 상태 |
|---|---|---|---|
| SRISK 공식 `(1-k)*(debt+equity)` 누락 | `risk_lib/systemic.py:61` | 동일 | **LIVE** (P0) |
| SA B-bucket RW=1.00 (Basel CRE20 = 1.50) — Sovereign·Bank·Corporate 3자산군 | `risk_lib/rwa_sa.py:20-27, 29-36, 43` | **`risk_lib/capital/rwa_sa.py:24, 34, 44`** (경로 이동, 값 미변경) | **LIVE** (P0) |
| CoVaR own-loss (mask 가 자기 손실 → system_loss 로 조건화) | `risk_lib/systemic.py:113,121-122` | `risk_lib/systemic.py:120-122` | **LIVE** (P0) |
| FRTB backtest multiplier 절반 (green=1.50, yellow≈1.7-1.92 vs MAR99 3.0-3.85) | `risk_lib/frtb.py:154-163` | `risk_lib/frtb.py:161-166` | **LIVE** (P0) |
| pillar3 deprecated 문서 vs 실사용 불일치 | `ops_pages/governance.py:526`, `tests/test_cro_layers.py:261,268` | 동일 (refactor 가 governance.py 미터치) | **LIVE** (P1) |

_※ SA B-bucket 경로 이동은 이번 refactor 이전에 있었음 (2026-06 이전). Diff 스팟 확인 결과 이번 refactor 는 rwa_sa.py 를 touch 하지 않음._

#### PR #10 tracked LIVE (전체 line-shift 반영)

| Finding | 이전 위치 | 이번 확인 | 상태 |
|---|---|---|---|
| applyPos NaN pass-through (p.x/y/z guard 없음) | `index.html:2520-2527` | `index.html:2564-2571` (+44 shift) | **LIVE** (P1) |
| destroyBlocks CHEST inventory drop 부재 | `index.html:774-788` | `index.html:783-797` (+9, 영역 미터치) | **LIVE** (P1) |
| health NaN pass-through (`typeof NaN === 'number'`) | `index.html:2580` | `index.html:2624` (+44 shift) | **LIVE** (P1) |
| Nether respawn (curDim 미리셋) | `index.html:1475-1478` | `index.html:1484-1498` | **LIVE** (P1) |
| saveGame sync stall | `index.html:2666-2668` | `index.html:588-603` (호출부 1845/1937/2660/2716) | **LIVE** (P1) — payload 에 hotbar 필드 추가로 오히려 미세하게 증가 |

#### 무커밋 PR: 이전 findings mechanically LIVE

- **PR #2** (`f8867b8`, 12주 무커밋): P0 × 2 + 다수 LIVE
- **PR #3** (`5a2200e`, 12주 무커밋): P0 × 0, P1 × 3 + P2 × 7 LIVE
- **PR #6** (`98cb1a4`, 12주 무커밋): P1 × 1 + P2 × 2 LIVE
- **PR #7 / #8** (`a60443b`, `574f8a1`, 12주 무커밋): P1 × 2 + P2 × 2 LIVE
- **PR #9** (`133985a`, 12주 무커밋): P0 × 1 + P1 × 3 + P2 × 7 LIVE
- **PR #22** (`907839e`, 5일 무커밋): P0 × 3 + P1 × 3+5 LIVE

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 findings | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#4** | 1 (additive) | — | **P0 × 1 + P1 × 2 + P2 × 5** LIVE (+ 지난 tracked P1×2 LIVE) | **block-merge** |
| **#5** | 2 (refactor + docs) | — | **P0 × 4 + P1 × 1** LIVE (rwa_sa 경로만 이동) | **block-merge** |
| **#10** | 1 (feature) | P2 × 1 + P3 × 1 | **P1 × 5** LIVE | changes requested |
| #9 | 0 | — | P0 × 1 + P1 × 3 + P2 × 7 LIVE | **block-merge** |
| #22 | 0 | — | P0 × 3 + P1 × 8 LIVE | **block-merge** |
| #2 | 0 | — | P0 × 2 LIVE | **block-merge** (12주 무커밋) |
| #3 | 0 | — | P1 × 3 + P2 × 7 LIVE | changes requested |
| #6 | 0 | — | P1 × 1 + P2 × 2 LIVE | changes requested |
| #7 / #8 | 0 | — | P1 × 2 + P2 × 2 LIVE | #7 close 권고 / #8 delta 검토 후 merge 가능 |

## 누적 13회 리뷰 결산

|  | #16 | #17 | #18 | #19 | #20 | #21 | #23 | #24 | #25 | **이번 (#26 예정)** |
|---|---|---|---|---|---|---|---|---|---|---|
| 신규 P0 | 7 | 10 | 3 | 4 | 0 | 1 | 3 | 0 | 2 | **0** |
| 신규 P1 | 18 | 24 | 9 | 13 | 0 | 8 | 3 | 5 | 10 | **0** |
| 신규 P2 | ≥15 | ≥18 | ≥10 | ≥12 | 0 | ≥8 | ≥5 | ≥8 | 25 | **1** |
| 누적 수정 | 0/22 | 0/32 | 0/44 | 0/57 | 0/57 | 7/57 | 7/60 | 7/65 | 7/77 | **7/79** |

**해석**: 세 신규 커밋 모두 tracked P0/P1 를 fix 하지 않았고, 신규 회귀 P0/P1 도 없음. 즉 이번 주는 "tracked 문제는 그대로, 새 회귀는 없음" — 정보량이 낮은 라운드. PR #5 refactor 는 semantics-preserving 확인됨 (품질 upgrade, 정확성 unchanged).

## 다음 라운드 권고

이번 주 신규 findings 가 사실상 P2×1·P3×1 뿐이므로, 권고는 지난 주와 거의 동일:

1. **PR #4 (P0 · 보안, 12주째 open)**: `pack_archive.add()` 에 `label = Path(label).name` 강제. 신규 커밋이 파일을 touch 했음에도 이 fix 는 안 됨.
2. **PR #4 (P1 · Basel III)**: `report_pack.py:3692 & 3718` 을 `harness/capital_adequacy_thresholds.json` 로드 방식으로 리라이트. 최소한 `+ 0.03` → `+ 0.035`.
3. **PR #5 (P0 × 4)**: SRISK 공식 수정, SA B-bucket RW 1.00 → 1.50 (`capital/rwa_sa.py`), CoVaR mask 를 `system_loss` 로 조건화, FRTB multiplier BCBS MAR99 값으로 복원. Refactor 여력이 있었으니 numeric fix 도 가능했을 것.
4. **PR #5 (P1 · pillar3)**: refactor 가 `ops_pages/*` 를 대거 재구조화했음에도 `governance.py:526` 의 deprecated import 는 그대로. 다음 refactor 라운드에 포함시킬 것.
5. **PR #10 (신규 P2)**: `for (const k in inv)` load-time 복원을 `for (const k of INV_ORDER)` 로 변경 or 초기 `inv` 에 NETHERRACK/SNOW 명시. 그리고 SNOW 는 자기 자신을 drop 하도록 하거나 `INV_ORDER` 에서 제거.
6. **PR #10 (tracked P1 × 5)**: 이번 커밋이 index.html 을 touch 했음에도 5개 tracked P1 어느 하나도 fix 안 됨 — 6주 연속 방치. Fix-PR 을 직접 제출하는 옵션 재검토.
7. **PR #9 (P0 sample report)**: 배포된 sample report 의 locator TBD 이슈 유지. 하네스 신뢰성 최우선.
8. **PR #22**: `code-review/` 슬러그 삭제 + `skills-lock.json` sourceCommit 추가 + `/implement` chain 삭제.

## 리뷰 방식

3개 병렬 Explore 에이전트:
- (A) PR #4 신규 커밋 `9d51bd3` (검증의견서 초안) fresh-eyes P0/P1 hunt + `report_pack.py:3692/3718` shift 확인 · 50k tokens · 28 tool_uses
- (B) PR #5 신규 커밋 `bbd71db` (refactor) + `135d144` (docs) semantics-preserving 검증 + 4 P0 spot-check + pillar3 P1 확인 · 65k tokens · 52 tool_uses
- (C) PR #10 신규 커밋 `e09336f` (hotbar 커스터마이즈) fresh-eyes P0/P1 + 5 tracked P1 line-shift · 47k tokens · 22 tool_uses

메인 세션: PR head SHA 대조표 (지난 리뷰 대비 3개 branch 만 이동, 나머지 21개 branch 무커밋) 확인 후 스코프 결정.

**커버리지**: 이번 라운드는 새 커밋 diff (총 ~5.2k LOC diff) 중심. 무커밋 PR 은 재-fresh-eyes 없이 head SHA 무변경 근거로 mechanically LIVE 처리.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
