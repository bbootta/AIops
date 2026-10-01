# 전체 저장소 코드 리뷰 — 30주차 (2026-07-29)

**세션 기준 시각:** 2026-07-29 21:12 UTC
**직전 리뷰:** PR #49 (2026-07-28 21:22 UTC, 29주차)
**베이스:** `origin/main` = `281d6017` (**28일째 무변경**)

---

## 1. 감시 활동 요약 (지난 24h)

| 채널 | 델타 | 비고 |
|---|---|---|
| `main` | 커밋 0 | 28일 무변경. `.gitkeep`/`CLAUDE.md`/`.claude/settings.json` 3파일 정지. |
| `claude/risk-management-agent-harness-B9Kxm` | **커밋 +12** | 독립검증 **12차→15차** 사이클 (F-B01·F-C01·F-C02·F-D01 시정) + 산출물 이력 보관 (`553a4a8`). HEAD `b31ab68` → `553a4a8`. 12개 커밋 전부 시정 사이클로 정합. |
| `claude/validation-team-agent-Pw9F5` | **커밋 +6** | 독립검증 응답 **12차~15차** + 12차 응답 보완 + 검증 산출물 정본 이전 (`docs/` → `validation-team-agent/docs/`, 우편함 `response.json` 은 심볼릭 링크). 판정 시퀀스: 경부적합 → 중부적합 → 경부적합 → 경부적합. HEAD `a78620c` → `59032de`. |
| PR #46 (nail simulator) | 커밋 0 | 헤드 `01fc7cb4` 정지 (**53h**). **§6 참조 — 3주 미이행.** |
| PR #38 (호프) | 커밋 0 | 헤드 정지 (~3주). |
| PR #10 (minecraft) | 커밋 0 | 헤드 정지 (~9일). |
| PR #43 (settings.json) | 커밋 0 | 헤드 정지 (5일). |
| PR #48 (nail 3D) | 커밋 0 | hand3d.js 5건 P2/P3 무커밋. |
| PR #30, #32, #34~#45, #47 | 커밋 0 | 각 헤드 무커밋. |

**총평:** 이번 라운드 델타는 **B9Kxm 12커밋 + Pw9F5 6커밋 = 18커밋** 이 두 브랜치에 집중. 두 브랜치는 여전히 open PR 미개설 상태이며 (29주차 §7 재확인). 나머지 27 open PR head 는 **zero-delta**. `main` 28일 무변경 (27→28일).

**주목할 프로세스 사건:** Pw9F5 15차 응답이 B9Kxm 신설 검사 (`tests/test_assumption_claims.py::test_every_generated_sentence_helper_is_wired`) 를 **자기충족 tautology** 로 반증 실험까지 곁들여 지적 (F-E01). 3선의 반증 실험이 warden 리뷰에 앞서 defect 를 정확히 지목한 회차. warden 은 이를 독립 재현하여 신규 P1 로 등재.

---

## 2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| **신규 P0** | **0** (기존 tracked P0 는 유지) |
| **신규 P1** | **2** — ① B9Kxm `tests/test_assumption_claims.py:56` 자기충족 grep (Pw9F5 F-E01 반증 실험 재현) · ② Pw9F5 `RUN-20260630-42.conditional_approval.json` 이 6차 스냅샷 상태로 15차 canonical 위치 점유 (결재 오독 위험) |
| **신규 P2** | **8** — B9Kxm 4건 (`_LINE_FIELDS` 손 열거 · `structure.py` set-검사 사각 · `RECALC_SCOPE` citation 규율 불일치 · `submission_digest` 기본값 빈 문자열) + Pw9F5 4건 (`response.json` target 슬롯 오용 재발 · 우편함 3종 dangling · `test_deliverable_location.py` 편향 커버리지 · F-E01 짝 미확인 통합) |
| **신규 P3** | **8** — B9Kxm 4건 (subprocess grep 상대경로 · `archive.py` 파일경로 강결합 · `coverage_report` 토큰 분모 오염 · FormSpec `sheet_order` 지문 누락) + Pw9F5 4건 (verdict 화이트리스트 `부적합` 누락 · `run_id` 하드코딩 · CHG-0160 컴포넌트 조합 · F-E02 "안전장치 하나 더" 근거 부재) |
| **Regression** | **0** (F-B01·F-C01·F-C02·F-D01 시정 self-consistent; 12→15차 4회 반복 대사 pinned) |
| **Tracked LIVE 유지** | P0×3 **15주** (PR #5 Basel/systemic) · P0 **11주** (PR #4 ERRATA) · P1×5 (PR #10 warden 10주 + PR #10 마을주민 dispose 3주 + PR #38 hope-shooter + PR #38 Unreal 핀 3주 + PR #43 main P1 5일) · **PR #46 P1→P0 `render.js` dead-store 3주 미이행** · **PR #48 P2×2 + P3×3 2주 미이행** · **B9Kxm P2×2 + P3×4 (29주차 신규, 24h 미이행)** · **Pw9F5 P3×1 (target 슬롯, 미해결 재발)** · Pw9F5 P3 "10회" 파일 재작성 과정에서 실질 해소 |
| **⚠ 특기** | **PR #46 `render.js` dead-store 3주 미이행 → §6 warden 프로세스 실패 격상 조건 발동** · **B9Kxm/Pw9F5 두 브랜치 여전히 open PR 미개설** (29주차 §7 재확인) · **Pw9F5 정본 이전이 우편함 4종 중 1종만 링크로 커버 — 나머지 3종 dangling** |

---

## 3. 신규 P1

### [P1-NEW #1] B9Kxm — `tests/test_assumption_claims.py:56-73` 자기충족 grep (F-D01 재발 가능)

**위치:** `tests/test_assumption_claims.py:56-73` (`test_every_generated_sentence_helper_is_wired`)

**소스:**
```py
out = subprocess.run(
    ["grep", "-rn", "coverage_report\\|coverage_sentence",
     "--include=*.py", "risk_lib", "tests"],
    capture_output=True, text=True).stdout
for fn in ("coverage_report", "coverage_sentence"):
    defs = [l for l in out.splitlines() if f"def {fn}" in l]
    uses = [l for l in out.splitlines()
            if fn in l and f"def {fn}" not in l and "import" not in l]
    assert defs, f"{fn} 정의를 찾지 못했다 — 검사가 헛돈다"
    assert uses, f"{fn}이 정의만 있고 호출부가 없다 (지적 F-D01)"
```

**결함:** grep 대상에 `tests/` 가 포함되고 검사 파일 자체 (`tests/test_assumption_claims.py`) 는 docstring · grep 인자 문자열 · `for fn in (…)` 튜플에 `coverage_report` 와 `coverage_sentence` 라는 문자열을 담고 있다. 따라서 `deliverables.py` 의 **실제 호출부를 전부 제거해도** `use` 카운트가 3 (검사 파일 자기 자신) 로 통과한다.

**Pw9F5 반증 실험 (F-E01):** 별도 워크트리에서 `coverage_report` 의 실제 호출부를 전부 삭제 후 pytest 실행 → `def 1 · use 3` 으로 여전히 PASS. use 3 은 전부 이 검사 파일의 텍스트 (`:59` docstring · `:64` grep 인자 · `:67` for-in 튜플). warden 재현 확인.

**failure scenario:** F-D01 이 지적한 것과 **정확히 같은 유형의 배선 부재** (예: 앞으로 신설하는 `pack_index_report` 같은 helper 가 정의만 있고 호출부 0건) 를 이 검사가 잡지 못한다. 하필 그 유형을 지키라고 만든 자리이며, F-602 (통제력 0 인 검증이 쟁점을 지키는 자리에 놓여 있었다) 와 같은 구조. `ADV-CALC-06` (실패 불가능성이 자료가 아니라 구조에서 나온다) 에 정확히 걸림.

**Fix (Pw9F5 3선 권고):** ⓐ grep 에 `--exclude=test_assumption_claims.py` 추가 · ⓑ 문자열 검색 대신 `ast` 로 `Call` 노드만 세기 · ⓒ 검사를 산출 쪽 모듈로 이동. ⓑ 가 가장 견고 (주석·문자열이 호출로 세어지지 않음).

**격상 기준:** Pw9F5 3선이 15차 응답에 게재 (약 2h 전, HEAD `f939743`). B9Kxm 이 24h 내 미시정 시 P0 격상 검토. 검사가 안전장치라 주장하는 자리에서 실제 통제력이 0 인 경우이며, F-602 재발과 같은 등급이므로 **P1 하한**.

---

### [P1-NEW #2] Pw9F5 — `RUN-20260630-42.conditional_approval.json` 이 6차 스냅샷 상태로 15차 canonical 위치 점유

**위치:** `validation-team-agent/docs/independent_validation/RUN-20260630-42.conditional_approval.json` · `.approval.md`

**결함:** 커밋 `59032de` (검증 산출물 정본 이전) 는 두 파일을 **rename-only** 로 새 canonical 위치로 옮겼다 (crc32 등 내용은 불변). 그러나 두 파일의 `request_id` 는 `IVR-68128ECE5694` (**6차**) 이고 현 게이트 응답은 `IVR-8CDB13393503` (**15차**). 파일명에 회차·IVR 접미사가 없어 "이 run 의 조건부 결재 정본" 으로 오독될 수 있다.

**failure scenario:** 결재 심사자가 canonical 경로 (`validation-team-agent/docs/independent_validation/RUN-20260630-42.conditional_approval.json`) 를 열어 **6차 조건** (예: 2026-08-10 이행기한, 특정 라인 재계산 요구) 을 15차 요청 (IVR-8CDB13393503) 의 후속 조건으로 착각. 7~15차에는 인간 결재가 이뤄지지 않았으므로 6차 스냅샷이 canonical 로 남아 있으면 "이미 결재된 상태" 라는 잘못된 안전감 부여. 이는 F-501 계열 (같은 사실이 두 시점에 손으로 적혀 있어 낡음) 과 같은 유형이며, 오히려 rename 이 낡음을 canonical 위치에 재-고정.

**Fix:** ⓐ 파일명에 회차·IVR 접미사 (예: `..._6th_IVR-68128ECE5694.approval.md`) · ⓑ 파일 최상단에 "이 기록은 6차 시점의 스냅샷이며 7~15차에는 별도 결재가 없다" 를 명시. ⓐ 가 게이트 fail-closed 와 호환 (경로가 회차 별이면 미결재 회차는 파일 없음이 자연).

---

## 4. 신규 P2

### [P2-NEW #1] B9Kxm — `risk_lib/regulatory/forms.py:878-890` `_LINE_FIELDS` 손 열거가 자신의 원칙 주석과 정반대

**위치:** `risk_lib/regulatory/forms.py:878-890` (`_LINE_FIELDS`, `_SPEC_FIELDS`)

**결함:** `submission_digest` 는 FormLine 의 속성을 손으로 열거한 `_LINE_FIELDS` 로 해싱한다. 바로 위 주석은 **"열거하면 열거에서 빠진 것이 조용히 뚫린다"** 고 F-301 계열의 원칙을 서술. 그런데 코드 자체가 그 원칙을 위배 — 새 FormLine 속성 (예: `notes`, `provenance_hash`) 을 추가해도 `_LINE_FIELDS` 에 넣지 않으면 지문이 움직이지 않는다.

**failure scenario:** 개발자가 F-D02 (예: 라인별 provenance 강화) 후속으로 FormLine 에 `provenance_hash` 필드 추가 → 서식 CONTENT 는 변했으나 request_id 는 그대로 → 이전 응답이 계속 유효한 것으로 인정 → **F-301 의 네 번째 반복**. 자기 코드 주석이 이 위험을 정확히 예언하고 있음.

**Fix:** `dataclasses.fields(FormLine)` 로 필드를 동적으로 얻어 해싱. FormSpec 도 동일 (P3-NEW #8 과 연결).

---

### [P2-NEW #2] B9Kxm — `risk_lib/regulatory/structure.py:74-88` set 기반 검사가 blind-spot 과소평가

**위치:** `risk_lib/regulatory/structure.py:74-88` (`coverage_sentence`) + `tests/test_form_structure.py:66-79`

**결함:** `coverage_sentence` 가 요청서에 공시하는 blind-spot 지표 `n_folded` 는 "접힌 계열 안에서 라인이 사라져도 통과한다" 만 서술. 그러나 실제 테스트가 `set(...)` 로 비교하기 때문에, 예 `_b2602_3` (외화 LCR·외화 HQLA 교대 서식) 처럼 접히지 않는 서식도 21쌍 중 HQLA 1건 삭제 시 20 HQLA + 21 LCR 이 되어도 set 에는 여전히 2종만 남아 통과한다.

**failure scenario:** structure_keys 가 접지 못하는 교대 라인 계열에서 개별 라인 1건이 삭제되어도 set 비교 검사가 통과 → 공시 문장은 "n_folded=0 이므로 이 유형에서는 사각이 없다" 로 읽히나 실제 사각은 더 큼 → 3선이 공시 문장을 그대로 신뢰하고 지나침.

**Fix:** `set()` 대신 `(form_id, key)` 쌍의 multiset (`Counter`) 비교, 문장도 이에 맞춰 갱신 ("접힌 계열 안" 조건을 넓혀 "이름 다중 등장 서식" 도 포함).

---

### [P2-NEW #3] B9Kxm — `risk_lib/validation/independent.py:38-49` `RECALC_SCOPE` citation 이 F-C02 규율과 어긋남

**위치:** `risk_lib/validation/independent.py:38-49` (`RECALC_SCOPE`) · 응답 `response.json:27,33`

**결함:** F-C02 시정으로 서식 라인 citation 은 "은행업감독규정 제26조 제1항 제1~3호" 로 항·호까지 통일. 그러나 `RECALC_SCOPE` 의 `cet1_ratio` · `total_ratio` citation 은 여전히 "은행업감독규정 제26조" 만 (호까지 없음). 이 값이 3선 응답에 그대로 실려 (RUN-20260630-42.response.json line 27/33), **같은 값에 두 종류의 citation 이 나가는 상태** 가 유지된다.

**failure scenario:** F-A02 가 지적한 "조항 수준 정확성" 요구가 서식 라인에서는 충족되나 recalc_targets 에서는 미충족 → 3선이 같은 실행 안에서 두 표기법을 보게 되어 오히려 자기 인용 규율이 자기 통제하 있는지 의심 → F-C02 근본 원인의 부분 재발.

**Fix:** `RECALC_SCOPE` 항목을 "은행업감독규정 제26조 제1항 제1~3호" 로 맞춘다. `leverage_ratio` 는 제26조 제1항 제4호.

---

### [P2-NEW #4] B9Kxm — `risk_lib/validation/independent.py:487-489` `submission_digest` 기본값 빈 문자열

**위치:** `risk_lib/validation/independent.py:487-489` (`build_request` submission_digest 계산부)

**소스:**
```py
submission_digest=(_submission_digest(built_forms) if built_forms else "")
```

**결함:** 서식을 조립하지 않은 실행에서 지문이 `""` 로 남는다. 이때 서식 인용을 아무리 바꿔도 request_id 가 움직이지 않아 F-301 의 원인이 **조건적으로 되살아난다**. 현재 정상 `build_studio` 경로에서는 `built_forms` 가 항상 넘어오지만, CLI 아닌 임시 진입점·테스트 유틸에서 잊으면 조용히 재현.

**failure scenario:** 개발자가 `build_request(result, portfolio=…, built_forms=None)` 로 임시 호출 → 서식 없이 요청서 생성 → submission_digest="" → 서식 라인 변경이 이 경로에서는 request_id 에 반영되지 않음 → F-301 유형 재발이지만 이번엔 "조건적" 이라 검출 지연.

**Fix:** `built_forms` 를 optional 로 두지 말고 필수 인자로. 서식 없는 실행이 정말 필요하면 명시적 `built_forms=[]` 를 요구하고 이 경우 예외 발생.

---

### [P2-NEW #5] Pw9F5 — `RUN-20260630-42.response.json` findings 의 `target` 슬롯 오용 재발 (PR #49 P3-NEW #5 미해결)

**위치:** `validation-team-agent/docs/independent_validation/RUN-20260630-42.response.json` findings[F-E01..F-E04]

**결함:** 5개 finding 중 4개가 `target: "rwa_final_total"` 로 태그되지만 실제 지적은 배선 검사 (F-E01) · CSV 산출 (F-E02) · 지문경계 (F-E03) · 설계토론 (F-E04) 로 RWA 수치와 무관. `recomputed`/`reported` 도 파일 수 (9, 181) · 호출부 카운트 (0, 3) · 더미 0 을 담아 **RWA 수치 슬롯이 자유 텍스트 카운터로 오용**. 동시에 `recalc_matches.rwa_final_total: true` 라 스키마 문자 그대로 읽는 툴은 "match 인데 finding 있음" 이라는 **모순 신호** 획득. **29주차 P3-NEW #5 와 완전 동일 유형이 재발**.

**failure scenario:** 게이트 다운스트림이 `recomputed`/`reported` 를 `target` 스케일로 해석하면 F-E04 의 `recomputed=181` 이 "RWA 181원" 으로 읽힘 → 리스크 지표가 대규모로 왜곡. `recalc_matches.rwa_final_total: true` 와 F-E04 (181 vs 0) 불일치 신호를 인간 리뷰가 조율해야 함.

**격상:** 29주차 지적 24h 미이행 후 재발이므로 P3 → **P2 격상**. Pw9F5 스키마가 응답이므로 오독 파급이 큼.

**Fix:** `target` 을 finding 성격에 맞게 태그 (`wiring_check` · `pack_deliverable_count` · `signature_boundary` · `design_answer`). 수치 없는 finding 은 `recomputed`/`reported` 를 `null` 로.

---

### [P2-NEW #6] Pw9F5 — 우편함 (mailbox) 4종 중 1종만 링크로 남음 · 나머지 3종 dangling

**위치:** `docs/independent_validation/` (repo 루트 우편함)

**결함:** 정본 이전 후 우편함에는 `RUN-20260630-42.response.json` 심볼릭 링크 1건만 남았다 (`../../validation-team-agent/docs/independent_validation/RUN-20260630-42.response.json`). 나머지 3종 (`opinion.md`, `approval.md`, `conditional_approval.json`) 은 우편함에서 **삭제됐고 어떤 스텁·리다이렉트·README 포인터도 없다**. 커밋 메시지 요약 ("우편함은 링크만 둔다") 은 4종 모두 링크로 남기는 것처럼 오독 가능하나 실제로는 1종만.

**failure scenario:** 외부 참조 (예: 이전 회차 응답에서 opinion.md 를 상대경로로 참조, 인간 검토자가 북마크한 경로) 가 `docs/independent_validation/RUN-20260630-42.opinion.md` 를 열면 **조용히 FileNotFound**. `test_deliverable_location.py` 는 opinion/approval/conditional_approval 의 우편함 스텁 부재를 검사하지 않는다 → 링크 없음 상태가 명시적으로 승인된 셈.

**Fix:** ⓐ 우편함에 `README.md` 또는 `MOVED.md` 를 두어 새 canonical 경로 안내 · ⓑ 4종 모두 우편함에 링크로 남기고 test_deliverable_location 이 4종 전부 검사 (링크 대칭성 확보).

---

### [P2-NEW #7] Pw9F5 — `test_deliverable_location.py` 커버리지 편향 (4종 정본 중 1종만 양방향)

**위치:** `validation-team-agent/tests/test_deliverable_location.py:44-77`

**결함:** 3개 검사 중 `test_deliverables_live_under_the_validation_team_path` 만 4종 SSOT 존재를 확인하고, 링크·페이로드 검사는 `response.json` 1종만. 우편함에 opinion/approval/conditional_approval 이 없다는 상태가 명시적으로 승인된 셈이지만, 나중에 누군가 우편함에 opinion.md 스텁을 만들어 정본과 갈라져도 이 검사가 못 잡는다 → F-501 (사본 갈라짐) 유형 재발 가능.

**failure scenario:** 인간 검토자가 우편함 (repo 루트 docs/) 에 편의상 opinion.md 요약을 복사 → 정본과 다른 텍스트 → 검사 3건 전부 초록 → 낡은 사본으로 결재 논의.

**Fix:** `DELIVERABLES` 튜플 전체를 우편함 존재 · 링크 대상 · 바이트 대조로 순회. 우편함에 "없어야 하는" 파일은 화이트리스트로 명시.

---

### [P2-NEW #8] Pw9F5 — F-E01 짝 검사 `coverage_sentence` 자기충족 여부 미확인 통합

**위치:** `validation-team-agent/docs/independent_validation/RUN-20260630-42.opinion.md` §7 · `.response.json` F-E01

**결함:** opinion.md §7 이 "`coverage_sentence` 쪽 자기충족 여부는 실제 호출부가 여럿 남아 있어 **분리 확인하지 못했습니다** — `coverage_report` 로 반증이 성립했으므로 같은 결함으로 봅니다." 라고 자백. 즉 F-E01 재현·반증은 `coverage_report` 만이고 `coverage_sentence` 는 **유추**. 그런데 `response.json` 은 두 함수에 대한 결함을 한 finding 에 묶어 판정한다.

**failure scenario:** `coverage_sentence` 배선은 실제로는 자기충족이 아닌데 (다른 진짜 호출부가 있어) B9Kxm 이 F-E01 시정으로 ⓑ (ast 기반) 변경 시 오히려 **정상 검사를 망가뜨릴 수 있다**. 잘못된 시정 방향 유도.

**Fix:** F-E01 을 `coverage_report` (확인됨) 와 `coverage_sentence` (미확인) 두 개 finding 으로 쪼개거나, opinion §7 의 미확인 자백을 response.json detail 에도 반영.

---

## 5. 신규 P3

### [P3-NEW #1] B9Kxm — `tests/test_assumption_claims.py:56` subprocess grep 상대경로

**위치:** `tests/test_assumption_claims.py:60`

`subprocess.run(["grep", "-rn", "…", "--include=*.py", "risk_lib", "tests"])` — pytest 를 repo 루트가 아닌 위치에서 실행하면 grep 이 대상 디렉터리를 못 찾아 빈 출력. `defs` 가 비어 "정의를 찾지 못했다 — 검사가 헛돈다" 오탐. 신뢰도 저하.

**Fix:** `Path(__file__).resolve().parents[1] / "risk_lib"` 절대경로 전달 또는 subprocess 대신 `Path.rglob` 스캔.

---

### [P3-NEW #2] B9Kxm — `risk_lib/archive.py:141-155` 이력의 request_id 원본이 파일 경로 관례에 강결합

**위치:** `risk_lib/archive.py:141-155` (`archive`) + `risk_lib/deliverables.py:266-279`

`archive` 가 `out/07_independent_validation/RUN-{asof-nodash}-{seed}.request.json` 을 읽어 `request_id` 를 채운다. `iv_request.write(iv_dir)` 이 파일 이름 규약을 바꾸거나 seed 가 다른 값이 되면 파일 없음 → `req = {}` 로 떨어지고 `VersionInfo` 의 request_id · submission_digest · self_validation 이 모두 빈 값 (에러 없이). 이력.csv 에 빈 요청 식별자 판이 남음.

**Fix:** `archive()` 가 `studio.iv_request` 를 직접 인자로 받거나 (중복 정본 방지), 파일 없을 때 명시적 실패.

---

### [P3-NEW #3] B9Kxm — `risk_lib/validation/doc_figures.py:257-273` `coverage_report` 토큰 분모 오염

**위치:** `risk_lib/validation/doc_figures.py:257-273`

`tokens = len(re.findall(r"[\d,]*\d", text))` 는 표시자 규약을 **설명하는** 코드 예시 · 회차 번호 · 해시 앞자리 등도 다 센다 (mask 는 covered 계산에만 씀). 결과적으로 share 가 실제 커버리지보다 낮게 나와 "통제가 3.7% 밖에 못 덮는다" 같은 오해. 3선 판단 근거로는 쓰지 않으니 P3.

**Fix:** tokens 계산에도 `_mask_code(text)` 를 적용하거나 산문 문장 토큰만 세도록 좁힘.

---

### [P3-NEW #4] B9Kxm — `risk_lib/regulatory/forms.py:895-905` FormSpec `sheet_order` 지문 누락

**위치:** `risk_lib/regulatory/forms.py:895-905` (`_SPEC_FIELDS`)

spec 지문에 `form_id|form_name|frequency|citation|source_domain` 만 넣는다. `sheet_order` 를 바꿔 목차·엑셀 시트 순서를 변경해도 request_id 가 움직이지 않아, 제출본의 순서가 바뀐 것을 이전 응답이 승인 상태로 인정. 값 자체 불변이라 영향 작으나 제출본 아이덴티티 일부가 빠진 것은 사실.

**Fix:** `sheet_order` 도 spec 지문에 포함하거나 (권장), 또는 `KNOWN_ASSUMPTIONS` 에 "시트 순서는 지문에 없다" 를 명시 공시.

---

### [P3-NEW #5] Pw9F5 — `test_deliverable_location.py:76` verdict 화이트리스트 `부적합` 누락

**위치:** `validation-team-agent/tests/test_deliverable_location.py:76`

`assert d["verdict"] in ("적합", "경부적합", "중부적합")` — 스키마상 `부적합` 도 가능한 값이며, 회차 이력에도 `중부적합` 판정 회차가 있다. 미래 회차에서 게이트가 `부적합` 을 담아 응답하면 이 검사가 오히려 실패해 fail-closed 잠금.

**Fix:** 화이트리스트에 `"부적합"` 추가 또는 스키마 파일에서 enum 로드.

---

### [P3-NEW #6] Pw9F5 — `test_deliverable_location.py:77` `run_id` 하드코딩

**위치:** `validation-team-agent/tests/test_deliverable_location.py:77`

`assert d["run_id"] == "RUN-20260630-42"` — 단일 실행 고착. 다음 기준일 실행 (예: `RUN-20260930-42`) 이 오면 이 검사를 매번 손으로 갱신. 유지비 발생.

**Fix:** `run_id` 를 파일명 파싱에서 유도하거나 정규식 (`RUN-\d{8}-\d+`) 로 검증.

---

### [P3-NEW #7] Pw9F5 — `change_manifest.json:2389` CHG-0160 `component` 필드에 두 컴포넌트 조합

**위치:** `validation-team-agent/harness/change_manifest.json:2389`

`"component": "validation-team-agent/docs/independent_validation/ (검증 산출물 정본 이전) + tests/test_deliverable_location.py"` — 스키마는 문자열 하나이나 실질은 두 컴포넌트. 회귀 시 롤백 범위 판단이 흐려짐 (`CHG-0160` 을 부분 롤백 시 대상을 기계 파싱 불가).

**Fix:** CHG-0160a (정본 이전) · CHG-0160b (테스트 신설) 두 항으로 분리하거나 배열 필드로 스키마 확장.

---

### [P3-NEW #8] Pw9F5 — `RUN-20260630-42.opinion.md` §5.1 · F-E02 "안전장치 하나 더 붙었다" 진술 근거 부재

**위치:** `.response.json` F-E02 · `opinion.md` §5.1

"약속이 0건이면 '검사가 헛돈다' 로 실패시키는 안전장치까지 있다. 이는 3선이 14차 §9.2 에서 권고한 통제와 같은 것이며, **권고보다 안전장치가 하나 더 붙었다**." — 그 안전장치 검사 (`test_assumptions_do_not_promise_missing_artefacts`) 가 실제 파일·라인 인용 없이 "건전하다" 로 단정. F-E01 이 짝 검사를 자기충족으로 판정한 상태이므로 옆 검사에도 반증 실험이 필요.

**Fix:** 그 짝 검사에도 반증 실험 (가정 문장을 임의로 조작해 실제 실패 유도) 을 넣거나 상세를 response.json 에 명시.

---

## 6. ⚠ 특기 #1: PR #46 `render.js` dead-store — **3주 미이행 → warden 프로세스 실패 격상 조건 발동**

**26주차 (2026-07-14) 최초 지적:** `js/render.js:597`, `:601`, `:606` — `g.push(` → `out.push(` (`g` 는 `:584` 에서 이미 join·push 되어 이후 push 는 dead-store).

**격상 이력:**
- 26주차: 최초 P1
- 27주차: 1주 미이행
- 28주차 (2026-07-27): 2주 미이행 → §7 "P1 dead-store 는 다음 라운드에서 P0 격상 검토" 명문 규정 도입
- 29주차 (2026-07-28): **P0 격상 확정**. 3주째 미이행 시 warden 프로세스 실패 격상.
- **30주차 (2026-07-29, 오늘): 3주 미이행 확정 → warden 프로세스 실패 격상 조건 발동.**

**현재 상태:** HEAD `01fc7cb4` 그대로 (2026-07-27 14:30:47 UTC, ~53h 무커밋). `js/render.js:580-615` 재확인 (`git show origin/claude/nail-simulation-program-i79qef:js/render.js`):

```
584: out.push(g.join(''));                                              // g 여기서 join·push
   ...
597 근방: g.push('<g filter="url(#soft1)" clip-path="url(#clip-...      // ridges — dead-store
601 근방: g.push('<path d="' + path + '" fill="none" stroke=...         // side stroke — dead-store
607 근방: g.push('<path d="' + G.nailPath(fg, d, 1.6) + ...             // env reflection — dead-store
```

**warden 프로세스 실패 격상 근거:**
1. 지시가 3주 (26/27/28/29 → 30) 미이행.
2. 격상 규정이 26주차부터 4단계 (신규 P1 → 1주 후보 → 2주 P0 → 3주 프로세스 실패) 모두 명문화된 상태에서 각 단계마다 저자가 다른 브랜치로 관심 이동.
3. Fix cost: **3줄 문자열 편집**. 저자 부재 문제가 아니라 우선순위 부재 문제.
4. Visual regression 이 사용자 대면 프로덕션 코드 (`nail-simulator`) 이며 자동 lint 로 잡히지 않음.

**격상 판정:** **warden 프로세스 실패 격상** (P0 유지 + 프로세스 이슈 티어). 4주째면 external escalation 검토 (인간 결재 · policy 조정).

**병행 권고:** `no-unused-expressions` 유형의 정적 lint 를 nail-simulator 파이프라인에 도입 (28주차 반복 권고, 30주차 재반복).

---

## 7. ⚠ 특기 #2: B9Kxm / Pw9F5 두 브랜치 여전히 open PR 미개설 · 델타 100% 집중

29주차 §7 재확인. 이번 라운드 델타 100% (18 커밋) 도 두 브랜치에서만 발생. 두 브랜치 모두 여전히 open PR 없음, 과거 merged PR 없음. warden 이 open PR head 만 순회했다면 §3 · §4 의 신규 P1×2 + P2×8 + P3×8 은 리뷰 시야 밖.

이번 회차는 warden 이 두 브랜치를 정면 리뷰에 편입 (29주차와 동일). 그러나 **정책 명문화 없이 예외 처리로 4주 연속 유지 중**. 다음 회차 (31주차) 에도 두 브랜치가 계속 델타의 대부분을 만든다면 policy 조항으로 성문화 필요.

**권고:** `AIMS_POLICY.md` (B9Kxm 존재) 에 "agent-team internal branches" 조항 명시 · Pw9F5 에도 대칭 명시 · warden trigger 를 open-PR-only 에서 "all-branches-with-recent-delta" 로 확장.

---

## 8. ⚠ 특기 #3: Pw9F5 정본 이전이 우편함 4종 중 1종만 링크로 커버 (P2-NEW #6 참조)

`59032de` 커밋 메시지 요약 ("우편함은 링크만 둔다") 이 4종 모두를 링크로 남기는 것처럼 오독 가능하나 실제로는 `response.json` 1종만 심볼릭 링크. 나머지 3종 (opinion/approval/conditional_approval) 은 삭제. §4 P2-NEW #6 에서 P2 로 등재.

**추가 위험:** `RUN-20260630-42.conditional_approval.json` 이 6차 스냅샷 (`IVR-68128ECE5694`) 인 채 15차 canonical 위치 점유 — §3 P1-NEW #2 로 등재. 이전 자체가 rename-only 였고, 파일 회차 접미사 부재로 결재 오독 위험 증폭.

**권고:** 이전 · 스냅샷 · 링크의 3중 실수가 한 커밋에 결합됐으므로 이전 프로토콜 자체를 문서화 (`validation-team-agent/harness/relocation_protocol.md`).

---

## 9. Tracked LIVE — 재확인

| PR / 브랜치 | 항목 | 방치 | 이번 라운드 상태 |
|---|---|---|---|
| **PR #46** | **`render.js` dead-store (P0)** | **3주** | **⚠ warden 프로세스 실패 격상 · §6** |
| PR #48 | `hand3d.js:361-365` buildHand 첫 진입 프리즈 (P2) | 2주 | 커밋 없음 |
| PR #48 | `hand3d.js:773-778` pick() 매 클릭 재할당 (P2) | 2주 | 커밋 없음 |
| PR #48 | `hand3d.js:672-676` wheel 페이지 스크롤 트랩 (P3) | 2주 | 커밋 없음 |
| PR #48 | `app.js:240-246` Blob URL revoke race (P3) | 2주 | 커밋 없음 |
| PR #48 | `hand3d.js:650-677` pointercancel 미처리 (P3) | 2주 | 커밋 없음 |
| PR #5 | Basel 기업 B RW 1.00 → 1.50 (P0) | 15주 | 커밋 없음 |
| PR #5 | SRISK `(1-k)` 인자 누락 (P0) | 15주 | 커밋 없음 |
| PR #5 | CoVaR own-loss mask (P0) | 15주 | 커밋 없음 |
| PR #4 | CHG-0143 재사용 + ERRATA-2026-07-14 (P0) | 11주 | 커밋 없음 |
| PR #10 | warden 벽투과 sonic LOS (P1) | 10주 | 커밋 없음 |
| PR #10 | 마을주민/동물 GPU 리소스 미해제 (P1) | 3주 | 커밋 없음 |
| PR #38 | `hope-ue/Content/build_content.py` 핀 이름 추측 (P1) | 3주 | 커밋 없음 |
| PR #38 | hope-shooter `src/main.js:445` wall-clip / 4-path dispose | 3주 | 커밋 없음 |
| PR #38 | Unreal C++ ~2400 LOC 미검증 | 5라운드 | 커밋 없음 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 5일 | main SHA 28일 무변경, 노출창 지속 |
| B9Kxm (29주차) | `cross_form.py:56` BR-14/2100 (P2) | 24h | cross_form.py 미변경 |
| B9Kxm (29주차) | `catalog.py:694-696` reserve_shortfall 라벨 (P2) | 24h | catalog.py 미변경 |
| B9Kxm (29주차) | `independent.py:255` `_headline` 키명 (P3) | 24h | 키명 그대로 |
| B9Kxm (29주차) | `forms_ext.py:395-396` br_npl tautology (P3) | 24h | 코드 그대로 |
| B9Kxm (29주차) | `forms.py:504-506` BR-11 aggregate tautology (P3) | 24h | 코드 그대로 |
| B9Kxm (29주차) | `provenance.py:474-484` check_strength_sentence 값 노출 (P3) | 24h | 코드 그대로 |
| Pw9F5 (29주차) | `response.json` target 슬롯 오용 (P3 → **P2 격상 재발**) | 24h | 신규 F-E01~04 에서 재발 · §4 P2-NEW #5 참조 |
| Pw9F5 (29주차) | "10회" 진술 (P3) | 24h | 파일 재작성 (12→15차 응답으로 대체) 과정에서 사라짐 → **실질 해소** |

---

## 10. 다음 라운드 (31주차) 권고

**즉시 (24h):**
1. **PR #46 `render.js:597, 601, 606` 3줄 → `out.push`** — **3주째 미이행 · warden 프로세스 실패 격상 확정**. 4주째면 external escalation.
2. B9Kxm `tests/test_assumption_claims.py:56-73` 자기충족 grep 시정 (P1-NEW #1, ast 기반 권장).
3. Pw9F5 `RUN-20260630-42.conditional_approval.json` · `.approval.md` 파일명에 회차·IVR 접미사 (P1-NEW #2).
4. B9Kxm `RECALC_SCOPE` citation 을 F-C02 규율에 맞추기 (P2-NEW #3, 1분 편집).
5. Pw9F5 `response.json` target 슬롯 재발 시정 (P2-NEW #5, 스키마 재정의).

**단주기 (1주):**
6. B9Kxm `_LINE_FIELDS` 손 열거 → `dataclasses.fields()` (P2-NEW #1).
7. B9Kxm `structure.py` set → Counter (P2-NEW #2).
8. B9Kxm `submission_digest` 기본값 예외화 (P2-NEW #4).
9. Pw9F5 우편함 3종 dangling 대응 (P2-NEW #6, README 또는 4종 링크).
10. Pw9F5 `test_deliverable_location.py` 커버리지 확장 (P2-NEW #7, 4종 대칭).
11. Pw9F5 F-E01 짝 검사 반증 실험 또는 finding 분리 (P2-NEW #8).

**기한 초과 (미이행 시 다음 라운드 격상):**
12. PR #5 Basel · SRISK · CoVaR (P0, **15주**).
13. PR #4 CHG-0143 + ERRATA (P0, **11주**).
14. PR #10 warden LOS 체크 (P1, **10주**).
15. PR #10 마을주민/동물 dispose 4경로 (P1, 3주).
16. PR #38 `build_content.py` 핀 검증 (P1, 3주).
17. PR #43 `.claude/settings.json` commit SHA 핀 1줄 (P1, 5일).
18. PR #48 hand3d.js P2×2 + P3×3 (2주).
19. B9Kxm 29주차 P2×2 + P3×4 (24h 미이행).

**프로세스:**
20. `AIMS_POLICY.md` / Pw9F5 대칭 문서에 "agent-team internal branches" 조항 명문화 (§7, 29주차 반복 권고).
21. PR #46 dead-store lint (`no-unused-expressions`) 도입 (28주차·29주차·30주차 반복 권고).
22. Pw9F5 `relocation_protocol.md` 신설 (§8).

---

## 11. 리뷰 방법 (재현 가능성)

- **소스:** `github.com/bbootta/AIops` 모든 branch (`main` = `281d6017`, 28일 무변경).
- **방법:** PR #49 의 truth table 을 baseline 으로 하여 각 branch head SHA 및 committer date 가 2026-07-28 21:12 UTC 이후인지로 delta 판별.
- **델타 발견 브랜치:**
  - `origin/claude/risk-management-agent-harness-B9Kxm` (**12 커밋** · Δ `b31ab68..553a4a8`) — Python 위험관리 라이브러리 (`risk_lib/**`) + 신규 `structure.py` · `doc_figures.py` · `archive.py` · 신규 3종 테스트 (`test_archive.py`, `test_assumption_claims.py`, `test_citations.py`) + 새 baseline (`citation_baseline.json`, `citation_clause_baseline.json`) + 산출물 이력 (`산출물/2026-06-30/20260729_v01/**`). `git diff b31ab68..553a4a8` 로 정적 분석.
  - `origin/claude/validation-team-agent-Pw9F5` (**6 커밋** · Δ `a78620c..59032de`) — 12~15차 응답 + 정본 이전 (`docs/` → `validation-team-agent/docs/`). `git diff a78620c..59032de` 로 정적 분석 + B9Kxm HEAD `553a4a8` 소스와 교차 검증.
- **Δ 없는 25 open PR head:** 별도 재검사 없음 (SHA 무변경 = 결함 상태 무변경).
- **크로스 체크:** Pw9F5 F-E01 자기충족 반증 실험 (`coverage_report` 실제 호출부 제거 후 tests/test_assumption_claims 통과 여부) 을 warden 이 코드 정독 및 grep 대상 자기포함 여부로 독립 재현 → 반증 성립 확인. B9Kxm submission_digest `bd27dd11…` 이동 (14→15차 서식 무변경이라 정합) 도 확인.
- **병렬 리뷰 에이전트:** B9Kxm 델타 · Pw9F5 델타 각각 general-purpose subagent 로 분산 후 warden 이 finding 통합·격상 판정. 두 agent 가 독립적으로 도출한 finding 이 서로를 refute 하지 않음 (F-E01 만 두 agent 가 동일 지적, warden 이 P1 로 최종 격상).

---

_본 문서는 리뷰 보고서 전달용. **머지 금지.** 아래 PR body 요약도 동일 내용._
