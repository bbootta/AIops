# 전체 저장소 코드 리뷰 — 32주차 (2026-07-31)

**세션 기준 시각:** 2026-07-31 21:03 UTC
**직전 리뷰:** PR #51 (2026-07-30 21:11 UTC, 31주차)
**베이스:** `origin/main` = `281d6017` (**30일째 무변경**)

---

## 1. 감시 활동 요약 (지난 24h)

| 채널 | HEAD SHA | 마지막 커밋 시각 (UTC) | 델타 | 비고 |
|---|---|---|---|---|
| `main` | `281d6017` | 2026-07-01 (30일 전) | 커밋 0 | `.gitkeep`/`CLAUDE.md`/`.claude/settings.json` 3파일 정지 |
| **PR #10 `claude/minecraft-game-tqv3ii`** | **`844fb48b`** | **2026-07-31 19:59:34** | **커밋 +1 (신규)** | **"Polish the graphics across ten passes" 316 add / 105 del · §3 참조** |
| `claude/risk-management-agent-harness-B9Kxm` | `553a4a8` | 2026-07-29 12:42:18 | 커밋 0 | 30주차 baseline SHA 그대로. **56h 무커밋** (2일 연속). §4 참조. |
| `claude/validation-team-agent-Pw9F5` | `59032de` | 2026-07-29 12:27:44 | 커밋 0 | 30주차 baseline SHA 그대로. **57h 무커밋** (2일 연속). §4 참조. |
| PR #46 `claude/nail-simulation-program-i79qef` | `01fc7cb4` | 2026-07-27 14:30:47 | 커밋 0 | **~102h 무커밋. §5 참조 — 5주 미이행 확정.** |
| PR #38 `claude/3d-shooting-game-khpuk3` | `6f9cfb1` | 2026-07-26 07:14:56 | 커밋 0 | 헤드 정지 |
| PR #32 `claude/mecha-chameleon-game-xyiguj` | `e63e5d2` | 2026-07-14 04:19:59 | 커밋 0 | 헤드 정지 |
| PR #30 `claude/iso-42001-agent-compliance-exq9qe` | `38376da` | 2026-07-13 14:45:03 | 커밋 0 | 헤드 정지 |
| PR #22 `claude/skills-plugin-install-nk7ez7` | `907839e` | 2026-07-05 05:16:15 | 커밋 0 | 헤드 정지 |
| PR #43·#45·#47·#48·#49·#50·#51 리뷰 draft head | — | — | 커밋 0 | 리뷰용 draft, 자체 델타 없음 |
| `codex/*`, `claude/quant-validation-agent-qytpk`, `claude/stock-trading-agent-harness-ZuSJc`, `claude/global-harness-enhancement-1v9b78`, `claude/problem-resolution-v9x6c5` 등 | — | — | 커밋 0 | 표본 검증 · 헤드 정지 |

**총평 (single-PR delta 라운드):** 이번 24h 는 PR #10 (마인크래프트) 에 신규 커밋 1건 (`844fb48b` "Polish the graphics across ten passes", 316 add / 105 del). 그 외 12개 표본 브랜치 전부 zero-delta. B9Kxm/Pw9F5 는 30주차 baseline 그대로 2일 연속 무커밋 (§4). PR #46 은 5주 연속 무커밋 확정 (§5). PR #51 이후 신규 PR 없음.

**핵심 마일스톤:**
- **PR #10 R8 pass 가 tracked P1 "동물/마을주민 GPU 리소스 미해제" 를 확장**. 동물 sub-mesh 를 6개 → 13개 (snout · 4 eyes · 2 ears · tail 신규) 로 늘렸으나 dispose 4경로 (killMob · updateAnimals cull · deactivateVillage · clearMobs) 는 이전과 동일하게 부재 → **누수 단위량 약 2.2배 증가** (§3).
- **PR #46 P0 5주 미이행 확정.** 31주차 external escalation 검토 조건 발동 상태 지속 (§5).
- **B9Kxm/Pw9F5 2일 연속 무커밋.** 31주차 §4 "다음 라운드 재확인" 조건 도달. **tracked-active → tracked-dormant 재분류 검토 조건 발동** (§4).

---

## 2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| **신규 P0** | **0** (기존 tracked P0 는 유지) |
| **신규 P1** | **0** (PR #10 tracked P1 확장 판정 — §3, 신규 finding 아님) |
| **신규 P2** | **1** — PR #10 동물 재질 per-instance jitter (§3-B) |
| **신규 P3** | **0** |
| **Regression** | **0** (PR #10 신규 커밋은 dead-code 도입 아니고 확장, HEAD 변경으로 상태 재확인) |
| **Tracked LIVE 재확인** | **50건** — P0×8 · P1×7 · P2×16 · P3×19. §6 참조. |
| **⚠ 특기** | **PR #10 P1 dispose 확장 (§3)** · **B9Kxm/Pw9F5 2일 연속 무커밋 → tracked-dormant 검토 (§4)** · **PR #46 5주 미이행 확정 (§5)** |

---

## 3. ⚠ 특기 #1: PR #10 R8 pass 가 tracked P1 "동물/마을주민 dispose 누수" 를 **확장** (2.2×)

### 3-A. 확장 상세 (P1 유지 · 누수 단위량 증가)

**커밋:** `844fb48b` (2026-07-31 19:59:34 UTC), commit msg "animals gain eyes, snouts, ears and tails with per-animal colour drift".

**변화된 `makeAnimalMesh`** (`minecraft/index.html:1992-2031`):

| 부위 | 변경 전 | 변경 후 | 지오메트리 |
|---|---|---|---|
| body | ✓ | ✓ | per-instance BoxGeometry |
| head | ✓ | ✓ | per-instance BoxGeometry |
| **snout** | — | **신규 (line 2005-2007)** | per-instance BoxGeometry |
| **eyes 흰자 ×2** | — | **신규 (line 2009-2011)** | per-instance BoxGeometry |
| **eyes 눈동자 ×2** | — | **신규 (line 2012-2014)** | per-instance BoxGeometry |
| **ears ×2** | — | **신규 (line 2017-2019)** | per-instance BoxGeometry |
| **tail** | — | **신규 (line 2021-2023)** | per-instance BoxGeometry |
| legs ×4 | ✓ | ✓ | per-instance BoxGeometry |
| **합계 sub-mesh** | **6** | **13** | **누수 단위 2.2배** |

**변화된 재질:**
- `EYE_WHITE` (line 1990) · `EYE_BLACK` (line 1991): **모듈 상수, 올바르게 공유** (dispose 대상 아님).
- `bodyMat` · `headMat`: **인스턴스별 jitter 로 매 개체마다 새 MeshLambertMaterial 생성** (line 1996-1997). §3-B 참조.
- `legMat` (line 1998): 변경 없음, 여전히 인스턴스별 (이전 결함 유지).

### 3-B. 신규 P2: 동물 재질 per-instance jitter → 재질 누수 표면 증가

**위치:** `minecraft/index.html:1995-1997`

```js
const jitter = (c) => new THREE.Color(c).offsetHSL(0, (Math.random() - 0.5) * 0.05, (Math.random() - 0.5) * 0.06);
const bodyMat = new THREE.MeshLambertMaterial({ color: jitter(type.body) });
const headMat = new THREE.MeshLambertMaterial({ color: jitter(type.head) });
```

**결함:** 이전 코드는 `type.body`/`type.head` 색을 그대로 사용해서 종별로 재질을 공유할 여지가 있었으나, 이번 R8 pass 는 매 개체마다 색을 HSL 지터링해서 재질을 **개체별 유일** 로 만들었다. 결과:
1. **드로우콜 최적화 불가**: 지터링된 재질 은 두 개체 간 절대 일치하지 않으므로 렌더러 batch merge 대상에서 제외.
2. **P1 dispose 누수 표면 확장**: 동물당 최소 3개 재질 (`bodyMat`, `headMat`, `legMat`) 이 인스턴스별로 존재. dispose 4경로 어디에서도 재질 dispose 없음.

**failure scenario:** ANIMAL_CAP=16 이므로 야생 동물은 상한 있지만, 플레이어가 150m 이상 이동하면 `updateAnimals(dt)` 의 `if (Math.hypot(...) > 150)` (line 2164) 로 cull → `animals.splice(i, 1)`. 이후 `animalTopupT` 3초 사이클마다 최대 3마리 새로 spawn. 5분 자유 이동 시 약 300 회 spawn/cull → **재질 300 × 3 = 900개 및 지오메트리 300 × 13 = 3900개** 누수. WebGL 재질 슬롯 상한 (드라이버별 상이, 통상 수천) 부담.

**Fix cost:** 종별 재질 캐시 도입 (약 10줄) — `const ANIMAL_MATS = new Map()`, `ANIMAL_MATS.get(type.body) ??= new MeshLambertMaterial({color: type.body})` 패턴. 또는 jitter 를 vertex color 로 굽고 재질 vertexColors=true 로 공유 (soldier 패턴 참조).

**격상 판정:** 신규 P2 (재질 누수 표면 확장 · dispose 4경로 부재의 결과 확대). 30일 미이행 시 P1 격상 검토.

### 3-C. dispose 4경로 상태 (변경 없음 · P1 유지)

R8 pass 는 sub-mesh 를 확장했지만 dispose 4경로 전부 이전과 동일한 `scene.remove(mesh)` 만:

| 경로 | 라인 | 코드 | 상태 |
|---|---|---|---|
| updateAnimals cull (>150m) | 2165 | `scene.remove(a.mesh); removeHpBar(a); animals.splice(i, 1)` | **children dispose 부재** |
| killMob (동물·주민 사망) | 3374 | `scene.remove(m.mesh); ... removeHpBar(m); ... animals.splice(ai, 1)` | **children dispose 부재** |
| deactivateVillage (마을 이탈) | 2296 | `scene.remove(animals[i].mesh); removeHpBar(animals[i]); animals.splice(i, 1)` | **children dispose 부재** |
| clearMobs (게임 리셋) | 5457 | `for (const a of animals) { scene.remove(a.mesh); removeHpBar(a); }` | **children dispose 부재** |

**참조 (올바른 패턴):**
- `SOLDIER_GEO`/`SOLDIER_MAT` (`minecraft/index.html:2423-2452`): 병사 100마리 소환을 대비한 병합 지오메트리 캐시 + `vertexColors: true` 공유 재질. **동물·주민 도 이 패턴을 따라야 한다.**
- `ZG_LEG`/`ZG_BODY`/`ZG_HEAD`/`ZG_ARM` (line 2660-2663): 좀비 지오메트리 공유. 마을 주민의 legs·body·head 도 이 상수를 재사용하는 것이 이미 코드에 존재 (line 2226·2230·2236) — 이것이 올바른 방향.

**Fix cost:**
- (a) `EYE_WHITE`/`EYE_BLACK` 처럼 나머지 sub-mesh 지오메트리도 모듈 상수로 승격 (`const ANIM_SNOUT = new BoxGeometry(...)` 등, 약 20줄). → 동물 지오메트리 인스턴스 0개.
- (b) legMat 도 상수화 (1줄).
- (c) bodyMat/headMat 는 §3-B 캐시 도입 (약 10줄).
- (d) 위 3개 완료 시 dispose 경로 수정 불필요 (지오메트리·재질이 공유 상수이므로 dispose 대상 없음).

**격상 판정 (P1 유지):** R8 이 확장했지만 fix cost 는 여전히 30줄 내. 26주차 이후 4주 방치되었던 항목이 확장된 형태로 5주째 진입. 다음 라운드 재확인.

---

## 4. ⚠ 특기 #2: B9Kxm / Pw9F5 **2일 연속 무커밋** → tracked-dormant 재분류 검토 조건 발동

31주차 (PR #51 §4) 는 "이번 라운드에서 P0 격상 없음, 다음 라운드 재확인" 판정. 32주차 (오늘) HEAD 확인 결과:

- `origin/claude/risk-management-agent-harness-B9Kxm` = `553a4a8` (2026-07-29 12:42:18 UTC, **56h 무커밋 · 2일 연속**)
- `origin/claude/validation-team-agent-Pw9F5` = `59032de` (2026-07-29 12:27:44 UTC, **57h 무커밋 · 2일 연속**)

### 관찰

30주차 (PR #50) 지적 항목 31/32주차 이행 상태:

| 항목 | 30주차 판정 | 32주차 상태 | 방치 |
|---|---|---|---|
| B9Kxm P1-NEW #1 `test_assumption_claims.py` 자기충족 grep | 24h 미이행 시 P0 격상 검토 | 미이행 | **72h** |
| Pw9F5 P1-NEW #2 `conditional_approval.json` 6차 스냅샷 canonical | 24h 미이행 시 P0 격상 검토 | 미이행 | **72h** |
| B9Kxm P2-NEW #3 `RECALC_SCOPE` citation F-C02 정합 | 1분 편집 | 미이행 | **72h** |
| B9Kxm 30주차 P2×4 + P3×4 | 1주 이내 | 미이행 | 72h |
| Pw9F5 30주차 P2×4 + P3×4 | 1주 이내 | 미이행 | 72h |
| B9Kxm 29주차 잔존 P2×2 + P3×4 | 재확인 | 미이행 | **96h** |

### 프로파일 재해석

31주차 §4 는 두 브랜치 zero-delta 를 "다음 사이클 준비 중 vs. 오퍼레이터 재조정 vs. 브랜치 정지" 3가지 가설로 열어둠. 2일 연속 무커밋 (56h/57h) 은 첫 두 가설의 시간 프로파일 (통상 사이클 6~24h) 을 이미 초과. **3번째 가설 (브랜치 정지) 의 가능성이 유의미 증가.**

### 판정

**tracked-active → tracked-dormant 재분류 검토 조건 발동.**

구체적 tracked-dormant 재분류의 warden 의미:
- 매 라운드 P1/P2/P3 시정 여부 확인 부담 완화 (dormant 는 주 1회 헤드 확인만).
- 격상 사이클 정지 (dormant 는 시간 경과로 자동 격상하지 않음).
- 활동 재개 시 tracked-active 로 복귀 · 격상 사이클 재개.

다음 라운드 (33주차) 재확인 프로토콜:
- 두 브랜치 HEAD SHA 동일 유지 확인 시 **정식 dormant 전환** (3일 연속 무커밋 · 통상 사이클 100% 초과).
- 활동 재개 시 (신규 커밋 발생) 30주차 P1×2 격상 사이클 (30→31→32→33 = 3주 미이행 → P0 검토) 재개.

**병행 (31주차 §4·§7 재반복):** `AIMS_POLICY.md` / Pw9F5 대칭 문서에 "agent-team internal branches" 조항 명문화 (**6주 연속** 재권고). 두 브랜치가 여전히 open PR 미개설 상태에서 활동 중단은 warden 큐에 유효 정보 없이 남는 부담.

---

## 5. ⚠ 특기 #3: PR #46 `render.js` dead-store — **5주 미이행 확정 · external escalation 검토 조건 지속**

### 격상 이력 (32주차 갱신)

| 주차 | 상태 | 근거 |
|---|---|---|
| 26주차 (2026-07-14) | 최초 P1 | `js/render.js:597, 601, 606` 세 곳 `g.push` dead-store |
| 27주차 | 1주 미이행 | 커밋 없음 |
| 28주차 | 2주 미이행 → 격상 규정 명문화 | "P1 dead-store 다음 라운드에서 P0 격상 검토" |
| 29주차 | **P0 격상 확정** | 3주 미이행 시 warden 프로세스 실패 격상 |
| 30주차 | **warden 프로세스 실패 격상** | 3주 미이행 확정. PR #50 §6: "4주째면 external escalation 검토" |
| 31주차 | **external escalation 검토 조건 발동** | 4주 미이행 확정 |
| **32주차 (오늘)** | **5주 미이행 확정 · external escalation 검토 조건 지속** | HEAD `01fc7cb4` 그대로 (**~102h 무커밋** = 4일 초 흐름) |

### 현재 상태 (독립 재확인)

- HEAD SHA: `01fc7cb4193fbf05cc7fd770c14526bf79f86b2e`
- `js/render.js` blob SHA: `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` (31주차와 동일)
- `nail(fg, d, sk, selected)` 함수의 dead-store 3건 (ridges · side stroke · env reflection · line 597/601/606) 확정 유지.

### 프로세스 관찰 (5주 도달)

31주차 external escalation 검토 조건 발동 이후 24h 무액션 (커밋도 · 인간 결재도 · policy 조정도 없음). warden 격상 사이클 자체가 forcing 함수 없음이 실증 5주째. PR #50 §6 명문 규정 ("4주째면 external escalation 검토") 이 발동만 되고 액션은 부재.

### 32주차 external escalation 권고 (재반복)

- **인간 결재선 알림 실행:** PR #46 저자 · 브랜치 소유자에게 4주+ 미이행 사실 통보. warden 세션은 GitHub MCP `mcp__github__add_issue_comment` 또는 `mcp__github__update_pull_request` 를 통해 PR #46 에 warden 코멘트 게시 검토 (본 리뷰 draft PR 은 리뷰 채널이지 저자 알림 채널이 아님).
- **policy 재조정:** warden 지적을 X주 내 응답하지 않는 draft PR 에 대한 forcing 함수 (draft 잠금 · auto-close) 논의.
- **PR #46 상태 재검토:** draft close · issue 재제기 검토.

**병행 (5주차 재반복):** `no-unused-expressions` lint 도입 · 시각적 회귀 스냅샷.

---

## 6. Tracked LIVE — 재확인 (전항 상태 유지 + PR #10 R8 확장 + 신규 P2 1건)

| PR / 브랜치 | 항목 | 방치 | 상태 |
|---|---|---|---|
| **PR #46** | **`render.js:597,601,606` dead-store (P0)** | **5주** | **⚠ external escalation 검토 조건 지속 · §5** |
| **PR #10** | **동물/마을주민 GPU 리소스 미해제 (P1) — R8 pass 로 sub-mesh 6→13 확장** | **5주** | **⚠ 누수 단위 2.2배 증가 · §3-A** |
| **PR #10** | **동물 재질 per-instance jitter (P2, NEW)** | **~2h** | **§3-B · 신규 finding** |
| PR #10 | warden 벽투과 sonic LOS (P1) | 11주 | 커밋 없음 (R8 은 시각 폴리시 전용) |
| PR #48 | `hand3d.js:361-365` buildHand 첫 진입 프리즈 (P2) | 3주 | 커밋 없음 |
| PR #48 | `hand3d.js:773-778` pick() 매 클릭 재할당 (P2) | 3주 | 커밋 없음 |
| PR #48 | `hand3d.js:672-676` wheel 페이지 스크롤 트랩 (P3) | 3주 | 커밋 없음 |
| PR #48 | `app.js:240-246` Blob URL revoke race (P3) | 3주 | 커밋 없음 |
| PR #48 | `hand3d.js:650-677` pointercancel 미처리 (P3) | 3주 | 커밋 없음 |
| PR #5 | Basel 기업 B RW 1.00 → 1.50 (P0) | **16주** | 커밋 없음 |
| PR #5 | SRISK `(1-k)` 인자 누락 (P0) | **16주** | 커밋 없음 |
| PR #5 | CoVaR own-loss mask (P0) | **16주** | 커밋 없음 |
| PR #4 | CHG-0143 재사용 + ERRATA-2026-07-14 (P0) | **12주** | 커밋 없음 |
| PR #38 | `hope-ue/Content/build_content.py` 핀 이름 추측 (P1) | 4주 | 커밋 없음 |
| PR #38 | hope-shooter `src/main.js:445` wall-clip / 4-path dispose (P1) | 4주 | 커밋 없음 |
| PR #38 | Unreal C++ ~2400 LOC 미검증 | 6라운드 | 커밋 없음 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 7일 | main SHA 30일 무변경, 노출창 지속 |
| B9Kxm (29주차) | `cross_form.py:56` BR-14/2100 (P2) | **96h** | 미변경 · §4 |
| B9Kxm (29주차) | `catalog.py:694-696` reserve_shortfall 라벨 (P2) | **96h** | 미변경 · §4 |
| B9Kxm (29주차) | `independent.py:255` `_headline` 키명 (P3) | **96h** | 미변경 · §4 |
| B9Kxm (29주차) | `forms_ext.py:395-396` br_npl tautology (P3) | **96h** | 미변경 · §4 |
| B9Kxm (29주차) | `forms.py:504-506` BR-11 aggregate tautology (P3) | **96h** | 미변경 · §4 |
| B9Kxm (29주차) | `provenance.py:474-484` check_strength_sentence 값 노출 (P3) | **96h** | 미변경 · §4 |
| **B9Kxm (30주차)** | **`test_assumption_claims.py:56-73` 자기충족 grep (P1)** | **72h** | **미변경 · §4** |
| B9Kxm (30주차) | `_LINE_FIELDS` 손 열거 (P2) | 72h | 미변경 · §4 |
| B9Kxm (30주차) | `structure.py` set 검사 사각 (P2) | 72h | 미변경 · §4 |
| B9Kxm (30주차) | `RECALC_SCOPE` citation 규율 불일치 (P2) | 72h | 미변경 · §4 |
| B9Kxm (30주차) | `submission_digest` 기본값 빈 문자열 (P2) | 72h | 미변경 · §4 |
| B9Kxm (30주차) | `test_assumption_claims.py:60` subprocess grep 상대경로 (P3) | 72h | 미변경 · §4 |
| B9Kxm (30주차) | `archive.py:141-155` request_id 원본 강결합 (P3) | 72h | 미변경 · §4 |
| B9Kxm (30주차) | `doc_figures.py:257-273` coverage_report 토큰 분모 오염 (P3) | 72h | 미변경 · §4 |
| B9Kxm (30주차) | `forms.py:895-905` FormSpec `sheet_order` 지문 누락 (P3) | 72h | 미변경 · §4 |
| **Pw9F5 (30주차)** | **`conditional_approval.json` 6차 스냅샷 canonical 점유 (P1)** | **72h** | **미변경 · §4** |
| Pw9F5 (30주차) | `response.json` target 슬롯 오용 재발 (P2) | 72h | 미변경 · §4 |
| Pw9F5 (30주차) | 우편함 3종 dangling (P2) | 72h | 미변경 · §4 |
| Pw9F5 (30주차) | `test_deliverable_location.py` 편향 커버리지 (P2) | 72h | 미변경 · §4 |
| Pw9F5 (30주차) | F-E01 짝 검사 `coverage_sentence` 미확인 통합 (P2) | 72h | 미변경 · §4 |
| Pw9F5 (30주차) | verdict 화이트리스트 `부적합` 누락 (P3) | 72h | 미변경 · §4 |
| Pw9F5 (30주차) | `run_id` 하드코딩 (P3) | 72h | 미변경 · §4 |
| Pw9F5 (30주차) | CHG-0160 컴포넌트 조합 (P3) | 72h | 미변경 · §4 |
| Pw9F5 (30주차) | F-E02 "안전장치 하나 더" 근거 부재 (P3) | 72h | 미변경 · §4 |

**총 tracked LIVE:** P0 = **8** · P1 = **7** · P2 = **16** (신규 P2 1건 포함) · P3 = **19** — 도합 **50건**.

---

## 7. 다음 라운드 (33주차) 권고

**즉시 (24h):**
1. **PR #46 `render.js:597, 601, 606` 3줄 → `out.push`** — **5주째 미이행 · external escalation 검토 조건 지속**. 인간 결재 · policy 조정 병행.
2. **PR #10 동물 sub-mesh 지오메트리·재질 공유화** — R8 확장 이후 dispose 4경로 부재의 결과가 2.2배 확대. `EYE_WHITE`/`EYE_BLACK` 처럼 나머지 sub-mesh 지오메트리도 모듈 상수 승격 (약 20줄). 또는 mergeToGeometry (line 2425) 로 병합.
3. B9Kxm `tests/test_assumption_claims.py:56-73` 자기충족 grep 시정 (30주차 P1-NEW #1, ast 기반 권장) — **72h 미이행 상태 지속, 다음 라운드 P0 격상 검토** (활동 재개 조건부).
4. Pw9F5 `conditional_approval.json` · `approval.md` 파일명 회차·IVR 접미사 (30주차 P1-NEW #2) — **72h 미이행 상태 지속, 다음 라운드 P0 격상 검토** (활동 재개 조건부).

**단주기 (1주):**
5. PR #10 동물 재질 per-instance jitter → 종별 재질 캐시 도입 (§3-B, 30일 미이행 시 P1 격상 검토).
6. B9Kxm `RECALC_SCOPE` citation F-C02 정합 (30주차 P2-NEW #3, 1분 편집).
7. B9Kxm/Pw9F5 30주차 P2×8 + P3×8 시정.
8. `AIMS_POLICY.md` / Pw9F5 대칭 문서에 "agent-team internal branches" 조항 명문화 (§4, **6주 연속** 재권고).
9. PR #46 dead-store lint (`no-unused-expressions`) 도입 (28·29·30·31·32 주차 반복 권고).

**기한 초과 (미이행 시 다음 라운드 격상):**
10. PR #5 Basel · SRISK · CoVaR (P0, **16주**).
11. PR #4 CHG-0143 + ERRATA (P0, **12주**).
12. PR #10 warden 벽투과 sonic LOS (P1, **11주**).
13. PR #38 `build_content.py` 핀 검증 (P1, 4주).
14. PR #43 `.claude/settings.json` commit SHA 핀 1줄 (P1, 7일).
15. PR #48 hand3d.js P2×2 + P3×3 (3주).
16. B9Kxm 29주차 P2×2 + P3×4 (**96h 미이행**).

**프로세스:**
17. **PR #46 external escalation 실행:** (a) 저자 알림 · (b) draft close / issue 재제기 검토 · (c) warden forcing 함수 (draft 잠금 · auto-close) 정책 논의.
18. **B9Kxm/Pw9F5 활동 재개 여부 다음 라운드 재확인:** 3일 연속 무커밋 (33주차) 확인 시 **정식 tracked-dormant 전환**. 활동 재개 시 30주차 P1×2 격상 사이클 재개.
19. **warden zero-delta / single-PR-delta 프로토콜 성문화:** 31주차 §5 권고 재반복.

---

## 8. 리뷰 방법 (재현 가능성)

- **소스:** `github.com/bbootta/AIops` 모든 branch (`main` = `281d6017`, 30일 무변경).
- **방법:** PR #51 의 truth table 을 baseline 으로 하여 각 branch head SHA 및 committer date 가 2026-07-30 21:11 UTC 이후인지로 delta 판별.
- **표본 검증한 브랜치:**
  - **`origin/claude/minecraft-game-tqv3ii` — HEAD `844fb48b` (2026-07-31 19:59:34 UTC), 신규 커밋 1건 (`3b78788..844fb48b`, 316 add / 105 del, `minecraft/index.html` + `minecraft/README.md`)** — §3 분석 대상.
  - `origin/main` — 커밋 0 (2026-07-01 이후)
  - `origin/claude/risk-management-agent-harness-B9Kxm` — HEAD `553a4a8` 정지 (56h 무커밋)
  - `origin/claude/validation-team-agent-Pw9F5` — HEAD `59032de` 정지 (57h 무커밋)
  - `origin/claude/nail-simulation-program-i79qef` — HEAD `01fc7cb4` 정지 (102h 무커밋)
  - `origin/claude/3d-shooting-game-khpuk3` · `origin/claude/mecha-chameleon-game-xyiguj` · `origin/claude/iso-42001-agent-compliance-exq9qe` · `origin/claude/skills-plugin-install-nk7ez7` — 커밋 0
  - `origin/claude/quant-validation-agent-qytpk` · `origin/claude/stock-trading-agent-harness-ZuSJc` · `origin/claude/global-harness-enhancement-1v9b78` · `origin/claude/problem-resolution-v9x6c5` · `origin/codex/create-trading-agent-from-tradingagents-github` — 커밋 0
- **PR 신규 여부:** `list_pull_requests` sort=created desc → 첫 6건 (#51, #50, #49, #48, #47, #46) 이 모두 PR #51 (2026-07-30 21:11 UTC) 이하 created_at → **신규 PR 없음** 확정.
- **PR #10 R8 pass 재현:**
  - HEAD SHA 확인: `844fb48bde70c5130536a559ee82af9d5f8ef0d8` ("Polish the graphics across ten passes")
  - Delta stat: 2 files, 316 add / 105 del
  - `minecraft/index.html:1985-2031` 정독 → `makeAnimalMesh` 에 snout/eyes×4/ears×2/tail 신규 sub-mesh 확인 (`^+` diff 확인 완료).
  - `makeVillagerMesh` (line 2223-2252) 는 diff 대상 아님 (기존 apron/nose/brow/arms 유지).
  - dispose 4경로 (line 2165 · 3374 · 2296 · 5457) diff 대상 아님, 상태 유지 확인.
  - shared const 패턴 확인: `EYE_WHITE`/`EYE_BLACK` (line 1990-1991, 신규 · **올바른 공유 패턴**), `bodyMat`/`headMat` (line 1996-1997, per-instance jitter · §3-B).
  - 참조 (올바른 패턴): `SOLDIER_GEO`/`SOLDIER_MAT` (line 2423-2452, 병합 지오메트리 캐시), `ZG_LEG`/`ZG_BODY`/`ZG_HEAD`/`ZG_ARM` (line 2660-2663, 좀비 지오메트리 공유).
- **PR #46 dead-store 재확인:** blob SHA `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` (31주차와 동일) → 상태 재확인 없이 유지 판정.
- **크로스 체크:** B9Kxm/Pw9F5 HEAD SHA 30주차 baseline (`553a4a8` · `59032de`) 그대로 · **파일 트리 전체 무변경** 확정 (SHA 는 파일 트리 전체를 커버).
- **병렬 리뷰 에이전트:** single-PR-delta 라 이번 라운드도 warden 단일 세션이 감시 활동 + PR #10 diff 정독 (691라인) + tracked LIVE 상태 확인 = 3단계 병렬 tool call 로 완료.

---

_본 문서는 리뷰 보고서 전달용. **머지 금지.** 아래 PR body 요약도 동일 내용._
