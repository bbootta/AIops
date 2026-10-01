# 전체 저장소 코드 리뷰 — 29주차 (2026-07-28)

**세션 기준 시각:** 2026-07-28 21:12 UTC
**직전 리뷰:** PR #48 (2026-07-27 21:12 UTC, 28주차)
**베이스:** `origin/main` = `281d6017` (무변경, **27일 방치**)

---

## 1. 감시 활동 요약 (지난 24h)

| 채널 | 델타 | 비고 |
|---|---|---|
| `main` | 커밋 0 | 27일 무변경. `.gitkeep`/`CLAUDE.md`/`.claude/settings.json` 3파일 정지. |
| `claude/risk-management-agent-harness-B9Kxm` | **커밋 +10** | 독립검증 **7차→11차** 사이클, 대손준비금 (F-601·F-602·F-603) 시정 → 8/9차 지적 시정 → 9차 EL 차감 실제 자본 반영 (F-802) → 10차 F-901 시정 (BF202 라인 복원 + 구조 회귀 통제 신설). HEAD `b31ab68`. |
| `claude/validation-team-agent-Pw9F5` | **커밋 +6** | 독립검증 응답 **8~11차** + 응답 보완 2건. 판정 시퀀스: 중부적합 → 중부적합 → 경부적합 → 중부적합 → 경부적합. HEAD `a78620c`. |
| PR #46 (nail simulator) | 커밋 0 | 헤드 `01fc7cb4` 정지 (~30h). **§6 참조 (2주 미이행).** |
| PR #38 (호프) | 커밋 0 | 헤드 정지 (~2주). |
| PR #10 (minecraft) | 커밋 0 | 헤드 정지 (~8일). |
| PR #43 (settings.json) | 커밋 0 | 헤드 정지 (4일). |
| PR #30, #32, #34~#45, #47, #48 | 커밋 0 | 각 헤드 무커밋. |

**총평:** 이번 라운드 델타는 **위험관리 하니스 (B9Kxm) 와 검증팀 (Pw9F5) 두 브랜치가 하루에 10 + 6 커밋 · 5회 상호 검증** 으로 집중. 두 브랜치 모두 open PR 이 없어 warden 시야 밖 개발이었으나 정면 리뷰 편입. 나머지 27 open PR head 는 무커밋 (`zero-delta`).

---

## 2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| **신규 P0** | **0** |
| **신규 P1** | **0** (신규 결함 기준; 회차 내 fix-then-verify 사이클로 대부분 자기해소) |
| **신규 P2** | **2** — B9Kxm `cross_form.py` "보통주자본비율" invariant 이 stress-path 산출물 참조 · B9Kxm `catalog.py` `reserve_shortfall` 컬럼 스키마 라벨이 F-601 회귀 재초대 |
| **신규 P3** | **6** — B9Kxm 4건 (`_headline` 키명, `br_npl` tautology, BR-11 tautology, `check_strength_sentence` self-null risk) + Pw9F5 2건 (`response.json` target 슬롯 오용, "10회" 진술 과다) |
| **Regression** | **0** (F-601·F-802·F-901 시정 self-consistent; 회차 내 4번째 층까지 pinned) |
| **Tracked LIVE 유지** | P0×3 **14주** (PR #5 Basel/systemic) · P0 **10주** (PR #4 ERRATA) · P1×5 (PR #10 warden 9주 · PR #10 마을주민 dispose 2주 · PR #38 hope-shooter · PR #38 Unreal 핀 2주 · PR #43 main P1 4일) · **PR #46 P1 `render.js` dead-store 2주 미이행** · **PR #48 P2×2 + P3×3 1주 미이행** |
| **⚠ 특기** | **PR #46 `render.js` dead-store 2주 연속 미이행 → §6 P0 격상 검토 후보 확정** · **B9Kxm/Pw9F5 두 브랜치는 PR 미개설 상태로 개발** (warden 시야 외) |

---

## 3. 신규 P2

### [P2-NEW #1] B9Kxm — `cross_form.py` "보통주자본비율" invariant 이 stress-path 산출물을 참조 → 향후 회귀 자폭

**위치:** `risk_lib/regulatory/cross_form.py:41` (`INVARIANTS` 등록), `risk_lib/regulatory/forms_ext.py:_br14`

**소스:**
```py
("보통주자본비율", ("BR-01","3100"), ("BR-21","1000"), ("BR-14","2100"))
```

- `BR-01/3100` = `r.bis.cet1_ratio` (as-of 시점 CET1 비율, 진짜 값).
- `BR-21/1000` = 같은 값의 다른 서식 참조.
- `BR-14/2100` = **`float(row["trough_cet1"])` (baseline 시나리오의 프로젝션 트로프)**. 현재 `StressPath("baseline", peak_severity=0.0)` 이 flat 이라 as-of 와 동일한 값이 나올 뿐, 정의상 다른 물건.

**failure scenario:** `risk_lib/stress/path.py` 에 baseline flat-이 아닌 어떤 조정 (배당 유출, 이익잉여금 성장 등) 이 도입되는 순간 `trough_cet1` (baseline) ≠ `r.bis.cet1_ratio`. `cross_form_보통주자본비율` 이 매 run FAIL 하지만 **BR-01/3100 은 옳음** — 대사가 잘못된 것 → 3선 시간 대량 소모.

**Fix:** ① `("BR-14","2100")` 을 invariant 에서 제거 (as-of 규제비율 대사만 유지), 또는 ② 값이 정의상 `r.bis.cet1_ratio` 인 다른 라인으로 교체.

---

### [P2-NEW #2] B9Kxm — `catalog.py` `reserve_shortfall` 컬럼 스키마 라벨이 F-601 회귀를 재초대

**위치:** `risk_lib/datamodel/catalog.py:694-696` (컬럼 정의), `rdm_asset_quality` 카탈로그.

**소스:**
```
column: "reserve_shortfall"
description: "대손준비금 소요액"
citation:    "은행업감독규정 제29조 제2항 — max(0, 최저적립액 − IFRS9 충당금)"
```

**F-601 이 확립한 것 (0302741, fdc37bd):**
- 은행업감독규정 제29조 제2항의 **대손준비금 소요액** 은 aggregate `max(0, Σmin_p − Σifrs9)` 이며,
- per-exposure `Σmax(0, min_p − ifrs9)` 은 서로 다른 물건 (건별 미달액 합 ≠ 규정 소요액).

**그런데 `rdm_asset_quality` 컬럼은 여전히 per-exposure 값을 담고, 라벨·인용조항은 aggregate 것을 가리킨다.** 새 서식 개발자가 이 컬럼을 재사용하면서 `.sum()` 을 붙이면 정확히 F-601 이 정정한 잘못된 계산이 다시 발생.

**failure scenario:** 신규 materializer 가 `df["reserve_shortfall"].sum()` 을 대손준비금 소요액 헤드라인으로 publish → 현 포트폴리오 기준 ~+47.3B 초과 (2.41× 정답 33.58B). 새 `test_form_structure.py` 는 form-line-code + line-name 만 프리즈 하므로 이 스키마 오용은 잡히지 않음.

**Fix (2단):**
1. 컬럼 이름을 `"per_exposure_reserve_gap"` 으로 변경, description 을 `"건별 대손준비금 미달액 (참고)"` 로,
2. citation 을 `datamodel.materialize_detail.reserve_requirement()` 로 (조항 인용은 aggregate 를 계산하는 함수에 붙어 있어야 함).

---

## 4. 신규 P3

### [P3-NEW #1] B9Kxm — `independent.py:255` `_headline["reserve_shortfall"]` 키명이 F-601 개념을 계속 홍보

**위치:** `risk_lib/validation/independent.py:255`, `RECALC_TARGETS` @ line 54.

Key 는 여전히 `"reserve_shortfall"` / `"대손준비금 소요액"` 인데 value 는 이제 `_reserve_required(aq)` (aggregate). 3선 감사자가 `aq["reserve_shortfall"].sum() == headline["reserve_shortfall"]` 로 자체 재계산을 시도하면 aggregate ≠ per-exposure sum 이라 false-positive mismatch (+47.3B) 로 잘못된 finding 등록.

**Fix:** ① 키명을 `reserve_required` 로 변경 (스키마 파괴적, 별도 회차) 또는 ② `RECALC_TARGETS[9]` 에 F-601 주석 명시 ("headline value 는 aggregate; column 은 per-exposure").

---

### [P3-NEW #2] B9Kxm — `forms_ext.py:395-396` `br_npl` 비율 대사가 tautology (같은 소스 참조)

**위치:** `risk_lib/regulatory/forms_ext.py:395-396`

`_ratio_check("고정이하여신비율 = 고정이하 ÷ 총여신", L, "2100", "2000", "1000")` — `L["2100"]` 은 위쪽에서 `npl / total` 로 세팅됨. `L["2000"]`, `L["1000"]` 도 같은 `aq[...].sum()` 소스. 따라서 `expected(2000/1000) == actual(2100)` 은 항상 성립 (F-703 자백 주석 있음).

**failure scenario:** 데이터 버그가 `aq["balance"]` 을 전체 스케일링 (단위 사고 등) → NPL, watch, total 이 함께 이동 → 두 비율 대사 모두 PASS → BR-NPL 서식이 잘못된 잔액으로 게시.

**Fix:** independent source 로 재계산 — 예 `total` 은 raw portfolio, `npl` 은 `dq["default_flag"] × balance` 등.

---

### [P3-NEW #3] B9Kxm — `forms.py:504-506` BR-11 aggregate-basis check 가 tautology

**위치:** `risk_lib/regulatory/forms.py:504-506`, sibling check 508-509.

`FormCheck("대손준비금 = 최저적립액 − 충당금 (합계 기준)", max(0, _val(L,"1000") − _val(L,"2000")), _val(L,"3000"), 1.0)` — 라인 1000, 2000, 3000 모두 `rr = reserve_requirement(t)` 에서 세팅되고 `rr["required"] = max(0, rr["min_provision"] − rr["ifrs9_provision"])`. 대사는 정의상 `max(0, a-b) == max(0, a-b)`. 이는 주석에도 자백 ("자료로는 틀릴 수 없다").

**failure scenario:** 누군가 `reserve_requirement()` 를 다른 컬럼에서 pull 하도록 편집 → 세 라인 함께 이동 → 대사 PASS 하지만 제출 숫자는 오답. `test_reserve_requirement_check_can_actually_fail` 은 injected fake 라인만 시험, 실 빌더 경로 미검증.

**Fix:** `expected` 를 정말 다른 소스로 계산 — `min_p` 는 `t["balance"] × t["min_provision_rate"]` 로, `ifrs` 는 `ecl_result` 로. 그러면 rr wiring 회귀가 대사에 걸림.

---

### [P3-NEW #4] B9Kxm — `provenance.py:474-484` `check_strength_sentence` 가 "쓰지 말라" 지표를 문장에 그대로 내보냄

**위치:** `risk_lib/regulatory/provenance.py:474-484`

Sentence 는 `"양변이 정확히 같은 검증이 X건이나 정상 소계 대사도 맞으면 일치하므로 의심 지표로 쓸 수 없다"` 라며 숫자 X 를 그대로 노출. 결재/감사가 X 를 "N tautologies remain" 로 인용할 위험 (저자 의도는 null-signal).

**Fix:** 문장에서 값을 빼고 dict 반환에만 남겨 개발자 검사용으로 한정.

---

### [P3-NEW #5] Pw9F5 — `response.json` `target`/`recomputed`/`reported` 슬롯이 구조적 finding 에 오용

**위치:** `docs/independent_validation/RUN-20260630-42.response.json` (F-A01, F-A03, F-A04, F-A05)

F-A01 이 `target: "rwa_final_total"`, `recomputed: 5896, reported: 5844` 로 세팅되어 있으나 이는 **서식 라인 인벤토리 카운트** (두 asof 시점). F-A02 `target: "reserve_shortfall"`, `recomputed: 2, reported: 1` 은 **citation 조항 수**. 동시에 `recalc_matches.rwa_final_total = true`, `recalc_matches.reserve_shortfall = true` → 스키마 문자 그대로 읽는 툴은 "recalc matches 인데 finding 이 있음" 이라는 모순 신호 획득.

**Fix:** 구조적/문서적 finding 에 별도 target 슬롯을 두거나, value-mismatch 아닌 경우 `recomputed`/`reported` 를 `null` 로.

---

### [P3-NEW #6] Pw9F5 — F-A02 "3선도 10회에 걸쳐 보지 못했다" 진술이 파일 이력과 불일치

**위치:** `docs/independent_validation/RUN-20260630-42.response.json` F-A02, `RUN-20260630-42.opinion.md §5.5`

`risk_lib/regulatory/forms_fss_asset.py` 는 `eafdf00` 에서 최초 도입, `forms_fss_overseas_a.py` 는 `cd876b8` 에서 도입 (라운드 4–6 사이). 국내/해외 citation-조항 divergence 는 최대 라운드 5–10 즉 **6회** 관측 가능. "10회" 는 과장.

**Fix:** "6회에 걸쳐" 또는 "제5차부터 10차까지" 로 표현 정정. §10 표는 이미 6-row 이므로 텍스트만 수정.

---

## 5. Tracked LIVE — 재확인

| PR / 브랜치 | 항목 | 방치 | 이번 라운드 상태 |
|---|---|---|---|
| **PR #46** | **`render.js` `g.push` 사후-join 누락 (P1)** | **2주** | **⚠ LIVE — 아래 §6 참조** |
| PR #48 | `hand3d.js:361-365` buildHand 첫 진입 프리즈 (P2) | 1주 | 커밋 없음 |
| PR #48 | `hand3d.js:773-778` pick() 매 클릭 스토리지 재할당 (P2) | 1주 | 커밋 없음 |
| PR #48 | `hand3d.js:672-676` wheel 페이지 스크롤 트랩 (P3) | 1주 | 커밋 없음 |
| PR #48 | `app.js:240-246` Blob URL revoke race (P3) | 1주 | 커밋 없음 |
| PR #48 | `hand3d.js:650-677` pointercancel 미처리 (P3) | 1주 | 커밋 없음 |
| PR #5 | Basel 기업 B RW `1.00 → 1.50` (P0) | 14주 | `risk_lib/capital/rwa_sa.py:42-49` — 커밋 없음 |
| PR #5 | SRISK `(1-k)` 인자 누락 (P0) | 14주 | `systemic.py:61` — 커밋 없음 |
| PR #5 | CoVaR own-loss mask (P0) | 14주 | `systemic.py:96-105` — 커밋 없음 |
| PR #4 | CHG-0143 재사용 + ERRATA-2026-07-14 (P0) | 10주 | 커밋 없음 |
| PR #10 | warden 벽투과 sonic LOS (P1) | 9주 | `minecraft/index.html:3008-3020` — 커밋 없음 |
| PR #10 | 마을주민/동물 GPU 리소스 미해제 (P1) | 2주 | 커밋 없음 |
| PR #38 | `hope-ue/Content/build_content.py` 핀 이름 추측 (P1) | 2주 | 커밋 없음 |
| PR #38 | hope-shooter `src/main.js:445` wall-clip / 4-path dispose | 2주 | hope-shooter 미터치 |
| PR #38 | Unreal C++ ~2400 LOC 미검증 | 4라운드 | 커밋 없음 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 4일 | main SHA 무변경, 노출창 지속 |

---

## 6. ⚠ 특기 #1: PR #46 `render.js` dead-store — **2주 미이행 → P0 격상 검토 확정**

**28주차 지시 (재요약):** 3 `g.push(` → `out.push(` 3줄 변경. `js/render.js:597`, `:601`, `:606`.

**현재 상태 (HEAD `01fc7cb4`, `js/render.js` 재검증):**

```
584: out.push(g.join(''));                                          // g 여기서 join
   ...
597 근방: g.push('<g filter="url(#soft1)" clip-path="url(#clip-...  // ridges — dead
601 근방: g.push('<path d="' + path + '" fill="none" stroke=...     // side stroke — dead
607 근방: g.push('<path d="' + G.nailPath(fg, d, 1.6) + ...         // env reflection — dead
```

**저자가 지난 24h 에 한 일:** PR #46 커밋 0. 다른 곳으로 관심 이동.

**28주차 진단이 "27→28 회귀" 를 예언한대로 정확히 유지:** 26주차 PR #45 P1 fix (`form_ids.py`) 가 25주간 유일한 tracked-fix 였고, 27→28 에서 회귀, 28→29 에서도 회귀.

**§2 특기 규칙에 따른 격상 근거:**
- 28주차 §7 "리뷰 지시가 1주 이상 미이행된 P1 은 다음 라운드에서 P0 격상 검토" 명문 규정.
- 2주 미이행 확정.
- 격상 근거 재확인:
  - Visual defect 는 사용자 대면 (렌더된 SVG 3개 요소 누락).
  - 자동 lint 로 잡히지 않아 회귀 재발 가능성 지속.
  - Fix cost: 3줄 문자열 편집.

**격상 판정:** **P1 → P0 격상** (visual regression 이 사용자 대면 프로덕션 코드에서 2주 무개입). 3주째 미이행 시 warden 프로세스 실패 신고.

---

## 7. ⚠ 특기 #2: B9Kxm / Pw9F5 두 브랜치가 PR 미개설 상태로 활발 개발

**관측:** 이번 라운드 델타의 100% 는 두 브랜치에서 발생 (16 커밋). 두 브랜치 모두 **open PR 이 없음** — GitHub PR 리스트 상 head 로 등록된 PR 없음, 과거 merged PR 도 없음. Warden 이 open PR head 만 순회할 경우 시야 밖.

**구조:**
- `claude/risk-management-agent-harness-B9Kxm` (agents · risk_lib · pyproject · tests · docs) — 하니스 본체.
- `claude/validation-team-agent-Pw9F5` (docs/independent_validation · harness · Python 미포함) — 상대 브랜치의 산출물에 대한 독립 검증 opinion 생성.
- 두 브랜치가 하루 5회 상호 request → opinion → fix 사이클을 성공적으로 회전 (7차 → 8차 → 9차 → 10차 → 11차).

**진단:** 이는 **정상 동작** (agent-team internal harness, warden 대상 아님) 일 수 있으나, 리뷰 관측 채널로서는 **누락 위험**. 만약 이 두 브랜치를 warden 이 놓쳤다면 이번 라운드의 §3 P2×2 + §4 P3×6 는 리뷰 시야 밖.

**권고:**
- 두 브랜치가 warden 대상인지 확인 (draft PR 로 등록 or agent-team internal 마킹).
- 만약 internal 이면 별도 리뷰 루트 명문화 (`AIMS_POLICY.md` 에 "agent-team internal branches" 조항 명시).

---

## 8. 다음 라운드 (30주차) 권고

**즉시 (24h):**
1. **PR #46 `render.js:597, 601, 606` 3줄 → `out.push`** — **P0 격상** (2주 미이행). 3주째면 warden 프로세스 실패 격상.
2. B9Kxm `cross_form.py:41` "보통주자본비율" invariant 에서 `("BR-14","2100")` 제거 (P2).
3. B9Kxm `catalog.py:694-696` `reserve_shortfall` 컬럼 rename + citation 재조준 (P2).
4. B9Kxm 4개 P3 fix (`_headline` 키명 주석 · `br_npl` independent source · BR-11 independent source · `check_strength_sentence` 값 제거).
5. Pw9F5 2개 P3 fix (`response.json` target 슬롯 · "10회" → "6회").
6. PR #48 P2×2 + P3×3 착수 (nail-simulation 3D 초기 진입 UX).

**기한 초과 (미이행 시 다음 라운드 격상):**
7. PR #5 Basel · SRISK · CoVaR (P0, **14주**).
8. PR #4 CHG-0143 + ERRATA (P0, **10주**).
9. PR #10 warden LOS 체크 (P1, **9주**).
10. PR #10 마을주민/동물 dispose 4경로 (P1, 2주).
11. PR #38 `build_content.py` 핀 검증 (P1, 2주).
12. PR #43 `.claude/settings.json` commit SHA 핀 1줄 (P1, 4일).

**프로세스:**
13. B9Kxm / Pw9F5 두 브랜치의 warden 상태 확인 (§7).
14. PR #46 dead-store lint 규칙 도입 (`no-unused-expressions` 등) — 28주차 반복 권고.

---

## 9. 리뷰 방법 (재현 가능성)

- **소스:** `github.com/bbootta/AIops` 모든 branch (`main` = `281d6017`).
- **방법:** PR #48 의 truth table 을 baseline 으로 하여, 각 branch head SHA 및 committer date 가 2026-07-27 21:12 UTC 이후인지로 delta 판별.
- **델타 발견 브랜치:**
  - `origin/claude/risk-management-agent-harness-B9Kxm` (10 커밋 · Δ `3e56c36..b31ab68`) — Python 위험관리 라이브러리 (`risk_lib/**`) + 테스트 + validation 산출물. `git diff 3e56c36..b31ab68` 로 정적 분석.
  - `origin/claude/validation-team-agent-Pw9F5` (6 커밋 · Δ `576e0c2..a78620c`) — 검증팀 산출물 (`docs/independent_validation/**` + `harness/**`). `git diff 576e0c2..a78620c` 로 정적 분석 + B9Kxm HEAD `b31ab68` 소스와 교차 검증 (숫자 · 라인 카운트 · challenge count).
- **Δ 없는 25 open PR head:** 별도 재검사 없음 (SHA 무변경 = 결함 상태 무변경).
- **크로스 체크:** Pw9F5 opinion 이 인용한 수치 (290 서식 · 5,844 라인 · 33.58B 대손준비금 · 25 challenges · 1,052 tests) 를 B9Kxm HEAD 에서 직접 재계산 → 모두 일치.

---

_본 문서는 리뷰 보고서 전달용. **머지 금지.** 아래 PR body 요약도 동일 내용._
