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

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
