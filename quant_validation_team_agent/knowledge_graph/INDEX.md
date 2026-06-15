# Quant Validation Knowledge Graph

This Obsidian entry point extends the quant-validation package with atomic
knowledge nodes. It is additive: existing operating documents, samples,
outputs, scripts, and tests are preserved.

## Core Maps

- [[SOURCE_REGISTRY]]
- [[Regulatory_Source_Control]]
- [[Basel_Framework]]
- [[Korean_Supervisory_Rules]]
- [[BCBS_239_Data_Aggregation]]
- [[Korea_Macro_Financial_Data_Map]]

## Credit Risk And Model Validation

- [[Credit_Rating_System]]
- [[Default_Definition]]
- [[PD]]
- [[LGD]]
- [[EAD]]
- [[CCF]]
- [[Downturn_Adjustment]]
- [[Calibration]]
- [[Discriminatory_Power]]
- [[Backtesting]]
- [[Override_Governance]]

## Market, Rate, Liquidity, And Aggregation

- [[Market_Risk_FRTB]]
- [[VaR_Backtesting]]
- [[P_L_Attribution]]
- [[IRRBB]]
- [[EVE_NII]]
- [[Liquidity_Risk_LCR_NSFR]]
- [[HQLA]]
- [[Operational_Risk]]
- [[Stress_Testing]]
- [[ICAAP]]

## Domestic Data Nodes

- [[Domestic_Data_BOK_ECOS]]
- [[Domestic_Data_KRX]]
- [[Domestic_Data_KOFIA_Bond]]
- [[Domestic_Data_DART_KIND]]

## Validation Guardrails

Every node should keep three anchors:

- Concept links: at least three wikilinks to neighboring nodes.
- Source links: `source_refs` entries that exist in [[SOURCE_REGISTRY]].
- Control links: a path back to [[Regulatory_Source_Control]] and
  [[Risk_Data_Lineage]] when source or data evidence can affect judgement.

