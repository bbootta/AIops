# 전체 저장소 코드 리뷰 — 16주차

**날짜:** 2026-07-12 (UTC)
**범위:** 감시 대상 10개 PR (#2, #3, #4, #5, #6, #7, #8, #9, #10, #22)
**기준선:** PR #28 (2026-07-11 21:14 UTC)

## 요약

- **PR #10, PR #5** 두 곳에서 신규 커밋 유입. 나머지 8개 PR head SHA 무변경.
- **PR #10** — 커밋 1건 (`663f4a35`): 신규 적(어둠 마법사·화염 임프)·위더 스톰 슈퍼보스·닥터 스트레인지 슈트 3단계·맵 128→192 확장·`WORLD_VER=4 → 5`.
- **PR #5** — 커밋 1건 (`b560abbd`): 문서 전용 (ISO/IEC 42001 내부심사 기록 md 1건 + `.gitignore` 1줄). 코드 무변경.
- **신규 P0 · 0건** — WORLD_VER 재승격 후보였으나 기존 tracked P1 재발이므로 승격 아님.
- **신규 P1 · 2건** — 모두 PR #10, 위더 스톰 폭발 스컬 → 체스트 콘텐츠 소실 (severity ↑↑) + WORLD_VER=5 재승격 → v4 세이브 인벤 손실 (14주 만에 첫 fix 성과가 이번 라운드에서 리그레션으로 되돌아온 형태).
- **신규 P2 · 3건 / P3 · 3건** — 모두 PR #10 (Wither Storm 관련).
- **Tracked 27건 재검증** — PR #10 tracked 7건 라인 시프트 재특정 · PR #5 P0×4 tracked 그대로 LIVE (doc-only 커밋으로 코드 무영향) · 나머지 8개 stable PR head SHA 무변경 → 전량 LIVE.

## 이번 라운드 신규 findings

### 신규 P0 · 0건

`WORLD_VER=4→5` 재승격이 잠재적 P0 후보였지만 트리거 조건이 여전히 "이전 버전 save 존재 + 새 커밋 로드" 로 한정 → **P1 로 유지** (단, 지난주 v3→v4 대비 pool 확대 · 재발 = 회귀 신호).

### 신규 P1 · 2건 — 모두 PR #10

| 위치 | 요지 |
|---|---|
| `minecraft/index.html:1663 + 821` (커밋 `663f4a35`) | Wither Storm 스컬 폭발이 `destroyBlocks(r=1)` 를 **2.2초마다 3연발** 로 호출 (`updateArrows` 폭발 처리부). 위더 스톰은 보스 스폰의 30% · HP 120 · 사거리 44 → 플레이어 거점(체스트 다수) 상공 체류 시 **볼레이 당 최대 3 CHEST 파괴 + 콘텐츠 전량 소실 + `chests` Map 엔트리 유지 (slow leak)**. PR #26 부터 tracked 된 destroyBlocks-CHEST 결함이 (a) 크리퍼 → (b) 미사일 → (c) 위더 스컬로 **3단계째 경로 확대**. 근본 fix 필요: `destroyBlocks` 안에서 CHEST 감지 시 (L2626-2628) drop + `chests.delete(key)` 미러링 (8줄). |
| `minecraft/index.html:3362` (커밋 `663f4a35`) | `WORLD_VER = 5` 로 재승격. `if (save.worldVer != null && save.worldVer !== WORLD_VER) throw` 는 15주 전과 동일. catch (L3395-3406) 는 여전히 dims/curDim 만 리셋, **inv/tools/hotbar/health/hunger/armor** 는 restore **전에 throw 발생 → 기본값**. 지난주 P1(v3→v4)이 미수정 상태로 **v4→v5 로 pool 확대** — 지난주 v4 로 이전한 사용자가 이번 주 fresh v4 세이브까지 모두 소실. **fix: catch 블록에서 save.inv/tools/hotbar 를 별도로 파싱해 restore, 또는 WORLD_VER 승격시 edits 만 폐기하고 inv 는 보존.** |

### 신규 P2 · 3건 — 모두 PR #10

| 위치 | 요지 |
|---|---|
| `minecraft/index.html:397 + 420-425` | 위더 스컬은 시각적으로 `mesh.scale.setScalar(3.2)` 로 3.2배 확대되나 충돌 체크는 `a.pos.x ± 0.35` 고정 화살 히트박스 사용. 큰 스컬이 플레이어를 스치듯 지나가도 miss. UX/난이도 mismatch. **fix: `opts.big` 이면 hit 반경 0.35 → 1.1 로 확대.** |
| `minecraft/index.html:640-651` (blinkTeleport) | 조준 방향 12칸 스텝 0.5 로 collision 체크. **스텝 크기가 벽 두께보다 크면 벽 관통 텔레포트 가능** (0.4 두께 벽·창문틀 등). Doctor Strange 로 노클립 이동 → 몹 회피/월드 escape 가능. **fix: 스텝 0.25 이하 또는 `d` 를 정수 격자 라스터화.** |
| `minecraft/index.html:412` (updateArrows) | `if (timeStop) return;` — timeStop 활성 중 arrows 갱신 완전 정지 → **투사체 `life` 카운트다운도 정지**. 그러나 timeStop 해제 후 `life` 는 그대로. 플레이어가 위더 볼레이 (life=4s) 를 timeStop 4초로 카운트 소진시켜도 여전히 재활성 → 회피 자동화 불가. 단 반대로 **timeStop 유지 중엔 arrows 자연 despawn 도 정지** → 배열 무한 성장 (다중 볼레이 중 timeStop 남용 시 GC 압력·시각 잔상). **fix: timeStop 중에도 `life -= dt` 은 진행하되 위치·충돌만 정지.** |

### 신규 P3 · 3건 — 모두 PR #10

- `minecraft/index.html:243-249` — `spawnWitherStorm()` 이 out-of-bounds 시 early-return 하나 상위 `zombieSpawnT` 는 이미 리셋됨 → 조용한 스폰 tick 낭비 (1 tick / 4s).
- `minecraft/index.html:634-654` — blinkTeleport 후 `player.vel.set(0,0,0)` 이 낙하속도까지 리셋 → 급낙하 중 blink 로 낙하 데미지 완전 회피 (Iron/Hulkbuster 낙하 데미지 유효 시 밸런스 우회).
- `minecraft/index.html:1663` — Wither Storm 은 `curDim` 무관하게 소환 가능 (오버월드/네더 공통). 네더에서 Wither Storm + Fire Imp 조합은 의도된 것인지 불명확 (README 는 "밤엔 위더 스톰 출몰" 만 언급).

## Tracked 27건 재검증 결과

**FIXED × 0 + PARTIAL × 3 + MOVED × 2 + LIVE × 22** (변화: 지난주 첫 FIXED × 1 → 유지, 신규 커밋 없는 stable PR × 8 의 tracked 22건 자동 LIVE).

### FIXED — 지난주 확인분 유지 · 이번 라운드 신규 FIXED 없음

- `validation-team-agent/middleware/permission_guard.py:118` (PR #4, 지난주 확인) — head SHA 무변경 → 유지 (재확인 필요 없음).

### PARTIAL — 3건 (지난주 대비 무변경)

| PR | 위치 | 상태 |
|---|---|---|
| #2 | `stock_trading/harness.py:210` | `[ERROR]` marker 추가되었으나 sticky APPROVED 잔존. **head SHA 무변경**. |
| #2 | `stock_trading/harness.py:82-141` | trader import + consulted closure 격리 완료. APPROVED sticky 잔존. **head SHA 무변경**. |
| #9 | `reports/basel-iii-endgame-implementation-status-2026-06-10.html:154-207` | 4 rows LIVE (지난주 강등 후 유지). **head SHA 무변경**. |

### MOVED — 2건 (PR #4, 재확인 필요)

`validation-team-agent/report_pack.py` 는 여전히 `src/vta/` 레이아웃으로 재구조화 진행 중 (PR #4 head SHA 무변경). 다음 커밋 유입 시 신규 위치 특정 필요.

- `report_pack.py:3718` Basel III Total-cap `+ 0.03`
- `report_pack.py:3692` `cet1_min_pillar1 = 0.045` hardcode

### LIVE — 22건 (라인 시프트 재특정 포함)

**PR #10 tracked 7건 라인 시프트 재특정** (이번 커밋 `663f4a35`, +399 lines):

| finding | prev line | **new line** |
|---|---|---|
| `applyPos` NaN 방어 부재 (인자 `p.x/p.y/p.z` 수치 검증 없음) | 3030 | **3326** |
| `destroyBlocks` CHEST 미처리 (드롭 없음 + `chests.delete` 없음) | 821 | **821** (변화 없음, 함수 정의) |
| `damage()` 후 `health = Math.max(0, health - n)` — NaN 오염 전파 | 1579 | **1777** |
| Nether respawn `curDim` 재설정 로직 | 1557 | *(TBD — 이번 커밋에서 명시 이동 없음, 추정 line shift +200)* |
| `saveGame` sync stall (10초 interval + beforeunload + visibilitychange) | 626 | **626** (변화 없음) |
| Load-time `for (const k in inv)` — 저장 파일이 없는 키 미보존 | 3093 | **3387** |
| `BLOCK.SNOW` 자체 드롭 잘못됨 (`[BLOCK.DIRT, 1]`) | 350 | **350** (변화 없음) |

**PR #10 tracked destroyBlocks-CHEST** → 오늘의 신규 P1 로 재분류 (severity ↑).

**PR #10 tracked WORLD_VER migration** → 오늘의 신규 P1 로 재특정 (v4→v5).

**PR #2 P0×2 LIVE + P0×2 PARTIAL**: `harness.py:~205` thinking=adaptive · `tools.py:234` place_order 음수 shares. **head SHA 무변경.**

**PR #4 P0×1 + P1×2 MOVED + P1×1 LIVE**: `pack_archive.py:82-83` path traversal · `scenario_weights.py:83` dict-zip dedup · report_pack.py 이동 확인 대기. **head SHA 무변경.**

**PR #5 P0×4 + P1×1 + P2×1 LIVE**: `systemic.py:61` SRISK `(1-k)` · `rwa_sa.py:26/36/46` B-bucket RW=1.00 · `systemic.py:122` CoVaR own-loss · `frtb.py:173` FRTB multiplier · `governance.py` pillar3 · `repro.py:~178` · `AIMS_POLICY.md:8 vs :32` — **이번 doc-only 커밋 (`b560abbd`) 은 산업표준 감사기록만 추가, 위 P0/P1 원인 코드는 무변경.** 15주 방치.

**PR #9 P1×1 LIVE + PARTIAL(4 rows)**: `harness/risk-research-runbook.md` G3/G4/G5 prose-only · reports 4 rows. **head SHA 무변경.**

**PR #22 P0×3 LIVE**: `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md:11 + :13`. **4주 방치.** 다음 라운드 close 재권고.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#10** | 1 (feature) | **P1×2** + P2×3 + P3×3 | tracked 7건 라인 시프트 · destroyBlocks-CHEST 심각도 ↑ · WORLD_VER 재승격 | **block-merge** (신규 P1 데이터 손실 + 재현) |
| **#5** | 1 (doc-only) | 0 | P0×4 + P1×1 + P2×1 LIVE (무변경) | **block-merge** (본질 코드 무변경, 감사 기록만 추가) |
| **#4** | 0 | — | P0×1 LIVE + P1×1 LIVE + P1×1 FIXED + P1×2 MOVED | changes requested |
| **#22** | 0 | — | P0×3 LIVE (4주 방치) | **close 권고** |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (7주 방치) | **block-merge** |
| **#9** | 0 | — | P0 4 rows LIVE + P1×1 LIVE (7주 방치) | **block-merge** |
| #3 / #6 | 0 | — | P1/P2 LIVE (7주 방치) | changes requested |
| #7 / #8 | 0 | — | P1×2 + P2×2 LIVE (7주 방치) | #7 close / #8 delta 검토 |

## 누적 16회 결산

|  | #24 | #25 | #26 | #27 | #28 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 2 | 0 | 0 | 0 | **0** |
| 신규 P1 | 5 | 10 | 0 | 1 | 2 | **2** |
| 신규 P2 | — | 25 | 1 | 2 | 4 | **3** |
| 누적 수정 | 7/65 | 7/77 | 7/79 | 7/82 | 8/84 | **8/86** (+0 FIXED, +0 MOVED, +0 PARTIAL) |

**해석.**

1. **PR #4 진행 정체 (2주째)** — 지난주 FIXED × 1 + MOVED × 2 로 진행 신호 확인 후 이번 주 커밋 0건. `src/vta/` 레이아웃 재구조화 완료 여부 불명.
2. **PR #5 doc-only 커밋** — ISO/IEC 42001 내부심사 기록 추가는 governance 측면에서 긍정적이나 **본질 P0×4 (SRISK/RWA/CoVaR/FRTB) 는 15주 방치**. `docs/aims_audits/2026-07-12_internal_audit.md` 는 "적합 13/13" 을 선언하지만 감사 대상은 산출된 report package 이지 리뷰 tracked 원인 코드가 아님 — self-audit 이 감독당국 실사 대체로 오해 가능성 있음, 별도 공식 관련 절차 필요.
3. **PR #10 재발 패턴** — WORLD_VER 승격은 지난주 이어 2주 연속 P1 finding 생산. 근본 원인 fix 없이 새 feature 커밋만 이어지는 상태. destroyBlocks-CHEST 도 3주째 경로 확대만 반복.

## 다음 라운드 권고

1. **PR #10 신규 P1×2 즉시 fix** — (a) `destroyBlocks` 안에 CHEST drop + `chests.delete` 미러링 (8줄), (b) load catch 에서 save.inv/tools/hotbar 별도 파싱 (5줄) 또는 WORLD_VER 승격 시 edits 만 폐기 정책.
2. **PR #4 후속 커밋 요청** — `src/vta/report_pack.py` 신규 위치에서 Basel Total-cap `+ 0.03 → + 0.035`, `cet1_min_pillar1` SSoT 로드 확인 필요.
3. **PR #5** — doc 성과는 인정하되 **본질 P0×4 fix 우선 요청** (SRISK `(1-k)` · Corporate B RW 1.00→1.50 · CoVaR mask · FRTB multiplier MAR99). doc-only 순환 지양.
4. **PR #22 4주 방치** — 다음 라운드도 무변화 시 **close 권고 절차 개시**.
5. **PR #2 7주 방치** — Sticky APPROVED 잔존 fix 요청 재환기.

## 리뷰 방식

**메인 스레드 단일 세션** (72K tokens · 24 tool_uses):

- 10개 감시 PR head SHA 대조표 (PR #10 · PR #5 두 개만 이동) → 스코프 한정
- PR #10 신규 커밋 diff (685 lines) 전량 정독 + 신규 P1×2 + P2×3 + P3×3 발견
- PR #10 head SHA `663f4a35` 파일 (3520 LOC) tracked 7건 라인 재특정
- PR #5 신규 커밋 diff (doc + .gitignore) — 코드 무변경 확인
- 8개 stable PR head SHA 무변경 → tracked 22건 전량 LIVE 확인 (spot-check 스킵)

상세: 본 파일 (`CODE_REVIEW_2026-07-12.md`)

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
