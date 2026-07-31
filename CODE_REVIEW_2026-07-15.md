# 전체 저장소 코드 리뷰 — 2026-07-15 (18주차)

## 요약

지난 라운드 (PR #31, 2026-07-13 21:13 UTC) 이후 ~40h. **감시 대상 11개 PR 중 3개 PR (#4, #5) + 신규 PR #32 이동, 나머지 8개 PR head SHA 무변경**.

- **PR #32 신규** — `e63e5d26` (2026-07-14 04:20 UTC) — 위장 잠입형 2D 아케이드 게임 `mecha-chameleon/index.html` 단일 파일 (824 lines) + README 27 lines. HTML5 Canvas + Vanilla JS, 의존성 없음.
- **PR #5 커밋 4건** (2026-07-14 10:19 ~ 10:52 UTC) — 감사 로그 확장 없이 executive/board_pack UI 강화: 4-b 섹션 sensitivity tornado + CRO 브리핑, KRI 스코어카드 12M 스파크라인, EN 보드팩 CRO briefing (한/영 단일 사실셋). 코드 변경 285 lines (`html_exec.py` +129, `board_pack.py` +13, `localization.py` +52, `viz_advanced.py` +23, `printable.py` +2, `tests/test_executive.py` +26). **tracked P0×4 미터치 (4주 연속)**.
- **PR #4 커밋 3건** (2026-07-14 10:17 ~ 10:48 UTC) — Round 75 CRO digest 이메일 초안 도구 신규 (219 lines) + ICAAP post_stress_level KPI 오표기 실버그 수정, Round 76 보고서 팩 다크모드, Round 77 CRO digest QoQ 섹션. 새 테스트 251 lines (v2_round75/76/77) — 1076 pass (1056→1076). **pseudonymize salt (P1) · Basel Total-cap `+ 0.03` (P1) · cet1 hardcode (P0) 미수정**.
- **신규 P0** — 0건.
- **신규 P1** — 1건 (PR #4 R39+ 다수 report pack 이 잘못된 fail/ok 라벨로 shipped, errata 통보 프로세스 부재).
- **신규 P2** — 3건, P3 — 4건.
- **Tracked 27건 재검증** — FIXED × 1 유지 + PARTIAL × 3 유지 + **LIVE × 23** (라인 시프트만 반영, PR #4 Round 76 dark mode `+60 lines` → tracked line 재특정).

## 이번 라운드 신규 P1 · 1건

### PR #4 — Round 75 (`2bf10b87`) 실버그 fix 는 완료, 그러나 R39+ 다수 output artifact 오라벨링에 대한 errata 프로세스 부재

Round 75 커밋 메시지 자체가 시인: **"registry ICAAP outputs 에 post_stress_level 누락 → 정상 모드 executive KPI 가 '스트레스 후 ICAAP 1.19' 를 fail 로 오표기 (임계 min 1.0 / warning 1.05 기준 1.1875 = ok). R39 이후 전체 팩에 존재"**.

R39 부터 이번 Round 74 까지 (≈36 rounds) 다수의 report pack 이 정상인 ICAAP 후 자본 비율을 **적색 fail 로 잘못 렌더링한 채 배포**된 것으로 확인. 검증팀 리뷰어가 자본 부족 상황으로 오인해 불필요한 시정조치 발동 가능성이 있는 governance-critical error 임에도 다음 조치가 명시되지 않음:

- 프로세스: (a) 영향 받은 이전 report pack 식별 & 이력, (b) 다운스트림 컨슈머 (CRO/이사회/감독당국 후보) 통지, (c) 정정본 재배포, (d) `docs/ERRATA-YYYY-MM-DD.md` 발행. **현재 change_manifest.json CHG-0140 은 코드-측 수정 기록만 유지 — output-artifact-side 정정 언급 없음**.
- 이는 규제 대응 컨텍스트 (Basel III / IFRS 9 검증 산출물) 에서 감사 성립 가능한 통제 실패에 해당. 검증팀 활동 자체가 감사 대상 (§AIMS-Policy) 이므로 fix 커밋 만으로 클로징하지 않고 errata 트레일이 별도로 필요.

**fix**: (a) `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 발행 (영향 범위 R39-R74 rounds, 오표기 상세, 영향 없음/있음 분류), (b) `change_manifest.json` CHG-0143 (proposed) 로 "output artifact re-issue" 항목 별도 등록, (c) 이전 shipped report pack 에 errata 배너 삽입 또는 archive 폴더 이동. 이는 PR #5 governance.py Pillar 3 deprecated flag 지적과 동일 계열 — **코드 수정 ≠ operational control 완결**.

## 이번 라운드 신규 P2 · 3건

### 1. PR #5 — `risk_lib/viz_advanced.py` sparkline: **synthetic 12M back-histories 를 실측 트렌드로 오독 가능**

커밋 `c98e4051` (Round 74 대응 Round 74.1) 는 KRI scorecard 카드마다 12M 스파크라인 + 트렌드 라벨 `12M ↗개선 / ↘악화 / →보합` 추가. 커밋 메시지 자체 명시: **"seed-pinned synthetic 12M back-histories (risk_lib.timeseries, reconciling to the current observation)"**. 즉:

- 스파크라인 자체는 **시드 고정 합성 데이터** — 마지막 값만 실측 관측치에 재조정. 12개월 중 앞 11개 값은 seed 로부터 합성됨.
- 그러나 exec dashboard 및 printable scorecard 어디에도 **"synthetic 예시" 배너·주석 없음**. CRO 가 보고서를 열면 "↗개선" 라벨 옆에 정말로 12M 실측 추세로 오독 가능.
- Round 77 커밋에서는 QoQ 표에 `"합성 panel 예시 문구 강제 (실측 오인 방지)"` 처리를 명시적으로 도입 → **개발자 스스로 이 위험을 인식하고 있음에도 sparkline 은 예외**. 일관성 문제.

**fix**: sparkline 카드 하단에 `합성 12M · 예시` micro-caption 추가 (`viz_advanced.py` sparkline 렌더 훅에서 `data-source="synthetic"` 태그 → CSS `::after`).

### 2. PR #32 — `mecha-chameleon/index.html:100+`: `startBtn:focus-visible` 활성 + Space keydown 이 `preventDefault` 처리되나 브라우저 click 활성화 가능성

```js
window.addEventListener('keydown', (e) => {
  if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown',' '].includes(e.key)) e.preventDefault();
  keys.add(e.code);
  if (e.code === 'KeyR' && state === 'over') restart();
});
```

`e.key === ' '` 인 Space 는 `preventDefault` 되어 페이지 스크롤은 막히나, **`startBtn` 이 마지막 focus 를 유지 (예: `restart()` 이전 Start 버튼 클릭 후 focus 남음)** 상태에서 게임 도중 Space 를 누르면 브라우저에 따라 button 의 activation 이벤트가 트리거되어 `restart()` 호출 → 진행 중 게임 초기화. `preventDefault` 는 스크롤은 막지만 button activation 은 브라우저 구현에 좌우.

**fix**: `restart()` 호출 후 `startBtn.blur()` 명시, 또는 `state === 'play'` 시 `startBtn` disabled 처리.

### 3. PR #32 — `mecha-chameleon/index.html:tongue.extend` 히트 판정 tunneling

```js
tongue.tipX += tongue.dx * 1500 * dt;  // 60fps 시 25px/frame
if (Math.hypot(b.x - tongue.tipX, b.y - tongue.tipY) < 16) { ... }  // 반경 16
```

60fps 정상 시 25px < 16px 반경 x2 = 32px → OK. 그러나 tab background / 저성능 기기에서 `dt` 가 0.033 (`Math.min(0.033, ...)`) 로 클램프될 때 step = 50px > 반경 32px → 벌레/헌터 통과 (tunneling). Game-critical 은 아니나, tongue 발사 후 판정 실패로 위장 소모만 발생 (`player.reveal = 0.9`).

**fix**: 스텝을 CCD (continuous collision detection) 로 segment vs point → tongue.tipX 이전-현재 세그먼트 상에 반경 16 있는 점 존재 여부. 또는 스텝 상한 (예: 20px) 로 서브샘플.

## 이번 라운드 신규 P3 · 4건

- **PR #32 `index.html:158`** — `mouse.down` 상태 저장하나 `update(dt)` 내에서 사용 안 함. `fireTongue()` 는 mousedown 이벤트에서만 호출. `mouse.down`/mouseup 리스너 dead code — 제거 또는 auto-fire 도입 시 사용.
- **PR #32 `index.html:255` `player.y > H + 60`** — 낙사 안전망은 `player.y = 0` 로 텔레포트 + `hp -= 10`. 상단 platform (`y=224`) 위로 순간이동해 위치가 겹치면 다음 프레임 낙사 재발. 반복 낙사 시 hp 순삭. 대신 spawn point 로 (W/2, GROUND_Y-14).
- **PR #32 `nextWave()`** — `player.hp = Math.min(100, player.hp + 12)` 는 웨이브 클리어 시 회복. 그러나 클리어 조건 `hunters.length === 0` 은 restart 직후에도 참 → 첫 웨이브 시작 전에도 발화. 실측: `waveDelay = 0.5` (restart) → 첫 nextWave 호출 시 hp=100, +12 clamp 무효. 실제 finding 은 아니나 논리적으로 heal-on-empty 는 별도 wave-complete 이벤트로 분리 가치.
- **PR #4 Round 76 dark mode** — `@media print` 라이트 강제는 좋으나 `@media (prefers-color-scheme: dark)` 로만 전환. 사용자가 브라우저에 명시적 light preference 걸어놨는데도 OS 다크 모드 시 다크가 됨 → `@media (prefers-color-scheme: dark)` + `:root[data-theme="dark"]` 조합 권장 (사용자 override 존중).

## Tracked 27건 재검증 결과

**FIXED × 1 유지 + PARTIAL × 3 유지 + LIVE × 23.** PR #4 Round 76 dark mode 커밋이 `tools/report_pack.py` 에 +60 lines (CSS 만) 추가 → 관련 tracked 라인 재특정 필요.

### PR #4 tracked LIVE 라인 재특정 (Round 76 시프트 반영)

실측 확인:

| 위치 (17주차) | 위치 (현재, 18주차) | 상태 | 근거 |
|---|---|---|---|
| `tools/report_pack.py:3707` | **`tools/report_pack.py:3762`** `cet1_min_pillar1 = 0.045` | **LIVE** | Round 76 CSS 삽입 +55 lines. 하드코드 문법 그대로. SSoT `load_thresholds()` 위임 미이행. |
| `tools/report_pack.py:3733` | **`tools/report_pack.py:3788`** `total < cet1_required + 0.03` | **LIVE** | 동 라인 시프트. `+ 0.035` 로 미수정 (Basel III Total capital 8.0% → CET1 4.5% 대비 surcharge). |
| `tools/report_pack.py` pseudonymize salt | **`tools/report_pack.py:4354`** `salt = hashlib.sha256(f"vta-pack-salt-{args.seed}".encode()).digest()` | **LIVE** | Round 77 미수정. **커밋 코멘트 자체 시인**: `"salt 가 추정 가능하므로 원본 파일 접근자는 재식별 시도 가능"` (라인 4354 위 주석). |

### FIXED × 1 (유지)

- **PR #4 `validation-team-agent/middleware/permission_guard.py:31-43`** — `PermissionFinding` 스키마 유지 확인.

### PARTIAL × 3 (유지)

| PR | 위치 | 상태 |
|---|---|---|
| #2 | `stock_trading/harness.py:210` | sticky `last_text` 여전 (**9주 무변화**). |
| #2 | `stock_trading/harness.py:82-141` | run-level sticky APPROVED 잔존. |
| #9 | `reports/basel-iii-endgame-implementation-status-2026-06-10.html:154-207` | 4 rows LIVE. |

### LIVE × 23 (요약)

이번 라운드 delta 커밋이 접촉하지 않은 파일의 tracked findings 는 자동으로 LIVE 유지. 세부:

- **PR #2 P0×2 LIVE** (**9주 방치**): `harness.py:~205` thinking=adaptive · `tools.py:234` place_order 음수 shares.
- **PR #4 P0×1 + P1×1 + P1×2 LIVE**: `pack_archive.py:82-83` path traversal · `scenario_weights.py:83` dict-zip dedup · `report_pack.py:3762` cet1 hardcode · `report_pack.py:3788` Basel Total-cap `+ 0.03` · `report_pack.py:4354` pseudonymize salt.
- **PR #5 P0×4 + P1×1 + P2×1 LIVE** (**4주 연속 exec/UI 커밋만, 본질 P0 미수정**): `systemic.py:61` SRISK `(1-k)` · `rwa_sa.py:26/36/46` B-bucket RW=1.00 · `systemic.py:122` CoVaR own-loss mask · `frtb.py:173` FRTB multiplier · `governance.py` Pillar 3 deprecated flag · `repro.py:~178` setdefault(asof, None) · `AIMS_POLICY.md:8 vs :32` 카운트 불일치.
- **PR #9 P1×1 LIVE**: `harness/risk-research-runbook.md` G3/G4/G5 prose-only.
- **PR #10 P1×5 + P1×2 + P2×1 + P2×3 + P3×1 LIVE** (2주 무변화): `applyPos` NaN L3390 · `destroyBlocks` CHEST L834 · `saveGame` sync stall L639 · `WORLD_VER=5` inv-loss L334 · blinkTeleport 벽 관통 · timeStop arrows 배열 성장 · Wither Storm 볼레이-체스트.
- **PR #22 P0×3 LIVE** (**6주 방치**): `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md:11+:13` /code-review chain + auto-commit.
- **PR #30 P1×1 LIVE** (2주 방치): `CLAUDE.md §0` + `docs/ISO-42001-AGENT-REQUIREMENTS.md` 소급 조항·CI check 부재.
- **PR #3/6/7/8 P1/P2 LIVE**: 9주 무변화.

## PR #32 신규 상세 리뷰 (851 lines)

전량 정독. **P0/P1 finding 없음**. P2×2, P3×2 는 위 신규 findings 섹션 참조.

**긍정 사항:**

- `<script>` 즉시 실행 함수 (`(() => { 'use strict'; ...`) 로 전역 오염 회피.
- 오디오 컨텍스트 lazy 초기화 (`if (!actx) actx = new (window.AudioContext || ...)()`) + try/catch 로 audio 미지원 브라우저 graceful degradation.
- `descEl.innerHTML` 사용은 정적 문자열 리터럴만, XSS 벡터 없음. `finalScoreEl.textContent` 은 안전.
- `dt = Math.min(0.033, (now - last) / 1000)` — 백그라운드 탭 복귀 시 시간 폭주 방지.
- HP/에너지 clamp (`Math.max(0, ...)` + `Math.min(100, ...)`) 일관.
- Playwright 헤드리스 검증 완료 (PR 본문 언급).

**경미 관찰 (findings 아님):**

- Fixed 960×600 캔버스 + `aspect-ratio: 960 / 600` 컨테이너 → 반응형 매우 좋음.
- `platforms` 배열은 top-collision 만 (수평-측면 통과) — 아케이드 관용, 의도적.
- WebAudio `beep` 함수 vol 기본 0.04 — 볼륨 절제, 무음 브라우저에서도 무리 없음.
- `state === 'menu'` 시 `drawBackground(); drawPlatforms();` 만 그림 → CPU 저부하 유지.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#32 (new)** | 1 (824 line game) | P2×2 + P3×3 | — | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (2주) | **block-merge** (소급 조항 필요) |
| **#10** | 0 | — | tracked 12 LIVE (2주 무변화) | **block-merge** |
| **#5** | 4 (exec UI) | **P2×1** (sparkline synthetic 미고지) | P0×4 + P1×1 + P2×1 LIVE (**4주 연속 방치**) | **block-merge / escalate** |
| **#4** | 3 (CRO digest + dark mode + QoQ) | **P1×1** (R39+ errata 프로세스 부재) + P3×1 (다크모드 override) | FIXED×1 · PARTIAL×3 · LIVE P0×1+P1×2 (라인 재특정) | **changes requested** |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**9주 방치**) | **block-merge** |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | **block-merge** |
| **#22** | 0 | — | P0×3 LIVE (**6주 방치**) | **close 권고 즉시 시행** |
| #3 / #6 | 0 | — | P1/P2 LIVE | changes requested |
| #7 / #8 | 0 | — | P1×2 + P2×2 LIVE | #7 close / #8 delta 검토 |

## 누적 18회 결산

|  | #26 | #27 | #28 | #29 | #31 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | 0 | 0 | **0** |
| 신규 P1 | 0 | 1 | 2 | 2 | 2 | **1** |
| 신규 P2 | 1 | 2 | 4 | 3 | 6 | **3** |
| 누적 수정 | 7/79 | 7/82 | 8/84 | 8/86 | 8/88 | **8/89** (변화 없음, 이번 fresh 4개 추가) |

**해석.**

1. **PR #5 4주 연속 exec/UI 순환 (P0×4 미수정)** — Round 대응 delta 는 tornado / sparklines / EN CRO briefing / board pack 개선. 산출물 폴리싱 방향으로 계속 진행되고 있으나, **본질 리스크 계산 로직의 tracked P0 findings 는 접촉되지 않음**. 이번 sparkline 신규 P2 (synthetic 미고지) 는 개발자가 QoQ 표에서는 인식하고 처리한 위험을 sparkline 에서는 놓친 것 — **자기 일관성** 문제.
2. **PR #4 R39+ 오라벨링 시인** — 코드 수정은 완료됐으나 이는 output artifact side effect 없이 처리되지 않는 governance-critical event. 다른 PR 들 (특히 PR #30 의 ISO 42001 gate) 이 아직 소급 조항 없이 open 인 상황에서 검증팀 자체 output 의 errata 프로세스 부재가 드러난 것은 self-audit / operational control 문제.
3. **PR #22 6주 방치** — 지난주 (5주) 대비 조치 없음. 다음 라운드 (19주차) 이후 **close 권고 즉시 시행 필요**.
4. **PR #2 9주 방치** — sticky APPROVED / thinking=adaptive 는 sub-agent 오케스트레이션의 근본 문제. Owner 부재 시 close 도 고려.
5. **PR #32 신규는 clean** — 게임 하나. 851 lines 전량 정독 결과 P0/P1 없음, P2/P3 polish 만. 다른 PR 들과 달리 즉시 mergeable 후보.

## 다음 라운드 권고

1. **PR #4 errata 프로세스 도입** — `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` + CHG-0143. R39-R74 rounds 영향 범위 명세.
2. **PR #5 sparkline synthetic 고지 추가** — QoQ 표와 동일한 처리 (`data-source="synthetic"` + CSS ::after 배너).
3. **PR #5 P0×4 fix 촉구 (4주 연속)** — SRISK `(1-k)` · Corporate B RW 1.00→1.50 · CoVaR mask · FRTB multiplier BCBS MAR99. 계속 UI 개선만으로는 **머지 절대 불가** 재환기.
4. **PR #4 tracked LIVE 3건 fix** — cet1 하드코드 → SSoT · Basel Total-cap `+ 0.035` · pseudonymize `--secret-key` env var 우선.
5. **PR #22 close 즉시** — 6주 방치, 소유자 응답 없음, 3개 P0 유지.
6. **PR #30 소급 조항 추가** — 지난주 지적 재환기, 그렇지 않으면 이 PR 하나가 6개 open agent PR block-merge.
7. **PR #32 polish** — startBtn.blur() + tongue CCD + sparkline 유사 sparkline 없음 (게임에는 sparkline 없음, 이건 PR #5 사항). 소규모 patch 로 즉시 mergeable.

## 리뷰 방식

**메인 스레드 단일 세션**:

- 11개 감시 PR (기존 10 + 신규 #32) head SHA 대조표 → 3개 이동 확인 (#32 신규, #5, #4).
- **PR #32 신규**: 824 lines HTML/JS 전량 정독 — 오디오/입력/물리/렌더링/HUD 4단 확인. XSS·CSP·상태 리셋 벡터 별도 점검.
- **PR #5 delta**: 4 commits 285 lines (`4b69ac6e`, `9f13eed5`, `c98e4051`, `27582402`) 정독. `html_exec.py`/`board_pack.py`/`localization.py`/`viz_advanced.py` 변경 부분 확인. Sparkline synthetic 고지 부재 확인.
- **PR #4 delta**: 3 commits 639 lines (`2bf10b87`, `915c52a6`, `89a67fe5`) 정독. `tools/cro_digest.py` 신규 219 lines · `tools/report_pack.py` +60 lines CSS · Round 75 실버그 커밋 메시지 정독으로 R39+ errata 부재 발견.
- **tracked 라인 재특정**: `report_pack.py:3762/3788/4354` 실측 확인 (Round 76 +55 line shift 반영, 문법 그대로 LIVE).
- 8개 stable PR head SHA 무변경 → tracked 21건 자동 LIVE.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
