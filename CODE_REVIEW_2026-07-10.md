# 전체 저장소 코드 리뷰 — 14주차 (2026-07-10)

## 요약

지난 라운드 (PR #26, 2026-07-09 21:11 UTC) 이후 **24h 무커밋 · 단 하나의 신규 커밋** — PR #5 에 `26e9b324` (ISO/IEC 42001 AIMS 정렬, 2026-07-09 23:42 UTC) 만 유입. 나머지 11개 branch 는 head SHA 무변경.

- **신규 커밋** — PR #5 · `26e9b324` (+314/-4, 15 파일). 프로즈 (AIMS_POLICY.md, aims-compliance-auditor.md, 10개 agent .md 섹션) + `risk_lib/repro.py` 7줄 + `tests/test_extras.py` 13줄.
- **신규 P0** — 0건.
- **신규 P1** — 1건 (AIMS_POLICY.md 내 스페셜리스트 개수 자체 모순).
- **신규 P2** — 2건 (repro.py 의 `setdefault(asof, None)` 함정 · test 커버리지 갭).
- **Tracked 26건 재검증** — **26/26 여전 LIVE**. `26e9b324` 은 tracked 결함 0건 fix.

## 이번 라운드 신규 findings

### 신규 P0 · 0건

`26e9b324` 은 additive — 신규 마크다운 + `risk_lib/repro.py` 의 `build_manifest` 에 4줄 (얕은 복사 + `asof` setdefault). 순서 (caller-supplied 가 setdefault 앞) 은 정확 · caller dict 미변형 · headline_digest 는 head 만 참조하므로 영향 없음. Regression test (`test_extras.py`) 는 auto-fill / caller-wins 두 브랜치 커버.

### 신규 P1 · 1건 — PR #5

| 위치 | 요지 |
|---|---|
| `AIMS_POLICY.md:8` (§1) vs `AIMS_POLICY.md:32` (§3 RACI) | §1 은 **9 스페셜리스트**, §3 RACI 는 **8종** 명시. 실제 `.claude/agents/` 스페셜리스트는 8종 (bis-ratio · credit-rating · delinquency · ifrs9-ecl · limit · rapm · rwa · stress). 커밋 메시지 자체도 "8 specialists + 1 validator" 서술. §1 이 오기 — ISO/IEC 42001 감사에서 문서-현실 불일치로 부적합 사유. **fix: §1 을 "전문 에이전트 8 + 검증자 + 내부심사자" (총 11) 로**. |

### 신규 P2 · 2건 — PR #5

| 위치 | 요지 |
|---|---|
| `risk_lib/repro.py:~160` | `parameters.setdefault("asof", meta.get("asof"))` — `meta` 에 `asof` 없을 때 **`None` 을 명시적으로 기록**. 신규 `aims-compliance-auditor.md:~44` 은 "parameters.asof 가 없는 manifest 는 부적합" 을 검사하지만, 키 자체는 존재하고 값만 null 이 되므로 audit 이 silent pass. 실제 재현 시 `run_pipeline(asof=None)` 로 재실행하려다 undefined 경로. **fix: `if (a := meta.get("asof")) is not None: parameters.setdefault("asof", a)`**. |
| `tests/test_extras.py:~260` | 신규 회귀 테스트가 `result.meta` 부재 케이스 미커버 — `getattr(result, "meta", None) or {}` fallback 경로 무테스트. 위 P2 fix 시 함께 케이스 추가 필요. |

## Tracked 26건 재검증 결과

**전체 26/26 여전 LIVE.** `26e9b324` 이 markdown-only + 좁은 코드 변경이므로 예상된 결과. 라인 이동만 반영.

### PR #2 (12주 무커밋)

| # | 위치 | 상태 |
|---|---|---|
| 1 | `harness.py:194` `thinking={"type":"adaptive"}` | **P0 LIVE** |
| 2 | `tools.py:234` (was ~213 — 21 라인 shift) `place_order` 음수 shares 무가드 | **P0 LIVE** |
| 3 | `harness.py:210` `except (APIError, Exception)` | P0 부분 LIVE |
| 4 | `harness.py:82-141` sticky approval | P0 부분 LIVE |

### PR #4 (지난 주 무커밋)

| # | 위치 | 상태 |
|---|---|---|
| 5 | `pack_archive.py:99,107` path traversal | **P0 LIVE** |
| 6 | `report_pack.py:3718` Basel III Total-cap `+ 0.03` | **P1 LIVE** |
| 7 | `report_pack.py:3692` cet1 pillar1 hardcode | **P1 LIVE** |
| 8 | `permission_guard.py:118` secret echo | **P1 LIVE** |
| 9 | `scenario_weights.py:84` dict-zip dedup | **P1 LIVE** |

### PR #5 (이번 주 additive 커밋 1건)

| # | 위치 | 상태 |
|---|---|---|
| 10 | `risk_lib/systemic.py:61` SRISK `(1-k)` 누락 | **P0 LIVE** |
| 11 | `risk_lib/capital/rwa_sa.py:26 · 36 · 46` (line shift 각 +2) Sovereign/Bank/Corporate B RW=1.00 | **P0 LIVE** (Corporate B 는 CRE20 명확 위반) |
| 12 | `risk_lib/systemic.py:122` (was ~120) CoVaR own-loss mask | **P0 LIVE** |
| 13 | `risk_lib/frtb.py:166` (was ~161) FRTB 백테스트 multiplier ({5:1.70, 6:1.76, 7:1.83, 8:1.88, 9:1.92}, BCBS MAR99 은 1.90/2.00/2.15/2.25/2.35) | **P0 LIVE** |
| 14 | `ops_pages/governance.py:526` pillar3 deprecated 미제거 | **P1 LIVE** |

### PR #9 (무커밋)

| # | 위치 | 상태 |
|---|---|---|
| 15 | `reports/…-2026-06-10.html:154-161` T1×5 · locator=TBD | **P0 LIVE** (C-001·C-004·C-005·C-006·C-008 다섯 행 모두 T1 배포) |
| 16 | `harness/risk-research-runbook.md:78·96·141` G3-G5 prose-only | **P1 LIVE** |

### PR #10 (지난 주 e09336f hotbar 커밋 이후 무커밋)

| # | 위치 | 상태 |
|---|---|---|
| 17 | `index.html:2564` `applyPos` NaN pass-through | **P1 LIVE** |
| 18 | `index.html:783` `destroyBlocks` CHEST 미방출 | **P1 LIVE** |
| 19 | `index.html:2624` `save.health` NaN pass-through | **P1 LIVE** |
| 20 | `index.html:1484` Nether respawn (curDim 미리셋) | **P1 LIVE** |
| 21 | `index.html:588` saveGame sync stall | **P1 LIVE** |
| 22 | `index.html:2627` (was ~2604) load-time `for (const k in inv)` | **P2 LIVE** (지난 주 신규) |
| 23 | `index.html:343` `BLOCK.SNOW` self-drop 부재 | **P3 LIVE** (지난 주 신규) |

### PR #22 (무커밋)

| # | 위치 | 상태 |
|---|---|---|
| 24 | `skills-lock.json` `sourceCommit` 부재 (grep = 0) | **P0 LIVE** |
| 25 | `.claude/skills/code-review/SKILL.md` slug 충돌 | **P0 LIVE** |
| 26 | `.claude/skills/implement/SKILL.md:13` `/code-review` chain + auto-commit | **P0 LIVE** |

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#5** | 1 (additive) | P1×1 + P2×2 | P0×4 + P1×1 LIVE | **block-merge** |
| **#4** | 0 | — | P0×1 + P1×4 LIVE | **block-merge** |
| **#9** | 0 | — | P0×1 + P1×1 (+이전 P1/P2 다수) LIVE | **block-merge** |
| **#22** | 0 | — | P0×3 LIVE | **block-merge** |
| **#2** | 0 | — | P0×4 LIVE (12주+ 무커밋) | **block-merge** |
| **#10** | 0 | — | P1×5 + P2×1 + P3×1 LIVE | changes requested |
| #3 | 0 | — | P1×3 + P2×7 LIVE | changes requested |
| #6 | 0 | — | P1×1 + P2×2 LIVE | changes requested |
| #7 / #8 | 0 | — | P1×2 + P2×2 LIVE | #7 close / #8 delta 검토 후 merge 가능 |

## 누적 14회 결산

|  | #23 | #24 | #25 | #26 | **이번** |
|---|---|---|---|---|---|
| 신규 P0 | 3 | 0 | 2 | 0 | **0** |
| 신규 P1 | 3 | 5 | 10 | 0 | **1** |
| 신규 P2 | ≥2 | — | 25 | 1 | **2** |
| 누적 수정 | 7/60 | 7/65 | 7/77 | 7/79 | **7/82** |

**해석.** 신규 P0/P1 은 지난 라운드 (0/0) 대비 소폭 상승 (0/1) — AIMS 정렬 커밋은 프로즈 위주로 안전한 편. 그러나 **tracked 26건 fix 여전 0건**. 특히 **PR #5 이 이번 주 코드 (`risk_lib/repro.py`) 를 실제로 touch 했음에도 4개 P0 (SRISK / Corporate B / CoVaR / FRTB) · 1개 P1 (pillar3) 어느 하나도 fix 안 됨** — 14주 연속 방치. AIMS 감사 인프라를 새로 짓기 전에 내부 감사 대상 (기존 정합 결함) 을 처리해야 한다는 신호.

## 다음 라운드 권고

1. **PR #5 신규 P1 (AIMS 문서 자체 모순)**: `AIMS_POLICY.md:8` 을 `AIMS_POLICY.md:32` 표 및 실제 `.claude/agents/` 카운트와 동기화. 1줄 fix.
2. **PR #5 신규 P2 (repro.py null asof)**: `setdefault` 를 `if (a := meta.get("asof")) is not None:` 가드로 감싸기 — aims-compliance-auditor 의 존재 검증이 실효되게 함.
3. **PR #5 tracked P0×4 (Basel/BCBS 수치)**: AIMS 인프라 라운드 (이번 커밋) 는 도메인 지식 필요 없는 형식 정합만 다룸. 수치 fix (SRISK 공식 · Corporate B RW 1.00→1.50 · CoVaR mask · FRTB multiplier BCBS MAR99 표) 는 각 1~3줄 mechanical. 다음 커밋에 포함시킬 것.
4. **PR #4 (P0 · 13주째 open)**: `pack_archive.add()` 에 `label = Path(label).name` 강제.
5. **PR #22**: `code-review/` 슬러그 삭제 + `skills-lock.json` `sourceCommit` 추가 + `/implement` chain 삭제. 14주 무커밋 지속.
6. **PR #10 (tracked P1×5)**: 5주 연속 방치. changes-requested 상태 유지.
7. **PR #2 (13주+ 무커밋)**: routine 이 fix-PR 직접 제출 옵션 재검토 (7-8주차 권고 유지).

## 리뷰 방식

**2개 병렬 Explore 에이전트 + 메인 재검증** — 이번 주 실질 코드 변화가 `risk_lib/repro.py` +7줄 밖에 없어 큰 fanout 불필요:

- **(A) PR #5 `26e9b324` 신규 커밋 fresh-eyes** — `mcp__github__get_commit sha=26e9b324 detail=full_patch` + `AIMS_POLICY.md`/`aims-compliance-auditor.md` 전문 + 10개 modified agent .md diff · 77K subagent tokens · 11 tool_uses.
- **(B) Tracked 26개 findings live-status 재검증** — PR #2/#4/#5/#9/#10/#22 각 anchor 원문 fetch 후 defect 문자열 매칭. 26/26 LIVE, 라인 shift 반영 · 161K subagent tokens · 45 tool_uses.
- **메인**: 11개 non-review PR head SHA 대조표 (지난 리뷰 대비 PR #5 만 이동) 확인, 스코프 한정, 결과 종합.

무커밋 PR (10개) 은 head SHA 무변경 근거로 mechanically LIVE 처리.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
