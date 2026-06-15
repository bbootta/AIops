---
node_id: domestic_data_krx
source_refs:
  - KR-KRX-DATA
  - KR-KIND
---
# Domestic Data KRX

KRX data supports listed market prices, index data, trading data, and
listed-company market notices. KIND is the listed-company disclosure channel.

Related nodes: [[Korea_Macro_Financial_Data_Map]], [[Market_Risk_FRTB]],
[[VaR_Backtesting]], [[P_L_Attribution]], [[HQLA]],
[[Risk_Data_Lineage]].

Validation impact:

- Price source, trading date, adjustment treatment, and vendor reconciliation
  should be explicit.
- Disclosure events may explain market or reputational risk but need timestamped
  evidence.
- Data vendor transformations should be separately versioned.

