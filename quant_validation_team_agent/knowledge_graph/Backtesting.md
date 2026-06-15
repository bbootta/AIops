---
node_id: backtesting
source_refs:
  - BIS-IRB-VALIDATION
  - BIS-MAR-FRTB-2019
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# Backtesting

Backtesting compares prior estimates or risk measures with realized outcomes.
Its meaning depends on the domain: PD default outcomes, EAD realized exposure,
LGD workout loss, or market-risk exceptions.

Related nodes: [[PD]], [[LGD]], [[EAD]], [[VaR_Backtesting]],
[[Calibration]], [[Risk_Data_Lineage]], [[Regulatory_Source_Control]].

Validation impact:

- Observation windows and realized-outcome definitions must be explicit.
- Exception counts or traffic-light outputs require official engine evidence.
- Backtesting failures may be Yellow or Red, but missing evidence is Gray.

