# AIops Risk Research Agent Harness

A tool-agnostic ("global") research-team harness for bank risk management
topics: Basel standards, supervisory materials, academic papers, bank case
studies, and current news.

One canonical agent set serves every runner — there are no per-tool copies to
keep in sync:

- **Claude Code** auto-discovers the subagents in `.claude/agents/`.
- **Codex and other `AGENTS.md` readers** get the same harness via the root
  `AGENTS.md`, which points at the same role files.

## Team

- `risk-research-lead`: scopes the question, assigns work, synthesizes findings; owns gates G1 and G4.
- `basel-standards-analyst`: reads Basel Committee and BIS source material.
- `jurisdiction-regulation-analyst`: compares local implementation across major regulators.
- `academic-literature-analyst`: reviews papers and research evidence.
- `bank-case-study-analyst`: analyzes bank disclosures, incidents, and remediation cases.
- `news-risk-intelligence-analyst`: monitors news, market events, enforcement, and emerging risks.
- `quant-risk-methodology-analyst`: evaluates models, metrics, stress testing, and methodology.
- `evidence-quality-reviewer`: checks citations, source quality, conflicts, and unsupported claims; owns the gate G5 verdict.

## Workflow and Quality Gates

Research runs through five blocking gates defined in
`harness/risk-research-runbook.md`:

| Gate | Stage | Passes when |
| --- | --- | --- |
| G1 | Intake | Scope, depth mode, and output format confirmed or stated as explicit assumptions |
| G2 | Source collection | Regulatory claims have T1 sources; no question rests solely on T4-T5 |
| G3 | Specialist analysis | Each hand-back meets the handoff contract with dated, sourced claims |
| G4 | Synthesis | All sections present; conflicts resolved per protocol; evidence matrix complete |
| G5 | Evidence review | Reviewer verdict `pass`, or `pass-with-edits` applied |

Depth modes (`rapid-scan` / `standard` / `deep`) size the team, evidence
requirements, and review strictness — see `harness/team.yaml`.

## Quick Start

Use the lead agent first:

```text
Use risk-research-lead to produce a professional research brief on:
"How Basel III finalization affects credit risk capital, operational risk,
and liquidity risk management for a mid-sized commercial bank."
```

For narrow work, call a specialist directly:

```text
Use basel-standards-analyst to summarize the current Basel Framework treatment
of operational risk capital and identify implementation caveats.
```

## Files

- `AGENTS.md`: global entrypoint for Codex and other `AGENTS.md`-reading tools.
- `.claude/agents/`: canonical specialist role definitions (Claude Code subagents).
- `harness/team.yaml`: team topology, depth modes, gates, delivery rules, and handoff rules.
- `harness/risk-research-runbook.md`: workflow, quality gates G1-G5, conflict-resolution protocol, freshness rules.
- `harness/source-map.md`: preferred sources and evidence tiers.
- `templates/research-brief.md`: final report format.
- `templates/evidence-matrix.md`: claim-to-source traceability table.
- `templates/source-log.csv`: structured source log.
- `templates/weekly-risk-watch.md`: recurring intelligence brief format.
- `reports/`: default output location, `reports/<topic-slug>-<YYYY-MM-DD>.html`.

## Research Standard

Material claims must be traceable to a dated source. Basel and regulatory
interpretations must start from official source text before relying on
commentary, consulting reports, or news. News-driven findings must include
event dates and publication dates. Time-sensitive claims carry an as-of date
verified in the current research run. Conflicting evidence is resolved by tier
and recency, or disclosed as contested — never silently dropped.

## Output Preference

Reports are HTML files in `reports/` by default, with embedded source logs and
evidence matrices. Report prose defaults to Korean; citations and tables may
stay in the source language.
