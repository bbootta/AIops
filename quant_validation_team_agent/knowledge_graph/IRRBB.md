---
node_id: irrbb
source_refs:
  - BIS-IRRBB-2016
  - BIS-SRP31-IRRBB
  - BIS-BF
---
# IRRBB

Interest rate risk in the banking book arises from adverse rate movements that
affect banking-book capital and earnings through repricing, basis, yield-curve,
optionality, and behavioral-assumption risk.

Related nodes: [[EVE_NII]], [[Stress_Testing]], [[Risk_Data_Lineage]],
[[Korea_Macro_Financial_Data_Map]], [[Domestic_Data_KOFIA_Bond]],
[[Basel_Framework]].

Validation impact:

- EVE and NII outputs require curve source, cash-flow mapping, behavioral
  assumption approval, and scenario version.
- Optionality assumptions need explicit policy and ALCO or equivalent approval.
- The agent must not create interest-rate shocks or present values.

