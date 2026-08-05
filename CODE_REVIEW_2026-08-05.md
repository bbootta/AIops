# 전체 저장소 코드 리뷰 — 37주차 (2026-08-05)

**직전 리뷰:** PR #56 (2026-08-04 21:07 UTC) 이후 ~24h.
**리뷰 시점:** 2026-08-05 21:09 UTC.
**결과 헤드라인:** **delta round — 활동 브랜치 2/2 재개 (B9Kxm +2 · Pw9F5 +2 · 36주차 정지 우려 해소).** B9Kxm 17차 규제 산출 시정(BF602 15.88% → 10.99%) + Pw9F5 16차 IV 응답(IVR-AC0EDF9E5A37 경부적합 4건 + 자기결함 SD-07 자발 공개). 신규 PR #57 (HANDOVER.md · doc-only) · **PR #58 (Minecraft 병렬 하네스 · PR #10과 중복 브랜치 · 거버넌스 신호)**. **PR #46 dead-store 10주 확정** (blob `0e0288c9…` 9일 무커밋 · warden non-forcing 6주 무액션). 신규 P0=0 · P1=0 · **P2=1** (B9Kxm 자기공시 BF602 4라인) · **P3=2** (Pw9F5 F-F02 시정파급 · F-F03 CRE35.4 SA북 혼입) · 거버넌스 flag ×1 (PR #58 duplicate). Regression 0. Escalation 1 (PR #46 9→10주 확정). Reclassification 0. **Tracked LIVE 72건 유지** (35주차 69 + 신규 3).

---

## §1. 감시 활동 (24h)

| 브랜치 / PR | 직전 HEAD | 신규 HEAD | 신규 커밋 | 무커밋 기간 |
|---|---|---|---|---|
| **B9Kxm** (PR #5) | `d47f866e` | **`e5cca222`** | **+2** | 활동 재개 (36주차 24h 정지 해소) |
| **Pw9F5** (PR #4) | `29eb4243` | **`75c01af4`** | **+2** | 활동 재개 (36주차 48h+ 정지 해소) |
| PR #38 (khpuk3) | `a9bbf3b5` | `a9bbf3b5` | 0 | ~3일 |
| PR #10 (tqv3ii) | `844fb48b` | `844fb48b` | 0 | **5일** |
| **PR #46** (i79qef) | `01fc7cb4` | `01fc7cb4` | **0** | **9일** (blob SHA `0e0288c9…` 불변) |
| `main` | `281d6017` | `281d6017` | 0 | **35일** |
| **PR #57** (pyic2r) | — | `a28774a0` | **신규 PR** | 2026-08-05 15:08 UTC — HANDOVER.md doc-only |
| **PR #58** (dhk8gr) | — | `8ae2ba90` | **신규 PR** | 2026-08-05 16:00 UTC — minecraft/ (PR #10과 병렬) |

**핵심 판정:**

1. **B9Kxm 활동 재개 · 17차 규제 산출 시정 (`e5cca222`).** 해외영업점 서식(BF602·BF602-1) 자본비율 분모에서 구조화 익스포저(집합투자증권 CRE60 · 유동화 CRE40) 4.128조가 빠져 있던 결함을 시정. 본점 자본비율은 89917dab(2026-08-03)에서 이미 통합(CET1 11.70% → 8.12%)됐는데, **해외영업점만 뒤늦게 발견됐다** — 층위 간 시정 파급 지연 사례(자기공시). BF602 총자본비율 **15.878% → 10.991%** (본점 10.939% 와 정합). 두 검사(`test_overseas_rwa_denominator_carries_every_hq_component` · `test_table_path_reports_the_same_basis_as_the_form_objects`)로 회귀 고정. 전체 스위트 1,078 passed.
2. **B9Kxm 부수 시정 — `provenance_stats_from_lines` basis 열 손실.** 정규 테이블 `reg_form_line`에서 3열(value·text_value·formula)만 되돌리고 `basis` 열을 버린 뒤 문구로 재추론. 배분값을 3선 요청서에 실측으로 넘기던 F-501 유형 결함. 실측 4,011→4,009 · 혼합 167→169 로 대사.
3. **B9Kxm 자기공시 이월 (신규 P2)** — BF602 2020~2050(CCR·시장·운영·산출하한) 4라인도 배분값이나 문구에 파생 표지 없어 실측으로 분류됨. "18차 3선 도전 지점 4로 올리고 손대지 않았다"로 자기공시. 시정 파급을 완결하지 않은 채 다음 IV 라운드로 미룸 — §4.5 신규 P2 등재.
4. **Pw9F5 활동 재개 · 16차 IV 응답 (`02d0bfa4`).** IVR-AC0EDF9E5A37 (B9Kxm 17차 요청)에 대한 완전 재현(request_id·digest 3종 비트 일치) + 독립 재계산 12/12. **경부적합 4건 (전부 값 아닌 과정):** F-F01/F-E01 자기충족 검사 존속 · F-F02 자체검증 스트레스 CET1만 비교 · F-F03 EL-충당금 SA북 혼입 · F-F04 응답 없는 요청 회차 선부여. **적합 2건**: F-F05 자기결함 SD-07 자발 공개 (재유동화 W=0 · STC p반감 누락 — 트렌치 대사에서 발견) + F-F06 도전 4건 + CO-010 신설. pytest 1,369 passed.
5. **PR #46 dead-store 10주 확정.** blob `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` 9일 무커밋 (35주차 8일 → 36주차 9일 → 37주차 10일). warden 사이클 non-forcing **6주째 무액션**. 31주차 external escalation 검토 발동 후 대안 미착수.
6. **PR #57 (신규 · draft).** HANDOVER.md(신규 · 311 add)와 CLAUDE.md 앞머리 "## 0. This Repository" 추가. 문서 변경만 · 코드 영향 없음. 브랜치 = 프로젝트 매핑, 최장 방치 표(19주/14주/9주), 37주차 즉시 항목 승계 등을 기록 — 세션 전환 대비 인수인계 문서로 합리적. 리뷰 지침 계열 저작 — 자체 리뷰 대상 아님.
7. **PR #58 (신규 · draft) — 거버넌스 flag.** `claude/minecraft-dev-work-dhk8gr` 브랜치. **`minecraft/index.html` 5,886줄 · `smoke-test.cjs` 389줄**. PR #10(`claude/minecraft-game-tqv3ii` · HEAD `844fb48b` · 8주간 tracked P1×2 + P2×2)과 **같은 이름의 폴더에 별도 세션이 처음부터 다시 만든 병렬 하네스**. 두 PR 이 같은 `minecraft/` 경로에서 서로 다른 소스로 열려 있음 = 머지 시 충돌 필연. §4.7 거버넌스 flag 등재.

---

## §2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **0** |
| 신규 P2 | **1** — B9Kxm BF602 2020~2050 4라인 basis 미표시 (§4.5) |
| 신규 P3 | **2** — Pw9F5 F-F02 시정 파급 실패 (§4.6) · F-F03 EL-충당금 SA북 혼입 CRE35.4 위반 (§4.6) |
| 거버넌스 flag | **1** — PR #58 duplicate minecraft harness (§4.7) |
| Regression | **0** |
| Escalation | **1** — PR #46 9주 확정 → **10주 확정** |
| Reclassification | **0** |
| Tracked LIVE 재확인 | **72** (P0×8 · P1×12 · P2×23 · P3×29, 35주차 69 + 신규 3) |

---

## §3. 35주차 즉시 항목 (8건) 이행 상태

35주차 §9 "다음 라운드 즉시 항목" 을 그대로 대조. 37주차 delta 라운드 결과:

| # | 항목 | 파일 | 판정 | 37주차 이행 상태 |
|---|---|---|---|---|
| 1 | B9Kxm P1-9 (9300 borrower 방향) | `code_scope.py:103` | 2줄 시정 | **미이행** — e5cca222 diff 미포함 |
| 2 | B9Kxm P1-10 (fund SA-CCR PFE ~4.4×) | `funds.py:245` | `saccr_input` 재사용 | **미이행** — e5cca222 diff 미포함 |
| 3 | B9Kxm P1-11 (NaN "nan" 버킷) | `exposure_agg.py:37` | `.astype(str)` 제거 | **미이행** — e5cca222 diff 미포함 |
| 4 | B9Kxm P1-12 (SEC-SA K_A NaN 방어) | `securitisation.py:381` | line 386 대칭 방어 | **미이행** — e5cca222 diff 미포함 |
| 5 | B9Kxm P2×6 + P3×4 | 5파일 (~40줄) | catalog FK 등 | **미이행** |
| 6 | PR #46 external escalation | 절차 재설계 | 검토 6주째 | **미이행** — blob 9일 무커밋 |
| 7 | Pw9F5 `reg_rules.py` P3×2 + `conditional_approval.json` P1 | `reg_rules.py` / `conditional_approval.json` | 활동 재개 시 우선 | **부분** — 활동 재개했으나 16차 IV 응답에 몰두 · conditional_approval 갱신 없음 · reg_rules 미터치 |
| 8 | B9Kxm 19주 tracked P0×3 (Basel B RW · SRISK · CoVaR) | `rwa_sa.py` / `srisk.py` / `covar.py` | 최장 tracked | **미이행** |

**판정:** delta 라운드였음에도 8건 중 7건 미이행 · 1건 부분(활동 재개만). B9Kxm 은 17차 새 결함(해외영업점 분모)에 자원을 배분했고, Pw9F5 는 IV 응답 사이클로 복귀. 35주차 finding 은 정확히 저자의 우선순위 밖에 있음을 실증 — **저자의 자발적 시정 계약이 없다** (30주차 판정 재확인). warden 이 지정한 즉시 항목이 저자의 다음 커밋에 반영되는 확률 = 여전히 낮음.

---

## §4. 신규 finding 및 활동 분석

### §4.1 B9Kxm delta (`e5cca222` · `e1e0c87f`)

**변경 통계:** 273 additions · 37 deletions · 9 files.

**성격:** 규제 산출 시정 1건 + 인수인계 문서 1건. 규제 산출 시정은 자기공시로 발견 → 즉시 시정 → 검사 2건으로 회귀 고정한 **모범 사이클**. 다만 아래 §4.5의 이월 항목이 뒤에 붙는다.

**시정 대상 파일:**
- `risk_lib/regulatory/forms_fss_overseas_b.py` (+19/-6) — 해외영업점 서식 분모에 구조화 통합
- `risk_lib/regulatory/forms_fss_overseas_b_data.py` (+7/-1) — 데이터 결합
- `risk_lib/regulatory/provenance.py` (+7/-1) — `basis` 열 손실 시정
- `tests/test_provenance.py` (+22) · `tests/test_regulatory.py` (+52) — 회귀 검사 신설

**tracked 파일 무변경:** `code_scope.py` · `funds.py` · `exposure_agg.py` · `securitisation.py` · `rwa_sa.py` · `srisk.py` · `covar.py` — 35주차 P1×4 + 19주 P0×3 finding 전건 LIVE.

### §4.2 Pw9F5 delta (`02d0bfa4` · `75c01af4`)

**변경 통계:** 16차 응답 대량 산출(응답 문서 + 재계산 결과 + 기억 원장 갱신) + 회차 원장 백필. 세부 파일 목록은 크지만 값이 아닌 과정.

**성격:** IV 응답 사이클 + 자기결함 자발 공개. **SD-07 (재유동화 W=0 · STC p반감 누락)** 은 검증팀이 트렌치 대사로 스스로 찾아낸 결함으로, 상시 독립검증의 규율이 실증적으로 작동한 사례. B9Kxm 17차 산출물을 12/12 재계산 대조하며 새 재계산기 2종(CRE60 펀드 · CRE40~44 유동화)을 신설.

**16차 응답 4건 finding:**
- **F-F01 (경부적합, §4.6):** 15차 응답 미수신 채 요청 3회 대체 — F-E01 자기충족 검사가 새 트리에 존속. 반증 재실험(실호출 제거해도 통과)으로 확정.
- **F-F02 (경부적합, §4.6 신규 P3):** 자체검증 스트레스 검사가 제약 비율 아닌 CET1만 비교. 기준 시나리오 total 침범(10.94% < 11.50%)이 자기 규칙(FAIL)을 비켜감. B9Kxm d47f866(2026-08-03 콕핏 KPI 시정)은 콕핏만 고침 — **시정 파급 원칙 ② 위반**.
- **F-F03 (경부적합, §4.6 신규 P3):** EL-적격충당금 비교에 SA북 충당금 30.2억 혼입 (CRE35.4 위반). 현재 부족액 0으로 산출값 영향 없음, 방향 **비보수**.
- **F-F04 (경부적합):** 응답 없는 요청에 회차 선부여(16차/17차) — F-502 자기 규칙과 충돌. 본 응답이 16차.

### §4.3 PR #57 (HANDOVER.md · CLAUDE.md 갱신)

**변경 통계:** 311 additions · 1 deletion · 2 files. 문서만.

**성격:** 저자 자체 인수인계 문서 신설. "main 만 봐서는 저장소 상태를 알 수 없는" 상태 — main 에 3파일(CLAUDE.md · .claude/settings.json · .gitkeep)만 있고 실질 작업물은 전부 미머지 브랜치에 존재 — 를 정면에서 인정하고 새 세션 진입점을 마련. HANDOVER.md 는:
- 프로젝트 개요·목표 (병렬 실험 저장소, 세 갈래: 리스크·검증 하네스 / 앱 프로토타입 / 리뷰 자동화)
- 폴더 구조·브랜치-프로젝트 매핑
- 마지막 상태 (36주차 리뷰 기준 zero-delta · 최장 방치 19주/14주/9주)
- **37주차 즉시 항목 6단계 승계**
- 실행·테스트 방법
- 알려진 이슈·보류 사항

**판정:** 리뷰 관점에서 이례적 · 긍정적. 이 리뷰 시리즈(warden PR)를 "결함 목록의 단일 출처"로 CLAUDE.md에 명문화 — warden 사이클의 제도적 인지 상승. draft 로 열어 두어 결정 대기 상태 유지.

**주의:** 이 리뷰 문서 자체가 참조되므로 이 후 리뷰가 HANDOVER.md의 즉시 항목 6단계와 일치해야 한다는 **자기 재귀 제약**이 생김. 실제로 이 37주차 리뷰의 §3 는 35주차 8건을 그대로 이월했고, HANDOVER.md의 6단계와 대체로 정합. 재귀 확정은 CLAUDE.md 시정 반영 후 검증 필요.

### §4.4 PR #58 (Minecraft 병렬 하네스) — 거버넌스 flag

**변경 통계:** 6,443 additions · 3 files · 54 commits. 새 브랜치 `claude/minecraft-dev-work-dhk8gr` (2026-08-05 16:00 UTC 신설).

**성격:** PR #10 (`claude/minecraft-game-tqv3ii` · 6,368 add · 53 commits · 8주 tracked)과 **같은 이름의 폴더(`minecraft/`) 아래 별도 세션에서 처음부터 다시 만든 병렬 하네스**. 두 PR 은 서로 인지하지 못한 채 동일 대상을 병렬 개발 중 — main 에 머지 시도 시 **경로 충돌 필연**.

**검토된 사양적 특징:**
- `smoke-test.cjs` 389줄 — THREE·DOM 모킹으로 index.html 스크립트를 노드에서 실행하는 헤드리스 스모크 (7 시나리오 A~G). 특히 **G 시나리오는 워든 음파 시야 판정을 벽 유무로 반증**한다 (PR #10 tracked P1 "warden 벽투과 14주 미해소" 결함과 정확히 대응). PR #58 이 이 회귀 검사를 가진 상태로 열린 것은 우연이 아니라 **PR #10 결함을 재구현 회피한 신설로 볼 여지**가 있음.
- 크레이터 저장 최적화 · 100명 웨이브 · 다이아 위더 스톰 등 PR #10 에는 없는 신기능 다수.

**판정 (거버넌스 flag):**
1. **경로 충돌 회피 결정 필요.** 어느 쪽이 정본인지 저자 결정 없음. PR #10 을 close 하지 않고 PR #58 을 여는 것은 stoic-ride 리뷰가 PR #10 에 부여한 tracked 상태를 유지하는 결과 → PR #10 tracked 만 계속 이월되는 왜곡 발생.
2. **PR #10 tracked 결함이 PR #58 에서 회귀됐는지 확인 필요.** smoke-test G 시나리오가 벽 판정을 다루므로 워든 벽투과는 PR #58 에서 시정된 것으로 잠정 판정. 반면 동물/마을주민 dispose 누수(PR #10 P1) · per-instance jitter(PR #10 P2) 는 코드 비교 없이는 판정 불가 — 별도 심층 리뷰 필요.
3. **거버넌스 결함 유형:** "저자 재시작으로 warden tracked 목록이 정지 갱신되는" 유형 — 33주차 Pw9F5 dormant 판정 → 34주차 복귀와 유사한 상황. 두 PR 을 관측 대상으로 유지하되 저자 판단(어느 쪽이 정본)을 기다린다.

**깊이 리뷰 유예:** PR #58 은 이 라운드 신설이라 24h 내 fresh-eyes 검토 window 부족 · 5,886줄 코드는 stoic-ride 라운드 예산 밖. 38주차 §4 에서 심층 리뷰 편성 예정.

### §4.5 신규 P2 — B9Kxm BF602 2020~2050 4라인 basis 미표시

**위치:** `risk_lib/regulatory/forms_fss_overseas_b.py` 관련 (17차 커밋 e5cca222 에서 자기공시).

**결함:** BF602 2020(CCR)·2030(시장리스크)·2040(운영리스크)·2050(산출하한) 4라인은 배분값(본점 합계 × 해외 EAD 비중 0.529575)이나 문구에 파생 표지 없어 `provenance.py` 재추론에서 **실측** 으로 분류됨. e5cca222 이 CET1 라인만 시정하고 이 4라인은 그대로 두어 **비대칭 partial fix** 상태. 저자가 "18차 3선 도전 지점 4로 올리고 손대지 않았다"고 자기공시.

**심각도 판정 (P2):**
- **산출값 영향:** 없음 (분모 총계는 이미 e5cca222 에서 정확히 배분됨). 이번 결함은 **산출 근거 라벨의 정합**만 영향.
- **감사 추적 왜곡:** 3선(Pw9F5)이 요청 패키지에서 이 4라인을 실측으로 받으면 잘못된 재현 근거를 검증 대상으로 삼음 → CO-011 유형 결함 재발 가능.
- **저자 관리:** 18차 IV 도전 지점으로 예약된 상태 · Pw9F5 16차 응답의 F-F03/CO-010 시정 파급 원칙 하에서 우선순위 상.

**즉시 시정 지침 (30분 규모):**
1. `forms_fss_overseas_b.py` 에서 4라인 build 로직에 `basis="mixed"` 명시.
2. `test_regulatory.py` 에 4라인 basis 계약을 매개변수화된 assertion 으로 추가.
3. `RUN-20260630-42.request.json` 재생성 후 실측 4,009→4,005 · 혼합 169→173 대사.

### §4.6 신규 P3×2 — Pw9F5 자체검증 결함 계열

**F-F02 시정 파급 실패 (신규 P3):**
- **위치:** Pw9F5 harness 2선 자체검증 스트레스 검사.
- **결함:** 스트레스 시나리오에서 CET1 만 요구비율 대비 비교하고 Tier1·총자본 미비교. B9Kxm `d47f866e` 커밋(콕핏 KPI 3층 비교로 시정)이 자체검증 스트레스 검사에는 반영 안 됨.
- **심각도 (P3):** 방향은 비보수 (제약 계층 초과를 초록으로 통과)이나 산출값 영향 0. 시정 파급 원칙 ② 위반 계열의 **반복 재발** — 지난 라운드에서도 F-501/F-B01/F-C01/F-D01 로 매번 잡혔던 유형 (Pw9F5 스스로 인정).

**F-F03 EL-적격충당금 SA북 혼입 (신규 P3):**
- **위치:** Pw9F5 EL vs 적격충당금 비교 로직 (CRE35.4 스코프).
- **결함:** CRE35.4 는 **IRB 익스포저** 의 EL 과 적격충당금 비교이나, 현 로직이 SA북 충당금 30.2억을 혼입. 현재 IRB 부족액 0 이라 산출값 영향 0.
- **심각도 (P3):** 규제 문언 오해 · 방향 비보수 · 데이터 상태(부족액 0)에 의해 조용히 은폐. 오늘은 발화하지 않으나 IRB 부족액이 생기는 순간 자본 요구 저평가.

**공통 심각도 판정 근거:** 현재 발화 0 · 저자 인지 · 다음 응답 사이클에서 시정 예정. 미이행 지속 시 P2 격상.

### §4.7 거버넌스 flag — PR #58 duplicate

§4.4 에서 상술. 리뷰 결과는 아래 두 결정 대기:
1. **PR #10 close / PR #58 정본화** — warden 이 PR #10 tracked 를 PR #58 에 이전. 이전 시 tracked P1×2 + P2×2 가 PR #58 에서 회귀했는지 별도 리뷰.
2. **PR #58 close / PR #10 정본화** — PR #58 6,443 add 삭제 · PR #10 지속 개발.

**저자 결정 대기 · warden 은 관측만.** 38주차 첫 활동이 어느 쪽으로 나오는지가 판정 신호.

---

## §5. PR #46 격상 — dead-store **10주 확정** · warden non-forcing 6주 무액션

**격상 이력 연장:**

| 주차 | 판정 |
|---|---|
| 26주차 | P1 최초 (render.js dead-store × 3) |
| 28주차 | P0 검토 발동 |
| 29주차 | P0 격상 |
| 30주차 | warden 프로세스 실패 격상 |
| 31주차 | external escalation 검토 조건 발동 |
| 32~36주차 | 5→6→7→8→9주 미이행 |
| **37주차** | **10주 확정** — HEAD `01fc7cb4` **9일 무커밋**, blob SHA `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` 유지 |

**판정:** 60일을 넘겼음에도 warden 사이클로 도달 불가함이 완전 확정. 31주차 external escalation 검토 발동 후 **6주째 무액션**. HANDOVER.md §4 "37주차 즉시 항목 6단계" 에도 이 항목이 명시 승계됐으나 저자 결정 없음. 자기수정 사이클이 아니라 외부 채널(승격·정지·저자 재할당) 필요.

**37주차 대응:** 리뷰는 이월 카운트만 갱신. warden 사이클 안에서 할 수 있는 조치의 상한이 완전히 확인됨.

---

## §6. PR #38 · PR #10 · main · 표본 감시

- **PR #38 (khpuk3):** HEAD `a9bbf3b5` 3일 무커밋. tracked LIVE 유지 (`build_content.py` P1×2 · hope-shooter dispose · Unreal C++ 미검증). 신규 finding 없음.
- **PR #10 (tqv3ii):** HEAD `844fb48b` **5일 무커밋** (35주차 3일 → 36주차 4일 → 37주차 5일). tracked LIVE — 동물/마을주민 dispose 누수 R8 확장 (P1 · 8주) · 동물 재질 per-instance jitter (P2 · 11일) · warden 벽투과 (P1 · **15주** — 최장 활동 브랜치 tracked P1). **PR #58 등장으로 저자 우선순위에서 밀렸을 가능성** (§4.4/§4.7).
- **main:** HEAD `281d6017` **35일 무변경** (36주차 34일 → +1). PR #42 (Codex plugin) 머지 후 정지. 실질적 릴리즈 채널이 아님. PR #57 HANDOVER.md 가 이 사실을 문서화.
- **PR #48 (28주차 자체 리뷰):** hand3d.js P2×2 + P3×3 · 8주 미이행. 자체 리뷰 PR 은 감시만.
- **PR #30 (ISO 42001) / PR #32 (mecha chameleon):** 활동 없음 · 표본 감시.

---

## §7. Tracked LIVE 총괄 (37주차)

| PR / 브랜치 | 항목 | 방치 (37주차 갱신) |
|---|---|---|
| **PR #46** | **`js/render.js` dead-store (P0)** | **10주 확정** (blob 9일 무커밋) |
| PR #10 | 동물/마을주민 dispose 누수 R8 확장 (P1) | 9주 |
| PR #10 | 동물 재질 per-instance jitter (P2) · warden 벽투과 (P1) | 11일 / **15주** |
| PR #5 (B9Kxm) | Basel B RW · SRISK · CoVaR own-loss mask (P0×3) | **20주** (최장 tracked P0) |
| PR #5 (B9Kxm) | 29주차 P2×2 + P3×4 · 30주차 P1+P2×4+P3×4 | active |
| PR #5 (B9Kxm) | 34주차 재분류 P1×1 + P2×2 (§4.2/§4.3) | 48h+ |
| PR #5 (B9Kxm) | 35주차 신규 P1×4 · P2×6 · P3×4 (§4.2/§4.3/§4.4) | **48h** (e5cca222 미터치) |
| PR #5 (B9Kxm) | **37주차 신규 P2 — BF602 2020~2050 4라인 basis 미표시 (§4.5)** | **신규 · self-declared** |
| PR #4 (Pw9F5) | CHG-0143 + ERRATA (P0) | 16주 |
| PR #4 (Pw9F5) | conditional_approval 6차 canonical (P1) + P2×4 + P3×4 | **8일** (16차 응답에 미포함) |
| PR #4 (Pw9F5) | 33주차 P3×3 (validation_memory) · 34주차 P3×2 (reg_rules) | 72h~96h |
| PR #4 (Pw9F5) | **37주차 신규 P3×2 — F-F02 시정 파급 · F-F03 SA북 혼입 (§4.6)** | **신규 · self-declared** |
| PR #48 | hand3d.js P2×2 + P3×3 | 8주 |
| PR #38 | build_content.py · hope-shooter dispose · Unreal C++ 미검증 | 8주 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 12일 |

**합계:** P0=**8** · P1=**12** · P2=**23** (35주 22 + 신규 1) · P3=**29** (35주 27 + 신규 2) = **72건 LIVE** (35주차 69 대비 +3 신규 · 확정 격상 1).

**최장 방치 갱신:**
- 최장 tracked P0: **B9Kxm Basel B RW · SRISK · CoVaR** — **20주** (36주차 19주 → +1)
- 최장 tracked P1: **PR #10 warden 벽투과** — **15주** (36주차 14주 → +1) — PR #58 smoke-test G 가 이 결함 시나리오를 담고 있음 · §4.4 참조
- 최장 확정: **PR #46 dead-store** — **10주 확정** (36주차 9주 → +1)

---

## §8. 다음 라운드 (38주차) 즉시 항목

35주차 즉시 항목 8건 이월 + 37주차 신규 3건 + 거버넌스 flag 1건 = 12건. 우선순위:

1. **B9Kxm 자기공시 P2 (BF602 2020~2050 4라인 basis)** — 30분 규모. §4.5 지침. 17차 partial fix 를 대칭 완결.
2. **B9Kxm P1-9 (9300 direction)** — 2줄 시정. `_ACCT_CCF` 에서 9300 제거 + `credit_scope()` in_scope 규칙에 방향 컬럼 추가.
3. **B9Kxm P1-10 (fund SA-CCR PFE)** — `saccr_trade_view` 를 `derivatives.saccr_input` 재사용.
4. **B9Kxm P1-11 (NaN "nan" 버킷)** — `_bucket()` `.astype(str)` 제거, Categorical 유지.
5. **B9Kxm P1-12 (SEC-SA K_A NaN 방어)** — line 386 대칭 방어 3줄.
6. **B9Kxm P2×6 + P3×4** — 시정 총 ~40줄. catalog FK 선언 시 회귀 test 다수 예상.
7. **Pw9F5 F-F02 시정 파급 (신규 P3)** — 자체검증 스트레스 검사에 Tier1·총자본 비교 추가.
8. **Pw9F5 F-F03 EL-충당금 SA북 분리 (신규 P3)** — CRE35.4 스코프 IRB 익스포저로 한정.
9. **Pw9F5 `conditional_approval.json` P1** — 8일 미이행. 16차 IV 응답과 별도 라인 처리.
10. **Pw9F5 `reg_rules.py` P3×2 + 33주차 validation_memory P3×3** — 활동 재개했으므로 이제 즉시 항목.
11. **PR #46 external escalation 실행** — 10주 확정 · **6주 무액션**. warden 사이클 non-forcing 완전 확정. 외부 채널 (승격·정지·저자 재할당) 필요.
12. **B9Kxm 20주 tracked P0×3 (Basel B RW · SRISK · CoVaR)** — 최장 tracked P0 연령 갱신.

**거버넌스 결정 필요:**
- **PR #10 vs PR #58 (§4.4/§4.7):** 저자 결정 없이는 tracked P1 warden 벽투과 15주 갱신이 계속됨. PR #58 정본화 시 이 항목은 solved 로 재분류 가능.
- **PR #57 결정:** draft 상태 유지 여부 · 정본 CLAUDE.md 로 머지 여부.

**신규 대비 조기 항목:**
- 38주차 PR #58 심층 리뷰 편성 예정 (5,886줄 index.html · 389줄 smoke-test — fresh-eyes 검토 window 부족).
- 저자 자원이 17차 (B9Kxm) · 16차 응답 (Pw9F5) · minecraft 재개발 (PR #58) 세 방향으로 갈리는 상황에서 35주차 즉시 항목 8건이 우선순위 하위에 잔류하는 패턴이 4주째 지속. 저자 계약 재확인 필요.

---

## §9. 리뷰 방법 · 재현

**감시 대상 (37주차):**
- 6개 tracked HEAD (B9Kxm/Pw9F5/PR #38/PR #10/PR #46/main) 최신 SHA 조회 (`list_pull_requests state=all`).
- PR #46 blob SHA 대조 (`get_file_contents path=js/render.js ref=refs/heads/claude/nail-simulation-program-i79qef`) → `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` = 35주차 대조값과 동일.
- B9Kxm delta 커밋 2건 (`e1e0c87f` doc · `e5cca222` fix) 각각 diff 통계 확인 → tracked 파일 미터치 검증.
- Pw9F5 delta 커밋 2건 (`02d0bfa4` IV 응답 · `75c01af4` 회차 백필) 커밋 메시지 완독 → 4 findings + SD-07 확인.
- 신규 PR #57 · PR #58 body · files · 요약 파일 diff 확인.
- 표본 PR (#30/#32/#48) HEAD 무변동 확인.

**신규 finding 판정 기준 (변동 없음):**
- **P0:** 실행 시 반드시 관측되는 결함 + 산출값 최소 1자리 이동. **0건.**
- **P1:** 실행 시 관측되는 결함이거나 phantom 값 생성 · 규제 산출 오차 배수급. **0건.**
- **P2:** 라벨 mismatch · 감사 추적 왜곡 · 감시 blind spot · 특정 시나리오 발화. **1건 (B9Kxm BF602 basis).**
- **P3:** defense-in-depth, 오늘 미발화이나 계약/원장 무결성 저해 잠재. **2건 (Pw9F5 F-F02 · F-F03).**

**delta 라운드 정의:**
- 활동 브랜치 중 하나 이상이 새 커밋 보유.
- diff 로 신규 finding 발화 가능.
- 이월 검증 (§7 방치 카운트 +1) + 확정 격상 (§5 PR #46 9→10주) + 즉시 항목 이월 (§8) + 신규 finding 등재 (§4) 수행.

---

## §10. 결론

**Δ:** 37주차 는 활동 브랜치 2/2 재개 · **delta round**. B9Kxm 17차 규제 산출 시정 (해외영업점 BF602 15.88%→10.99% · 본점 정합) + `provenance_stats_from_lines` basis 열 손실 시정. Pw9F5 16차 IV 응답 (경부적합 4건 · 자기결함 SD-07 자발 공개). 36주차의 "두 활동 브랜치 동시 정지" 우려 해소.

**35주차 즉시 항목 8건 중 7건 미이행 · 1건 부분** — delta 라운드였음에도 저자 자원이 17차 신결함 (B9Kxm 해외영업점) · 16차 IV 사이클 (Pw9F5) 로 배분됨. 저자의 자발적 시정 계약이 warden 지정 항목과 정렬하지 않는 30주차 판정 재확인. **HANDOVER.md (PR #57) 가 이 리뷰를 "결함 목록 단일 출처" 로 CLAUDE.md 에 명문화한 것은 warden 사이클의 제도적 인지 상승** — 결과 검증은 38주차 이후.

**신규 finding 3건 (P2×1 · P3×2)** — 전건 자기공시 유형 (B9Kxm e5cca222 partial fix 자기공시 · Pw9F5 16차 F-F02/F-F03 자기 결함 인정). 자기공시가 warden 등재의 주요 경로가 된 것은 리뷰 시리즈의 성숙 신호이나, "self-declared → self-deferred → warden tracked" 파이프라인의 시간축 실측 필요.

**거버넌스 flag: PR #58 (Minecraft 병렬)** — PR #10 과 같은 경로에 별도 세션이 처음부터 재구현. warden 관측만 · 저자 결정 대기. PR #10 tracked P1 warden 벽투과 15주 항목이 PR #58 smoke-test G 시나리오와 정확히 대응하는 것은 우연 아닐 가능성.

**PR #46 10주 확정 · warden non-forcing 6주 무액션.** 60일 이상 자기수정 사이클로 도달 불가함이 완전 확정. HANDOVER.md 즉시 항목 6단계에 명시 승계됐으나 저자 결정 없음. 외부 채널(승격·정지·저자 재할당) 필요는 재확인.

**Tracked LIVE 72건 유지** (P0×8 · P1×12 · P2×23 · P3×29). 신규 P2×1 · P3×2 · 확정 격상 1. 최장 tracked P0 (**B9Kxm Basel B RW/SRISK/CoVaR — 20주**) · 최장 tracked P1 (**PR #10 warden 벽투과 — 15주 · PR #58 smoke-test G 로 우회 시정 가능성**) · 최장 확정 (**PR #46 dead-store — 10주**) 전건 연령 갱신.

**37주차 특기:** delta 라운드가 정상 사이클을 재확립. 두 활동 브랜치 재개 + 문서화 브랜치 (PR #57) + 병렬 재구현 브랜치 (PR #58) 3방향 activity 확산은 25주차 이후 최대 폭. 저자 자원 분산이 35주차 즉시 항목의 지속적 후순위화를 낳는 구조가 재실증. 38주차에서 즉시 항목 이행률(현재 0/8) 개선 여부가 warden 사이클 유효성의 정량 지표.

**머지 금지** — 리뷰 보고서 전달용 draft.
