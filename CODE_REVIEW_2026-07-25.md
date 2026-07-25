# 전체 저장소 코드 리뷰 — 2026-07-25 (26주차)

**Baseline:** PR #43 (2026-07-24 21:07 UTC, 25주차 델타 라운드) — 신규 P1×1 + P3×2 (전건 PR #42), tracked LIVE 3건 + 3건 방치.
**이번 델타 창:** 2026-07-24 21:07 UTC ~ 2026-07-25 (약 24h).

## 델타 요약

| 항목 | 값 |
|---|---|
| main 신규 커밋 | **0건** (PR #43 신규 P1 24h 미이행) |
| 감시 13개 PR head 변화 | **4건** (#4, #5, #10, #38) / 9건 zero-delta |
| 신규 findings | **P0×1, P1×3, P2×5, P3×7** |
| Tracked LIVE (PR #5 + PR #10) | **4건 유지** (모두 6~11주째 방치) |
| Tracked LIVE (PR #38, rewrite) | **패턴 재도입** — SUPERSEDED 라벨 부적절 |
| Tracked (PR #4 CHG-0143 + ERRATA) | **P0 로 승격** — 8주 방치 + 이번 CHG-0146/0147 신규 등록 중 미언급 |
| PR #43 P1 (`.claude/settings.json`) | **LIVE 24h 미이행** |

---

## 1. main 재확인 — PR #43 P1 은 24h 미이행

`.claude/settings.json:2-8` 은 어제 SHA 그대로 (`281d601`). commit/ref/tag 핀 없음. `enabledPlugins."codex@openai-codex": true` 프로젝트 스코프. 저장소를 여는 모든 세션이 여전히 `openai/codex-plugin-cc` 의 upstream default branch HEAD 를 승인 없이 실행. **fix 채널이 27일 연속 정지** (마지막 감시 PR 커밋 = PR #38 `3ffdf95`, 2026-07-22).

---

## 2. 감시 PR delta — 4/13 활성화

### PR #10 (minecraft, `03c52573`, +107/-11) — 1커밋

**Tracked LIVE — warden 벽투과 (7주째)**
- `minecraft/index.html:2052-2064`: 이전 라인 2014-2026 이 hotkey 커밋 +88 라인으로 밀림. 로직 그대로 — `d < 18` 단일 조건, LOS 체크 없음, `damage(5)` 호출.
- **주석이 결함을 사양처럼 정당화**: L2053 "벽을 뚫는", L2058 "블록 무시". 결함 코드에 자기 정당화 주석이 붙는 순간 tracked 는 close 가 아니라 **재검증 라운드**로 이관해야 함.

**[P3-NEW]** `minecraft/index.html:2481` — `Tab` 처리에서 무조건 `preventDefault()`. 시작 오버레이/일시정지 화면에서 브라우저 포커스 이동·키보드 접근성 차단.
- Fix: `if (!isTouch && (playing() || suitPickOpen)) { e.preventDefault(); toggleSuitPick(!suitPickOpen); }` 로 조건 안쪽 이동.

**[P3-NEW]** `minecraft/index.html:3336-3340` — `pickSuit(0)` 호출 시 `if (level === 0 && suitLevel === 0) return;` 조기 종료로 이미 열린 Tab 픽커가 닫히지 않음. UI 표시("0=사람으로/해제")와 동작 불일치.

**[P3-NEW]** `minecraft/index.html:3403-3404` — chip 에 `touchstart` + `click` 이중 바인딩. Android 일부 웹뷰에서 합성 click 발화 시 `pickSuit(i)` 이중 호출로 방금 고른 슈트가 즉시 토글되어 해제.

---

### PR #38 (hope-shooter/hope-ue, `a4bf8554`, 7커밋) — 대량 rewrite + Unreal 포팅

**Tracked findings 라벨 정정** — 5건 중 1건만 실제 FIXED, 3건은 rewrite 로 소멸 후 **동일 패턴 재도입**.

| 이전 finding | 라벨 | 증거 |
|---|---|---|
| `removeEnemy` GPU dispose 4경로 | **REINTRODUCED** | `hope-shooter/src/main.js` `dropEnemy`(L387) / `burst`(L307) / `tracer`(L323) / `shedWisp`(L294) 전부 `.dispose()` 호출 없음 |
| GPU dispose 3개소 | SUPERSEDED (코드 소멸) | — |
| 벽투과 사격 | **REINTRODUCED** | `src/main.js:445` `ray.intersectObjects(enemyMeshes, false)` — 파사드/차량/오브젝트 raycast 없음 |
| window blur / dt 폭주 | **FIXED** | `src/main.js:721` `dt = Math.min(now - prevTime, 0.05)` 클램프 확인 |
| Reflector textureWidth | SUPERSEDED | vendor 삭제, `three/addons/objects/Reflector.js` 상류 사용 (`world.js:299`) |

**[P0-NEW] 미검증 Unreal C++ 1600+LOC 가 head 로 진입**
- `hope-ue/Source/**/*.{cpp,h}` — 마지막 커밋 (`a4bf8554`) 메시지가 스스로 "not verified: none of this was compiled or run" 자백. Epic 계정 없이 빌드 불가, `.umap` 자산 의도적 비어있음.
- 실패 시나리오: PR 병합 시 `hope-ue/` 를 clone 하는 이용자는 UBT 컴파일 오류·에디터 시작맵 부재를 즉시 마주침. 리뷰 게이트를 통과한 "동작 코드" 라는 표시가 head 라벨에 붙음.
- Fix: (a) 별도 실험 브랜치로 분리 또는 draft 태그 유지, (b) `hope-ue/README.md` 최상단에 "not tested, may not compile" 배너 + CI 제외 명시.

**[P1-NEW] 벽투과 사격 재도입** (`hope-shooter/src/main.js:445`)
- `enemyMeshes` 만 raycast. `solids` (3인칭 카메라 오클루전용) / `obstacles` 미포함. 파사드·차량·잔해 뒤 적을 관통 사격 가능.
- Fix: `solids ∪ enemyMeshes` 병합 raycast 후 최근접 히트가 `userData.enemy` 일 때만 데미지.

**[P1-NEW] GPU 리소스 누수 재도입** (`hope-shooter/src/main.js`)
- `makeShadowCreature` 는 소환마다 Capsule/Sphere/RoundedBox/Cone 지오메트리 ~30개 + 고유 `MeshStandardMaterial(shadowSkin())` + `eyeMat` 신규 인스턴스. 제거 시 dispose 없음(L820, L828, L807).
- 시나리오: 웨이브 다수 진행 → WebGL 메모리 지속 증가 → 장시간 세션 컨텍스트 로스트/크래시.
- Fix: 각 제거 지점에서 `mesh.traverse(m => { m.geometry?.dispose(); m.material?.dispose(); })` 또는 창조물 풀 도입.

**[P2-NEW] Electron 포인터락 우회** (`hope-shooter/electron/main.js`, `src/main.js:585-611`)
- 커밋 `11766327` 은 근본 원인(permission handler 미등록) 대신 raw mouse 폴백으로 우회. 화면 밖 마우스 이동 → 클릭 시 창 밖 컨텍스트 메뉴 잔존.
- Fix: `session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(perm === 'pointerLock'))`.

**[P2-NEW] CSP 부재 + dev 스크립트 파손**
- `dist/index.html` 에 `<meta http-equiv="Content-Security-Policy">` 없음 (sandbox 로 보완되나 심층 방어 부재).
- `package.json` `dev` 스크립트가 `http-server` 호출하나 devDeps 미포함 → `npm run dev` 실패.

**[P3-NEW] 스모크/회귀 테스트 부재**
- `hope-shooter/package.json` 에 `test` 스크립트 없음, `hope-ue/` 자동화 전무. 대량 rewrite 후 회귀 감지 수단 상실.

**메타 우려**: 이번 델타로 이전 4주간의 tracked 상당수가 "SUPERSEDED" 처리되지만 **동일 부류 결함(dispose 누락, 벽투과)이 새 코드에 그대로 재도입**. 근본 원인은 코드가 아니라 **팀 규범 부재** — 리뷰 체크리스트에 다음 두 항목을 상수 검증으로 승격 필요:
1. 씬 그래프에서 제거되는 모든 오브젝트는 지오메트리·머티리얼 dispose 명시
2. 명중 판정 raycast 는 반드시 solids/obstacles 를 포함

---

### PR #5 (risk-management-agent-harness, `ecfed284`, 15커밋) — RYNTA v9.0 대량 반영

**Tracked LIVE 3건 — 전건 12주째 유지**

| # | 항목 | 증거 (fresh) |
|---|---|---|
| 1 | Basel 기업 B 등급 SA RW `1.00 → 1.50` | `risk_lib/capital/rwa_sa.py:42` `_RW_CORPORATE = {..., "B": 1.00, "CCC-": 1.50, ...}`. CRE20.42 는 BB- 이하 150%. 동일 테이블이 `standardised_rwa_total()` output-floor 분모로 재사용되므로 **RWA·output floor·BIS·MDA·레버리지가 동시 낙관 편향** |
| 2 | SRISK `(1-k)` 계수 누락 | `risk_lib/systemic.py:56` `srisk = prudential_ratio * debt - (1 - lrmes) * equity`. Brownlees-Engle 정의: `SRISK = k·D − (1−k)·(1−LRMES)·E`. Equity 항의 `(1-k)` 계수 없음 → k=0.08 기준 약 8% 편향 |
| 3 | CoVaR 자기손실 마스킹 | `risk_lib/systemic.py:96-105` `system_loss = losses.sum(axis=1)` 이 은행 i 자신 손실 포함. `mask = losses[:, i] >= thresh` 는 정의상 i 의 큰 손실을 뽑아 `system_loss[mask]` 를 구조적 팽창 → ΔCoVaR 순환 참조 부풀림. Fix: `system_loss.sum(axis=1) - losses[:, i]` |

**검증한 자기신고 수정**
- ✅ `_check_ead_positive` 중복 등록 → `label` 인자로 `ead_nonneg_sa`, `ead_nonneg_irb` 분리 등록 (`risk_lib/validation/consistency.py:96`)
- ✅ 자기참조 reconcile 은 이번 라운드에서는 `governance.py`·`adjustments.py` 가 게시본 값 대비 잔차 산출로 처리됨 — 다만 §특별 우려 3 참조

**[P1-NEW] 서식번호 형식이 사실상 FSS 위장**
- `risk_lib/regulatory/form_ids.py` internal_code 가 `BA2101`, `BA3101`, `BA5101` — **금감원 은행업감독업무보고서 실제 접두어 `BA` 를 그대로 사용**. `(내부)` 접미어가 붙지만 엑셀 시트명(31자 제한)·CSV·복사·붙여넣기 과정에서 접미어 유실이 자연스럽게 발생.
- 시나리오: 담당자가 `BA2101` 셀만 발췌해 재사용 → 존재하지 않거나 다른 서식과 충돌하는 번호로 감독 제출.
- Fix: internal 접두어를 `INT-BR-01` 등 FSS 비충돌 문자열로 변경, `display()` 가 official 없을 때 원본 코드 노출 자체를 금지.

**[P1-NEW 후속]** `reg_submission.status = approved` 승격 게이트가 대사 실패 유무에만 걸려 있고 `official_code is None` 을 차단하지 않음 — 서식번호 없어도 approved 진입 가능. 승격 게이트에 `n_official() == len(FORM_IDS)` 조건 추가 필요.

**[P2-NEW] `fitted_portfolio` 문서 의존성**
- `run_pipeline` 이 PD 모델 재적합 결과를 포트폴리오에 되쓰므로, 원본 프레임 기반 재현은 IRB RWA 에서 ~12% 오차 항구. 회귀 테스트로 오차의 **존재만** 확인 (사라지지 않도록 assert) — 사용자가 raw 프레임으로 감사 재현 시 "숫자가 왜 다른가"를 문서 없이 발견 불가.

**[P2-NEW] CRM 이 published RWA 에 반영되지 않음**
- 커밋 `8e4f3391` 스스로 "collateral 모듈은 존재하고 RWA agent 스펙은 CRM 을 요구하나 `run_pipeline` 이 `apply_crm()` 을 호출하지 않는다" 인정.
- `rwa_crm_allocation` 은 "만약 적용됐다면" 관측치, 게시 숫자는 pre-CRM EAD. RYNTA 커버리지 문서에는 반영됐으나 **PR 본문·CRO 브리핑에서 이 조건이 사라지면 은행업감독업무규정 CRM 인정 조건에 대한 오도** 리스크. Round 11 이전 CRO 브리핑 명시 필요.

**[P3-NEW]** `risk_lib/ui_studio/governance.py:47` `_MASKED_FIELDS` 에 `guarantor_id` 중복; 같은 파일 `_agent_domain` 이 다수 에이전트를 기본값(`"G · 에이전트 운영"`)으로 오분류.

---

### PR #4 (validation-team-agent, `991b0e4c`, 6커밋) — Rounds 79~82

**[P0-UPGRADE] CHG-0143 재할당 + ERRATA-2026-07-14 — 8주 방치 + 이번 라운드 신규 CHG-0146/0147 등록 중 미언급**
- `validation-team-agent/harness/change_manifest.json:2135` 의 CHG-0143 은 여전히 `status: "proposed"` / `human_approval_required: true`. 내용은 "SVG aria-label 추가"(Round 78)로 재할당 문구·근거 없음.
- `ERRATA-2026-07-14` 는 `validation-team-agent/` 전체 참조 0건 (Grep 검증). 어떤 changelog/docs/manifest 에도 등장하지 않음.
- 이번 회차 ruff 픽스(`aff178c8`) 및 4개 신규 라운드(`CHG-0144~0147`)는 CHG-0143 을 언급하지 않음 — tracked 지적을 리뷰 프로세스가 조용히 지나감 → **P2 → P0 로 승격**.

**[P1-NEW] `check_findings=False` 우회 경로에 감사 로그 없음**
- `validation-team-agent/tools/manifest.py:promote:99-117` — Critical Finding 위 승격이 `check_findings=False` 로 우회 가능하나, `manifest_entry` 에 `bypassed_findings_check` 필드 부재, `logs/` 에 이벤트 없음.
- 시나리오: Critical Finding 이 열려 있는 상태에서 승인자가 우회 promote → 감사관이 정상 promote 와 구분 불가.
- Fix: `manifest_entry` 에 `bypassed_findings_check: bool` + `bypass_reason: str` 필드, `logs/manifest_bypass_events.jsonl` append.

**[P2-NEW] pack_verify 는 여전히 self-referencing**
- `tools/pack_verify.py:_verify_pages:170-206` `--deep` 재빌드가 `run_demo` + `build_pack` 같은 파이프라인 재사용. 파이프라인 자체 버그면 원본과 재빌드 모두 동일 오답 → PASS 반환.
- 사후 위·변조는 잡지만 산출 로직 오류는 못 잡음. Fix: docstring 에 "결정성만 증명, 산출 정확성 미증명" 명시 + Golden fixture 대조를 별도 검사(VAL-010)로 병행.

**[P2-NEW] `detect_recurrence` 조인 키 무검증**
- `tools/validation_finding.py:168-178` — 재발 판정 키 `(domain, root_cause, target)` 중 `target` 이 자유 문자열·정규화 없음.
- 실패 시나리오: `target=None` 두 건이 서로 재발로 판정 (양쪽 None → 참), `target=""` / `" T"` / `"T "` / 대소문자 차이로 우회.
- Fix: `open_finding` 에서 `target` required + enum/regex 검증, 저장 전 `strip().casefold()` 정규화.

**[P3-NEW]** `tools/val_coverage.py:37` `_WEIGHT = {..., "partial":0.5, ...}` 는 코드 주석에만 라벨, `val_requirement_coverage.json` 상 사용자에게 노출되는 55.6% 수치의 주관성 미표기. `summarize()` 반환에 `weighting_source: "subjective_0.5_partial"` 태그 필요.

**ruff pinning fix (`aff178c8`) — 안전**
- `extend-select=["E741"]` → `select=["E4","E7","E9","F","E741"]`. 실효 룰셋은 이전과 동일 (ruff 0.5+ 기본이 E4/E7/E9/F). silently dropped 되어 실질 이슈를 놓친 룰 없음.

---

## 3. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **1** (PR #38 미검증 Unreal head 진입) |
| 신규 P1 | **3** (PR #38 wall-clip 재도입 · PR #38 GPU dispose 재도입 · PR #5 BA-접두어 위장) |
| 신규 P2 | **5** (PR #38 Electron ptr-lock · PR #38 CSP·dev 스크립트 · PR #4 pack_verify self-ref · PR #4 recurrence 키 · PR #5 fitted_portfolio · PR #5 CRM 미반영) |
| 신규 P3 | **7** (PR #10 ×3 · PR #38 ×1 · PR #5 ×1 · PR #4 ×1) |
| Tracked LIVE 재확인 | PR #10 warden(7주) · PR #5 Basel(12주) · PR #5 SRISK(12주) · PR #5 CoVaR(12주) |
| P0 로 승격 | PR #4 CHG-0143 (8주 무언급, 이번 라운드 4건 CHG 신규 등록 중 미포함) |
| PR #43 지시 이행 | **0/1** — main `.claude/settings.json` P1 24h 미이행 |

---

## 4. 시사점

1. **PR #43 P1 24h 미이행** — 어제 지적된 공급망 노출이 하루 그대로. **fix 채널이 감시 PR 뿐 아니라 리뷰 자체에도 정지**된 시그널.
2. **PR #38 rewrite anti-pattern** — 대량 rewrite 는 tracked findings 를 코드에서 지우지만 결함 부류(dispose 누락·벽투과)는 새 코드에 재도입. 리뷰 결과의 실제 효용이 0.
3. **PR #5 self-referencing checks 재발성** — 이번 15커밋에서만 3건의 자기참조 패턴이 발견·수정 (`_check_ead_positive` 중복, page65 ledger 자기대사, market_data 부트스트랩 대수적 역산). 30c85f72 커밋 스스로 "checks that cannot fail is worse than no check" 원칙 언급 — 이 원칙을 회귀 테스트로 고정 필요.
4. **외부 리뷰 피드백 무시** — PR #5 tracked 3건 12주, PR #4 CHG-0143 8주, PR #10 warden 7주, PR #38 dispose 4주 (rewrite 이후 재도입). 내부 nonconformity workflow(AIMS cl.10.2)는 자기 감사에는 적용되나 **외부 리뷰 피드백 트리아지 프로세스 부재** 확인.
5. **미검증 Unreal C++ head 진입 (P0)** — "not verified" 자백을 커밋 메시지에 명시했다는 것 자체가 이례적. draft PR 이나 실험 폴더로 격리하는 프로세스 자체가 없어 head 로 진입.

## 5. 다음 라운드 (27주차) 권고 — 우선순위

### 즉시 (금주)
1. **[신규 P0]** PR #38 `hope-ue/` 를 별도 실험 브랜치로 분리 또는 draft 유지, README 배너 + CI 제외.
2. **[신규 P1]** PR #5 `form_ids.py` 의 `BA` 접두어 → `INT-BR-*` 로 변경, `display()` 에서 official 없을 때 원본 노출 차단.
3. **[신규 P1]** PR #38 `main.js:445` 벽투과 사격 raycast 를 solids ∪ enemyMeshes 병합으로.
4. **[신규 P1]** PR #38 `dropEnemy`/`burst`/`tracer`/`shedWisp` 4경로 dispose 추가.
5. **[신규 P1]** PR #4 `manifest.py:promote` 우회 감사 로그 필드·이벤트 추가.
6. **[PR #43 P1 미이행]** `.claude/settings.json` commit SHA 핀 (1줄). 27주차 계속 open 시 warden·Basel 과 동급으로 tracked 이관.

### 프로세스 (다음 2주)
7. **[신규 P0 승격]** PR #4 CHG-0143 tracked + ERRATA-2026-07-14 changelog 반영 — 승격 조건 명시.
8. **[신규 P2]** PR #4 `pack_verify` self-referencing 한계 docstring 명시 + Golden fixture 검사 병행.
9. **[신규 P2]** PR #4 `detect_recurrence` target 키 정규화·검증.
10. **[신규 P2]** PR #5 CRM 미반영 사실을 CRO 브리핑에 명시.
11. **[신규 P2]** PR #38 CSP 메타 추가 + `dev` 스크립트 devDeps 정리.
12. **[신규 P2]** PR #5 `reg_submission` 승격 게이트에 `official_code` 완비 조건 추가.
13. **[구조]** 리뷰 체크리스트에 상수 검증 항목 승격: (a) 씬 그래프 제거 시 dispose 명시, (b) 명중 판정 raycast solids/obstacles 포함, (c) 자기참조 check 금지 (fault injection 테스트 필수).

### Tracked backlog (12~7주 무이행)
14. PR #5 3건 (Basel B RW, SRISK (1-k), CoVaR self-mask) — 12주.
15. PR #10 warden LOS (`minecraft/index.html:2052-2064`) — 7주.
16. PR #38 rewrite 이전 dispose·wall-clip 지시 → 재도입된 코드에도 그대로 적용.

## 6. 부속

- 이번 라운드에서 확인된 재발성 결함 부류(**dispose 누락**, **벽투과 raycast**, **self-referencing checks**, **자기 참조 reconcile**) 는 개별 fix 이상으로 팀 규범·CI 게이트로 승격되어야 함. 개별 PR 별 지시가 4주~12주째 무응답인 상황에서 프로세스 결함으로 승격하지 않으면 27주차에도 동일 재도입이 예상됨.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
