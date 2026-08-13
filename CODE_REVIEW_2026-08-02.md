# 전체 저장소 코드 리뷰 — 34주차 (2026-08-02)

**직전 리뷰:** PR #53 (2026-08-01 21:11 UTC) 이후 ~24h.
**리뷰 시점:** 2026-08-02 21:xx UTC.
**결과 헤드라인:** **비-zero delta**. Pw9F5·B9Kxm·PR #38 3개 브랜치 동시 활성화, 각 ~1,000+ LOC. Pw9F5 규제 규칙 카탈로그 구축 및 CLAUDE.md §2 범위 재선언(CHG-0162/0163). **B9Kxm dormant → active 복귀** (32주차 §4 조건 취소, 3커밋 · 1,045 LOC). PR #38 skinned mesh 및 노출 chain 물리화(2커밋). PR #46 dead-store 7주째 확정.

---

## §1. 감시 활동 (24h)

| 브랜치 / PR | 직전 HEAD | 신규 HEAD | 신규 커밋 | LOC (add / del) |
|---|---|---|---|---|
| **Pw9F5** (PR #4, validation-team-agent) | `170d7e05` | `29eb4243` | **2** (CHG-0162 · CHG-0163) | +1,258 / -3 |
| **B9Kxm** (PR #5, risk-management-agent-harness) | `553a4a8d` (dormant) | `676b6531` | **3** (RWA 3레벨 · 메뉴 마커 제거 · 화면 대확장 8건) | +1,178 / -55 |
| **PR #38** (khpuk3, 3d-shooting-game) | `6f9cfb13` | `a9bbf3b5` | **2** (officer 재현 · skinned mesh) | 대량 (graphics) |
| PR #46 (i79qef, nail-simulator) | `01fc7cb4` | `01fc7cb4` | **0** | — (**7주째 무커밋**) |
| PR #10 · #32 · #48 및 기타 표본 | (변동 없음) | — | 0 | — |
| `main` | `281d6017` | `281d6017` | 0 | — (32일 무변경) |

**핵심 판정:**

1. **B9Kxm 33주차 §4 tracked-dormant 판정 취소.** 신규 3커밋 (`d0829639` · `7938f122` · `676b6531`) 이 dormant 임계선(72h) 도달 직후 화면 계층 전면 재편성으로 활성화. dormant flag 해제, tracked-active 복귀.
2. **Pw9F5 규제 규칙 카탈로그(`reg_rules.py` + `regulatory_rule_catalog.json`) 신설.** 3원칙(OVR-000 원문 주기 ≠ 내부 주기 · OVR-001 경과조치 유효일자 · OVR-009 폐기 수치 차단)을 기계로 강제. 25 신규 테스트, `output_floor_factor(date)` 로 상수 금지 원칙 실증. 자체 검증에서 **실질 발견 1건(CO-010: 15회 교환 내내 완전적용 계수 상수 사용)** 도출 — 카탈로그가 실효.
3. **PR #46 dead-store 7주째 확정.** HEAD `01fc7cb4` 6일 무커밋 지속. `render.js:597,601,606` blob SHA `0e0288c9…` 변동 없음. 33주차 external escalation 검토 조건 24h+ 무액션.
4. **신규 P3×5:** Pw9F5 `reg_rules.py` × 2, B9Kxm `code_scope.py` × 3.

---

## §2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **0** |
| 신규 P2 | **0** |
| 신규 P3 | **5** — Pw9F5 `reg_rules.py` × 2, B9Kxm `code_scope.py` × 3 |
| Regression | **0** |
| Escalation | **1** — PR #46 6주 → **7주 확정** |
| Reclassification | **1** — B9Kxm tracked-dormant → tracked-active (33주차 §4 조건 취소) |
| Tracked LIVE 재확인 | **53건 유지** + 신규 5 = **58** (P0×8 · P1×7 · P2×16 · P3×27) |

---

## §3. Pw9F5 심층 검토

### §3.1 CHG-0162 — 규제 규칙 카탈로그 (`ba2781a2`, 2026-08-02 13:57 UTC)

**신규 파일:**
- `harness/regulatory_rule_catalog.json` (+386)
- `tools/reg_rules.py` (+281)
- `tests/test_reg_rules.py` (+268)
- `harness/valdoc_coverage.json` (+222)
- `harness/valdoc_discrepancy_registry.json` (+65)

**설계 강점:**
- **원문 주기 ≠ 내부 주기 분리 강제.** `frequency_basis=LEGAL` 이면 `frequency_raw` 에 UNSPECIFIED_MARKER("정기적", "미명시", "폐기") 가 등장할 수 없음. 15회 교환 내 발생한 오표기 패턴을 카탈로그 무결성 검사로 재발 차단.
- **경과조치를 유효일자 규칙으로 표현.** `output_floor_factor(as_of)` 가 65%(2026) → 70%(2027) → 72.5%(2028~) 를 날짜에서 파생. 상수 하나(2선/3선 `FULLY_LOADED_FLOOR=0.725`) 로 박은 15회 교환 오류가 카탈로그 구축과 동시에 노출 → CO-010 등재.
- **그룹 유효기간 겹침/빈틈 검사 (`verify` § 그룹 스팬 루프).** 정렬된 (from, to) 쌍을 순회하며 무기한 rule 이후 후속 rule 존재 시 문제 등록, 인접 규칙 사이 1일 초과 갭 검출.
- **폐기 규칙 재사용 차단 (OVR-009).** `RETIRED` 는 `effective_to` + `replaced_by` 필수, `replaced_by` 실재 검사.
- **테스트 반증 짝 (규칙마다 위반 fixture).** 실패할 수 없는 검사는 통제가 아니다 — F-602/F-E01 교훈의 자기 적용.

**신규 P3 발견:**

#### P3-4 (Pw9F5): `verify()` `groups` 스팬 구축 시 `m["effective_from"]` 서브스크립트 (`reg_rules.py:104-107`)

```python
spans = sorted(
    ((_d(m["effective_from"]), _d(m.get("effective_to")), m["rule_id"])
     for m in members),
    key=lambda x: x[0] or date.min)
```

`ACTIVE` + `group_id` 을 가진 규칙이 `effective_from` 필드 자체를 결여하면 `KeyError` 로 `verify()` 가 크래시. 방어선은 catalog 편집 워크플로우이지만, `verify()` 는 문제를 **목록으로 돌려주는 계약** 이므로 크래시는 계약 위반. 앞서 line 91 의 유효일자 형식 검사도 `_d()` 호출 자체는 필드 존재를 가정 (`_d(r.get("effective_from"))` — `.get` 이므로 None 허용). 정합성을 맞추려면 `m.get("effective_from")` 로 통일 후 None spans 을 필터 또는 문제 등록.

**Fix:** `_d(m.get("effective_from"))` 로 교체 + None spans 필터. 3줄 편집.

**failure_scenario:** 카탈로그 편집자가 `group_id: OUTPUT_FLOOR`, `status: ACTIVE`, `frequency_basis: LEGAL` 규칙을 추가하며 `effective_from` 을 실수로 누락 → `pytest tests/test_reg_rules.py` 크래시 (KeyError), 다른 문제들도 함께 리포트되지 않음.

#### P3-5 (Pw9F5): `replaced_by` 체인 검증 부재 (`reg_rules.py:82-88`)

```python
elif r["replaced_by"] not in {x.get("rule_id") for x in rules}:
    problems.append(f"{rid}: replaced_by {r['replaced_by']} 가 카탈로그에 없다")
```

`replaced_by` 는 rule 존재만 확인, 상태(ACTIVE) 는 확인하지 않음. RETIRED-A → replaced_by RETIRED-B → replaced_by 없음 체인이 형성되면 A 폐기 후 어느 규칙이 활성인지 카탈로그로 알 수 없음. OVR-009 "폐기 수치 차단" 정신에는 `replaced_by` 가 ACTIVE 이어야 완결.

**Fix:** `replaced_by` 대상의 `status` 가 ACTIVE 인지 확인 (2줄).

**failure_scenario:** 규제 개정 2회 (규칙 A → B → C) 를 카탈로그에 반영하며 B → C 전환 시 B 의 `replaced_by=C` 갱신을 잊고 A 만 재폐기 → `A.replaced_by=B` 이지만 B 는 RETIRED, 활성 규칙 조회 시 A → B (retired) → dead-end.

### §3.2 CHG-0163 — 검증 범위 8부문 재선언 (`29eb4243`, 2026-08-02 15:25 UTC)

`CLAUDE.md §2` 를 RDM·BIS / 신용·RWA / ECL / 시장 / ALM·IRRBB·유동성 / 운영 / 통합위기 / 적합성검증 자체 8부문 표로 교체. 15회 교환 실행이 문서 범위(신용·ECL·스트레스 중심)보다 넓었던 P-DOC 정정. 각 부문을 `regulatory_rule_catalog` 담당 규칙과 연결. 지원 불가 영역·§5 금지 행위 무변경.

**품질 평가:** 문서와 실행 정합화 (Δ 0 → Δ 정정). 신규 finding 없음.

### §3.3 Pw9F5 tracked LIVE 재확인

| 항목 | 상태 | 방치 |
|---|---|---|
| CHG-0143 + ERRATA-2026-07-14 (P0) | LIVE | 13주 |
| `conditional_approval.json` 6차 canonical (P1) | LIVE | 5일 |
| 33주차 신규 P3×3 (`validation_memory.py` regex · external skip · n_rounds) | LIVE | 24h |
| **신규 P3×2** (`reg_rules.py` verify KeyError · replaced_by chain) | NEW | — |

---

## §4. B9Kxm 활동 재개 (dormant → active)

### §4.1 dormant 취소 판정

- 33주차 §4: "80h 25m 무커밋 → 32주차 §4 dormant 임계선(72h) 도달 → tracked-dormant 재분류".
- 34주차 관측: 2026-08-02 15:36 UTC (`d0829639`) 부터 3커밋 연달아 발생 (2026-08-02 15:36 · 15:43 · 17:01 UTC).
- 판정: tracked-dormant → **tracked-active 복귀**. 후속 라운드는 full-review 모드 (신규 커밋 없어도 표본 감시 지속).

### §4.2 신규 3커밋 요약

| SHA | 시각 | 주제 | LOC |
|---|---|---|---|
| `d0829639` | 15:36 | RWA 메뉴 3레벨 트리 (부문 개요 리프-부모) | 소 |
| `7938f122` | 15:43 | 메뉴 전면 재작성 (부문 마커 A/B/…/Δ 제거) | 중 |
| **`676b6531`** | **17:01** | **화면 대확장 8건** (오버레이/시뮬/한도/역스트레스/코드관리/ALM 분리/요약) | **+1,004 / -41** |

### §4.3 `676b6531` 심층 (8-item bundle)

**변경 파일:**
- `risk_lib/ui_studio/app.py` (+675) — 8건 화면 신설/개편
- `risk_lib/datamodel/code_scope.py` (**신규 +141**) — 계정·상품 마스터 + 리스크별 대상 규칙
- `risk_lib/datamodel/catalog.py` (+93) — 코드 매핑 카탈로그 확장
- `tests/test_ui_interactive.py` (+86 / -29) — 라벨 기반 탭 조회 이관, 인덱스 함정 해소

**신규 P3 발견 (`code_scope.py`):**

#### P3-6 (B9Kxm): `market_scope()` 파생 상품 risk_factor 통화 축 소실 (`code_scope.py:112-116`)

```python
"risk_factor": ("금리" if grp in ("파생", "자금") or c == "P-BND"
                else "주가" if c == "P-EQT"
                else "환율" if cur == "외화" else "—") if in_scope else "—",
```

`P-FXS` (통화스왑, grp="파생", cur="외화") · `P-OPT` (옵션, grp="파생", cur="외화") 는 `grp in ("파생", "자금")` 이 먼저 매치되어 risk_factor="금리" 로 확정. 통화스왑 1차 리스크는 FX+금리 조인트, 옵션은 기초자산 따라 갈리는데 통화 축이 소실. 매트릭스 화면의 리스크 요인 라벨링이 실제 편익과 어긋남. 산출 영향 없음 (표시용) 이지만 사용자가 이 표를 근거로 코드 예외 제안을 하면 오도.

**Fix:** cur == "외화" 우선순위를 파생/자금 앞으로, 또는 파생 세부구분(IRS/FXS/OPT) 별도 분기 (5줄).

**failure_scenario:** 사용자가 매트릭스 화면에서 P-FXS 를 조회 → "금리" 로 표시됨 → FX 스트레스 시 P-FXS 미포함을 정상으로 오인.

#### P3-7 (B9Kxm): `alm_scope()` LCR HQLA 분류가 1210 국공채 단독 (`code_scope.py:135`)

```python
"lcr_category": ("HQLA" if grp == "유가증권" and c == "1210"
                 else "유출" if st == "부채"
                 else "유입" if st == "자산" else "—"),
```

1220 회사채는 신용등급에 따라 HQLA L2A/2B 편입 가능 (Basel LCR §50-53). 이 표는 국공채만 HQLA 로, 회사채는 "유입" (자산) 으로 분류 → 유출량 대비 HQLA 커버리지 표시 시 회사채 보유분이 HQLA 에서 누락. SYNTHETIC 마스터의 표시상 라벨이라 산출 영향 없음이나, 이 표를 참조 자료로 사용하는 후속 개발이 편입 로직을 잘못 상속할 위험.

**Fix:** 회사채 신용등급 필드가 없으므로 HQLA 계층은 별도 매핑 원장으로 분리 (7~10줄) 또는 최소 주석으로 국공채-only 한계 명시.

**failure_scenario:** 유동성 화면 개발자가 이 함수를 HQLA 판정 SoR 로 오해 → LCR 분자 계산에 국공채만 반영 → HQLA 저평가.

#### P3-8 (B9Kxm): `credit_scope()` "9300 차입약정" 우리 신용 익스포저 오분류 (`code_scope.py:80-85`)

```python
in_scope = grp in ("대출채권", "유가증권", "예치금", "파생") or onb == "부외"
```

9300 (차입약정) 은 은행 자신의 차입 가능 한도 (someone else 가 우리에게 준 committed line) → **부채/자금 측** 이지 우리 신용 익스포저 아님. `onb == "부외"` 만으로 in_scope=True 처리 시 우리 EAD 로 잘못 표기 → `default_recognition="거래상대방 부도"` 로 붙임.

지급보증(9100) · 미사용약정(9200) 은 우리가 제공한 우발 자산 → 우리 신용 EAD 맞음. 9300 은 방향 반대.

**Fix:** 부외 항목 중 방향(제공/수령) 컬럼을 ACCOUNTS 에 추가하거나 9300 명시 제외 규칙 (2줄).

**failure_scenario:** 신용 RWA 화면 개발자가 이 in_scope 를 참조 → 9300 잔액을 CCF 환산 대상에 포함 → 신용 RWA 과대.

---

## §5. PR #38 (khpuk3, 3d-shooting) 델타

### 5.1 신규 커밋

- `9607bdbe` (2026-08-02 14:30 UTC) — Fix the officer, and stop the street blowing out to white. 6-각 촬영 근거 기반 수치 재조정.
- `a9bbf3b5` (2026-08-02 16:53 UTC) — Replace capsule limbs with real skinned mesh. body.js 신설, LBS 도입, 3개 issue (winding · shoulders wings · limb cap) 검증 기록.

### 5.2 검토 상태

두 커밋 모두 렌더링/기하 계층 (three.js 계열) 이며 커밋 메시지에 "Verified by screenshot at each step" 명시. 순수 그래픽 계층은 이번 라운드 심층 검토 우선순위에서 제외 (32주차 §7 표본 감시 기준). 다음 라운드에서 tracked LIVE 항목 (build_content.py P1×2 + Unreal C++ 미검증) 재확인.

---

## §6. PR #46 격상 — dead-store 7주 확정

**격상 이력:**

| 주차 | 판정 |
|---|---|
| 26주차 | P1 최초 발견 (render.js dead-store × 3) |
| 28주차 | P0 검토 규정 발동 (1주 미이행) |
| 29주차 | P0 격상 |
| 30주차 | warden 프로세스 실패 격상 |
| 31주차 | external escalation **검토 조건** 발동 |
| 32~33주차 | 5주 → 6주 미이행 (external escalation 검토 24h+ 무액션) |
| **34주차** | **7주 확정** — HEAD `01fc7cb4` 6일 무커밋, blob SHA `0e0288c9…` 유지 |

**판정:** warden 격상 사이클 자체가 forcing 함수 없음이 7주 연속 실증. 32주차에 제안된 external escalation 절차는 조건 발동 후 3주째 미실행 → 절차 자체가 non-forcing.

---

## §7. Tracked LIVE 총괄

| PR / 브랜치 | 항목 | 방치 |
|---|---|---|
| **PR #46** | **`render.js:597,601,606` dead-store (P0)** | **7주 확정** |
| **PR #10** | **동물/마을주민 dispose 누수 (P1) — R8 로 6→13 확장** | **6주** |
| PR #10 | 동물 재질 per-instance jitter (P2) | 8일 |
| PR #10 | warden 벽투과 sonic LOS (P1) | 12주 |
| PR #5 (B9Kxm) | Basel B RW · SRISK (1-k) · CoVaR own-loss mask (P0×3) | **17주 · active 복귀** |
| PR #5 (B9Kxm) | 29주차 P2×2 + P3×4 | active 복귀 |
| PR #5 (B9Kxm) | 30주차 test_assumption 자기충족 grep (P1) + P2×4 + P3×4 | active 복귀 |
| **PR #5 (B9Kxm)** | **NEW P3×3: code_scope.py 파생 risk_factor · HQLA 국공채-only · 9300 차입약정** | **~신규** |
| PR #4 (Pw9F5) | CHG-0143 + ERRATA-2026-07-14 (P0) | 13주 |
| PR #4 (Pw9F5) | conditional_approval 6차 canonical (P1) + P2×4 + P3×4 | 5일 |
| PR #4 (Pw9F5) | 33주차 P3×3 (`validation_memory.py`) | 24h |
| **PR #4 (Pw9F5)** | **NEW P3×2: reg_rules.py verify KeyError · replaced_by chain** | **~신규** |
| PR #48 | hand3d.js buildHand · pick · wheel · Blob revoke · pointercancel (P2×2 + P3×3) | 5주 |
| PR #38 | build_content.py · hope-shooter dispose · Unreal C++ 미검증 (P1×2 + 미검증) | 5주 / 7라운드 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 9일 |

**합계:** P0 = **8** · P1 = **7** · P2 = **16** · P3 = **27** (기존 22 + 신규 5) = **58건 LIVE**.

---

## §8. 다음 라운드 (35주차) 즉시 항목

1. **PR #46 `render.js` 3줄 시정 + external escalation 실행** — 7주 확정, 32주차 검토 조건 발동 후 3주 무액션. warden 사이클이 forcing 이 아님을 재확인만 반복하는 상태 종식 필요.
2. **PR #10 동물 sub-mesh 지오메트리·재질 공유화** — 6주 P1, R8 확장 이후 누수 2.2× 지속.
3. **Pw9F5 `conditional_approval.json` 파일명 회차 접미사** — 5일 미이행, 활동 재개(2 CHG) 에도 미터치.
4. **Pw9F5 `reg_rules.py` 신규 P3×2 시정** — verify KeyError 3줄, replaced_by ACTIVE 검사 2줄.
5. **B9Kxm `code_scope.py` 신규 P3×3 시정** — risk_factor 우선순위, HQLA 계층 분리, 9300 명시 제외 (총 ~15줄).
6. **B9Kxm active 복귀 정착 여부 재확인** — 34주차 활동은 UI 화면 계층에 집중. 17주 tracked P0×3 (Basel B RW · SRISK · CoVaR) 은 여전히 미터치.

---

## §9. 리뷰 방법 · 재현

**감시 대상:**
- `main` HEAD, 브랜치별 최신 3커밋 (`list_commits`), 33주차 tracked-active 브랜치 4개 (Pw9F5 · B9Kxm · khpuk3 · i79qef).
- 신규 커밋 발생 브랜치는 파일별 diff 확인 (`get_commit` stats + files).

**심층 대상 결정:**
- 신설 파일 우선 (`reg_rules.py` · `code_scope.py`) — self-contained 하며 규칙 밀도 높음.
- 신설 원장/JSON 은 tests 짝이 검증하므로 verify 로직만 검토.
- 순수 렌더링/기하 계층(PR #38) 은 표본 감시로 보류.

**신규 finding 판정 기준:** 실행 시 반드시 관측되는 결함이 아닌 방어선 이슈는 P3 (defense-in-depth). 산출값에 영향 없으나 후속 개발이 잘못 상속할 위험은 P3. 산출값에 영향 있으면 P2 이상.

**재현 절차:**
- `reg_rules.py` P3-4: `regulatory_rule_catalog.json` 에 `{"rule_id":"TEST","status":"ACTIVE","group_id":"OUTPUT_FLOOR","frequency_basis":"LEGAL",...}` 추가하되 `effective_from` 필드 자체 삭제 → `python -m tools.reg_rules verify` 실행 → `KeyError: 'effective_from'` 크래시.
- `code_scope.py` P3-6: `python -c "from risk_lib.datamodel.code_scope import market_scope; print(market_scope().query('product_code==\"P-FXS\"'))"` → risk_factor="금리".

## §10. 결론

**Δ:** 34주차 delta 는 33주차 대비 3배 규모 (3개 브랜치 활성화). 신규 P3 5건은 전부 방어선 이슈이며 산출 영향 없음. **B9Kxm dormant 복귀** 는 긍정 신호이나 17주 tracked P0×3 은 여전히 미터치, 활동 재개가 tracked 이슈 해소로 이어지지 않음. **Pw9F5 규제 규칙 카탈로그** 는 이번 라운드 최대 아키텍처 성과 — 상수 하나로 박아 온 15회 교환 오류를 카탈로그가 즉시 노출 (CO-010). **PR #46 7주** 는 warden 프로세스 자체의 forcing 부재를 실증.

**머지 금지** — 리뷰 보고서 전달용 draft.
