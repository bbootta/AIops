---
node_id: var_backtesting
source_refs:
  - BIS-MAR-FRTB-2019
---
# VaR Backtesting

VaR backtesting compares risk measure forecasts with realized or hypothetical
P&L outcomes according to the approved market-risk policy.

Related nodes: [[Market_Risk_FRTB]], [[P_L_Attribution]], [[Backtesting]],
[[Risk_Data_Lineage]], [[Domestic_Data_KRX]], [[Regulatory_Source_Control]].

Validation impact:

- Exceptions need consistent P&L definition, date alignment, and model version.
- The agent records official exception evidence and escalation status.
- It must not recompute VaR or infer missing P&L adjustments.

