# 전체 저장소 코드 리뷰 — 40주차 (2026-08-08)

**직전 리뷰:** PR #61 (2026-08-07 21:15 UTC) 이후 ~24h.
**리뷰 시점:** 2026-08-08 21:xx UTC.
**결과 헤드라인:** **역대 최대 규모 delta round — B9Kxm +9 커밋 · 43 파일 · +10,333/-521 라인.** 24h 만에 (a) ALM 엔진 전면 재구축 (갭 근사 → 계약 현금흐름 엔진, 12 모듈 신규/재작성) (b) UI 대확장 (Executive/종합보고서 화면 · KRI 카드 · 거시지표 모니터링 · 한도관리 개명) (c) 검증 가정 30건 접이식 UI · AI틱 문구 42건 정비 (d) 원장 109→131장 · 컬럼 +1,206 (e) 적대적 검증 3렌즈 27건 지적 · 중대 10건 재현·시정 · **3건 부분 시정 (다음 라운드 이월)**. Minecraft PR #58 +3 커밋 (신규 필살기 + **자기 회귀 2건 자기시정** + **smoke-test H 관대함 자기공시**). Pw9F5 · PR #46 · PR #10 · PR #38 · PR #57 · main 전건 무커밋. **9주 연속 warden 지정 즉시 항목 정렬 없음 확정 재확인** (15건 중 0건 정합). 신규 P0=0 · **P1=1** (ALM 이사회 팩 ΔEVE 갭 근사 유지 + `alm_irrbb_engine_single_source` WARN, self-declared 부분 시정) · **P2=2** (ΔNII 명목 55.5% 미산출 · 잔존만기 축 사다리 미실체화) · **P3=2** (`macro_indicator` 값 전건 basis="파생" · PR #58 smoke-test H 관대함 자기공시). Self-fixed **10+건** (한도 어휘 mismatch 4건 · auto-viz 2건 · 11 dead deep-links · Minecraft 20x 카메라 회귀 · 광선포 조준 어긋남). Regression **3** (37주차 BF602 basis 4일 이월 · 39주차 신규 P1/P2/P3 각 24h+ 미시정). Escalation **1** (PR #46 12주 → **13주 확정** · warden non-forcing **8주 무액션**). Pw9F5 dormant **2주차** (76h+ 무커밋). **Tracked LIVE 81건** (39주차 76 + 신규 P1×1·P2×2·P3×2).

---

## §1. 감시 활동 (24h)

| 브랜치 / PR | 직전 HEAD | 신규 HEAD | 신규 커밋 | 무커밋 기간 |
|---|---|---|---|---|
| **B9Kxm** (PR #5) | `e4dfef07` | **`9c6005a`** | **+9** | **역대 최대 delta 라운드** |
| **Pw9F5** (PR #4) | `75c01af4` | `75c01af4` | 0 | **76h+** (dormant 2주차 · 취소 조건 관측 없음) |
| PR #38 (khpuk3) | `a9bbf3b5` | `a9bbf3b5` | 0 | ~6일 |
| PR #10 (tqv3ii) | `844fb48b` | `844fb48b` | 0 | **8일** |
| **PR #46** (i79qef) | `01fc7cb4` | `01fc7cb4` | **0** | **12일** (blob `0e0288c9…` 불변) |
| PR #57 (pyic2r) | `a28774a0` | `a28774a0` | 0 | 78h+ |
| **PR #58** (dhk8gr) | `8ae2ba90` | **`6bc8467`** | **+3** | 활동 재개 (자기 회귀 2건 자기시정) |
| `main` | `281d6017` | `281d6017` | 0 | 2026-07-24 이후 무변경 |
| 기타 표본 (#30/#32/#48) | (변동 없음) | — | 0 | 표본 감시 |

**핵심 판정:**

1. **B9Kxm 역대 최대 delta 라운드 (+9 커밋).** 24h 자원 규모는 34주차 dormant 취소 3커밋 · 35주차 대확장 9커밋 · 39주차 5커밋을 넘어서는 **역대 1위** — 43 파일 · +10,333/-521 라인. **ALM 엔진 전면 재구축** (기존 갭 근사 IRRBB 123줄 폐기 · 계약 현금흐름 엔진 12 모듈 신규/재작성 · daycount/schedule/contracts/cashflow/behaviour/params/curves/nii/liquidity/irrbb/lcr/nsfr) + **UI 대확장** (Executive/종합보고서 화면 · KRI 카드 · 거시지표 모니터링) + **검증 가정 30건 접이식** + **AI틱 문구 42건** + **원장 109→131장 · 컬럼 +1,206**.

2. **그러나 39주차 즉시 항목 15건 중 0건 정합.** 저자 시정은 (a) ALM 엔진 재설계 (b) UI 확장 (c) 자기 회귀 즉시 시정 (한도 어휘 4건 · auto-viz 2건 · 11 dead deep-links) 에 배분. **34주차 재분류 P1 · 35주차 신규 P1×4 · 37주차 P2 (BF602 basis) · 39주차 신규 P1/P2/P3 (test_req_trace · IV 프로토콜 · README clone-only) 전건 미시정.** **9주 연속 warden↔저자 계약 미정렬 확정 재확인** (30/32~39주차 승계 → **40주차 9주 확정**).

3. **B9Kxm 자기공시 신규 결함 3종.** ALM 재구축 커밋 `9c6005a` 자체가 **적대적 검증 3렌즈 27건 지적 중 3건은 다음 라운드 이월** 명시:
   - **ΔNII** — `pass_through_beta` 원장 비어 명목 55.5% 제외한 부분 산출 (§5.2 신규 P2)
   - **잔존만기 축 사다리** — 함수로만 있고 원장 미실체화 (§5.3 신규 P3)
   - **이사회 팩 ΔEVE** — 갭 근사 유지 · `alm_irrbb_engine_single_source` WARN (§5.1 신규 P1 · **이사회/결재선 산출물에 갭 근사 잔존이 직접 표시**)

4. **B9Kxm ALM WIP 커밋 2건 공유 브랜치 push.** `ccce6db` · `e6a2797` 모두 커밋 메시지에 "아직 배선되지 않았고 파이프라인이 쓰지 않는다" 명시. `9c6005a`에서 배선 완료. 중간 SHA 를 체크아웃하는 사용자는 미배선 모듈만 받음. **재현성 · git 이력 정합성 저해** — §5.5 신규 P3 후보로 검토했으나 (a) 워크플로 브랜치 특성 (b) 배선 커밋이 같은 라운드 내 존재로 P3 등재 유예 · 유형만 §5.6 기록.

5. **B9Kxm `macro_indicator` 값 전건 basis="파생".** 12지표 (GDP/CPI/기준금리/…/KOSPI/CDS/은행NPL/장단기금리차) 원장에 ECOS 통계표코드 · KOSIS 표ID 컬럼 신설 · 시나리오 심도(gdp_path·severity) 를 지표 표준편차 단위로 부여. **그러나 외부 통계 접근 4경로 (curl · WebFetch · 헤드리스 크로미움 · WebSearch) 전부 EGRESS_BLOCKED/403** → 실측 없이 파생값. 화면에 "값이 전건 파생" 명시하나 · **시나리오 정당화 원장 (재현되지만 정당화 안 됨) 판정 그대로.** §5.4 신규 P3.

6. **B9Kxm 자기 회귀 즉시 시정 (한도 어휘 mismatch 4건).** `2827cc3` 커밋 메시지 "검수가 내 버그를 4건 잡았다" 자기공시 — 직전 커밋 `5614fb0` 에서 엔진 판정 어휘 (BREACH/CRITICAL/WARN/OK) 와 화면 어휘 (`'breach'`/`'warning'`) mismatch 로 **한 번도 매치되지 않았음** 명시. 4 하위 결함: (a) 한도관리 요약 "위반 없음" · KPI "위반 2 · 원장 25행" 불일치 (b) 콕핏 인사이트 한도 위반 줄 누락 (c) 최고 소진율 114.6% (등급_총노출_6조) 에 다른 행 이름 (섹터_총노출_2조) 표시 — "없는 값을 만든 셈이다" (d) 카탈로그 원장명 결측 `원장 null` 표시. **4건 전건 자기 라운드 내 시정 (self-fixed) 후 등재** · `limitBreached()`/`limitTone()` 한 쌍으로 통일. **`test_summary_strip_is_deterministic_rule_output` 계약이 있었다면 처음부터 잡혔음** 자기공시.

7. **Minecraft PR #58 자기 회귀 2건 자기시정.** `6b559bb` (20x 다이아 위더 · 광선포 신설) 로 인한 회귀 2건:
   - `937d218` — **20x 카메라 170블록 후퇴 → 지형 · 안개 벽 형성** (청크 R=min(8,viewDist/16)=112블록 · far=viewDist=110). 20x → 8x 축소로 시정. 자기공시 "안개와 프레이밍은 실제 렌더로만 판단할 수 있어 브라우저 확인이 남아 있다" — **검증 미완 지문 그대로 push.**
   - `6bc8467` — **광선 원점 (입 +33블록) 과 방향 (카메라 방향) 어긋나 표적 위 30블록 지나침.** `cannonAimPoint()` 로 십자선 광선 첫 교점 계산 후 관통. **자기공시: "종전에는 보스가 38칸 거체라 30칸 어긋나도 스쳐 맞아서 이 결함을 통과시켰다"** — **§5.5 신규 P3 (smoke-test 관대함)**. 보스 크기 2×0.6 로 축소 · 원상 복구 시 600/600 무피해 실패 확인.

8. **PR #46 dead-store 13주 확정.** blob `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` 12일 무커밋 (39주차 11일 → +1). warden 사이클 non-forcing **8주 무액션** (39주차 7주 → +1). ~85일 방치 · warden 자기수정 도달 불가 완전 재재재확인. **warden 프로세스 실패가 tracked 결함 최장 방치 (20주+3일 tracked P0) 의 39%에 도달** (39주차 35% → +4%p).

9. **PR #10 vs PR #58 정본 결정 77h+ 무진전.** 39주차 승계 (53h → +24h). 40주차 무진전 시 warden 권고 등재 실행 검토 조건 재발동 — **40주차 실행 시점 도달 · 조건 발동 확정.**

---

## §2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **1** — B9Kxm ALM 이사회 팩 ΔEVE 갭 근사 유지 · `alm_irrbb_engine_single_source` WARN (self-declared 부분 시정) |
| 신규 P2 | **2** — (a) B9Kxm ΔNII 명목 55.5% 미산출 (pass_through_beta 원장 빔) (b) B9Kxm 잔존만기 축 사다리 함수만 · 원장 미실체화 |
| 신규 P3 | **2** — (a) B9Kxm `macro_indicator` 값 전건 basis="파생" (12지표 · 외부 EGRESS_BLOCKED) (b) PR #58 smoke-test H 관대함 자기공시 (30블록 어긋나도 통과) |
| Self-fixed (미추적) | **10+** — B9Kxm 한도 어휘 mismatch 4건 · auto-viz 12행 미리보기 · 축 우선순위 · 11 dead deep-links · Executive Report ECL 단위 · Minecraft 20x 카메라 회귀 · 광선포 조준 어긋남 등 |
| 거버넌스 flag | **1** — PR #58 vs PR #10 정본 결정 미이행 (37주차 승계 · 77h+ 무진전 · 40주차 warden 권고 등재 실행 검토 조건 확정 발동) |
| Regression | **3** — (a) 37주차 P2 (BF602 basis) **4일 이월** (Pack v04 편성 없음) (b) 39주차 P1 test_req_trace 미시정 · 24h+ 이월 (c) 39주차 P2 IV 프로토콜 미시정 · 20차 IVR-8F60B82AE085 open + 24h fingerprint drift (재발부 없음, 무응답 지속) |
| Escalation | **1** — PR #46 12주 확정 → **13주 확정** · warden non-forcing 7주 → **8주** |
| Reclassification | **0** |
| Tracked LIVE | **81** (P0×8 · P1×14 · P2×26 · P3×33, 39주차 76 + 신규 P1×1·P2×2·P3×2) |

---

## §3. 39주차 즉시 항목 (15건) 이행 상태

39주차 §10 그대로 대조. **HEAD 이동 B9Kxm/PR #58 만 · 광범위 로직 변경 있으나 warden 지정 항목과 정렬 없음 · 15건 중 0건 정합.**

| # | 항목 | 파일 | 판정 | 40주차 이행 상태 |
|---|---|---|---|---|
| 1 | PR #46 external escalation 실행 | 절차 재설계 | **13주 확정 · 8주 무액션** | **미이행** — blob 12일 무커밋 · warden 프로세스 실패 정량 확대 |
| 2 | B9Kxm `test_req_trace.py` P1 (§5.1 39주차) | `tests/test_req_trace.py` | pytest --collect-only 파싱 전환 · pass 2차 게이트 | **미이행** — 24h+ 이월 · ALM UI 재구축에 자원 배분 |
| 3 | B9Kxm IV 요청 프로토콜 P2 (§5.2 39주차) | `.claude/skills/independent-validation/SKILL.md` | 라이프사이클 규칙 확장 · Pw9F5 합의 큐 | **미이행** — 20차 IVR-8F60B82AE085 open · 24h fingerprint drift로 재차 stale 판정 임박 (21차 재발부 관측 안 됨) |
| 4 | B9Kxm README clone-only P3 (§5.3 39주차) | `README.md` / `.gitignore` | clone 사용자 절차 추가 | **미이행** — 24h+ 이월 |
| 5 | PR #10 vs PR #58 정본 결정 | 거버넌스 | 24h 무진전 | **미이행** — **77h+ 무진전** · 40주차 warden 권고 등재 실행 조건 확정 발동 |
| 6 | Pw9F5 정식 dormant 상태 · 활동 재개 여부 | Pw9F5 활동 | 관찰 | **dormant 지속** — 76h+ 무커밋 · 2주차 · 취소 조건 관측 없음 |
| 7 | B9Kxm P1-9 (9300 direction) | `code_scope.py:103` | 2줄 시정 | **미이행** — 7번째 이월 |
| 8 | B9Kxm P1-10 (fund SA-CCR PFE) | `funds.py:245` | saccr_input 재사용 | **미이행** |
| 9 | B9Kxm P1-11 (NaN "nan" 버킷) | `exposure_agg.py:37` | `.astype(str)` 제거 | **미이행** |
| 10 | B9Kxm P1-12 (SEC-SA K_A NaN 방어) | `securitisation.py:381` | line 386 대칭 방어 | **미이행** |
| 11 | B9Kxm tracked P0×3 (Basel B RW · SRISK · CoVaR) | `rwa_sa.py` / `srisk.py` / `covar.py` | 20주+3일 최장 tracked P0 | **미이행** — **20주+3일** |
| 12 | B9Kxm 자기공시 P2 (BF602 basis) full fix | `forms_fss_overseas_b.py` | 4라인 basis 시정 | **미이행 확정** — Pack v04 편성 없음 (Pack v03 이후 재편성 없음) · 4일 이월 |
| 13 | B9Kxm P2×6 + P3×4 (35주차 승계) | 5파일 (~40줄) | catalog FK 등 | **미이행** — 5주 이월 |
| 14 | Pw9F5 F-F02 · F-F03 · conditional_approval P1 | Pw9F5 다수 | 활동 재개 시 | **11일 미이행** (39주차 10일 → +1) |
| 15 | warden 스코프 확장 검토 | 리뷰 스코프 정의 | 재현성 · 인제스트 · 카탈로그 무결성 유형 포함 | **미이행** — 관찰만 · 스코프 재정의 문서 없음 |

**판정:** 15건 중 0건 정합 시정. B9Kxm 은 24h 자원을 warden 지정 항목이 아닌 (a) ALM 엔진 전면 재구축 (b) UI 대확장 (c) 자기 회귀 즉시 시정 에 배분. **warden 지정 즉시 항목 이행률: 0/15 (0.0%)** — 32~39주차 이어 **40주차 9주 연속 0/N 확정 재확인**.

**저자 계약과 warden 지정의 미정렬 판정:** 30주차 최초 판정 → 32~39주차 8주 연속 재확인 → **40주차 9주 확정 재확인**. 자기공시→다음 라운드 도전 예약 파이프라인이 warden 등재 파이프라인을 완전히 대체하는 구조가 굳어짐 · **40주차 신규 3건 중 P1/P2×2/P3×2 전건 self-declared** 로 39주차 3건 전건 self-declared 승계 · **2주 연속 신규 finding 전건 self-declared 확정.**

---

## §4. B9Kxm delta 9커밋 상술

시간순 (2026-08-08 01:12 → 19:50 UTC · 약 19h 집중 작업).

### §4.1 `810f5b5` (01:12) — 보고서 그룹 신설 + Executive Report 화면

**성격:** 에이전틱 UI 메뉴 최상단에 `보고서` 그룹 신설 · 통제센터 위 배치. Executive Report 화면 = `02_reports/executive.html` 과 **같은 생성기** (`html_exec.briefing_facts` · `_cro_briefing` · `_kri_card_data` · `_top_actions`) 호출 · 두 화면 정합 계약 3건 테스트로 고정.

**시정 (self-fixed):** ECL 카드 단위 십억원 통일 (기존 원단위 · 브리핑 십억원과 불일치).

**부수 시정 (self-fixed):** 테스트 건수 불일치 완전 해소 — `pip install playwright` 후 `test_ui_interactive.py` 54건 수집·통과. 1,092+54=1,146 total. HANDOFF §1 절차 등재.

**리뷰 판정:** 신규 finding 0건 (모두 self-fixed) · 유형 §5.6 기록.

### §4.2 `2fb990a` (08:38) — 종합보고서로 개명 + KRI 카드 + 원장 자동 시각화

**성격:** `Executive Report` → `종합보고서` 개명. KRI 표 → 카드 격자 (12개월 스파크라인 · RED/AMBER/WATCH/GREEN 배지 · 3단 한계 · 12M 추세). 화면 73개에 autoChart 걸어 원장 107장 중 72장 자동 시각화 · 인라인 SVG 원시함수 6종 (bars/stackBars/donut/heat/waterfall/gauge · **외부 라이브러리 회피 — 아티팩트 CSP 차단 방지**).

**자기공시 (self-fixed):** 자동 시각화 도입 중 2건 자기 시정:
1. **미리보기 12행 vs 전량 프레임** — 2,980행 익스포저 원장의 12행 막대는 "표본이지 분포가 아니다 — 원장을 잘못 말하는 차트". 전량 프레임 (D.data · 92/107) 만 사용으로 시정.
2. **축 우선순위** — 컬럼 순서 첫 매치 (`n_exposures` > `rwa`) → RWA 원장이 "익스포저 수 구성" 표시. 우선순위 목록 (PREF) 로 시정 · 건수는 금액 없을 때만.

**리뷰 판정:** 자기 회귀 자체 시정 (self-fixed 2건). 신규 finding 0건 · 유형 §5.6 기록. **§5.6 관찰: 자기 시정 파이프라인이 자기 회귀 시정을 흡수하는 구조 확대** (37주차부터 관측 · 40주차 §4.2/§4.6 두 커밋에서 재확인).

### §4.3 `3feb9a6` (09:15) — 거시지표 원장 2장 + 한도 유형 확대

**성격:** `macro_indicator` · `macro_scenario_link` 원장 신설. 12지표 (GDP·CPI·기준금리·국고채3년·원달러·실업률·가계부채/GDP·주택가격·KOSPI·CDS·은행NPL·장단기금리차) 에 ECOS 통계표코드 · KOSIS 표ID · 시나리오별 충격을 지표 표준편차 단위로 부여. 한도 3종 → 5축 (차주·섹터·국가·자산군·등급) 확대. `LimitEngine.evaluate`에 `min_utilisation` 인자 추가 (기본 0.90 유지 · 화면용 전량 프레임 0.0 수신).

**자기공시 신규 P3 (§5.4):** 12지표 값 전건 **basis="파생"** — 외부 통계 접근 4경로 (`curl` CONNECT 403 · `WebFetch` EGRESS_BLOCKED · 헤드리스 크로미움 `net::ERR_TUNNEL_CONNECTION_FAILED` · `WebSearch` 산문 요약) 전부 차단. **시나리오 심도 재현성 유지 · 정당화 불가** 상태로 원장 등재.

**리뷰 판정:** 신규 P3 (§5.4 등재) · 심도 원장 자체는 진전 · 파생값 표시 명시성은 화면에 있음.

### §4.4 `5614fb0` (09:25) — 종합보고서 링크 실화면 · 한도관리 개명 · 메뉴 재배치

**성격:** 종합보고서 CRO 브리핑·액션 문장의 딥링크 11개 전부 `ops/*.html` 리포트 페이지 가리켜 **not found** 자기공시. 대응 화면 매핑으로 시정 · 매핑 없는 링크는 텍스트로 변환 ("죽은 링크 남기지 않는다"). 처음엔 `TABS.findIndex` 인덱스 조회로 어긋남 (LCR 누르면 코드 매핑 열림) · 라벨 조회로 시정 · 브라우저 확인.

**부수 시정 (self-fixed):** `한도` → `한도관리` 개명 · 위반 보고서 (0.90+) 와 전량 프레임 분리 · 차원별 최대 소진율 막대 · 심각도 KPI. 메뉴: 사업성 → `(참고)` 개명 · 맨 끝 배치. 위기상황 하위 `거시지표 모니터링` 추가.

**리뷰 판정:** 신규 finding 0건 · 11 dead deep-links self-fixed · **다음 커밋 (§4.6) 에서 한도 어휘 mismatch 4건 자기공시 · 이 커밋 산출물의 결함으로 지목됨** · 커밋 간 자기 회귀 관측.

### §4.5 `1170a49` (09:38) — 거시지표 최근값 단일 소스

**성격:** `scenario_links` 자체 최근 관측 · 모니터링 화면 자체 최근 관측 → 두 곳 latest 갈라짐 위험. `latest_observations` 단일 소스로 통합. 12지표 전건 일치 확인.

**리뷰 판정:** 신규 finding 0건 · **§5.6 관찰: 소스 오브 트루스 정합 시정 (single source) 이 저자 자체 감사 파이프라인의 반복 유형** — 39주차 §4.1 TRACE 조용한 기본값 (75/56 병기) 도 동일 유형 · 자체 감사가 정합성 결함을 반복 발견하는 구조 재확인.

### §4.6 `2827cc3` (10:14) — 검증 가정 30건 접이식 · 거시지표 화면 · AI틱 문구 42건

**성격:** 3선 도전 가정 30건을 details 접이식 (요약 + 부문 분류·건수 배지·검색·전체펼치기). 거시지표 모니터링 화면 (KPI 4장 · 경보표 · 부문별 지표표 · 계열 추이 · 시나리오 연결). AI틱 문구 42건 실무 문장 정비 (실무·규제 캐비앳은 보존).

**자기공시 (self-fixed 4건):** 커밋 메시지 "검수가 내 버그를 4건 잡았다" — `5614fb0` (§4.4) 에서 도입된 한도 어휘 mismatch 4건:
1. **한도관리 요약 "위반 없음"** but 바로 아래 KPI **위반 2 · 원장 25행** — 프레임 혼동 (위반 보고서 셈 · 본문 전량 프레임 그림).
2. **콕핏 인사이트 한도 위반 줄 통째 누락**.
3. **최고 소진율 (114.6% 등급_총노출_6조) 에 다른 행 이름 (섹터_총노출_2조) 표시** — 자기공시 "없는 값을 만든 셈이다".
4. **엔진 산출 직접 프레임 카탈로그 원장명 없어 `원장 null` 표시**.

원인: 엔진 어휘 (BREACH/CRITICAL/WARN/OK) 와 화면 어휘 (`'breach'`/`'warning'`) 불일치 — **"한 번도 매치되지 않았다"**. `limitBreached()` / `limitTone()` 한 쌍으로 통일. `test_summary_strip_is_deterministic_rule_output` 이 4행짜리 위반 보고서 기준 단언 · **"이 단언이 제대로 있었으면 위 버그가 처음부터 잡혔다"** 자기공시.

**리뷰 판정:** 4건 전건 self-fixed (같은 라운드 내 시정). 등재 없음. 그러나 **§5.5 · §5.6 관찰: 자기 회귀 파이프라인 = 저자 시정 파이프라인의 지속 유형** · 39주차 F-F04 파생 (§5.2) 과 동일 카테고리.

### §4.7 `ccce6db` (10:18) — ALM 현금흐름 엔진 (작업 중)

**성격:** ALM 재설계 워크플로 부분 산출물 · **커밋 메시지 자기공시: "아직 배선되지 않았고 파이프라인이 쓰지 않는다."** · `daycount.py` (87줄) + `schedule.py` (221줄). 기존 IRRBB 123줄 갭 근사 폐기 예고.

**리뷰 판정:** WIP 커밋 · 워크플로 브랜치이므로 재현성 저해 위험 낮음 · 유형 §5.6 기록 (WIP push 유형). 신규 finding 0건.

### §4.8 `e6a2797` (13:36) — ALM 계약·행동 현금흐름 엔진 (작업 중)

**성격:** WIP 계속 · `contracts.py` (276줄) + `cashflow.py` (541줄) + `behaviour.py` (296줄) + `params.py` (503줄) + `tests/test_alm_cashflow.py` (530줄 · **40건 통과**). 커밋 메시지 자기공시: **"아직 파이프라인에 배선되지 않았다."**

**리뷰 판정:** 테스트 40건 pass 확인 (자체 스위트 · 파이프라인 배선 전) · WIP 커밋 · 다음 커밋에서 배선 · 유형 §5.6.

### §4.9 `9c6005a` (19:50) — ALM 재구축 완결 · 배선 · 적대적 검증 3렌즈

**성격 (가장 큰 커밋):** 현금흐름 엔진 위에 금리시나리오 · IRRBB · 유동성 얹고 카탈로그 · 파이프라인 · 화면까지 연결. **적대적 검증 3렌즈 27건 지적 · 중대 10건 재현·시정 · 3건 부분 시정 (다음 라운드 이월).**

**신규:**
- `alm/curves.py` (544줄) — 충격 곡선 원장 (`alm_rate_shock_param` · `alm_scenario_def` · `alm_post_shock_floor`). KRW 행 NULL (미확인) · USD 프록시 시 `shock_source='프록시(USD)'` 명시.
- `alm/nii.py` (307줄) — ΔNII 12개월 전방 (마진 포함 · EVE 제외).
- `alm/liquidity.py` (573줄) — 만기 사다리 · 생존기간 · 잔존만기 축.

**재작성:**
- `alm/irrbb.py` — **갭 근사 폐기** · `alm_cashflow_bucket` 재평가. **계약·행동조정 두 기준 병기 — 비만기예금 때문에 최악 시나리오가 서로 반대** (계약 parallel_up −29.5% vs 행동조정 parallel_down −4.7% of Tier1). `worst_eve` · `by_scenario` 모듈 함수로 승격 · materialize 폴백 결함 해소 (`alm_irrbb_shock` 1행·0.0 → 6행).
- `alm/lcr.py` — 계수 · 상한 3종 원장 이관.
- `alm/nsfr.py` — 만기 분할 계수 원장 이관 · 미산출 항목 NULL·미확인.

**원장 확대:** 109 → **131장** · 컬럼 **+1,206**. 화면 6장 (금리리스크 · 현금흐름 원장 · 유동성 사다리 · 유동성리스크 · 생존기간 · ALM 계수 원장) 전부 원장 연결 · **리터럴 수치 없음**.

**검증에서 값 변동:**
- 원화유동성비율 2.99 → 0.336 (충족 → 위반)
- 외화유동성비율 0.748 → 0.336 (위반 유지)
- 원인 자기공시: "제26조·제63조는 잔존만기 기준인데 행태 슬로팅된 리프라이싱 사다리를 분모로 쓰고 있었다. 10년 변동금리 대출이 1개월 유동성자산이 되고 요구불예금은 1개월 유출에서 빠져 있었다." 축 잔존만기 전환 결과. **다만 시행세칙 원문 미열람이라 절대수준은 결재 대상이 아님 · citation 명시.**

**부분 시정 (다음 라운드 이월) 자기공시 3건:**
1. **ΔNII** — `pass_through_beta` 원장 비어 명목 55.5% 제외한 부분 산출. 제외 규모 원장 컬럼 3개로 노출 · `evidence_status` 미확인. **§5.2 신규 P2.**
2. **잔존만기 축 사다리** — 함수로만 있고 원장 미실체화. **§5.3 신규 P3.**
3. **이사회 팩 ΔEVE** — **아직 갭 근사** · `alm_irrbb_engine_single_source` WARN. **§5.1 신규 P1** (결재선/이사회 산출물에 갭 근사 잔존 · single_source 위반 · 자체 감사에서 감지).

**리뷰 판정:** 
- 적대적 검증 3렌즈 27건 지적 자체는 저자 자체 감사 확대 진전 (긍정 관측 · §5.7).
- 그러나 부분 시정 3건 self-declared 는 **자기공시→다음 라운드 도전 예약 파이프라인** 의 이번 라운드 5건 신규 등재 근거 (§5.1~§5.4).
- ALM 갭 근사 폐기·계약 CF 전환은 34주차 dormant 취소 이후 최대 아키텍처 변경 · 저자 자체 감사에서 도출 · **warden 감시 범위 밖 유형** (§5.6).

---

## §5. 신규 finding 및 활동 분석

### §5.1 신규 P1 — B9Kxm 이사회 팩 ΔEVE 갭 근사 유지 · `alm_irrbb_engine_single_source` WARN

**위치:** `alm/irrbb.py` (재작성) · `alm_irrbb_engine_single_source` 자체 감사 규칙 · 이사회 팩 산출.

**결함:** `9c6005a` 커밋에서 계약·행동 두 기준 병기 IRRBB 엔진으로 전환 · `alm_irrbb_shock` 원장 1행·0.0 → 6행 정합화. **그러나 이사회 팩 ΔEVE 는 아직 갭 근사 사용 · `alm_irrbb_engine_single_source` 자체 감사에서 WARN.** 저자 자기공시 (`9c6005a` 커밋 메시지 부분 시정 3번).

**심각도 판정 (P1):**
- **직접 영향:** 이사회 팩 · 결재선 산출물이 새 계약 CF 엔진과 정합 안 됨 → **두 IRRBB 판이 동시 산출** (감독 서식 · 화면 = 계약 CF · 이사회 팩 = 갭 근사). 부문 갈라짐 재발.
- **거버넌스 파급:** ALM 재구축 커밋 목적 자체가 "갭 근사를 계약 현금흐름으로 바꾸고 원장·화면에 배선한다" 인데 이사회 팩은 예외 · single_source 규칙 자체 WARN.
- **자기공시 상태:** `9c6005a` 커밋 메시지 명시 부분 시정 3번. **자기공시→다음 라운드 도전 예약 파이프라인의 이번 라운드 대표 사례.** tracked 미등재.
- **재현 절차:** `alm_irrbb_engine_single_source` 원장 WARN 상태 확인 · 이사회 팩 ΔEVE 소스 함수 (`board_pack.py` 계열) 가 새 `worst_eve`/`by_scenario` 대신 갭 근사 경로 사용 여부 대조.

**즉시 시정 지침:**
1. 이사회 팩 ΔEVE 소스 함수를 `alm/irrbb.py::worst_eve` (또는 by_scenario) 로 배선 · `alm_irrbb_engine_single_source` WARN 해소.
2. 배선 커밋과 동시에 이사회 팩 재산출 · 계약·행동조정 두 기준 병기 (parallel_up −29.5% vs parallel_down −4.7% 케이스가 이사회 팩에서도 나오도록).
3. 40주차 부분 시정 3건 (§5.1/§5.2/§5.3) 을 다음 Pack 편성 (Pack v04) 게이트에 등록 · 41주차 결과 확인.

### §5.2 신규 P2 — B9Kxm ΔNII 명목 55.5% 미산출 (`pass_through_beta` 원장 빔)

**위치:** `alm/nii.py` (신규) · `alm_pass_through_beta` 원장.

**결함:** ΔNII 12개월 전방 산출 시 전가율 (`pass_through_beta`) 원장이 비어 있어 **명목 55.5% 제외한 부분 산출.** 저자 자기공시: "제외 규모를 원장 컬럼 3개로 드러내고 evidence_status를 미확인으로 내렸다."

**심각도 판정 (P2):**
- **직접 영향:** ΔNII 산출값이 44.5% 명목만 반영 · 규모 노출은 되나 정합 안 됨. 감독 서식·화면 ΔNII 라벨과 실제 산출 스코프 mismatch.
- **거버넌스 파급:** `evidence_status='미확인'` 명시 · 결재 안전장치는 있으나 · 산출 자체가 부분값.
- **자기공시 상태:** `9c6005a` 커밋 메시지 명시 부분 시정 1번. tracked 미등재.

**즉시 시정 지침:**
1. `alm_pass_through_beta` 원장을 실측 (한국은행 이자율 전가 연구 · 또는 자체 관측 회귀) 로 채움 · 최소한 자산군별 대표값 (예금 · 대출 · 시장성 상품) 3~5행.
2. 채울 값이 없으면 명목 55.5% 이 왜 제외되는지 화면 · 감독 서식에 caveat 명시 (`evidence_status='미확인'` 자동 문구 확장).
3. 41주차 Pack 편성 시 ΔNII 산출 스코프 (`nominal_covered` · `nominal_excluded` · `evidence_status`) 3컬럼을 게이트 판정에 등록.

### §5.3 신규 P3 — B9Kxm 잔존만기 축 사다리 함수만 · 원장 미실체화

**위치:** `alm/liquidity.py::residual_maturity_ladder` (함수 존재) · 대응 원장 (`alm_residual_maturity_ladder` 또는 유사) 미생성.

**결함:** `9c6005a` 자기공시: "잔존만기 축 사다리는 함수로만 있고 원장으로 실체화되지 않았다." 화면 · 감독 서식이 원장 대신 함수 호출로 값 수신 → **원장-화면 정합 검증 파이프라인 (autoChart 등) 우회.**

**심각도 판정 (P3):**
- **직접 영향:** 원장 미실체화만 · 함수 산출값 자체는 문제 없음 (원화·외화유동성비율 재계산 근거).
- **거버넌스 영향:** 원장 정합 검증 우회 · `autoChart` 자동 시각화 미적용 · 카탈로그 대조 (§5.6 F-6-8 참조 · 39주차 self-fixed) 우회.
- **자기공시 상태:** `9c6005a` 커밋 메시지 명시 부분 시정 2번. tracked 미등재.

**즉시 시정 지침:**
1. `alm/liquidity.py::residual_maturity_ladder` 반환값을 `alm_residual_maturity_ladder` 원장에 등재 · 카탈로그 대조 (ARCHITECTURE.md) 반영.
2. 화면 · 감독 서식이 함수 대신 원장 참조로 전환.

### §5.4 신규 P3 — B9Kxm `macro_indicator` 값 전건 basis="파생"

**위치:** `alm/params.py` 또는 유사 · `macro_indicator` 원장 (12지표) · `macro_scenario_link` 원장.

**결함:** 12지표 (GDP·CPI·기준금리·국고채3년·원달러·실업률·가계부채/GDP·주택가격·KOSPI·CDS·은행NPL·장단기금리차) 원장에 ECOS 통계표코드 · KOSIS 표ID 컬럼 신설 · 그러나 **값은 전건 basis="파생"** — 외부 통계 접근 4경로 (`curl` CONNECT 403 · `WebFetch` EGRESS_BLOCKED · 헤드리스 크로미움 `net::ERR_TUNNEL_CONNECTION_FAILED` · `WebSearch` 산문 요약) 전부 차단.

**심각도 판정 (P3):**
- **직접 영향:** 시나리오 심도 정당화 원장은 진전 · 값 자체가 파생이라 실측 대비 불명. 화면에 "값이 전건 파생" 명시.
- **거버넌스 영향:** ECOS/KOSIS 코드가 실제 계열을 가리키므로 egress 열리면 `macro_monitor.py` 한 모듈만 갈아끼우면 됨 (커밋 자기공시). 인프라 제약이지 코드 결함은 아님.
- **자기공시 상태:** `3feb9a6` 커밋 메시지 명시. tracked 미등재.

**즉시 시정 지침:**
1. 관리자 프록시 정책 검토 · `ecos.bok.or.kr` · `kosis.kr` · `bok.or.kr` · `fred.stlouisfed.org` · `api.worldbank.org` · `sdmx.oecd.org` egress 허용 요청 (감시 · 규제 통계는 정책 허용 여지 큼).
2. egress 열리기 전까지 파생값 사용 caveat 를 감독 서식·이사회 팩에 자동 첨부.
3. 유형: **환경-엔진 정합** (인프라 제약이 산출 정당화를 저해하는 유형 · warden 감시 범위 밖).

### §5.5 신규 P3 — PR #58 smoke-test H 관대함 자기공시

**위치:** `minecraft/smoke-test.cjs` · 시나리오 H (거대 위더 스톰 광선포 격파).

**결함:** `6bc8467` 커밋 메시지 자기공시: **"종전에는 보스가 38칸 거체라 30칸 어긋나도 스쳐 맞아서 이 결함을 통과시켰다."** 광선 원점 (입 +33블록) 과 방향 (카메라 방향) 어긋나 표적 위 30블록 지나쳤으나 큰 판정 상자로 인해 스모크 테스트가 오탐 · **결함 탐지 실패.**

**심각도 판정 (P3):**
- **직접 영향:** 이 결함은 이미 자기 시정됨 (`6bc8467` 에서 `cannonAimPoint()` 도입 · 보스 크기 2×0.6 축소 · 원상 복구 시 600/600 무피해 실패 확인).
- **거버넌스 영향:** 스모크 테스트 판정 상자 크기 · 카메라 위치 등 프레임 파라미터가 **결함 탐지 감도** 를 결정 · 다른 시나리오 (A~G · I) 도 유사 감도 저하 위험. **39주차 §5.1 B9Kxm `test_req_trace.py` 표면 검사와 동일 카테고리 (테스트 자체가 대상을 검증하지 못하는 유형).**
- **자기공시 상태:** `6bc8467` 커밋 메시지 명시. tracked 미등재.

**즉시 시정 지침:**
1. `minecraft/smoke-test.cjs` 전 시나리오 (A~I) 판정 상자 · 카메라 파라미터 감도 재검토 · 각 시나리오별 "결함 도입 시 실패" 대조 케이스 추가.
2. 유형: **테스트 오탐 저하** (§5.6 F-6-3 자기충족 검사 · 39주차 §5.1 test_req_trace 표면 검사와 동일 카테고리).

### §5.6 Self-fixed (미추적) 10+건 · 유형 기록

**B9Kxm (같은 라운드 내):**

1. **한도 어휘 mismatch 4건** (§4.6) — 엔진 (BREACH/…) vs 화면 (`'breach'`) 어휘 미매치 · `limitBreached()`/`limitTone()` 통일. **유형: 소스 오브 트루스 정합** (39주차 F-6-8 문서-저장소 정합과 동일 카테고리 · 이번 라운드 §4.5 → §4.6 커밋 간 자기 회귀).
2. **auto-viz 12행 미리보기 vs 전량 프레임** (§4.2) — 원장 잘못 말하는 차트 · 전량 프레임 사용으로 시정. **유형: 데이터 대표성 결함.**
3. **auto-viz 축 우선순위** (§4.2) — `n_exposures`가 `rwa` 앞이라 RWA 원장이 "익스포저 수 구성" 표시 · 우선순위 목록으로 시정. **유형: 시각화 축 선택 결함.**
4. **11 dead deep-links** (§4.4) — CRO 브리핑·액션 딥링크 전부 `ops/*.html` 리포트 페이지 · 화면에 없음. 대응 매핑 · 매핑 없는 링크는 텍스트로. **유형: 문서-저장소 정합.**
5. **Executive Report ECL 카드 단위** (§4.1) — 원단위 vs 브리핑 십억원 · 십억원으로 통일. **유형: 단위 정합.**
6. **거시지표 최근값 갈라짐 위험** (§4.5) — `scenario_links` vs 모니터링 화면 각자 최근 관측 · `latest_observations` 단일 소스로. **유형: 소스 오브 트루스 통합.**

**PR #58 (같은 라운드 내):**

7. **20x 카메라 회귀** (§8 참조 · `937d218`) — 20x → 8x 축소 · fog/far 카메라 거리 연동. **유형: UI 회귀 자기 시정** (검증 미완: "안개와 프레이밍은 실제 렌더로만 판단할 수 있어 브라우저 확인이 남아 있다" 자기공시).
8. **광선포 조준 어긋남** (§8 참조 · `6bc8467`) — 광선 원점 vs 방향 어긋남 · `cannonAimPoint()` 도입. **유형: 산술 오류 자기 시정.**

**메타 관찰 (Δ 40주차):**

- **자기 회귀 파이프라인 확대 관측:** 이번 라운드 §4.5 (한도 도입) → §4.6 (한도 어휘 4건 자기 시정) · `6b559bb` (20x 도입) → `937d218` (카메라 회귀 자기 시정) → `6bc8467` (조준 어긋남 자기 시정). **동일 라운드 내 도입-회귀-시정 사이클이 두 브랜치에서 동시 관측.**
- **WIP 커밋 2건 공유 브랜치 push 유형** — `ccce6db` · `e6a2797` 모두 "아직 배선되지 않았다" 자기공시 · `9c6005a` 에서 배선. 워크플로 브랜치이므로 재현성 저해 낮음 · 그러나 중간 SHA 체크아웃 사용자는 미배선 모듈. **유형: WIP 공유 브랜치 push** (P3 등재 유예 · 유형만 기록).
- **테스트 오탐 저하 유형 반복 관측** — 39주차 §5.1 (test_req_trace 표면 grep) · 40주차 §5.5 (smoke-test H 판정 상자 크기). **저자 자체 감사가 이 유형을 반복 발견 → warden 스코프 확장 대상 후보 (§10 조건 승계).**

### §5.7 긍정 관측 — B9Kxm 적대적 검증 3렌즈 27건 지적

**`9c6005a` 커밋 자체가 적대적 검증 3렌즈로 27건 지적을 받아 · 중대 10건 재현·시정 · 3건 부분 시정 자기공시.** 이는 39주차 §5.4 (외부 데이터엔지팀 검토 6건 반영) 파이프라인의 40주차 재현 · **저자 자체 감사 인프라가 스스로 결함을 발견하는 구조** 확대.

**긍정 관측:**
- 적대적 검증 3렌즈 도입은 저자 자체 감사 성숙도 지표.
- 부분 시정 3건 자기공시는 tracked 등재 파이프라인의 원료로 재활용 (§5.1~§5.3 등재).
- warden 등재 없이도 저자 자체 감사가 24h 내 신규 결함 27건 발견 · 10건 시정 · 3건 이월 문서화 → **자기공시 파이프라인의 발견 채널로서 실효성 유지.**

**우려 관측 (긍정 관측의 이면):**
- warden 등재 파이프라인 → 저자 무시 · 자기공시 파이프라인 → 저자 관리로 이원화 · warden 지정 항목 이행률 0/15 (0.0%) 확정 재확인.
- 자체 감사 27건 발견 · warden 지정 15건 미시정 → **저자 자체 감사가 warden 감시를 실질 대체하고 있는 관측 확대.**

### §5.8 거버넌스 flag — PR #58 vs PR #10 정본 결정 77h+ 무진전 · 40주차 warden 권고 등재 실행 조건 확정 발동

39주차 §5.5 승계. 오늘 갱신:
- PR #10 HEAD `844fb48b` **8일 무커밋** (39주차 7일 → +1)
- PR #58 HEAD `8ae2ba90` → **`6bc8467`** (활동 재개 · 3커밋 delta) · 그러나 정본 결정 관측 없음 · 여전히 draft
- **77h+ 무진전** — 39주차 53h → +24h · **40주차 무진전 시 warden 권고 등재 실행 검토 조건 확정 발동**
- PR #10 tracked P1 warden 벽투과 **15주+3일** 갱신

**40주차 판정:** **warden 권고 등재 실행 조건 확정 발동.** 41주차 무진전 시 warden 권고 등재 실행 (기존 warden 권고 등재 표준 절차 대비 예외 없음 확인 · PR #58 활동 재개로 정본 대상 브랜치 확정 근거는 강화).

---

## §6. Pw9F5 dormant 2주차 · 76h+ 무커밋

**HEAD `75c01af4` 불변 · 마지막 커밋 2026-08-05 16:34 UTC · 리뷰 시점 (2026-08-08 21:xx UTC) 대비 ~76.5h.**

**39주차 판정 승계:** 정식 dormant 재판정 상태 유지. 39주차 53h → 40주차 76.5h · 취소 조건 (활동 재개 · IV 응답 큐 진전) 관측 없음.

**Tracked LIVE 지속 (Pw9F5):**
- CHG-0143 + ERRATA (P0) — **19주** (39주차 18주 → +1)
- `conditional_approval.json` 6차 canonical (P1) — **11일** (39주차 10일 → +1) + P2×4 + P3×4
- 33주차 P3×3 (`validation_memory`) — LIVE
- 34주차 P3×2 (`reg_rules.py` verify KeyError · replaced_by 체인) — LIVE
- 37주차 신규 P3×2 (F-F02 시정 파급 · F-F03 SA북 혼입) — LIVE
- 39주차 신규 P2 (§5.2 39주차 F-F04 파생 IV 프로토콜) — LIVE · **§2 Regression 등재 · 20차 IVR-8F60B82AE085 open 후 fingerprint drift (B9Kxm 10k+ 라인 delta) 로 재차 stale 임박 · 21차 재발부 관측 안 됨**

**신규 finding (Pw9F5 스스로):** 0건 (활동 없음).

**40주차 신규 판정:** **dormant 2주차 지속 · 취소 조건 관측 없음 · 41주차 활동 재개 여부 관찰.** 41주차에도 dormant 유지 시 → **정식 dormant 3주차 · 처음 도달** (33주차 dormant 판정 → 34주차 취소 사례 초과).

**IV 요청 큐 상태 (§5.2 39주차 P2 파생 관측):**
- 20차 IVR-8F60B82AE085 open · Pw9F5 무응답 · **B9Kxm 40주차 대확장으로 fingerprint drift 재차 발생 · stale 임박** · 그러나 21차 재발부 관측 안 됨 (24h delta 내 IV 요청 커밋 없음).
- **§5.2 39주차 판정 (IV 요청 단독 무효화·재발부 프로토콜 F-F04 파생) 은 이번 라운드 재발부 없음으로 관찰만 · 21차 재발부 관측 시 재격상 검토.**

---

## §7. PR #46 격상 — dead-store **13주 확정** · warden non-forcing **8주 무액션**

**격상 이력 연장:**

| 주차 | 판정 |
|---|---|
| 26주차 | P1 최초 (render.js dead-store × 3) |
| 28주차 | P0 검토 발동 |
| 29주차 | P0 격상 |
| 30주차 | warden 프로세스 실패 격상 |
| 31주차 | external escalation 검토 조건 발동 |
| 32~39주차 | 5→6→7→8→9→10→11→12주 미이행 |
| **40주차** | **13주 확정** — HEAD `01fc7cb4` **12일 무커밋** · blob SHA `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` 유지 |

**판정:** ~85일 방치. warden 사이클 자체가 forcing 함수 없음이 **13주 연속** 실증. 31주차 external escalation 검토 발동 후 **8주 무액션**. 39주차 다음 라운드 즉시 항목 1번 (PR #46 external escalation 실행) 미이행 승계.

**40주차 판정 강화:** warden 사이클로 도달 불가함이 완전 확정된 상태에서 warden 조치 능력 상한이 계속 초과. **warden 프로세스 실패가 tracked 결함보다 오래 방치되는 메타 실패** 지속:
- 8주 무액션 = 56일
- 최장 tracked P0 (B9Kxm Basel B RW · SRISK · CoVaR) = 20주+3일 = 143일
- **비율: 8/20 = 40%** (39주차 35% → +5%p) · **warden 프로세스 실패 방치 비율 정량 확대 지속 (2주 연속 +4~5%p).**

---

## §8. PR #58 delta 3커밋 · PR #38 · PR #10 · main · 표본 감시

### §8.1 PR #58 (Minecraft dhk8gr) — 3커밋 delta

**시간순 (2026-08-08 10:17 → 10:38 UTC · 약 21분 집중):**

- **`6b559bb` (10:17)** — 신규 필살기 · 💎 다이아 위더 20x (몸 높이 약 90블록) + F 광선포 (충전 0.8초 · 발사 2초 · 굵기 24칸 · 사거리 180블록 · 반경 12칸 · 0.12초마다 90 피해 · 총 ~1,500). 3인칭 카메라 170블록 후퇴. `far` 260 확대. 검증 시나리오 H 추가 (거대 위더 스톰 광선포 격파 단언).
- **`937d218` (10:28)** — 카메라 회귀 자기 시정. 20x 카메라 170블록 후퇴 → 청크 (R=min(8,viewDist/16)=112블록) · 안개 (`far=viewDist=110`) 벽 지형 통째 지움. **20x → 8x** 축소 (약 36블록 · 적 거대 위더 스톰과 같은 덩치) · 카메라 68블록으로 · `applyFogForCamera` 도입. **자기공시: "안개와 프레이밍은 실제 렌더로만 판단할 수 있어 브라우저 확인이 남아 있다"** — 검증 미완 push.
- **`6bc8467` (10:38)** — 광선포 조준 어긋남 자기 시정. 광선 원점 (입 +33블록) 과 방향 (카메라 방향) 어긋나 표적 위 30블록 지나침. `cannonAimPoint()` 도입 (십자선 첫 교점 계산 · 관통). **자기공시: 시나리오 H 판정 상자 크기로 결함 통과** — §5.5 신규 P3.

**리뷰 판정:**
- **자기 회귀 파이프라인 재관측** (§5.6 · 40주차 두 브랜치 동시 관측).
- **§5.5 신규 P3** (smoke-test H 판정 상자 관대함) 자기공시 등재.
- Self-fixed 2건 (§5.6): 20x 카메라 회귀 · 광선포 조준.
- **PR #58 vs PR #10 정본 결정 여전히 미이행** · 활동 재개는 있으나 정본 결정 관측 없음.

### §8.2 PR #38 (khpuk3)

**HEAD `a9bbf3b5` **~6일 무커밋** (39주차 5일 → +1). tracked LIVE 유지 (`build_content.py` P1×2 · hope-shooter dispose · Unreal C++ 미검증). 신규 finding 없음.

### §8.3 PR #10 (tqv3ii)

**HEAD `844fb48b` **8일 무커밋** (39주차 7일 → +1). tracked LIVE — 동물/마을주민 dispose 누수 R8 확장 (P1 · **9주+3일**) · 동물 재질 per-instance jitter (P2 · 14일) · **warden 벽투과 (P1 · 15주+3일 — 최장 활동 브랜치 tracked P1)**. **PR #58 vs PR #10 정본 결정 77h+ 무진전** — §5.8.

### §8.4 main

**HEAD `281d6017` 마지막 커밋 2026-07-24.** PR #42 (Codex plugin) 머지 후 정지. 실질적 릴리즈 채널이 아님.

### §8.5 표본 (#30/#32/#48/#57)

- **PR #48 (28주차 자체 리뷰):** hand3d.js P2×2 + P3×3 · **9주+2일** 미이행. 자체 리뷰 PR 은 감시만.
- **PR #57 (HANDOVER.md):** HEAD `a28774a0` 78h+ 무진전. draft 상태 유지 · 결정 대기.
- **PR #30 (ISO 42001) / PR #32 (mecha chameleon):** 활동 없음 · 표본 감시.

---

## §9. Tracked LIVE 총괄 (40주차)

| PR / 브랜치 | 항목 | 방치 (40주차 갱신) |
|---|---|---|
| **PR #46** | **`js/render.js` dead-store (P0)** | **13주 확정** (blob 12일 무커밋) |
| PR #10 | 동물/마을주민 dispose 누수 R8 확장 (P1) | 9주+3일 |
| PR #10 | 동물 재질 per-instance jitter (P2) · warden 벽투과 (P1) | 14일 / **15주+3일** |
| PR #5 (B9Kxm) | Basel B RW · SRISK · CoVaR own-loss mask (P0×3) | **20주+3일** (최장 tracked P0) |
| PR #5 (B9Kxm) | 29주차 P2×2 + P3×4 · 30주차 P1+P2×4+P3×4 | active |
| PR #5 (B9Kxm) | 34주차 재분류 P1×1 + P2×2 | 120h+ |
| PR #5 (B9Kxm) | 35주차 신규 P1×4 · P2×6 · P3×4 | **120h+** (로직 파일 대확장 있으나 지정 항목 미시정 · 40주차 ALM 재구축 자원 배분 대상 아님) |
| PR #5 (B9Kxm) | 37주차 신규 P2 — BF602 basis 미표시 | **4일** (Pack v04 편성 없음, Regression 확정) |
| PR #5 (B9Kxm) | 39주차 신규 P1 — `test_req_trace.py` 표면 grep 검사 | **24h+ 미시정 · Regression 등재** |
| PR #5 (B9Kxm) | 39주차 신규 P2 — IV 요청 단독 무효화·재발부 프로토콜 (F-F04 파생) | **24h+ · 20차 IVR-8F60B82AE085 open · fingerprint drift 재발 · 21차 재발부 관측 없음** |
| PR #5 (B9Kxm) | 39주차 신규 P3 — README `sha256sum -c` clone-only 실패 | **24h+ 미시정 · Regression 등재** |
| **PR #5 (B9Kxm)** | **40주차 신규 P1 — ALM 이사회 팩 ΔEVE 갭 근사 · `alm_irrbb_engine_single_source` WARN (§5.1)** | **신규 · self-declared** |
| **PR #5 (B9Kxm)** | **40주차 신규 P2 — ΔNII 명목 55.5% 미산출 (pass_through_beta 원장 빔) (§5.2)** | **신규 · self-declared** |
| **PR #5 (B9Kxm)** | **40주차 신규 P2 — 잔존만기 축 사다리 미실체화 (§5.3)** | **신규 · self-declared** |
| **PR #5 (B9Kxm)** | **40주차 신규 P3 — `macro_indicator` 값 전건 basis="파생" (§5.4)** | **신규 · self-declared** |
| PR #4 (Pw9F5) | CHG-0143 + ERRATA (P0) | **19주** |
| PR #4 (Pw9F5) | conditional_approval 6차 canonical (P1) + P2×4 + P3×4 | **11일** |
| PR #4 (Pw9F5) | 33주차 P3×3 (validation_memory) · 34주차 P3×2 (reg_rules) | 168h~192h |
| PR #4 (Pw9F5) | 37주차 신규 P3×2 — F-F02 시정 파급 · F-F03 SA북 혼입 | **96h** |
| PR #48 | hand3d.js P2×2 + P3×3 | 9주+2일 |
| PR #38 | build_content.py · hope-shooter dispose · Unreal C++ 미검증 | 9주+2일 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 15일 |
| **PR #58** | **40주차 신규 P3 — smoke-test H 판정 상자 관대함 (§5.5, self-declared)** | **신규 · self-declared** |

**합계:** P0=**8** · P1=**14** (13→14, +ALM ΔEVE 신규) · P2=**26** (24→26, +ΔNII 신규 · +잔존만기 사다리 신규) · P3=**33** (31→33, +macro_indicator 파생 신규 · +smoke-test H 신규) = **81건 LIVE** (39주차 76 대비 +5 신규 · 전건 self-declared).

**최장 방치 갱신:**
- 최장 tracked P0: **B9Kxm Basel B RW · SRISK · CoVaR** — **20주+3일** (39주차 20주+2일 → +1일)
- 최장 tracked P1: **PR #10 warden 벽투과** — **15주+3일** (39주차 15주+2일 → +1일) — PR #58 활동 재개 (§8.1) · 정본 결정 대기
- 최장 확정: **PR #46 dead-store** — **13주 확정** (39주차 12주 → +1주)
- 최장 warden 미행동: **PR #46 external escalation** — **8주 무액션** (39주차 7주 → +1주) · **tracked 결함 최장 방치의 40% 도달** (39주차 35% → +5%p · 2주 연속 +5%p 정도 확대)

---

## §10. 다음 라운드 (41주차) 즉시 항목

39주차 이월 15건 + 40주차 신규 5건 (P1×1 · P2×2 · P3×2) = **20건**. 우선순위:

1. **PR #46 external escalation 실행** — 13주 확정 · **8주 무액션**. warden 사이클 non-forcing 완전 확정. 외부 채널 (승격·정지·저자 재할당) 필요는 재재재확인 · 40주차 새 강조점: **8주가 tracked 결함 최장 방치 (20주+3일 tracked P0) 의 40%에 도달** — 39주차 35% → +5%p · warden 프로세스 실패 방치 비율 2주 연속 +5%p 정도 확대.
2. **B9Kxm 40주차 신규 P1 (§5.1)** — 이사회 팩 ΔEVE 를 `worst_eve`/`by_scenario` 로 배선 · `alm_irrbb_engine_single_source` WARN 해소 · Pack v04 편성.
3. **B9Kxm 40주차 신규 P2 (§5.2)** — `alm_pass_through_beta` 원장 채움 (또는 caveat 자동화) · ΔNII 산출 스코프 게이트 등록.
4. **B9Kxm 40주차 신규 P2 (§5.3)** — `residual_maturity_ladder` 원장 등재 · 카탈로그 반영.
5. **B9Kxm 40주차 신규 P3 (§5.4)** — 프록시 정책 검토 · egress 확보 · 미확보 시 caveat 자동화.
6. **PR #58 40주차 신규 P3 (§5.5)** — smoke-test 전 시나리오 판정 상자 감도 재검토 · 결함 도입 대조 케이스 추가.
7. **B9Kxm 39주차 신규 P1 `test_req_trace.py`** — pytest --collect-only 파싱 · 2차 게이트 · **24h+ 미시정 Regression**.
8. **B9Kxm 39주차 신규 P2 IV 프로토콜** — 라이프사이클 명세 · **20차 IVR fingerprint drift 재발 관측 (21차 재발부 없음, 지연 상태)** · **24h+ 미시정 Regression**.
9. **B9Kxm 39주차 신규 P3 README clone-only** — **24h+ 미시정 Regression**.
10. **PR #10 vs PR #58 정본 결정** — **77h+ 무진전 · 40주차 warden 권고 등재 실행 조건 확정 발동** · 41주차 무진전 시 warden 권고 등재 실행.
11. **Pw9F5 dormant 2주차 · 41주차 활동 재개 여부** (§6). 41주차 dormant 지속 시 정식 3주차 (사상 초유 도달).
12. **B9Kxm P1-9/10/11/12** (35주차 승계 · 5주 이월).
13. **B9Kxm tracked P0×3 (Basel B RW · SRISK · CoVaR)** — **20주+3일 최장 tracked P0**.
14. **B9Kxm 자기공시 P2 (BF602 basis)** — **4일 이월 Regression**.
15. **B9Kxm P2×6 + P3×4 (35주차 승계)**.
16. **Pw9F5 F-F02 · F-F03 · conditional_approval P1 (11일)** — dormant 취소 시 우선.
17. **warden 스코프 확장 검토** — 재현성 · 인제스트 · 카탈로그 무결성 · **테스트 오탐 저하 유형 (40주차 §5.5 · 39주차 §5.1 반복 관측)** 반영 · 스코프 재정의 문서화.
18. **자기 회귀 파이프라인 관측 확대** (§5.6) — 40주차 두 브랜치 동시 관측. 저자 시정 사이클의 내부 상태 지표로 계속 관찰.
19. **B9Kxm ALM 재구축 후속 검증** — Pack v04 편성 시 계약·행동조정 두 기준 병기 상 감독 서식·이사회 팩 정합 확인 · 원화·외화유동성비율 (0.336 위반) 시행세칙 원문 참조 확보 시 절대수준 결재 판정 재검토.
20. **자체 감사 인프라 (적대적 검증 3렌즈) 성숙도 관찰 (§5.7)** — 27건 지적 · 10건 시정 · 3건 이월의 이번 라운드 케이스가 41주차 재현 여부 · 저자 감사 파이프라인의 실질적 warden 대체 지속 여부 추적.

**신규 대비 조기 항목:**
- Pw9F5 41주차 활동 재개 없으면 dormant 3주차 (사상 초유).
- PR #10 tracked P1 warden 벽투과 **16주** 갱신 임박.
- PR #46 **14주 확정** 임박 · warden non-forcing **9주 무액션** 임박.
- 40주차 신규 5건 이월 시 신규→다음 주 Regression 등재 파이프라인이 4주 연속 반복 (37주차 BF602 · 38주차 IV 백로그 → 39주차 P2 격상 · 39주차 신규 3건 → 40주차 Regression 3건 · 40주차 신규 5건 → 41주차 Regression 5건 예약).

---

## §11. 리뷰 방법 · 재현

**감시 대상 (40주차):**
- 8개 tracked HEAD (B9Kxm/Pw9F5/PR #38/PR #10/PR #46/PR #57/PR #58/main) 최신 SHA 조회.
- PR #46 blob SHA 대조 → `0e0288c93564fda41e881e87bfbc5f6c6a85ae28` = 39주차 대조값과 동일 확인.
- B9Kxm delta 커밋 9건 (`810f5b5` · `2fb990a` · `3feb9a6` · `5614fb0` · `1170a49` · `2827cc3` · `ccce6db` · `e6a2797` · `9c6005a`) 각각 커밋 메시지 · 파일 diff 통계 분석.
- PR #58 delta 커밋 3건 (`6b559bb` · `937d218` · `6bc8467`) 커밋 메시지 분석 (자기 회귀 자기 시정 · smoke-test 관대함 자기공시).
- Pw9F5 마지막 커밋 시각 확인 → 2026-08-05 16:34 UTC → 리뷰 시점 대비 ~76.5h → 48h+ dormant 상태 유지 확인.
- 표본 PR (#30/#32/#48/#57) HEAD 무변동 확인.
- delta 라운드 확정 후 심층 분석 수행 · 39주차 finding 지속성 재확인 (전건 Regression 등재) + 신규 P1/P2×2/P3×2 등재.

**신규 finding 판정 기준 (변동 없음):**
- **P0:** 실행 시 반드시 관측되는 결함 + 산출값 최소 1자리 이동. **0건.**
- **P1:** 실행 시 관측되는 결함이거나 phantom 값 생성 · 규제 산출 오차 배수급. **1건 (ALM 이사회 팩 ΔEVE 갭 근사 유지, self-declared).**
- **P2:** 라벨 mismatch · 감사 추적 왜곡 · 감시 blind spot · 특정 시나리오 발화. **2건 (ΔNII 55.5% 미산출, self-declared · 잔존만기 축 사다리 미실체화, self-declared).**
- **P3:** defense-in-depth, 오늘 미발화이나 계약/원장 무결성 저해 잠재. **2건 (macro_indicator 파생값, self-declared · smoke-test H 관대함, self-declared).**

**delta round 정의 (40주차 재확인):**
- 활동 브랜치 중 하나에서 5+ 커밋 · 로직 파일 광범위 변경. **40주차: 9커밋 · 43 파일 · +10,333/-521 라인 · 역대 1위 규모.**
- 신규 P1+P2+P3 다수 등재 (전건 self-declared) + 이월 검증 (§9 방치 카운트 +1) + 확정 격상 (§7 PR #46 12→13주) + 즉시 항목 이월 확대 (§10) 수행.
- 저자 대확장 시정이 warden 지정과 정렬 안 되는 패턴 재확인 (**9주 연속**).

**재현 절차:**
```
# 8개 HEAD 대조 (직전 라운드 대비)
for pr in 5 4 38 10 46 57 58; do
  gh pr view $pr --json headRefOid,updatedAt
done
git ls-remote origin main   # 281d6017 유지 여부

# B9Kxm delta 9건 확인
gh api repos/bbootta/AIops/commits?sha=claude/risk-management-agent-harness-B9Kxm\&since=2026-08-07T21:15:00Z
# → 810f5b5 · 2fb990a · 3feb9a6 · 5614fb0 · 1170a49 · 2827cc3 · ccce6db · e6a2797 · 9c6005a

# PR #58 delta 3건 확인
gh api repos/bbootta/AIops/commits?sha=claude/minecraft-dev-work-dhk8gr\&since=2026-08-07T21:15:00Z
# → 6b559bb · 937d218 · 6bc8467

# PR #46 blob 대조
gh api repos/bbootta/AIops/contents/js/render.js?ref=01fc7cb4 --jq .sha
# → 0e0288c93564fda41e881e87bfbc5f6c6a85ae28 (39주차 = 40주차 · blob 불변)

# Pw9F5 마지막 커밋 시각
gh api repos/bbootta/AIops/commits?sha=claude/validation-team-agent-Pw9F5\&per_page=1 --jq '.[0].commit.author.date'
# → 2026-08-05T16:34:06Z (76h+ 확정)

# B9Kxm 부분 시정 3건 (§5.1~§5.3) 확인 — 커밋 메시지 검색
git log 9c6005a -1 --format=%B | grep -A20 "부분 시정"
# → ΔNII pass_through_beta · 잔존만기 축 사다리 · 이사회 팩 ΔEVE 갭 근사

# PR #58 smoke-test H 관대함 자기공시 확인
git log 6bc8467 -1 --format=%B | grep "30칸"
# → "종전에는 보스가 38칸 거체라 30칸 어긋나도 스쳐 맞아서 이 결함을 통과시켰다"
```

---

## §12. 결론

**Δ:** 40주차 는 **역대 최대 규모 delta round**. B9Kxm +9 커밋 (43 파일 · +10,333/-521 라인) — ALM 엔진 전면 재구축 (`9c6005a`) · UI 대확장 (Executive/종합보고서 화면 · KRI 카드 · 거시지표 모니터링) · 검증 가정 30건 접이식 UI · AI틱 문구 42건 · 원장 109→131장 · 컬럼 +1,206. PR #58 +3 커밋 (활동 재개 · 자기 회귀 2건 자기시정 · smoke-test H 관대함 자기공시). Pw9F5 · PR #46 · PR #10 · PR #38 · PR #57 · main 전건 무커밋.

**39주차 즉시 항목 15건 중 0건 정합 · 15건 미이행** — B9Kxm 은 24h 자원 규모를 warden 지정 항목이 아닌 (a) ALM 엔진 전면 재구축 (b) UI 대확장 (c) 자기 회귀 즉시 시정 (한도 어휘 4건 · auto-viz 2건 · 11 dead deep-links · Minecraft 카메라·조준) 에 배분. **저자 자발적 시정 계약이 warden 지정 항목과 정렬 안 되는** 판정을 30/32~39주차 이어 **40주차 9주 연속 확정 재확인**. warden 지정 항목 이행률 정량: **0/15 (0.0%) 9주 연속**.

**신규 P1×1 · P2×2 · P3×2 전건 self-declared.** (a) ALM 이사회 팩 ΔEVE 갭 근사 유지 · `alm_irrbb_engine_single_source` WARN (§5.1) · (b) ΔNII 명목 55.5% 미산출 (§5.2) · (c) 잔존만기 축 사다리 미실체화 (§5.3) · (d) macro_indicator 값 전건 basis="파생" (§5.4) · (e) PR #58 smoke-test H 관대함 (§5.5). 4건 B9Kxm 자체 감사 (적대적 검증 3렌즈 27건 지적 중 부분 시정 3건 + macro_indicator egress 차단 1건) · 1건 PR #58 자체 감사. **자기공시 파이프라인이 warden 등재 파이프라인을 완전히 대체하는 구조** 가 40주차 신규 5건 전건 self-declared 로 재확인 (39주차 3건 self-declared 승계 · **2주 연속 신규 finding 전건 self-declared 확정**).

**Self-fixed 10+건 (같은 라운드 내 도입-회귀-시정 사이클)** — 한도 어휘 4건 (§4.6) · auto-viz 2건 (§4.2) · 11 dead deep-links (§4.4) · Executive ECL 단위 (§4.1) · 거시지표 최근값 단일 소스 (§4.5) · Minecraft 20x 카메라 회귀 (§8.1 `937d218`) · 광선포 조준 어긋남 (§8.1 `6bc8467`). **자기 회귀 파이프라인 확대 관측** — B9Kxm/PR #58 두 브랜치 동시 관측 (§5.6).

**PR #46 13주 확정 · warden non-forcing 8주 무액션.** ~85일 방치. warden 사이클 안 조치 소진 재재재확인. **8주 무액션은 tracked 결함 최장 방치 (20주+3일 tracked P0) 의 40%에 도달** (39주차 35% → +5%p) · **warden 프로세스 실패 방치 비율 2주 연속 +5%p 정도 확대**.

**Pw9F5 dormant 2주차.** 76h+ 무커밋 (39주차 53h → +24h) · 취소 조건 관측 없음. 41주차 활동 재개 없으면 **사상 초유 dormant 3주차** 도달. 20차 IVR-8F60B82AE085 open + fingerprint drift 재발 (B9Kxm 10k+ 라인 delta) · 21차 재발부 관측 없음 (지연 상태) · 39주차 P2 (IV 프로토콜 F-F04 파생) Regression 확대.

**PR #10 vs PR #58 정본 결정 77h+ 무진전 · 40주차 warden 권고 등재 실행 조건 확정 발동.** 41주차 무진전 시 warden 권고 등재 실행.

**Tracked LIVE 81건** (P0×8 · P1×14 · P2×26 · P3×33). 신규 P1×1 · P2×2 · P3×2 · Regression 3 (39주차 신규 3건 미시정) · Escalation 1 (PR #46 12→13주) · Reclassification 0. 최장 tracked P0 (**B9Kxm Basel B RW/SRISK/CoVaR — 20주+3일**) · 최장 tracked P1 (**PR #10 warden 벽투과 — 15주+3일**) · 최장 확정 (**PR #46 dead-store — 13주**) · 최장 warden 미행동 (**PR #46 external escalation — 8주**) 전건 연령 갱신.

**40주차 특기:** 
1. **역대 최대 규모 delta 라운드** (9커밋 · 10k 라인 · 43 파일) — 35주차 9커밋 대확장 · 39주차 5커밋 delta 초과.
2. **ALM 엔진 전면 재구축** — 기존 갭 근사 IRRBB 123줄 폐기 · 계약 현금흐름 엔진 (daycount/schedule/contracts/cashflow/behaviour/params/curves/nii/liquidity/irrbb/lcr/nsfr) 신설 · 원장 109→131장 · 컬럼 +1,206.
3. **적대적 검증 3렌즈 27건 지적 · 중대 10건 시정 · 3건 부분 시정** — 저자 자체 감사 인프라 확대 · 39주차 외부 데이터엔지팀 검토 6건과 유사 패턴 · 자기공시 파이프라인의 발견 채널 성숙 (§5.7).
4. **9주 연속 warden 지정 항목 정렬 없음 확정 재확인** — 저자 시정 파이프라인이 (1) 자체 감사 (2) 외부 팀 검토 (3) 자기 회귀 즉시 시정 (4) Pack 편성 (5) 자기공시 후 다음 라운드 도전 예약 의 5단계로 굳어짐 · warden 즉시 항목은 이 5단계 파이프라인 어디에도 진입 못 함이 9주 연속 확정.
5. **자기 회귀 파이프라인 두 브랜치 동시 관측** — B9Kxm (한도 어휘 4건 · auto-viz 2건 · 11 dead deep-links) + PR #58 (20x 카메라 · 광선포 조준) · 동일 라운드 내 도입-회귀-시정 사이클 · 저자 시정 인프라의 내부 상태 지표.
6. **테스트 오탐 저하 유형 2주 연속 자기공시** — 39주차 §5.1 (test_req_trace 표면 grep) · 40주차 §5.5 (smoke-test H 판정 상자 관대함) · **warden 스코프 확장 대상 후보로 확정.**

**머지 금지** — 리뷰 보고서 전달용 draft.
