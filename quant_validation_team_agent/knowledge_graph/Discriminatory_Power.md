---
node_id: discriminatory_power
source_refs:
  - BIS-IRB-VALIDATION
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# Discriminatory Power

Discriminatory power assesses whether a model ranks risk consistently across
borrowers, facilities, or segments.

Related nodes: [[Credit_Rating_System]], [[PD]], [[Calibration]],
[[Backtesting]], [[Override_Governance]], [[Risk_Data_Lineage]].

Validation impact:

- AUROC, Gini, KS, and similar statistics must come from approved outputs.
- Segment-level degradation should be tracked even when aggregate performance is
  acceptable.
- Missing sample-definition evidence maps to Gray.

