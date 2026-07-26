# [2026-07-26] 전체 저장소 코드 리뷰 — 27주차

**리뷰 기간:** 2026-07-25T21:14:56Z (PR #45 baseline) → 2026-07-26T21:00Z (~24h)
**리뷰 SHA baseline (main):** `281d60170963a1f0dc4adbb21198474e1651bb3e` (변경 없음)
**리뷰 방식:** 3개 병렬 general-purpose 서브에이전트 — PR #46 신규, PR #5 델타, PR #10 + PR #38 델타

---

## 요약

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **3** — PR #46 렌더 레이어 소실 · PR #10 마을주민/동물 dispose · PR #38 Unreal 재료 함수 핀 이름 추측 |
| 신규 P2 | **5** — PR #46 ×3 (loadLook, blob URL, quota) · PR #5 ×2 (CCR 스프레드 무반응, 하향 이산) |
| 신규 P3 | **8** — PR #46 ×4 · PR #10 ×1 · PR #5 ×2 · PR #38 ×1 |
| Tracked LIVE 재확인 | **4주째 신규 P0 없음**, 그러나 P0×3 12주 · PR #38 Unreal 미검증 2라운드 유지 |
| **Fixed 최초 확인** | **PR #45 P1 form_ids.py BA-접두어 → `0758cde5`** ✓ |
| PR #45 지시 이행 | **1/6** — form_ids fix 만 이행 |

### 신규 활동

- **PR #46 신규** — 네일 시뮬레이터 (~2500 LOC, vanilla JS/SVG, 10 커밋: 초기 + 다크테마·단일파일 번들 + realism rounds R1-R100 세 뭉치). 저자가 진단 시트(9분할 × 4종)로 100라운드 다듬음, 헤드리스 22 시나리오 통과. 그럼에도 렌더 결함 1건 발견.
- **PR #5** — 10 커밋: 감독규정 편제 34장 업무보고서 + 14축 동시 스트레스 + 상시 독립검증(3선) 위임 + F-001~F-301 시정 4라운드 + FSS 서식 마스터 정합 fix + retail 서식 분리.
- **PR #10** — 4 커밋: 모바일 핫바 · 오버월드 10배 확장(608×608, 청크 스트리밍) + 마을·주민·가축 · 색상 포탈 + 성 방어 맵 · 성 규모 3배(101블록) + 100인 웨이브.
- **PR #38** — 1 커밋: Unreal side 트라이플래너 마스터 재료 + Megascans 자동 임포트 스크립트 + Physical Camera + 파사드 릴리프. 저자 자백 "not verified: nothing here was compiled or run" 2라운드 연속.
- **PR #4** — 0 커밋. **CHG-0143 재할당 + ERRATA-2026-07-14 발행 8주 연속 미이행 → 이전 라운드에서 P0 승격 유지.**
- **main** — 0 커밋. PR #43 P1 (`.claude/settings.json` commit SHA 핀) **48h 연속 미이행**.

---

## Tracked LIVE — 재확인 결과

| PR | 항목 | 방치 | 이번 라운드 상태 | 위치 |
|---|---|---|---|---|
| PR #5 | Basel 기업 B RW `1.00 → 1.50` | **12주** | **CONFIRMED LIVE** | `risk_lib/capital/rwa_sa.py:42-49` `_RW_CORPORATE["B"]=1.00` |
| PR #5 | SRISK `(1-k)(1-LRMES)·Equity` 계수 | **12주** | **CONFIRMED LIVE** | `risk_lib/systemic.py:61` `srisk = ... - (1-lrmes)*equity` (누락된 `k` 인자) |
| PR #5 | CoVaR own-loss mask | **12주** | **CONFIRMED LIVE** | `risk_lib/systemic.py:96-105` `system_loss.sum(axis=1)` 이 자기 손실 포함 |
| PR #5 | form_ids.py BA-접두어 위장 (PR #45 신규 P1) | 1일 | ✅ **FIXED-BY `0758cde5`** | `_BR_INTERNAL` → `RM-####`, FSS 마스터 검증 통과 |
| PR #4 | CHG-0143 재사용 + ERRATA-2026-07-14 미발행 | **8주 (P0)** | 0 커밋, LIVE 유지 | — |
| PR #10 | warden 벽투과 sonic LOS | **7주** | **CONFIRMED LIVE** | `minecraft/index.html:3008-3020` LOS 체크 여전히 없음 (역방향 자기정당화 주석까지 추가된 상태) |
| PR #10 | `damage()` L~3405 stale comment | 6주 | STILL STALE | 위더 스톰 80% 미언급 |
| PR #38 | Unreal C++ ~1600 LOC 미검증 | 2라운드 | **CONFIRMED WIDER (+~800 LOC)** | 이번 `6f9cfb13`도 자백 유지 |
| PR #38 | `hope-shooter/src/main.js:445` wall-clip raycast | 1일 | **STILL LIVE** | 이번 커밋 hope-shooter/ 미터치 |
| PR #38 | dispose 4-path (`dropEnemy`/`burst`/`tracer`/`shedWisp`) | 1일 | **STILL LIVE** | 동상 |
| PR #38 | Electron pointer-lock, CSP | 1일 | STILL LIVE | 동상 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 2일 | **CONFIRMED LIVE** | main SHA 무변경 |

---

## 신규 P1 — 3건

### [P1-NEW] PR #46 — `render.js` 사이드 스트로크·측면 반사·능선 무성 소실

**위치:** `nail-simulator/js/render.js:391-410` (내부 `nail()`)

**결함:** L~387에서 `out.push(g.join(''))` 로 임시 배열 `g` 를 방출한 뒤, 후속 3개 시각 레이어(사이드 스트로크·환경 반사·능선)는 다시 `g.push(...)` 로 쓴다. `g` 는 이후 재-join 되지 않으므로 그대로 버려진다.

**실패 시나리오:** 렌더 되는 모든 손톱에서 (a) 어두운 사이드 rim 아웃라인, (b) 매트가 아닌 마감의 프리엣지 아래 환경 반사, (c) `sheer < 0.6` 자연 네일의 세로 능선 3종이 DOM 에 들어가지 않는다. 저자가 R14/R21/R28 에서 명시적으로 "해결"했다고 기록한 시각 요소가 최종 산출물에 존재하지 않음.

**Fix (3줄):** 해당 세 `g.push(` 를 `out.push(` 로 변경.

**저자 리서치 사이클과의 관계:** 저자는 100 realism 라운드와 진단 시트(9분할)를 만들어 확인했으나 이 결함이 통과됐다. 스크린샷 diff 대신 코드-수준 static analysis 를 라운드에 포함시켰다면 R14 후속 회귀에서 잡혔을 것.

### [P1-NEW] PR #10 — 마을주민/동물 GPU 리소스 미해제

**위치:** `minecraft/index.html:1955-1983` (`makeVillagerMesh`) · `:1745-1763` (`makeAnimalMesh`) · 정리 경로 `:1897, :2028, :3094, :5133`

**결함:** `makeVillagerMesh`/`makeAnimalMesh` 가 인스턴스마다 새 `BoxGeometry` 를 생성한다. 동물은 `MeshLambertMaterial` 도 인스턴스별. 정리 경로는 `scene.remove()` 만 호출하고 `.dispose()` 를 부르지 않는다.

**실패 시나리오:** 608×608 확장 오버월드에서 마을 근접→이탈 반복 시, 마을당 마을주민 4명 × ~5 박스 + 축사 6마리 × 4 박스 + 3 재질이 매 라운드 누적. 지속 로밍 세션(30-60분)에서 WebGL 컨텍스트 손실. **PR #38 P2-1 (`removeEnemy` dispose) 와 동일 클래스의 결함이 다른 PR 에서 재발생.**

**Fix:** 정리 경로에서 `geo.dispose(); mat.dispose()` 호출 추가. 또는 좀비/스켈레톤에 이미 적용된 `ZG_BODY`/`ZG_LEG` 모듈-스코프 shared-mesh 패턴을 마을주민·동물에도 확장.

### [P1-NEW] PR #38 — Unreal `MaterialFunctionCall` 핀 이름 문자열 추측

**위치:** `hope-ue/Content/build_content.py:117, 124, 143, 148`

**결함:** `WorldAlignedTexture`/`WorldAlignedNormal` 재료 함수의 입출력 핀을 문자열로 지정 — `"TextureObject (T2d)"`, `"TextureSize (S)"`, `"XYZ Texture"`, `"G"` — 저자 커밋 본문 자백 *"both Python scripts depend on engine function pin names written from memory"*.

**실패 시나리오:** 어느 문자열이라도 실제 `.uasset` 입출력과 다르면 `mel.connect_material_expressions` 는 `False` 를 반환하지만 `build_master()` 자체는 raise 하지 않고 완료한다. 결과: 마스터 재료 그래프가 조용히 disconnected → 모든 표면이 fallback tint(WHITE tex × 0.5)로 렌더. 저자가 예상하는 "fallback material" 로 degrade 되지 않는 은닉 실패.

**Fix:** `mel.connect_material_expressions` 반환값을 검사해 `False` 시 raise 하거나, 커밋 전 `.uasset` 에서 핀 이름 실측.

---

## 신규 P2 — 5건

### [P2-NEW] PR #46 — `loadLook` 이 legacy/tampered 스토리지에서 크래시

**위치:** `js/app.js:198`

`Object.assign(defaultDesign(), look.nails[id])` — 이전 스키마 look 이나 tampered `localStorage['nailsim.looks']` 에 `nails` 키가 없으면 `TypeError: Cannot read properties of undefined`. 클릭 핸들러 조용히 abort. **Fix:** `(look.nails||{})[id]`.

### [P2-NEW] PR #46 — Blob URL 이 다운로드 시작 전에 revoke

**위치:** `js/app.js:181-186` `exportPNG`

`a.click()` 직후 `URL.revokeObjectURL(a.href)` 동기 호출. Chrome 은 관대하지만 Firefox/Safari 는 다운로드 취소. **Fix:** `setTimeout(()=>URL.revokeObjectURL(a.href), 1000)`.

### [P2-NEW] PR #46 — 저장된 look 목록 무한 증가, quota 오류 삼킴

**위치:** `js/app.js:190-193` `writeLooks`

`QuotaExceededError` catch 후 return. 사용자 관점에서는 Save 클릭 → 아무 반응 없음 → 실패 인지 불가. **Fix:** 목록 상한 또는 사용자 알림.

### [P2-NEW] PR #5 — CCR 스트레스가 스프레드에 무반응 (CVA 는 스프레드-민감)

**위치:** `risk_lib/stress/multi_axis.py:~189`

`ccr_multiplier = v["rwa_sa"] / sa_base` — `sa_book` 은 sovereign+bank 만이므로 순수 credit_spread 축을 크게 흔들어도 `rwa_sa` 는 미동. 결과: severity=3 spread 스트레스에서도 `rwa_ccr ≈ books.ccr_rwa`. CVA 는 MAR50 정의상 스프레드-민감이므로 실제 스트레스보다 자본을 과대 추정. **Fix:** CVA 에 대해 명시적 스프레드 배수 (예: `1 + β·|Δspread_bp|/100`) 추가.

### [P2-NEW] PR #5 — 등급 하향 이산 함수가 역스트레스 임계를 양자화

**위치:** `risk_lib/stress/multi_axis._downgrade`

`np.floor(0.5*severity)` → severity ≥ 2.0 까지 rating 불변, 이후 1노치 점프. `solve_critical_severity` 는 `tol=1e-4` 이분법인데 목표 CET1 이 노치 스텝 경계에 걸리면 함수가 평평→불연속이라 반환값이 스텝 경계로 잠긴다. **Fix:** rating bucket 분수 보간 또는 flat-path 를 선형 RW 맵으로 대체.

---

## 신규 P3 — 8건

- **PR #46 `app.js:125`** 프리셋 클릭이 여전히 배열 인덱스 참조 (`+b.dataset.val`) — 저자 "index → name" 리팩터가 `defaultDesign` 에만 반영. `DESIGNS` 재정렬 시 조용히 잘못된 프리셋 선택.
- **PR #46 `app.js:187` `readLooks`** — `JSON.parse(...) || []` 가 `Array.isArray` 검사 없이 truthy 통과. `saveLook` 이후 `list.push is not a function`.
- **PR #46 `build-single-file.py:26-28`** — `re.search(...).group(1)` 이 `<title>`/`<body>` 없을 시 `AttributeError`.
- **PR #46 `build-single-file.py:35-38`** — 인라인 JS 에 `</script>` 미이스케이프. 현재 JS 에는 해당 문자열 없지만 향후 리스크.
- **PR #10 `stampVillage:882`** — genBox 가드 밖의 raw `setBlock` 1줄. 현재 상위 루프가 필터하므로 안전, 리팩터 시 order-independence 파괴 가능.
- **PR #5 `pipeline.run_pipeline`** — `model_cards = build_model_cards(...) if False else []` 데드코드 (`backtest` 도 스코프 없음).
- **PR #5 `prudential/ownership.py`** — `_SHARE_OF_OTHER_ASSETS = {"subsidiary": 0.18, "business_property": 0.34}` 근거 없는 하드코딩. `_MAJOR_SHAREHOLDER_IDENTIFIED=False` 로 `ms_credit=0` 이 되면 결재자에게 "all clear" 로 오독 가능 — WARN 추가 권고.
- **PR #38 `import_megascans.py:120`** — 무조건 `virtual_texture_streaming=True`, CVar `r.VirtualTextures` 검사 없음. 설정 drift 시 텍스처 없이 렌더.

---

## Regressions from F-* remediation loop (PR #5)

**결과: 없음.** PR #5 이번 라운드 4-round F-fix 체인 (F-001/002/003/004/005/006 → F-101/102/103/106 → F-201/202/207 → F-301) 을 정적 추적:

- **F-001 / F-101** — `bis.synthesise_capital` 은 `annual_profit` 만 사용, RWA 참조 없음. `_stage_capital` 은 `capital is None` 일 때만 호출. ✓
- **F-002** — `rwa_internal_total = rwa_sa + rwa_irb + ccr_total + mkt.rwa + op.rwa` (baseline `_stage_capital`) **및** `stress/multi_axis.evaluate_point` 양쪽 모두. CCR 이 스트레스 경로에도 포함. ✓
- **F-006 (floor denominator re-shock)** — `standardised_rwa_total(_stressed_full(books, sh, sc), ...)` 이 심도마다 SA 분모를 재-충격. ✓
- **F-207 conditional-approval** — `ValidationGate.require(conditional=...)` 이 `ConditionalApproval.require_complete()` 로 4-필드 강제, 미달 시 raise. fail-closed. ✓
- **F-301 canonical `request_identifier`** — `asdict(request)` × `_ID_EXCLUDED_FIELDS = {request_id, created_at}` + `json.dumps(sort_keys=True, separators=(",", ":"), default=str)`. 결정론적. numpy 스칼라도 `int(v)` 로 캐스팅. ✓

**F-301 fix 품질 노트:** "필드를 손으로 열거하지 않는다" 원칙을 지문 설계에 적용한 것이 인상적. F-102 에서 세운 원칙(파급표 자동 생성)의 재사용.

---

## 시사점 및 다음 라운드 (28주차) 권고

### 이번 라운드가 보여준 것

1. **첫 tracked-P1 fix 시행** — PR #5 `form_ids.py` BA-접두어 (PR #45 P1) 가 `0758cde5` 로 실제 해결됐다. PR #45 발생 후 24h 이내 이행. **25주 리뷰 사이클에서 tracked finding 이 커밋으로 fix 된 최초 관측 사례**. 다만 이 fix 는 규제 서식 정합 이슈로, 12주 방치 중인 Basel III/systemic P0×3 는 여전히 미터치.

2. **재발 패턴 확인**: dispose 누락이 PR #10 (마을주민/동물) 에서 재출현. PR #38 rewrite 후 재도입 → PR #10 신규 콘텐츠. **저장소 차원 코딩 컨벤션에 "씬 그래프 제거 시 dispose 필수" 를 명시 승격 필요.**

3. **미검증 코드 증가** — PR #38 Unreal 포트가 2라운드 연속 "not verified" 자백. 이번 라운드에서 ~800 LOC 추가. Unreal Python API 핀 이름이 "written from memory" 인 상태로 커밋됨 (build_content.py) — 은닉 실패 클래스.

4. **realism 100 라운드 후에도 렌더 결함이 살아남음** — PR #46 진단 시트(9분할, 22 시나리오)가 시각 diff 는 잡았으나 코드-수준 dead-store 결함은 놓쳤다. 저자 자기-리뷰의 blind spot.

### 즉시 (금주)

1. **PR #46 `render.js:391-410`** — 3줄 fix (`g.push` → `out.push`). **P1**.
2. **PR #10 마을주민/동물 dispose** — 정리 경로 4개소에 `.dispose()` 추가. **P1**.
3. **PR #38 `build_content.py`** — Unreal 핀 이름 실측 후 `mel.connect_material_expressions` 반환 검사. **P1**.
4. **PR #5 Basel corp B RW `1.00 → 1.50`** — 1줄. **P0, 12주 방치**.
5. **PR #5 systemic.py SRISK · CoVaR** — 각 1-2줄. **P0, 12주 방치**.
6. **PR #43 `.claude/settings.json` commit SHA 핀** — 1줄. **P1, 48h 방치**.
7. **PR #10 warden 벽투과 LOS 체크** — `hasLineOfSight()` 추가. **P1, 7주 방치**.
8. **PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 발행** — **P0, 8주 방치**.

### 프로세스 (신규)

9. **`.claude/settings.json` 스키마 게이트** (PR #43 P3-2 유지) + 저장소 dispose-필수 컨벤션 문서화.
10. **realism 라운드 프로세스에 코드-수준 dead-store 정적 검사 포함** — PR #46 이 P1 을 100라운드 안에 잡지 못한 원인은 스크린샷 diff-only 감시 때문.
11. **외부 리뷰 피드백 트리아지 프로세스 (25주 연속 미실행)** — PR #45 §"프로세스" 재환기.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
