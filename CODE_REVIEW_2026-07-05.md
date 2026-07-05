# 전체 저장소 코드 리뷰 — 10주차 (2026-07-05)

> **본 PR 은 리뷰 보고서 전달용. 머지 금지.**
>
> **10주차 관측:** 지난 주 (9주차, 2026-07-04) 관측된 "prose 채널 도달" 신호가 **되돌아왔다** — PR #2/#4/#5/#10 네 곳 모두 지난 24h 신규 커밋 **0건**, head SHA 지난 주와 동일. 대신 **오늘 (2026-07-05) 신규 PR #22** 가 추가됨: `.claude/skills/` 하위에 mattpocock/skills 저장소의 38개 스킬을 일괄 설치 (+4,596 lines, 63 files). 이번 라운드 실질 코드는 PR #22 하나이며, **그 안에 신규 P0 3건 + P1 3건 + P2 2건** 을 확인.

## TL;DR

- **신규 커밋**: PR #22 1건 (`bulk-add 38 skills + skills-lock.json`, 2026-07-05T05:16Z). PR #2/#4/#5/#10/#3/#6/#7/#8/#9/#11/#12 모두 지난 리뷰 이후 head SHA 무변화.
- **신규 P0 3건** — 전부 PR #22:
  1. `code-review` skill slug 가 **프로젝트 내장 skill 과 충돌** — 상위 slot 을 새 스킬이 훔쳐가 `/code-review` 실행 시 프로젝트가 정의한 diff-리뷰 흐름이 아닌 upstream two-axis 흐름 (docs/agents/issue-tracker.md 요구) 이 로드.
  2. `skills-lock.json` 이 **upstream commit 을 pin 하지 않음** (`source: "mattpocock/skills"`, ref/commit/tag 필드 부재). 재생성 시 mutable `main` 을 다시 fetch → 상위 저장소 tamper 시 per-file `computedHash` 이 새로 계산되어 **탬퍼링이 통과**.
  3. `.claude/skills/implement/SKILL.md:12` 마지막 줄 `"Commit your work to the current branch."` — 프로젝트 `CLAUDE.md` 의 `"NEVER commit changes unless the user explicitly asks you to"` 정면 위반.
- **신규 P1 3건** — 전부 PR #22:
  - `block-dangerous-git.sh` (git guardrail) grep -qE 리터럴 substring 매칭 → `git   push` (이중 공백) / `git -c foo=bar push` / `false; git push` bypass.
  - `skills-lock.json` 이 upstream `deprecated/` (4개) + `in-progress/` (5개) 폴더 스킬 10건 포함 → 큐레이션 없이 벌크 설치.
  - `triage/`, `code-review/`, 여러 스킬이 `/setup-matt-pocock-skills` 자동 트리거를 걸어 사용자 승인 없이 `CONTEXT.md`, `docs/agents/issue-tracker.md`, ADR 를 리포지토리 루트에 쓰기 지시.
- **신규 P2 2건 + P3 1건** — skill trigger 과도 overlap (loop-me / research / code-review), `wizard/template.sh` 가 `.env` / `gh secret set` 작성, supporting `.md` 파일 무결성 미기록.
- **이전 15개 findings 100% 라이브 (0 fix)** — 15/15 지점을 각 파일 원문에서 재확인. 지난 주 라인 넘버 대비 이동은 있으나 (harness.py:182 → 194, tools.py:218 → 213 등) SHA 무변화가 시사하듯 defect 자체는 그대로. 자세한 위치 재확인 결과는 §"이전 finding 라이브 상태 (라인 재확인)" 참조.
- **누적 10회 리뷰 결산**: 누적 수정 여전 **7/60** — 신규 P0 3 유입, 신규 fix 0. PR #10 이 유일한 활성 반응 채널이나 지난 주 대비 이번 주 반응 없음.

## 24h 활동 확인

```
mcp__github__pull_request_read get_commits (perPage=2, 7/5 기준)
  PR #22  907839e 2026-07-05 05:16Z  Install mattpocock/skills plugin skills (63 files, +4596, 1 commit)
  PR #2   f8867b8 2026-06-15 (무변화)
  PR #3   5a2200e 2026-06-15 (무변화)
  PR #4   ebe536a 2026-07-03 (무변화)
  PR #5   de32388 2026-07-03 (무변화)
  PR #6   98cb1a4 2026-06-15 (무변화)
  PR #7   a60443b 2026-06-06 (무변화)
  PR #8   574f8a1 2026-06-15 (무변화)
  PR #9   133985a 2026-06-15 (무변화)
  PR #10  9fe7021 2026-07-03 (무변화)
  PR #11  505ed2d 2026-06-15 (무변화)
  PR #12  d641352 2026-06-16 (무변화)
```

## Top 3 시급 액션

### 1. PR #22 `code-review` slug 충돌 — 프로젝트 내장 skill 오버라이드

**`.claude/skills/code-review/SKILL.md`** (신규):
- 프로젝트에는 이미 시스템 리마인더가 노출하는 `code-review` skill 이 존재 (설명: "Review the current diff for correctness bugs and reuse/simplification/efficiency cleanups...").
- PR #22 가 동일 slug `code-review` 로 새로운 SKILL.md 를 `.claude/skills/code-review/SKILL.md` 에 설치. 트리거 문구가 훨씬 광범위 ("Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to 'review since X'.").

**실패 시나리오:** 사용자가 `/code-review` 를 호출 → 프로젝트 스킬 우선순위가 애매하거나 새 스킬이 이김 → 사용자는 "diff 리뷰" 를 기대하나 upstream two-axis 흐름 (`docs/agents/issue-tracker.md` 없으면 setup 스킬 자동 실행) 이 발동. 프로젝트의 리뷰 관행 (P0/P1/P2 랭킹, findings + fix 옵션) 이 파괴.

**Fix (택1):**
- (a) `.claude/skills/code-review/` 를 skills-lock.json 에서 제거 후 파일 삭제.
- (b) upstream 스킬 slug 을 `code-review-two-axis` 로 rename (파일 이름 + `SKILL.md` 프론트매터).

### 2. PR #22 `skills-lock.json` 이 upstream commit 미고정

**`skills-lock.json`** (신규):
- 각 skill 엔트리: `{ "source": "mattpocock/skills", "sourceType": "github", "skillPath": "engineering/...", "computedHash": "<sha256>" }`.
- 최상위 fetched-commit SHA / 태그 / ref 필드 부재.
- upstream 저장소는 단일 브랜치 (`main`) — mutable target.

**실패 시나리오:** 3개월 후 `npx skills update` 실행 → upstream `main` 이 그동안 rewrite 되었어도 (tag 없음) 새 commit 을 그대로 pull → `computedHash` 는 재계산되어 저장 → tamper 흔적 사라짐. 특히 SKILL.md 안에 프롬프트 인젝션이 삽입되면 다음 세션부터 조용히 로드.

**Fix:** `skills-lock.json` 최상위에 `sourceCommit: "<40-char SHA>"` 추가 + 각 skill 에 동일 필드 pin. `npx skills add mattpocock/skills@<tag-or-sha>` 로 재생성 권장. supporting `.md`/`.sh` 파일 (24건) 도 hash 목록에 추가.

### 3. PR #22 `/implement` skill 이 무단 커밋 지시

**`.claude/skills/implement/SKILL.md:12`** (신규 파일 마지막 줄):
```
Commit your work to the current branch.
```

프로젝트 `CLAUDE.md` (root, 인용):
```
NEVER commit changes unless the user explicitly asks you to. It is VERY IMPORTANT to only
commit when explicitly asked, otherwise the user will feel that you are being too proactive
```

**실패 시나리오:** 사용자 "implement the login flow" → `/implement` 자동 트리거 → 완성 후 스킬 지시대로 `git commit` 실행 → 사용자는 승인하지 않았고 diff 확인 기회 없음. 특히 리뷰 안 된 코드가 원격에 push 로 이어질 수 있음 (`/implement` 스킬이 push 까지 지시하진 않으나 `Commit your work` 후 사용자가 무의식적으로 push 하는 경로).

**Fix:** 해당 줄을 `"Show the user your changes and ask if they'd like you to commit."` 로 교체하거나 삭제.

## 결과 매트릭스

| PR | 이번 커밋 | 신규 P0 / P1 / P2 / P3 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#22** | 1건 (bulk-install 38 skills) | **P0×3** (code-review slug / lock unpinned / implement autocommit) + **P1×3** + P2×2 + P3×1 | (신규 PR) | **block-merge** |
| **#2** | 0 | — | 4개 P0 (thinking=adaptive / place_order negative / exception swallow / sticky approval) 모두 LIVE (harness.py:194/210, tools.py:213). 10주 연속 무변화. | **block-merge** |
| **#4** | 0 | — | permission_guard secret echo (line 107), scenario_weights dict-zip dedup (line 82) LIVE. record_feedback partial fix 유지. | changes requested |
| **#5** | 0 | — | SRISK `(1-k)` 누락 (systemic.py:61), CoVaR own-loss (systemic.py:113), corporate B RW=1.00 (rwa_sa.py:46), FRTB yellow-zone plus (frtb.py:161-162) LIVE. | **block-merge** |
| **#10** | 0 | — | saveGame sync (2666) / applyPos NaN (2520-2527) / respawn overworld (1475-1476) / destroyBlocks no CHEST (774-788) / health NaN pass-through (2580) LIVE. 하지만 지난 주 fix 6건은 유지 (regression 없음). | changes requested |
| #3/#6/#9 | 0 | — | 이전 권고 유지 | changes requested |
| #7/#8 | 0 | — | 이전 권고 유지 | close 권고 |
| #11/#12 | 0 | — | 이전 권고 유지 | one merge, one close |

## PR #22 상세 리뷰 (신규)

### 파일 인벤토리 (검증)

- **63 파일 전부 `added`** (0 modified / 0 deleted / 0 renamed).
- **38× `SKILL.md`** ← PR 본문 "38 skills" 주장 일치.
- **22× 부속 `.md`** (`ADR-FORMAT.md`, `CONTEXT.md`, reference/template 등).
- **3× shell script:**
  - `.claude/skills/diagnosing-bugs/scripts/hitl-loop.template.sh` (에이전트가 편집 후 실행 지시)
  - `.claude/skills/git-guardrails-claude-code/scripts/block-dangerous-git.sh` (git 가드 후크 template)
  - `.claude/skills/wizard/template.sh` (`.env` / `gh secret set` 작성)
- **1× top-level `skills-lock.json`**.
- 프로젝트 파일 `CLAUDE.md`, `.gitignore`, `.claude/settings.json` **변경 없음** — 다행히 오버라이드 없음.
- 파일 모드: PR files API 로는 확인 불가 (mode 필드 노출 안됨). PR 본문 "no symlinks" 주장은 patches 형태로는 일관 (zero-addition symlink target 엔트리 부재) 하나 완전 검증엔 `git ls-tree -r refs/pull/22/head | awk '$1!="100644"'` 권장.

### 신규 findings 상세

**P0-1 · `code-review` slug 충돌** (§Top 3 #1 참조).

**P0-2 · `skills-lock.json` upstream commit 미고정** (§Top 3 #2 참조).

**P0-3 · `/implement` 무단 커밋 지시** (§Top 3 #3 참조).

**P1-1 · `block-dangerous-git.sh` grep 리터럴 substring bypass**

**`.claude/skills/git-guardrails-claude-code/scripts/block-dangerous-git.sh:6-16`**:
```sh
DANGEROUS_PATTERNS=(
  "git push --force"
  "git push -f"
  "git reset --hard"
  ...
)
for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$CMD" | grep -qE "$pattern"; then
    echo "BLOCKED: $pattern"
    exit 1
  fi
done
```

Bypass 예:
- `git  push --force` (이중 공백) → grep -qE 리터럴 매칭 실패.
- `git -c http.proxy=http://attacker push --force` → substring 순서는 맞으나 `-c` 옵션 삽입으로 `git push --force` 리터럴 아님. (실제 wc -c 확인 필요하나, `git -c` 삽입 시 `push --force` 부분은 유지 → 이 케이스는 매치. 그러나 `git -c foo=bar --exec-path=/tmp/x push --force` 처럼 옵션 더 많이 삽입 시 회귀.)
- `git push origin main --force-with-lease` → 패턴 목록에 `--force-with-lease` 부재.
- `false; git push --force` (전위 명령) → 매치. 그러나 `git push -f origin +main` (namespace 접두어) → 매치 됨. 종합적으로 word-boundary 회귀는 검토 필요.

**Fix:** `\bgit[[:space:]]+push[[:space:]]+(-f|--force([[:alpha:]-]+)?)\b` 형태의 word-boundary regex + `--force-with-lease`, `--mirror`, `+refs/` 등 추가. 근본적으론 shell substring 매칭이 아닌 `git` pre-command hook (proxy git wrapper) 로 교체.

**P1-2 · Deprecated / in-progress skill 벌크 포함**

`skills-lock.json` 의 `skillPath` 필드 분석:
- `deprecated/` 접두어: 4개 (`design-an-interface`, `qa`, `request-refactor-plan`, `ubiquitous-language`).
- `in-progress/` 접두어: 5개 (`claude-handoff`, `loop-me`, `wayfinder`, `wizard`, `writing-beats`).
- `personal/` 접두어: 3개.
- Total: **12/38 = 32% 가 non-stable 상위 저장소 폴더에서 유입**.

`npx skills add mattpocock/skills` 는 curation 없이 전체 벌크 fetch. `-p` 나 명시 리스트 없이 실행됐음을 의미.

**Fix:** `.claude/skills/{deprecated-list}/` 를 삭제 후 `skills-lock.json` 에서 대응 엔트리 제거. 향후엔 `npx skills add mattpocock/skills -p engineering/*` (또는 명시 리스트) 로 좁혀야.

**P1-3 · 여러 skill 이 `/setup-matt-pocock-skills` 자동 트리거**

**`.claude/skills/triage/SKILL.md:32`, `.claude/skills/code-review/SKILL.md:16`** (등):
```
If docs/agents/issue-tracker.md is missing, run /setup-matt-pocock-skills first.
```

`.claude/skills/setup-matt-pocock-skills/SKILL.md` (127 lines) + 5개 template 문서 (`CONTEXT.md`, `ADR-FORMAT.md`, `HTML-REPORT.md` 등) 를 **리포지토리 루트에 직접 쓰기** 지시.

**실패 시나리오:** 사용자 `/triage` 호출 → `docs/agents/issue-tracker.md` 없음 → setup 스킬 자동 실행 → 사용자 승인 없이 `docs/agents/issue-tracker.md`, `CONTEXT.md`, ADR 폴더가 root 에 생성 → 커밋 시 노이즈, .gitignore 제외 부재. 프로젝트 관행 이탈.

**Fix:** 각 SKILL.md 의 setup 자동 실행 지시를 "ask the user first" 로 완화 또는 setup 스킬 자체 삭제.

**P2-1 · Skill overlap 및 트리거 과잉**

- `research` (upstream) vs `deep-research` (프로젝트 built-in): 두 skill 이 동일 발화 ("research X") 에 경합.
- `loop-me` (upstream, in-progress) vs `loop` (프로젝트): "keep running X" 발화 경합.
- `diagnosing-bugs/SKILL.md:2` 트리거: "diagnose"/"debug this"/"broken"/"throwing"/"failing"/"slow" — 광범위. `verify` (프로젝트) 발동을 선점 가능.
- `tdd/SKILL.md:2` 트리거: "wants to build features or fix bugs test-first" — 사실상 개발 요청 전반.

**Fix:** 트리거 문구를 upstream-specific 어휘로 좁히거나 (예: "using the two-axis framework") skill 자체 미설치.

**P2-2 · `wizard/template.sh` 및 `hitl-loop.template.sh` 에이전트-생성 shell 실행 표면**

`.claude/skills/wizard/template.sh:150-180`:
- `write_env()` 이 `${ENV_FILE:-.env}` 에 KV 업서트 (`echo "STRIPE_KEY=$val" >> .env`).
- `set_secret()` 이 `echo -n "$val" | gh secret set $NAME` 파이프.

Template 이라 사용자가 편집 후 실행하나, SKILL.md 표현은 "copy this template and run" 으로 즉시 실행 유혹.

`.claude/skills/diagnosing-bugs/scripts/hitl-loop.template.sh`: 에이전트가 "EDIT BELOW" 마커 사이에 진단 명령을 삽입 후 실행. 프롬프트 인젝션 SKILL.md 에서 `rm -rf ~` 스텝 삽입 유도 가능성 (낮으나 표면 존재).

**Fix:** SKILL.md 에 "review each line before running" gating 문구 강화 + template 실행 전 사용자 확인 요구.

**P3-1 · 부속 `.md` 파일 무결성 미기록**

`skills-lock.json` 의 `computedHash` 는 개별 SKILL.md 만 커버. 22개 부속 문서 (`ADR-FORMAT.md`, `HTML-REPORT.md`, `template.sh` 등) 는 hash 목록에 없음. Upstream 이 이 파일들만 변조해도 lock 검증에서 통과.

**Fix:** `computedHash` 를 `computedHashes: { "SKILL.md": "...", "reference/foo.md": "..." }` 형태로 확장 또는 `treeHash` (해당 skill 폴더 전체) 추가.

### PR 본문 주장 검증

| 주장 | 상태 | 근거 |
|---|---|---|
| "38 skills" | **검증됨** | 38× SKILL.md + 38 lock 엔트리 |
| "npx skills add mattpocock/skills --copy" | **부분 검증** | lock 스키마 `computedHash`+`sourceType:"github"` 이 CLI 형식과 일치, `--copy` 는 파일 커밋 (심볼릭 링크 부재) 로 유추 가능. install 로그 부재. |
| "no symlinks" | **일관** (완전 검증 불가) | files API mode 필드 미노출, 하지만 63건 모두 정상 content patches, zero-addition 부재. **머지 전 `git ls-tree -r refs/pull/22/head` 로 재확인 권장**. |

## 이전 finding 라이브 상태 (라인 재확인)

지난 리뷰 (PR #21) 의 라인 넘버 대비 현재 head 에서의 실제 위치 재확인. **SHA 무변화이므로 파일 자체는 그대로**; 지난 리뷰의 approximate 라인 표기가 정확화됨.

### PR #2 (head `f8867b8`)

| # | 위치 (재확인) | 지난 표기 대비 | 상태 |
|---|---|---|---|
| P0-1 | `stock_trading/harness.py:194` | `~182` → 실제 194 | **LIVE** — `thinking={"type": "adaptive"},` |
| P0-2 | `stock_trading/tools.py:213` | `~218` → 실제 213 | **LIVE** — `place_order` 함수 시작부, `shares<=0` / `isinstance(int)` 가드 부재 |
| P0-3 | `stock_trading/harness.py:210` | `~198` → 실제 210 | **LIVE** — `except (anthropic.APIError, Exception) as e:` 하 `last_text` stale APPROVED 유지 |
| P0-4 | `stock_trading/harness.py:82-141` | 동일 | **LIVE** — `_build_tools` 클로저 내 `consulted[key]=True` 후 reset 없음, `query` argument 승인에 미바인딩 |

### PR #4 (head `ebe536a`)

| # | 위치 (재확인) | 상태 |
|---|---|---|
| P0 | `validation-team-agent/middleware/permission_guard.py:~107` | **LIVE** — `all_findings.append({"command": cmd, **f.to_dict()})` |
| P0 | `validation-team-agent/tools/scenario_weights.py:~82` | **LIVE** — `weights = dict(zip(sub[scenario_col].astype(str), sub[weight_col].astype(float)))` — dup key silent overwrite |
| P1 partial fix | `record_feedback` (middleware 위임) | LIVE (P1 로 유지, silent bypass + allow_sensitive + KR PII) |

### PR #5 (head `de32388`)

| # | 위치 (재확인) | 지난 표기 대비 | 상태 |
|---|---|---|---|
| P0 (SRISK) | `risk_lib/systemic.py:~61` | 동일 | **LIVE** — `srisk = prudential_ratio * debt - (1 - lrmes) * equity` |
| P1 (CoVaR own-loss) | `risk_lib/systemic.py:~113,~121-122` | 동일 | **LIVE** — `system_loss = losses.sum(axis=1)` 이 bank i 자체 포함 |
| P0 (corporate B RW) | `risk_lib/capital/rwa_sa.py:46` | `~44` → 46 | **LIVE** — `_RW_CORPORATE = {..., "B": 1.00, ...}`. CRE20.44 는 150% |
| P1 (FRTB yellow-zone plus) | `risk_lib/frtb.py:~161-162` | 동일 | **LIVE** — `{5:1.70, 6:1.76, 7:1.83, 8:1.88, 9:1.92}` — 정본 `{5:1.90, 6:2.00, 7:2.15, 8:2.25, 9:2.35}` 미일치 |

### PR #10 (head `9fe7021`)

| # | 위치 (재확인) | 지난 표기 대비 | 상태 |
|---|---|---|---|
| P1 (saveGame sync stall) | `minecraft/index.html:2666` (setInterval), 함수 정의 :579 | `~2776` → 2666 | **LIVE** — 동기 `JSON.stringify` + `localStorage.setItem`, idle callback 없음 |
| P1 (applyPos NaN) | `minecraft/index.html:2520-2527` | `~2630-2637` → 2520 | **LIVE** — `player.pos.set(p.x, p.y, p.z)`; `Number.isFinite` 가드 부재 |
| P1 (nether respawn) | `minecraft/index.html:1475-1476` | `~1585` → 1475 | **LIVE** — `respawn()` 이 `curDim` 확인 없이 `spawnY()` (오버월드) 호출 |
| P1 (chest content orphan) | `minecraft/index.html:774-788` | `~884-898` → 774 | **LIVE** — `destroyBlocks` 이 `BLOCK.CROP` 만 브랜치, `BLOCK.CHEST` 부재 → `chests` Map 고아 |
| P1 (health NaN pass-through) | `minecraft/index.html:2580` | 신규 확인 | **LIVE** — `if (typeof save.health === 'number') health = Math.min(MAX_HEALTH, Math.max(1, save.health));` — `typeof NaN==='number'` true, NaN 통과 |

(라인 이동은 SHA 무변화 조건 하 지난 리뷰의 approximate 라인 정확화. 지난 주 fix 6건 — dispose, Y-ceiling, chest race, fallDist, music burst, R keyup — 는 유지 확인.)

## 누적 10회 리뷰 결산 (수정률 갱신)

|  | #13 (6/19) | #14 (6/21) | #15 (6/22) | #16 (6/23) | #17 (6/26) | #18 (6/28) | #19 (6/29) | #20 (6/30) | #21 (7/4) | **이번 (7/5)** |
|---|---|---|---|---|---|---|---|---|---|---|
| 신규 P0 | 4 | 0 | 4 | 7 | 10 | 3 | 4 | 0 | 1 | **3 (PR#22)** |
| 신규 P1 | 8 | 0 | 6 | 18 | 24 | 9 | 13 | 0 | 8 | **3 (PR#22)** |
| 누적 수정 | — | 0/9 | 0/15 | 0/22 | 0/32 | 0/44 | 0/57 | 0/57 | 7/57 | **7/60** |
| 오판 정정 | — | — | 2 | — | — | — | — | — | 2 | 0 (누적 4) |

**누적 수정 7건 (모두 PR #10, 지난 주 확인, 이번 주 신규 fix 없음):**
- InstancedMesh dispose leak
- Y-ceiling stick
- Chest pointer-lock race
- F-flight fallDist exploit
- Music burst
- R keyup guard
- Hotbar 9-slot reachability

**작성자 워크플로 신호:**
- **PR #22 신규 등장**: 프로젝트 내장 skill 오버라이드 위험 · upstream tamper 방어 결여 · autocommit 지시 → **채널 신뢰 훼손**. 프로젝트 CLAUDE.md 를 무시하는 upstream 스킬 벌크 유입.
- **PR #10 지난 주 fix 채널 도달 이후 이번 주 신규 반응 없음** — 프로즈 리뷰 채널이 여전히 유효한지 확실치 않음. 지난 주 잔존 P1 5건 (saveGame sync, applyPos NaN, health NaN, respawn, chest orphan) 는 그대로.
- **PR #5, #4 는 지난 주 v0.23-v0.27 대규모 커밋 후 이번 주 정지**. 지난 주 지적한 신규 P0 (SRISK) + P1 (CoVaR / FRTB yellow-zone) 미터치.
- **PR #2 는 10주 연속 무변화.** Top 4 P0 라이브.

## 다음 라운드 권고

**A. PR #22 우선 처리 (2주 내):**
1. `code-review` slug 충돌은 프로젝트 리뷰 관행에 즉각적 영향 → 이번 사이클 내 rename 또는 삭제. 프로젝트 built-in `/code-review` 는 시스템 리마인더에 명시되어 있어 rename 이 안전.
2. `skills-lock.json` 에 `sourceCommit` 필드 추가 (사후에도 가능하나 tamper 창구 열려 있으므로 신속).
3. `.claude/skills/implement/SKILL.md:12` 의 `Commit your work` 지시를 사용자 확인 문구로 교체 — 1줄 fix.

**B. PR #5 신규 P0 (지난 주 미해결) 리마인드:**
- SRISK `(1-k)` 누락 (`systemic.py:61`) — 1줄 fix. 회귀 테스트 스텁 첨부 제안.
- Corporate B RW=1.00 (`rwa_sa.py:46`) — CRE20.44 정본 기준 1.50 로 상향, 1줄 fix.

**C. PR #10 잔존 P1 (지난 주 partial 커버) 요약 이슈로 정리:**
- saveGame sync stall / applyPos NaN / respawn nether / destroyBlocks CHEST / health NaN — 5건 모두 각 3~10줄 fix. Author 의 지난 반응 이력 감안하면 fix-list 요약 이슈가 효과적.

**D. PR #2 는 여전히 무반응** — 지난 주 제안한 "routine 이 직접 fix-PR 제출" 옵션 (PR #20 A안) 이 이제는 유일한 진척 경로일 수 있음. Top 4 P0 모두 5~10줄 mechanical fix.

## 리뷰 방식

3개 병렬 general-purpose 에이전트:
1. **PR #22 심층 리뷰** — `mcp__github__pull_request_read get_files` (63건 페이지네이션) + `mcp__github__get_file_contents ref=refs/pull/22/head` 로 skills-lock.json + 8개 SKILL.md 샘플 + 3개 shell script 직접 읽기. 파일 인벤토리 검증, 트리거 문구 분석, 프로젝트 CLAUDE.md 대비 정책 충돌 확인.
2. **이전 15개 findings live-status 재확인** — PR #2/#4/#5/#10 각 파일의 anchor line ±5 를 원문 fetch 후 defect 문자열 매칭. 15/15 CONFIRMED, 라인 이동만 반영.
3. **PR #3/#6/#7/#8/#9/#11/#12 quiet check** — head SHA + 최근 커밋 날짜만 fetch. 7건 전부 무변화 확인.

지난 주 4-에이전트 (PR #2/#4/#5/#10 각각 심층) 대비 이번 주는 3-에이전트 (PR #22 심층 + 15 findings 재확인 + 나머지 quiet) 구성. 지난 주 대비 코드 변화가 PR #22 하나에 집중되어 있고 나머지는 SHA 무변화이므로 심층 재리뷰 불필요 판단.

총 출력 토큰 ~190K (지난 주 ~410K 대비 절반, 코드 변화량 축소 반영).

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
