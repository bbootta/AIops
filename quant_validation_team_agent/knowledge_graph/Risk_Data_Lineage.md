---
node_id: risk_data_lineage
source_refs:
  - BIS-BCBS239-2026
  - BIS-BCP-2024
---
# Risk Data Lineage

Risk data lineage records where input data originated, how it was transformed,
which version was used by the calculation engine, and how that result appears in
reports.

Related nodes: [[BCBS_239_Data_Aggregation]], [[Regulatory_Source_Control]],
[[PD]], [[LGD]], [[EAD]], [[Liquidity_Risk_LCR_NSFR]],
[[Korea_Macro_Financial_Data_Map]].

Validation impact:

- A clean metric with unclear lineage remains Gray.
- The agent can summarize lineage evidence but must not reconstruct missing
  transformations from report values.
- The lineage path should connect data source, policy version, engine run log,
  result identifier, reviewer decision, and final report artifact.

