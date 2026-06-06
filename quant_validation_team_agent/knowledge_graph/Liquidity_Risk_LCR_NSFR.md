---
node_id: liquidity_risk_lcr_nsfr
source_refs:
  - BIS-LCR-SUMMARY
  - BIS-NSFR-SUMMARY
  - BIS-BF
---
# Liquidity Risk LCR NSFR

LCR and NSFR validation checks short-term liquidity stress resilience, longer
term funding stability, HQLA eligibility, runoff assumptions, maturity mapping,
and funding concentration evidence.

Related nodes: [[HQLA]], [[Risk_Data_Lineage]], [[Stress_Testing]],
[[BCBS_239_Data_Aggregation]], [[Domestic_Data_KOFIA_Bond]],
[[Regulatory_Source_Control]].

Validation impact:

- HQLA classification evidence and runoff assumption approval are mandatory.
- Cash-flow projections must reconcile to source systems and engine output.
- The agent records official LCR/NSFR outputs and does not calculate ratios.

