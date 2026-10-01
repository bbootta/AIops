# 전체 저장소 코드 리뷰 — 2026-07-13 (17주차)

## 요약

지난 라운드 (PR #29, 2026-07-12 21:12 UTC) 이후 ~18h. **감시 대상 10개 PR 중 3개 PR (#10, #5, #4) 에 신규 커밋 유입, 신규 PR #30 (ISO 42001 compliance) 1건 등장**, 나머지 6개 PR head SHA 무변경.

- **PR #30 신규** — `38376da7` — ISO/IEC 42001 필수 요건 문서·템플릿·CLAUDE.md §0 도입 (docs-only, 149 lines).
- **PR #10 커밋 1건** (2026-07-13 14:48 UTC, `e41c634`) — 토스트 알림 시스템 + 업적 10종 + 피격 스파크 (72 lines).
- **PR #5 커밋 5건** (2026-07-12 23:38 UTC ~ 2026-07-13 15:00 UTC) — audit ledger 14→23 확장, 2차 내부심사 및 §6-4 시정조치, CRO 브리핑 자동 서사 6단, CET1 buffer-ladder 차트, registry 파생 full page catalog. **코드 변경 있음 (risk_lib/html_exec.py +161, risk_lib/audit_trail.py +85), 그러나 여전히 tracked P0×4 는 미수정 (거버넌스/UX 개선 위주)**.
- **PR #4 커밋 2건** (2026-07-12 23:36 UTC, `5bd453b` + 2026-07-13 14:52 UTC, `7c0d1c1c`) — 운영 데이터 어댑터 (CSV/Parquet + PII 차단 boundary 3중) + report_pack `--input-csv` 원스톱 CLI. 신규 파일 `tools/data_adapter.py` (248 lines) · 새 테스트 25건 (1046→1056 pass).
- **신규 P0** — 0건.
- **신규 P1** — 2건 (PR #4 pseudonymize salt 예측 가능성, PR #10 데이터 손실 지속).
- **신규 P2** — 6건, P3 — 4건.
- **Tracked 27건 재검증** — FIXED × 1 유지 (`permission_guard.py`) + PARTIAL × 3 유지 + LIVE × 23 (지난주 MOVED×2 는 실제로는 LIVE 로 재분류 — 새 layout 에 SSoT 구현하되 old path 잔존).

## 이번 라운드 신규 findings

### 신규 P0 · 0건

PR #30 도입한 §0 mandatory ISO 42001 gate 가 잠재적 P0 후보 (기존 10개 open PR 을 소급 차단할 수 있음). 그러나 (a) main 에는 아직 mergeable 상태, (b) 소급 시점·범위 미정의 → **P1 (governance) 로 판정**.

### 신규 P1 · 2건

| 위치 | 요지 |
|---|---|
| `validation-team-agent/tools/report_pack.py:main()` (Round 74, `7c0d1c1c`) | `salt = hashlib.sha256(f"vta-pack-salt-{args.seed}".encode()).digest()` — pseudonymize salt 가 argparse `--seed` (int) 로 완전 결정. 원본 파일 접근자는 파일 + 리포트 조합만으로 사전 계산 15hex SHA256 lookup 으로 pseudonym → 원본 ID 역매핑 자명. Round 73 `os.urandom(16)` 대비 **confidentiality → reproducibility 로 trade-off 했으나 access-control 대안 미제시**. `data_adapter.py` 헤더의 "**pseudonymize 기본 적용**" 안전 boundary 주장이 사실상 무효화. 커밋 코멘트 자체가 "salt 가 추정 가능하므로 원본 파일 접근자는 재식별 시도 가능" 시인. **fix: `--secret-key` env-var 우선, 없을 때만 seed 파생 (경고 로그)**. |
| `docs/ISO-42001-AGENT-REQUIREMENTS.md` (PR #30, `38376da7`) + `CLAUDE.md` §0 | "Every agent... MUST satisfy" + "does not meet all checklist items must not be merged" 는 현재 open PR #2·#3·#4·#5·#6·#9·#22 (모두 agent 성격) 를 **소급 차단**. 다음 미정의: (a) grandfathering 조항, (b) 마감일 (grace period), (c) "agent" 정의 (single subagent .md vs harness whole vs skill?), (d) 강제 메커니즘 (CI 미제공 → prose only). 현행대로면 이번 주 governance PR 하나가 나머지 6개 PR 을 block-merge. `CLAUDE.md §0` 강도(prose gate) 는 PR #5 의 `governance.py` Pillar 3 deprecated flag 와 동일한 실효성 패턴. **fix: 소급 조항 명시 (기존 PR grace, cutoff date), "agent" scope 정의, CI check 최소 하나 (예: `find */COMPLIANCE.md`) 추가**. |

### 신규 P2 · 6건

- **PR #4 `tools/data_adapter.py:120`** — `pd.to_datetime(df[mapping["date_col"]])` format 인자 없음. `"01/02/2024"` 같은 모호 문자열은 pandas 추론에 맡겨져 dayfirst 여부에 따라 조용히 오해석. 규제용 데이터에 silent misparsing 위험. **fix: `format='ISO8601'` 또는 명시 format 요구**.
- **PR #4 `tools/data_adapter.py:load_validation_input()`** — PII drop 시 + pseudonymize 시 두 번 `df.copy()`. 수백만 행 데이터에서 메모리 2배 사용, OOM 위험. **fix: pseudonymize 를 in-place 로 병합**.
- **PR #5 `risk_lib/audit_trail.py:114-129`** — `result.rwa["market"]/["op"]/["standardised_total"]` 접근에 guard 없음 (아래 optional 필드 `getattr(result, "ccr", None)` 는 guard 有). 파이프라인 config 에서 market/op RWA 스킵 시 KeyError. 혼합 방어 스타일 → 유지보수 이슈.
- **PR #5 `risk_lib/html_exec.py:_deep_dive_nav()`** — `groups.setdefault(spec.module.rsplit(".", 1)[-1], [])` 모듈 basename 으로만 그룹핑. 하위패키지 다른 두 모듈이 동일 basename (예: `credit.credit` vs `capital.credit`) 이면 병합. 66개 페이지 확장 시 잠재 충돌.
- **PR #10 `minecraft/index.html:1787-1798` (`toast()`)** — 큐 크기 상한 없음. 위더 스톰 스컬 폭발 + 보스 처치 + 밤 시작 등이 짧게 겹치면 20+ concurrent toast DOM element (각 `ms + 400ms` remove) 생성 → 상단 flex 레이아웃 thrash. `if (el.remove)` 체크는 element 의 method reference 이므로 항상 truthy — 방어로서 no-op.
- **PR #10 `minecraft/index.html:1789-1794`** — 업적 localStorage 키 `mc_achv` 에 version 필드 없음. 향후 업적 ID rename 시 stored set 이 stale garbage 로 잔존. `WORLD_VER` throw 패턴과 동일한 forward-compat 미비.

### 신규 P3 · 4건

- **PR #10 `updateSky()` 야간 감지** — 세이브가 s ≈ -0.06 (밤 초입) 에서 로드되면 `prevSun (1) >= -0.05 && s < -0.05` 로 즉시 "🌙 밤이 됩니다" 토스트 발화 (실제로는 이미 밤).
- **PR #10 `hunter` 업적** — `killCount` 는 `zi >= 0` (좀비 array 소속) 시에만 증가. 스켈레톤/보스/위더도 zombies 에 담기지만, 만약 별도 배열의 몹을 추가하면 카운트 누락 가능. 현재는 정상.
- **PR #4 `load_mapping()`** — 필수 키 누락을 `MappingError` 로 raise; 실제로는 스키마 문제이므로 명명 부적절 (`SchemaError` 등 별도 클래스).
- **PR #4 `_pseudonymize()`** — 15 hex (60 bit) 로 축소, 100만 건 기준 collision 확률 여전히 ≈4e-7 수준. 결정 가능하나 문서화 부재.

## Tracked 27건 재검증 결과

**FIXED × 1 유지 + PARTIAL × 3 유지 + LIVE × 23.** 지난주 MOVED × 2 (`report_pack.py` Basel Total-cap · `cet1_min_pillar1`) 는 실측 결과 **LIVE 재분류**.

### FIXED (유지)

- **PR #4 `validation-team-agent/middleware/permission_guard.py:31-43` (`PermissionFinding`)** — `category/pattern/length/location` 필드만 노출, matched text 없음. 15주차 첫 FIXED 유지 확인.

### 지난주 MOVED × 2 → 이번 주 LIVE 재분류 (PR #4)

지난주 (`PR #29`) 는 `report_pack.py` 가 `src/vta/` 로 이동하며 두 finding 이 MOVED 라고 판단했지만, 이번 라운드 실제 확인:

| 위치 (현재) | 상태 | 근거 |
|---|---|---|
| `tools/report_pack.py:3707` `cet1_min_pillar1 = 0.045` | **LIVE** | 파일 이동 없이 여전히 hardcode (라인 시프트 3692→3707). 새로운 `src/vta/domains/capital.py:54` 는 SSoT `load_thresholds()` 사용하나 old path 병존. |
| `tools/report_pack.py:3733` `total < cet1_required + 0.03` | **LIVE** | Basel III Total capital = 8.0% → CET1(4.5%) 대비 surcharge 는 `+ 0.035` 이어야 함. 3720 → 3733 line shift, 여전히 `+ 0.03`. |

### PARTIAL × 3 (유지)

| PR | 위치 | 상태 |
|---|---|---|
| #2 | `stock_trading/harness.py:210` | `[ERROR]` marker 추가되었으나 sticky `last_text` 여전 반환 (2주 무변화). |
| #2 | `stock_trading/harness.py:82-141` | trader import + consulted closure 격리 완료. APPROVED 플래그 run 내 sticky 여전. |
| #9 | `reports/basel-iii-endgame-implementation-status-2026-06-10.html:154-207` | 4 rows LIVE (2주 무변화). |

### LIVE × 23 (라인 시프트 포함)

- **PR #2 P0×2 LIVE** (2주 무커밋 → 8주 방치): `harness.py:~205` thinking=adaptive · `tools.py:234` place_order 음수 shares.
- **PR #4 P0×1 + P1×1 + P1×2 LIVE** (재분류 후): `pack_archive.py:82-83` path traversal · `scenario_weights.py:83` dict-zip dedup · `report_pack.py:3707` cet1 hardcode · `report_pack.py:3733` Basel Total-cap `+ 0.03`.
- **PR #5 P0×4 + P1×1 + P2×1 LIVE** (3주 연속 doc-only 커밋에도 미수정): `systemic.py:61` SRISK `(1-k)` · `rwa_sa.py:26/36/46` B-bucket RW=1.00 · `systemic.py:122` CoVaR own-loss · `frtb.py:173` FRTB multiplier · `governance.py` pillar3 deprecated · `repro.py:~178` setdefault(asof, None) · `AIMS_POLICY.md:8 vs :32` 카운트 불일치.
- **PR #9 P1×1 LIVE**: `harness/risk-research-runbook.md` G3/G4/G5 prose-only.
- **PR #10 P1×5 + P1×2 (지난주 추가) + P2×1 + P2×3 (지난주 추가) + P3×1 LIVE** (신규 커밋은 UI 만, tracked 미수정):
  - `applyPos` NaN: 3326 → **3390** (+64)
  - `destroyBlocks` CHEST: 821 → **834** (+13)
  - `saveGame` sync stall: 626 → **639** (+13)
  - `WORLD_VER=5` migration inv-loss: **334** (unchanged)
  - blinkTeleport 벽 관통 (지난주 P2) · timeStop arrows 배열 성장 (지난주 P2) · Wither Storm 볼레이 폭발-체스트 (지난주 P1)
- **PR #22 P0×3 LIVE** (5주 방치, close 권고 임박): `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md:11+:13` /code-review chain + auto-commit.
- **PR #3/6/7/8 P1/P2 LIVE**: 8주 무변화.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#30 (new)** | 1 (governance doc) | **P1×1** | — | **block-merge** (소급 조항 필요) |
| **#10** | 1 (UI feature) | P2×2 + P3×2 | tracked 12 LIVE (line-shift) | **block-merge** (tracked 미수정 지속) |
| **#5** | 5 (doc/UI/audit) | P2×2 | P0×4 + P1×1 + P2×1 LIVE (3주 연속 방치) | **block-merge** |
| **#4** | 2 (data adapter + CLI) | **P1×1** + P2×2 + P3×2 | FIXED×1 유지 · PARTIAL×3 유지 · LIVE 재분류 P0×1+P1×3 | changes requested (pseudonymize salt 재검토 필수) |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (8주 방치) | **block-merge** |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | **block-merge** |
| **#22** | 0 | — | P0×3 LIVE (**5주 방치**) | **close 권고 시행** |
| #3 / #6 | 0 | — | P1/P2 LIVE | changes requested |
| #7 / #8 | 0 | — | P1×2 + P2×2 LIVE | #7 close / #8 delta 검토 |

## 누적 17회 결산

|  | #25 | #26 | #27 | #28 | #29 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 2 | 0 | 0 | 0 | 0 | **0** |
| 신규 P1 | 10 | 0 | 1 | 2 | 2 | **2** |
| 신규 P2 | 25 | 1 | 2 | 4 | 3 | **6** |
| 누적 수정 | 7/77 | 7/79 | 7/82 | 8/84 | 8/86 | **8/88** (변화 없음, 재분류 2건 LIVE 복귀) |

**해석.**

1. **PR #4 구조 재편 진척 확인, 그러나 old path 잔존이 finding 존치 원인** — `src/vta/domains/capital.py` 는 SSoT (`load_thresholds()`) 사용해 hardcode 없이 구현했으나, `tools/report_pack.py` old path 가 아직 CLI (`report_pack --input-csv`) 의 primary entry point. 지난주 "MOVED × 2" 는 판단 오류 (파일이 실제 이동한 게 아니라 병렬 구현). **다음 라운드에서 old path 제거 또는 SSoT 로 위임 필요**.
2. **PR #5 doc-only 순환 3주째** — 이번 주도 audit ledger 확장 + CRO 브리핑 + registry nav 등 governance/UX. 2차 내부심사 (aims-compliance-auditor 에이전트 독립 수행) 는 심사 실행 자체의 독립 증적 확보로 긍정적이나, 심사 대상이 **산출된 report package 이지 리뷰 tracked P0×4 원인 코드가 아님**. self-audit 이 감독당국 실사 대체 오해 가능성 재환기.
3. **PR #30 신규 governance PR** — ISO 42001 compliance 도입은 방향성 옳으나 **enforcement gap 이 P1**. 현행 CLAUDE.md §0 은 6개 open agent PR 을 즉시 block 하는 강도로 작성됨. 소급 조항·CI 강제 없이 prose 만으로 gate 하는 방식은 PR #5 의 Pillar 3 deprecated flag 와 동일 실패 패턴 재현.
4. **PR #10 tracked 12건 미수정 지속** — 이번 UI 커밋은 게임 피드백 개선 (토스트/업적/피격 스파크) 로 데이터 손실·보안 finding 과 무관. 3주 연속 feature 위주로만 진행.
5. **PR #22 5주 방치** — 다음 라운드에서도 무변화 시 **close 권고 절차 시행 필요**.

## 다음 라운드 권고

1. **PR #30 신규 P1 즉시 fix** — CLAUDE.md §0 에 (a) grace period + cutoff date, (b) "agent" scope 정의 (하이라키 명시), (c) 최소한의 CI check (예: `find agents/ -name "COMPLIANCE.md"`) 추가. 그렇지 않으면 이 PR 하나가 나머지 6개 PR block-merge 원인이 됨.
2. **PR #4 신규 P1 fix** — `report_pack.py` pseudonymize 를 (a) `--secret-key` env-var 우선, (b) fallback 시 명시 경고 로그, (c) 재현성 필요 없을 때 `os.urandom` 유지 (Round 73 방식). Round 74 자체는 훌륭한 CLI wiring 이나 confidentiality/reproducibility trade-off 문서화 필요.
3. **PR #4 tracked LIVE 재분류 반영** — old `tools/report_pack.py` 를 SSoT (`src/vta/domains/capital.py:load_thresholds()`) 로 위임하거나 deprecate 표시. Basel Total-cap `+ 0.03` → `+ 0.035`.
4. **PR #5 P0×4 fix 촉구 재환기 (3주 연속)** — SRISK `(1-k)` · Corporate B RW 1.00→1.50 · CoVaR mask · FRTB multiplier BCBS MAR99 표. Doc/UI 개선 성과는 인정하되 본질 P0 는 별도 트랙 필요.
5. **PR #22 5주 방치 → close 권고 시행**.
6. **PR #2 8주 방치** — Sticky APPROVED 잔존 fix 재환기 (매주 반복).

## 리뷰 방식

**메인 스레드 단일 세션**:
- 10개 감시 PR + PR #30 head SHA 대조표 (4개 이동) → 스코프 한정
- **PR #30 신규**: 149 라인 (CLAUDE.md §0 + docs/ISO-42001 + templates/AGENT-COMPLIANCE) 전량 정독, governance-shape finding 발견
- **PR #10 delta**: 72 lines (`e41c634`) 전량 정독 + tracked 7건 라인 재특정
- **PR #5 delta**: 5 commits 372 lines (`216b7a5`, `8c4512f`, `98a6a86`, `59aa3db`, `dc4223d`) 정독, 신규 P2×2 발견, tracked P0×4 미터치 확인
- **PR #4 delta**: 2 commits 822 lines (`5bd453b` + `7c0d1c1c`) 정독 — `tools/data_adapter.py` (248 lines 신규), `tools/report_pack.py` +74 lines, pseudonymize salt 이슈 발견
- `permission_guard.py:31-43` FIXED 유지 확인
- `report_pack.py:3707/3733` **MOVED 오분류 → LIVE 재분류** 실측 확인
- 6개 stable PR head SHA 무변경 → tracked 20건 자동 LIVE

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
