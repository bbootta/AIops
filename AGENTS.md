# Codex Instructions

This directory contains a Codex-oriented research-team harness for bank risk
management topics.

## Operating Model

- Start with `harness/team.yaml` to identify the right specialist roles.
- Use `agents/` as Codex-neutral role prompts and checklists.
- Use `harness/risk-research-runbook.md` for workflow and quality gates.
- Use `harness/source-map.md` to prioritize primary sources.
- Use `templates/` for report structure and evidence traceability.
- Produce final research reports as HTML files under `reports/` unless the user
  asks for a different format.

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
- For current information, verify the latest source before writing conclusions.
- Every material claim needs a dated source.
- Separate event date from publication date for news.
- Include an evidence matrix and source log in each HTML report.
