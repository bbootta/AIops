---
node_id: default_definition
source_refs:
  - BIS-IRB-VALIDATION
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# Default Definition

Default definition is the rule that determines when an obligor or exposure is
treated as defaulted for model development, calibration, backtesting, and
regulatory reporting.

Related nodes: [[PD]], [[LGD]], [[EAD]], [[Credit_Rating_System]],
[[Backtesting]], [[Calibration]], [[Regulatory_Source_Control]].

Validation impact:

- A changed default definition changes sample construction and historical
  comparability.
- Inconsistent default flags across PD, LGD, and EAD are a lineage defect.
- Missing default-definition policy evidence defaults to Gray.

