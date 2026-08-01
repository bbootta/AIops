# [2026-08-01] 전체 저장소 코드 리뷰 — 33주차

**리뷰 시각:** 2026-08-01 21:07 UTC
**리뷰 대상:** `main` (SHA `281d6017` · 31일째 무변경) + open PR head 30건 표본
**직전 리뷰:** PR #52 (2026-07-31 21:11 UTC · 32주차)
**리뷰 브랜치:** `claude/stoic-ride-krq1eo`

---

## §0. 헤드라인

- **PR #4 (Pw9F5) 이 dormant 검토 조건을 취소 — 신규 커밋 1건 `170d7e05`** (검증 기억 계층 신설, 670 add / 11 files). Pw9F5 는 32주차 §4 tracked-active 유지.
- **PR #5 (B9Kxm) `553a4a8` SHA 3일 8h 무커밋 (~80.4h) — 32주차 §4 dormant 전환 3일 임계선 (72h) 도달.** 33주차에 정식 **tracked-active → tracked-dormant** 재분류.
- **PR #46 (nail sim) `01fc7cb4` SHA 5일 30h 무커밋 — P0 dead-store 6주 미이행 확정.** 32주차 external escalation 검토 조건 24h 무액션 지속 → 6주째.
- 그 외 12개 표본 브랜치 전부 zero-delta. `main` 30일+ 무변경.
- **Pw9F5 신규 커밋 심층 검토:** P0/P1/P2 신규 finding **0건**. 신규 P3×3 (regex 문자 클래스 · external member 존재 검사 우회 · n_rounds 파생 신뢰성). 32주차 tracked P1 (`conditional_approval.json` 회차 접미사) **미이행** — 새 커밋이 해당 파일을 만지지 않음.

---

## §1. 감시 활동 및 델타 요약

32주차 리뷰(PR #52, 2026-07-31 21:11:52 UTC) 이후 ~24h. 브랜치 표본 15개 감시:

| 브랜치 | 32주차 baseline SHA | 33주차 SHA | 델타 |
|---|---|---|---|
| `main` | `281d6017` | `281d6017` | zero (31일) |
| `claude/nail-simulation-program-i79qef` (PR #46) | `01fc7cb4` | `01fc7cb4` | zero (6주) |
| `claude/minecraft-game-tqv3ii` (PR #10) | `844fb48b` | `844fb48b` | zero (32주차 R8 이후) |
| `claude/3d-shooting-game-khpuk3` (PR #38) | `6f9cfb13` | `6f9cfb13` | zero |
| `claude/skills-plugin-install-nk7ez7` (PR #22) | `907839e2` | `907839e2` | zero |
| `claude/mecha-chameleon-game-xyiguj` (PR #32) | `e63e5d26` | `e63e5d26` | zero |
| `claude/iso-42001-agent-compliance-exq9qe` (PR #30) | `38376da7` | `38376da7` | zero |
| `claude/global-harness-enhancement-1v9b78` (PR #9) | `133985a2` | `133985a2` | zero |
| `claude/stock-trading-agent-harness-ZuSJc` (PR #2) | `f8867b8f` | `f8867b8f` | zero |
| `codex/create-trading-agent-…` (PR #6) | `98cb1a46` | `98cb1a46` | zero |
| `codex/improve-operational-package-…` (PR #3) | `5a2200e3` | `5a2200e3` | zero |
| `codex/fix-validation-team-agent-ci-…` (PR #7) | `a60443b4` | `a60443b4` | zero |
| `codex/fix-validation-team-agent-ci-…-uaix1g` (PR #8) | `574f8a1c` | `574f8a1c` | zero |
| **`claude/risk-management-agent-harness-B9Kxm` (PR #5)** | `553a4a8d` | `553a4a8d` | **zero (~80h · 3일 8h)** |
| **`claude/validation-team-agent-Pw9F5` (PR #4)** | `59032de` | **`170d7e05`** | **+1 커밋** |

**신규 PR:** 없음. PR #52 이후 신규 open PR 0건.

**단일 델타:** `claude/validation-team-agent-Pw9F5` `59032de` → `170d7e05` (2026-08-01 00:19:56 UTC).

---

## §2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **0** |
| 신규 P2 | **0** |
| 신규 P3 | **3** — Pw9F5 `tools/validation_memory.py` × 3 |
| Regression | **0** |
| Tracked LIVE 재확인 | **50건 유지** — P0×8 · P1×7 · P2×16 · P3×19 (Pw9F5 신규 P3 3건 추가로 총 53) |

---

## §3. Pw9F5 신규 커밋 `170d7e05` 심층 검토

**커밋:** `170d7e05` "아키텍처 고도화: 검증 기억 계층 신설 — 회차·계보·자기결함·이월을 생성값으로" (2026-08-01 00:19:56 UTC · Claude Fable 5 authored)
**규모:** 670 add / 0 del · 11 files (신규 6 · 수정 5).
**핵심 변경:**

- `validation-team-agent/memory/validation_rounds.jsonl` (신규, 15줄) — 15회 독립검증 백필, 회차·판정·게이트·심각도 카운트 원장.
- `validation-team-agent/memory/finding_patterns.json` (신규, 55줄) — 4개 결함 계보 (P-DOC/P-RECALC/P-CTRL/P-STALE).
- `validation-team-agent/memory/self_defects.jsonl` (신규, 6줄) — 3선 자기결함 6건.
- `validation-team-agent/memory/carryover_register.jsonl` (신규, 9줄) — 이월·미확인 9건.
- `validation-team-agent/tools/validation_memory.py` (신규, 322줄) — rounds/patterns/self-defects/carryover/verify 5개 서브커맨드 CLI.
- `validation-team-agent/tests/test_validation_memory.py` (신규, 224줄) — verify 15개 규칙에 대한 반증 테스트 22건.
- 수정 5건: `harness/system_prompt.md` (+21) · `harness/change_manifest.json` (+15) · `src/vta/cli/__main__.py` (+1) · `tools/cli_index.py` (+1) · `README.md` (+1).

### §3.1 강점 (긍정 평가)

- **설계 원칙 일관성:** verify 규칙 15종 각각에 대해 위반 fixture 로 반증하는 테스트가 짝지어져 있음 — F-602/F-E01 교훈 ("실패할 수 없는 검사는 통제가 아니다") 이 자기 산출물에 적용됨.
- **파생값 강제:** `severity_counts` 는 `findings` 실계에서 파생 강제 (line 125-129). `verdict` 는 최고 심각도에서 파생 강제 (line 131-135). 반복 횟수는 `len(members)` (F-501 원칙).
- **참조 무결성:** 프로토콜 `origin` 이 가리키는 F-XXX 는 회차 원장에 실재해야 통과 (line 185-190). 패턴 멤버·자기결함 근거도 동일 (line 148-151, 175-176).
- **회차 게이트 예외 사유 필수:** gate 가 파생값과 다를 때 `gate_note` 필수 (line 137-141) — 1~3차 조건부 경로 미존재 시기를 정확히 커버.
- **테스트 배선 확인 완료:** `test_cli_verify_exit_codes` 는 exit code 1 을 강제 (line 216-224).

### §3.2 신규 finding

#### P3-1: `_FINDING_REF` 정규식 문자 클래스 `[0-9A-E]` — 향후 F-F01+ 범위 확장 시 조용히 검사 우회

**파일:** `validation-team-agent/tools/validation_memory.py:50`

```python
_FINDING_REF = re.compile(r"F-[0-9A-E]\d{2}")
```

**현재 상태:** 15회차까지 finding ID 는 F-001 ~ F-E05. 첫 문자 범위 [0-9A-E] 로 전부 커버됨.

**failure scenario:** 16회 이후 F-F01, F-G01, F-H01 등이 회차 원장에 추가되면 `_FINDING_REF.findall(origin)` 이 해당 ID 를 매치하지 않음. 프로토콜 `origin` 문자열이 "이 도전은 F-F01 에서 태어났다" 라고 적혀 있어도 `for fid in _FINDING_REF.findall(origin)` 이 빈 리스트를 반환 → **origin 역참조 검사가 침묵으로 우회**. `F-F01` 이 회차 원장에 존재하는지 여부와 무관하게 문제가 보고되지 않음.

**격상 판정:** P3. 회차가 15회를 넘으면 활성화. 현재는 잠재적 결함.

**Fix cost:** 정규식을 `r"F-[0-9A-Z]\d{2}"` 로 확장하거나 (~5개 문자 추가 · 1줄 수정) 회차 원장에서 사용된 실제 first-char set 을 동적으로 유도. 후자가 원칙적으로 옳음 (파생값).

#### P3-2: `open_member_external=true` 가 존재 검사를 전면 우회 — 잠재적 미실재 참조 통과

**파일:** `validation-team-agent/tools/validation_memory.py:155-161`, `validation-team-agent/memory/finding_patterns.json:44-46` (P-STALE)

```python
if p["status"] == "live":
    om = p.get("open_member")
    if not om:
        problems.append(...)
    elif not p.get("open_member_external") and om not in all_findings:
        problems.append(...)
```

**현재 상태:** P-STALE 패턴이 `open_member: "F-E04"` + `open_member_external: true` 로 표기됨. F-E04 는 실제로 15회차 원장에 존재하지만 (round 15, F-E04, "적합"), `open_member_external=true` 로 인해 line 160 의 `om not in all_findings` 검사가 스킵됨.

**failure scenario:** 실수 또는 편집 오류로 `open_member: "F-XX99"` (미실재 ID) 를 넣고 `open_member_external: true` 로 표시하면 verify 통과. "external" 이 "회차 원장 밖" 을 의미한다면 검사 우회가 설계 의도지만, F-E04 처럼 실제로 회차 원장에 존재하는 것을 external 로 표기한 사례가 있어 의미론이 혼탁.

**격상 판정:** P3. F-E04 실재로 현재는 defense-in-depth 부재만 노출. 원장이 커지면 오탈자 유입 위험.

**Fix cost:** (a) `open_member_external` 을 제거하고 항상 all_findings 검사 (외부 참조는 pattern 밖 별도 필드로 분리), 또는 (b) external 이더라도 별도 `external_registry` 원장을 신설해 상호 실재 강제. 5~15줄.

#### P3-3: `n_rounds = len(rounds)` — 회차 sequence 위반 후 downstream 범위 검사의 상한 부풀림

**파일:** `validation-team-agent/tools/validation_memory.py:143`

```python
n_rounds = len(rounds)
```

**failure scenario:** JSONL 이 손상되어 `seq` 가 [1, 1, 2] (중복) 라 가정. Line 107 이 "회차 번호가 1..N 연속이 아니다" 를 problems 에 추가하고 계속 진행. `n_rounds = 3` (len 기반) 이지만 실제 max(seq) = 2. Self-defect `round=3` (실재하지 않는 회차 3) 이 line 173 `if not 1 <= 3 <= 3` 검사를 통과 (거짓 통과). Carryover `last_seen_round=3` 도 line 199 통과.

즉 sequence 무결성이 이미 깨진 상태에서 downstream 범위 검사가 부풀린 상한으로 오작동. 1차 위반은 이미 보고되므로 2차 위반의 침묵은 정보 손실.

**격상 판정:** P3. 정상 상태에서는 발현하지 않음. 원장 편집 사고 조합 시나리오만 활성화.

**Fix cost:** `n_rounds = max((r["seq"] for r in rounds), default=0)` (1줄 교체). 또는 sequence 위반 시 early-return.

### §3.3 32주차 tracked P1 (Pw9F5 conditional_approval 회차 접미사) 재확인

**tracked 항목:** "Pw9F5 30주차 conditional_approval 6차 스냅샷 canonical (P1) + P2×4 + P3×4" (PR #52 §요약).

**커밋 `170d7e05` 파일 명단에 `docs/independent_validation/RUN-20260630-42.conditional_approval.json` 없음.** 파일은 `RUN-20260630-42` 접두사 (평면 명명) 유지 — 회차 접미사 (`.round6.` 등) 부재 계속. **P1 미이행 · 4일차 (30주차 지적 이후 72+h)**.

커밋 메시지 "부수 정리" 절에는 IVR-68128ECE5694 조건부 결재 후속조건 3건을 원장에 기록했다고 서술 (F-604 검증) — 이는 **감사추적 기록** 이지 **파일 명명 이슈** 가 아님. 30주차 P1 은 여전히 LIVE.

### §3.4 판정 요약 (Pw9F5 신규 커밋)

- 신규 P0/P1/P2: **0건**.
- 신규 P3: **3건** (P3-1, P3-2, P3-3, 모두 `tools/validation_memory.py`).
- 32주차 tracked P1 미이행: 파일명 회차 접미사 그대로 · **4일 미이행**.
- 32주차 tracked P2×4, P3×4 (Pw9F5): 커밋이 해당 파일 (조건부결재 · 6차 스냅샷 · 관련 도구) 을 만지지 않음 → LIVE 유지.

**전반적 평가:** 커밋 자체는 **아키텍처적으로 훌륭함** (파생값 강제 · 테스트 반증 · 프로토콜 origin 역참조 · 이월 원장). 신규 finding 3건 모두 잠재적 · 미래 확장 시 활성화되는 유형. R8 (마인크래프트) 처럼 tracked P1 을 확장하지 않음 — 다른 파일 계층 (신설 memory/) 에서 작업. 즉 **긍정적 델타** (누수 확장 X, 새 감시 계층 +1). 다만 30주차 tracked P1 은 4일째 미이행.

---

## §4. B9Kxm 정식 dormant 재분류 (32주차 §4 조건 도달)

**32주차 §4 조건문:** "33주차 3일 연속 무커밋 시 정식 dormant 전환".

**33주차 관측:**
- `origin/claude/risk-management-agent-harness-B9Kxm` = `553a4a8d` (2026-07-29 12:42:18 UTC)
- 현재 (2026-08-01 21:07 UTC) 까지 **80h 25m · 3일 8h** 무커밋.
- **72h 임계선 초과** → 정식 dormant 재분류 조건 충족.

**재분류 결정:** `PR #5 (B9Kxm)` **tracked-active → tracked-dormant**. 후속 라운드에서는 delta-only 감시 (신규 커밋이 발생하면 즉시 tracked-active 복귀).

**tracked LIVE 유지:**
- 16주차 이후 Basel B RW · SRISK (1-k) · CoVaR own-loss mask (P0×3) — 16주차 (**LIVE 유지**)
- 29주차 cross_form · catalog · _headline · br_npl · BR-11 · check_strength (P2×2 + P3×4) — dormant 상태에서도 tracked
- 30주차 test_assumption_claims 자기충족 grep (P1) + P2×4 + P3×4 — dormant 상태에서도 tracked (**4일차**)

---

## §5. PR #46 `render.js` dead-store — 6주 미이행 확정

**격상 이력:** 26주차 P1 → 27주차 후보 → 28주차 P0 검토 규정 → 29주차 P0 격상 → 30주차 warden 프로세스 실패 → 31주차 external escalation 검토 조건 발동 → 32주차 5주 미이행 확정 → **33주차 6주 미이행 확정 · external escalation 검토 조건 지속**.

- HEAD `01fc7cb4` 그대로 (2026-07-27 14:30:51 UTC 이후 무커밋 · **5일 30h · 6일 6h**).
- `js/render.js` blob SHA `0e0288c9…` 유지.
- dead-store 3건 (`render.js:597, 601, 606` · ridges · side stroke · env reflection) 확정.

32주차 external escalation 검토 조건 발동 이후 24h 무액션 (커밋도 · 인간 결재도 · policy 조정도 없음). warden 격상 사이클 자체가 forcing 함수 없음이 실증 6주째.

**33주차 판정:** external escalation 검토 조건 6주 미이행 유지. 격상 사이클 자체가 non-forcing 임이 6주 연속 실증 — 격상 규정 자체의 재설계 필요성 재확인.

---

## §6. Tracked LIVE 요약

| PR / 브랜치 | 항목 | 방치 | 33주차 상태 변화 |
|---|---|---|---|
| **PR #46** | **`render.js:597,601,606` dead-store (P0)** | **6주** | external escalation 24h 무액션 지속 |
| **PR #10** | **동물/마을주민 dispose 누수 (P1) — R8 로 6→13 확장** | **5주** | 무변경 (R8 이후 무커밋) |
| **PR #10** | **동물 재질 per-instance jitter (P2)** | **~24h** | 무변경 |
| PR #5 (B9Kxm) | Basel B RW · SRISK (1-k) · CoVaR own-loss mask (P0×3) | **16주** | **tracked-dormant 재분류** |
| PR #4 (Pw9F5) | conditional_approval 6차 스냅샷 canonical (P1) + P2×4 + P3×4 | **4일** | 커밋이 대상 파일 미터치 |
| PR #4 (Pw9F5) | **NEW P3×3: validation_memory.py regex · external skip · n_rounds** | **~신규** | 이번 라운드 |
| PR #4 | CHG-0143 + ERRATA-2026-07-14 (P0) | **12주** | 무변경 |
| PR #48 | hand3d.js buildHand · pick · wheel · Blob revoke · pointercancel (P2×2 + P3×3) | 4주 | 무변경 |
| PR #10 | warden 벽투과 sonic LOS (P1) | **11주** | 무변경 |
| PR #38 | build_content.py · hope-shooter dispose · Unreal C++ 미검증 (P1×2 + 미검증) | 4주 / 6라운드 | 무변경 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 8일 | 무변경 |
| B9Kxm 29주차 | cross_form · catalog · _headline · br_npl · BR-11 · check_strength (P2×2 + P3×4) | 96h+ | dormant |
| **B9Kxm 30주차** | **test_assumption_claims 자기충족 grep (P1)** + P2×4 + P3×4 | **96h** | dormant |

**합계:** P0 = 8 · P1 = 7 · P2 = 16 · P3 = 22 (기존 19 + 신규 3) = **53건 LIVE**.

---

## §7. 34주차 즉시 항목

1. **PR #46 `render.js` 3줄 시정 + external escalation 실행** — 6주 미이행 확정, 24h 무액션 지속 · 6주 연속.
2. **PR #10 동물 sub-mesh 지오메트리·재질 공유화** — R8 확장 이후 누수 2.2× 지속. 약 30줄 편집.
3. **Pw9F5 `conditional_approval.json` 파일명 회차 접미사** — 4일 미이행. Pw9F5 활동 재개 확인됨 (`170d7e05`), 다음 커밋 사이클에서 우선순위.
4. **Pw9F5 `tools/validation_memory.py` 신규 P3×3 시정** — (a) 정규식 문자 클래스 확장 · (b) `open_member_external` 의미 분리 · (c) `n_rounds` max(seq) 파생. 총 ~10줄.
5. **B9Kxm 활동 재개 여부 모니터링** — dormant 상태 유지. 신규 커밋 발생 시 tracked-active 복귀.

---

## §8. 리뷰 방법 · 재현 절차

**감시 대상 브랜치:** 15개 (§1 표 참조).

**감시 명령:**
```
mcp__github__list_branches → SHA 비교 (32주차 baseline)
mcp__github__list_commits --sha=<branch> --since=2026-07-31T21:11:52Z
mcp__github__get_commit --sha=<new SHA> --detail=stats
```

**심층 검토 대상:** Pw9F5 `170d7e05` — 신규 파일 4개 (memory/) + 신규 도구 (`tools/validation_memory.py`) + 신규 테스트 (`tests/test_validation_memory.py`).

**재현 절차 (Pw9F5 신규 P3 3건):**
1. `git fetch origin claude/validation-team-agent-Pw9F5 --depth=2`
2. `git checkout FETCH_HEAD -- validation-team-agent/tools/validation_memory.py`
3. Line 50: `_FINDING_REF = re.compile(r"F-[0-9A-E]\d{2}")` — 문자 클래스 확인 (P3-1).
4. Line 155-161: `open_member_external` 조건 확인 (P3-2). `memory/finding_patterns.json` P-STALE 참조.
5. Line 143: `n_rounds = len(rounds)` — sequence 위반 시나리오 fixture 재현 가능 (P3-3).

**Tracked LIVE 재확인 방법:** 32주차 리뷰 §요약 표의 파일 경로·SHA 를 각 브랜치 HEAD 에서 재확인. 이번 라운드는 zero-delta 관측 (PR #5/PR #10/PR #46 등 SHA 무변화) 로 tracked 상태 자동 유지.

---

## §9. 리뷰 결론

- **PR #4 (Pw9F5) 이 tracked P1 (파일명 회차 접미사) 를 안 만졌지만, 신규 아키텍처 계층 (검증 기억 원장) 을 4개 신설. 아키텍처적 품질은 높음.** 신규 finding 3건 모두 P3 (잠재적).
- **PR #5 (B9Kxm) 는 정식 tracked-dormant.** 33주차 3일 조건 도달.
- **PR #46 은 external escalation 6주째 non-forcing.**
- 34주차 delta 관측 대상: (a) Pw9F5 tracked P1 이행 · (b) B9Kxm 활동 재개 · (c) PR #10 R9 pass · (d) PR #46 dead-store 시정.

**머지 금지** — 리뷰 보고서 전달용 draft.
