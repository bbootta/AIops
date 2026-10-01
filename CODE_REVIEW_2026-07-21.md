# 전체 저장소 코드 리뷰 — 2026-07-21 (23주차)

## 요약

지난 라운드 (PR #37, 2026-07-20 21:10 UTC) 이후 ~24h. **감시 12개 PR 전건 head SHA 무변경**. 신규 PR **1건** — PR #38 (`hope-shooter/index.html` 3D FPS 게임, +2606 lines / 3 files).

- **신규 P0** — 0건.
- **신규 P1** — 0건.
- **신규 P2** — 3건 (전건 PR #38: 벽 관통 사격 · GPU 리소스 미해제 · window blur 시 이동키 스탠딩).
- **신규 P3** — 3건 (PR #38: 빈 탄창 클릭시 firing 리셋 · resize 시 setPixelRatio 미갱신 · pointerlockerror 무처리).
- **Tracked 재확인** — 12개 감시 PR 전건 무커밋 → 이전 findings **자동 LIVE 유지**. PR #10 warden 벽투과 **3주 연속 미이행**, PR #5 P0×3 **9주 연속**, PR #4 ERRATA **6주 연속** 미발행.

## 이번 라운드 델타 커밋

| PR | 이전 head (PR #37) | 현재 head | 커밋 | 요지 |
|---|---|---|---|---|
| **#38** | 신규 | **`36000ee8`** | **2** | (1) `d15af336` Three.js r128 기반 FPS 초기 구현 (WASD + 포인터락 마우스 · 웨이브 · WebAudio · 절차적 캔버스 텍스처) · (2) `36000ee8` ACES 톤매핑 + UnrealBloom + 필름 그레인/비네트, M16A1 뷰모델, 그림자 크리처 스모크 위습 등 시네마틱 오버홀 |
| 그 외 12개 | 무변경 | — | 0 | PR #2/#3/#4/#5/#6/#7(dirty)/#8(dirty)/#9/#10/#22/#30/#32 head 무커밋 |

**최근 커밋 시각**: PR #38 `36000ee8` `2026-07-21 03:41:35Z` (~18h 전). PR #10 마지막 코드 커밋 `2026-07-20 11:00` (~34h 무커밋으로 카운터 롤오버). 다른 감시 PR 은 ≥4d 무커밋.

## 이번 라운드 신규 P0 · 0건

## 이번 라운드 신규 P1 · 0건

PR #38 최초 리뷰에서 P1 미발견 사유:

- **핵심 게임 루프 (input → shoot → collide → wave)** 가 단일 파일 1528 lines 안에서 명료히 분리됨. `state` 오브젝트 단일 SoT, `animate()` 하나에 통합 dispatch.
- **`state.reloading` / `state.firing` / `state.over` / `state.running` 4-flag 상호배제 로직**이 shoot(L1231), animate 사격 게이트(L1385), pointerlock 핸들러(L1191), gameOver(L1301) 4곳에서 일관 처리 — 재현 가능한 데드락/leak 시나리오 미발견.
- **웨이브 grace `setTimeout(2200)` (L1427)** 이 이론적으로 `state.over` 스탈 참조 위험이 있으나, **enemies.length === 0 게이트가 wave 종료 순간까지 살아있는 적 존재를 배제** 하여 재현 조건 (동일 프레임 죽음+웨이브클리어) 이 실제로 발생 불가능. 이론적 race 로만 남음 (P3 하단).

## 이번 라운드 신규 P2 · 3건

### 2-1. PR #38 총알이 벽·차량·잔해를 관통 — Raycast LOS 체크 부재

**`hope-shooter/index.html:1250`**:

```javascript
raycaster.set(camera.position, dir);
raycaster.far = 200;
const hits = raycaster.intersectObjects(enemyMeshes, false);
```

**증상**: raycast 대상이 `enemyMeshes` 만 — 건물 `world` / 자동차 `obstacles` / 잔해가 `intersectObjects` 인자에 포함되지 않음. **폐허 상가 벽 · 세단 지붕 · collapsed lot 슬래브 뒤에 있는 그림자 크리처를 그대로 저격 가능**.

- 세단 4대: z = -26 / -58 / -95 / -140, 지붕고 1.66m (`car` 그룹, L708 roof). 크리처 키 2.32m 이지만 몸통·다리 상당 부분이 세단 뒤로 은폐되는 각도 존재.
- 자동차 `obstacles.push({ minX, maxX, minZ, maxZ, ... })` 는 **player collision 전용** (L731) — 사격 판정에는 미참여.
- 크리처는 반대로 건물·차량을 통과해 플레이어에 다가옴 (L1464 `e.position.add(tmpV)` 무필터). **양방향 관통**으로, PR #10 warden 벽투과 (3주 연속 LIVE) 와 정확히 동일 패턴.

**fix**: `intersectObjects` 대상에 `[...enemyMeshes, ...world.children]` 를 합치거나, 별도 `world.raycast` 로 먼저 벽 거리 계산 후 enemy hit distance 와 비교. `world` 자식 순회는 60여 개 mesh 로 성능 문제 없음.

**우선순위 P2**: 게임 계약 (은폐/엄폐) 파괴이나, 스토리 상 "그림자" 크리처의 초자연적 성격으로 해석 여지 있음 — 그러나 플레이어→적 사격도 관통은 명백한 exploit.

### 2-2. PR #38 파티클/트레이서/위습 GPU 리소스 미해제 — 장시간 세션 메모리 누적

**`hope-shooter/index.html:995-1015 / 1018-1026 / 913-927`**:

```javascript
function burst(pos, color, n, speed) {
  const geo = new THREE.BufferGeometry();
  ...
  const mat = new THREE.PointsMaterial({ color, size: 0.09, ... });
  const pts = new THREE.Points(geo, mat);
  ...
}
// 소멸 시 (L1507):
if (p.userData.life <= 0) { scene.remove(p); particles.splice(particles.indexOf(p), 1); }
```

**증상**: `burst()` 는 shot 당 매번 새 `BufferGeometry` + `PointsMaterial` 생성. 소멸 시 `scene.remove` 만 호출, `.dispose()` 미호출 → **WebGL context 의 GPU 버퍼 / 텍스처 참조가 lingering**. `tracer()` (LineBasicMaterial), `shedWisp()` (SpriteMaterial) 모두 동일.

- FIRE_INTERVAL = 0.11s → 최대 ~9 shots/sec. `burst` 는 shot 당 1회 + hit 당 1회 → 사격 세션 20분 = 약 10,800 `Points` 객체.
- Three.js 표준 관행: `scene.remove(obj); obj.geometry.dispose(); obj.material.dispose();` 순서 필수.
- Chrome DevTools Memory > Heap snapshot 에서 `Float32Array` (position buffer, 유닛 크기 ~200 B) 및 material internal refs 가 누적 관측 가능.

**fix (3줄 × 3개소)**: 각 소멸 분기에 `p.geometry.dispose(); p.material.dispose();` 추가. `wisps` / `tracers` 동일 처리.

**우선순위 P2**: 15-20분 이내 세션에서는 체감 어렵지만, 웨이브 스케일링 (`hp = 3 + Math.floor(wave/2)`, `speed = ... * (1 + wave*0.07)`) 상 40분+ 세션이 자연스러운 게임 → 누적 시 프레임 드랍/OOM 리스크.

### 2-3. PR #38 window blur 시 이동키 상태 유지 — alt-tab 복귀 후 자동 이동

**`hope-shooter/index.html:1211-1215`**:

```javascript
document.addEventListener('keydown', (e) => {
  state.keys[e.code] = true;
  if (e.code === 'KeyR') tryReload();
});
document.addEventListener('keyup', (e) => { state.keys[e.code] = false; });
```

**증상**: `W` 를 누른 채 `Alt+Tab` 으로 다른 창에 포커스 → 브라우저 밖에서 `W` 릴리스 → keyup 이벤트가 문서에 도달하지 않음 → `state.keys['KeyW'] === true` 유지. 사용자가 탭에 돌아오면 pointer-lock 해제로 오버레이 표시, "작 전 재 개" 클릭 → **release 하지 않은 W 로 즉시 전진 시작**. 사용자는 마우스 클릭이 전진 시작 트리거로 오인.

- 동일 문제로 `state.firing` 은 `mousedown` 시 true → alt-tab 중 mouseup 이 밖에서 발생 → 복귀 시 자동 연사.

**fix (2줄)**: 
```javascript
window.addEventListener('blur', () => { state.keys = {}; state.firing = false; });
```

**우선순위 P2**: 재현이 100% 명확하고, FPS 표준 사례. `pointerlockchange` 는 pointer lock 만 다루므로 blur 대체 불가.

## 이번 라운드 신규 P3 · 3건

### 3-1. PR #38 빈 탄창 클릭 시 `state.firing = false` 강제 — 재장전 후 재클릭 필요

**`hope-shooter/index.html:1231`**:

```javascript
function shoot() {
  if (state.ammo === 0) { playClick(180); state.firing = false; tryReload(); return; }
```

**증상**: 사용자가 마우스를 눌러 연사 중 탄창이 소진되면 `firing = false` 로 리셋 → 재장전 완료 후에도 firing = false → 사용자가 마우스를 놓았다가 다시 눌러야 사격 재개. FPS 관례상 many titles 는 마우스 홀드 상태를 유지하여 자동 재개.

**fix**: `state.firing = false` 라인 제거. `state.firing` 은 mouseup 이벤트로만 리셋.

**우선순위 P3**: UX 불편, 순수 논리 결함 아님.

### 3-2. PR #38 resize 핸들러가 `renderer.setPixelRatio` 미갱신

**`hope-shooter/index.html:1517-1522`**:

```javascript
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});
```

**증상**: 브라우저를 저해상도 모니터 → 고DPR 모니터로 드래그 이동 시 `devicePixelRatio` 가 변경되지만, 초기 `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))` (L148) 는 재실행되지 않음 → 렌더 해상도가 새 모니터에 맞지 않아 blurry.

**fix (1줄)**: resize 콜백에 `renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));` 추가.

**우선순위 P3**: 흔치 않은 사용 케이스, 시각 열화만.

### 3-3. PR #38 `pointerlockerror` 이벤트 미처리 — 실패 시 silent

**`hope-shooter/index.html:1188`**:

```javascript
canvas.requestPointerLock();
```

브라우저가 pointer lock 을 거부 (샌드박스 iframe, 사용자 사전 거부 등) 시 `pointerlockerror` 가 발생하지만 handler 없음 → 사용자는 "작 전 개 시" 를 눌러도 마우스가 자유롭게 유지되어 게임이 진행되지 않는 원인을 알 수 없음.

**fix (3줄)**: 
```javascript
document.addEventListener('pointerlockerror', () => {
  alert('마우스 잠금이 거부되었습니다. 브라우저 설정 확인 후 재시도하세요.');
  state.running = false;
});
```

**우선순위 P3**: edge case, mainstream 브라우저에서 정상 동작.

## 이번 라운드 참고 (P3 미만, 정보성 1건)

### PR #38 웨이브 grace `setTimeout(2200)` 이론적 race — 실제 재현 불가능

**`hope-shooter/index.html:1427`**:

```javascript
setTimeout(() => { if (!state.over) nextWave(); }, 2200);
```

`state.pending = -1` grace 진입 후 `state.over` 만 체크하고 `state.running` 미체크, 그리고 timeout ID 를 저장하지 않아 `resetGame()` 시 clear 불가. **이론적으로**: 플레이어가 grace 중 사망 → 즉시 재투입 → 이전 timeout 이 뒤늦게 fire → wave counter 가 이중 증가.

**실측**: grace 진입 조건은 `enemies.length === 0` — 이 시점에 남은 적이 없어 플레이어를 공격할 소스 부재. 따라서 grace period 중 플레이어 사망 재현 경로 미발견 (환경 데미지·낙사·시간 감쇠 무존재).

**분류**: 실제 발현 불가능한 이론 결함으로, **P3 미만 정보성** 기록. 방어적 코드로 timeout ID 저장 후 `resetGame()`/`gameOver()` 에서 `clearTimeout` 추가 권장 (2줄).

## Tracked LIVE 재확인 (전건 head SHA 무변경으로 자동 유지)

### PR #10 warden sonic 벽투과 — **3주 연속 LIVE (PR #37 지시 미이행)**

`minecraft/index.html:2014-2026` 무변경 (head `6601e55a` 유지, 34h+ 무커밋). PR #36 (21주차) · PR #37 (22주차) 지시 반복 미이행. **PR #38 (신규 FPS) 의 벽 관통 사격 P2-1 과 동일 패턴**이 저장소 전체에 재현되고 있음을 인지.

### PR #10 `applyPos` NaN 방지 부재 / `blinkTeleport` 0.5-step / `damage()` L2400 주석 stale — LIVE 유지

3건 모두 무변경.

### PR #5 corporate B RW = 1.00 — **9주 연속 LIVE**

`risk_lib/capital/rwa_sa.py:49` `"B": 1.00` 유지. Basel III CRE20 = 1.50 정정 미이행. 1줄 fix 9주 방치.

### PR #5 SRISK `(1-k)` — **9주 연속 LIVE**

`risk_lib/systemic.py:52` 무변경.

### PR #5 CoVaR own-loss mask — **9주 연속 LIVE**

`risk_lib/systemic.py:103` 무변경.

### PR #4 ERRATA-2026-07-14 미발행 — **6주 연속**

`docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 여전히 미존재. R39-R74 오라벨링 shipped 유지.

### PR #4 CHG-0143 재할당 미이행 — **6주 연속**

`report_pack.py` P0/P1 3건 모두 LIVE (`~L3762` cet1 SSoT · `~L3788` Basel Total-cap surcharge · `~L4354` salt 재식별).

## 그 외 tracked LIVE (커밋 무변경 → 자동 유지)

- **PR #2 `stock_trading/harness.py` — 14주 방치**: sticky last_text L210 · run-level sticky APPROVED L82-141 · P0×2 + PARTIAL×2. **close 절차 진입 4주 연속 권고**.
- **PR #3 `quant_validation_team_agent/` — 13주 방치**: 6/15 대응 후 무커밋.
- **PR #6 codex trading agent — 13주 방치**: P1×1 LIVE. close 권고.
- **PR #7 (dirty) — 12+주 방치**: P1×1 + P2×1 LIVE. close 권고.
- **PR #8 (dirty) — 12+주 방치**: P1×1 + P2×1 LIVE. base rebase 필요.
- **PR #9 `risk-research-harness` — 무변화**: P1×1 LIVE + PARTIAL 유지.
- **PR #22 `.claude/skills/` — 11주 방치**: `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md` /code-review chain + auto-commit. **7주 연속 close 권고**.
- **PR #30 `CLAUDE.md §0` + `docs/ISO-42001-AGENT-REQUIREMENTS.md` — 7주 방치**: 소급 조항 부재, CI check 부재.
- **PR #32 `mecha-chameleon/index.html` — 6주 무변화**: `startBtn.blur()` 미도입, tongue CCD 미도입.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#38** | **2** (초기 구현 + 시네마틱 오버홀) | **P2×3 + P3×3** (초회 리뷰) | — | 벽투과 사격 fix + GPU dispose + blur 핸들러 3건 처리 후 mergeable |
| **#32** | 0 | — | P2×2 + P3×3 LIVE (**6주**) | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (**7주 방치**) | **block-merge** (소급 조항 필요) |
| **#10** | 0 | — | tracked LIVE 12 (warden **3주 연속 미수정**) | **block-merge** (warden 관통 해결 후 mergeable) |
| **#5** | 0 | — | P0×3 + P1×1 + P2×2 LIVE (**9주 연속 P0 미수정**) | **block-merge / escalate** |
| **#4** | 0 | — | P0×1 + P1×2 LIVE + FIXED×1 · PARTIAL×3 (**6주 연속 errata 미발행**) | **changes requested + CHG-0143 재할당 강제** |
| **#3** | 0 | — | P1/P2 LIVE (**13주 방치**) | owner 미회신 시 close |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**14주 방치**) | **close 절차 진입** (4주 연속) |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | block-merge |
| **#22** | 0 | — | P0×3 LIVE (**11주 방치**) | **close 즉시 시행** (7주 연속) |
| **#6** | 0 | — | P1×1 LIVE (13주 방치) | close |
| **#7** | 0 (dirty) | — | P1×1 + P2×1 LIVE | close (#8 이 승계) |
| **#8** | 0 (dirty) | — | P1×1 + P2×1 LIVE | base rebase 후 재검토 |

## 누적 23회 결산

|  | #33 | #34 | #35 | #36 | #37 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | 0 | 0 | **0** |
| 신규 P1 | 1 | 0 | 1 | 1 | 0 | **0** |
| 신규 P2 | 3 | 0 | 1 | 0 | 0 | **3** |
| 신규 P3 | 4 | 0 | 0 | 0 | 1 | **3** |
| Tracked 재분류 | 2 | 0 | 5 | 3 | 0 | **0** |
| 누적 수정 | 8/89 | 8/89 | 8+/90 | 8/89 | 8/89 | **8/90+6=8/96** (신규 P2×3 + P3×3 총 6건 추가) |

## 주요 시사점

1. **PR #38 (신규 FPS) 가 PR #10 (Minecraft) 의 벽투과 패턴을 그대로 재현** — Raycast LOS 미체크가 저장소 전체를 관통하는 반복 패턴. `intersectObjects(enemyMeshes)` 만 사용 (L1250) — 벽·차량·잔해 미포함. PR #10 warden sonic (3주 연속 LIVE) · PR #38 rifle raycast 모두 동일한 "적 대상만 판정" 로직 → **저장소 차원 코딩 컨벤션 리뷰 필요**.

2. **PR #38 초기 리뷰에서 P0/P1 미발견은 단일 파일 · 단일 state SoT · 명시적 flag 관리의 산물** — 1528 lines 게임 로직이 하나의 `state` 오브젝트 + 하나의 `animate()` 를 축으로 정렬되어 상호배제가 표면화됨. 이는 PR #10 (4414 lines) 대비 리뷰 가능성이 높은 구조.

3. **GPU 리소스 미해제 (P2-2)** 는 Three.js 표준 관행 미준수 사례. PR #10 도 유사한 우려가 있으나 명시 tracked 되지 않음 — 다음 라운드에서 PR #10 도 spot-check 권장.

4. **PR #5 P0×3 (**9주**) · PR #4 ERRATA (**6주**) · PR #22 close (**7주**) · PR #2 close (**14주**) · PR #30 소급조항 (**7주**)** — 실행 프로세스 부재 지속. PR #37 시사점과 동일.

5. **감시 12개 PR 전건 무커밋 · 신규 PR 1건 (초기)** — 활동이 PR #38 신규 세션에 집중된 라운드. 24h 델타이나 PR #38 이 대형 신규 (2606 lines) 로 실질 리뷰 부하는 평시 수준.

## 다음 라운드 (24주차) 권고

1. **PR #38 벽투과 사격 fix (P2-1)** — `intersectObjects` 에 `world.children` 추가, 벽 hit distance 와 enemy hit distance 비교.
2. **PR #38 GPU dispose 추가 (P2-2)** — burst/tracer/wisp 3개소 각 2줄 (`geometry.dispose(); material.dispose();`).
3. **PR #38 window blur 핸들러 (P2-3)** — 2줄, `state.keys = {}; state.firing = false;`.
4. **PR #10 warden 벽투과 fix 강제 (4주째)** — `hasLineOfSight()` 체크 추가 (raycast/DDA 도구 이미 존재). PR #38 동일 패턴 동시 fix 권장.
5. **PR #10 `damage()` L2400 주석 갱신** (1줄, 위더 스톰 80% 반영 — PR #37 P3 미이행).
6. **PR #5 corporate B RW = 1.00 → 1.50 fix 강제 (9주 연속)** — 1줄 `risk_lib/capital/rwa_sa.py:49`.
7. **PR #5 SRISK · CoVaR fix** — `systemic.py:52` `k·assets` / `systemic.py:103` point mask.
8. **PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 발행 강제 (6주 연속)**.
9. **PR #22 close 시행 (7주 연속)**.
10. **PR #2 close 시행 (14주 방치)**.
11. **PR #7 close, #8 base rebase**.

## 리뷰 방식

**메인 스레드 단일 세션, PR #38 신규 파일 전문 실측 + 12개 감시 PR head SHA 대조**:

- 13개 감시 PR head SHA 대조 → **12개 무변경**, **1개 신규 (PR #38 `36000ee8`)** 확인. `list_pull_requests state=open perPage=100` → 페이지 1 실측 max=#38 (2026-07-21 03:41 UTC) → **신규 PR 1건**.
- **PR #38 3개 파일 fetch** (index.html 1528 lines, three.min.js 6 lines 헤더만, postprocessing.js 1072 lines).
  - `three.min.js` 헤더 확인: Three.js r128 (Copyright 2010-2021) 정상 vendored.
  - `postprocessing.js` 헤더 확인: EffectComposer/RenderPass/ShaderPass/UnrealBloomPass 정상 vendored.
  - `index.html` **1528 lines 전문 실측 read**: 
    - 게임 상태 (`state` L1122-1131) · 입력 (L1199-1215) · 사격 (`shoot` L1230-1276) · 웨이브 (L1281-1288) · 리셋 (L1290-1299) · 콜리전 (L1314-1330) · 메인 루프 (`animate` L1338-1515) 전 구간 검사.
    - Raycast (L1248-1250) → `enemyMeshes` 만 대상 → **P2-1 벽투과 확정**.
    - `burst`/`tracer`/`shedWisp` 소멸 (L1495/1507/1511) → `.dispose()` 미호출 → **P2-2 GPU 누적 확정**.
    - `keydown`/`keyup` (L1211-1215) → `window.blur` 핸들러 부재 → **P2-3 stuck-key 확정**.
    - `shoot()` 빈 탄창 (L1231) → `state.firing = false` 강제 → P3-1.
    - resize (L1517-1522) → `setPixelRatio` 미갱신 → P3-2.
    - pointerlock (L1188) → `pointerlockerror` 무처리 → P3-3.
    - Grace `setTimeout` (L1427) → 이론 race 확인, 재현 조건 부재 → 정보성.
- **PR #2/#3/#4/#5/#6/#7/#8/#9/#10/#22/#30/#32 head SHA 무변경** → 자동 LIVE 유지 (실측 재검증 생략, PR #37 실측 재활용).

**단독 리뷰어 (에이전트 배정 없음), 저-중 위험도 라운드**. PR #38 최초 리뷰라 표면 노출이 높으나 단일 파일 · 명시적 state 로 P0/P1 표면화 없음. 저장소 차원 반복 패턴 (raycast LOS 미체크) 을 PR #10 tracked 와 연결 지시.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
