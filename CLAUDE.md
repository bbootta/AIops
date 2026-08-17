# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes, plus this repository's working conventions.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 0. This Repository

**Read `HANDOVER.md` first.** It carries the current state: what lives on which branch, what's in progress, what the next steps are, and what not to touch.

Structure in one line: `main` is an intentionally empty hub (`CLAUDE.md`, `HANDOVER.md`, `.claude/settings.json`, `.gitkeep`); every project lives on its own unmerged feature branch.

Conventions that follow from that:

- **One branch = one project.** Check out the branch you're working on. Don't start work on `main`, and don't pull files from a branch into `main` — `main` being empty is deliberate (commit `ebb9e8a`).
- **Don't merge PRs on your own.** 43 PRs are open and merge strategy is an open decision (see `HANDOVER.md` §6.2).
- **`claude/stoic-ride-*` PRs are review reports, not code.** Never merge them, never delete their branches — they are the delta baseline for the daily review series.
- **The latest `CODE_REVIEW_*.md` is the single source of truth for open defects.** Read it before claiming something is or isn't a known issue.
- **Never weaken a safety gate to make something pass** — `risk_lib` CLI exit codes, `independent.py` fail-closed delegation, `stock_trading`'s dual execution gate. Fix the cause instead.
- Each project branch carries its own `CLAUDE.md` and `README.md`. Those take precedence within that branch's directory.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Punctuation Rule (Global)

**Never use long dashes.** Em dash (—) and en dash (–) are banned in all output: documents, artifacts, HTML, commit messages, chat replies, and any other deliverable.

Replacements:
- Appositive or explanation: use a comma or colon (:)
- Ranges (dates, numbers): use a tilde (~)
- Word joining: use a hyphen (-)

## 6. 검증의 두 층 (이 저장소 고유)

**자체검증과 상시 독립검증은 다른 것이다. 하나로 대체하지 않는다.**

| 층 | 담당 | 하는 일 |
|---|---|---|
| 자체검증 (2선) | 이 저장소의 `risk-validator` | 정합성·규제기준·통계 체크. **같은 코드·같은 가정**을 쓴다 |
| 상시 독립검증 (3선) | 적합성검증 팀에이전트<br>`claude/validation-team-agent-Pw9F5` | 개발조직과 분리된 기준셋으로 **독립 재계산**. 가정을 도전한다 |

리스크 산출 작업을 하면 **매번 예외 없이**:

1. 자체검증을 돌린다 (`run_consistency_checks` → `val_check`).
2. 독립검증 요청을 만들어 적합성검증 팀에 위임한다
   (`risk_lib.validation.independent.build_request` → `docs/independent_validation/`).
   절차는 `.claude/skills/independent-validation/SKILL.md`.
3. 결재 상신 직전에 게이트를 확인한다 (`check_gate(...).require()`).
   게이트는 **fail-closed** 이며, 응답이 없으면 `응답대기`이며 결재 불가다.
   판정이 `경부적합`(중부적합 0건)이면 게이트는 `조건부`이며, 결재 책임자가
   잔여위험·후속조건·이행기한·배포 범위를 기록해야만 통과한다
   (`require(ConditionalApproval(...))`). 기록 없이는 통과하지 않는다.

보고할 때는 두 줄을 함께 적는다. 독립검증이 `응답대기`인데 "검증 완료"라고
쓰지 않는다.

```
자체검증 (2선)      PASS n · WARN n · FAIL 0
상시 독립검증 (3선)  응답대기 (IVR-…)  또는  적합 (IVR-…)
```

새 headline 수치를 만들면 `independent.RECALC_SCOPE`에 넣는다. 거기 없으면
3선이 그 수치를 다시 계산하지 않는다.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
