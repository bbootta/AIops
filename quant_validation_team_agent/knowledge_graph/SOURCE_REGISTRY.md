# SOURCE_REGISTRY

Official and operational sources used by the knowledge graph. Source IDs are
referenced from node frontmatter as `source_refs`.

| source_id | authority | scope | url |
|---|---|---|---|
| BIS-BF | BIS/BCBS | Consolidated Basel Framework entry point | https://www.bis.org/baselframework/background.htm |
| BIS-CRP-2025 | BIS/BCBS | Principles for the management of credit risk | https://www.bis.org/bcbs/publ/d595.htm |
| BIS-BCBS239-2026 | BIS/BCBS | BCBS 239 implementation update and data aggregation focus | https://www.bis.org/publ/bcbs_nl36.htm |
| BIS-IRB-VALIDATION | BIS/BCBS | IRB rating systems and parameter validation reference | https://www.bis.org/publ/bcbs_wp14.htm |
| BIS-BCP-2024 | BIS/BCBS | Core Principles for effective banking supervision | https://www.bis.org/bcbs/publ/d573.htm |
| BIS-MAR-FRTB-2019 | BIS/BCBS | Minimum capital requirements for market risk, integrated into Basel Framework | https://www.bis.org/bcbs/publ/d457.htm |
| BIS-IRRBB-2016 | BIS/BCBS | Interest rate risk in the banking book standard, integrated into Basel Framework | https://www.bis.org/bcbs/publ/d368.htm |
| BIS-SRP31-IRRBB | BIS/BCBS | Basel Framework SRP31 IRRBB chapter | https://www.bis.org/basel_framework/chapter/SRP/31.htm |
| BIS-LCR-SUMMARY | BIS/FSI | Liquidity Coverage Ratio executive summary | https://www.bis.org/fsi/fsisummaries/lcr.htm |
| BIS-NSFR-SUMMARY | BIS/FSI | Net Stable Funding Ratio executive summary | https://www.bis.org/fsi/fsisummaries/nsfr.htm |
| KR-BANK-SUP-DETAIL-ANNEX3 | Korea Law Service | Bank supervision detailed rule annex for credit risk and IRB requirements | https://law.go.kr/LSW/flDownload.do?flSeq=131147849 |
| KR-STRESS-ANNEX19 | Korea Law Service | Stress testing standard annex | https://www.law.go.kr/LSW/flDownload.do?bylClsCd=200201&flNm=%5B%EB%B3%84%ED%91%9C+19%5D+%EC%9C%84%EA%B8%B0%EC%83%81%ED%99%A9%EB%B6%84%EC%84%9D+%EC%8B%A4%EC%8B%9C+%EA%B8%B0%EC%A4%80&flSeq=161246687 |
| KR-ICAAP-ANNEX3-9 | Korea Law Service | ICAAP build, operation, management, and review standard annex | https://www.law.go.kr/LSW/flDownload.do?bylClsCd=200201&flNm=%5B%EB%B3%84%ED%91%9C+3%EC%9D%989%5D+%EB%82%B4%EB%B6%80%EC%9E%90%EB%B3%B8%EC%A0%81%EC%A0%95%EC%84%B1+%ED%8F%89%EA%B0%80%C2%B7%EA%B4%80%EB%A6%AC%EC%B2%B4%EC%A0%9C+%EA%B5%AC%EC%B6%95%C2%B7%EC%9A%B4%EC%9A%A9+%EB%B0%8F+%EC%A0%90%EA%B2%80+%EA%B8%B0%EC%A4%80&flSeq=137870347 |
| KR-BOK-ECOS | Bank of Korea | Macroeconomic and financial time-series data source | https://ecos.bok.or.kr |
| KR-KRX-DATA | Korea Exchange | Listed market, index, trading, disclosure-adjacent market data | https://data.krx.co.kr |
| KR-KOFIA-BOND | Korea Financial Investment Association | Bond information and yield curve data | https://www.kofiabond.or.kr |
| KR-DART | Financial Supervisory Service | Corporate filings and public disclosure documents | https://dart.fss.or.kr |
| KR-KIND | Korea Exchange | Listed-company disclosure and market notice data | https://kind.krx.co.kr |

## Source Integrity Rules

- A node may cite a source only by `source_id`; free-text URLs belong here.
- If a source is current but domestic applicability is unclear, the judgement
  path must link to [[Regulatory_Source_Control]] and default to Gray until a
  policy owner confirms applicability.
- Data sources are evidence sources, not calculation engines. Results still
  require official engine output identifiers and [[Risk_Data_Lineage]].

