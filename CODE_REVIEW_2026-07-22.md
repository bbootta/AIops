# 전체 저장소 코드 리뷰 — 2026-07-22 (24주차)

## 요약

지난 라운드 (PR #39, 2026-07-21 21:12 UTC) 이후 ~15h. **감시 13개 PR 중 12개 head SHA 무변경**, **PR #38 1건만 신규 커밋 `3ffdf95`** (2026-07-22 12:39 UTC, 시네마틱 리파인: Reflector 젖은 도로 + 휴머노이드 그림자 + 하늘 노출 조정, +307/-32 lines · +1 벤더 파일).

## 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **0** |
| 신규 P2 | **1** (PR #38 `removeEnemy` 신규 휴머노이드 ~40 mesh dispose 부재, P2-2 스코프 심화) |
| 신규 P3 | **1** (PR #38 Reflector 텍스처 크기 고정 1024, DPR/resize 무반영) |
| Tracked 재확인 | PR #38 P2×3 + P3×3 전건 **신규 커밋에서 미수정**; PR #10 warden 벽투과 **4주 연속 LIVE**, PR #5 P0×3 **10주 연속**, PR #4 ERRATA **7주 연속** 미발행 |

## 이번 라운드 델타 커밋

| PR | 이전 head (PR #39) | 현재 head | 커밋 | 요지 |
|---|---|---|---|---|
| **#38** | `36000ee8` | **`3ffdf95`** | **1** | (`3ffdf95` 2026-07-22 12:39 UTC) Reflector 젖은 아스팔트, 휴머노이드 그림자 재구성 (hips/torso/shoulders/neck/head/hair×11 + 팔·다리 3-segment × 2 + claw 3개), 하늘 exposure 0.92 + bloom threshold 상향, `vendor/reflector.js` (197 lines) 벤더링 |
| 그 외 12개 | 무변경 | — | 0 | PR #2/#3/#4/#5/#6/#7(dirty)/#8(dirty)/#9/#10/#22/#30/#32 head 무커밋 |

**최근 커밋 시각**: PR #38 `3ffdf95` `2026-07-22 12:39:54Z` (~8.5h 전). PR #10 마지막 코드 커밋 `2026-07-20 11:00` (~50h 무커밋). 다른 감시 PR 은 ≥7d 무커밋.

## PR #39 지시사항 이행 현황 — 0/10 이행 · PR #38 신규 커밋에서 P2-1~P2-3, P3-1~P3-3 **미해결**

| PR #39 권고 (24주차 대상) | 이행 여부 |
|---|---|
| 1. PR #38 벽투과 사격 fix (P2-1) — `intersectObjects` 에 `world.children` 포함 | **미이행** — `hope-shooter/index.html:1328` 여전히 `raycaster.intersectObjects(enemyMeshes, false)` |
| 2. PR #38 GPU dispose 추가 (P2-2) — burst/tracer/wisp 3개소 각 2줄 | **미이행** — L1573/1585/1589 여전히 `scene.remove` 만 호출, `.dispose()` 없음 |
| 3. PR #38 window blur 핸들러 (P2-3) — 2줄 | **미이행** — `blur` 이벤트 리스너 부재 (`resize` 만 L1595) |
| 4. PR #10 warden 벽투과 fix 강제 (**4주 연속**) | **미이행** — PR #10 head SHA 무변경 |
| 5. PR #10 `damage()` L2400 주석 갱신 | **미이행** |
| 6. PR #5 corporate B RW=1.00 → 1.50 fix (**10주 연속**) | **미이행** — PR #5 head SHA 무변경 |
| 7. PR #5 SRISK · CoVaR fix (**10주 연속**) | **미이행** |
| 8. PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 (**7주 연속**) | **미이행** |
| 9. PR #22 close (**8주 연속**) | **미이행** |
| 10. PR #2 close (**15주 방치**) | **미이행** |

**이행률 0/10**. PR #38 소유자는 신규 커밋을 발행했으나 PR #39 지시 6건 (P2×3 + P3×3) 을 모두 우회하고 시각 리파인만 반영.

## 이번 라운드 신규 P0 · 0건

## 이번 라운드 신규 P1 · 0건

## 이번 라운드 신규 P2 · 1건

### 2-1. PR #38 `removeEnemy` — 휴머노이드 재구성으로 dispose 부재 심각도 급증 (P2-2 스코프 심화)

**`hope-shooter/index.html:1060-1069`**:

```javascript
function removeEnemy(e) {
  scene.remove(e);
  enemies.splice(enemies.indexOf(e), 1);
  e.traverse((m) => {
    if (m.isMesh) {
      const i = enemyMeshes.indexOf(m);
      if (i >= 0) enemyMeshes.splice(i, 1);
    }
  });
}
```

**증상**: `3ffdf95` 이후 `makeShadowCreature()` (L974-1042) 는 크리처 하나당 다음 mesh 를 생성:
- 상반신: hips · torso · shoulders yoke · shL/shR (2 sphere) · neck · head **= 7 mesh**
- hair: 11 × Cone **= 11 mesh**
- 팔 × 2 (`makeLimb` isLeg=false, L943): upper Cylinder + joint Sphere + lower Cylinder + hand Box + claw Cone × 3 **= 7 mesh × 2 = 14 mesh**
- 다리 × 2 (`makeLimb` isLeg=true): upper + joint + lower + foot Box **= 4 mesh × 2 = 8 mesh**
- aura Sprite **= 1 mesh**

**총 ~41 mesh × 1 cloned Material (`shadowMat.clone()` L976) per creature**. `removeEnemy` 는 `scene.remove(e)` 만 호출, 자식 mesh 의 `geometry.dispose()` / cloned material `dispose()` 미호출.

- 웨이브 스케일링: `state.pending = 4 + state.wave * 2` (L1361) → wave 10 = 24 kill 파, wave 20 = 44 kill 파. 세션 20-30분 = 200-400 kill = **8,200~16,400 leaked geometry + 200~400 orphan MeshLambertMaterial**.
- 각 geometry 는 vertex Float32Array (~40-200 B) + GPU vertex buffer 참조. `MeshLambertMaterial` 인스턴스는 uniform state + shader program 참조.
- Three.js 표준: `mesh.geometry.dispose(); mesh.material.dispose();` per removed mesh.

**fix (7줄)**:
```javascript
function removeEnemy(e) {
  scene.remove(e);
  enemies.splice(enemies.indexOf(e), 1);
  e.traverse((m) => {
    if (m.isMesh) {
      const i = enemyMeshes.indexOf(m);
      if (i >= 0) enemyMeshes.splice(i, 1);
      m.geometry.dispose();
    }
    if (m.material && m.material.dispose && !m.material._sharedTex) m.material.dispose();
  });
}
```

또는 재사용 관점에서 `makeLimb`/`makeShadowCreature` 를 공유 geometry pool 로 리팩터링 (한 번 만들고 `Mesh` 인스턴스만 생성). 후자가 근본 해결.

**우선순위 P2**: P2-2 (particles/tracers/wisps) 와 동일 패턴이나, 크리처 kill 은 웨이브 필수 이벤트로 회피 불가 → 세션 길이 · 웨이브 진행에 비례해 리크 규모가 particles 대비 자릿수 큼. `3ffdf95` 이전 크리처 (단순 실루엣) 도 leak 하고 있었으나, 이번 커밋에서 sub-mesh 40배 증가로 **동일 코드가 잠재 P3 에서 실효 P2 로 재분류**.

**연계 지시 (P2-2 fix 시 함께)**: 크리처·파티클·트레이서·위습 4개 경로 dispose 를 하나의 커밋으로 처리.

## 이번 라운드 신규 P3 · 1건

### 3-1. PR #38 `Reflector` 텍스처 해상도 1024 고정 — DPR/resize 무반영

**`hope-shooter/index.html:496-502`**:

```javascript
const roadReflector = new THREE.Reflector(
  new THREE.PlaneGeometry(STREET_WIDTH, STREET_LENGTH + 40),
  { textureWidth: 1024, textureHeight: 1024, color: 0x30302b }
);
```

**증상**: `textureWidth`/`textureHeight` 는 초기화 시 1024 로 고정. `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))` (L149) 은 반영되지 않음.

- **고DPR 디스플레이 (Retina, 4K)**: 화면 세로 해상도 2000+px 대비 반사 텍스처 1024px → 반사 이미지 blurry, 몰입감 저하.
- **저사양 모바일** (DPR 1, 뷰포트 360×640): 1024×1024 반사 텍스처가 오히려 오버킬 — GPU 대역폭 낭비.
- **resize 미갱신**: 사용자가 브라우저 창을 확대/축소해도 반사 텍스처 해상도는 초기 값 유지 (P3-2 resize `setPixelRatio` 누락과 동일 패턴이 신규 자산에도 적용됨).

**fix (2줄)**: 해상도를 뷰포트에 연동
```javascript
const rtRes = Math.min(1024, Math.round(window.innerWidth * Math.min(devicePixelRatio, 2) * 0.6));
// ...{ textureWidth: rtRes, textureHeight: rtRes, ... }
// resize 콜백:
roadReflector.getRenderTarget().setSize(newRtRes, newRtRes);
```

또는 `Reflector` 를 삭제 후 재생성 (단순하나 렌더패스 재컴파일 비용).

**우선순위 P3**: 시각 품질만 영향, 게임 로직 무결성 유지. 현 `state.firing`/blur 등 P2 대비 낮은 우선순위.

## Tracked LIVE 재확인 (PR #38 신규 커밋에서 미수정 · 12 PR head SHA 무변경)

### PR #38 P2×3 + P3×3 — 신규 커밋 `3ffdf95` 에서 전건 미수정

| 이전 finding (PR #39) | 현재 상태 | 코드 위치 |
|---|---|---|
| P2-1 벽 관통 사격 (raycast LOS 부재) | **LIVE** | `hope-shooter/index.html:1328` `intersectObjects(enemyMeshes, false)` |
| P2-2 burst/tracer/wisp GPU dispose | **LIVE** | L1573/1585/1589 `scene.remove(...)` 만 |
| P2-3 window blur 시 이동키 stuck | **LIVE** | `blur` 이벤트 리스너 부재 |
| P3-1 빈 탄창 `state.firing = false` 강제 | **LIVE** | L1309 |
| P3-2 resize `setPixelRatio` 미갱신 | **LIVE** | L1595-1600 `renderer.setSize` 만 |
| P3-3 `pointerlockerror` 무처리 | **LIVE** | 리스너 부재 |

### PR #10 warden sonic 벽투과 — **4주 연속 LIVE**

`minecraft/index.html:2014-2026` 무변경 (head `6601e55a` 유지, **50h 무커밋**). PR #36 (21주차) · PR #37 (22주차) · PR #38 신규 커밋에서 저장소 반복 패턴 재확인 (P2-1 동일 로직). 4주 연속 지시 미이행.

### PR #10 `applyPos` NaN 방지 부재 / `blinkTeleport` 0.5-step / `damage()` L2400 주석 stale — LIVE 유지

3건 모두 무변경.

### PR #5 corporate B RW = 1.00 — **10주 연속 LIVE**

`risk_lib/capital/rwa_sa.py:49` `"B": 1.00` 유지. Basel III CRE20 = 1.50 정정 미이행. 1줄 fix 10주 방치.

### PR #5 SRISK `(1-k)` — **10주 연속 LIVE**

`risk_lib/systemic.py:52` 무변경.

### PR #5 CoVaR own-loss mask — **10주 연속 LIVE**

`risk_lib/systemic.py:103` 무변경.

### PR #4 ERRATA-2026-07-14 미발행 — **7주 연속**

`docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 여전히 미존재. R39-R74 오라벨링 shipped 유지.

### PR #4 CHG-0143 재할당 미이행 — **7주 연속**

`report_pack.py` P0/P1 3건 모두 LIVE (`~L3762` cet1 SSoT · `~L3788` Basel Total-cap surcharge · `~L4354` salt 재식별).

## 그 외 tracked LIVE (커밋 무변경 → 자동 유지)

- **PR #2 `stock_trading/harness.py` — 15주 방치**: sticky last_text L210 · run-level sticky APPROVED L82-141 · P0×2 + PARTIAL×2. **close 절차 진입 5주 연속 권고**.
- **PR #3 `quant_validation_team_agent/` — 14주 방치**: 6/15 대응 후 무커밋.
- **PR #6 codex trading agent — 14주 방치**: P1×1 LIVE. close 권고.
- **PR #7 (dirty) — 13+주 방치**: P1×1 + P2×1 LIVE. close 권고.
- **PR #8 (dirty) — 13+주 방치**: P1×1 + P2×1 LIVE. base rebase 필요.
- **PR #9 `risk-research-harness` — 무변화**: P1×1 LIVE + PARTIAL 유지.
- **PR #22 `.claude/skills/` — 12주 방치**: `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md` /code-review chain + auto-commit. **8주 연속 close 권고**.
- **PR #30 `CLAUDE.md §0` + `docs/ISO-42001-AGENT-REQUIREMENTS.md` — 8주 방치**: 소급 조항 부재, CI check 부재.
- **PR #32 `mecha-chameleon/index.html` — 7주 무변화**: `startBtn.blur()` 미도입, tongue CCD 미도입.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#38** | **1** (`3ffdf95` 시각 리파인) | **P2×1 + P3×1** (신규 코드 대상) | 이전 P2×3 + P3×3 **전건 LIVE** (신규 커밋에서 미수정) | 벽투과 사격 · GPU dispose (크리처 포함 4경로) · blur 핸들러 3건 처리 후 mergeable |
| **#32** | 0 | — | P2×2 + P3×3 LIVE (**7주**) | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (**8주 방치**) | **block-merge** (소급 조항 필요) |
| **#10** | 0 | — | tracked LIVE 12 (warden **4주 연속 미수정**) | **block-merge** (warden 관통 해결 후 mergeable) |
| **#5** | 0 | — | P0×3 + P1×1 + P2×2 LIVE (**10주 연속 P0 미수정**) | **block-merge / escalate** |
| **#4** | 0 | — | P0×1 + P1×2 LIVE + FIXED×1 · PARTIAL×3 (**7주 연속 errata 미발행**) | **changes requested + CHG-0143 재할당 강제** |
| **#3** | 0 | — | P1/P2 LIVE (**14주 방치**) | owner 미회신 시 close |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**15주 방치**) | **close 절차 진입** (5주 연속) |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | block-merge |
| **#22** | 0 | — | P0×3 LIVE (**12주 방치**) | **close 즉시 시행** (8주 연속) |
| **#6** | 0 | — | P1×1 LIVE (14주 방치) | close |
| **#7** | 0 (dirty) | — | P1×1 + P2×1 LIVE | close (#8 이 승계) |
| **#8** | 0 (dirty) | — | P1×1 + P2×1 LIVE | base rebase 후 재검토 |

## 누적 24회 결산

|  | #34 | #35 | #36 | #37 | #38(리뷰) | #39(리뷰) | **이번** |
|---|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | 0 | — | 0 | **0** |
| 신규 P1 | 0 | 1 | 1 | 0 | — | 0 | **0** |
| 신규 P2 | 0 | 1 | 0 | 0 | — | 3 | **1** |
| 신규 P3 | 0 | 0 | 0 | 1 | — | 3 | **1** |
| Tracked 재분류 | 0 | 5 | 3 | 0 | — | 0 | **0** |
| 누적 수정 | 8/89 | 8/90 | 8/89 | 8/89 | — | 8/96 | **8/98** (신규 P2×1 + P3×1 = 2건 추가) |

_주: #38(리뷰) 열은 코드 PR 이 아닌 게임 PR — 리뷰 대상. #39(리뷰) 열이 지난 라운드 리뷰._

## 주요 시사점

1. **PR #38 신규 커밋 `3ffdf95` 은 PR #39 지시 6건 (P2×3 + P3×3) 을 모두 우회하고 시각 리파인만 반영** — 지시 이행률 0/6. 소유자가 리뷰 응답 없이 다른 축으로 진행 중. `stoic-ride` 시리즈 리뷰 지시가 PR 소유자 세션에 도달·소화되지 않는 워크플로 결함 재확인 (PR #10 warden 4주 연속 미이행과 동일 패턴).

2. **`removeEnemy` P2 재분류의 근본 원인**: 이전 크리처 구조는 단순 실루엣 (~1-3 mesh) 이라 dispose 부재의 영향이 particles 대비 미미했으나, `3ffdf95` 이후 humanoid 재구성으로 **크리처당 ~41 mesh + cloned material** 로 급증 → 동일 결함 코드가 P3-이하 정보성에서 실효 P2 로 자연 승격. 이는 **레거시 결함이 신규 커밋에 의해 재활성화되는 패턴** — 저장소 차원에서 "무해 판정된 결함" 을 리팩터링 이후 재검증하는 규칙 부재.

3. **Reflector textureWidth 고정 (P3-1) 은 P3-2 (resize setPixelRatio 부재) 와 동일한 "초기값 hardcode + resize 무갱신" 패턴** — 저장소 차원 코딩 관행 이슈. `hope-shooter` 는 3개소 (setPixelRatio · Reflector textureWidth · UnrealBloom Vector2) 가 모두 초기 window 값에 의존.

4. **PR #5 P0×3 (10주) · PR #4 ERRATA (7주) · PR #22 close (8주) · PR #2 close (15주) · PR #30 소급조항 (8주)** — 실행 프로세스 부재 지속. PR #37/#39 시사점과 동일.

5. **감시 12개 PR 전건 무커밋 · 신규 PR 0건 · PR #38 1커밋 (~15h 델타)** — 활동이 PR #38 단일 세션에 국한된 라운드. 커밋 규모 (+307 lines / +1 vendored) 는 평시 수준.

## 다음 라운드 (25주차) 권고

1. **PR #38 `removeEnemy` dispose 추가 (신규 P2-1)** — 7줄, 크리처 · particle · tracer · wisp 4경로 통합 처리.
2. **PR #38 벽투과 사격 fix (P2-1 tracked, 2주 연속)** — `intersectObjects` 에 `world.children` 추가.
3. **PR #38 GPU dispose particles/tracers/wisps (P2-2 tracked, 2주 연속)** — 3개소 각 2줄.
4. **PR #38 window blur 핸들러 (P2-3 tracked, 2주 연속)** — 2줄.
5. **PR #38 Reflector textureWidth 반응형 (신규 P3-1)** — 2줄.
6. **PR #10 warden 벽투과 fix 강제 (5주째)** — `hasLineOfSight()` 체크 추가. PR #38 벽투과와 동일 패턴 동시 fix.
7. **PR #10 `damage()` L2400 주석 갱신** (1줄, 위더 스톰 80% 반영).
8. **PR #5 corporate B RW = 1.00 → 1.50 fix 강제 (10주 연속)** — 1줄 `risk_lib/capital/rwa_sa.py:49`.
9. **PR #5 SRISK · CoVaR fix (10주)** — `systemic.py:52`/`:103`.
10. **PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 발행 강제 (7주 연속)**.
11. **PR #22 close 시행 (8주 연속)**.
12. **PR #2 close 시행 (15주 방치)**.
13. **PR #7 close, #8 base rebase**.

## 리뷰 방식

**메인 스레드 단일 세션, PR #38 신규 커밋 `3ffdf95` 전문 실측 + 12개 감시 PR head SHA 대조**:

- 13개 감시 PR head SHA 대조 → **12개 무변경**, **1개 신규 커밋 (PR #38 `3ffdf95`)** 확인. `list_pull_requests state=all perPage=20` → 페이지 1 max=#39 (2026-07-21 리뷰 PR) → 코드 PR 신규 0건, PR #38 만 커밋 활동.
- **PR #38 `hope-shooter/index.html` 1607 lines 전문 실측 read** (이전 1528 → +79 lines):
  - `THREE.Reflector` 신설 (L496-502) → **textureWidth 1024 고정 · resize 미갱신 → P3-1 신규**.
  - `makeShadowCreature` (L974-1042) + `makeLimb` (L943-972) 재구성 → **~41 mesh/creature, `removeEnemy` L1060-1069 dispose 부재 → P2-1 신규 (P2-2 스코프 심화)**.
  - Raycast (L1328) → 여전히 `enemyMeshes` 만 → **P2-1 (PR #39) LIVE**.
  - burst/tracer/wisp 소멸 (L1573/1585/1589) → `.dispose()` 미호출 → **P2-2 (PR #39) LIVE**.
  - keydown/keyup + resize (L1289-1290, L1595-1600) → blur/setPixelRatio 부재 → **P2-3/P3-2 (PR #39) LIVE**.
  - shoot() 빈 탄창 (L1309) → `state.firing = false` 강제 → **P3-1 (PR #39) LIVE**.
  - pointerlock → `pointerlockerror` 무처리 → **P3-3 (PR #39) LIVE**.
- **PR #2/#3/#4/#5/#6/#7/#8/#9/#10/#22/#30/#32 head SHA 무변경** → 자동 LIVE 유지 (실측 재검증 생략, PR #39 실측 재활용).

**단독 리뷰어 (에이전트 배정 없음), 저-중 위험도 라운드**. PR #38 델타 커밋이 시각 축에 국한되어 로직 표면 노출 최소, P0/P1 미발견. 그러나 **레거시 dispose 결함이 sub-mesh 40배 증가로 P3→P2 자연 승격**한 사례로 기록.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
