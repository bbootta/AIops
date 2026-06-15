---
node_id: override_governance
source_refs:
  - BIS-IRB-VALIDATION
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# Override Governance

Override governance controls manual changes to ratings, grades, parameter
inputs, or risk classifications.

Related nodes: [[Credit_Rating_System]], [[Discriminatory_Power]],
[[Calibration]], [[Backtesting]], [[Regulatory_Source_Control]],
[[Risk_Data_Lineage]].

Validation impact:

- Overrides require reason codes, approver authority, timestamp, and policy
  version.
- High override concentration can indicate model weakness or process drift.
- Missing override evidence maps to Gray even if final grades appear reasonable.

