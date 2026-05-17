# AIops Risk Research Agent Harness

This repository defines a specialist research-team harness for bank risk
management topics, including Basel standards, supervisory materials, academic
papers, bank case studies, and current news.

## Team

- `risk-research-lead`: scopes the question, assigns work, synthesizes findings.
- `basel-standards-analyst`: reads Basel Committee and BIS source material.
- `jurisdiction-regulation-analyst`: compares local implementation across major regulators.
- `academic-literature-analyst`: reviews papers and research evidence.
- `bank-case-study-analyst`: analyzes bank disclosures, incidents, and remediation cases.
- `news-risk-intelligence-analyst`: monitors news, market events, enforcement, and emerging risks.
- `quant-risk-methodology-analyst`: evaluates models, metrics, stress testing, and methodology.
- `evidence-quality-reviewer`: checks citations, source quality, conflicts, and unsupported claims.

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

- `AGENTS.md`: Codex entrypoint and operating instructions.
- `agents/`: reusable specialist role definitions.
- `harness/team.yaml`: team topology, expected outputs, and handoff rules.
- `harness/risk-research-runbook.md`: operating workflow and quality gates.
- `harness/source-map.md`: preferred sources and evidence tiers.
- `templates/research-brief.md`: final report format.
- `templates/evidence-matrix.md`: claim-to-source traceability table.
- `templates/source-log.csv`: structured source log.
- `templates/weekly-risk-watch.md`: recurring intelligence brief format.

## Research Standard

Material claims must be traceable to a dated source. Basel and regulatory
interpretations must start from official source text before relying on
commentary, consulting reports, or news. News-driven findings must include
event dates and publication dates.

## Output Preference

Reports should be produced as HTML files in `reports/` by default. Include
embedded source logs and evidence matrices unless the user asks for a different
format.
