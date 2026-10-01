# [2026-07-06] 전체 저장소 코드 리뷰 — 11주차

## 요약

**지난 라운드 (PR #23, 2026-07-05) 이후 24h 무커밋.** PR #2/#4/#5/#10/#22 모두 head SHA 지난 라운드와 동일. 이번 라운드는 **재검증 (re-verify) + 세부 정정 (calibration)** 라운드로 진행. 리포트 라인이 이동한 finding 은 정확 위치로 갱신, 지난 라운드 리뷰가 과대/과소 기술한 항목은 소폭 정정.

**핵심 결과:**
- 지난 라운드 15건 finding 재확인 → **13건 LIVE (완전 확인) + 2건 부분 LIVE (문구 조정 필요)**
- 지난 라운드 리뷰 정정 4건 (파일 경로 1건, 방어 커버리지 1건, 카운트 1건, 영향 범위 1건)
- PR #22 에 대한 **fresh-eyes 스캔에서 신규 P1 5건** 추가 확인 (모두 skill-flow 가 프로젝트 boundary 밖 파일을 쓰거나 auto-commit 하는 패턴)
- PR #10 지난 주 fix 6건 중 **2건 (chest race guard · music burst throttle) 이 소스 상에서 확인되지 않음** — 지난 라운드 리뷰가 오판이거나 regression 가능성

## 지난 라운드 15건 재확인 매트릭스

| PR | Finding | 지난 표기 | 이번 재확인 | 상태 |
|---|---|---|---|---|
| #2 | `thinking={"type":"adaptive"}` | harness.py:194 | :194 | **LIVE (정확)** |
| #2 | `place_order` 음수 shares 가드 부재 | tools.py:213 | :213 | **LIVE (정확)** |
| #2 | exception swallow → stale APPROVED | harness.py:210 | :210 | **부분 LIVE** — `pass` 삭제되고 `print` + `last_text` append 됨. "silent swallow" 문구는 부정확, 그러나 결과적으로 stale `APPROVED` 을 `last_text` 로 재출력하는 증상은 잔존 |
| #2 | sticky approval + trade unbound | harness.py:82-141 | 82-141 | **부분 LIVE** — sticky-approval (line 104-105, 118-119, 132-133 에서 True 만 세팅) 확인. `trade` unbound 는 이 범위에 없음 (`result = trader.execute(query)` 사용). 지난 리뷰 기술 절반이 부정확 |
| #4 | permission_guard secret echo | permission_guard.py:107 | :118 | **LIVE (라인 이동)** — `check_commands` 가 `{"command": cmd, ...}` 로 원문 command 를 finding 에 첨부. Docstring 은 원문 금지를 명시 |
| #4 | scenario_weights dict-zip dedup | scenario_weights.py:82 | :84 | **LIVE (라인 이동)** — `dict(zip(sub[scenario_col], sub[weight_col]))` 로 duplicate scenario 라벨이 later-wins 통합 |
| #4 | record_feedback partial LIVE | classify_error.py:154+ | 동일 | **partial LIVE 재확인** — `_scan_feedback_for_sensitive` 게이트 존재하나 `--allow-sensitive` 로 bypass 가능하며, bypass/miss 시 원문이 `classify_feedback.jsonl` 에 verbatim 저장 |
| #5 | SRISK `(1-k)` 누락 | systemic.py:61 | :61 | **LIVE (정확)** — 코드/docstring 모두 잘못된 공식. Brownlees & Engle (2017) `(1-k)·(1-LRMES)·Equity` 대비 `(1-LRMES)·Equity` 로 (1-k) 누락 |
| #5 | Corporate B RW=1.00 (CRE20.44 위반) | rwa_sa.py:46 | :43 | **LIVE + 확장** — 동일 defect 가 Sovereign 표 (lines 20-27) · Bank 표 (lines 29-36) 에도 반복. 즉 3개 asset class 에 걸쳐 있음 (지난 라운드는 Corporate 만 지목) |
| #5 | CoVaR own-loss | systemic.py:113,121-122 | 동일 | **LIVE (정확)** — `system_loss = losses.sum(axis=1)` 후 `losses[:, i]` 로 conditioning → 자기 자신 손실이 포함되어 conditional 값 인플레이션 |
| #5 | FRTB yellow-zone plus-factor | frtb.py:161-162 | :154-158 | **LIVE (라인 이동)** — 코드 `{5:1.70, 6:1.76, 7:1.83, 8:1.88, 9:1.92}` vs Basel 기준 `{5:1.90, 6:2.00, 7:2.15, 8:2.25, 9:2.35}` (base 1.5 + plus-factor) |
| #10 | saveGame sync stall | index.html:2666/579 | 동일 | **LIVE (정확)** — 10s 간격 `JSON.stringify(전체 edits + chests)` + `localStorage.setItem` |
| #10 | applyPos NaN 통과 | index.html:2520-2527 | 동일 | **LIVE (정확)** — `isNaN`/`isFinite` 가드 없음. `player.pos.set(NaN, NaN, NaN)` 통과 |
| #10 | Nether respawn (overworld terrain) | index.html:1475-1476 | :1475-1478 | **LIVE (정확)** — `spawnY() = max(terrainHeight(0,0), SEA_LEVEL) + 2`, `curDim` 무시 |
| #10 | destroyBlocks CHEST branch 부재 | index.html:774-788 | 동일 | **LIVE (정확)** — creeper-explosion 경로에는 CHEST 분기 없음 (mining 경로 line 2162 에는 있음). 폭발 시 `chests` map orphan 잔존 |
| #10 | health NaN pass-through | index.html:2580 | :2580 | **LIVE (정확)** — `typeof NaN === 'number'` 통과, `Math.min(MAX, Math.max(1, NaN)) === NaN` |

**정리:** 13/15 완전 LIVE, 2/15 부분 LIVE (PR #2 P0#3, PR #2 P0#4 각 절반씩). 수정된 finding 없음.

## PR #22 재검증 + fresh-eyes

### 지난 라운드 6건 (P0×3 + P1×3) 재확인

**P0#1** `code-review` slug 충돌: **LIVE** — `.claude/skills/code-review/SKILL.md` frontmatter `name: code-review`. 프로젝트 내장 `/code-review` (diff 리뷰) 를 shadow.

**P0#2** `skills-lock.json` upstream pin 부재: **LIVE (경로 정정)**
- 실제 위치: **repo 루트 `/skills-lock.json`** (지난 라운드는 `.claude/skills/skills-lock.json` 로 기술 — 부정확).
- Top-level keys: `version`, `skills` 만. Repo-level `sourceCommit`/`ref`/`tag` 부재.
- 엔트리 필드: `source`, `sourceType`, `skillPath`, `computedHash` — 파일 단위 hash 는 upstream commit 이 아니라 fetch 결과의 파일 해시. 재fetch 시 upstream `main` 이 이동해도 매치할 대상이 없어 검증 실패.

**P0#3** `/implement` auto-commit: **LIVE** — `.claude/skills/implement/SKILL.md:12` 마지막 줄 verbatim `Commit your work to the current branch.`

**P1#4** `block-dangerous-git.sh` bypass: **LIVE (커버리지 정정)**
- 파일: `.claude/skills/git-guardrails-claude-code/scripts/block-dangerous-git.sh`, `if echo "$COMMAND" | grep -qE "$pattern"` over 리스트 `("git push" "git reset --hard" ... "push --force" "reset --hard")`.
- 지난 라운드 주장 정정:
  - `git push --force-with-lease` → **실제로는 차단됨** (substring `"git push"` 매치)
  - `false; git push --force` → **실제로는 차단됨** (동일 이유)
- 실제 bypass 표면 (재확인): `git   push` (double space), `git\tpush` (tab), `command git\ push` (backslash-space via `command` builtin), `"$(echo git) push"` (subshell), line-continuation `git\<newline>push`.
- Hook wiring 여부: **미연결** — `.claude/settings.json` 자체가 head SHA 에 없음. 사용자가 명시적으로 skill 을 install 하지 않으면 활성화되지 않음 → **잠재적 P2 로 재분류 권고**.

**P1#5** non-stable upstream 경로: **LIVE (카운트 정정)** — 13/38 = **34%** (지난 라운드 12/38 = 32%). 세부:
- `skills/deprecated/` (4): `design-an-interface`, `qa`, `request-refactor-plan`, `ubiquitous-language`
- `skills/in-progress/` (7): `claude-handoff`, `loop-me`, `wayfinder`, `wizard`, `writing-beats`, `writing-fragments`, `writing-shape`
- `skills/personal/` (2): `edit-article`, `obsidian-vault`

**P1#6** `/setup-matt-pocock-skills` 자동 트리거: **LIVE (조건부)**
- `triage/SKILL.md`: `"The mapping should have been provided to you - run /setup-matt-pocock-skills if not."`
- `code-review/SKILL.md`: `"The issue tracker should have been provided ... run /setup-matt-pocock-skills if docs/agents/issue-tracker.md is missing."`
- 무조건이 아니라 file-exist 게이트지만, 신규 리포에는 두 파일 다 없으므로 첫 실행 시 매번 트리거.

### 신규 P1 5건 (fresh-eyes)

**FRESH-P1 (a)** `.claude/skills/setup-pre-commit/SKILL.md` — skill 흐름 step 8 이 `.husky/`, `.lintstagedrc`, `.prettierrc`, `package.json` 수정 후 고정 메시지로 auto-commit. 프로젝트 boundary 밖 (`.claude/` 외부) 파일 다수 mutate + lockfile 갱신 + 사용자 승인 없는 commit.

**FRESH-P1 (b)** `.claude/skills/setup-matt-pocock-skills/SKILL.md` — `CLAUDE.md`, `AGENTS.md` 를 mutate 하고 `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `docs/agents/domain.md` 를 신규 생성. P1#6 의 구체적 side-effect.

**FRESH-P1 (c)** `.claude/skills/implement/SKILL.md` — 흐름 내부에서 `/tdd`, `/code-review` 자체 호출. P0#1 로 shadow 된 `/code-review` 를 자동 chain 하므로 `/implement` 실행 시 upstream two-axis 리뷰가 강제 발동.

**FRESH-P1 (d)** `.claude/skills/triage/SKILL.md` — `.out-of-scope/*.md` 을 repo 루트에 작성하고 issue tracker 에 AI-attributed 코멘트 (`> *This was generated by AI during triage.*`) 를 자동 게시.

**FRESH-P1 (e)** `.claude/skills/handoff/SKILL.md` — handoff 문서를 "the temporary directory of the user's OS" 에 저장. 공용 호스트에서 world-readable temp 경로 사용 위험 + sensitive-info 판별을 모델 자율에 위임.

### PR #22 P0-hunt 부정 결과 (안심 신호)

- `.claude/settings.json` **없음** — 하드코딩된 hook wiring 부재. Skill 은 사용자가 직접 install 해야 활성화됨.
- `.claude/skills/**/*.md`, `block-dangerous-git.sh` 내 **하드코딩된 token/URL/credential 미검출**.

## PR #10 지난 주 fix 6건 재확인

| Fix 항목 | 재확인 결과 |
|---|---|
| dispose cleanup | ✅ 존재 (line 711 mesh dispose, line 2465 `removeAllChunkMeshes`) |
| Y-ceiling clamp | ✅ 존재 (`if (y < 0 || y > Y_MAX) continue` at 779, 2101) |
| **chest race guard** | ⚠ **소스에 확인되지 않음** — `openChest` (line 2439) 은 `chestOpen` UI 플래그 세팅만. `chestLock`/`chestBusy` 등 sentinel 부재. 지난 라운드 리뷰 오판 또는 regression |
| fallDist reset | ✅ 존재 (declared 1461, reset 1481/1525/1596) |
| **music burst throttle** | ⚠ **소스에 확인되지 않음** — `setInterval(musicTick, 900)` at 847. `lastMusic`/burst-window/throttle 관련 identifier 부재. 지난 라운드 리뷰 오판 또는 regression |
| R keyup handling | ✅ 존재 (keyup at 1531-1533, keydown `!e.repeat` guard at 1529) |

**결론:** 4/6 확인, 2/6 미확인. 지난 라운드가 오판했을 가능성이 크나, 작성자가 커밋을 되돌렸다면 regression. Head SHA 미변경 = 이번 라운드가 지난 라운드보다 정확할 확률 높음.

## 결과 매트릭스 (10개 code PR)

| PR | 이번 커밋 | 이번 신규 findings | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#22** | 0 | **FRESH-P1×5** | P0×3 LIVE + P1×3 LIVE (2건 정정) | **block-merge**, 5개 fresh 정리 필요 |
| **#2** | 0 | — | P0#1/#2 완전 LIVE + P0#3/#4 부분 LIVE | **block-merge** (10주 무커밋) |
| **#4** | 0 | — | P0×2 LIVE + record_feedback partial | changes requested |
| **#5** | 0 | — | P0×2 LIVE + P1×2 LIVE, corp-B 영향 3개 asset class 로 확장 | **block-merge** |
| **#10** | 0 | — | P1×5 LIVE, 지난 fix 4/6 확인 · 2/6 미확인 | changes requested + 지난 fix 조회 필요 |
| #3 | 0 | — | 이전 권고 유지 | changes requested |
| #6 | 0 | — | 이전 권고 유지 | changes requested |
| #7 | 0 | — | 이전 권고 유지 | close 권고 |
| #8 | 0 | — | 이전 권고 유지 | close 권고 |
| #9 | 0 | — | 이전 권고 유지 | changes requested |

## 누적 11회 리뷰 결산

|  | #13 | #14 | #15 | #16 | #17 | #18 | #19 | #20 | #21 | #23 | **이번** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 신규 P0 | 4 | 0 | 4 | 7 | 10 | 3 | 4 | 0 | 1 | 3 | **0** |
| 신규 P1 | 8 | 0 | 6 | 18 | 24 | 9 | 13 | 0 | 8 | 3 | **5** |
| 누적 수정 | — | 0/9 | 0/15 | 0/22 | 0/32 | 0/44 | 0/57 | 0/57 | 7/57 | 7/60 | **7/65** |
| 오판 정정 | — | — | 2 | — | — | — | — | — | 2 | 0 | **4** (누적 8) |

**신호:**
- **24h 무커밋** — PR #22 를 포함한 5개 활성 PR 이 모두 정지. 지난 라운드 P0 지적에 대한 반응 없음.
- **정정 4건 발생** — 리뷰 자체의 세밀도가 상승 (파일 위치, 커버리지, 카운트, 영향 범위 순). 리뷰 quality gate 필요 신호.
- **fresh-P1 5건은 PR #22 의 skill install 채널에 집중** — 프로젝트 boundary 밖 mutate + auto-commit + AI-attributed 자동 게시 패턴이 반복적으로 나타남. 이 채널 전체가 프로젝트 CLAUDE.md ("NEVER commit changes unless the user explicitly asks you to") 와 정면 충돌.

## 다음 라운드 권고

**A. PR #22 우선 처리 (지난 라운드 권고 + 이번 정정):**
1. `code-review` slug 삭제/rename (1줄 fix, P0#1).
2. `/skills-lock.json` 에 upstream commit/ref/tag 추가 (P0#2).
3. `/implement/SKILL.md` `Commit your work to the current branch.` 삭제 또는 "ask the user first" 로 대체 (P0#3, 1줄 fix).
4. 신규 5개 fresh-P1 은 upstream 스킬 텍스트 원본 문제이므로 skill 채택 정책을 재검토: (i) upstream 을 fork 후 프로젝트 규칙에 맞춰 patched 버전 유지, 또는 (ii) 사용자 명시 승인 없이 auto-commit/repo-root-write 하는 스킬은 install-list 에서 제외.

**B. PR #5 지난 주 신규 P0 리마인드 (확장 반영):**
- `rwa_sa.py` corp-B RW 1.00→1.50 fix 시 **Sovereign · Bank 표 (lines 20-27, 29-36) 도 동일 fix 필요** — 3곳 병행 수정.
- `systemic.py:61` SRISK `(1-k)` 추가 — 1줄 fix + 회귀 테스트.

**C. PR #10 지난 fix 확인 필요:**
- `chest race guard` · `music burst throttle` 이 실제로 존재하는지 작성자 확인 요청. 없다면 지난 라운드 리뷰 오판 (누적 오판 정정에 반영), 있다면 명시적 identifier 로 재commit 요청.

**D. PR #2 10주 무반응 지속** — routine 이 fix-PR 직접 제출 옵션 (PR #20 A안) 재검토 권고.

## 리뷰 방식

3개 병렬 Explore 에이전트:
1. **PR #22 재검증 + fresh-eyes** — 6건 finding 원문 재확인, 63 파일 skill 번들 스캔, 프로젝트 boundary/CLAUDE.md 위반 패턴 헌팅.
2. **PR #2 + PR #10 재검증** — 각 finding 을 anchor 파일 원문 fetch 후 defect 문자열 매칭. 지난 fix 6건도 소스 상 존재 확인.
3. **PR #4 + PR #5 재검증** — 각 finding 원문 재확인, 정확 라인 갱신.

지난 라운드 대비 이번 라운드는 **재검증 심도** 를 높여 파일 위치 · 방어 커버리지 · 영향 범위를 세밀 정정. 총 출력 토큰 약 240K (지난 라운드 190K 대비 +26%). Head SHA 무변경으로 코드 리뷰가 아닌 리뷰의 리뷰가 절반 이상.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
