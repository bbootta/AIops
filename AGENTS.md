# Agent Instructions

This repository is a tool-agnostic research-team harness for bank risk
management topics. One canonical agent set serves every runner:

- **Claude Code** auto-discovers the subagents in `.claude/agents/`.
- **Codex and other tools that read `AGENTS.md`** load the same files as role
  prompts. The YAML frontmatter is metadata (`name`, `description`, suggested
  `tools`); the markdown body is the role prompt.

## Operating Model

- Start with `harness/team.yaml` for team topology, depth modes
  (rapid-scan / standard / deep), quality gates, and delivery rules.
- Use `.claude/agents/` as the canonical role prompts and checklists; the
  entry point is `risk-research-lead`.
- Follow `harness/risk-research-runbook.md` for the workflow, blocking gates
  G1-G5, the conflict-resolution protocol, and freshness rules.
- Use `harness/source-map.md` to prioritize primary sources.
- Use `templates/` for report structure and evidence traceability.
- Produce final reports as HTML files at
  `reports/<topic-slug>-<YYYY-MM-DD>.html` unless the user asks for a
  different format. Report prose defaults to Korean.

## Default Team

- `risk-research-lead`
- `basel-standards-analyst`
- `jurisdiction-regulation-analyst`
- `academic-literature-analyst`
- `bank-case-study-analyst`
- `news-risk-intelligence-analyst`
- `quant-risk-methodology-analyst`
- `evidence-quality-reviewer`

## Quality Rules

- Use official Basel, BIS, central-bank, supervisory, and legal sources first.
- Every material claim needs a dated source.
- For current information, verify the latest source before writing conclusions
  and stamp time-sensitive claims with an as-of date.
- Separate event date from publication date for news.
- Resolve conflicting evidence by tier, then recency and supersession; if the
  conflict survives, disclose both sides as contested — never average or
  silently drop one.
- Include an evidence matrix and source log in each report.
- Final briefs require an `evidence-quality-reviewer` verdict (gate G5),
  except rapid-scan self-checks.
