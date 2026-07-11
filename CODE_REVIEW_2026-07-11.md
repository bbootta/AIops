# 전체 저장소 코드 리뷰 — 2026-07-11 (15주차)

## 요약

지난 라운드 (PR #27, 2026-07-10 21:13 UTC) 이후 24h. **감시 대상 10개 PR 중 PR #10 하나에만 신규 커밋 6건 유입**, 나머지 9개 PR head SHA 무변경.

- **PR #10 커밋 6건** (2026-07-11 05:39 ~ 13:21 UTC) — 히어로 슈트 변신(아이언맨→헐크버스터), 3인칭 카메라, 무기(펄서/미사일/레이저), 3개 신규 바이옴(정글/산악/버섯 들판), Free-orbit 카메라. `WORLD_VER=3` → `WORLD_VER=4` 승격.
- **신규 P0** — 0건.
- **신규 P1** — 2건 (모두 PR #10, 후술 데이터 손실 · 미사일-체스트 상호작용).
- **신규 P2** — 4건, P3 — 2건 (모두 PR #10).
- **Tracked 26건 재검증** — **FIXED × 1 (14주 만에 첫 실제 수정)** + PARTIAL × 3 + MOVED × 2 + LIVE × 20.

## 이번 라운드 신규 findings

### 신규 P0 · 0건

`WORLD_VER=4` 승격이 잠재적 P0 후보였지만, 데이터 손실은 v3 save 를 가진 기존 플레이어에 국한 (신규 세션 무영향) + 트리거 조건이 "이전 세이브 존재 + 새 커밋 로드" 로 명확 → **P1 로 판정**.

### 신규 P1 · 2건 — 모두 PR #10

| 위치 | 요지 |
|---|---|
| `minecraft/index.html:3068` (커밋 `145db1f1`) | `WORLD_VER=4` bump 이 v3 save 로드 시 `throw` → 캐치 핸들러 (L3101-3111) 는 dims 만 초기화, inv/tools/hotbar/health/hunger 는 restore 이전에 throw 발생 → **기존 플레이어 인벤토리·도구·핫바 전량 소실**. 6개 신규 바이옴은 기존 편집 블록과 코스메틱만 다르므로 v3→v4 마이그레이션이 안전 가능. **fix: v3 save 는 dims/edits 유지한 채 worldVer 만 승격, 또는 catch 에서 inv/tools/hotbar 별도 파싱**. |
| `minecraft/index.html:821` (미사일 폭발이 새로 트리거) | `explodeAt(r,dmg)` → `destroyBlocks` 가 CHEST 를 파괴하되 콘텐츠 드롭 부재 + `chests` Map 엔트리 미제거. PR #26 부터 crecper 경로에서 P1 로 tracked 되던 결함이 이번 커밋 `657e32ab` 의 미사일(반경 2, Hulkbuster 반경 3) 로 **정상 플레이 루틴 이벤트로 승격** → severity ↑. `chests` map 은 GC 되지 않아 slow memory leak. **fix: destroyBlocks 안에서 CHEST 감지 시 L2626-2628 로직 (drop + `chests.delete(key)`) 미러**. |

### 신규 P2 · 4건 — 모두 PR #10

| 위치 | 요지 |
|---|---|
| `minecraft/index.html:1816-1825, 2301-2323` | 슈트 해제(`toggleSuit`) 시 `suitBoostLight` (`PointLight`) 와 `u.flames.visible` 초기화 안 됨 — 마지막 위치에 주황 광원 영구 잔존. |
| `minecraft/index.html:2074-2101` | 두 손가락 → 한 손가락 전환 시 `lookX/lookY` 미갱신 → 첫 `touchmove` 가 stale 값과의 델타로 yaw/pitch 스냅. |
| `minecraft/index.html:1604-1606` | `preventDefault` on `AltLeft/AltRight` 이 무조건 발동 → 시작 화면·인벤토리 등에서도 브라우저 Alt+menu 단축키 차단. `if (locked && suit)` 게이트 필요. |
| `minecraft/index.html:2087` | Pinch 처리에서 tpts Map value 를 mutate 후 delta 계산 → asymmetric pinch 시 의도치 않은 yaw. |

### 신규 P3 · 2건 — 모두 PR #10

| 위치 | 요지 |
|---|---|
| `minecraft/index.html:2422-2427` | Laser 빔 길이 30 vs `pickBlock` 내부 REACH clamp — 블록 관통 렌더링. |
| `minecraft/index.html:2337, 2350` | `bolts` 상한 30 을 펄서/미사일이 공유 → 펄서 spam 이 미사일 발사 starve. |

## Tracked 26건 재검증 결과

**FIXED × 1 + PARTIAL × 3 + MOVED × 2 + LIVE × 20 = 26.** 14주 연속 "26/26 LIVE" 흐름이 처음 깨졌음.

### FIXED — 1건 (PR #4)

- **`validation-team-agent/middleware/permission_guard.py:118`** — `PermissionFinding` 이 category/pattern/length/location 튜플만 노출, matched text 는 docstring 에서 명시 제외. **prior P1 secret echo 실질 수정**. 14주 만에 첫 tracked fix.

### PARTIAL — 3건 (PR #2 × 2, PR #9 × 1)

| PR | 위치 | 상태 |
|---|---|---|
| #2 | `stock_trading/harness.py:210` | Exception marker `[ERROR]` 는 추가되었으나 sticky `last_text` (APPROVED prefix 가능) 여전 반환. 절반 해결. |
| #2 | `stock_trading/harness.py:82-141` | `trader` import 완료 (unbound 해결) + `consulted` 가 run 당 closure 로 격리. 하지만 **APPROVED 플래그 자체는 run 내에서 sticky** (re-consult 시 reset 안 됨). |
| #9 | `reports/basel-iii-endgame-implementation-status-2026-06-10.html:154-207` | 5 rows LIVE → **4 rows LIVE** (C-001·C-004·C-005·C-006). 한 행 (추정 C-009) 이 High → Medium 강등된 듯. 핵심 결함 (T1 + High + locator=TBD) 은 잔존. |

### MOVED — 2건 (PR #4)

`validation-team-agent/report_pack.py` 파일이 검색되지 않음 — **`src/vta/` 레이아웃으로 재구조화 진행 중** (2026-07-08 마지막 커밋 관련):

- `report_pack.py:3718` — Basel III Total-cap `+ 0.03` (should be `+ 0.035`) — **파일 이동, 재확인 필요**
- `report_pack.py:3692` — `cet1_min_pillar1 = 0.045` hardcode — **파일 이동, 재확인 필요**

**주의**: 결함이 사라진 게 아니라 파일이 옮겨졌으니 다음 라운드에서 새 위치 특정 필요. 진행 신호로 해석.

### LIVE — 20건 (라인 시프트 포함)

- **PR #2 P0×2 LIVE**: `harness.py:~205` thinking=adaptive · `tools.py:234` place_order 음수 shares.
- **PR #4 P0×1 + P1×1 LIVE**: `pack_archive.py:82-83` (was 99/107, 라인 시프트 -17) path traversal · `scenario_weights.py:83` dict-zip dedup.
- **PR #5 P0×4 + P1×1 + P2×1 LIVE**: `systemic.py:61` SRISK `(1-k)` · `rwa_sa.py:26/36/46` B-bucket RW=1.00 (Sovereign·Bank·Corporate 3 asset class) · `systemic.py:122` CoVaR own-loss · `frtb.py:173` (was 166, 라인 시프트 +7) FRTB multiplier · `governance.py` pillar3 deprecated · `repro.py:~178` `setdefault(asof, None)` (이전 라운드 P2 승계) · `AIMS_POLICY.md:8` vs `:32` 스페셜리스트 카운트 (이전 P1 승계).
- **PR #9 P1×1 LIVE**: `harness/risk-research-runbook.md:74/104/129` (was 78/96/141) G3/G4/G5 gates prose-only.
- **PR #10 P1×5 + P2×1 + P3×1 LIVE** (전체 라인 시프트 +40 ~ +500):
  - `applyPos` NaN: 2564 → **3030**
  - `destroyBlocks` CHEST: 783 → **821** (신규 P1 로 위 재분류, 미사일 폭발 트리거 신설)
  - `health` NaN: 2624 → **1579** (rig 재구성으로 이동)
  - Nether respawn `curDim`: 1484 → **1557**
  - `saveGame` sync stall: def **626** (was 588), 호출부 8곳
  - Load-time `for (const k in inv)`: 2627 → **3093** (여전히 부분 saves 침묵 초기화)
  - `BLOCK.SNOW` self-drop: 343 → **350**
- **PR #22 P0×3 LIVE**: `skills-lock.json` (37개 skill 전부 `sourceCommit` 부재, 0 hits) · `.claude/skills/code-review/SKILL.md` (slug 충돌) · `.claude/skills/implement/SKILL.md:11 + :13` (`/code-review` chain + `Commit your work` auto-commit 지시).

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#10** | 6 (feature) | **P1×2** + P2×4 + P3×2 | P1×5 + P2×1 + P3×1 LIVE (line-shift) | **block-merge** (신규 P1 데이터 손실) |
| **#4** | 0 | — | P0×1 LIVE + P1×1 LIVE + **P1×1 FIXED** + P1×2 MOVED | changes requested (fix 진행 확인) |
| **#5** | 0 | — | P0×4 + P1×2 + P2×1 LIVE | **block-merge** |
| **#22** | 0 | — | P0×3 LIVE | **block-merge** |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (부분 개선) | **block-merge** (14주+ 정체지만 부분 이동) |
| **#9** | 0 | — | P0 5→4 rows LIVE (PARTIAL) + P1×1 LIVE | **block-merge** |
| #3 / #6 | 0 | — | P1/P2 LIVE | changes requested |
| #7 / #8 | 0 | — | P1×2 + P2×2 LIVE | #7 close / #8 delta 검토 후 merge |

## 누적 15회 결산

|  | #23 | #24 | #25 | #26 | #27 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 3 | 0 | 2 | 0 | 0 | **0** |
| 신규 P1 | 3 | 5 | 10 | 0 | 1 | **2** |
| 신규 P2 | ≥2 | — | 25 | 1 | 2 | **4** |
| 누적 수정 | 7/60 | 7/65 | 7/77 | 7/79 | 7/82 | **8/84** (+1 FIXED, +2 MOVED, +3 PARTIAL) |

**해석.** 3개 지표에서 첫 유의미한 변화:

1. **첫 tracked FIXED 확인** — `permission_guard.py:118` (PR #4). 14주 prose 리뷰의 첫 성과.
2. **PR #4 구조 재편 진행** — `report_pack.py` (Basel III 소스) 가 `src/vta/` 레이아웃으로 이동. Basel 관련 P1 fix 를 위한 사전 정지 작업으로 해석 가능. 다음 라운드에서 신규 위치 특정 후 재확인.
3. **PR #2 두 P0 부분 개선** — trader unbound 해결 + `[ERROR]` marker 추가. Sticky APPROVED 잔존.

반대로:
- **PR #10 신규 P1×2** 는 각각 (a) 데이터 손실 (기존 플레이어 인벤 소실), (b) severity 상승 (미사일-체스트 상호작용) — 리그레션.
- **PR #5 tracked P0×4 는 이번 주 무커밋** (14주 방치 지속).

## 다음 라운드 권고

1. **PR #10 신규 P1×2 즉시 fix** — WORLD_VER 마이그레이션 (v3 inv 유지) 은 v3→v4 코스메틱 승격 명시로 5줄 이내. destroyBlocks CHEST 미러링은 L2626-2628 로직 재사용으로 8줄 이내.
2. **PR #4 재확인 작업** — `report_pack.py` 신규 위치 (`src/vta/**/report_pack.py` 또는 유사) 특정 → Basel Total-cap `+ 0.03` → `+ 0.035` · `cet1_min_pillar1` SSoT 로드 방식으로 재작성.
3. **PR #5 tracked P0×4 재환기** — SRISK `(1-k)` · Corporate B RW 1.00→1.50 (3 asset class) · CoVaR mask · FRTB multiplier BCBS MAR99 표. 각 1~3줄 mechanical fix. 이번 주 무커밋 유지 시 fix-PR 자동 제출 옵션 재검토.
4. **PR #22 3주 방치** — `code-review/` 슬러그 삭제 · `skills-lock.json` `sourceCommit` 추가 · `/implement` chain + auto-commit 삭제. 다음 리뷰에서도 무변화면 close 권고.
5. **PR #2**: 부분 개선 확인 → prose 채널 도달 중. Sticky APPROVED 잔존 fix 요청.

## 리뷰 방식

**2개 병렬 Explore 에이전트 + 메인 검증**:

- **(A) PR #10 fresh-eyes** — 90K subagent tokens · 36 tool_uses. 6개 신규 커밋 diff + head SHA `34a5899d` 파일 (3227 LOC) 전수 스캔. Part 1 신규 P1×2 + P2×4 + P3×2. Part 2 tracked 7건 라인 재특정.
- **(B) Stable PR tracked 재검증** — 112K subagent tokens · 28 tool_uses. PR #2/#4/#5/#9/#22 head SHA 무커밋 21건 spot-check. FIXED × 1 (permission_guard) · PARTIAL × 3 (harness.py 두 건, report html) · MOVED × 2 (report_pack 이동) · LIVE × 15 확인.
- **메인**: 10개 감시 PR head SHA 대조표 (PR #10 만 이동) → 스코프를 (a) PR #10 6 commits + (b) tracked 26건 spot-check 로 한정. 코드 없는 무커밋 PR (7개) 은 mechanically 라인 재특정 없이 LIVE 처리.

---

_본 리뷰 보고서는 draft PR body 로 요약 표시되며, 상세는 이 파일 (`CODE_REVIEW_2026-07-11.md`) 참조._
