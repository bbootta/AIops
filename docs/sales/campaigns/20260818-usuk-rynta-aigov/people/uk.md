# RYNTA 캠페인 인물 특정: UK 16개 기관

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/people/uk.md`
> 기준일(확인일): 2026-09-14 · 작성: prospect-researcher
> 방법: 공개 출처(기관 공식 리더십 페이지, 보도자료, 뉴스, 규제기관 공표, 공개 LinkedIn 프로필, 공개 임원 디렉토리)만 웹 검색으로 조회해 타깃 직책의 실제 인물을 특정하고 현직 여부를 재확인했다. 비공개 정보 수집 없음.
>
> **이메일: 전 레코드 email 필드는 "[PO/도구]"다.** 이 문서는 어떤 형태의 이메일 주소도 추정·생성·기재하지 않는다(list-build-spec §1.2).
> **jurisdiction은 근무지 기준(KB09 §8.2).** UK 근무지가 출처에서 확인된 경우 메모에 표기. 관할 불명·비UK 인물은 회피 등급으로 태깅하고 편입하지 않는다(G2).
> 페르소나: EB = CRO/리스크총괄, champion = Model Risk/Validation/AI Governance 리더, tech_buyer = CDO/CDAO/CAIO/CIO.
> 적합도: 강 = 공식 페이지 또는 복수 독립 출처로 현직 확인 / 중 = 신뢰 출처 1~2개, 발송 전 재확인 권고 / 후보 = 단일·간접 출처, 재확인 필수.
>
> 제약 기록: 본 세션에서 기관 공식 도메인·다수 뉴스 도메인의 직접 fetch가 네트워크에서 차단되어, 확인은 검색 결과(스니펫) 기반이다. "재확인 필요" 표기 항목은 PO가 발송 전 LinkedIn Sales Navigator 또는 기관 페이지에서 현직 재확인해야 한다.

---

## 1. Yorkshire Building Society (UK-S3)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| YBS-P1 | Richard Bowles | Chief Risk Officer | EB | 2024-02 | https://www.yorkshirepost.co.uk/business/yorkshire-building-society-appoints-new-chief-risk-officer-4514593 · https://www.ybs.co.uk/your-society/inside-your-society/execteam (2026-09-14) | 강 |
| YBS-P2 | Rebecca Fitzgerald | Director of Data & AI (DataIQ 표기: Director of Architecture, Data and AI) | tech_buyer | 미확인 (재임 3년+ 보도) | https://www.dataiq.global/dataiq100/rebecca-fitzgerald-director-of-architecture-data-and-ai-yorkshire-building-society/ · https://uk.linkedin.com/in/rebecca-fitzgerald-3a42b89b (2026-09-14) | 강 |

- YBS-P1: 전 Coventry Building Society CRO. 에이전틱 AI 언더라이팅(Covecta)·AI 에이전트 3종의 리스크 통제 증명 책임자로 캠페인 가설의 EB 정확 일치. 근무지 UK(요크셔 기반 기관 임원, Yorkshire Post 보도).
- YBS-P2: 100개 AI 유스케이스·Data and AI Academy 확산의 실행 소유자. LinkedIn 프로필이 uk.linkedin.com으로 UK 근무지 표시.
- 미확인: Head of Model Risk 실명. Model Risk Oversight 기능 실재는 채용공고로 확인(https://uk.linkedin.com/jobs/view/model-risk-oversight-lead-manager-model-validation-at-yorkshire-building-society-4197313397). Sales Navigator 쿼리: `company:("Yorkshire Building Society") AND ("Head of Model Risk" OR "Model Risk Oversight" OR "Model Validation") AND location:("United Kingdom")`

## 2. Nationwide Building Society (UK-S1)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| NBS-P1 | Gavin Smyth | Chief Risk Officer | EB | 2020-11 (2017 입사) | https://www.bloomberg.com/profile/person/22873067 · https://www.nationwide.co.uk/about-us/governance-reports-and-results/board-and-executive-committee (2026-09-14) | 강 |
| NBS-P2 | Matthew Jones | Head of Decision Science (출처별 표기 상이: "Head of Risk Decision & Data Science", "head of decision science and analytical innovation") | champion | 미확인 | https://realworlddatascience.net/people-paths/posts/2024/03/21/mjones-interview.html · https://www.bankofengland.co.uk/minutes/2026/february/ai-consortium-minutes-9-february-2026 · https://www.linkedin.com/in/matthew-jones-1b853b13/ (2026-09-14) | 중 |
| NBS-P3 | Sri Kanisapakkam | Chief Data and Analytics Officer | tech_buyer | 2023-06 | https://www.dataiq.global/dataiq100/sri-kanisapakkam-chief-data-officer-nationwide-building-society/ (2026-09-14) | 강 |

- NBS-P1: 계정 시그널(Virgin Money 모델 estate 통합)의 총괄 책임. "신임 임원" 아님(리서치 파일 §2 정직 표기 유지). 근무지 UK(런던, LinkedIn 지역 표기).
- NBS-P2: BoE·FCA AI Consortium의 Nationwide 측 멤버로 2026-02-09 회의록에 실명 기재. 계정 시그널과 직접 연결되는 챔피언. 정확한 현재 직함 표기는 출처 간 상이하므로 발송 전 재확인 필요.
- NBS-P3: 전 TSB·Barclays. 그룹 데이터·분석 총괄로 tech_buyer 정확 일치.
- 미확인: Group Director of Modelling(리서치 파일 §3 언급 직책) 실명, Head of AI Governance 실명. Sales Navigator 쿼리: `company:("Nationwide Building Society") AND ("Director of Modelling" OR "Head of Model Risk" OR "Model Validation" OR "AI Governance" OR "Responsible AI") AND location:("United Kingdom")`

## 3. OSB Group (UK-B4)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| OSB-P1 | Hasan Kazmi | Group Chief Risk Officer | EB | 2021 | https://www.osb.co.uk/about-us/our-people/ · https://www.globaldata.com/company-profile/onesavings-bank-plc/executives/ (2026-09-14) | 강 |
| OSB-P2 | Simon Jeffery | Chief Data Officer | tech_buyer | 2022-04 | https://theorg.com/org/osb-group/org-chart/simon-jeffery · https://rocketreach.co/simon-jeffery-email_58652172 (2026-09-14) | 중 |

- OSB-P1: 전 Deloitte Risk and Regulatory 시니어 디렉터. EIR 이력 보유 조직의 모델·AI 리스크 통제 책임자로 EB 정확 일치.
- OSB-P2: 전 Ecclesiastical Insurance Group Data Director. 트랜스포메이션 프로그램의 AI·고급 분석 확산과 접점. 근무지 England(Bournemouth, 공개 디렉토리 표기). 출처가 애그리게이터라 발송 전 재확인 권고.
- 미확인: Head of Model Risk / Model Validation 실명, Group Chief Transformation Officer 실명(직책 실재는 공개 디렉토리에서 확인되나 이름 미특정). Sales Navigator 쿼리: `company:("OSB Group" OR "OneSavings Bank") AND ("Head of Model Risk" OR "Model Validation" OR "Chief Transformation Officer") AND location:("United Kingdom")`
- 참고: 신임 CEO가 2026-09 취임 예정으로 보도됨(https://www.theglobeandmail.com/investing/markets/markets-news/Tipranks/1492924/osb-group-sets-september-2026-start-date-for-new-chief-executive/). 임원진 변동 가능성이 있어 발송 직전 전건 재확인 권고.

## 4. Shawbrook Group (UK-B9)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| SHB-P1 | Hugh Fitzpatrick | Chief Risk Officer | EB | 미확인 (GE Capital 출신) | https://www.shawbrook.co.uk/about-us/ (2026-09-14) | 강 |
| SHB-P2 | Shan Lodh | Director of Data Platforms | tech_buyer | 미확인 | https://www.technologyreview.com/2024/08/26/1096349/readying-business-for-the-age-of-ai/ (2026-09-14) | 후보 |

- SHB-P1: 전 GE Capital UK CRO. "AI를 대출 사이클 전 단계 배치" 공시의 리스크 방어 책임자. 기관 공식 About Us 페이지 기재.
- SHB-P2: 데이터 플랫폼 총괄로 AI 배치의 기술 접점. 출처가 2024-08 기사 단일이므로 현직 재확인 필수.
- 미확인: Head of Model Risk / Model Validation 실명. 또한 CTO Russ Thornton은 2025-07 Nottingham Building Society로 이직 확인(https://www.thenottingham.com/media-centre/russ-thornton-chief-technology-officer)되어 기술 라인 후임이 불명. Sales Navigator 쿼리: `company:("Shawbrook") AND ("Head of Model Risk" OR "Model Validation" OR "Chief Technology Officer" OR "Chief Data Officer") AND location:("United Kingdom")`

## 5. Starling Bank (UK-B10)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| STL-P1 | Keith Algie | Group Chief Risk Officer | EB | 2026-03 선임 발표 (규제 승인 조건부) | https://www.starlingbank.com/news/starling-appoints-new-group-chief-risk-officer/ · https://www.uktech.news/fintech/starling-bank-appoints-new-chief-risk-officer-20260324 · https://www.finextra.com/newsarticle/47722/inside-starling-a-conversation-with-group-cro-keith-algie (2026-09-14) | 강 |
| STL-P2 | Harriet Rees | Group Chief Information Officer (HMT Financial Services AI Champion, BoE AI Taskforce Co-Chair) | tech_buyer | 2018 입사, AI Champion 2026-01-20부 | https://www.starlingbank.com/people/harriet-rees/ · https://www.gov.uk/government/news/ai-champions-appointed-to-help-city-safely-seize-ai-opportunities (2026-09-14) | 강 |

- STL-P1: ANZ에서 20년+ 리스크 경력(CRO Europe and Americas 등). **신임 CRO 자체가 시그널**(부임 후 30~120일 유효창 내, KB03 §5.2). 전임 Cyrille Salle De Chou는 2026-03 퇴임 확인.
- STL-P2: 계정 핵심 시그널(HMT AI Adoption Plan 공동 작성)의 당사자. Data Science 조직 창설자로 champion 성격 겸유. 근무지 UK(런던, 기관 공식 인물 페이지).
- 미확인: Head of Model Risk / AI Governance 전담 리더 실명(직책 실재 자체가 미확인, 리서치 파일 §4와 동일). Sales Navigator 쿼리: `company:("Starling Bank") AND ("Model Risk" OR "AI Governance" OR "Responsible AI" OR "Head of Data Science") AND location:("United Kingdom")`

## 6. Skipton Building Society (UK-S4)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| SKP-P1 | Steve O'Regan | Chief Risk Officer | EB | 2022-08 (2019-08 Chief Internal Auditor로 입사) | https://theorg.com/org/skipton-building-society/org-chart/steve-oregan · https://wiza.co/d/skipton-building-society/eb22/steve-o-regan (2026-09-14) | 중 |
| SKP-P2 | Jenny Wood | Chief Information Officer [직함 표기 재확인 필요] | tech_buyer | 미확인 | https://www.yorkshirepost.co.uk/business/skipton-building-society-staff-freed-up-for-right-customer-conversations-with-major-ai-rollout-5335253 (2026-09-14) | 후보 |

- SKP-P1: 전 Bank of Ireland Group Chief Internal Auditor. Copilot 전사 확산기의 리스크 통제 EB. 출처가 애그리게이터 중심이라 기관 공식 페이지 재확인 권고.
- SKP-P2: Copilot 확산·AI 롤아웃을 언론에 직접 설명한 기술 임원으로 계정 시그널의 실행 소유자. 검색 스니펫 기반 특정이므로 이름·직함 모두 발송 전 재확인 필수.
- 미확인: Head of Model Risk 실명. Sales Navigator 쿼리: `company:("Skipton Building Society") AND ("Head of Model Risk" OR "Model Validation" OR "Chief Data Officer") AND location:("United Kingdom")`

## 7. Coventry Building Society (UK-S2)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| CBS-P1 | Patrick Moynihan | Group Chief Risk Officer | EB | 미확인 (전임 이동 경과상 2024 이후 추정 금지, 재확인 필요) | https://www.linkedin.com/in/patrick-moynihan-27965a29/ · https://theorg.com/org/coventry-building-society?person=patrick-moynihan (2026-09-14) | 중 |

- CBS-P1: 전 Barclays·HSBC Innovation Banking. CRO 계보는 공개 보도로 교차 확인됨: Richard Bowles가 2024-02 YBS로 이동(https://www.insidermedia.com/news/yorkshire/yorkshire-building-society-appoints-chief-risk-officer), interim CRO Graeme Forrester가 2026-04 Principality로 이동(https://theintermediary.co.uk/2026/04/principality-building-society-strengthens-team-with-key-executive-appointments/), 이후 현직으로 Moynihan이 공개 프로필에 기재. 기관 공식 페이지 재확인 권고.
- 미확인: **Group Head of Model Risk Management and Validation 실명.** 직책 실재는 2026-01-16 채용공고의 보고라인으로 확인(리서치 파일 §2, https://www.ziprecruiter.co.uk/jobs/488994214-senior-manager-model-risk-management-and-validation-at-coventry-building-society). 챔피언 1순위 직책이므로 우선 특정 필요. Sales Navigator 쿼리: `company:("Coventry Building Society") AND ("Head of Model Risk" OR "Model Risk Management and Validation") AND location:("United Kingdom")`

## 8. Leeds Building Society (UK-S5)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| LBS-P1 | Katherine Tong | Chief Risk Officer | EB | 2025 Q4 선임, 2026-01-01부 공식 교체 | https://www.leedsbuildingsociety.co.uk/your-society/about-us/board-of-directors/ · https://www.bloomberg.com/profile/person/19733191 (2026-09-14) | 강 |

- LBS-P1: **계정 핵심 시그널(신임 CRO)의 당사자로 최우선 특정 완료.** 2001년 입사 내부 승진, 직전 Director of Compliance, Legal, Risk and Secretary. 전임 Andy Mellor를 2026-01-01부 교체(기관 이사회 페이지 기재). 근무지 UK(Leeds 본사 내부 승진 임원). 리서치 파일 §2의 "풀네임 미확정" 항목 해소.
- 참고: 신임 CEO Annette Barnes(2026-04)는 시그널 근거이나 타깃 페르소나(a~d) 대상 아님.
- 미확인: Head of Model Risk / Model Validation 실명(직책 실재 포함), 코어 현대화 프로그램 리드 실명. Sales Navigator 쿼리: `company:("Leeds Building Society") AND ("Head of Model Risk" OR "Model Validation" OR "Chief Information Officer" OR "Chief Data Officer") AND location:("United Kingdom")`

## 9. Metro Bank (UK-B3)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| MTB-P1 | Kirsten McLeod | Chief Risk Officer | EB | 미확인 (직전 Metro Bank Chief Credit Officer) | https://www.metrobankonline.co.uk/about-us/metro-bank-team/metrobank-team/kirsten-mcleod/ · https://www.metrobankonline.co.uk/about-us/metro-bank-team/ (2026-09-14) | 강 |

- MTB-P1: 기관 공식 리더십 페이지에 CRO로 기재. 신용 출신 CRO로 에이전틱 AI 상업대출 배치(Covecta)의 리스크 통제 서사와 접점이 정확. 근무지 UK(런던 본사 기관 공식 페이지).
- 미확인: Head of Model Risk / Credit Risk Models 실명, Corporate & Commercial AI 배치 책임 임원 실명. Sales Navigator 쿼리: `company:("Metro Bank") AND ("Head of Model Risk" OR "Model Validation" OR "Credit Risk Model" OR "Chief Data Officer") AND location:("United Kingdom")`

## 10. Paragon Banking Group (UK-B5)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| PAR-P1 | Ben Whibley | Chief Risk Officer | EB | 2020 (Deputy CRO 2017~2020, Paragon Bank CRO 2015~2017) | https://www.globaldata.com/company-profile/paragon-banking-group-plc/executives/ (2026-09-14) | 중 |

- PAR-P1: IRB 프로그램·PRA 강화 신청 프로세스 대응의 총괄 EB. 그룹 내 10년+ 리스크 경력. 출처가 임원 디렉토리 단일이므로 기관 공식 페이지(Risk and Compliance Committee 문서 https://www.paragonbankinggroup.co.uk/resources/paragongroup/documents/corporategovernance/riskcompliancecommittee) 재확인 권고.
- 미확인: Head of Model Risk / IRB Programme Lead 실명, Head of Model Validation 실명. IRB 신청 국면의 챔피언 1순위 직책이므로 우선 특정 필요. Sales Navigator 쿼리: `company:("Paragon Banking Group" OR "Paragon Bank") AND ("Head of Model Risk" OR "IRB" OR "Model Validation" OR "Model Development") AND location:("United Kingdom")`

## 11. Monzo Bank (UK-B11)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| MZO-P1 | Iain Laing | Group Chief Risk Officer | EB | 미확인 | https://monzo.com/meet-our-executive-team (2026-09-14) | 강 |

- MZO-P1: 기관 공식 임원 페이지에 Group CRO로 기재. 전 Nationwide CRO 경력 보유자로 FCA AI Live Testing 참여·급성장 국면의 EB. 근무지 UK(런던 본사 기관 공식 페이지).
- 미확인: Head of Model Risk / ML 리더십 실명, AI Governance 리더 실명. (CISO Mike Bray는 공개 확인되나 타깃 페르소나 a~d 밖이라 미편입.) Sales Navigator 쿼리: `company:("Monzo") AND ("Model Risk" OR "Head of Machine Learning" OR "AI Governance" OR "Responsible AI" OR "Chief Data Officer") AND location:("United Kingdom")`

## 12. Close Brothers Group (UK-B6)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| CBG-P1 | Robert Sack | Group Chief Risk Officer | EB | 2015-04 | https://www.bloomberg.com/profile/person/19482417 · https://www.closebrothers.com/who-we-are (2026-09-14) | 강 |

- CBG-P1: 전 Barclays Group Head of Wholesale Risk·CRO Africa. 모터파이낸스 배상 국면 + AI "at pace" 배치의 리스크 통제 EB. 기관 공식 Who we are 페이지 기재.
- 미확인: Head of Model Risk / Model Validation 실명, Transformation/Operations AI 배치 소유 임원 실명. Sales Navigator 쿼리: `company:("Close Brothers") AND ("Head of Model Risk" OR "Model Validation" OR "Transformation Director" OR "Chief Data Officer") AND location:("United Kingdom")`

## 13. Investec (UK-B7, Investec Bank plc 한정)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| (편입 불가) | Mark Currie | Group Chief Risk Officer (Investec Group, DLC) | (EB 상당) | 미확인 (그룹 32년 재직) | https://za.linkedin.com/in/mark-currie-9934084 · https://www.investec.com/en_za/welcome-to-investec/contact-us/our-offices/johannesburg-office/mark-currie.html (2026-09-14) | 회피 (근무지 SA) |

- Mark Currie: 그룹 CRO이나 **근무지가 Johannesburg(남아공)로 확인**되어 캠페인 관할(UK) 밖이다. 리서치 파일 §4 규칙(남아공 법인 인물은 회피 등급, 편입 금지)에 따라 회피 태깅만 기록하고 리스트에 편입하지 않는다. 판정은 sales-compliance-officer로 이관(G2).
- 미확인: **Investec Bank plc(UK 법인, PRA 규제) 전담 CRO 실명.** Ruth Leas가 2017~2019 IBP CRO였으나 2019 CEO 승진 이후의 후임을 공개 검색에서 특정하지 못했다. Head of Model Risk(UK)·CIO(UK)도 미특정. Sales Navigator 쿼리: `company:("Investec") AND ("Chief Risk Officer" OR "Head of Risk" OR "Head of Model Risk" OR "Model Validation") AND location:("United Kingdom" OR "London")` (근무지 UK 필터 필수)

## 14. Allica Bank (UK-B17)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| ALL-P1 | Alan Dunmur | Chief Risk Officer | EB | 미확인 | https://www.allica.bank/meet-the-board (2026-09-14) | 중 |

- ALL-P1: 기관 공식 리더십 페이지 기반 검색 결과로 CRO 확인. "AI 에이전트 배포로 대출 의사결정 가속" 선언 조직의 신용 AI 리스크 EB. 검색 스니펫 기반이므로 기관 페이지에서 직함 원문 재확인 권고.
- 미확인: Head of Credit Risk / Model Risk 실명, CTO / Head of Data & AI 실명. Sales Navigator 쿼리: `company:("Allica Bank") AND ("Head of Credit Risk" OR "Model Risk" OR "Chief Technology Officer" OR "Head of Data") AND location:("United Kingdom")`

## 15. Zopa Bank (UK-B14)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| ZPA-P1 | Graham Robinson | Chief Risk Officer | EB | 2021-11 | https://www.crunchbase.com/person/graham-robinson-aa64 · https://www.linkedin.com/in/grahamjohnrobinson/ · https://www.crowdfundinsider.com/2021/11/182483-zopa-bank-appoints-graham-robinson-previously-at-monzo-as-its-new-chief-risk-officer/ (2026-09-14) | 중 |

- ZPA-P1: 전 Monzo Director of Credit, Capital One 18년. ML 신용 스코어링 + AI Assistant 확장 국면의 EB로 신용 리스크 전문성이 캠페인 가설과 정확히 접점. 2021년 선임 보도 이후 현직 표기는 공개 프로필(Crunchbase·LinkedIn) 기준이므로 발송 전 재확인 권고. 기관 리더십 페이지: https://www.zopa.com/about/leadership
- 미확인: Head of Credit Risk / Model Risk 실명, Chief Data/AI Officer(AI Assistant 소유 조직) 실명. Sales Navigator 쿼리: `company:("Zopa") AND ("Head of Credit Risk" OR "Model Risk" OR "Chief Data Officer" OR "Head of Data Science" OR "Head of AI") AND location:("United Kingdom")`

## 16. IG Group (UK-P2)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| IGG-P1 | Sarah Gore Langton | Chief Risk Officer | EB | 2024~2025 (보도 기준, 정확 일자 미확인. 2015 입사, 2017~ Chief Compliance Officer 후 승진) | https://uk.linkedin.com/in/sarah-gore-langton-4b78a0219 · https://www.financemagnates.com/executives/moves/ig-group-names-new-chief-operating-officer-and-chief-risk-officer/ · https://fxnewsgroup.com/forex-news/executives/exclusive-ig-group-to-name-jody-dunn-as-coo-sarah-gore-langton-cro/ (2026-09-14) | 강 |

- IGG-P1: 전 BlackRock 출신, IG 내부 승진(컴플라이언스 총괄 경력). AI 스쿼드 확산 + 전략 리뷰 국면의 EB. LinkedIn 프로필이 uk.linkedin.com으로 UK 근무지 표시. 전임 Group CRO Joe McCaughran은 2025년 ClearBank로 이직 확인(https://fxnewsgroup.com/forex-news/executives/exclusive-ig-group-risk-head-joe-mccaughran-leaves-joins-clearbank/).
- 미확인: Head of Model Risk / Quantitative Risk 실명, CTO / Head of AI(AI 스쿼드 소유) 실명. Sales Navigator 쿼리: `company:("IG Group") AND ("Model Risk" OR "Quantitative Risk" OR "Chief Technology Officer" OR "Head of AI" OR "Chief Data Officer") AND location:("United Kingdom")`

---

## 요약

| 구분 | 값 |
|---|---|
| 특정 완료 인물 | **22명** (16개 기관 중 15개 기관에서 1명 이상 특정) |
| 적합도 분포 | 강 13 · 중 7 · 후보 2 |
| 페르소나 분포 | EB 15 · champion 1 (Matthew Jones) · tech_buyer 6 |
| 회피 태깅 (편입 불가) | 1명 (Mark Currie, Investec Group CRO, 근무지 SA. G2로 compliance-officer 판정 이관) |
| 인물 0명 기관 | 1곳 (Investec: UK 법인 CRO 미특정, Sales Navigator 쿼리 제공) |
| 기관당 2명 이상 확보 | 6곳 (YBS, Nationwide, OSB, Shawbrook, Starling, Skipton) |
| 기관당 1명 (2~3명 목표 미달) | 9곳 (Coventry, Leeds, Metro, Paragon, Monzo, Close Brothers, Allica, Zopa, IG) |
| 미확인 직책 (Sales Navigator 쿼리 제공) | 16건: YBS Head of Model Risk · Nationwide Group Director of Modelling/AI Governance · OSB Head of Model Risk/CTO(트랜스포메이션) · Shawbrook Head of Model Risk/CTO 후임 · Starling Model Risk/AI Governance · Skipton Head of Model Risk · Coventry Group Head of MRM&V(챔피언 1순위) · Leeds Head of Model Risk/현대화 리드 · Metro Head of Model Risk · Paragon IRB/Model Risk 리더(챔피언 1순위) · Monzo Model Risk/ML 리더 · Close Brothers Head of Model Risk · Investec UK CRO/Model Risk · Allica Credit/Model Risk·CTO · Zopa Model Risk·CDO · IG Model Risk·CTO |

### 재확인 필요 항목 (발송 전, PO/도구)

1. **후보 등급 2명 필수 재확인**: Shan Lodh(Shawbrook, 2024 출처 단일), Jenny Wood(Skipton, 검색 스니펫 기반 특정. 이름·직함 모두).
2. **중 등급 7명 현직 재확인**: Matthew Jones(직함 표기), Simon Jeffery, Steve O'Regan, Patrick Moynihan, Ben Whibley, Alan Dunmur, Graham Robinson. 기관 공식 페이지 또는 Sales Navigator 대조.
3. **Starling Keith Algie**: 2026-03 선임이 "규제 승인 조건부"였으므로 발송 시점에 승인 완료·재직 여부 확인.
4. **OSB Group**: 2026-09 신임 CEO 취임 예정 보도에 따라 임원진 연쇄 변동 가능성. 발송 직전 전건 재확인.
5. **시그널 유효기간**: 1차 배치 계정(YBS, Nationwide, Coventry, Skipton 등) 시그널이 2026-09-17~18 만료(prospect-list-summary §4). 인물 특정과 별개로 시그널 재확인 없이는 G4 보류 유지.
6. 모든 레코드는 G9 필수 필드(data_source, collected_date, LIA 문서 ID, 보관기간 만료일, corporate_subscriber_flag) 충족 전 발송 큐 진입 불가. LIA·보관기간은 sales-compliance-officer 공급 대기.

### 방법·제약 기록

- 이 문서의 확인은 전부 2026-09-14 웹 검색(공개 출처) 기반이다. 세션 네트워크 제약으로 기관 공식 도메인 직접 열람이 차단되어 검색 결과 스니펫으로 교차 확인했으며, 세션 검색 한도 도달로 일부 2·3순위 인물(주로 Head of Model Risk 계열)은 미특정으로 남기고 Sales Navigator 쿼리로 대체했다.
- 이메일 주소는 어떤 레코드에도 없다. email 필드는 전건 "[PO/도구]"이며 PO가 검증 도구(UK: Cognism 권고)로 채운다.
