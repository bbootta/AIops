---
node_id: korea_macro_financial_data_map
source_refs:
  - KR-BOK-ECOS
  - KR-KRX-DATA
  - KR-KOFIA-BOND
  - KR-DART
  - KR-KIND
---
# Korea Macro Financial Data Map

The Korea macro-financial data map connects domestic source systems to risk
domains and validation evidence.

Related nodes: [[Domestic_Data_BOK_ECOS]], [[Domestic_Data_KRX]],
[[Domestic_Data_KOFIA_Bond]], [[Domestic_Data_DART_KIND]],
[[Risk_Data_Lineage]], [[Stress_Testing]], [[Downturn_Adjustment]].

Validation impact:

- Macroeconomic series, market data, bond curves, and disclosure data need
  source-specific identifiers and extraction timestamps.
- The map supports evidence routing for credit, market, IRRBB, liquidity,
  operational, strategic, and reputational risk.
- Any transformation from source data to risk engine input must be versioned and
  auditable.

