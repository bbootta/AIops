---
node_id: domestic_data_kofia_bond
source_refs:
  - KR-KOFIA-BOND
---
# Domestic Data KOFIA Bond

KOFIA bond data supports Korean bond yields, reference curves, term-structure
inputs, and fixed-income market evidence.

Related nodes: [[Korea_Macro_Financial_Data_Map]], [[IRRBB]], [[EVE_NII]],
[[Liquidity_Risk_LCR_NSFR]], [[HQLA]], [[Risk_Data_Lineage]].

Validation impact:

- Curve source, tenor mapping, business-day convention, and extraction timestamp
  are mandatory lineage fields.
- Bond curve data can support IRRBB and liquidity validation but does not define
  internal behavioral assumptions.
- Curve-vintage mismatch between ALM and reporting outputs requires Action
  Notice.

