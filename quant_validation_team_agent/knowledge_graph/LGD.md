---
node_id: lgd
source_refs:
  - BIS-IRB-VALIDATION
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# LGD

Loss given default estimates loss severity after default. Validation checks
workout cash-flow evidence, collateral treatment, cure handling, discounting,
cost allocation, and downturn adjustment.

Related nodes: [[Default_Definition]], [[PD]], [[EAD]],
[[Downturn_Adjustment]], [[Calibration]], [[Backtesting]],
[[Risk_Data_Lineage]].

Validation impact:

- Open recovery cases need approved treatment rules.
- Collateral valuation and haircut lineage must be tied to the engine input.
- Missing discount-rate policy or workout data lineage maps to Gray.

