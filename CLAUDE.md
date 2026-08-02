# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

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

## 5. 3D Games: Pick the Target by Graphics Ambition

**Decide browser vs. installed app up front. Say which and why before writing code.**

The graphics ceiling drives the delivery target, not the other way round:

- **Browser (single page, WebGL)** — prototypes, stylised or low-poly looks, anything
  meant to be opened from a link. Cheapest to iterate and share. Accept the ceiling:
  no native GPU features, load time paid on every visit, asset budget bounded by what
  a page can reasonably inline.
- **Installed app (Electron/Tauri, or a real engine)** — anything reaching for
  photoreal: heavy PBR material sets, HDRI lighting, cascaded shadows, layered
  post-processing, large scan-based assets. Ship an installer per OS.

Guidance:
- State the choice and its ceiling before building. If the ask is "make it photoreal"
  on a browser target, say plainly that the target is the limiting factor.
- Prefer starting in the browser while the look is still being found — the iteration
  loop is much faster — then wrap the same renderer in a desktop shell once the
  graphics ambition outgrows it. Don't rewrite to switch.
- Cross-OS installers must be built on their own OS (or CI). Building a Windows or
  macOS installer from Linux does not work; hand over the build config and say so
  rather than claiming a build that was never produced.
- Verify the packaged app actually launches and renders. A successful package step is
  not evidence the game runs.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
