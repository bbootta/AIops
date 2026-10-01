# 전체 저장소 코드 리뷰 — 2026-07-16 (19주차)

## 요약

지난 라운드 (PR #33, 2026-07-15) 이후 ~24h. **감시 대상 12개 PR (#2, #3, #4, #5, #6, #7, #8, #9, #10, #22, #30, #32) 전부 head SHA 무변경.** 마지막 코드 커밋은 PR #5 (2026-07-14 10:52 UTC) — 리뷰 시점 기준 ~50h 무커밋.

- **신규 P0** — 0건.
- **신규 P1** — 0건.
- **신규 P2** — 0건.
- **신규 P3** — 0건.
- **Tracked 27건 재검증** — 스팟체크 7건 파일 실측 확인, 전건 LIVE 유지 (라인 이동 없음). FIXED × 1 유지 + PARTIAL × 3 유지 + **LIVE × 23 유지**.

이번 라운드는 delta 없음 → 신규 finding 도 없음. **8주차 lean (PR #20) 이후 두 번째 zero-delta 라운드**. 다만 tracked LIVE 는 지속 누적: PR #5 는 **5주 연속 exec/UI 만 만지고 본질 P0×4 미터치**, PR #2 는 **10주차 완전 방치**, PR #22 는 **7주차 close 권고 반복 무응답**.

## 이번 라운드 신규 finding · 0건

12개 감시 PR 모두 head SHA 무변경으로 신규 리뷰 대상 코드 없음. 아래 tracked LIVE 세부는 지난 18주차와 위치·상태 동일 (스팟체크 결과 반영).

## Tracked 27건 재검증 결과 (스팟체크 7건)

**전건 LIVE 유지 확인.** 이번 라운드 delta 커밋이 없으므로 라인 이동 없음. 다음 파일들을 각 head SHA 에서 실측 재검증:

### PR #4 — `validation-team-agent/tools/report_pack.py` (head `89a67fe5`, 4411 lines)

| 라인 | 코드 | 상태 |
|---|---|---|
| **3762** | `cet1_min_pillar1 = 0.045` | **LIVE** — Basel III minima SSoT (`load_thresholds()`) 위임 미이행. |
| **3788** | `total < cet1_required + 0.03` | **LIVE** — Total capital surcharge 는 8.0% - 4.5% = **0.035** 여야 함 (0.03 → CET1 4.5%+3.0%=7.5% 로 실 요구치 대비 완화). |
| **4354** | `salt = hashlib.sha256(f"vta-pack-salt-{args.seed}".encode()).digest()` | **LIVE** — 커밋 자체 주석: `"salt 가 추정 가능하므로 원본 파일 접근자는 재식별 시도 가능"`. `--secret-key` env-var 우선 처리 미도입. |

**추가로 확인:** 지난주 신규 P1 인 R39-R74 ICAAP `post_stress_level` 오라벨링 errata 프로세스 부재도 그대로 — `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 미발행, `change_manifest.json` CHG-0143 미등록 확인 (`git log` 상 last commit `89a67fe5` = 지난주 Round 77 QoQ 커밋).

### PR #5 — `risk_lib/systemic.py` (head `27582402`)

| 라인 | 코드 | 상태 |
|---|---|---|
| **61** | `srisk = prudential_ratio * debt - (1 - lrmes) * equity` | **LIVE** — Brownlees & Engle (2017) 정의는 `k·(D+(1-LRMES)·E) - (1-LRMES)·E`. 현행 식은 자산 대신 부채에 prudential ratio 적용 → capital shortfall 과잉 계상. |
| **122** | `mask = losses[:, i] >= thresh` | **LIVE** — CoVaR 정의 상 mask 는 시스템 전체 손실이 아닌 **개별 은행 i 자신의 손실**로 조건화. Adrian & Brunnermeier (2016) 는 `X^i = VaR^i` 로 조건, 여기선 own-loss quantile 상위 5% 만 걸림 → tail-dependence 왜곡. |

### PR #2 — `stock_trading/harness.py` (head `f8867b8f`, 10주차 방치)

| 라인 | 코드 | 상태 |
|---|---|---|
| **~210** | `last_text = last_text + f"\n\n[ERROR] tool_runner_failed: ..."` | **LIVE** — tool_runner exception 시 이전 last_text (unrelated turn) 에 에러 문자열 concat 후 최종 리포트 title 에 흘러들어감. PARTIAL 등급 유지. |
| **82-141** | `if verdict == "APPROVED": consulted["analyst"] = True` (동 패턴 risk/portfolio) | **LIVE** — run-level dict `consulted` 는 run 종료까지 sticky. Analyst 가 첫 종목 APPROVED 하면 두 번째 종목 REJECTED 여도 `consulted["analyst"]` 는 True 유지 → `instruct_trader` gate 통과 가능. |

### 그 외 tracked LIVE (스팟체크 미실시, 커밋 무변경 → 자동 유지)

- **PR #2 P0×2 LIVE + PARTIAL×2** (**10주 방치**): `harness.py:~205` thinking=adaptive · `tools.py:234` place_order 음수 shares.
- **PR #4 P0×1 + P1×2 LIVE + FIXED×1 + PARTIAL×3**: `pack_archive.py:82-83` path traversal · `scenario_weights.py:83` dict-zip dedup · `report_pack.py:3762/3788/4354` (위 표 참조).
- **PR #5 P0×4 + P1×1 + P2×2 LIVE** (**5주 연속 exec/UI 커밋만, P0 미수정**):
  - `systemic.py:61` SRISK `(1-k)` (위 표)
  - `systemic.py:122` CoVaR own-loss mask (위 표)
  - `rwa_sa.py:26/36/46` B-bucket RW=1.00 (Basel III D. Weights 대비 corporate B = 1.50)
  - `frtb.py:173` FRTB multiplier (BCBS MAR99 스케일 미적용)
  - `governance.py` Pillar 3 deprecated flag (미대응)
  - `repro.py:~178` `setdefault(asof, None)` (asof 부재 시 None 캐싱)
  - `AIMS_POLICY.md:8 vs :32` 카운트 불일치
  - `viz_advanced.py` sparkline synthetic 미고지 (지난주 신규 P2)
- **PR #9 P1×1 LIVE + PARTIAL×1**: `harness/risk-research-runbook.md` G3/G4/G5 prose-only.
- **PR #10 P1×5 + P1×2 + P2×1 + P2×3 + P3×1 LIVE** (3주 무변화): `applyPos` NaN L3390 · `destroyBlocks` CHEST L834 · `saveGame` sync stall L639 · `WORLD_VER=5` inv-loss L334 · blinkTeleport 벽 관통 · timeStop arrows 배열 성장 · Wither Storm 볼레이-체스트.
- **PR #22 P0×3 LIVE** (**7주 방치**): `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md:11+:13` /code-review chain + auto-commit.
- **PR #30 P1×1 LIVE** (3주 방치): `CLAUDE.md §0` + `docs/ISO-42001-AGENT-REQUIREMENTS.md` 소급 조항·CI check 부재.
- **PR #3/6/7/8 P1/P2 LIVE**: 10주 무변화 (#7·#8 은 base branch `claude/validation-team-agent-Pw9F5` 대비 **mergeable_state=dirty** — PR #4 base rebase 필요).

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#32** | 0 | — | P2×2 + P3×3 LIVE (2주 무변화) | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (**3주**) | **block-merge** (소급 조항 필요) |
| **#10** | 0 | — | tracked 12 LIVE (**3주 무변화**) | **block-merge** |
| **#5** | 0 | — | P0×4 + P1×1 + P2×2 LIVE (**5주 연속 방치**) | **block-merge / escalate** |
| **#4** | 0 | — | P0×1 + P1×3 LIVE + FIXED×1 · PARTIAL×3 | **changes requested** |
| **#3** | 0 | — | P1/P2 LIVE (**10주 방치**) | **owner 확인, 미회신 시 close** |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**10주 방치**) | **close 권고** |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | **block-merge** |
| **#22** | 0 | — | P0×3 LIVE (**7주 방치**) | **close 즉시 시행** |
| **#6** | 0 | — | P1×1 LIVE (10주 방치) | close |
| **#7** | 0 (dirty) | — | P1×1 + P2×1 LIVE | close (#8 이 승계) |
| **#8** | 0 (dirty) | — | P1×1 + P2×1 LIVE | base rebase 후 재검토 |

## 누적 19회 결산

|  | #27 | #28 | #29 | #31 | #33 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | 0 | 0 | **0** |
| 신규 P1 | 1 | 2 | 2 | 2 | 1 | **0** |
| 신규 P2 | 2 | 4 | 3 | 6 | 3 | **0** |
| 신규 P3 | — | — | — | — | 4 | **0** |
| 누적 수정 | 7/82 | 8/84 | 8/86 | 8/88 | 8/89 | **8/89** (미증가) |

**해석.**

1. **연속 2회 zero-delta 아닌 zero-commit** — 8주차 (PR #20) 는 delta 있으나 lean 이었고, 이번은 순수 무커밋. **50h 무커밋** 은 이 저장소의 통상 코드 흐름 (라운드당 3-4 커밋/PR × 2-4 PR/주) 대비 이례적 정지.
2. **PR #5 5주 연속 P0×4 방치** — 지난주 이미 escalate 표시. 이번주도 delta 없어 상황 악화. 특히 `systemic.py:61` (SRISK 잘못된 자산-대체) 과 `rwa_sa.py:26/36/46` (Basel corporate B RW=1.00) 은 **Basel III / FSS 리스크관리 하네스** 라는 PR 목적 자체를 훼손하는 결함. 코드 품질 문제 이전에 요건 미달.
3. **PR #22 7주차 close 권고** — 3주 연속 close 권고 (17주차→18주차→19주차). owner 응답 없음, 3 P0 유지, 하위 skill 슬러그 충돌 (`code-review/`) 이 다른 PR 의 slash command wiring 을 오염시킬 위험 지속.
4. **PR #2 10주차 완전 방치** — 지난주 "Owner 부재 시 close 고려" 로 격상. 이번주 그대로 → **close 절차 진입 권고**. sticky APPROVED / thinking=adaptive 는 새 harness 로 재작성이 실질 필요.
5. **PR #7/#8 base branch drift** — 두 PR 모두 base 는 `claude/validation-team-agent-Pw9F5`. base head SHA 는 `83fbb375` 로 실제 PR #4 head `89a67fe5` (Round 77) 와 이미 74 커밋 어긋남 → mergeable_state=dirty. 재작업 없이는 머지 불가.
6. **PR #30 소급 조항** — 지난주 지적 반복. 이 PR 이 open 인 상태에서 새 agent 추가 (예: PR #5, PR #4) 는 §0 위반 위험. block-merge 유지.

## 다음 라운드 권고

1. **PR #22 close 시행** — 3주 연속 권고 미이행, 7주 방치. owner 미응답 시 20주차 리뷰 전 시행.
2. **PR #2 close 절차** — 10주 방치, tracked P0×2 + PARTIAL×2 지속. `stock_trading` harness 는 실사용 흔적 없음.
3. **PR #5 P0×4 fix 강제** — 5주 연속 escalate. SRISK 식 / Corporate B RW / CoVaR mask / FRTB multiplier 4건 은 **`risk_lib` 정의 자체 오류** — UI 개선으로 상쇄 불가.
4. **PR #7 close, #8 base rebase** — codex/validation CI PR 2건 모두 base drift. #7 은 #8 이 승계 후 close, #8 은 base rebase 후 재리뷰.
5. **PR #4 errata + LIVE 3건 fix** — 지난주와 동일: `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` + `report_pack.py:3762/3788/4354` 3건.
6. **PR #30 소급 조항 추가** — 지난주와 동일.
7. **PR #32 polish** — 지난주와 동일 (startBtn.blur() + tongue CCD). 소규모 patch 로 즉시 mergeable.

## 리뷰 방식

**메인 스레드 단일 세션**:

- 12개 감시 PR head SHA 대조 → **12/12 무변경** 확인 (2026-07-14 10:52 UTC 이후 무커밋).
- `mcp__github__pull_request_read get` 로 각 PR 의 `head.sha` + `updated_at` 확인. #7/#8 `mergeable_state=dirty` 재확인.
- Tracked LIVE 스팟체크 3개 PR × 7건 (`report_pack.py` L3760-3795 + L4350-4360, `systemic.py` L55-70 + L115-130, `harness.py` L82-141 + L205-215) `raw.githubusercontent.com` 실측 fetch → 코드 문법 그대로 존재 확인.
- 이번 라운드 delta 없음 → 신규 finding 검색 대상 없음, 리뷰 방식 자동 축약.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
