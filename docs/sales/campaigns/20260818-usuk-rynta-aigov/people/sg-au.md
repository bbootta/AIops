# 인물 특정: SG/AU 세그먼트 (8개 기관)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/people/sg-au.md`
> 기준일: 2026-09-14 / 작성: prospect-researcher / 검토: sales-lead (대기)
> 방법: 공개 출처 한정(보도자료, 뉴스, 공개 LinkedIn 프로필, 기업 디렉토리). 기관 공식 리더십 페이지(bendigoadelaide.com.au, boq.com.au, judo.bank, gxs.com.sg, amp.com.au, trustbank.sg 계열)는 이 환경의 네트워크 프록시에 전건 차단되어 접근 불가했고, 해당 기관은 2차 출처로 대체 후 "원문 대조 필요"를 남겼다.

## 공통 규칙

- **email 필드: 전 인물 "[PO/도구]".** 이메일 주소는 추정·생성·기재하지 않았다.
- AU 레코드는 발송 전 주소별 공개 게시 증빙(Spam Act conspicuous publication)이 별도로 필요하다. 이 작업에서는 확인하지 않았다(PO 단계). 공식 페이지가 전부 프록시 차단이라 임원 연락처 공개 게시를 우연히 확인한 사례도 없다.
- 페르소나 매핑: CRO=EB, Head of Model Risk/Validation=champion, AI Governance/Responsible AI 리더=champion, CDO/CDAO/CAIO=tech_buyer. 이 세그먼트는 기관 규모가 작아 CTO/CIO/COO(기술 총괄)를 tech_buyer로, 로컬 CEO·부문 총괄을 EB로 매핑했다.
- 적합도: 강 = 복수 출처 또는 1차 출처(보도자료·공시)로 현직·직함 일치, 중 = 2차 출처 단수 또는 공식 원문 미대조, 후보 = 페르소나 인접이나 직무 소유 불명.

---

## 1. Bendigo and Adelaide Bank (AU-B1)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| BEN-P1 | Kerrie Noonan | Chief Risk Officer | EB | 2024-12 | https://www.bloomberg.com/profile/person/24434023 , https://www.bendigobank.com.au/media/bendigo-bank-announces-changes-and-additions-to-executive-team/ (2026-09-14) | 강 |
| BEN-P2 | Kieran O'Meara | Chief Technology Officer | tech_buyer | 2025-04-01 | https://www.bendigobank.com.au/media/bendigo-bank-appoints-kieran-omeara-as-chief-technology-officer/ , https://www.brokerdaily.au/lender/19918-bendigo-bank-appoints-new-chief-technology-officer (2026-09-14) | 강 |
| BEN-P3 | Xavier Shay | Chief Digital Officer (Up CEO 겸직) | tech_buyer | 2024-09 | https://www.itnews.com.au/news/bendigo-and-adelaide-bank-appoints-a-digital-chief-611280 , https://ami.org.au/knowledge-hub/bendigo-bank-names-chief-marketing-customer-and-digital-officers-amidst-executive-shakeup/ (2026-09-14) | 중 |

- BEN-P1: 2026-08-18 APRA 라이선스 조건(비재무 리스크·독립 검토자 요건)의 이행을 소유하는 자리. 30년+ 은행권 리스크 경력. 이 계정 EB 1순위.
- BEN-P2: 전 Telstra Group CIO & Head of Software Engineering & IT. Google Cloud AI(금융범죄 모델)·Infosys 프로그램의 기술 소유자로 추정.
- BEN-P3: 디지털 채널·Up 브랜드 중심이라 AI 거버넌스 직접 소유는 불명. 후순위 tech_buyer.
- 미확인: Head of Model Risk / Model Validation. 공개 출처에서 특정 실패. PO용 Sales Navigator 쿼리: `company:"Bendigo and Adelaide Bank" AND title:("Head of Model Risk" OR "Model Validation" OR "Model Risk" OR "Head of Risk Analytics")`
- 재확인 필요: 공식 임원 페이지(bendigoadelaide.com.au/about-us/our-executive/) 프록시 차단으로 원문 대조 필요.

## 2. iFAST Corporation (SG-S1)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| IFA-P1 | Eddie Pang | Group Chief Risk Officer | EB | 2022-02-01 (2019년 SG CRO로 합류) | https://theedgemalaysia.com/article/ifast-group-set-have-new-chief-financial-officer-and-chief-risk-officer-feb-1 , https://www.ifastcorp.com/ifastcorp/aboutus/management-board.tpl (2026-09-14) | 강 |
| IFA-P2 | Tan Tia Hong | Group Chief Operating Officer | tech_buyer | 2026-02-28 | https://www.marketscreener.com/news/ifast-corporation-ltd-announces-appointment-of-tan-tia-hong-as-group-chief-operating-officer-effec-ce7e5dd3d088f324 (2026-09-14) | 강 |

- IFA-P1: 전 MAS 은행부 Assistant Director·PwC 출신. "AI 생산성으로 2027년부터 마진 개선" 가이던스의 리스크 방어 책임자.
- IFA-P2: 2010년 IT 프로그래머로 입사해 2018년부터 그룹 IT(개발·인프라·보안) 총괄. 별도 Group CTO 직책이 없어 기술 구매 접점은 이 자리로 판단. 2026-02-28 신규 부임 직후라 어젠다 설정기.
- 미확인: Head of Model Risk / AI Governance 리더. PO용 쿼리: `company:"iFAST" AND title:("Model Risk" OR "AI Governance" OR "Responsible AI" OR "Head of Data Science")`
- 메모: Chairman & CEO Lim Chung Chun은 페르소나 외(창업자 CEO)라 미편입. 필요시 PO 판단.

## 3. Moomoo Singapore (SG-S2)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| MOO-P1 | Jeyson Ng | Chief Executive Officer, Moomoo Singapore | EB | 2026-06 (발표 2026-06-05) | https://www.prnewswire.com/apac/news-releases/moomoo-singapore-announces-jeyson-ng-as-chief-executive-officer-302792494.html , https://fintechnews.sg/132680/wealthtech/moomoo-singapore-ceo/ (2026-09-14) | 강 |
| MOO-P2 | Benson Chua | Head of Compliance (Moomoo, SG 소재) | champion | 미상 | https://sg.linkedin.com/in/benson-chua-dip-rc-9a0587118 (공개 프로필, 2026-09-14) | 중 |

- MOO-P1: 신임 CEO(전임 Country Head Echo Zhao 승계). 부임 3개월차로 기술·투자자 교육 확장을 공언, MooFest AI 3종·에이전틱 API의 통제 어젠다를 정할 위치. 조직 규모상 EB 겸 로컬 결정권자.
- MOO-P2: 공개 LinkedIn 단일 출처. MAS AIRG 대응 실무(CMS 인가사 컴플라이언스) 접점 가설. 직함 관할 범위(SG 법인 한정 여부) 재확인 필요.
- **구 데이터 폐기 경고: 전 CEO Gavin Chia는 2026-05 Longbridge Southeast Asia CEO로 이직 확인** (https://www.prnewswire.com/apac/news-releases/longbridge-names-gavin-chia-as-singapore-and-regional-ceo-southeast-asia-marking-a-new-chapter-for-the-ai-powered-digital-brokerage-302767964.html). 재활용 금지.
- 미확인: Head of Risk / CRO (SG 법인). PO용 쿼리: `company:"Moomoo" AND geography:"Singapore" AND title:("Head of Risk" OR "Chief Risk Officer" OR "Risk Management")`

## 4. Bank of Queensland (AU-B2)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| BOQ-P1 | Rachel Stock | Chief Risk Officer | EB | 2024-02-01 (CRO Designate로 합류 후 David Watts 승계) | https://www.boq.com.au/About-us/media-centre/media-releases/2024/two-new-executives , https://www.financialstandard.com.au/news/boq-bolsters-executive-team-179780018 (2026-09-14) | 강 |
| BOQ-P2 | Craig Ryman | Chief Information Officer, BOQ Group | tech_buyer | 2020-07 | https://www.cio.com/article/193581/craig-ryman-named-new-bank-of-queensland-tech-boss.html , https://au.linkedin.com/in/craig-ryman-b666284 (2026-09-14) | 강 |
| BOQ-P3 | Ben Beeching | Chief Data Officer | tech_buyer | 미상 | https://www.theofficialboard.com/biography/ben-beeching-27g57 (2026-09-14) | 후보 |

- BOQ-P1: 단일 실시간 대출 엔진·"AI-led verification" 확대의 리스크 소유자. 자동 승인 확대 국면의 EB.
- BOQ-P2: 전 AMP CIO/COO. 대출 엔진 통합·Temenos·Copilot 등 기술 전환 어젠다 소유. AI-led verification 설계의 기술측 접점.
- BOQ-P3: 2차 디렉토리(theofficialboard) 단일 출처라 현직·직함 재확인 필요. 확인되면 데이터·AI 챔피언 후보로 승격.
- 미확인: Head of Model Risk. PO용 쿼리: `company:"BOQ Group" OR "Bank of Queensland" AND title:("Head of Model Risk" OR "Model Validation" OR "Credit Risk Analytics")`
- 맥락: 신임 CEO Rod Finch 2026-03-01 부임(https://www.bankingday.com/rod-finch-appointed-boq-ceo). 카피의 타이밍 근거로 활용 가능.
- 재확인 필요: 공식 임원 페이지(boq.com.au/about-us/executive-team) 프록시 차단으로 원문 대조 필요.

## 5. GXS Bank (SG-B1)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| GXS-P1 | Vincent Mok | Group Chief Risk Officer | EB | 미상 (전 GX Bank Berhad CRO에서 이동) | https://www.gxs.com.sg/leadership (검색 결과로 확인, 원문 차단) , https://www.linkedin.com/in/vincent-mok-1992185a/ (2026-09-14) | 강 |

- GXS-P1: 25년+ 리스크 경력(CIMB·Alliance Bank 소비자신용). 대출 +323% 성장 포트폴리오와 AIRG 대응의 리스크 소유자.
- **구 데이터 폐기 경고: Chief Data Officer Geraldine Wong은 2026-02 말 퇴사 확인** (https://fintechnews.sg/124712/digital-banking-news-singapore/gxs-bank-leadership/ , Grab 금융서비스 통합 심화 국면. Group Head of Business Banking Vishal Shah도 동시 퇴사). 재활용 금지.
- 미확인 1: CDO 후임 또는 Head of Data & AI. 후임 보도 없음. PO용 쿼리: `company:"GXS Bank" AND title:("Chief Data Officer" OR "Head of Data" OR "Head of AI" OR "Data Science")`. Grab 그룹 통합으로 데이터·AI 기능이 Grab 측으로 이관됐을 가능성 있음(그 경우 관할·계정 처리 PO 판단 필요).
- 미확인 2: Head of Model Risk / Model Validation. PO용 쿼리: `company:"GXS Bank" AND title:("Model Risk" OR "Model Validation")`
- 재확인 필요: gxs.com.sg/leadership 원문 대조(프록시 차단).

## 6. Trust Bank (SG-B3)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| TRU-P1 | Srinivas Patil | Chief Technology Officer (CTO & Head of Applied Engineering) | tech_buyer | 2021-09 | https://www.linkedin.com/in/srinivas-patil-045b3421/ , https://theorg.com/org/trust-bank/org-chart/srinivas-patil (2026-09-14) | 중 |

- TRU-P1: 창립기부터 CTO. "AI·자동화 주도 효율" 흑자 서사의 기술 실행 소유자. 2차 출처 복수 일치이나 공식 원문 미대조라 중.
- **구 데이터 폐기 경고: 창립 CRO Lalit Lohia는 Mashreq Head of Retail Credit Risk로 이직 확인** (Mashreq 공식 Instagram 환영 게시물 https://www.instagram.com/p/DWyTxMEFahQ/ , "Founding CRO of Trust Bank Singapore"로 과거형 소개, 게시 시점 2026년 추정, 2026-09-14 확인). theorg 등 디렉토리에는 아직 CRO로 남아 있으나 재활용 금지.
- 미확인: CRO 후임. 승계 보도 없음. PO용 쿼리: `company:"Trust Bank Singapore" AND title:("Chief Risk Officer" OR "Head of Risk" OR "Risk Management" seniority:VP+)`
- 메모: CEO Dwaipayan Sadhu, COO James Ong은 페르소나 외. 모회사 Standard Chartered가 UK 부서접근-PO승인 목록이므로 이 계정의 그룹 관계 처리는 기존 리서치 파일(sg-b3) §1 조건 그대로 PO 판단 대기.

## 7. Judo Bank (AU-B3)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| JUD-P1 | Renee Roberts | Chief Risk Officer | EB | 2024-09-06 | https://www.capitalbrief.com/briefing/judo-bank-gets-new-coo-chief-risk-officer-f62b17b0-a6d0-402e-9aa2-6343993c97f8/ (2026-09-14) | 강 |
| JUD-P2 | Nathalie Moss | Chief Technology Officer | tech_buyer | 2026-04 | https://www.itnews.com.au/news/judo-bank-hires-ex-bendigo-cio-625008 (2026-09-14) | 강 |

- JUD-P1: 전 APRA Executive Director (Banking). 감독당국 출신 CRO라 APRA AI 서한·CPS 230 언어가 그대로 통하는 EB. AI 크레딧 메모 자동화의 리스크 소유자.
- JUD-P2: 전 Bendigo and Adelaide Bank 임시 CIO. 2026-04 부임, mid-2024 이후 처음 부활한 CTO 직책. AWS AI 통합(콜 요약·크레딧 메모)의 실행 소유자로 추정. 부임 5개월차 어젠다 설정기.
- 미확인: Head of Credit Risk / Model Risk. PO용 쿼리: `company:"Judo Bank" AND title:("Head of Credit Risk" OR "Model Risk" OR "Credit Analytics")`
- 재확인 필요: judo.bank 거버넌스 페이지 원문 대조(프록시 차단). 2026-08-18 FY26 발표 이후 임원 변동 여부는 미점검.

## 8. AMP Bank (AU-B4)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| AMP-P1 | Sean O'Malley | Group Executive, AMP Bank | EB | 2021-09 | https://theorg.com/org/amp-ltd/org-chart/sean-omalley , https://thefintechtimes.com/amp-unveils-new-bank-powered-by-engine-by-starling-to-support-australias-underserved-smes/sean-omalley-group-executive-at-amp-bank/ (2026-09-14) | 강 |
| AMP-P2 | David Cullen | Chief Risk & Legal Officer (AMP Limited 그룹) | EB | 2025-04 | https://www.amp.com.au/about-amp/what-we-do/board-and-management (검색 결과로 확인, 원문 차단) (2026-09-14) | 중 |
| AMP-P3 | Kavita Mistry | Chief Technology Officer (AMP Limited 그룹) | tech_buyer | 2024-01 | https://www.amp.com.au/about-amp/what-we-do/board-and-management (검색 결과로 확인, 원문 차단) , https://www.globaldata.com/company-profile/amp-ltd/executives/ (2026-09-14) | 중 |

- AMP-P1: AMP Bank GO 스케일업(예금 A$1.7bn·고객 2배)의 사업 소유자. 은행 부문 CPS 230 어젠다의 실질 EB.
- AMP-P2: 그룹 리스크·법무·거버넌스 통합 소유(전 Group General Counsel). 은행 부문 전속 CRO가 아니라 법무 겸직 그룹 임원이라는 점에서 중. 은행 부문 CRO는 별도 미확인.
- AMP-P3: AustralianSuper·ANZ 출신, 데이터·AI 전문성 명시된 그룹 CTO. GO의 기술 스택(Engine by Starling) 위 어슈어런스 논의의 기술측 접점.
- 미확인: AMP Bank 부문 CRO / Head of Operational Risk. PO용 쿼리: `company:"AMP" AND title:("Chief Risk Officer" OR "Head of Risk" OR "Operational Risk") AND keyword:"Bank"` (주의: 검색 중 확인된 Michelle James는 "CRO, Technology and Operations"라는 하위 기능 직책으로 표기 출처가 디렉토리뿐이라 미편입, PO 재확인 대상)
- 재확인 필요: amp.com.au board-and-management 원문 대조(프록시 차단). 2026-03 신임 그룹 CEO Blair Vernon 체제 개편으로 임원 변동 가능성 있음.

---

## 요약

- **특정 완료: 17명** (BEN 3, IFA 2, MOO 2, BOQ 3, GXS 1, TRU 1, JUD 2, AMP 3). 적합도 강 11, 중 5, 후보 1.
- 기관당 2명 이상 충족: 6/8. **미달 2건: GXS(1명), Trust Bank(1명).** 두 곳 모두 핵심 직책 이탈(GXS CDO, Trust CRO)이 원인이며 후임 미보도.
- **미확인 직책: 9건** (기관별 모델리스크/AI거버넌스 계열 7건 + GXS CDO 후임 + Trust Bank CRO 후임). 각 섹션에 PO용 Sales Navigator 쿼리 기재. 추측으로 채우지 않았다.
- **전직 확인(재활용 금지) 3건:** Gavin Chia(Moomoo → Longbridge, 2026-05), Geraldine Wong(GXS 퇴사, 2026-02), Lalit Lohia(Trust Bank → Mashreq).
- **재확인 필요:** (a) AU 4개 기관 + GXS + AMP 공식 리더십 페이지 원문 대조(프록시 차단으로 전건 2차 출처 의존), (b) BOQ-P3 Ben Beeching·MOO-P2 Benson Chua·TRU-P1 Srinivas Patil의 현직·직함(단수 또는 디렉토리 출처), (c) AMP 2026-03 CEO 교체 이후 임원 변동, (d) Judo FY26 발표(2026-08-18) 이후 임원 변동.
- email 필드: 전건 "[PO/도구]". AU 주소별 공개 게시 증빙(Spam Act)은 PO 단계 미착수. G9 필수 필드(수신 근거, SG/AU 프레임)는 sales-compliance-officer 프레임 확정 대기.
