# 전체 저장소 코드 리뷰 — 28주차 (2026-07-27)

**세션 기준 시각:** 2026-07-27
**직전 리뷰:** PR #47 (2026-07-26 21:15 UTC, 27주차)
**베이스:** `origin/main` = `281d6017` (무변경, 26일 방치)

---

## 1. 감시 활동 요약 (지난 24h)

| 채널 | 델타 | 비고 |
|---|---|---|
| `main` | 커밋 0 | 26일 무변경. `.gitkeep`/`CLAUDE.md`/`.claude/settings.json` 3파일 정지. |
| PR #46 (nail simulator) | **커밋 +3** | `b9fabee6` (nail roll 회전 축 수정) · `445cd9c3` (**신규 3D SDF/WebGL2 렌더러, +817 LOC**) · `01fc7cb4` (2D/3D 실측 손 치수 보정) |
| PR #38 (호프) | 커밋 0 | 헤드 `6f9cfb13` 정지 (~30h). |
| PR #10 (minecraft) | 커밋 0 | 헤드 정지 (~7일). |
| PR #5 (risk_lib) | 커밋 0 | 헤드 정지 (~13주). |
| PR #4 (change mgmt) | 커밋 0 | 헤드 정지 (~9주). |
| PR #43 (settings.json) | 커밋 0 | 헤드 정지 (3일). |
| PR #30, #32, #34~#45 | 커밋 0 | 각 헤드 무커밋. |

**총평:** 실사 델타는 PR #46 한 곳. `445cd9c3` 이 815 LOC 신규 WebGL2/SDF 렌더러 도입으로 이번 라운드 최대 코드 유입원. 그 외 25 PR head 는 무커밋 (`zero-delta`).

---

## 2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| **신규 P0** | **0** |
| **신규 P1** | **0** |
| **신규 P2** | **2** — PR #46 pick() 프레임버퍼 스토리지 매 클릭 재할당 · PR #46 3D 첫 진입 UI 무응답 (수 초 프리즈) |
| **신규 P3** | **3** — PR #46 wheel 이벤트가 페이지 스크롤 트랩 · Blob URL revoke race · pointercancel 미처리 |
| **Regression** | **0** (기존 F-001~F-301 remediation 정합 유지) |
| **Tracked 재확인** | 아래 §4 참조 |
| **⚠ 특기** | **PR #47 P1 (render.js `g.push` 사후-join 누락) — 1주 미이행. 27주 “3줄 fix” 지시에도 불구 헤드에 그대로 잔존.** |

---

## 3. 신규 P2 (delta 원인 PR #46)

### [P2-NEW] PR #46 — 3D 첫 진입 시 UI 무응답 (~수 초 프리즈)

**위치:** `js/hand3d.js:361-365` (`buildHand()`) → `:265-320` (`surfaceNets`) → `:234-255` (`field`) + `:347-359` (`fieldNormals`)

**경로 분석:**
- `surfaceNets([-8.9,-8.6,-2.3], [5.3,14.6,2.1], 0.13)` → 격자 셀 약 `110 × 179 × 34 ≈ 669k`. 각 셀에서 `field()` 1회 호출.
- `field()` 는 5개 손가락 LIMB 순회 × 손가락당 ~14 캡슐 세그먼트 = 최대 ~70 `segZ` 호출 (경계 상자로 상당 부분 걸러짐). 그래도 격자 총량과 곱해지면 수십 M 산술.
- 뒤이어 `fieldNormals` 는 정점마다 `field()` 를 6회(중심차분) 호출. 수천~수만 정점 × 6 → 추가 수 M 호출.
- 전량 **동기 메인스레드**. `NS.hand3d.init` → `upload(buildHand())` 이 반환할 때까지 렌더/이벤트 루프 정지.

**증상:** 사용자가 `[3D]` 토글을 처음 눌렀을 때 브라우저 이벤트 루프가 수 초 정지. 아무 진행 표시 없음. `bindInput()` 도 그 시점까진 미등록이라 취소 불가.

**커밋 본문 자백은 렌더 프레임 비용만 언급:** *"브라우저 렌더 12.5ms/프레임(레이아웃 포함) — 슬라이더 드래그에 충분"* — 이는 build 후 draw 비용이고, **초기 build 비용은 측정치 없음**.

**Fix 옵션 (택 1):**
1. `buildHand()` 결과를 빌드 타임에 사전계산 → `js/hand-mesh.js` 정적 임베드 (형상이 하드코딩된 상수 `FINGERS`/`SPINES`/`ZFLAT` 만 쓰므로 사전계산 가능).
2. `requestIdleCallback` / `setTimeout` chunking 으로 셀 순회 분할 + 진행률 표시.
3. `OffscreenCanvas` + Worker 로 build 격리.

**우선순위:** P2 — 정확성/보안 결함은 아니나 **첫 인상 UX 파손** (사용자가 잘못된 것으로 판단해 재로드하면 매번 재빌드).

---

### [P2-NEW] PR #46 — `pick()` 매 클릭 시 텍스처·렌더버퍼 스토리지 재할당

**위치:** `js/hand3d.js:770-806` (`pick`), 특히 `:773-778`

```js
gl.bindTexture(gl.TEXTURE_2D, pickTex);
gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, size[0], size[1], 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
gl.bindRenderbuffer(gl.RENDERBUFFER, pickRB);
gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, size[0], size[1]);
```

`texImage2D` (new storage + upload) 과 `renderbufferStorage` (new storage) 는 **캔버스 크기 변경 시에만** 필요. 매 클릭마다 다시 호출하면 GPU 할당·해제 반복 → 파편화 · 드라이버 stall 위험.

**실측 규모:** 800×600 캔버스 · devicePixelRatio=2 → `1600×1200×4 = ~7.5MB` texture + `1600×1200×2 = ~3.75MB` renderbuffer 를 클릭마다 재할당.

**Fix:** `pickTex`/`pickRB` 크기를 캐시하고 `size[0]!==cachedW || size[1]!==cachedH` 일 때만 재할당. `resize()` 훅 안에서 갱신하면 pick 경로는 texParameteri 만 재적용해도 됨 (실제로 파라미터는 첫 회에만 필요).

**우선순위:** P2 — 성능 저하 실측 가능 (특히 저사양 GPU / 통합 그래픽).

---

## 4. 신규 P3 (PR #46)

### [P3-NEW #1] `js/hand3d.js:672-676` — wheel 이벤트가 페이지 스크롤을 무조건 트랩

```js
canvas.addEventListener('wheel', function (e) {
  e.preventDefault();
  orbit.dist = Math.max(12, Math.min(60, orbit.dist * (1 + Math.sign(e.deltaY) * 0.09)));
  if (redraw) redraw();
}, { passive: false });
```

캔버스가 뷰포트 대부분을 차지하는 앱 특성상 실사용 문제는 작지만, 캔버스가 포함된 페이지에서 스크롤 시 마우스가 캔버스 위를 지나가는 순간 스크롤이 잠긴다. 최소한 `orbit.dist` 가 이미 min/max 클램프된 경우엔 `preventDefault` 를 스킵하는 편이 안전.

**Fix (2줄):**
```js
var next = orbit.dist * (1 + Math.sign(e.deltaY) * 0.09);
if (next < 12 || next > 60) return;   // 클램프 경계에서 페이지 스크롤 반환
e.preventDefault();
orbit.dist = Math.max(12, Math.min(60, next));
```

---

### [P3-NEW #2] `js/app.js:240-246` — Blob URL 을 `a.click()` 직후 동기 revoke → 브라우저에 따라 다운로드 취소 위험

```js
function download(blob) {
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'nail-simulation.png';
  a.click();
  URL.revokeObjectURL(a.href);   // ← 여기
}
```

`a.click()` 이 시작한 다운로드가 아직 stream 을 여는 중일 수 있음. 즉시 `revokeObjectURL` 은 크롬/파이어폭스 최신 판에선 대체로 문제 없으나, 사파리/구 Edge 에선 실패 사례 보고. 관례상 `setTimeout(..., 0)` 이나 `requestIdleCallback` 래핑.

**Fix (1줄):** `setTimeout(function(){ URL.revokeObjectURL(a.href); }, 0);`

---

### [P3-NEW #3] `js/hand3d.js:650-677` — `pointercancel` 미처리 → drag state stuck

`bindInput` 은 `pointerdown`/`pointermove`/`pointerup`/`wheel` 만 등록. `pointercancel` 은 없음. 터치 이벤트에서 시스템 제스처 (예: iPad 홈 인디케이터 스와이프) 나 브라우저의 몸짓 인식이 `pointercancel` 을 발화하면 `drag` 객체가 `null` 로 초기화되지 않은 채 남는다. 다음 `pointerdown` 없이 `pointermove` 만 와도 `if (!drag) return` 은 통과 → 궤도가 예상 밖으로 움직이는 케이스는 없지만, `setPointerCapture` 도 자동 해제되지 않았을 수 있어 다음 포인터가 안 잡힘.

**Fix (2줄):**
```js
canvas.addEventListener('pointercancel', function () { drag = null; });
```

---

## 5. Tracked LIVE — 재확인

| PR | 항목 | 방치 | 이번 라운드 상태 |
|---|---|---|---|
| **PR #46** | **`render.js` `g.push` 사후-join 누락 (P1)** | **1주** | **⚠ LIVE — 아래 §6 참조** |
| PR #5 | Basel 기업 B RW `1.00 → 1.50` (P0) | 13주 | `risk_lib/capital/rwa_sa.py:42-49` — 커밋 없음 |
| PR #5 | SRISK `(1-k)` 인자 누락 (P0) | 13주 | `systemic.py:61` — 커밋 없음 |
| PR #5 | CoVaR own-loss mask (P0) | 13주 | `systemic.py:96-105` — 커밋 없음 |
| PR #4 | CHG-0143 재사용 + ERRATA-2026-07-14 (P0) | 9주 | 커밋 없음 |
| PR #10 | warden 벽투과 sonic LOS (P1) | 8주 | `minecraft/index.html:3008-3020` — 커밋 없음 |
| PR #10 | 마을주민/동물 GPU 리소스 미해제 (P1) | 1주 | 커밋 없음 |
| PR #38 | `hope-ue/Content/build_content.py` 핀 이름 추측 (P1) | 1주 | 커밋 없음, 자백 유지 |
| PR #38 | hope-shooter `src/main.js:445` wall-clip / 4-path dispose | 1주 | hope-shooter 미터치 |
| PR #38 | Unreal C++ ~2400 LOC 미검증 | 3라운드 | 커밋 없음 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 3일 | main SHA 무변경, 노출창 지속 |

---

## 6. ⚠ 특기: PR #47 P1 (`render.js` dead-store) — 1주 미이행

**27주차에서 지시한 3줄 fix:** *"해당 3 `g.push(` → `out.push(`."*

**현재 상태 (헤드 `01fc7cb4`, `js/render.js`):**

| 라인 | 코드 (요약) | 상태 |
|---:|---|---|
| 584 | `out.push(g.join(''));` | `g` 를 여기서 join → `out` 에 push. |
| 597 | `g.push('<g filter=... clip-path=... ridges ...`);` | ⚠ **join 이후 g 에 push — dead store** |
| 601 | `g.push('<path d=... stroke=... side stroke ...');` | ⚠ 같은 문제 |
| 606 | `g.push('<path d=... clip-path=... env reflection ...');` | ⚠ 같은 문제 |

**함수 반환:** `return out.join('')` (line 627) — `g` 는 두 번째로 join 되지 않음. 27주차와 완전히 동일한 defect. 라인번호만 신규 3D 코드 관계로 밀려남 (391-410 → 584-606).

**영향 (재확인):**
- **세로 미세 융선** (line 597): 자연 네일의 세로 결. 폴리시 얇을 때 보여야 함.
- **손톱 측면 그루브 stroke** (line 601): 손톱 측면에 살짝 파인 그림자 stroke.
- **프리엣지 아래 환경 반사** (line 606): 젤 마감의 특징 반사 stroke.

**저자가 27주차 이후 실제로 한 일 (커밋 로그):**
- `b9fabee6` — nail roll 축 회전 중심 수정
- `445cd9c3` — 신규 3D SDF/WebGL2 렌더러 추가 (2D 는 손 안 댐)
- `01fc7cb4` — 2D/3D 실측 손 치수 보정 (렌더 파이프라인 수정 없음)

**진단:** 27주 리뷰가 명시적으로 지목한 3줄 fix 를 그대로 두고 신규 기능(3D 렌더러 815 LOC)을 얹었다. 결과적으로 **26주차 PR #45 P1 fix (`form_ids.py`) 로 처음 관측된 "tracked → fixed" 사이클이 27→28주 에서 즉시 회귀** — 25주 기간 중 유일한 tracked fix 사례를 유지하지 못했다.

---

## 7. 다음 라운드 (29주차) 권고

**즉시 (24h):**
1. **PR #46 `render.js:597, 601, 606` 3줄 → `out.push`** — 27주차 지시 반복 (P1, **1주 → 2주 넘김 방지**).
2. PR #46 `hand3d.js:773-778` — pick() 스토리지 캐시 (P2).
3. PR #46 `hand3d.js:361` — buildHand 프리컴퓨트 or 청킹 (P2).
4. PR #46 3줄 P3 fix (wheel guard / setTimeout revoke / pointercancel).

**기한 초과 (미이행 시 다음 라운드 격상):**
5. PR #5 Basel · SRISK · CoVaR (P0, **13주**).
6. PR #4 CHG-0143 + ERRATA (P0, **9주**).
7. PR #10 warden LOS 체크 (P1, **8주**).
8. PR #10 마을주민/동물 dispose 4경로 (P1, 1주).
9. PR #38 `build_content.py` 핀 검증 (P1, 1주).
10. PR #43 `.claude/settings.json` commit SHA 핀 1줄 (P1, 3일).

**프로세스:**
11. 리뷰 지시가 1주 이상 미이행된 P1 은 다음 라운드에서 **P0 격상 검토** (현재 PR #46 render.js dead-store 가 첫 후보).
12. PR #46 에 dead-store lint 규칙 (`eslint-plugin-no-unused-vars` / `no-unused-expressions`) 도입 — 26주간 6번의 realism-pass round 진단 시트가 잡지 못한 코드 레벨 결함이므로 자동 검사 필요.

---

## 8. 리뷰 방법 (재현 가능성)

- **소스:** `github.com/bbootta/AIops` open PR HEAD SHA (`main` = `281d6017`)
- **방법:** PR #47 의 `truth table` 을 baseline 으로 하여, 각 PR head SHA 및 updated_at 이 2026-07-26 21:15 UTC 이후인지 여부로 delta 판별. Delta 있는 PR (본 라운드는 PR #46) 에 대해서만 파일 fetch 후 정적 분석.
- **PR #46 검사 파일:** `js/render.js` (802 LOC) · `js/hand3d.js` (817 LOC) · `js/app.js` (330 LOC) · `js/geometry.js` (183 LOC) · `index.html` (96 LOC)
- **비검사 파일:** `dist/nail-simulator.html` (2561 LOC bundled) — 소스 파일과 동등 코드 기반이므로 중복. `docs/realism-rounds.log` (101 LOC 로그) — 코드 아님. `css/style.css` (225 LOC) — 이번 라운드 결함 없음.

---

_본 문서는 리뷰 보고서 전달용. **머지 금지.** 아래 PR body 요약도 동일 내용._
