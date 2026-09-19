# 전체 저장소 코드 리뷰 — 39주차 (2026-08-07)

**직전 리뷰:** PR #60 (2026-08-06 21:16 UTC) 이후 ~24h.
**리뷰 시점:** 2026-08-07 21:xx UTC.
**결과 헤드라인:** **delta round — B9Kxm +5 커밋 (로직 파일 광범위 변경 · 외부 데이터엔지팀 검토 반영 + 요건 감사 시정 5건 + Pack v03 편성 + 20차 IV 요청).** Pw9F5 · PR #57 · PR #58 · PR #46 · PR #10 · PR #38 · main 전건 무커밋 (46h~37일). 38주차 near-zero-delta 이후 24h 만에 B9Kxm 대확장 재개, 그러나 **warden 지정 즉시 항목과 정렬 없음** (8주 연속). **Pw9F5 46h+ 무커밋 · 48h 임박 → 정식 dormant 재판정 조건 임박**. **PR #46 dead-store 12주 확정** (blob `0e0288c9…` 11일 무커밋 · warden non-forcing 7주 무액션). 신규 P0=0 · **P1=1** (test_req_trace.py 표면 검사 결함, self-declared) · **P2=1** (IV 요청 단독 무효화 프로토콜, F-F04 파생) · **P3=1** (README `sha256sum -c` clone-only 실패, self-declared). Self-fixed 5건 (외부 검토 반영, 미추적). Regression 1 (37주차 P2 BF602 basis 미시정 지속). Escalation 1 (PR #46 11→12주 확정). Reclassification 1 (38주차 P3 IV 백로그 深化 → 20차 open 1건으로 표면 감소, 프로토콜 관점 P2 격상). **Tracked LIVE 76건** (38주차 73 + 신규 P1×1·P2×1·P3×1 · reclass 그대로).

---

## §1. 감시 활동 (24h)

| 브랜치 / PR | 직전 HEAD | 신규 HEAD | 신규 커밋 | 무커밋 기간 |
|---|---|---|---|---|
| **B9Kxm** (PR #5) | `05ad5dc3` | **`e4dfef07`** | **+5** | 활동 대확장 (로직 변경) |
| **Pw9F5** (PR #4) | `75c01af4` | `75c01af4` | 0 | **~46h** (48h 임박 · dormant 재판정) |
| PR #38 (khpuk3) | `a9bbf3b5` | `a9bbf3b5` | 0 | ~5일 |
| PR #10 (tqv3ii) | `844fb48b` | `844fb48b` | 0 | **7일** |
| **PR #46** (i79qef) | `01fc7cb4` | `01fc7cb4` | **0** | **11일** (blob `0e0288c9…` 불변) |
| PR #57 (pyic2r) | `a28774a0` | `a28774a0` | 0 | 54h+ |
| PR #58 (dhk8gr) | `8ae2ba90` | `8ae2ba90` | 0 | 53h+ |
| `main` | `281d6017` | `281d6017` | 0 | **37일** |
| 기타 표본 (#30/#32/#48) | (변동 없음) | — | 0 | 표본 감시 |

**핵심 판정:**

1. **B9Kxm 대확장 재개 (+5 커밋).** 로직 파일 광범위 변경 — 요건 감사 시정 5건 · Pack v03 산출 · IV 요청 3단 재발부 (18차→19차→20차) · 외부 데이터엔지팀 검토 반영 6건. 24h 자원 규모는 34주차 dormant 취소 3커밋 · 35주차 대확장 9커밋에 비견. **역대 상위 3위권 delta 라운드.**
2. **그러나 warden 지정 즉시 항목과 정렬 없음.** 저자 시정은 (a) 외부 데이터엔지팀 검토 (F-1/F-2/F-6-3/F-6-4/F-6-8) 6건 (b) 요건 감사 자체 시정 5건 (TRACE 판정 gap, CCR-EC 누락, stress buffers hardcoded, crm_rating.grade type, ECL TTC/PIT gap). **34주차 재분류 P1 · 35주차 신규 P1×4 · 37주차 P2 (BF602 basis) 는 여전히 미시정** — 8주 연속 warden↔저자 계약 미정렬 확대 재확인.
3. **Pw9F5 46h+ 무커밋 · 48h 임박.** 33주차 dormant 판정 기준 48h+에 도달 임박. 리뷰 시점(2026-08-07 21:xx UTC) 기준 마지막 커밋(2026-08-05 16:34 UTC) 대비 ~53h → **48h 초과 확정 → 정식 dormant 재판정 시행**.
4. **B9Kxm이 스스로 자기공시한 P1 후보 결함 1건 · P3 후보 1건.** (a) `tests/test_req_trace.py` 요건 증빙 검사가 소스 grep만 하고 실행/수집 확인 없음 → **한 번도 실행되지 않은 테스트가 요건 증빙으로 통과**. (b) README `sha256sum -c` clone-only 사용자 실패 (팩 208 파일 중 git 추적 7개, 정책상 의도지만 클론 사용자 미상정). 둘 다 HANDOFF §1/§4.2에 기록만, tracked 미등재. **§5 신규 P1·P3 등재.**
5. **B9Kxm IV 요청 3단 재발부 관측 (F-F04 파생).** 18차 IVR-CEB70642E24B → 지문 이동으로 자체 무효화 → 19차 IVR-397316300BCF → 다시 자체 무효화 → 20차 IVR-8F60B82AE085. 3선(Pw9F5)이 응답 못 한 상태에서 B9Kxm 단독으로 요청 무효화·재발부. 16차 IV 응답의 F-F04 지적(응답 없는 요청에 회차 선부여) 파생 변형. **§5 신규 P2 등재.**
6. **PR #46 dead-store 12주 확정.** blob `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` 11일 무커밋 (38주차 10일 → +1). warden 사이클 non-forcing **7주 무액션** (38주차 6주+1일 → +1일). ~78일 방치 · warden 자기수정 도달 불가 완전 재재확인.
7. **PR #57/PR #58 · PR #10 vs PR #58 정본 결정 24h 무진전.** 38주차 승계.
8. **B9Kxm 요건 감사 시정 5건의 자기공시 특성.** `a9d9bb7` 커밋 메시지 자체가 이전 판의 진단 오류를 여러 건 자기정정 — "확률가중 ECL이 버려진다"(18차 IV 진단)가 실은 report.py/board_pack.py에서 이미 라벨 병기 중이었음을 자기공시 · 실제 문제는 3선 재계산 스코프. 자기공시가 warden 등재 파이프라인의 주된 경로임을 재확인 (37주차→38주차 확대 판정 재재확인).

---

## §2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **1** — B9Kxm `tests/test_req_trace.py` 표면 grep 검사, 실행/수집 확인 없음 (self-declared by `be2a9264`, HANDOFF §1 기록만 tracked 미등재) |
| 신규 P2 | **1** — B9Kxm IV 요청 단독 무효화·재발부 프로토콜 (F-F04 파생, 18→19→20차 3단 재발부, self-declared) |
| 신규 P3 | **1** — B9Kxm README `sha256sum -c` clone-only 사용자 실패 (팩 208 파일 중 git 추적 7개, self-declared by `e4dfef07`) |
| Self-fixed (미추적) | **5** — 외부 데이터엔지팀 검토 F-1/F-2/F-6-3/F-6-4/F-6-8 (재현성 hash salt · 인제스트 silent drop · RWA 대사 동어반복 · rdm_dq_result PK 부재 · ARCHITECTURE.md 카탈로그 드리프트, 전건 동일 라운드 fix) |
| 거버넌스 flag | **1** — PR #58 vs PR #10 정본 결정 미이행 (37주차 승계 · 24h 무진전 · 총 53h+ 무진전) |
| Regression | **1** — B9Kxm 37주차 자기공시 P2 (BF602 2020~2050 4라인 basis) Pack v03 편성됐으나 basis 열 미시정 (2일 → 3일 이월) |
| Escalation | **1** — PR #46 11주 확정 → **12주 확정** |
| Reclassification | **1** — 38주차 신규 P3 (Pw9F5 IV 응답 백로그 2건 深) → 20차 open 1건으로 표면 감소, 프로토콜 관점 F-F04 파생 P2로 격상 |
| Tracked LIVE 재확인 | **76** (P0×8 · P1×13 · P2×24 · P3×31, 38주차 73 + 신규 P1×1·P2×1·P3×1) |

---

## §3. 38주차 즉시 항목 (13건) 이행 상태

38주차 §10 그대로 대조. **HEAD 이동은 B9Kxm 만 · 광범위 로직 변경 있으나 warden 지정 항목과 정렬 없음 · 13건 중 0건 정합 · 1건 자기공시 (BF602 basis 미시정 지속) · 12건 미이행**.

| # | 항목 | 파일 | 판정 | 39주차 이행 상태 |
|---|---|---|---|---|
| 1 | PR #46 external escalation 실행 | 절차 재설계 | 12주 확정 · 7주 무액션 | **미이행** — blob 11일 무커밋 |
| 2 | PR #10 vs PR #58 정본 결정 | 거버넌스 | 24h 무진전 | **미이행** — 53h+ 무진전 |
| 3 | Pw9F5 IV 응답 백로그 (17차/18차) | Pw9F5 IV 응답 | 개시 | **미이행** — Pw9F5 46h+ 무커밋 · B9Kxm이 18/19차 지문 이동으로 자체 무효화 후 20차 재발부 |
| 4 | B9Kxm P1-9 (9300 direction) | `code_scope.py:103` | 2줄 시정 | **미이행** — e4dfef07 diff 미포함 |
| 5 | B9Kxm P1-10 (fund SA-CCR PFE) | `funds.py:245` | saccr_input 재사용 | **미이행** |
| 6 | B9Kxm P1-11 (NaN "nan" 버킷) | `exposure_agg.py:37` | `.astype(str)` 제거 | **미이행** |
| 7 | B9Kxm P1-12 (SEC-SA K_A NaN 방어) | `securitisation.py:381` | line 386 대칭 방어 | **미이행** |
| 8 | B9Kxm 20주+1일 tracked P0×3 (Basel B RW · SRISK · CoVaR) | `rwa_sa.py` / `srisk.py` / `covar.py` | 최장 tracked | **미이행** → **20주+2일** |
| 9 | B9Kxm 자기공시 P2 (BF602 basis) | `forms_fss_overseas_b.py` | 4라인 basis 시정 | **부분→미이행 확정** — Pack v03 편성됐으나 basis 열 시정 커밋 없음 (3일 이월) |
| 10 | B9Kxm P2×6 + P3×4 (35주차 승계) | 5파일 (~40줄) | catalog FK 등 | **미이행** |
| 11 | Pw9F5 F-F02 시정 파급 (37주차 신규 P3) | 자체검증 스트레스 검사 | Tier1/총자본 비교 추가 | **미이행** — 브랜치 무커밋 |
| 12 | Pw9F5 F-F03 EL-충당금 SA북 분리 | EL vs 적격충당금 로직 | CRE35.4 IRB 한정 | **미이행** — 브랜치 무커밋 |
| 13 | Pw9F5 `conditional_approval.json` P1 · reg_rules P3×2 · 33주차 validation_memory P3×3 | Pw9F5 다수 | 활동 재개 시 | **10일 미이행** (38주차 9일 → +1) |

**판정:** 13건 중 0건 정합 시정. B9Kxm 은 24h 자원을 (a) 외부 팀 검토 반영 (b) 자체 요건 감사 시정 (c) Pack v03 편성 (d) IV 요청 재발부 에 배분. **warden 지정 즉시 항목 이행률: 0/13 (0.0%)** — 32~38주차 이어 **39주차 확정 재확인** (8주 연속 0/N).

**저자 계약과 warden 지정의 미정렬 판정:** 30주차 최초 판정 → 32/33/34/35/36/37/38주차 연속 재확인 → **39주차 8주차 확정 재확인**. **자기공시→다음 라운드 도전 예약** 파이프라인이 warden 등재 파이프라인을 대체하는 구조가 굳어지고 있음.

---

## §4. B9Kxm delta 5커밋 상술

### §4.1 `a9d9bb7` (2026-08-06 23:05) — 요건 감사 시정 5건

**성격:** 저자 자체 요건 감사 통해 발견한 산출/문서 결함 5건 동시 시정. **자기공시 파이프라인의 대표 사례.**

**시정 내역:**
1. **TRACE 조용한 기본값** — `TRACE.get(rid, ("미반영", (), ""))`가 75/131건 명시 판정 + 56건 기본값 → "판정 미반영"과 "판정 안 됨"이 같은 칸. TRACE +11 · UNASSESSED 45 신설. 반영 59→66 · 부분 16→24 · 미반영 56→41.
2. **CCR-EC 누락** — `ccr_total`이 `_stage_icaap`의 신용 경제자본에 빠짐. B2914 Credit VaR가 CCR을 빼고 합산하면서 9000 라인이 그 배제를 명시. CCR 라인(1275) 신설.
3. **stress/trace.py buffers 하드코딩** — 바로 위 주석이 "파이프라인과 같은 입력으로 세워야 한다"라고 명시. `meta["buffers"]`로 실제 값 넘기게 시정.
4. **crm_rating.grade 타입 오류** — 카탈로그 string 선언인데 `RatingGrade(...)` 객체. 다른 8곳은 `.grade` 사용. `test_crm_rating_grades_come_from_master_scale`가 그 상태를 계약으로 고정 (검사가 코드와 같은 오해 공유).
5. **ECL PIT/TTC gap** — `RECALC_SCOPE`와 감독 서식이 TTC만, PIT 3선 재계산 안 됨. RECALC_SCOPE 12→13종 (ecl_weighted_total 추가). ecl_ttc_pit_gap 신설 — TTC 975억 · PIT 1,350억 · uplift +38.4%.

**GOLDEN 재고정 6 · PASS 49→51 · 헤드라인 무변 · 테스트 1,082 passed · 1 skipped.**

**리뷰 판정:**
- 시정 5건 모두 self-fixed, warden tracked 미등재.
- 그러나 시정 유형이 **자기충족 검사 유형** (§5.4 참조) — RWA 대사 동어반복 (`floor_addon = final − sum` 후 `sum + addon == final` 항상 통과)이 다음 커밋 `e4dfef07`에서 별도 F-6-3으로 재지적된 것과 유사 유형.
- 신규 finding **0건 (모두 self-fixed)**. 유형만 §5.4에 기록.

### §4.2 `50d2524` (2026-08-06 23:09) — 19차 IV 요청 (IVR-397316300BCF)

**성격:** `a9d9bb7`의 지문 이동으로 18차 IVR-CEB70642E24B 자동 stale → 19차 재발부. 서식 라인 5,910→5,911. 반영 59→66 · 부분 16→24 · 미반영 56→41.

**자기정정 (특기):** 18차 진단 "확률가중 ECL이 버려진다"가 틀렸음 자기공시. report.py/board_pack.py에서 이미 라벨 병기 중. 실제 문제는 3선 재계산 스코프 (RECALC_SCOPE 12→13).

**리뷰 판정:**
- IV 요청 자체 무효화·재발부는 **F-F04 파생 프로토콜 결함** — §5.2 참조 (신규 P2).
- 18차 진단 자기정정은 self-fixed (미추적) — 유형만 기록.

### §4.3 `00733cd` (2026-08-07 00:30) — Pack v03 편성

**성격:** asof 2026-06-30 · 수행일자 2026-08-07. 서식 290 · 라인 5,911 · 제출본 지문 `de37f4814855e734…` · 코드 `50d2524650c8`. 자체검증 PASS 62 · WARN 6 · FAIL 0. **GATE 부적합 유지 — fail-closed, 결재 상신 불가.**

**리뷰 판정:**
- Pack v03 는 Pack v02 판을 요건 감사 5건(a9d9bb7) 반영 + 19차 IV 요청(50d2524) 반영으로 재산출한 판.
- 15차 이후 3선 응답을 받은 판 없음 — 판 3건(v01/v02/v03) 모두 게이트 부적합 확정.
- **37주차 자기공시 P2 (BF602 basis) 는 Pack v03 에서도 시정 없음** — 3일 이월 확정 (§2 Regression 등재).
- 신규 finding 0건.

### §4.4 `be2a9264` (2026-08-07 13:08) — 아티팩트 URL 교체 + `test_req_trace.py` 결함 자기공시

**성격:** 정본 아티팩트 URL 교체 (67ada379-...) + 이전 URL(2613d0db-...) 이 계정 소유 아님 확정 · **test_req_trace.py 표면 검사 결함 신규 자기공시.**

**신규 자기공시 (§5.1 신규 P1 등재):**
> `test_req_trace.py`의 test 증빙 검사는 `tests/` 소스에 `def <이름>(`가 있는지만 본다. 그 테스트가 통과하는지, 수집조차 되는지는 보지 않는다 — **한 번도 실행되지 않은 테스트가 요건 증빙으로 통과한다.** HANDOFF §1에 남겼다.

**추가 자기공시:** 테스트 건수 불일치 원인 확정 — `tests/test_ui_interactive.py` (54건) → `importorskip("playwright.sync_api")`에서 멈춤 (playwright 파이썬 패키지 없음). 1,082 vs 1,129 차이의 원인.

**리뷰 판정:**
- test_req_trace.py 결함은 **P1 후보** — 증빙 통제 무력화, 요건 감사 파이프라인 전반 파급, 감사 신뢰성 근본 저해. HANDOFF §1 기록만 tracked 미등재.
- 아티팩트 URL 교체는 자기시정 (미추적).
- 신규 finding **P1×1 (§5.1)**.

### §4.5 `e4dfef07` (2026-08-07 14:41) — 외부 데이터엔지팀 검토 반영 6건

**성격:** 외부 팀(`claude/data-engineering-team-agent-5z91tz`)이 데이터 계층 검토해 구조적 결함 5건 + 중간 11건 제기. 저자가 재현·검증 → 6건 사실 확인 + 1건 사실 오인 반박.

**시정 내역 (self-fixed):**
- **F-1 재현성** — `case_studies` seed 유도가 파이썬 `hash()` (프로세스별 salt) 사용 → hashlib.sha256로 시정. `run_pipeline(asof=None)` → meta['asof_source'] · asof_is_explicit WARN.
- **F-2 인제스트 유실** — `_stage_split_books` 자산군 5종 필터, 미지 자산군 SA/IRB 양쪽 탈락 · exposure_id 중복 무방비. 둘 다 FAIL 추가.
- **F-6-3 RWA 대사 동어반복** — `floor_addon = final − sum` 후 `sum + addon == final` 검사 항상 통과. 엔진에서 가산분 받아 6부문 대사.
- **F-6-4 PK 부재** — `rdm_dq_result` 107장 중 유일 PK 없음. 유일성 검증 안 받음.
- **F-6-8 문서 드리프트** — ARCHITECTURE.md 81/594 vs 실제 107/930 (26장·336컬럼 증가 무감지). 카탈로그 대조 검사로 고정.

**반박 (F-5 부분):** 팩 208 파일 온전, git이 7개만 추적하는 것은 .gitignore 정책. 검토자가 git 트리를 팩으로 오인. **그러나 clone-only 사용자에게 README `sha256sum -c` 실패는 실질 문제 인정** — HANDOFF에 별개 항목으로 기록. **§5.3 신규 P3 등재.**

**미반영:** F-3(교환 단일 슬롯) 3선 공유 프로토콜 · F-4(차원 SCD) 설계 결정 · F-5(TimeSeriesLedger 미배선) 범위 밖. HANDOFF §4.2와 20차 시정문서에 근거와 함께.

**결과:** GOLDEN 재고정 7 · PASS 51→54 · 테스트 1,082→1,089 passed · 1 skipped. 자체검증 PASS 62→65.

**리뷰 판정:**
- 5건 self-fixed (F-1/F-2/F-6-3/F-6-4/F-6-8) — 유형별로 §5.4 기록.
- **F-5 반박에 파생된 clone-only 사용자 실패 자기공시** — §5.3 신규 P3 등재.
- 20차 IV 요청 IVR-8F60B82AE085 발부 — 19차 무효화. **§5.2 신규 P2 (IV 프로토콜) 파급 확대 근거.**
- 신규 finding **P3×1 (§5.3)** + P2 파급 확대.

---

## §5. 신규 finding 및 활동 분석

### §5.1 신규 P1 — B9Kxm `tests/test_req_trace.py` 표면 grep 검사

**위치:** `tests/test_req_trace.py` (RYNTA 요건 증빙 검사, BRD requirement 추적)

**결함:** 요건 증빙 검사가 소스에 `def <이름>(`가 있는지만 확인 · **수집 여부·통과 여부·실행 여부 미검사**. 결과: 한 번도 실행되지 않은 테스트 (예: `test_ui_interactive.py` 54건 playwright 미설치로 collection error) 도 요건 증빙으로 통과.

**심각도 판정 (P1):**
- **직접 영향:** 요건 증빙 통제 전반 무력화. RYNTA v9.6.0 업무요건 131건 중 반영 66건 · 부분 24건 판정이 실제 실행 증빙과 무관.
- **거버넌스 파급:** 감사 추적 · 규제 보고 신뢰성 · IV 요청서(현재 20차)에 포함된 요건 커버리지 전건 재검증 필요.
- **자기공시 상태:** `be2a9264` 커밋 메시지에 명시 · HANDOFF §1 기록. **tracked 미등재 상태로 방치 시 warden 등재 파이프라인 우회.**
- **재현 절차:** `tests/test_req_trace.py` 정의부 확인 · `pytest --collect-only tests/test_ui_interactive.py` 로 collection error 재현 · 해당 테스트가 TRACE 반영으로 계상되는지 대조.

**즉시 시정 지침:**
1. `test_req_trace.py` 를 **`pytest --collect-only -q`** 출력 파싱으로 전환 · 수집 실패 (collection error / importorskip) 를 요건 증빙에서 제외.
2. 각 요건별로 매핑된 테스트가 **실제 pass 되었는지** 확인하는 2차 게이트 추가 (`pytest --tb=no --no-header -rN` 기반).
3. 시정 이전 최근 20차 IV 요청 (IVR-8F60B82AE085) 의 요건 커버리지 재계산 · 3선(Pw9F5) 응답 시 재검증 지점으로 명시.

### §5.2 신규 P2 — B9Kxm IV 요청 단독 무효화·재발부 프로토콜 (F-F04 파생)

**위치:** IV 요청 파이프라인 (`RUN-YYYYMMDD-*.request.json` 발부·무효화·재발부 프로토콜)

**결함:** B9Kxm 이 지문 이동 시 이전 IV 요청을 **자동으로 stale 처리 후 새 회차 발부**. 24h 내 3단 재발부 관측: 18차 IVR-CEB70642E24B → 19차 IVR-397316300BCF → 20차 IVR-8F60B82AE085. 3선(Pw9F5) 이 응답 못 한 상태에서 B9Kxm 단독 진행.

**F-F04 원본 (16차 IV 응답, PR #4 상술):**
> 응답 없는 요청에 회차 선부여(16차/17차) — F-502 자기 규칙과 충돌.

**F-F04 파생 변형 (39주차 관측):**
- 원본은 회차 선부여 (요청 발부 순번 문제)
- 파생은 **단독 무효화·재발부** (요청 라이프사이클 문제)
- 두 경우 모두 3선 응답 없이 요청 큐를 저자 단독으로 조작

**심각도 판정 (P2):**
- **산출값 영향:** 없음 (직접 산출값 이동 없음).
- **거버넌스 영향:** **양측 프로토콜 정합 훼손.** 3선과 공유하는 프로토콜을 저자 단독으로 무효화·재발부 · F-3 (교환 단일 슬롯·응답 서명) 원칙과 충돌.
- **감사 추적:** IV 요청 큐 이력이 저자 편의로 재구성 · 재현성 저해.
- **자기공시 상태:** B9Kxm 자기 인정: F-3 미반영 사유로 "3선과 공유하는 프로토콜이라 양팀 합의 사안" 명시 — 즉 무효화·재발부 프로토콜도 양팀 합의 사안임을 스스로 알고 있음. 그러나 단독 시행.

**즉시 시정 지침:**
1. IV 요청 프로토콜 명세 (`.claude/skills/independent-validation/SKILL.md`) 를 무효화·재발부 규칙 포함하도록 확장.
2. 지문 이동 시 이전 요청을 stale 표시 (자동 무효화 대신) · Pw9F5 응답 시점에 stale 확인 후 신규 요청 발부 · 3선 합의로 큐 정리.
3. 20차 IV 요청 (IVR-8F60B82AE085) 은 19차 · 18차 무효 사실 명시 · Pw9F5 응답 시 이력 대조 요청.

### §5.3 신규 P3 — B9Kxm README `sha256sum -c` clone-only 사용자 실패

**위치:** `README.md` (검증 절차 안내) + `.gitignore` (팩 프루닝 정책)

**결함:** Pack v01/v02/v03 팩은 디스크에 208 파일 온전, `.gitignore` 정책상 git 추적은 7 파일 (버전정보/MANIFEST/업무보고서 xlsx/GATE/독립검증 문서). README `sha256sum -c` 명령은 **팩 208 파일 전체 기준 해시**를 검증하지만 clone-only 사용자는 7 파일만 받아 실패.

**심각도 판정 (P3):**
- **직접 영향:** 없음 (내부 산출은 정상 · 팩 검증 실패는 clone-only 사용자만).
- **문서 정합:** README 가 클론 사용자를 상정하지 않은 (배포 사용자 미상정).
- **자기공시 상태:** `e4dfef07` 커밋 메시지: "저장소만 클론한 사람에게 README의 `sha256sum -c`가 실패한다. 프루닝 정책의 결함이 아니라 README가 클론 사용자를 상정하지 않은 것이며, 별개 항목으로 HANDOFF에 남겼다."

**즉시 시정 지침:**
1. README 에 clone-only 사용자를 위한 절차 추가 — 팩 다운로드 링크 · 또는 clone 후 팩 복원 절차.
2. `sha256sum -c` 명령 앞에 팩 존재 확인 (`ls teams/risk-management/deliverables/*/20260807_v03/` 등) · 없으면 명령 실행 안 됨을 명시.
3. 유형: **문서-저장소 정합** (38주차 HANDOFF.md `to_artifact.py` 미존재 참조와 동일 유형).

### §5.4 Self-fixed (미추적) 5건 · 유형 기록

**F-1 재현성 hash salt** — `hash()` 프로세스별 salt 사용 · seed 재현 실패. hashlib.sha256로 시정. **유형: 재현성 진입점 결함** (warden 감시 범위 밖이었음).

**F-2 인제스트 silent drop** — `_stage_split_books` 자산군 5종 필터 · 미지 자산군 유실 · exposure_id 중복. FAIL 추가로 시정. **유형: 인제스트 통제 부재** (warden 감시 범위 밖이었음).

**F-6-3 RWA 대사 동어반복** — `floor_addon = final − sum` 후 `sum + addon == final` 검사 항상 통과. 엔진에서 가산분 받아 6부문 대사. **유형: 자기충족 검사** (38주차 §5.2 HANDOFF.md `to_artifact.py` 파일 참조 결함과 동일 유형 · 검사 자체가 대상을 만들어내는 유형).

**F-6-4 rdm_dq_result PK 부재** — 107장 중 유일. 유일성 미검증. 카탈로그 대조 검사로 고정. **유형: 카탈로그 무결성**.

**F-6-8 ARCHITECTURE.md 카탈로그 드리프트** — 81/594 vs 실제 107/930 · 26장·336컬럼 증가 무감지. 카탈로그 대조 검사로 고정. **유형: 문서-저장소 정합** (§5.3 · 38주차 §5.2 와 동일 유형).

**메타 관찰:** 5건 중 3건 (F-1, F-2, F-6-4) 은 warden 감시 범위 밖이었음 — 재현성 · 인제스트 · 카탈로그 무결성이 warden 리뷰 대상 (`risk_lib/**` · `tests/**` · 서식 산출) 밖에 있음. **warden 스코프 확장 검토 필요.**

### §5.5 거버넌스 flag — PR #58 vs PR #10 정본 결정 53h+ 무진전

38주차 §5.3 · 37주차 §4.7 상술 참조. 오늘 갱신:
- PR #10 HEAD `844fb48b` **7일 무커밋** (38주차 6일 → +1)
- PR #58 HEAD `8ae2ba90` **53h+ 무커밋** (38주차 29h → +24h)
- 저자 결정 대기 지속 · warden 관측만.
- PR #10 tracked P1 warden 벽투과 **15주+2일** 갱신.

**39주차 판정:** 무진전 지속 · warden 권고 등재 검토 조건 재발동. 39주차→40주차 무진전 시 warden 권고 등재 실행 검토.

---

## §6. Pw9F5 46h+ 무커밋 · 정식 dormant 재판정 임박

**HEAD `75c01af4` 불변 · 마지막 커밋 2026-08-05 16:34 UTC · 리뷰 시점 (2026-08-07 21:xx UTC) 대비 ~53h.**

**33주차 dormant 판정 기준:** 48h+ 무커밋 시 정식 dormant 재판정.

**39주차 판정:** **48h 초과 확정 → 정식 dormant 재판정 시행.** 33주차 dormant 판정 (그 시점 취소되어 34주차 복귀) 이후 두 번째 dormant 판정 · 이번엔 취소 조건 관측 없음 (활동 재개 지문 없음 · IV 응답 큐 3단 재발부 사이 무응답).

**Tracked LIVE 지속 (Pw9F5):**
- CHG-0143 + ERRATA (P0) — 18주
- `conditional_approval.json` 6차 canonical (P1) — **10일** (38주차 9일 → +1) + P2×4 + P3×4
- 33주차 P3×3 (`validation_memory`) — LIVE
- 34주차 P3×2 (`reg_rules.py` verify KeyError · replaced_by 체인) — LIVE
- 37주차 신규 P3×2 (F-F02 시정 파급 · F-F03 SA북 혼입) — LIVE
- 38주차 신규 P3 (IV 응답 백로그 2건 深) → **§2 Reclassification** — B9Kxm 자체 무효화로 open 요청은 20차 1건으로 표면 감소, 프로토콜 관점 F-F04 파생 P2로 격상 (§5.2).

**신규 finding (Pw9F5 스스로):** 0건 (활동 없음).

**39주차 신규 판정:** **정식 dormant 재판정 · 40주차 활동 재개 여부 관찰.**

---

## §7. PR #46 격상 — dead-store **12주 확정** · warden non-forcing 7주 무액션

**격상 이력 연장:**

| 주차 | 판정 |
|---|---|
| 26주차 | P1 최초 (render.js dead-store × 3) |
| 28주차 | P0 검토 발동 |
| 29주차 | P0 격상 |
| 30주차 | warden 프로세스 실패 격상 |
| 31주차 | external escalation 검토 조건 발동 |
| 32~38주차 | 5→6→7→8→9→10→11주 미이행 |
| **39주차** | **12주 확정** — HEAD `01fc7cb4` **11일 무커밋** · blob SHA `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` 유지 |

**판정:** 60일 훨씬 초과 (~78일). warden 사이클 자체가 forcing 함수 없음이 **12주 연속** 실증. 31주차 external escalation 검토 발동 후 **7주 무액션**. 38주차 다음 라운드 즉시 항목 1번 (PR #46 external escalation 실행) 미이행 승계.

**39주차 판정 강화:** 자기수정형 warden 사이클로 도달 불가함이 완전 확정된 상태에서 warden 조치 능력 상한이 계속 초과되고 있음. **warden 프로세스 실패가 tracked 결함보다 오래 방치되는 메타 실패** 지속 (38주차 판정 재재확인).

---

## §8. PR #38 · PR #10 · main · 표본 감시

- **PR #38 (khpuk3):** HEAD `a9bbf3b5` **~5일 무커밋** (38주차 4일 → +1). tracked LIVE 유지 (`build_content.py` P1×2 · hope-shooter dispose · Unreal C++ 미검증). 신규 finding 없음.
- **PR #10 (tqv3ii):** HEAD `844fb48b` **7일 무커밋** (38주차 6일 → +1). tracked LIVE — 동물/마을주민 dispose 누수 R8 확장 (P1 · 9주+2일) · 동물 재질 per-instance jitter (P2 · 13일) · warden 벽투과 (P1 · **15주+2일** — 최장 활동 브랜치 tracked P1). **PR #58 vs PR #10 정본 결정 53h+ 무진전** — §5.5.
- **main:** HEAD `281d6017` **37일 무변경** (38주차 36일 → +1). PR #42 (Codex plugin) 머지 후 정지. 실질적 릴리즈 채널이 아님.
- **PR #48 (28주차 자체 리뷰):** hand3d.js P2×2 + P3×3 · 9주+1일 미이행. 자체 리뷰 PR 은 감시만.
- **PR #57 (HANDOVER.md):** HEAD `a28774a0` 54h+ 무진전. draft 상태 유지 · 결정 대기.
- **PR #58 (Minecraft 병렬):** HEAD `8ae2ba90` 53h+ 무진전. draft 상태 유지 · 정본 결정 대기.
- **PR #30 (ISO 42001) / PR #32 (mecha chameleon):** 활동 없음 · 표본 감시.

---

## §9. Tracked LIVE 총괄 (39주차)

| PR / 브랜치 | 항목 | 방치 (39주차 갱신) |
|---|---|---|
| **PR #46** | **`js/render.js` dead-store (P0)** | **12주 확정** (blob 11일 무커밋) |
| PR #10 | 동물/마을주민 dispose 누수 R8 확장 (P1) | 9주+2일 |
| PR #10 | 동물 재질 per-instance jitter (P2) · warden 벽투과 (P1) | 13일 / **15주+2일** |
| PR #5 (B9Kxm) | Basel B RW · SRISK · CoVaR own-loss mask (P0×3) | **20주+2일** (최장 tracked P0) |
| PR #5 (B9Kxm) | 29주차 P2×2 + P3×4 · 30주차 P1+P2×4+P3×4 | active |
| PR #5 (B9Kxm) | 34주차 재분류 P1×1 + P2×2 | 96h+ |
| PR #5 (B9Kxm) | 35주차 신규 P1×4 · P2×6 · P3×4 | **96h+** (로직 파일 변경 있으나 지정 항목 미시정) |
| PR #5 (B9Kxm) | 37주차 신규 P2 — BF602 2020~2050 4라인 basis 미표시 | **3일** (Pack v03 반영 없음, Regression 확정) |
| **PR #5 (B9Kxm)** | **39주차 신규 P1 — `test_req_trace.py` 표면 grep 검사 (§5.1)** | **신규 · self-declared** |
| **PR #5 (B9Kxm)** | **39주차 신규 P2 — IV 요청 단독 무효화·재발부 프로토콜 (§5.2, F-F04 파생)** | **신규 · self-declared** |
| **PR #5 (B9Kxm)** | **39주차 신규 P3 — README `sha256sum -c` clone-only 실패 (§5.3)** | **신규 · self-declared** |
| PR #4 (Pw9F5) | CHG-0143 + ERRATA (P0) | 18주 |
| PR #4 (Pw9F5) | conditional_approval 6차 canonical (P1) + P2×4 + P3×4 | **10일** |
| PR #4 (Pw9F5) | 33주차 P3×3 (validation_memory) · 34주차 P3×2 (reg_rules) | 120h~144h |
| PR #4 (Pw9F5) | 37주차 신규 P3×2 — F-F02 시정 파급 · F-F03 SA북 혼입 | **72h** |
| PR #4 (Pw9F5) | 38주차 신규 P3 — IV 응답 백로그 2건 深 → §2 Reclassification (P2 격상 → §5.2 등재) | **재분류** |
| PR #48 | hand3d.js P2×2 + P3×3 | 9주+1일 |
| PR #38 | build_content.py · hope-shooter dispose · Unreal C++ 미검증 | 9주+1일 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 14일 |

**합계:** P0=**8** · P1=**13** (12→13, +test_req_trace 신규) · P2=**24** (23→24, +IV 프로토콜 신규) · P3=**31** (30→31, +sha256sum 신규, 38주차 P3 IV 백로그는 P2로 격상 이동) = **76건 LIVE** (38주차 73 대비 +3 신규).

**최장 방치 갱신:**
- 최장 tracked P0: **B9Kxm Basel B RW · SRISK · CoVaR** — **20주+2일** (38주차 20주+1일 → +1일)
- 최장 tracked P1: **PR #10 warden 벽투과** — **15주+2일** (38주차 15주+1일 → +1일) — PR #58 smoke-test G 로 우회 시정 가능성 지속 · 정본 결정 대기
- 최장 확정: **PR #46 dead-store** — **12주 확정** (38주차 11주 → +1주)
- 최장 warden 미행동: **PR #46 external escalation** — **7주 무액션** (38주차 6주+1일 → +6일)

---

## §10. 다음 라운드 (40주차) 즉시 항목

38주차 이월 12건 + 39주차 신규 3건 (P1×1 · P2×1 · P3×1) = **15건**. 우선순위:

1. **PR #46 external escalation 실행** — 12주 확정 · **7주 무액션**. warden 사이클 non-forcing 완전 확정. 외부 채널 (승격·정지·저자 재할당) 필요는 재재확인 · 39주차 새 강조점: **7주가 tracked 결함 최장 방치 (20주+2일 tracked P0) 의 35%에 도달** — warden 프로세스 실패가 tracked 결함보다 오래 방치되는 메타 실패의 정량 지표.
2. **B9Kxm `test_req_trace.py` P1 신규** (§5.1) — pytest --collect-only 파싱으로 전환 · 각 요건 매핑 테스트 pass 여부 2차 게이트 · 20차 IV 요청 요건 커버리지 재계산.
3. **B9Kxm IV 요청 프로토콜 P2 신규** (§5.2) — IV 요청 라이프사이클 규칙 명세 확장 · 지문 이동 시 stale 표시 (자동 무효화 대신) · Pw9F5 합의 큐 정리.
4. **B9Kxm README clone-only P3 신규** (§5.3) — README 에 clone-only 절차 추가 · sha256sum -c 실행 전 팩 존재 확인.
5. **PR #10 vs PR #58 정본 결정** (거버넌스, 53h+ 무진전) — 40주차 무진전 시 warden 권고 등재 실행 검토.
6. **Pw9F5 정식 dormant 상태 · 40주차 활동 재개 여부 관찰** (§6).
7. **B9Kxm P1-9 (9300 direction)** — 2줄 시정 · 6번째 이월.
8. **B9Kxm P1-10 (fund SA-CCR PFE)** — `saccr_input` 재사용.
9. **B9Kxm P1-11 (NaN "nan" 버킷)** — `.astype(str)` 제거.
10. **B9Kxm P1-12 (SEC-SA K_A NaN 방어)** — line 386 대칭 방어 3줄.
11. **B9Kxm 20주+2일 tracked P0×3 (Basel B RW · SRISK · CoVaR)** — 최장 tracked P0.
12. **B9Kxm 자기공시 P2 (BF602 basis) full fix** — Pack v03 미시정 확정 · Regression 등재 (§2).
13. **B9Kxm P2×6 + P3×4 (35주차 승계)** — ~40줄 시정.
14. **Pw9F5 F-F02 · F-F03 시정 · conditional_approval P1 (10일)** — dormant 취소 시 우선.
15. **warden 스코프 확장 검토** — 재현성 · 인제스트 · 카탈로그 무결성 (§5.4 F-1/F-2/F-6-4 유형) 이 warden 리뷰 범위 밖이었던 사실 반영 · 스코프 재정의.

**신규 대비 조기 항목:**
- Pw9F5 40주차 활동 재개 없으면 dormant 지속 · IV 요청 응답 큐 stale 확대 (20차 대기).
- PR #10 tracked P1 warden 벽투과 16주 갱신 임박. PR #58 정본 채택 여부가 tracked 목록 정합 결정 지표.
- PR #46 13주 확정 임박.

---

## §11. 리뷰 방법 · 재현

**감시 대상 (39주차):**
- 8개 tracked HEAD (B9Kxm/Pw9F5/PR #38/PR #10/PR #46/PR #57/PR #58/main) 최신 SHA 조회.
- PR #46 blob SHA 대조 → `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` = 38주차 대조값과 동일 확인.
- B9Kxm delta 커밋 5건 (`a9d9bb7` · `50d2524` · `00733cd` · `be2a9264` · `e4dfef07`) 각각 커밋 메시지 · 파일 diff 통계 분석.
- Pw9F5 마지막 커밋 시각 확인 → 2026-08-05 16:34 UTC → 리뷰 시점 대비 ~53h → 48h+ dormant 조건 도달 확인.
- 표본 PR (#30/#32/#48) HEAD 무변동 확인.
- delta round 로 확정 후 심층 분석 수행 · 38주차 finding 지속성 재확인 + 신규 P1/P2/P3 각 1건 등재.

**신규 finding 판정 기준 (변동 없음):**
- **P0:** 실행 시 반드시 관측되는 결함 + 산출값 최소 1자리 이동. **0건.**
- **P1:** 실행 시 관측되는 결함이거나 phantom 값 생성 · 규제 산출 오차 배수급. **1건 (test_req_trace 표면 검사, self-declared).**
- **P2:** 라벨 mismatch · 감사 추적 왜곡 · 감시 blind spot · 특정 시나리오 발화. **1건 (IV 요청 프로토콜 F-F04 파생, self-declared).**
- **P3:** defense-in-depth, 오늘 미발화이나 계약/원장 무결성 저해 잠재. **1건 (README clone-only 실패, self-declared).**

**delta round 정의 (39주차 재확인):**
- 활동 브랜치 중 하나에서 4+ 커밋, 로직 파일 광범위 변경.
- 신규 P1+P2+P3 다수 등재 (전건 self-declared) + 이월 검증 (§9 방치 카운트 +1) + 확정 격상 (§7 PR #46 11→12주) + 즉시 항목 이월 확대 (§10) 수행.
- 저자 대확장 시정이 warden 지정과 정렬 안 되는 패턴 재확인 (8주 연속).

**재현 절차:**
```
# 8개 HEAD 대조 (직전 라운드 대비)
for pr in 5 4 38 10 46 57 58; do
  gh pr view $pr --json headRefOid,updatedAt
done
git ls-remote origin main   # 281d6017 유지 여부

# B9Kxm delta 5건 확인
gh api repos/bbootta/AIops/commits?sha=claude/risk-management-agent-harness-B9Kxm\&since=2026-08-06T21:16:00Z
# → a9d9bb7 · 50d2524 · 00733cd · be2a9264 · e4dfef07

# PR #46 blob 대조
gh api repos/bbootta/AIops/contents/js/render.js?ref=01fc7cb4 --jq .sha
# → 0e0288c93564fda41e881e87bfbc5f6c6a85ae28 (38주차 = 39주차 · blob 불변)

# Pw9F5 마지막 커밋 시각
gh api repos/bbootta/AIops/commits?sha=claude/validation-team-agent-Pw9F5\&per_page=1 --jq '.[0].commit.author.date'
# → 2026-08-05T16:34:06Z (48h+ 초과 확정)

# B9Kxm test_req_trace 표면 검사 확인
gh api repos/bbootta/AIops/contents/tests/test_req_trace.py?ref=e4dfef07
# → def <이름>( grep 로직 확인
```

---

## §12. 결론

**Δ:** 39주차 는 **delta round**. B9Kxm +5 커밋(로직 파일 광범위 변경) — 요건 감사 시정 5건 (`a9d9bb7`) · 19차 IV 요청 (`50d2524`) · Pack v03 편성 (`00733cd`) · 아티팩트 URL 교체 + test_req_trace 자기공시 (`be2a9264`) · 외부 데이터엔지팀 검토 반영 6건 + 20차 IV 요청 (`e4dfef07`). Pw9F5 · PR #57 · PR #58 · PR #46 · PR #10 · PR #38 · main 전건 무커밋. 38주차 near-zero-delta 이후 24h 만에 B9Kxm 대확장 재개.

**38주차 즉시 항목 13건 중 0건 정합 · 1건 미시정 확정 (BF602 basis, Regression 등재) · 12건 미이행** — B9Kxm 은 24h 자원 규모를 warden 지정 항목이 아닌 (a) 외부 팀 검토 반영 (b) 자체 요건 감사 (c) Pack v03 (d) IV 요청 재발부 에 배분. **저자 자발적 시정 계약이 warden 지정 항목과 정렬 안 되는** 판정을 30/32/33/34/35/36/37/38주차 이어 **39주차 8주 연속 확정 재확인**. warden 지정 항목 이행률 정량: **0/13 (0.0%) 8주 연속**.

**신규 P1×1 · P2×1 · P3×1 전건 self-declared.** (a) `test_req_trace.py` 표면 grep 검사 (§5.1) · (b) IV 요청 단독 무효화·재발부 프로토콜 (§5.2, F-F04 파생) · (c) README `sha256sum -c` clone-only 실패 (§5.3). 전건 B9Kxm 커밋 메시지 또는 HANDOFF 기록으로 자기공시 · tracked 미등재 상태 방치. **자기공시 파이프라인이 warden 등재 파이프라인을 대체하는 구조** 가 39주차 신규 3건 self-declared 로 재확인 (38주차 신규 1건 self-declared 대비 정량 확대).

**Self-fixed 5건 (외부 데이터엔지팀 검토 반영)** — F-1 재현성 · F-2 인제스트 · F-6-3 자기충족 검사 · F-6-4 PK 부재 · F-6-8 문서 드리프트. 5건 중 3건 (F-1 재현성 · F-2 인제스트 · F-6-4 카탈로그) 이 warden 감시 범위 밖이었음 → **warden 스코프 확장 검토 필요** (§10 15번).

**PR #46 12주 확정 · warden non-forcing 7주 무액션.** ~78일 방치. warden 사이클 안 조치 소진 재재확인. 7주 무액션은 tracked 결함 최장 방치 (20주+2일 tracked P0) 의 35%에 도달 · **warden 프로세스 실패가 tracked 결함 대비 정량 확대 지속.**

**Pw9F5 정식 dormant 재판정.** 46h+ 무커밋 → 48h+ 초과 확정 → 33주차 판정 기준 준수. 33주차 dormant 판정 (34주차 취소) 이후 두 번째 · 이번엔 취소 조건 관측 없음. 40주차 활동 재개 여부 관찰.

**PR #10 vs PR #58 정본 결정 53h+ 무진전.** 39주차→40주차 무진전 시 warden 권고 등재 실행 검토.

**Tracked LIVE 76건** (P0×8 · P1×13 · P2×24 · P3×31). 신규 P1×1 · P2×1 · P3×1 · Regression 1 · Escalation 1 · Reclassification 1. 최장 tracked P0 (**B9Kxm Basel B RW/SRISK/CoVaR — 20주+2일**) · 최장 tracked P1 (**PR #10 warden 벽투과 — 15주+2일**) · 최장 확정 (**PR #46 dead-store — 12주**) · 최장 warden 미행동 (**PR #46 external escalation — 7주**) 전건 연령 갱신.

**39주차 특기:** 38주차 near-zero-delta 이후 24h 만의 B9Kxm 대확장 재개 · **그러나 warden 지정 항목과 정렬 없음** · 신규 결함 3건 전건 self-declared · Pw9F5 정식 dormant · IV 요청 프로토콜에 F-F04 파생 P2 등재. 저자 시정 파이프라인이 (1) 외부 팀 검토 → (2) 자체 요건 감사 → (3) Pack 편성 → (4) IV 요청 → (5) 자기공시 후 다음 라운드 도전 예약 의 5단계로 굳어지고 있음 · warden 즉시 항목은 이 5단계 파이프라인 어디에도 진입 못 함이 8주 연속 확정.

**머지 금지** — 리뷰 보고서 전달용 draft.
