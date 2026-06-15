---
node_id: regulatory_source_control
source_refs:
  - BIS-BF
  - BIS-BCP-2024
  - KR-BANK-SUP-DETAIL-ANNEX3
---
# Regulatory Source Control

Regulatory source control is the discipline that separates an official source,
its effective date, domestic applicability, internal policy adoption, and final
approval authority.

Related nodes: [[SOURCE_REGISTRY]], [[Basel_Framework]],
[[Korean_Supervisory_Rules]], [[Risk_Data_Lineage]],
[[BCBS_239_Data_Aggregation]].

Validation impact:

- Missing effective date or applicability evidence maps to Gray.
- A Basel source integrated into the Basel Framework still needs domestic policy
  mapping before the agent treats it as an internal rule.
- Conflicting source versions are handled as an Action Notice, not by automatic
  interpretation.

