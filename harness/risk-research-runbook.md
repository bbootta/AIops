# Risk Research Team Runbook

Workflow and quality gates for the risk-management research team. Gates G1-G5
are blocking: work does not advance past a gate until its pass criteria are
met.

## 1. Intake

Clarify the research objective before collecting sources.

Required fields:

- Topic and decision context.
- Target institution type, jurisdiction, and business model.
- Risk types in scope: credit, market, operational, liquidity, IRRBB, model, cyber, climate, conduct, compliance.
- Time horizon: current rules, historical analysis, forward-looking implementation, or event watch.
- Depth mode: rapid-scan, standard, or deep (see `team.yaml`).
- Desired output: executive memo, technical note, board pack, evidence matrix, or weekly watch.

If the user does not specify a jurisdiction, default to global Basel text plus
US, EU, UK, and Korea implementation notes where relevant.

**Gate G1 — intake passes when** every required field is either confirmed by
the user or recorded as an explicit assumption in the research plan. Do not
collect sources before G1 passes.

## 2. Scoping

The `risk-research-lead` creates a plan with:

- Core research questions.
- Specialist assignments, marking which tracks run in parallel.
- Source requirements by evidence tier.
- Expected tables and exhibits.
- Known ambiguity or likely conflicts.

Specialist tracks with no input dependency on each other run in parallel.

## 3. Source Collection

Preferred sequence:

1. Official Basel, BIS, central-bank, and supervisory sources.
2. Legal or regulatory text for the relevant jurisdiction.
3. Bank filings, Pillar 3 reports, audited statements, and stress-test disclosures.
4. Peer-reviewed papers and working papers.
5. Reputable news and market intelligence.
6. Consulting or vendor commentary only as secondary context.

Every source entry should capture title, author or institution, publication
date, URL or document locator, evidence tier, and the claims it supports.

**Gate G2 — source floor passes when** every regulatory or Basel claim in
scope has at least one T1 source identified, no research question rests solely
on T4-T5 sources, and each source entry has a publication date and access date.

## 4. Specialist Analysis

Each specialist returns (the handoff contract, repeated in every agent file):

- Key findings.
- Source-backed claims.
- Practical implications for risk management.
- Limitations and uncertainty.
- Items requiring lead synthesis or reviewer attention.

No specialist should treat consulting commentary or news as a substitute for
official source text when interpreting Basel or local rules.

**Gate G3 — a specialist hand-back passes when** it contains all five contract
items and every material claim names its source with a date and locator. The
lead returns incomplete hand-backs to the specialist instead of patching them
during synthesis.

## 5. Synthesis

The lead turns specialist notes into:

- Executive summary.
- Regulatory baseline.
- Risk-management implications.
- Bank-case evidence.
- Research evidence.
- Current-event signals.
- Actionable recommendations.
- Open questions and monitoring triggers.

**Gate G4 — synthesis passes when** every section above is present or
explicitly marked out of scope, all conflicts are resolved per the protocol
below, and the evidence matrix covers every material claim.

### Conflict-Resolution Protocol

When sources or specialists disagree:

1. Rank by evidence tier: a T1 source beats lower tiers for regulatory and
   factual claims.
2. Within the same tier, the more recent publication wins; check whether the
   newer document explicitly supersedes the older one (Basel versions, amended
   rules, corrected filings).
3. If the conflict survives steps 1-2 (for example, two current T1 sources
   from different authorities), present both positions with dates and scope
   and label the claim contested — never average or silently drop a side.
4. Record every conflict and its resolution in the evidence matrix notes.

### Freshness Rules

- Stamp every time-sensitive claim with an as-of date.
- Before final delivery, re-verify claims about consultations, phase-ins,
  pending rules, or ongoing events against the live source.
- If the topic is dynamic, state the recheck interval in the brief's
  monitoring section.

## 6. Evidence Review

The `evidence-quality-reviewer` checks:

- Each material claim has a source.
- Source tier is appropriate for the claim.
- Dates are present and precise.
- Basel and regulatory claims use official sources first.
- News claims distinguish event date from publication date.
- Conflicting evidence is disclosed and resolved per the protocol above.
- Time-sensitive claims carry as-of dates verified in this run.
- The brief avoids unsupported predictions.

The reviewer spot-checks at least three material claims against their cited
sources and opens the review with a verdict line: `VERDICT: pass`,
`VERDICT: pass-with-edits`, or `VERDICT: revise`.

**Gate G5 — review passes when** the verdict is `pass`, or `pass-with-edits`
with the listed edits applied. A `revise` verdict returns the brief to the
lead; resubmission repeats G5. In rapid-scan mode the lead self-checks against
the reviewer checklist and notes this in the brief.

## 7. Final Delivery

Final outputs include:

- Decision-useful conclusion.
- Evidence matrix.
- Source log.
- Explicit caveats.
- Suggested next monitoring cycle if the topic is dynamic.

Default report format: an HTML file at
`reports/<topic-slug>-<YYYY-MM-DD>.html` unless the user asks for another
format. The report must be readable directly in a browser and include source
links, evidence tiers, and claim traceability. Report prose defaults to Korean
(`default_language` in `team.yaml`); citations and tables may stay in the
source language.

## Prompt Pattern

```text
Use risk-research-lead for a professional risk-management research brief.

Topic:
[topic]

Decision context:
[why this matters]

Jurisdictions:
[global Basel + target jurisdictions]

Risk types:
[credit / market / operational / liquidity / model / other]

Output:
[executive memo / board note / technical appendix / weekly watch]

Depth:
[rapid-scan / standard / deep]
```

## Quality Bar

Use exact dates when discussing recent developments. If a source may have
changed, verify the latest official text before presenting a conclusion.
