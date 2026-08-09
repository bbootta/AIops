# Basel Framework 공식 원문 소스북

> 기준일: **2026-08-09**  
> 범위: BIS/BCBS가 정의한 통합 Basel Framework 14개 Standard의 현행·장래·과거 Chapter 버전 전수 및 주요 역사적 원문  
> 언어: 공식 영문 제목 유지, 한국어 실무 안내 병기

## 0. 문서 사용법과 범위

이 문서는 Basel 기준의 비공식 번역본이나 국내 시행규정이 아니라 **공식 원문 전체를 빠짐없이 찾아갈 수 있는 버전 고정형 source map**이다. BIS의 통합 Basel Framework는 개별 PDF 한 권이 아니라 Standard → Chapter → paragraph 구조이며, 시행일과 공표일에 따라 같은 Chapter에 여러 버전이 존재한다.

BIS 이용조건은 BIS Material의 비상업적 다운로드·표시·인쇄·재배포를 허용하지만, 다른 상업적 publication/product에서의 전문 재수록은 별도 허가가 필요할 수 있다. 기업 내부·제품화 등 최종 이용형태가 확정되지 않았으므로 본 파일은 원문 전문을 복제하지 않고 공식 원문 위치·버전·상태를 전수 정리했다. 각 Chapter의 `공식 원문` 링크는 시행일(`inforce`)과 공표일(`published`)로 정확한 버전을 지정하며, `tldate`는 기준일 당시의 탐색 맥락을 제공한다. 공식 페이지에서 **PDF version** 또는 **PDF version (no FAQs)**를 선택할 수 있다.

- [Basel Framework 공식 진입점](https://www.bis.org/basel_framework/)
- [현행 Consolidated Basel Framework 전체 PDF](https://www.bis.org/baselframework/BaselFramework.pdf)
- [Consolidated Basel Framework mapping table](https://www.bis.org/bcbs/publ/d462/framework_mapping.xlsx)
- [BIS 이용조건](https://www.bis.org/terms_conditions.htm)
- [BIS permission requests](https://www.bis.org/permission_requests.htm)
- [BCBS publications](https://www.bis.org/bcbs/publications.htm)

### 완전성 요약

| 구분 | 건수 | 해석 |
|---|---:|---|
| Standard | 14 | BIS 통합 Framework의 전체 Standard |
| Current Chapter | 124 | 2026-08-09 현재 적용 중인 Chapter 버전 |
| Forthcoming Chapter version | 12 | 기준일 현재 공표됐으나 장래 시행 예정 |
| Chapter-version ledger | 308 | BIS 공식 source dataset의 current/superseded/removed/future 전 버전 |
| BCBS Standards publications | 94 | BIS가 publication type을 `Standards`로 분류한 발간물 전수 |
| Framework source metadata last modified | — | Fri, 26 Jun 2026 14:56:50 GMT |
| Publications source metadata last modified | — | Tue, 28 Jul 2026 12:08:44 GMT |

전체 버전 대사: ceased 48, current 124, forthcoming 12, removed 117, superseded 7 = 308

## 1. 14개 Standard 개요

| Code | 공식 영문명 | 한국어 업무영역 | Current | Future | All versions | 공식 원문 |
|---|---|---|---:|---:|---:|---|
| SCO | Scope and definitions | 적용범위 및 정의 | 6 | 1 | 15 | [Standard page](https://www.bis.org/basel_framework/standard/SCO.htm?tldate=20260809) |
| CAP | Definition of capital | 자본의 정의 | 5 | 0 | 7 | [Standard page](https://www.bis.org/basel_framework/standard/CAP.htm?tldate=20260809) |
| RBC | Risk-based capital requirements | 위험가중자본 요건 | 5 | 2 | 15 | [Standard page](https://www.bis.org/basel_framework/standard/RBC.htm?tldate=20260809) |
| CRE | Calculation of RWA for credit risk | 신용위험 RWA 산출 | 27 | 4 | 86 | [Standard page](https://www.bis.org/basel_framework/standard/CRE.htm?tldate=20260809) |
| MAR | Calculation of RWA for market risk | 시장위험 RWA 산출 | 15 | 0 | 44 | [Standard page](https://www.bis.org/basel_framework/standard/MAR.htm?tldate=20260809) |
| OPE | Calculation of RWA for operational risk | 운영위험 RWA 산출 | 2 | 2 | 19 | [Standard page](https://www.bis.org/basel_framework/standard/OPE.htm?tldate=20260809) |
| LEV | Leverage ratio | 레버리지비율 | 5 | 0 | 13 | [Standard page](https://www.bis.org/basel_framework/standard/LEV.htm?tldate=20260809) |
| LCR | Liquidity Coverage Ratio | 유동성커버리지비율 | 7 | 0 | 10 | [Standard page](https://www.bis.org/basel_framework/standard/LCR.htm?tldate=20260809) |
| NSF | Net stable funding ratio | 순안정자금조달비율 | 4 | 0 | 6 | [Standard page](https://www.bis.org/basel_framework/standard/NSF.htm?tldate=20260809) |
| LEX | Large exposures | 거액익스포저 | 4 | 0 | 8 | [Standard page](https://www.bis.org/basel_framework/standard/LEX.htm?tldate=20260809) |
| MGN | Margin requirements | 증거금 요건 | 3 | 0 | 4 | [Standard page](https://www.bis.org/basel_framework/standard/MGN.htm?tldate=20260809) |
| SRP | Supervisory review process | 감독검토절차 | 12 | 0 | 20 | [Standard page](https://www.bis.org/basel_framework/standard/SRP.htm?tldate=20260809) |
| DIS | Disclosure requirements | 공시 요건 | 21 | 3 | 52 | [Standard page](https://www.bis.org/basel_framework/standard/DIS.htm?tldate=20260809) |
| BCP | Core Principles for effective banking supervision | 효과적인 은행감독을 위한 핵심원칙 | 8 | 0 | 9 | [Standard page](https://www.bis.org/basel_framework/standard/BCP.htm?tldate=20260809) |

## 2. 현행 Chapter 전수 색인

아래 124건은 2026-08-09 현재의 Chapter 버전이다. `Last update`는 공식 메타데이터의 최종 갱신일이며 국내 시행일과 같다는 의미가 아니다.

### SCO — Scope and definitions / 적용범위 및 정의

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| SCO10 | Introduction | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO30 | Banking, securities and other financial subsidiaries | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO40 | Global systemically important banks | 2021-11-09 | 2021-11-09 | [Official](https://www.bis.org/basel_framework/chapter/SCO/40.htm?inforce=20211109&published=20211109&tldate=20260809) |
| SCO50 | Domestic systemically important banks | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO60 | Cryptoasset exposures | 2026-01-01 | 2024-11-27 | [Official](https://www.bis.org/basel_framework/chapter/SCO/60.htm?inforce=20260101&published=20241127&tldate=20260809) |
| SCO95 | Glossary and abbreviations | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/SCO/95.htm?inforce=20230101&published=20200327&tldate=20260809) |

### CAP — Definition of capital / 자본의 정의

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| CAP10 | Definition of eligible capital | 2019-12-15 | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CAP/10.htm?inforce=20191215&published=20200605&tldate=20260809) |
| CAP30 | Regulatory adjustments | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CAP50 | Prudent valuation guidance | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CAP90 | Transitional arrangements | 2020-04-03 | 2020-04-03 | [Official](https://www.bis.org/basel_framework/chapter/CAP/90.htm?inforce=20200403&published=20200403&tldate=20260809) |
| CAP99 | Application guidance | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/99.htm?inforce=20191215&published=20191215&tldate=20260809) |

### RBC — Risk-based capital requirements / 위험가중자본 요건

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| RBC20 | Calculation of minimum risk-based capital requirements | 2023-01-01 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20230101&published=20201126&tldate=20260809) |
| RBC25 | Boundary between the banking book and the trading book | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/RBC/25.htm?inforce=20230101&published=20200327&tldate=20260809) |
| RBC30 | Buffers above the regulatory minimum | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| RBC40 | Systemically important bank buffers | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/40.htm?inforce=20191215&published=20191215&tldate=20260809) |
| RBC90 | Transitional arrangements | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/RBC/90.htm?inforce=20230101&published=20200327&tldate=20260809) |

### CRE — Calculation of RWA for credit risk / 신용위험 RWA 산출

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| CRE20 | Standardised approach: individual exposures | 2023-01-01 | 2025-06-10 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20230101&published=20250610&tldate=20260809) |
| CRE21 | Standardised approach: use of external ratings | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/21.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE22 | Standardised approach: credit risk mitigation | 2023-01-01 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/22.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE30 | IRB approach: overview and asset class definitions | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/30.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE31 | IRB approach: risk weight functions | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/31.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE32 | IRB approach: risk components | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/32.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE33 | IRB approach: supervisory slotting approach for specialised lending | 2019-12-15 | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/CRE/33.htm?inforce=20191215&published=20221208&tldate=20260809) |
| CRE34 | IRB approach: RWA for purchased receivables | 2023-01-01 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/34.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE35 | IRB approach: treatment of expected losses and provisions | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/35.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE36 | IRB approach: minimum requirements to use IRB approach | 2023-01-01 | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/CRE/36.htm?inforce=20230101&published=20221208&tldate=20260809) |
| CRE40 | Securitisation: general provisions | 2023-01-01 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/40.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE41 | Securitisation: standardised approach | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/41.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE42 | Securitisation: External-ratings-based approach (SEC-ERBA) | 2023-01-01 | 2023-01-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/42.htm?inforce=20230101&published=20230101&tldate=20260809) |
| CRE43 | Securitisation: Internal assessment approach (SEC-IAA) | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/43.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE44 | Securitisation: Internal-ratings-based approach | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/44.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE45 | Securitisations of non-performing loans | 2023-01-01 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/45.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE50 | Counterparty credit risk definitions and terminology | 2019-12-15 | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/50.htm?inforce=20191215&published=20240705&tldate=20260809) |
| CRE51 | Counterparty credit risk overview | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/51.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE52 | Standardised approach to counterparty credit risk | 2023-01-01 | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/52.htm?inforce=20230101&published=20200605&tldate=20260809) |
| CRE53 | Internal models method for counterparty credit risk | 2023-01-01 | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/53.htm?inforce=20230101&published=20200605&tldate=20260809) |
| CRE54 | Capital requirements for bank exposures to central counterparties | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/54.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE55 | Counterparty credit risk in the trading book | 2023-01-01 | 2023-12-14 | [Official](https://www.bis.org/basel_framework/chapter/CRE/55.htm?inforce=20230101&published=20231214&tldate=20260809) |
| CRE56 | Minimum haircut floors for securities financing transactions | 2023-01-01 | 2021-07-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/56.htm?inforce=20230101&published=20210701&tldate=20260809) |
| CRE60 | Equity investments in funds | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/60.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE70 | Capital treatment of unsettled transactions and failed trades | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/70.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE90 | Transition | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/90.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE99 | Application guidance | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/99.htm?inforce=20230101&published=20200327&tldate=20260809) |

### MAR — Calculation of RWA for market risk / 시장위험 RWA 산출

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| MAR10 | Market risk terminology | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR11 | Definitions and application of market risk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/11.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR12 | Definition of trading desk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/12.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR20 | Standardised approach: general provisions and structure | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR21 | Standardised approach: sensitivities-based method | 2023-01-01 | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/MAR/21.htm?inforce=20230101&published=20260323&tldate=20260809) |
| MAR22 | Standardised approach: default risk capital requirement | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/22.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR23 | Standardised approach: residual risk add-on | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/23.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR30 | Internal models approach: general provisions | 2023-01-01 | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/30.htm?inforce=20230101&published=20240705&tldate=20260809) |
| MAR31 | Internal models approach: model requirements | 2023-01-01 | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/31.htm?inforce=20230101&published=20200605&tldate=20260809) |
| MAR32 | Internal models approach: backtesting and P&L attribution test requirements | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/32.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR33 | Internal models approach: capital requirements calculation | 2023-01-01 | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/33.htm?inforce=20230101&published=20200605&tldate=20260809) |
| MAR40 | Simplified standardised approach | 2023-01-01 | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/40.htm?inforce=20230101&published=20240705&tldate=20260809) |
| MAR50 | Credit valuation adjustment framework | 2023-01-01 | 2020-07-08 | [Official](https://www.bis.org/basel_framework/chapter/MAR/50.htm?inforce=20230101&published=20200708&tldate=20260809) |
| MAR90 | Transitional arrangements | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/90.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR99 | Guidance on use of the internal models approach | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/99.htm?inforce=20230101&published=20200327&tldate=20260809) |

### OPE — Calculation of RWA for operational risk / 운영위험 RWA 산출

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| OPE10 | Definitions and application | 2023-01-01 | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20230101&published=20240705&tldate=20260809) |
| OPE25 | Standardised approach | 2023-01-01 | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20230101&published=20240705&tldate=20260809) |

### LEV — Leverage ratio / 레버리지비율

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| LEV10 | Definitions and application | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV20 | Calculation | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV30 | Exposure measurement | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/30.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV40 | Leverage ratio requirements for global systemically important banks | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/40.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV90 | Transition | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/90.htm?inforce=20230101&published=20200327&tldate=20260809) |

### LCR — Liquidity Coverage Ratio / 유동성커버리지비율

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| LCR10 | Definitions and application | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR20 | Calculation | 2019-12-15 | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/LCR/20.htm?inforce=20191215&published=20221208&tldate=20260809) |
| LCR30 | High-quality liquid assets | 2019-12-15 | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/LCR/30.htm?inforce=20191215&published=20200605&tldate=20260809) |
| LCR31 | Alternative liquidity approaches | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/31.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR40 | Cash inflows and outflows | 2019-12-15 | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/LCR/40.htm?inforce=20191215&published=20230330&tldate=20260809) |
| LCR90 | Transition | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/90.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR99 | Application guidance | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/99.htm?inforce=20191215&published=20191215&tldate=20260809) |

### NSF — Net stable funding ratio / 순안정자금조달비율

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| NSF10 | Definitions and applications | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/NSF/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| NSF20 | Calculation and reporting | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/NSF/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| NSF30 | Available and required stable funding | 2019-12-15 | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/NSF/30.htm?inforce=20191215&published=20240705&tldate=20260809) |
| NSF99 | Definitions and applications | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/NSF/99.htm?inforce=20191215&published=20191215&tldate=20260809) |

### LEX — Large exposures / 거액익스포저

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| LEX10 | Definitions and application | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEX/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEX20 | Requirements | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEX30 | Exposure measurement | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEX/30.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEX40 | Large exposure rules for global systemically important banks | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/40.htm?inforce=20191215&published=20191215&tldate=20260809) |

### MGN — Margin requirements / 증거금 요건

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| MGN10 | Definitions and application | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MGN/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MGN20 | Requirements | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MGN/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MGN90 | Transition | 2020-04-03 | 2020-04-03 | [Official](https://www.bis.org/basel_framework/chapter/MGN/90.htm?inforce=20200403&published=20200403&tldate=20260809) |

### SRP — Supervisory review process / 감독검토절차

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| SRP10 | Importance of supervisory review | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP20 | Four key principles | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP30 | Risk management | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP31 | Interest rate risk in the banking book | 2026-01-01 | 2024-07-16 | [Official](https://www.bis.org/basel_framework/chapter/SRP/31.htm?inforce=20260101&published=20240716&tldate=20260809) |
| SRP32 | Credit risk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/SRP/32.htm?inforce=20230101&published=20200327&tldate=20260809) |
| SRP33 | Market risk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/SRP/33.htm?inforce=20230101&published=20200327&tldate=20260809) |
| SRP35 | Compensation practices | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/35.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP36 | Risk data aggregation and risk reporting | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/36.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP50 | Liquidity monitoring metrics | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP90 | Transition | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/90.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP98 | Application guidance on interest rate risk in the banking book | 2026-01-01 | 2024-07-16 | [Official](https://www.bis.org/basel_framework/chapter/SRP/98.htm?inforce=20260101&published=20240716&tldate=20260809) |
| SRP99 | Application guidance | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/99.htm?inforce=20191215&published=20191215&tldate=20260809) |

### DIS — Disclosure requirements / 공시 요건

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| DIS10 | Definitions and applications | 2026-01-01 | 2024-07-17 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20260101&published=20240717&tldate=20260809) |
| DIS20 | Overview of risk management, key prudential metrics and RWA | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS21 | Comparison of modelled and standardised RWA | 2023-01-01 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/DIS/21.htm?inforce=20230101&published=20201126&tldate=20260809) |
| DIS25 | Composition of capital and TLAC | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/25.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS26 | Capital distribution constraints | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/26.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS30 | Links between financial statements and regulatory exposures | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS31 | Asset encumbrance | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/31.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS35 | Remuneration | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/35.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS40 | Credit risk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/40.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS42 | Counterparty credit risk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/42.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS43 | Securitisation | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/43.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS45 | Sovereign exposures | 2023-01-01 | 2021-11-11 | [Official](https://www.bis.org/basel_framework/chapter/DIS/45.htm?inforce=20230101&published=20211111&tldate=20260809) |
| DIS50 | Market risk | 2023-01-01 | 2021-11-11 | [Official](https://www.bis.org/basel_framework/chapter/DIS/50.htm?inforce=20230101&published=20211111&tldate=20260809) |
| DIS51 | Credit valuation adjustment risk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/51.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS55 | Cryptoasset exposures | 2026-01-01 | 2024-07-17 | [Official](https://www.bis.org/basel_framework/chapter/DIS/55.htm?inforce=20260101&published=20240717&tldate=20260809) |
| DIS60 | Operational risk | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/60.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS70 | Interest rate risk in the banking book | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/70.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS75 | Macroprudential supervisory measures | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/75.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS80 | Leverage ratio | 2023-01-01 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/80.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS85 | Liquidity | 2019-12-15 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/85.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS99 | Worked examples | 2023-01-01 | 2021-11-11 | [Official](https://www.bis.org/basel_framework/chapter/DIS/99.htm?inforce=20230101&published=20211111&tldate=20260809) |

### BCP — Core Principles for effective banking supervision / 효과적인 은행감독을 위한 핵심원칙

| Chapter | Official title | Effective as of | Last update | 공식 원문 |
|---|---|---|---|---|
| BCP01 | Foreword | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/01.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP02 | Introduction to the Core Principles | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/02.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP10 | Explanation of certain terms used in the Core Principles | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/10.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP20 | Assessment methodology | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/20.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP30 | Preconditions for effective banking supervision | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/30.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP40 | The Core Principles and assessment criteria | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/40.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP98 | Update on Committee standards, guidelines and sound practices | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/98.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP99 | Structure and guidance for assessment reports prepared by the International Monetary Fund and World Bank | 2024-04-25 | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/99.htm?inforce=20240425&published=20240425&tldate=20260809) |

## 3. 장래 시행 예정 Chapter 버전

기준일 현재 공표되어 있으나 시행일이 미래인 버전은 12건이다. 현재 버전과 혼용하지 않는다.

| Chapter | Official title | Published | Effective as of | 공식 원문 |
|---|---|---|---|---|
| SCO40 | Global systemically important banks | 2023-11-08 | 2027-01-01 | [Official](https://www.bis.org/basel_framework/chapter/SCO/40.htm?inforce=20270101&published=20231108&tldate=20260809) |
| RBC20 | Calculation of minimum risk-based capital requirements | 2020-11-26 | 2028-01-01 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20280101&published=20201126&tldate=20260809) |
| RBC30 | Buffers above the regulatory minimum | 2023-11-08 | 2027-01-01 | [Official](https://www.bis.org/basel_framework/chapter/RBC/30.htm?inforce=20270101&published=20231108&tldate=20260809) |
| CRE20 | Standardised approach: individual exposures | 2025-06-10 | 2028-01-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20280101&published=20250610&tldate=20260809) |
| CRE22 | Standardised approach: credit risk mitigation | 2025-10-28 | 2028-11-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/22.htm?inforce=20281101&published=20251028&tldate=20260809) |
| CRE32 | IRB approach: risk components | 2025-10-28 | 2028-11-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/32.htm?inforce=20281101&published=20251028&tldate=20260809) |
| CRE51 | Counterparty credit risk overview | 2025-10-28 | 2028-11-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/51.htm?inforce=20281101&published=20251028&tldate=20260809) |
| OPE10 | Definitions and application | 2026-03-23 | 2029-04-01 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20290401&published=20260323&tldate=20260809) |
| OPE25 | Standardised approach | 2024-07-05 | 2027-01-01 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20270101&published=20240705&tldate=20260809) |
| DIS10 | Definitions and applications | 2024-07-17 | 2027-01-01 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20270101&published=20240717&tldate=20260809) |
| DIS51 | Credit valuation adjustment risk | 2023-11-08 | 2027-01-01 | [Official](https://www.bis.org/basel_framework/chapter/DIS/51.htm?inforce=20270101&published=20231108&tldate=20260809) |
| DIS75 | Macroprudential supervisory measures | 2023-11-08 | 2027-01-01 | [Official](https://www.bis.org/basel_framework/chapter/DIS/75.htm?inforce=20270101&published=20231108&tldate=20260809) |

## 4. Chapter-version 전체 원장

이 표는 중복 Chapter code를 제거하지 않는다. 동일 code의 복수 행은 개정 이력이며, 산출·검증 시에는 반드시 상태와 시행일을 함께 사용한다.

| Standard | Chapter | Official title | Status @ 2026-08-09 | Published | Effective | Out of force | Removed | Updated | 공식 원문 |
|---|---|---|---|---|---|---|---|---|---|
| SCO | SCO10 | Introduction | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO | SCO30 | Banking, securities and other financial subsidiaries | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO | SCO40 | Global systemically important banks | ceased | 2019-12-15 | 2019-12-15 | 2020-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/40.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO | SCO40 | Global systemically important banks | superseded | 2019-12-15 | 2021-01-01 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/40.htm?inforce=20210101&published=20191215&tldate=20260809) |
| SCO | SCO40 | Global systemically important banks | current | 2021-11-09 | 2021-11-09 | 2026-12-31 | — | 2021-11-09 | [Official](https://www.bis.org/basel_framework/chapter/SCO/40.htm?inforce=20211109&published=20211109&tldate=20260809) |
| SCO | SCO40 | Global systemically important banks | forthcoming | 2023-11-08 | 2027-01-01 | — | — | 2023-11-08 | [Official](https://www.bis.org/basel_framework/chapter/SCO/40.htm?inforce=20270101&published=20231108&tldate=20260809) |
| SCO | SCO50 | Domestic systemically important banks | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO | SCO60 | Cryptoasset exposures | removed | 2022-12-16 | 2025-01-01 | — | 2023-12-14 | 2022-12-16 | [Official](https://www.bis.org/basel_framework/chapter/SCO/60.htm?inforce=20250101&published=20221216&tldate=20260809) |
| SCO | SCO60 | Cryptoasset exposures | removed | 2023-12-14 | 2025-01-01 | — | 2024-05-13 | 2023-12-14 | [Official](https://www.bis.org/basel_framework/chapter/SCO/60.htm?inforce=20250101&published=20231214&tldate=20260809) |
| SCO | SCO60 | Cryptoasset exposures | removed | 2024-05-13 | 2026-01-01 | — | 2024-07-17 | 2024-05-13 | [Official](https://www.bis.org/basel_framework/chapter/SCO/60.htm?inforce=20260101&published=20240513&tldate=20260809) |
| SCO | SCO60 | Cryptoasset exposures | removed | 2024-07-17 | 2026-01-01 | — | 2024-11-27 | 2024-12-12 | [Official](https://www.bis.org/basel_framework/chapter/SCO/60.htm?inforce=20260101&published=20240717&tldate=20260809) |
| SCO | SCO60 | Cryptoasset exposures | current | 2024-11-27 | 2026-01-01 | — | — | 2024-11-27 | [Official](https://www.bis.org/basel_framework/chapter/SCO/60.htm?inforce=20260101&published=20241127&tldate=20260809) |
| SCO | SCO95 | Glossary and abbreviations | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/95.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SCO | SCO95 | Glossary and abbreviations | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SCO/95.htm?inforce=20220101&published=20191215&tldate=20260809) |
| SCO | SCO95 | Glossary and abbreviations | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/SCO/95.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CAP | CAP10 | Definition of eligible capital | superseded | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CAP | CAP10 | Definition of eligible capital | current | 2020-06-05 | 2019-12-15 | — | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CAP/10.htm?inforce=20191215&published=20200605&tldate=20260809) |
| CAP | CAP30 | Regulatory adjustments | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CAP | CAP50 | Prudent valuation guidance | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CAP | CAP90 | Transitional arrangements | superseded | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/90.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CAP | CAP90 | Transitional arrangements | current | 2020-04-03 | 2020-04-03 | — | — | 2020-04-03 | [Official](https://www.bis.org/basel_framework/chapter/CAP/90.htm?inforce=20200403&published=20200403&tldate=20260809) |
| CAP | CAP99 | Application guidance | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CAP/99.htm?inforce=20191215&published=20191215&tldate=20260809) |
| RBC | RBC20 | Calculation of minimum risk-based capital requirements | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| RBC | RBC20 | Calculation of minimum risk-based capital requirements | removed | 2019-12-15 | 2022-01-01 | 2026-12-31 | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20220101&published=20191215&tldate=20260809) |
| RBC | RBC20 | Calculation of minimum risk-based capital requirements | removed | 2020-03-27 | 2023-01-01 | 2027-12-31 | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| RBC | RBC20 | Calculation of minimum risk-based capital requirements | current | 2020-11-26 | 2023-01-01 | 2027-12-31 | — | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20230101&published=20201126&tldate=20260809) |
| RBC | RBC20 | Calculation of minimum risk-based capital requirements | removed | 2019-12-15 | 2027-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20270101&published=20191215&tldate=20260809) |
| RBC | RBC20 | Calculation of minimum risk-based capital requirements | removed | 2020-03-27 | 2028-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20280101&published=20200327&tldate=20260809) |
| RBC | RBC20 | Calculation of minimum risk-based capital requirements | forthcoming | 2020-11-26 | 2028-01-01 | — | — | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/RBC/20.htm?inforce=20280101&published=20201126&tldate=20260809) |
| RBC | RBC25 | Boundary between the banking book and the trading book | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/25.htm?inforce=20191215&published=20191215&tldate=20260809) |
| RBC | RBC25 | Boundary between the banking book and the trading book | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/25.htm?inforce=20220101&published=20191215&tldate=20260809) |
| RBC | RBC25 | Boundary between the banking book and the trading book | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/RBC/25.htm?inforce=20230101&published=20200327&tldate=20260809) |
| RBC | RBC30 | Buffers above the regulatory minimum | current | 2019-12-15 | 2019-12-15 | 2026-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| RBC | RBC30 | Buffers above the regulatory minimum | forthcoming | 2023-11-08 | 2027-01-01 | — | — | 2023-11-08 | [Official](https://www.bis.org/basel_framework/chapter/RBC/30.htm?inforce=20270101&published=20231108&tldate=20260809) |
| RBC | RBC40 | Systemically important bank buffers | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/40.htm?inforce=20191215&published=20191215&tldate=20260809) |
| RBC | RBC90 | Transitional arrangements | removed | 2019-12-15 | 2022-01-01 | 2026-12-31 | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/RBC/90.htm?inforce=20220101&published=20191215&tldate=20260809) |
| RBC | RBC90 | Transitional arrangements | current | 2020-03-27 | 2023-01-01 | 2028-01-01 | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/RBC/90.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | removed | 2020-03-27 | 2023-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | removed | 2020-11-26 | 2023-01-01 | — | 2022-12-08 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | removed | 2022-12-08 | 2023-01-01 | — | 2025-06-10 | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20230101&published=20221208&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | current | 2025-06-10 | 2023-01-01 | 2027-12-31 | — | 2025-06-10 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20230101&published=20250610&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | removed | 2024-11-27 | 2028-01-01 | — | 2025-06-10 | 2025-06-10 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20280101&published=20241127&tldate=20260809) |
| CRE | CRE20 | Standardised approach: individual exposures | forthcoming | 2025-06-10 | 2028-01-01 | — | — | 2025-06-10 | [Official](https://www.bis.org/basel_framework/chapter/CRE/20.htm?inforce=20280101&published=20250610&tldate=20260809) |
| CRE | CRE21 | Standardised approach: use of external ratings | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/21.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE21 | Standardised approach: use of external ratings | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/21.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE21 | Standardised approach: use of external ratings | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/21.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE22 | Standardised approach: credit risk mitigation | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/22.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE22 | Standardised approach: credit risk mitigation | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/22.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE22 | Standardised approach: credit risk mitigation | removed | 2020-03-27 | 2023-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/22.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE22 | Standardised approach: credit risk mitigation | current | 2020-11-26 | 2023-01-01 | — | — | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/22.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE | CRE22 | Standardised approach: credit risk mitigation | forthcoming | 2025-10-28 | 2028-11-01 | — | — | 2025-10-28 | [Official](https://www.bis.org/basel_framework/chapter/CRE/22.htm?inforce=20281101&published=20251028&tldate=20260809) |
| CRE | CRE30 | IRB approach: overview and asset class definitions | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE30 | IRB approach: overview and asset class definitions | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/30.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE30 | IRB approach: overview and asset class definitions | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/30.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE31 | IRB approach: risk weight functions | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/31.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE31 | IRB approach: risk weight functions | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/31.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE31 | IRB approach: risk weight functions | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/31.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE32 | IRB approach: risk components for each asset class | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/32.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE32 | IRB approach: risk components | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/32.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE32 | IRB approach: risk components | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/32.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE32 | IRB approach: risk components | forthcoming | 2025-10-28 | 2028-11-01 | — | — | 2025-10-28 | [Official](https://www.bis.org/basel_framework/chapter/CRE/32.htm?inforce=20281101&published=20251028&tldate=20260809) |
| CRE | CRE33 | IRB approach: supervisory slotting approach for specialised lending | removed | 2019-12-15 | 2019-12-15 | — | 2022-12-08 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/33.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE33 | IRB approach: supervisory slotting approach for specialised lending | current | 2022-12-08 | 2019-12-15 | — | — | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/CRE/33.htm?inforce=20191215&published=20221208&tldate=20260809) |
| CRE | CRE34 | IRB approach: RWA for purchased receivables | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/34.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE34 | IRB approach: RWA for purchased receivables | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/34.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE34 | IRB approach: RWA for purchased receivables | removed | 2020-03-27 | 2023-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/34.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE34 | IRB approach: RWA for purchased receivables | current | 2020-11-26 | 2023-01-01 | — | — | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/34.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE | CRE35 | IRB approach: treatment of expected losses and provisions | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/35.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE35 | IRB approach: treatment of expected losses and provisions | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/35.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE35 | IRB approach: treatment of expected losses and provisions | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/35.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE36 | IRB approach: minimum requirements to use IRB approach | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/36.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE36 | IRB approach: minimum requirements to use IRB approach | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/36.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE36 | IRB approach: minimum requirements to use IRB approach | removed | 2020-03-27 | 2023-01-01 | — | 2022-12-08 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/36.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE36 | IRB approach: minimum requirements to use IRB approach | current | 2022-12-08 | 2023-01-01 | — | — | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/CRE/36.htm?inforce=20230101&published=20221208&tldate=20260809) |
| CRE | CRE40 | Securitisation: general provisions | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/40.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE40 | Securitisation: general provisions | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/40.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE40 | Securitisation: general provisions | removed | 2020-03-27 | 2023-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/40.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE40 | Securitisation: general provisions | current | 2020-11-26 | 2023-01-01 | — | — | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/40.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE | CRE41 | Securitisation: standardised approach | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/41.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE42 | Securitisation: External-ratings-based approach (SEC-ERBA) | removed | 2019-12-15 | 2019-12-15 | — | 2022-12-31 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/42.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE42 | Securitisation: External-ratings-based approach (SEC-ERBA) | current | 2023-01-01 | 2023-01-01 | — | — | 2023-01-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/42.htm?inforce=20230101&published=20230101&tldate=20260809) |
| CRE | CRE43 | Securitisation: Internal assessment approach (SEC-IAA) | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/43.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE44 | Securitisation: Internal-ratings-based approach | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/44.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE44 | Securitisation: Internal-ratings-based approach | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/44.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE44 | Securitisation: Internal-ratings-based approach | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/44.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE45 | Securitisations of non-performing loans | current | 2020-11-26 | 2023-01-01 | — | — | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/CRE/45.htm?inforce=20230101&published=20201126&tldate=20260809) |
| CRE | CRE50 | Counterparty credit risk definitions and terminology | removed | 2019-12-15 | 2019-12-15 | — | 2024-07-05 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE50 | Counterparty credit risk definitions and terminology | current | 2024-07-05 | 2019-12-15 | — | — | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/50.htm?inforce=20191215&published=20240705&tldate=20260809) |
| CRE | CRE51 | Counterparty credit risk overview | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/51.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE51 | Counterparty credit risk overview | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/51.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE51 | Counterparty credit risk overview | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/51.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE51 | Counterparty credit risk overview | forthcoming | 2025-10-28 | 2028-11-01 | — | — | 2025-10-28 | [Official](https://www.bis.org/basel_framework/chapter/CRE/51.htm?inforce=20281101&published=20251028&tldate=20260809) |
| CRE | CRE52 | Standardised approach to counterparty credit risk | removed | 2019-12-15 | 2019-12-15 | 2022-12-31 | 2020-06-05 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/52.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE52 | Standardised approach to counterparty credit risk | ceased | 2020-06-05 | 2019-12-15 | 2022-12-31 | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/52.htm?inforce=20191215&published=20200605&tldate=20260809) |
| CRE | CRE52 | Standardised approach to counterparty credit risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/52.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE52 | Standardised approach to counterparty credit risk | removed | 2020-03-27 | 2023-01-01 | — | 2020-06-05 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/52.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE52 | Standardised approach to counterparty credit risk | current | 2020-06-05 | 2023-01-01 | — | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/52.htm?inforce=20230101&published=20200605&tldate=20260809) |
| CRE | CRE53 | Internal models method for counterparty credit risk | removed | 2019-12-15 | 2019-12-15 | 2022-12-31 | 2020-06-05 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/53.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE53 | Internal models method for counterparty credit risk | ceased | 2020-06-05 | 2019-12-15 | 2022-12-31 | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/53.htm?inforce=20191215&published=20200605&tldate=20260809) |
| CRE | CRE53 | Internal models method for counterparty credit risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/53.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE53 | Internal models method for counterparty credit risk | removed | 2020-03-27 | 2023-01-01 | — | 2020-06-05 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/53.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE53 | Internal models method for counterparty credit risk | current | 2020-06-05 | 2023-01-01 | — | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/CRE/53.htm?inforce=20230101&published=20200605&tldate=20260809) |
| CRE | CRE54 | Capital requirements for bank exposures to central counterparties | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/54.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE54 | Capital requirements for bank exposures to central counterparties | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/54.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE54 | Capital requirements for bank exposures to central counterparties | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/54.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE55 | Counterparty credit risk in the trading book | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/55.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE55 | Counterparty credit risk in the trading book | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/55.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE55 | Counterparty credit risk in the trading book | removed | 2020-03-27 | 2023-01-01 | — | 2023-12-14 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/55.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE55 | Counterparty credit risk in the trading book | current | 2023-12-14 | 2023-01-01 | — | — | 2023-12-14 | [Official](https://www.bis.org/basel_framework/chapter/CRE/55.htm?inforce=20230101&published=20231214&tldate=20260809) |
| CRE | CRE56 | Minimum haircut floors for securities financing transactions | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/56.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE56 | Minimum haircut floors for securities financing transactions | removed | 2020-03-27 | 2023-01-01 | — | 2021-07-01 | 2020-07-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/56.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE56 | Minimum haircut floors for securities financing transactions | current | 2021-07-01 | 2023-01-01 | — | — | 2021-07-01 | [Official](https://www.bis.org/basel_framework/chapter/CRE/56.htm?inforce=20230101&published=20210701&tldate=20260809) |
| CRE | CRE60 | Equity investments in funds | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/60.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE60 | Equity investments in funds | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/60.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE60 | Equity investments in funds | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/60.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE70 | Capital treatment of unsettled transactions and failed trades | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/70.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE90 | Transition | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/90.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE90 | Transition | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/90.htm?inforce=20230101&published=20200327&tldate=20260809) |
| CRE | CRE99 | Application guidance | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/99.htm?inforce=20191215&published=20191215&tldate=20260809) |
| CRE | CRE99 | Application guidance | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/CRE/99.htm?inforce=20220101&published=20191215&tldate=20260809) |
| CRE | CRE99 | Application guidance | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/CRE/99.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR10 | Definition and application for market risk | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MAR | MAR10 | Market risk terminology | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/10.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR10 | Market risk terminology | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR11 | Definitions and application of market risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/11.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR11 | Definitions and application of market risk | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/11.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR12 | Definition of trading desk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/12.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR12 | Definition of trading desk | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/12.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR20 | Standardised approach | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MAR | MAR20 | Standardised approach: general provisions and structure | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/20.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR20 | Standardised approach: general provisions and structure | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR21 | Standardised approach: sensitivities-based method | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/21.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR21 | Standardised approach: sensitivities-based method | removed | 2020-03-27 | 2023-01-01 | — | 2024-07-05 | 2024-07-19 | [Official](https://www.bis.org/basel_framework/chapter/MAR/21.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR21 | Standardised approach: sensitivities-based method | removed | 2024-07-05 | 2023-01-01 | — | 2026-03-23 | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/MAR/21.htm?inforce=20230101&published=20240705&tldate=20260809) |
| MAR | MAR21 | Standardised approach: sensitivities-based method | current | 2026-03-23 | 2023-01-01 | — | — | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/MAR/21.htm?inforce=20230101&published=20260323&tldate=20260809) |
| MAR | MAR22 | Standardised approach: default risk capital requirement | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/22.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR22 | Standardised approach: default risk capital requirement | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/22.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR23 | Standardised approach: residual risk add-on | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/23.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR23 | Standardised approach: residual risk add-on | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/23.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR30 | Internal models approach | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MAR | MAR30 | Internal models approach: general provisions | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/30.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR30 | Internal models approach: general provisions | removed | 2020-03-27 | 2023-01-01 | — | 2022-12-08 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/30.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR30 | Internal models approach: general provisions | removed | 2022-12-08 | 2023-01-01 | — | 2024-07-05 | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/MAR/30.htm?inforce=20230101&published=20221208&tldate=20260809) |
| MAR | MAR30 | Internal models approach: general provisions | current | 2024-07-05 | 2023-01-01 | — | — | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/30.htm?inforce=20230101&published=20240705&tldate=20260809) |
| MAR | MAR31 | Internal models approach: model requirements | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/31.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR31 | Internal models approach: model requirements | removed | 2020-03-27 | 2023-01-01 | — | 2020-06-05 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/31.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR31 | Internal models approach: model requirements | current | 2020-06-05 | 2023-01-01 | — | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/31.htm?inforce=20230101&published=20200605&tldate=20260809) |
| MAR | MAR32 | Internal models approach: backtesting and P&L attribution test requirements | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/32.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR32 | Internal models approach: backtesting and P&L attribution test requirements | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/32.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR33 | Internal models approach: capital requirements calculation | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/33.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR33 | Internal models approach: capital requirements calculation | removed | 2020-03-27 | 2023-01-01 | — | 2020-06-05 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/33.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR33 | Internal models approach: capital requirements calculation | current | 2020-06-05 | 2023-01-01 | — | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/33.htm?inforce=20230101&published=20200605&tldate=20260809) |
| MAR | MAR40 | Simplified standardised approach | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/40.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR40 | Simplified standardised approach | removed | 2020-03-27 | 2023-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/40.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR40 | Simplified standardised approach | removed | 2020-11-26 | 2023-01-01 | — | 2024-07-05 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/MAR/40.htm?inforce=20230101&published=20201126&tldate=20260809) |
| MAR | MAR40 | Simplified standardised approach | current | 2024-07-05 | 2023-01-01 | — | — | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/MAR/40.htm?inforce=20230101&published=20240705&tldate=20260809) |
| MAR | MAR50 | Credit valuation adjustment framework | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MAR | MAR50 | Credit valuation adjustment framework | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/50.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR50 | Credit valuation adjustment framework | removed | 2020-03-27 | 2023-01-01 | — | 2020-07-08 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/50.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR50 | Credit valuation adjustment framework | current | 2020-07-08 | 2023-01-01 | — | — | 2020-07-08 | [Official](https://www.bis.org/basel_framework/chapter/MAR/50.htm?inforce=20230101&published=20200708&tldate=20260809) |
| MAR | MAR90 | Transitional arrangements | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/90.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR90 | Transitional arrangements | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/90.htm?inforce=20230101&published=20200327&tldate=20260809) |
| MAR | MAR99 | Application guidance | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/99.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MAR | MAR99 | Guidance on use of the internal models approach | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MAR/99.htm?inforce=20220101&published=20191215&tldate=20260809) |
| MAR | MAR99 | Guidance on use of the internal models approach | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/MAR/99.htm?inforce=20230101&published=20200327&tldate=20260809) |
| OPE | OPE10 | Definitions and application | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| OPE | OPE10 | Definitions and application | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20220101&published=20191215&tldate=20260809) |
| OPE | OPE10 | Definitions and application | removed | 2020-03-27 | 2023-01-01 | — | 2023-03-30 | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| OPE | OPE10 | Definitions and application | removed | 2023-03-30 | 2023-01-01 | — | 2024-07-05 | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20230101&published=20230330&tldate=20260809) |
| OPE | OPE10 | Definitions and application | current | 2024-07-05 | 2023-01-01 | 2029-04-01 | — | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20230101&published=20240705&tldate=20260809) |
| OPE | OPE10 | Definitions and application | forthcoming | 2026-03-23 | 2029-04-01 | — | — | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/OPE/10.htm?inforce=20290401&published=20260323&tldate=20260809) |
| OPE | OPE20 | Basic indicator approach | removed | 2019-12-15 | 2019-12-15 | 2021-12-31 | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/OPE/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| OPE | OPE20 | Basic indicator approach | ceased | 2020-03-27 | 2019-12-15 | 2022-12-31 | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/OPE/20.htm?inforce=20191215&published=20200327&tldate=20260809) |
| OPE | OPE25 | Standardised approach | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20191215&published=20191215&tldate=20260809) |
| OPE | OPE25 | Standardised approach | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20220101&published=20191215&tldate=20260809) |
| OPE | OPE25 | Standardised approach | removed | 2020-03-27 | 2023-01-01 | — | 2020-06-05 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20230101&published=20200327&tldate=20260809) |
| OPE | OPE25 | Standardised approach | removed | 2020-06-05 | 2023-01-01 | — | 2022-12-08 | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20230101&published=20200605&tldate=20260809) |
| OPE | OPE25 | Standardised approach | removed | 2022-12-08 | 2023-01-01 | — | 2023-03-30 | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20230101&published=20221208&tldate=20260809) |
| OPE | OPE25 | Standardised approach | removed | 2023-03-30 | 2023-01-01 | 2026-12-31 | 2024-07-05 | 2024-07-19 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20230101&published=20230330&tldate=20260809) |
| OPE | OPE25 | Standardised approach | current | 2024-07-05 | 2023-01-01 | 2026-12-31 | — | 2026-03-23 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20230101&published=20240705&tldate=20260809) |
| OPE | OPE25 | Standardised approach | removed | 2023-11-08 | 2027-01-01 | — | 2024-07-05 | 2023-11-08 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20270101&published=20231108&tldate=20260809) |
| OPE | OPE25 | Standardised approach | forthcoming | 2024-07-05 | 2027-01-01 | — | — | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/OPE/25.htm?inforce=20270101&published=20240705&tldate=20260809) |
| OPE | OPE30 | Advanced Measurement Approaches | removed | 2019-12-15 | 2019-12-15 | 2021-12-31 | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/OPE/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| OPE | OPE30 | Advanced Measurement Approaches | ceased | 2020-03-27 | 2019-12-15 | 2022-12-31 | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/OPE/30.htm?inforce=20191215&published=20200327&tldate=20260809) |
| LEV | LEV10 | Definitions and application | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEV | LEV10 | Definitions and application | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/10.htm?inforce=20220101&published=20191215&tldate=20260809) |
| LEV | LEV10 | Definitions and application | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV | LEV20 | Calculation | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEV | LEV20 | Calculation | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/20.htm?inforce=20220101&published=20191215&tldate=20260809) |
| LEV | LEV20 | Calculation | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV | LEV30 | Exposure measurement | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEV | LEV30 | Exposure measurement | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/30.htm?inforce=20220101&published=20191215&tldate=20260809) |
| LEV | LEV30 | Exposure measurement | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/30.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV | LEV40 | Leverage ratio requirements for global systemically important banks | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/40.htm?inforce=20220101&published=20191215&tldate=20260809) |
| LEV | LEV40 | Leverage ratio requirements for global systemically important banks | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/40.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEV | LEV90 | Transition | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEV/90.htm?inforce=20220101&published=20191215&tldate=20260809) |
| LEV | LEV90 | Transition | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEV/90.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LCR | LCR10 | Definitions and application | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR | LCR20 | Calculation | removed | 2019-12-15 | 2019-12-15 | — | 2022-12-08 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR | LCR20 | Calculation | current | 2022-12-08 | 2019-12-15 | — | — | 2022-12-08 | [Official](https://www.bis.org/basel_framework/chapter/LCR/20.htm?inforce=20191215&published=20221208&tldate=20260809) |
| LCR | LCR30 | High-quality liquid assets | removed | 2019-12-15 | 2019-12-15 | — | 2020-06-05 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR | LCR30 | High-quality liquid assets | current | 2020-06-05 | 2019-12-15 | — | — | 2020-06-05 | [Official](https://www.bis.org/basel_framework/chapter/LCR/30.htm?inforce=20191215&published=20200605&tldate=20260809) |
| LCR | LCR31 | Alternative liquidity approaches | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/31.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR | LCR40 | Cash inflows and outflows | removed | 2019-12-15 | 2019-12-15 | — | 2023-03-30 | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/LCR/40.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR | LCR40 | Cash inflows and outflows | current | 2023-03-30 | 2019-12-15 | — | — | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/LCR/40.htm?inforce=20191215&published=20230330&tldate=20260809) |
| LCR | LCR90 | Transition | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/90.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LCR | LCR99 | Application guidance | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LCR/99.htm?inforce=20191215&published=20191215&tldate=20260809) |
| NSF | NSF10 | Definitions and applications | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/NSF/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| NSF | NSF20 | Calculation and reporting | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/NSF/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| NSF | NSF30 | Available and required stable funding | removed | 2019-12-15 | 2019-12-15 | — | 2023-03-30 | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/NSF/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| NSF | NSF30 | Available and required stable funding | removed | 2023-03-30 | 2019-12-15 | — | 2024-07-05 | 2023-03-30 | [Official](https://www.bis.org/basel_framework/chapter/NSF/30.htm?inforce=20191215&published=20230330&tldate=20260809) |
| NSF | NSF30 | Available and required stable funding | current | 2024-07-05 | 2019-12-15 | — | — | 2024-07-05 | [Official](https://www.bis.org/basel_framework/chapter/NSF/30.htm?inforce=20191215&published=20240705&tldate=20260809) |
| NSF | NSF99 | Definitions and applications | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/NSF/99.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEX | LEX10 | Definitions and application | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEX | LEX10 | Definitions and application | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/10.htm?inforce=20220101&published=20191215&tldate=20260809) |
| LEX | LEX10 | Definitions and application | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEX/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEX | LEX20 | Requirements | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEX | LEX30 | Exposure measurement | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| LEX | LEX30 | Exposure measurement | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/30.htm?inforce=20220101&published=20191215&tldate=20260809) |
| LEX | LEX30 | Exposure measurement | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/LEX/30.htm?inforce=20230101&published=20200327&tldate=20260809) |
| LEX | LEX40 | Large exposure rules for global systemically important banks | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/LEX/40.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MGN | MGN10 | Definitions and application | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MGN/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MGN | MGN20 | Requirements | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MGN/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MGN | MGN90 | Transition | superseded | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/MGN/90.htm?inforce=20191215&published=20191215&tldate=20260809) |
| MGN | MGN90 | Transition | current | 2020-04-03 | 2020-04-03 | — | — | 2020-04-03 | [Official](https://www.bis.org/basel_framework/chapter/MGN/90.htm?inforce=20200403&published=20200403&tldate=20260809) |
| SRP | SRP10 | Importance of supervisory review | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP20 | Four key principles | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP30 | Risk management | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP31 | Interest rate risk in the banking book | superseded | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/31.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP31 | Interest rate risk in the banking book | current | 2024-07-16 | 2026-01-01 | — | — | 2024-07-16 | [Official](https://www.bis.org/basel_framework/chapter/SRP/31.htm?inforce=20260101&published=20240716&tldate=20260809) |
| SRP | SRP32 | Credit risk | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/32.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP32 | Credit risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/32.htm?inforce=20220101&published=20191215&tldate=20260809) |
| SRP | SRP32 | Credit risk | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/SRP/32.htm?inforce=20230101&published=20200327&tldate=20260809) |
| SRP | SRP33 | Market risk | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/33.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP33 | Market risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/33.htm?inforce=20220101&published=20191215&tldate=20260809) |
| SRP | SRP33 | Market risk | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/SRP/33.htm?inforce=20230101&published=20200327&tldate=20260809) |
| SRP | SRP34 | Operational risk | removed | 2019-12-15 | 2019-12-15 | 2021-12-31 | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/34.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP34 | Operational risk | ceased | 2020-03-27 | 2019-12-15 | 2022-12-31 | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/SRP/34.htm?inforce=20191215&published=20200327&tldate=20260809) |
| SRP | SRP35 | Compensation practices | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/35.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP36 | Risk data aggregation and risk reporting | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/36.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP50 | Liquidity monitoring metrics | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP90 | Transition | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/90.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP98 | Application guidance on interest rate risk in the banking book | superseded | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/98.htm?inforce=20191215&published=20191215&tldate=20260809) |
| SRP | SRP98 | Application guidance on interest rate risk in the banking book | current | 2024-07-16 | 2026-01-01 | — | — | 2024-07-16 | [Official](https://www.bis.org/basel_framework/chapter/SRP/98.htm?inforce=20260101&published=20240716&tldate=20260809) |
| SRP | SRP99 | Application guidance | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/SRP/99.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | removed | 2019-12-15 | 2020-12-31 | 2021-12-31 | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20201231&published=20191215&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | removed | 2020-03-27 | 2023-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | removed | 2020-11-26 | 2023-01-01 | — | 2021-11-11 | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20230101&published=20201126&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | superseded | 2021-11-11 | 2023-01-01 | 2026-12-31 | — | 2021-11-11 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20230101&published=20211111&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | current | 2024-07-17 | 2026-01-01 | — | — | 2024-07-17 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20260101&published=20240717&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | removed | 2023-11-08 | 2027-01-01 | — | 2024-07-17 | 2024-09-04 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20270101&published=20231108&tldate=20260809) |
| DIS | DIS10 | Definitions and applications | forthcoming | 2024-07-17 | 2027-01-01 | — | — | 2024-07-17 | [Official](https://www.bis.org/basel_framework/chapter/DIS/10.htm?inforce=20270101&published=20240717&tldate=20260809) |
| DIS | DIS20 | Overview of risk management, key prudential metrics and RWA | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/20.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS20 | Overview of risk management, key prudential metrics and RWA | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/20.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS20 | Overview of risk management, key prudential metrics and RWA | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/20.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS21 | Comparison of modelled and standardised RWA | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/21.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS21 | Comparison of modelled and standardised RWA | removed | 2020-03-27 | 2023-01-01 | — | 2020-11-26 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/21.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS21 | Comparison of modelled and standardised RWA | current | 2020-11-26 | 2023-01-01 | — | — | 2020-11-26 | [Official](https://www.bis.org/basel_framework/chapter/DIS/21.htm?inforce=20230101&published=20201126&tldate=20260809) |
| DIS | DIS25 | Composition of capital and TLAC | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/25.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS26 | Capital distribution constraints | removed | 2019-12-15 | 2020-12-31 | 2021-12-31 | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/26.htm?inforce=20201231&published=20191215&tldate=20260809) |
| DIS | DIS26 | Capital distribution constraints | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/26.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS26 | Capital distribution constraints | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/26.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS30 | Links between financial statements and regulatory exposures | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/30.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS31 | Asset encumbrance | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/31.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS31 | Asset encumbrance | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/31.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS35 | Remuneration | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/35.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS40 | Credit risk | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/40.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS40 | Credit risk | removed | 2019-12-15 | 2020-12-31 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/40.htm?inforce=20201231&published=20191215&tldate=20260809) |
| DIS | DIS40 | Credit risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/40.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS40 | Credit risk | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/40.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS42 | Counterparty credit risk | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/42.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS42 | Counterparty credit risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/42.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS42 | Counterparty credit risk | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/42.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS43 | Securitisation | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/43.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS45 | Sovereign exposures | current | 2021-11-11 | 2023-01-01 | — | — | 2021-11-11 | [Official](https://www.bis.org/basel_framework/chapter/DIS/45.htm?inforce=20230101&published=20211111&tldate=20260809) |
| DIS | DIS50 | Market risk | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/50.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS50 | Market risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/50.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS50 | Market risk | removed | 2020-03-27 | 2023-01-01 | — | 2021-11-11 | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/50.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS50 | Market risk | current | 2021-11-11 | 2023-01-01 | — | — | 2021-11-11 | [Official](https://www.bis.org/basel_framework/chapter/DIS/50.htm?inforce=20230101&published=20211111&tldate=20260809) |
| DIS | DIS51 | Credit valuation adjustment risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/51.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS51 | Credit valuation adjustment risk | current | 2020-03-27 | 2023-01-01 | 2026-12-31 | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/51.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS51 | Credit valuation adjustment risk | forthcoming | 2023-11-08 | 2027-01-01 | — | — | 2023-11-08 | [Official](https://www.bis.org/basel_framework/chapter/DIS/51.htm?inforce=20270101&published=20231108&tldate=20260809) |
| DIS | DIS55 | Cryptoasset exposures | current | 2024-07-17 | 2026-01-01 | — | — | 2024-07-17 | [Official](https://www.bis.org/basel_framework/chapter/DIS/55.htm?inforce=20260101&published=20240717&tldate=20260809) |
| DIS | DIS60 | Operational risk | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/60.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS60 | Operational risk | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/60.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS60 | Operational risk | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/60.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS70 | Interest rate risk in the banking book | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/70.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS75 | Macroprudential supervisory measures | current | 2019-12-15 | 2019-12-15 | 2026-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/75.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS75 | Macroprudential supervisory measures | forthcoming | 2023-11-08 | 2027-01-01 | — | — | 2023-11-08 | [Official](https://www.bis.org/basel_framework/chapter/DIS/75.htm?inforce=20270101&published=20231108&tldate=20260809) |
| DIS | DIS80 | Leverage ratio | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/80.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS80 | Leverage ratio | removed | 2019-12-15 | 2022-01-01 | — | 2020-03-27 | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/80.htm?inforce=20220101&published=20191215&tldate=20260809) |
| DIS | DIS80 | Leverage ratio | current | 2020-03-27 | 2023-01-01 | — | — | 2020-03-27 | [Official](https://www.bis.org/basel_framework/chapter/DIS/80.htm?inforce=20230101&published=20200327&tldate=20260809) |
| DIS | DIS85 | Liquidity | current | 2019-12-15 | 2019-12-15 | — | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/85.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS99 | Worked examples | ceased | 2019-12-15 | 2019-12-15 | 2022-12-31 | — | 2019-12-15 | [Official](https://www.bis.org/basel_framework/chapter/DIS/99.htm?inforce=20191215&published=20191215&tldate=20260809) |
| DIS | DIS99 | Worked examples | current | 2021-11-11 | 2023-01-01 | — | — | 2021-11-11 | [Official](https://www.bis.org/basel_framework/chapter/DIS/99.htm?inforce=20230101&published=20211111&tldate=20260809) |
| BCP | BCP01 | The core principles | ceased | 2019-12-15 | 2019-12-15 | 2024-04-24 | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/01.htm?inforce=20191215&published=20191215&tldate=20260809) |
| BCP | BCP01 | Foreword | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/01.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP | BCP02 | Introduction to the Core Principles | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/02.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP | BCP10 | Explanation of certain terms used in the Core Principles | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/10.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP | BCP20 | Assessment methodology | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/20.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP | BCP30 | Preconditions for effective banking supervision | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/30.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP | BCP40 | The Core Principles and assessment criteria | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/40.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP | BCP98 | Update on Committee standards, guidelines and sound practices | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/98.htm?inforce=20240425&published=20240425&tldate=20260809) |
| BCP | BCP99 | Structure and guidance for assessment reports prepared by the International Monetary Fund and World Bank | current | 2024-04-25 | 2024-04-25 | — | — | 2024-04-25 | [Official](https://www.bis.org/basel_framework/chapter/BCP/99.htm?inforce=20240425&published=20240425&tldate=20260809) |

## 5. BCBS `Standards` 발간물 전수 색인

BIS의 BCBS Publications 모집단에서 publication type이 `Standards`인 94건을 전수 수록했다. Consolidated 60, Superseded 34. `Consolidated`는 통합 Framework에 반영됐다는 뜻이며, 국내 법규에 곧바로 직접 효력이 있다는 뜻은 아니다.

| No. | Date | Official title | Publication status | Topics | Official source |
|---:|---|---|---|---|---|
| 1 | 1988-07-15 | International convergence of capital measurement and capital standards | Superseded | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs04a.htm) |
| 2 | 1991-11-06 | Amendment of the Basel capital accord in respect of the inclusion of general provisions/general loan-loss reserves in capital | Superseded | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs09.htm) |
| 3 | 1992-07-28 | Minimum standards for the supervision of international banking groups and their cross-border establishments | Superseded | Supervisory cooperation | [BIS/BCBS](https://www.bis.org/publ/bcbsc314.htm) |
| 4 | 1994-12-28 | Amendment to the 1988 Capital Accord Recognition of Collateral | Superseded | Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs14a.htm) |
| 5 | 1995-04-29 | Basel Capital Accord: treatment of potential exposure for off-balance-sheet items | Superseded | Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs18.htm) |
| 6 | 1996-01-04 | Amendment to the capital accord to incorporate market risks | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs24.htm) |
| 7 | 1996-01-04 | Overview of the amendment to the capital accord to incorporate market risks | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs23.htm) |
| 8 | 1996-01-04 | Supervisory framework for the use of 'backtesting' in conjunction with the internal models approach to market risk capital requirements | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs22.htm) |
| 9 | 1997-09-19 | Modifications to the market risk amendment | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs24a.htm) |
| 10 | 1997-09-22 | Core principles for effective banking supervision | Superseded | Basel core principles | [BIS/BCBS](https://www.bis.org/publ/bcbs30a.htm) |
| 11 | 1998-04-06 | Amendment to the Basel Capital Accord of July 1988 | Superseded | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs36.htm) |
| 12 | 1998-04-18 | International convergence of capital measurement and capital standards (updated to April 1998) | Superseded | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbsc111.htm) |
| 13 | 1999-10-11 | The Core Principles Methodology | Superseded | Basel core principles | [BIS/BCBS](https://www.bis.org/publ/bcbs61.htm) |
| 14 | 2004-06-10 | Basel II: International Convergence of Capital Measurement and Capital Standards: a Revised Framework | Superseded | Operational risk, Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs107.htm) |
| 15 | 2005-07-30 | The Application of Basel II to Trading Activities and the Treatment of Double Default Effects | Superseded | Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs116.htm) |
| 16 | 2005-11-15 | Amendment to the capital accord to incorporate market risks | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs119.htm) |
| 17 | 2005-11-15 | Basel II: International Convergence of Capital Measurement and Capital Standards: A Revised Framework | Superseded | Operational risk, Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs118.htm) |
| 18 | 2006-06-30 | Basel II: International Convergence of Capital Measurement and Capital Standards: A Revised Framework - Comprehensive Version | Consolidated | Operational risk, Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs128.htm) |
| 19 | 2006-10-05 | Core Principles Methodology | Superseded | Basel core principles | [BIS/BCBS](https://www.bis.org/publ/bcbs130.htm) |
| 20 | 2006-10-05 | Core Principles for Effective Banking Supervision | Superseded | Basel core principles | [BIS/BCBS](https://www.bis.org/publ/bcbs129.htm) |
| 21 | 2006-10-24 | Risk weight for International Finance Facility for Immunization (IFFIm) | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs_nl10.htm) |
| 22 | 2009-06-18 | Core Principles for Effective Deposit Insurance Systems | Superseded | Resolution and deposit insurance | [BIS/BCBS](https://www.bis.org/publ/bcbs156.htm) |
| 23 | 2009-07-13 | Enhancements to the Basel II framework | Consolidated | Credit risk, Governance | [BIS/BCBS](https://www.bis.org/publ/bcbs157.htm) |
| 24 | 2009-07-13 | Guidelines for computing capital for incremental risk in the trading book | Consolidated | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs159.htm) |
| 25 | 2009-07-13 | Revisions to the Basel II market risk framework | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs158.htm) |
| 26 | 2009-12-23 | LGD Floors | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs_nl14.htm) |
| 27 | 2010-05-04 | Risk weight for the Multilateral Investment Guarantee Agency (MIGA) | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs_nl15.htm) |
| 28 | 2010-12-16 | Basel III: A global regulatory framework for more resilient banks and banking systems | Superseded | Market risk, Credit risk, Definition of capital | [BIS/BCBS](https://www.bis.org/publ/bcbs189_dec2010.htm) |
| 29 | 2010-12-16 | Basel III: International framework for liquidity risk measurement, standards and monitoring | Superseded | Liquidity risk | [BIS/BCBS](https://www.bis.org/publ/bcbs188.htm) |
| 30 | 2011-01-13 | Final elements of the reforms to raise the quality of regulatory capital issued by the Basel Committee | Consolidated | Definition of capital | [BIS/BCBS](https://www.bis.org/bcbs/publ/d191a.htm) |
| 31 | 2011-01-27 | Core Principles for Effective Deposit Insurance Systems - A methodology for compliance assessment | Superseded | Resolution and deposit insurance | [BIS/BCBS](https://www.bis.org/publ/bcbs192.htm) |
| 32 | 2011-02-11 | Revisions to the Basel II market risk framework - updated as of 31 December 2010 | Consolidated | Market risk | [BIS/BCBS](https://www.bis.org/publ/bcbs193.htm) |
| 33 | 2011-06-01 | Basel III: A global regulatory framework for more resilient banks and banking systems - revised version June 2011 | Consolidated | Market risk, Credit risk, Definition of capital | [BIS/BCBS](https://www.bis.org/publ/bcbs189.htm) |
| 34 | 2011-07-01 | Pillar 3 disclosure requirements for remuneration | Superseded | Disclosure, Governance | [BIS/BCBS](https://www.bis.org/publ/bcbs197.htm) |
| 35 | 2011-10-25 | Treatment of trade finance under the Basel capital framework | Consolidated | Credit risk, Leverage ratio | [BIS/BCBS](https://www.bis.org/publ/bcbs205.htm) |
| 36 | 2011-11-04 | Global systemically important banks: Assessment methodology and the additional loss absorbency requirement | Superseded | Macroprudential / systemic importance | [BIS/BCBS](https://www.bis.org/publ/bcbs207.htm) |
| 37 | 2012-06-26 | Composition of capital disclosure requirements - Rules text | Consolidated | Definition of capital, Disclosure | [BIS/BCBS](https://www.bis.org/publ/bcbs221.htm) |
| 38 | 2012-07-25 | Capital requirements for bank exposures to central counterparties | Superseded | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs227.htm) |
| 39 | 2012-09-14 | Core principles for effective banking supervision | Consolidated | Basel core principles | [BIS/BCBS](https://www.bis.org/publ/bcbs230.htm) |
| 40 | 2012-10-11 | A framework for dealing with domestic systemically important banks | Consolidated | Macroprudential / systemic importance | [BIS/BCBS](https://www.bis.org/publ/bcbs233.htm) |
| 41 | 2013-01-07 | Basel III: The Liquidity Coverage Ratio and liquidity risk monitoring tools | Consolidated | Liquidity risk | [BIS/BCBS](https://www.bis.org/publ/bcbs238.htm) |
| 42 | 2013-04-11 | Monitoring tools for intraday liquidity management | Consolidated | Liquidity risk | [BIS/BCBS](https://www.bis.org/publ/bcbs248.htm) |
| 43 | 2013-07-03 | Global systemically important banks: updated assessment methodology and the higher loss absorbency requirement | Consolidated | Macroprudential / systemic importance | [BIS/BCBS](https://www.bis.org/publ/bcbs255.htm) |
| 44 | 2013-09-02 | Margin requirements for non-centrally cleared derivatives | Superseded | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs261.htm) |
| 45 | 2013-12-13 | Capital requirements for banks' equity investments in funds | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs266.htm) |
| 46 | 2014-01-12 | Basel III leverage ratio framework and disclosure requirements | Consolidated | Disclosure, Leverage ratio | [BIS/BCBS](https://www.bis.org/publ/bcbs270.htm) |
| 47 | 2014-01-12 | Liquidity coverage ratio disclosure standards | Superseded | Disclosure, Liquidity risk | [BIS/BCBS](https://www.bis.org/publ/bcbs272.htm) |
| 48 | 2014-01-12 | The Liquidity Coverage Ratio and restricted-use committed liquidity facilities | Consolidated | Liquidity risk | [BIS/BCBS](https://www.bis.org/publ/bcbs274.htm) |
| 49 | 2014-03-18 | Risk Weight for the European Stability Mechanism (ESM) and European Financial Stability Facility (EFSF) | Consolidated | Credit risk, Liquidity risk | [BIS/BCBS](https://www.bis.org/publ/bcbs_nl17.htm) |
| 50 | 2014-03-31 | The standardised approach for measuring counterparty credit risk exposures | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs279.htm) |
| 51 | 2014-04-10 | Capital requirements for bank exposures to central counterparties | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs282.htm) |
| 52 | 2014-04-15 | Supervisory framework for measuring and controlling large exposures | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs283.htm) |
| 53 | 2014-10-31 | Basel III: the net stable funding ratio | Consolidated | Liquidity risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d295.htm) |
| 54 | 2014-11-06 | The G-SIB assessment methodology - score calculation | Consolidated | Macroprudential / systemic importance | [BIS/BCBS](https://www.bis.org/bcbs/publ/d296.htm) |
| 55 | 2014-12-11 | Revisions to the securitisation framework | Superseded | Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d303.htm) |
| 56 | 2015-01-28 | Revised Pillar 3 disclosure requirements | Consolidated | Market risk, Credit risk, Disclosure | [BIS/BCBS](https://www.bis.org/bcbs/publ/d309.htm) |
| 57 | 2015-03-18 | Margin requirements for non-centrally cleared derivatives | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d317.htm) |
| 58 | 2015-06-22 | Net Stable Funding Ratio disclosure standards | Superseded | Disclosure, Liquidity risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d324.htm) |
| 59 | 2016-01-14 | Minimum capital requirements for market risk | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d352.htm) |
| 60 | 2016-04-21 | Interest rate risk in the banking book | Consolidated | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d368.htm) |
| 61 | 2016-07-11 | Revisions to the securitisation framework | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d374.htm) |
| 62 | 2016-10-12 | TLAC holdings standard | Consolidated | Definition of capital | [BIS/BCBS](https://www.bis.org/bcbs/publ/d387.htm) |
| 63 | 2016-11-30 | Risk weight for the International Development Association (IDA) | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/publ/bcbs_nl19.htm) |
| 64 | 2017-03-29 | Pillar 3 disclosure requirements - consolidated and enhanced framework | Consolidated | Disclosure | [BIS/BCBS](https://www.bis.org/bcbs/publ/d400.htm) |
| 65 | 2017-03-29 | Regulatory treatment of accounting provisions - interim approach and transitional arrangements | Consolidated | Accounting and auditing, Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d401.htm) |
| 66 | 2017-10-06 | Implementation of net stable funding ratio and treatment of derivative liabilities | Consolidated | Liquidity risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d417a.htm) |
| 67 | 2017-10-10 | Risk weight for Asian Infrastructure Investment Bank | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d417b.htm) |
| 68 | 2017-12-07 | Basel III: Finalising post-crisis reforms | Consolidated | Operational risk, Credit risk, Leverage ratio | [BIS/BCBS](https://www.bis.org/bcbs/publ/d424.htm) |
| 69 | 2018-05-14 | Capital treatment for simple, transparent and comparable short-term securitisations | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d442.htm) |
| 70 | 2018-06-29 | Treatment of extraordinary monetary policy operations in the Net Stable Funding Ratio | Consolidated | Liquidity risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d444.htm) |
| 71 | 2018-07-05 | Global systemically important banks: revised assessment methodology and the higher loss absorbency requirement | Consolidated | Macroprudential / systemic importance | [BIS/BCBS](https://www.bis.org/bcbs/publ/d445.htm) |
| 72 | 2018-08-30 | Pillar 3 disclosure requirements - regulatory treatment of accounting provisions | Consolidated | Accounting and auditing, Credit risk, Disclosure | [BIS/BCBS](https://www.bis.org/bcbs/publ/d446.htm) |
| 73 | 2018-12-11 | Pillar 3 disclosure requirements - updated framework | Consolidated | Disclosure | [BIS/BCBS](https://www.bis.org/bcbs/publ/d455.htm) |
| 74 | 2019-01-14 | Minimum capital requirements for market risk | Consolidated | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d457.htm) |
| 75 | 2019-06-26 | Leverage ratio treatment of client cleared derivatives | Consolidated | Leverage ratio | [BIS/BCBS](https://www.bis.org/bcbs/publ/d467.htm) |
| 76 | 2019-06-26 | Revisions to leverage ratio disclosure requirements | Consolidated | Disclosure, Leverage ratio | [BIS/BCBS](https://www.bis.org/bcbs/publ/d468.htm) |
| 77 | 2019-07-23 | Margin requirements for non-centrally cleared derivatives | Superseded | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d475.htm) |
| 78 | 2019-12-16 | Launch of the consolidated Basel Framework | Consolidated | Operational risk, Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d491.htm) |
| 79 | 2020-04-03 | Margin requirements for non-centrally cleared derivatives | Consolidated | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d499.htm) |
| 80 | 2020-07-08 | Targeted revisions to the credit valuation adjustment risk framework | Consolidated | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d507.htm) |
| 81 | 2020-11-26 | Capital treatment of securitisations of non-performing loans | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d511.htm) |
| 82 | 2021-07-01 | Technical amendments - Minimum haircut floors for securities financing transactions | Consolidated | Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d520.htm) |
| 83 | 2021-11-09 | G-SIB assessment methodology review process - technical amendment finalisation | Consolidated | Macroprudential / systemic importance | [BIS/BCBS](https://www.bis.org/bcbs/publ/d527.htm) |
| 84 | 2021-11-11 | Revisions to market risk disclosure requirements | Consolidated | Market risk, Disclosure | [BIS/BCBS](https://www.bis.org/bcbs/publ/d529.htm) |
| 85 | 2021-11-11 | Voluntary disclosure of sovereign exposures | Consolidated | Market risk, Credit risk, Disclosure | [BIS/BCBS](https://www.bis.org/bcbs/publ/d528.htm) |
| 86 | 2022-12-16 | Prudential treatment of cryptoasset exposures | Consolidated | Operational risk, Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d545.htm) |
| 87 | 2023-11-08 | Finalisation of various technical amendments | Consolidated | Operational risk, Disclosure, Macroprudential / systemic importance | [BIS/BCBS](https://www.bis.org/bcbs/publ/d557.htm) |
| 88 | 2024-04-25 | Core Principles for effective banking supervision | Consolidated | Basel core principles | [BIS/BCBS](https://www.bis.org/bcbs/publ/d573.htm) |
| 89 | 2024-07-16 | Recalibration of shocks for interest rate risk in the banking book | Consolidated | Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d578.htm) |
| 90 | 2024-07-17 | Cryptoasset standard amendments | Consolidated | Operational risk, Market risk, Liquidity risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d579.htm) |
| 91 | 2024-07-17 | Disclosure of cryptoasset exposures | Consolidated | Disclosure | [BIS/BCBS](https://www.bis.org/bcbs/publ/d580.htm) |
| 92 | 2024-11-27 | Finalisation of various technical amendments | Consolidated | Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d583.htm) |
| 93 | 2025-10-28 | Technical Amendment - Hedging of counterparty credit risk exposures | Consolidated | Market risk, Credit risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d600.htm) |
| 94 | 2026-03-23 | Finalisation of technical amendment and frequently asked questions | Consolidated | Operational risk, Market risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d610.htm) |

## 6. Basel I → Final Basel III 원문 계보 및 최근 개정

현행 적용 근거는 Section 2의 통합 Framework다. 아래 문서는 제도 발전·문단 매핑·변경이력 확인용이며, `Superseded` 문서를 현행 산출 근거로 사용해서는 안 된다.

| Date | Package | Official title | Framework status | Official source |
|---|---|---|---|---|
| 1988-07-15 | Basel I | International convergence of capital measurement and capital standards | Superseded | [BIS/BCBS](https://www.bis.org/publ/bcbs04a.htm) |
| 1996-01-04 | Basel I amendment | Amendment to the capital accord to incorporate market risks | Superseded | [BIS/BCBS](https://www.bis.org/publ/bcbs24.htm) |
| 2006-06-30 | Basel II | International Convergence of Capital Measurement and Capital Standards: A Revised Framework – Comprehensive Version | Integrated | [BIS/BCBS](https://www.bis.org/publ/bcbs128.htm) |
| 2009-07-13 | Basel 2.5 | Enhancements to the Basel II framework | Integrated | [BIS/BCBS](https://www.bis.org/publ/bcbs157.htm) |
| 2009-07-13 | Basel 2.5 | Revisions to the Basel II market risk framework | Superseded | [BIS/BCBS](https://www.bis.org/publ/bcbs158.htm) |
| 2009-07-13 | Basel 2.5 | Guidelines for computing capital for incremental risk in the trading book | Superseded | [BIS/BCBS](https://www.bis.org/publ/bcbs159.htm) |
| 2011-06-01 | Initial Basel III | A global regulatory framework for more resilient banks and banking systems – revised June 2011 | Integrated | [BIS/BCBS](https://www.bis.org/publ/bcbs189.htm) |
| 2013-01-07 | Basel III | The Liquidity Coverage Ratio and liquidity risk monitoring tools | Integrated | [BIS/BCBS](https://www.bis.org/publ/bcbs238.htm) |
| 2014-01-12 | Basel III | Basel III leverage ratio framework and disclosure requirements | Integrated | [BIS/BCBS](https://www.bis.org/publ/bcbs270.htm) |
| 2014-03-31 | Basel III | The standardised approach for measuring counterparty credit risk exposures | Integrated | [BIS/BCBS](https://www.bis.org/publ/bcbs279.htm) |
| 2014-04-15 | Basel III | Supervisory framework for measuring and controlling large exposures | Integrated | [BIS/BCBS](https://www.bis.org/publ/bcbs283.htm) |
| 2014-10-31 | Basel III | The net stable funding ratio | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d295.htm) |
| 2014-12-11 | Basel III | Revisions to the securitisation framework | Superseded / revised | [BIS/BCBS](https://www.bis.org/bcbs/publ/d303.htm) |
| 2016-01-14 | FRTB | Minimum capital requirements for market risk | Superseded | [BIS/BCBS](https://www.bis.org/bcbs/publ/d352.htm) |
| 2016-04-21 | Basel III | Interest rate risk in the banking book | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d368.htm) |
| 2017-03-29 | Pillar 3 | Pillar 3 disclosure requirements – consolidated and enhanced framework | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d400.htm) |
| 2017-12-07 | Final Basel III | Basel III: Finalising post-crisis reforms | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d424.htm) |
| 2018-12-11 | Pillar 3 | Pillar 3 disclosure requirements – updated framework | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d455.htm) |
| 2019-01-14 | FRTB | Minimum capital requirements for market risk | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d457.htm) |
| 2019-12-15 | Consolidation | Launch of the consolidated Basel Framework | Current architecture | [BIS/BCBS](https://www.bis.org/bcbs/publ/d491.htm) |
| 2020-07-08 | CVA | Targeted revisions to the credit valuation adjustment risk framework | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d507.htm) |
| 2022-12-16 | Cryptoassets | Prudential treatment of cryptoasset exposures | Integrated / amended | [BIS/BCBS](https://www.bis.org/bcbs/publ/d545.htm) |
| 2024-04-25 | BCP | Core Principles for effective banking supervision | Integrated | [BIS/BCBS](https://www.bis.org/bcbs/publ/d573.htm) |
| 2024-07-16 | IRRBB | Recalibration of shocks for interest rate risk in the banking book | Integrated; effective 2026 | [BIS/BCBS](https://www.bis.org/bcbs/publ/d578.htm) |
| 2024-07-17 | Cryptoassets | Cryptoasset standard amendments | Integrated; effective 2026 | [BIS/BCBS](https://www.bis.org/bcbs/publ/d579.htm) |
| 2024-07-17 | Cryptoassets | Disclosure of cryptoasset exposures | Integrated; effective 2026 | [BIS/BCBS](https://www.bis.org/bcbs/publ/d580.htm) |
| 2025-10-28 | CCR | Hedging of counterparty credit risk exposures | Forthcoming; effective 2028-11-01 | [BIS/BCBS](https://www.bis.org/bcbs/publ/d600.htm) |
| 2026-03-23 | Technical amendment | Finalisation of technical amendment and frequently asked questions | Integrated / forthcoming | [BIS/BCBS](https://www.bis.org/bcbs/publ/d610.htm) |

## 7. Framework 밖의 주요 BCBS 원칙·지침

아래 자료는 자본·유동성 산식 Chapter와 성격이 다른 원칙 또는 감독지침이다. 'Basel Framework 전수' 건수에는 포함하지 않았으나, 은행 리스크관리·검증·감독 대응에는 함께 적용 여부를 판단해야 한다.

| Domain | Official title | Official source |
|---|---|---|
| Risk data | Principles for effective risk data aggregation and risk reporting (BCBS 239) | [BIS/BCBS](https://www.bis.org/publ/bcbs239.htm) |
| Stress testing | Stress testing principles | [BIS/BCBS](https://www.bis.org/bcbs/publ/d450.htm) |
| Governance | Corporate governance principles for banks | [BIS/BCBS](https://www.bis.org/bcbs/publ/d328.htm) |
| Operational risk | Revisions to the principles for the sound management of operational risk | [BIS/BCBS](https://www.bis.org/bcbs/publ/d515.htm) |
| Operational resilience | Principles for operational resilience | [BIS/BCBS](https://www.bis.org/bcbs/publ/d516.htm) |
| Climate risk | Principles for the effective management and supervision of climate-related financial risks | [BIS/BCBS](https://www.bis.org/bcbs/publ/d532.htm) |
| Liquidity risk | Principles for Sound Liquidity Risk Management and Supervision | [BIS/BCBS](https://www.bis.org/publ/bcbs144.htm) |
| FX settlement | Supervisory guidance for managing risks associated with the settlement of foreign exchange transactions | [BIS/BCBS](https://www.bis.org/publ/bcbs241.htm) |

## 8. 첨부 2016년 교육자료의 누락 방지 매핑

첨부자료는 주제 탐색에만 사용했고 규범적 근거·수치·문구는 인용하지 않았다. 자료 중 유동성·금리리스크 PDF 2개는 바이트 단위 중복이며, 암호화된 PPTX 1개는 내용 확인 대상에서 제외했다.

| 교육자료 주제 | 현행 공식 원문 | 검증상 유의점 |
|---|---|---|
| 기업·개인 신용평가모형, PD 및 등급체계 | CRE30–CRE36; SRP model risk expectations | 방법론 참고만; 2017 final reforms 이후 IRB 제한·input floor 재대조 |
| LGD 측정 | CRE32, CRE36 | downturn LGD, MoC, default/workout, input floor 현행본 재대조 |
| 신용위험 SA/IRB RWA | CAP, RBC, CRE | 2016년 이전 수치·위험가중치 사용 금지 |
| 거래상대방·CVA·CCP | CRE51–CRE56; MAR50 | CEM·구 CVA 체계와 현행 SA-CCR/BA-CVA/SA-CVA 구분 |
| FRTB | RBC25; MAR11–MAR99 | 2016 초판이 아니라 2019 최종 및 후속 통합본 적용 |
| 유동성·금리리스크 | LCR; NSF; SRP31; SRP98 | 2024 IRRBB shock recalibration 및 2026 시행본 반영 |
| 신용편중·거액익스포저 | LEX; SRP concentration risk | single-name LEX와 산업·상관 편중의 Pillar 2 성격 분리 |
| 통합위기상황분석 | SRP; companion Stress testing principles | Basel Framework 조항과 별도 BCBS 원칙을 함께 확인 |
| 외환결제리스크 | Companion FX settlement guidance; LCR/OPE/SRP | Basel Framework 본문과 별도 지침 구분 |
| Pillar 3 및 운영위험 SMA | DIS; OPE | 첨부 교육자료에서 사실상 누락되어 공식 원문으로 보완 |

## 9. 검증·감사 사용 체크리스트

| 점검항목 | 확인내용 | 증빙 | 미충족 시 조치 |
|---|---|---|---|
| 버전 고정 | Chapter code만이 아니라 inforce·published·조회기준일을 고정 | 본 원장의 URL 및 실행/보고 기준일 | 현행본 재조회 후 재산출 |
| 국내 이행 | BCBS 기준이 국내 법규·감독규정·시행세칙에 전환됐는지 확인 | 금융위·금감원 최신 원문 및 개정 부칙 | 차이분석과 국내 적용 예외 문서화 |
| 데이터 라인리지 | 규제 문단 → 요건 → 데이터 항목 → 산식 → 보고서 셀 연결 | RDM 사전, 매핑표, ETL 로그 | 누락·중복 매핑 보완 및 재처리 |
| 산식 독립검산 | 표준방법·IRB·시장·운영·유동성·레버리지 산식을 별도 엔진으로 재계산 | 테스트 케이스, 대사표, 허용오차 | 원인분석 후 승인 전 반영 금지 |
| 변경관리 | current와 forthcoming을 분리하고 시행 전 영향평가 | 변경요청서, 영향분석, 4-Eyes 승인 | 운영 반영 보류 |
| 증빙 보존 | 원문 URL·다운로드일·hash·버전·승인 이력 보존 | evidence ledger | 원문 재확보 및 해시 재대사 |
| 변경 탐지 | 전체 PDF는 생성시각 때문에 내용 불변이어도 byte hash가 바뀔 수 있으므로 chapter/version manifest를 비교 | chapter code·inforce·published·updated diff | 변경 chapter만 내용·산식 영향분석 |

## 10. 한계 및 추가 검증 필요사항

- 이 소스북은 BCBS 국제기준의 원문 위치·버전을 정리한 것이며 한국 법령·감독규정의 효력 판단을 대체하지 않는다.
- 장래 시행 버전은 BCBS 기준일이며 관할별 국내 시행일·경과조치가 다를 수 있다.
- consultative document, FAQ-only publication, RCAP 평가보고서, Basel III monitoring report 및 모든 sound practice를 전수 수록한 출판물 아카이브는 아니다.
- BIS 사이트가 이후 개정되면 표시와 메타데이터가 달라질 수 있으므로 원문 PDF의 다운로드일·SHA-256을 별도 보존하는 것이 적절하다. 다만 SHA-256은 보관본의 byte 무결성 증빙이지 규제 내용 변경 탐지 수단이 아니다. 전체 PDF에는 생성시각이 포함돼 내용이 같아도 hash가 달라질 수 있다.
- 이 문서는 BIS 공식 사이트의 원천 metadata를 기준으로 만들었으나 해당 data endpoint는 문서화된 공개 API가 아니므로 향후 구조가 변경될 수 있다.
- 보고서에는 'BCBS 원문 기준'과 '국내 시행규정 기준'을 분리하고, 차이를 예외사항으로 명시해야 한다.

### 누락 가능 항목

BCBS가 기준일 이후 공표·정정한 문서, 각국 이행규정, 비(非)Framework sound practices 전체, 표준별 별도 Excel disclosure template의 변경이력은 별도 갱신 대상이다.

### 반대 시각 또는 보수적 해석

'모든 바젤 기준'을 BCBS의 모든 standards·guidelines·sound practices·consultations·implementation reports까지 포함하는 의미로 해석하면 본 범위보다 훨씬 넓다. 본 문서는 BIS가 공식적으로 'full set of standards'라고 정의하는 통합 Basel Framework를 완전성 모집단으로 삼았다.

### 추가 검증 필요사항

실제 시스템 요건정의나 검증보고서에 사용하기 전에는 (1) 국내 최신 시행세칙 문단 매핑, (2) 장래 시행본 영향분석, (3) 원문 PDF hash와 보관 위치, (4) FAQ 포함 여부, (5) 공시 Excel template 버전을 독립 확인해야 한다.

