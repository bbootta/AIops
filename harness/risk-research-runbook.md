# Risk Research Team Runbook

## 1. Intake

Clarify the research objective before collecting sources.

Required fields:

- Topic and decision context.
- Target institution type, jurisdiction, and business model.
- Risk types in scope: credit, market, operational, liquidity, IRRBB, model, cyber, climate, conduct, compliance.
- Time horizon: current rules, historical analysis, forward-looking implementation, or event watch.
- Desired output: executive memo, technical note, board pack, evidence matrix, or weekly watch.

If the user does not specify a jurisdiction, default to global Basel text plus US, EU, UK, and Korea implementation notes where relevant.

## 2. Scoping

The `risk-research-lead` creates a plan with:

- Core research questions.
- Specialist assignments.
- Source requirements by evidence tier.
- Expected tables and exhibits.
- Known ambiguity or likely conflicts.

## 3. Source Collection

Preferred sequence:

1. Official Basel, BIS, central-bank, and supervisory sources.
2. Legal or regulatory text for the relevant jurisdiction.
3. Bank filings, Pillar 3 reports, audited statements, and stress-test disclosures.
4. Peer-reviewed papers and working papers.
5. Reputable news and market intelligence.
6. Consulting or vendor commentary only as secondary context.

Every source entry should capture title, author or institution, publication date,
URL or document locator, evidence tier, and the claims it supports.

## 4. Specialist Analysis

Each specialist returns:

- Key findings.
- Source-backed claims.
- Practical implications for risk management.
- Limitations and uncertainty.
- Items requiring lead synthesis or reviewer attention.

No specialist should treat consulting commentary or news as a substitute for
official source text when interpreting Basel or local rules.

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

## 6. Evidence Review

The `evidence-quality-reviewer` checks:

- Each material claim has a source.
- Source tier is appropriate for the claim.
- Dates are present and precise.
- Basel and regulatory claims use official sources first.
- News claims distinguish event date from publication date.
- Conflicting evidence is disclosed.
- The brief avoids unsupported predictions.

## 7. Final Delivery

Final outputs should include:

- Decision-useful conclusion.
- Evidence matrix.
- Source log.
- Explicit caveats.
- Suggested next monitoring cycle if the topic is dynamic.

Default report format: create an HTML file in `reports/` unless the user asks
for another format. The HTML report should be readable directly in a browser and
should include source links, evidence tiers, and claim traceability.

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
[rapid scan / standard / deep research]
```

## Quality Bar

Use exact dates when discussing recent developments. If a source may have
changed, verify the latest official text before presenting a conclusion.
