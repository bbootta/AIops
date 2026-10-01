# 전체 저장소 코드 리뷰 — 36주차 (2026-08-04)

**직전 리뷰:** PR #55 (2026-08-03 21:28 UTC) 이후 ~24h.
**리뷰 시점:** 2026-08-04 21:xx UTC.
**결과 헤드라인:** **zero-delta round — 6/6 tracked HEAD 무커밋 (B9Kxm / Pw9F5 / PR #38 / PR #10 / PR #46 / main).** B9Kxm 35주차 대확장(9커밋 · +5,312 LOC · 신규 P1×4/P2×6/P3×4)의 즉시 항목 **8건 전건 미이행 24h**. Pw9F5 활동 48h 정지. **PR #46 dead-store 9주 확정** (blob `0e0288c9…` 8일 무커밋). 신규 P0/P1/P2/P3 = 0/0/0/0. Regression 0. Escalation 1 (PR #46 8→9주). Reclassification 0. **Tracked LIVE 69건 유지.**

---

## §1. 감시 활동 (24h)

| 브랜치 / PR | 직전 HEAD | 신규 HEAD | 신규 커밋 | 무커밋 기간 |
|---|---|---|---|---|
| **B9Kxm** (PR #5) | `d47f866e` | `d47f866e` | **0** | **24h** (35주차 대확장 이후 24h 정지) |
| **Pw9F5** (PR #4) | `29eb4243` | `29eb4243` | **0** | **48h+** (마지막 커밋 08-02 15:25 UTC) |
| PR #38 (khpuk3) | `a9bbf3b5` | `a9bbf3b5` | 0 | 48h+ |
| PR #10 (tqv3ii) | `844fb48b` | `844fb48b` | 0 | **4일** |
| **PR #46** (i79qef) | `01fc7cb4` | `01fc7cb4` | **0** | **8일** (blob SHA `0e0288c9…` 불변) |
| `main` | `281d6017` | `281d6017` | 0 | **34일** |
| 기타 표본 (#30/#32/#48) | (변동 없음) | — | 0 | 표본 감시 |

**핵심 판정:**

1. **B9Kxm 24h 정지.** 35주차 대확장 delta (9커밋 · +5,312/-113 LOC) 이후 활동 없음. 35주차 신규 P1×4 (§4.2) · P2×6 (§4.3) · P3×4 (§4.4) 및 34주차 재분류 P1×1 + P2×2 (§4.2/§4.3) **13건 전건 미이행**. 하루라는 짧은 window 이나 즉시 항목 8건이 "다음 라운드 즉시 항목" 으로 지시된 상태에서 활동 정지 자체가 특기 사항.
2. **Pw9F5 48h 무커밋.** 34주차 CHG-0162 (`reg_rules.py`) · CHG-0163 이후 48시간 정지. `conditional_approval.json` P1 **7일 미이행** (35주차 6일 → +1). 34주차 신규 P3×2 (`reg_rules.py` verify KeyError · replaced_by 체인) 미이행.
3. **PR #46 dead-store 9주 확정.** blob `0e0288c9…` 8일 무커밋. 31주차 external escalation 검토 발동 후 **5주째 무액션**. warden 사이클 non-forcing 완전 확정 후 대안이 필요하다는 35주차 판정 그대로 유효.
4. **신규 P0/P1/P2/P3 = 0/0/0/0.** zero-delta 라운드는 정의상 신규 finding 부재. tracked LIVE 재확인만 수행 — 69건 유지.
5. **PR #10 4일 · PR #38 48h · main 34일 무변경.** 계약된 감시 대상 전체가 static.

---

## §2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **0** |
| 신규 P2 | **0** |
| 신규 P3 | **0** |
| Regression | **0** |
| Escalation | **1** — PR #46 8주 확정 → **9주 확정** |
| Reclassification | **0** |
| Tracked LIVE 재확인 | **69** (P0×8 · P1×12 · P2×22 · P3×27, 35주차 대비 변동 없음) |

---

## §3. 35주차 즉시 항목 (8건) 이행 상태

35주차 §8 "다음 라운드 즉시 항목" 을 그대로 대조. **HEAD 불변이므로 8건 전건 미이행이 자동 확정.**

| # | 항목 | 파일 | 판정 | 이행 |
|---|---|---|---|---|
| 1 | B9Kxm P1-9 (9300 borrower 방향) | `code_scope.py:103` | 2줄 시정 | **미이행** |
| 2 | B9Kxm P1-10 (fund SA-CCR PFE ~4.4×) | `funds.py:245` | `saccr_input` 재사용 | **미이행** |
| 3 | B9Kxm P1-11 (NaN "nan" 버킷) | `exposure_agg.py:37` | `.astype(str)` 제거 | **미이행** |
| 4 | B9Kxm P1-12 (SEC-SA K_A NaN 방어) | `securitisation.py:381` | line 386 대칭 방어 | **미이행** |
| 5 | B9Kxm P2×6 + P3×4 | 5파일 (~40줄) | catalog FK 등 | **미이행** |
| 6 | PR #46 external escalation | 절차 재설계 | 검토 5주째 | **미이행** |
| 7 | Pw9F5 `reg_rules.py` P3×2 + conditional_approval P1 | `reg_rules.py` / `conditional_approval.json` | 활동 재개 시 우선 | **미이행** (활동 48h 정지) |
| 8 | B9Kxm 17주 tracked P0×3 (Basel B RW · SRISK · CoVaR) | `rwa_sa.py` / `srisk.py` / `covar.py` | 최장 tracked | **미이행** |

24h 짧은 window 감안 시 8건 전건 미이행이 "warden 사이클 실패" 신호는 아니나, 35주차 대확장 라운드 직후 활동 정지는 **`저자 = 시정 주체` 가정이 성립하지 않는다** 는 30주차 판정 재확인.

---

## §4. B9Kxm 24h 정지 · 35주차 finding 지속성 재검증

**HEAD `d47f866e` 불변 → diff 부재 → 35주차 신규 finding 13건 (P1×4 · P2×6 + 재분류 2 · P3×4 + 재분류 1) 전건 LIVE.**

35주차 신규 finding 은 fresh-eyes 심층 검토로 도출된 것이며, 24h 무변경 window 에서 새로 발화하거나 소멸하지 않는다. 다만 zero-delta 라운드는 **35주차 판정을 한 라운드 늦게 재확인하는 검증 기회** — 다음 항목을 명시적으로 확인했다:

- **P1-9 (9300 방향):** `_ACCT_CCF["9300"]="commitment_gt_1y"` 매핑 유지. `credit_scope()` 이 9300 계정을 `in_scope=True`, `ccf_rate=0.40` 로 처리하는 경로 유효. 오늘 이 매핑을 참조하는 화면·엔진 사용자가 있다면 phantom EAD 를 생성한다는 판정 그대로.
- **P1-10 (fund SA-CCR PFE):** `saccr_trade_view` 가 raw notional 을 넘기는 로직 그대로. supervisory duration/delta 미적용. IRS/CRS/OPT 계열 fund 파생의 add-on 이 여전히 4.4× 저평가.
- **P1-11 (NaN "nan"):** `pd.cut(..., right=False).astype(str)` 그대로. 요구불예금·영구채·상한 초과값 → `"nan"` 문자열 버킷.
- **P1-12 (SEC-SA K_A NaN):** line 381 에 방어 없음. 세그먼트 하나가 NaN 이면 SSFA 지수 항까지 전파.
- **P2×6 + P3×4:** market risk_factor · LCR HQLA blanket · catalog FK · UNRATED > CCC- · ECL fillna · swaption DV01 δ · retail_other 라벨 · IRBA flag · ThreadPool pre-SA-fill · rw_before_floor 캡-후 라벨 · `_clip_mt` NaN · `sec_erba_rwa` resec — 12건 (P2 8 + P3 4) 전건 LIVE.

**35주차 §4.6 병렬 실행 안전성 판정** (RNG offset 개별 · DataFrame copy 후 mutation · 오늘 writer-reader collision 없음) 도 그대로 유효. 신규 파일 진입 없음.

---

## §5. Pw9F5 48h 무커밋 · conditional_approval P1 7일

**HEAD `29eb4243` 불변, 마지막 커밋 2026-08-02 15:25 UTC — 리뷰 시점 대비 54시간.** 34주차 CHG-0162 (`reg_rules.py` 규제 룰 카탈로그 신설) · CHG-0163 (§2 8부문 재선언) 이후 활동 정지.

**Tracked LIVE 지속:**
- CHG-0143 + ERRATA (P0) — 14주
- `conditional_approval.json` 6차 canonical (P1) — **7일** (35주차 6일 → +1) + P2×4 + P3×4
- 33주차 P3×3 (`validation_memory`) — LIVE
- 34주차 P3×2 (`reg_rules.py` verify KeyError · replaced_by 체인) — LIVE

**신규 finding 없음.** 활동 재개 시 §3 항목 7 우선 처리 예정.

---

## §6. PR #46 격상 — dead-store **9주 확정** · warden non-forcing 5주 무액션

**격상 이력 연장:**

| 주차 | 판정 |
|---|---|
| 26주차 | P1 최초 (render.js dead-store × 3) |
| 28주차 | P0 검토 발동 |
| 29주차 | P0 격상 |
| 30주차 | warden 프로세스 실패 격상 |
| 31주차 | external escalation 검토 조건 발동 |
| 32~35주차 | 5→6→7→8주 미이행 |
| **36주차** | **9주 확정** — HEAD `01fc7cb4` **8일 무커밋**, blob SHA `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` 유지 |

**판정:** warden 사이클 자체가 forcing 함수 없음 **9주 연속** 실증. 31주차 external escalation 검토 발동 후 **5주째 무액션**. 35주차 다음 라운드 즉시 항목 6번 ("PR #46 external escalation 실행") 미이행. 절차 자체 재설계 미착수.

**36주차 판정 강화:** 9주 = 60일 이상. 자기수정형 warden 사이클로는 도달 불가. 절차가 아니라 외부 채널(승격·정지·저자 재할당)이 필요하다는 결론이 계량적으로 완전 확정됨.

---

## §7. PR #38 · PR #10 · main · 표본 감시

- **PR #38 (khpuk3):** HEAD `a9bbf3b5` 48h+ 무커밋 (35주차 24h → +24h). 34주차 skinned mesh 커밋 이후 활동 없음. tracked LIVE — `build_content.py` P1×2 · hope-shooter dispose · Unreal C++ 미검증 유지. 신규 finding 없음.
- **PR #10 (tqv3ii):** HEAD `844fb48b` **4일 무커밋** (35주차 3일 → +1). tracked LIVE — 동물/마을주민 dispose 누수 R8 확장 (P1 · 7주) · 동물 재질 per-instance jitter (P2 · 10일) · warden 벽투과 (P1 · **14주** — 최장 활동 브랜치 tracked P1).
- **main:** HEAD `281d6017` **34일 무변경** (35주차 33일 → +1). PR #42 (Codex plugin) 머지 후 정지. 실질적 릴리즈 채널이 아님.
- **PR #48 (28주차 자체 리뷰):** hand3d.js P2×2 + P3×3 · 7주 미이행. 자체 리뷰 PR 은 감시만.
- **PR #30 (ISO 42001) / PR #32 (mecha chameleon):** 활동 없음 · 표본 감시.

---

## §8. Tracked LIVE 총괄 (36주차)

| PR / 브랜치 | 항목 | 방치 (36주차 갱신) |
|---|---|---|
| **PR #46** | **`js/render.js` dead-store (P0)** | **9주 확정** (blob 8일 무커밋) |
| PR #10 | 동물/마을주민 dispose 누수 R8 확장 (P1) | 8주 |
| PR #10 | 동물 재질 per-instance jitter (P2) · warden 벽투과 (P1) | 10일 / **14주** |
| PR #5 (B9Kxm) | Basel B RW · SRISK · CoVaR own-loss mask (P0×3) | **19주** (최장 tracked P0) |
| PR #5 (B9Kxm) | 29주차 P2×2 + P3×4 · 30주차 P1+P2×4+P3×4 | active |
| PR #5 (B9Kxm) | 34주차 재분류 P1×1 + P2×2 (§4.2/§4.3) | 24h+ |
| PR #5 (B9Kxm) | 35주차 신규 P1×4 · P2×6 · P3×4 (§4.2/§4.3/§4.4) | **24h** |
| PR #4 (Pw9F5) | CHG-0143 + ERRATA (P0) | 15주 |
| PR #4 (Pw9F5) | conditional_approval 6차 canonical (P1) + P2×4 + P3×4 | **7일** |
| PR #4 (Pw9F5) | 33주차 P3×3 (validation_memory) · 34주차 P3×2 (reg_rules) | 48h~72h |
| PR #48 | hand3d.js P2×2 + P3×3 | 7주 |
| PR #38 | build_content.py · hope-shooter dispose · Unreal C++ 미검증 | 7주 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 11일 |

**합계:** P0=**8** · P1=**12** · P2=**22** · P3=**27** = **69건 LIVE** (35주차와 동일 · 신규/재분류/격상해소 전무 · 방치 +1일씩 이월).

**최장 방치 갱신:**
- 최장 tracked P0: **B9Kxm Basel B RW · SRISK · CoVaR** — **19주** (35주차 18주 → +1)
- 최장 tracked P1: **PR #10 warden 벽투과** — **14주** (35주차 13주 → +1)
- 최장 확정: **PR #46 dead-store** — **9주 확정** (35주차 8주 → +1)

---

## §9. 다음 라운드 (37주차) 즉시 항목

35주차 즉시 항목 8건 이월 (전건 미이행 이유가 24h 무커밋). 우선순위 그대로 유지:

1. **B9Kxm P1-9 (9300 direction)** — 2줄 시정. `_ACCT_CCF` 에서 9300 제거 + `credit_scope()` in_scope 규칙에 방향 컬럼 추가.
2. **B9Kxm P1-10 (fund SA-CCR PFE)** — `saccr_trade_view` 를 `derivatives.saccr_input` 재사용.
3. **B9Kxm P1-11 (NaN "nan" 버킷)** — `_bucket()` `.astype(str)` 제거, Categorical 유지.
4. **B9Kxm P1-12 (SEC-SA K_A NaN 방어)** — line 386 대칭 방어 3줄.
5. **B9Kxm P2×6 + P3×4** — 시정 총 ~40줄. catalog FK 선언 시 회귀 test 다수 예상.
6. **PR #46 external escalation 실행** — 9주 확정 · **5주 무액션**. warden 사이클 non-forcing 완전 확정. 외부 채널 (승격·정지·저자 재할당) 필요.
7. **Pw9F5 `reg_rules.py` P3×2 + `conditional_approval.json` P1** — 48h+ 무커밋 지속. 활동 재개 시 우선.
8. **B9Kxm 19주 tracked P0×3 (Basel B RW · SRISK · CoVaR)** — 최장 tracked P0 연령 갱신. 35주차 대확장에도 미터치.

**신규 대비 조기 항목:**
- 36주차 zero-delta 자체는 특기 사항이 아니나, 35주차 대확장 직후 저자 활동 정지는 30주차 판정("저자 = 시정 주체" 가정 미성립) 재실증. 37주차에서 B9Kxm 활동 재개 여부가 warden 사이클 유효성의 부분 지표.
- Pw9F5 활동 재개 여부. 48h+ 정지 · `conditional_approval.json` P1 7일 미이행. 다음 라운드 활동 재개 시 conditional_approval 재선언 여부 즉시 확인.

---

## §10. 리뷰 방법 · 재현

**감시 대상 (36주차):**
- 6개 tracked HEAD (B9Kxm/Pw9F5/PR #38/PR #10/PR #46/main) 최신 SHA 조회 (`list_pull_requests state=all`).
- PR #46 blob SHA 대조 (`get_file_contents path=js/render.js ref=01fc7cb4`) → `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` = 35주차 대조값과 동일.
- 표본 PR (#30/#32/#48) HEAD 무변동 확인.
- zero-delta 확정 후 심층 분석 skip · 35주차 finding 지속성만 명시적 재확인.

**신규 finding 판정 기준 (변동 없음):**
- **P0:** 실행 시 반드시 관측되는 결함 + 산출값 최소 1자리 이동. **0건.**
- **P1:** 실행 시 관측되는 결함이거나 phantom 값 생성 · 규제 산출 오차 배수급. **0건.**
- **P2:** 라벨 mismatch · 감사 추적 왜곡 · 감시 blind spot · 특정 시나리오 발화. **0건.**
- **P3:** defense-in-depth, 오늘 미발화이나 계약/원장 무결성 저해 잠재. **0건.**

**zero-delta 라운드 정의:**
- 모든 tracked HEAD 가 직전 라운드 HEAD 와 동일.
- diff 부재로 신규 코드에서 새 finding 이 발화하지 않음.
- 이월 검증 (§8 방치 카운트 +1) + 확정 격상 (§6 PR #46 8→9주) + 즉시 항목 이월 (§9) 만 수행.

**재현 절차:**
```
# 6개 HEAD 대조 (직전 라운드 대비)
for pr in 5 4 38 10 46; do
  # HEAD sha == 35주차 §1 표의 값?
  gh pr view $pr --json headRefOid,updatedAt
done
git ls-remote origin main   # 281d6017 유지 여부

# PR #46 blob 대조
gh api repos/bbootta/AIops/contents/js/render.js?ref=01fc7cb4 --jq .sha
# → 0e0288c93564fda41e881e87bfbc5f6c6a85ae28 (35주차 = 36주차)
```

---

## §11. 결론

**Δ:** 36주차 는 6/6 tracked HEAD 무커밋 · **zero-delta round**. 35주차 대확장 (9커밋 · 5,312 LOC · 원장 4종 신설) 직후 B9Kxm 활동 정지. Pw9F5 는 34주차 CHG-0162 이후 48h+ 정지. PR #38 · #10 · #46 · main 은 계속 static.

**35주차 즉시 항목 8건 전건 미이행 (24h window 자연 결과)** — window 자체가 짧아 자동으로 "warden 사이클 실패" 를 뜻하지 않으나, 35주차 신규 P1×4 (규제 오산출 3건 + 데이터 함정 1건) 는 규제 산출값 왜곡을 야기하므로 다음 라운드 활동 재개 시 우선 순위 최상. **저자 활동 정지 자체가 "저자 = 시정 주체" 가정의 재실증 불성립 신호.**

**PR #46 9주 확정 · warden non-forcing 5주 무액션.** 60일 이상 자기수정 사이클로 도달 불가함이 계량적으로 완전 확정. 외부 채널(승격·정지·저자 재할당)로 전환 필요.

**Tracked LIVE 69건 유지.** 신규/재분류/격상해소 전무. 방치 카운터만 +1일씩 이월. 최장 tracked P0 (**B9Kxm Basel B RW / SRISK / CoVaR — 19주**) · 최장 tracked P1 (**PR #10 warden 벽투과 — 14주**) · 최장 확정 (**PR #46 dead-store — 9주**) 전건 연령 갱신.

**36주차 특기:** zero-delta 자체는 통상. 다만 35주차 대확장 (B9Kxm) 과 34주차 대전 (Pw9F5 CHG-0162) 두 활동 브랜치가 동시에 정지한 상태는 25주차 이후 처음. 37주차에서 두 브랜치 중 하나라도 활동 재개하지 않으면 dormant 판정 필요 (Pw9F5 는 33주차 시점에 이미 "정식 dormant" 판정 후 34주차 복귀 이력 있음).

**머지 금지** — 리뷰 보고서 전달용 draft.
