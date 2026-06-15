---
node_id: pd
source_refs:
  - BIS-IRB-VALIDATION
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# PD

Probability of default is a parameter describing default likelihood over the
approved horizon and population. Validation focuses on policy alignment,
discrimination, calibration, stability, and backtesting evidence from the
calculation engine.

Related nodes: [[Default_Definition]], [[Credit_Rating_System]],
[[Calibration]], [[Discriminatory_Power]], [[Backtesting]],
[[Downturn_Adjustment]], [[Risk_Data_Lineage]].

Validation impact:

- PD must use the approved default definition and observation window.
- Long-run average, current portfolio mix, and downturn conservatism should be
  evidenced by policy or engine outputs.
- The agent may interpret official outputs but must not compute PD.

