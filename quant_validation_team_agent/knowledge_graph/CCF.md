---
node_id: ccf
source_refs:
  - BIS-IRB-VALIDATION
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# CCF

Credit conversion factor connects undrawn commitments to EAD. It should be
validated through approved observation windows, product segmentation, limit
change handling, and realized drawdown evidence.

Related nodes: [[EAD]], [[Default_Definition]], [[Backtesting]],
[[Calibration]], [[Risk_Data_Lineage]], [[Credit_Rating_System]].

Validation impact:

- CCF results without facility-limit lineage are insufficient.
- Product segmentation must be stable or explicitly versioned.
- The agent records engine result IDs and does not estimate CCF directly.

