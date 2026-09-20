# 인물 특정: 미국 보험·자산운용 8개 기관 (US-I/US-A 배치)

| 항목 | 내용 |
|---|---|
| 기준일 (전건 확인일) | 2026-09-14 |
| 작성 에이전트 | prospect-researcher |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 방법 | 공개 출처(공식 리더십 페이지, 보도자료, 뉴스, SEC 공시, 공개 LinkedIn)만으로 타깃 직책의 실제 인물을 특정하고 현직 여부를 WebSearch로 재확인. 비공개 정보 수집 없음 |

운영 규칙:

- email 필드는 전 레코드 `[PO/도구]`. 이메일 주소는 어떤 형태로도 추정·생성·기재하지 않았다.
- jurisdiction: 전 레코드 US (근무지 기준). 수집일 = 확인일 2026-09-14.
- 적합도: 강 = 공식·복수 출처로 현직·직함 확인 / 중 = 현직 개연 높으나 출처 또는 일자 정밀도 부족 / 후보 = 직함·좌석 상태 또는 페르소나 적합성 미확정.
- 본 문서는 인물 특정 산출물이며 발송 판단이 아니다. 발송 큐 진입은 G9 필수 필드 충족과 PO 보류 해제 이후에만 가능하다 [G1][G4][G9].

---

## 1. MetLife (US-I1)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| MET-P1 | Marlene Debel | Executive Vice President and Chief Risk Officer, Head of MetLife Insurance Investments | EB | CRO 2019-05 | https://www.metlife.com/about-us/corporate-governance/our-executive-leadership-team/marlene-debel/ (2026-09-14) | 강 |
| MET-P2 | Tamar Shapiro | Chief Data and Analytics Officer | tech_buyer | 2024-07 (발표) | https://www.metlife.com/about-us/newsroom/2024/july/metlife-adds-industry-top-talent-to-global-technology-and-operations/ (2026-09-14) | 강 |
| MET-P3 | Bill Pappas | Executive Vice President, Head of Global Technology and Operations | tech_buyer | 부임일 미확인 | https://www.metlife.com/about-us/corporate-governance/our-executive-leadership-team/ (2026-09-14) | 중 |

인물별 관련성 메모:

- MET-P1 Debel: 공식 리더십 페이지에 현직 확인. Q2 콜의 "거버넌스·리스크 감독이 AI 배치 중심" 공언을 실행하는 리스크 조직의 정점. 보험 투자 부문도 겸해 모델 인벤토리 접점이 넓다.
- MET-P2 Shapiro: 전사 데이터·분석·AI 전략과 responsible use of AI를 직무 범위로 명시한 CDAO. Instagram Head of Analytics 출신, 2024-07 영입.
- MET-P3 Pappas: 38,000명 규모 기술·운영 조직에서 AI 확산을 총괄. 다만 거버넌스 전담이 아니라 페르소나 적합성은 간접이어서 중.

미확인 직책: Head of Model Risk / Head of AI Governance 전담 임원은 공개 출처에서 미확인 (Global Responsible AI Policy는 존재하나 전담 좌석 공표 없음).
- PO용 Sales Navigator 쿼리: `company:"MetLife" AND ("Head of Model Risk" OR "Model Risk Management" OR "Responsible AI" OR "AI Governance") AND location:"United States"`

---

## 2. Prudential Financial (US-I2)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| PRU-P1 | Bob Bastian | Chief Data and AI Officer | tech_buyer | 2026-04 | https://www.cdomagazine.tech/leadership-moves/prudential-financial-promotes-bob-bastian-to-chief-data-and-ai-officer · https://www.linkedin.com/in/bobbastian12/ (2026-09-14) | 강 |
| PRU-P2 | Meyrick Douglas | Senior Vice President and Chief Risk Officer | EB | 2023 | https://www.insuranceerm.com/news-comment/meyrick-douglas-to-become-prudential-financial-cro-in-2023.html · https://crocouncil.org/about-us/council-members/profile/meyrick-douglas (2026-09-14) | 강 |

인물별 관련성 메모:

- PRU-P1 Bastian: 시그널 인물 (CDAIO 승격, 2026-04). 직무 기술에 "strengthening risk management" 명시, 약 30년 재직 후 CIO에서 승격. 현직 LinkedIn·CDO Magazine으로 재확인.
- PRU-P2 Douglas: 2023년 CRO 부임(전임 Nick Silitch 은퇴). 이전에 Deputy CRO로서 모델리스크 관리 인프라 구축을 직접 이끈 이력이 있어 PRD-VAL 서사와 정합. 참고: 구 자료(Comparably 등)의 Nick Silitch 표기는 구정보다.

미확인 직책: Chief Actuary는 Candace Woods 은퇴 확인(후임 공표 미발견, https://www.adapt.io/contact/candace-woods/875194492 2026-09-14), Head of Model Risk 전담도 미확인. 재직 표기가 남은 구 출처가 있어 주의.
- PO용 Sales Navigator 쿼리: `company:"Prudential Financial" AND ("Chief Actuary" OR "Head of Model Risk" OR "Model Risk Management" OR "Actuarial Modeling") AND location:"United States"`

---

## 3. Allstate (US-I5, 좁은 접근 전제)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| ALL-P1 | Mark Prindiville | Executive Vice President and Chief Risk Officer | EB | 2020 | https://www.allstatecorporation.com/about/leadership/mark-prindiville.aspx (2026-09-14) | 강 |
| ALL-P2 | Steven Armstrong | Senior Vice President and Chief Actuary | champion | 2017-02 | https://www.linkedin.com/in/sasarm34/ · https://theorg.com/org/allstate/org-chart/steven-armstrong (2026-09-14) | 강 |
| ALL-P3 | Eric Huls | Chief Data Officer / Chief Data Science Officer | tech_buyer | 부임일 미확인 (재직 2000-07~) | https://www.comparably.com/companies/allstate/eric-huls · https://www.linkedin.com/in/erichuls/ (2026-09-14) | 중 |

인물별 관련성 메모:

- ALL-P1 Prindiville: 공식 리더십 페이지에 현직 확인, 전사 리스크·수익 활동 총괄. ALLIE(내부 전용 LLM 생태계)와 규제 요율 모델의 경계 감사 가능성 논의의 EB.
- ALL-P2 Armstrong: 요율 정교화·모델링을 총괄하는 Chief Actuary(전 CAS 회장). 좁은 접근(3선 독립검증 보완) 전제에서 가장 직접적인 챔피언 접점.
- ALL-P3 Huls: 데이터·데이터사이언스 총괄로 250+ 분석 모델 기반의 소유 라인 개연. 다만 공식 페이지가 아닌 비공식 출처 의존, 직함 표기가 출처 간 상이(CDO/CAO)하여 중.

미확인 직책: Head of Responsible AI / AI Governance 전담은 공개 출처에서 미확인.
- PO용 Sales Navigator 쿼리: `company:"Allstate" AND ("Responsible AI" OR "AI Governance" OR "Model Risk" OR "Model Validation") AND location:"United States"`

---

## 4. T. Rowe Price (US-A1)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| TROW-P1 | Ted Carter | Chief Risk Officer (Enterprise Risk Management Committee 의장) | EB | 부임일 미확인 | https://www.troweprice.com/en/us/bios/ted-carter (2026-09-14, 검색 결과로 확인·직접 열람 불가) | 중 |
| TROW-P2 | Vinit Agrawal | Head of Investment Data Insights and AI Solutions | tech_buyer | 2026-08-13 (AI 총괄 지정 발표) | https://www.troweprice.com/en/us/press/2026/press-release--t--rowe-price-advances-ai-strategy-with-leadershi · https://www.planadviser.com/t-rowe-price-expands-ai-leadership-roles/ (2026-09-14) | 강 |
| TROW-P3 | Sal Dhanani | Head of Global Distribution AI Strategy and Transformation | tech_buyer | 2026-08-13 (발표) | https://www.planadviser.com/t-rowe-price-expands-ai-leadership-roles/ (2026-09-14) | 후보 |

인물별 관련성 메모:

- TROW-P1 Carter: 자사 공식 bio에 CRO·ERM 위원회 의장으로 기재. 2026-08-13 발표의 "enhanced risk oversight" 문언을 받아낼 EB. 사이트 직접 열람이 프록시로 차단되어 검색 결과 경유 확인이라 중, 재확인 필요.
- TROW-P2 Agrawal: 시그널 인물 (2026-08-13 AI 리더십 개편). 투자 부문 AI 전략(제품·교육·파트너십·리서치) 총괄로 지정. Investment AI Solutions 조직 확장의 소유자.
- TROW-P3 Dhanani: 같은 발표에서 유통 부문 AI 총괄로 지정. 거버넌스 접점은 간접이라 후보로만 등재.

미확인 직책: Head of Model Risk / AI Governance 전담은 공개 출처에서 미확인 (발표문의 risk oversight는 조직명·인명 미공개).
- PO용 Sales Navigator 쿼리: `company:"T. Rowe Price" AND ("Model Risk" OR "Investment Risk" OR "AI Governance" OR "Responsible AI") AND location:"United States"`

---

## 5. Franklin Templeton (US-A2)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| BEN-P1 | Joe Boerio | Executive Vice President, Chief Risk and Transformation Officer | EB | 부임일 미확인 | https://www.linkedin.com/in/joe-boerio/ · https://www.crunchbase.com/person/joe-boerio (2026-09-14) | 중 |
| BEN-P2 | Deep Ratna Srivastav | Chief AI Officer | tech_buyer | 2025-01 (발표) | https://www.cdomagazine.tech/leadership-moves/franklin-templeton-appoints-deep-ratna-srivastav-as-chief-ai-officer · https://www.linkedin.com/in/deepsrivastavinnovate/ (2026-09-14) | 강 |

인물별 관련성 메모:

- BEN-P1 Boerio: Chief Risk and Transformation Officer로 리스크와 트랜스포메이션을 겸장, "리스크 기능 안의 AI" 가설(2026-07-31 콜)과 정면으로 겹치는 EB. 공식 리더십 페이지 확인이 안 되어 중, 재확인 필요.
- BEN-P2 Srivastav: 전 SVP, Head of AI and Digital Transformation에서 CAIO로 선임(발표 2025-01). AI 제품 개발·도입 총괄, Intelligence Hub 어젠다의 기술 구매자 라인.

미확인 직책: Head of Investment Risk / Model Risk 전담 미확인. 참고: Surajit Ray가 Franklin Equity Group의 Head of Portfolio Construction and Quantitative Risk로 선임(2025-05, 부문 단위라 본 리스트 제외, https://www.businesswire.com/news/home/20250521826757/en/ 2026-09-14).
- PO용 Sales Navigator 쿼리: `company:"Franklin Templeton" AND ("Investment Risk" OR "Model Risk" OR "AI Governance" OR "Responsible AI") AND location:"United States"`

---

## 6. Lincoln Financial (US-I3)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| LNC-P1 | Nilanjan (Neel) Adhya | Executive Vice President, Chief AI, Data and Analytics Officer | tech_buyer | 2026-01-09 (효력) | https://www.lincolnfinancial.com/public/aboutus/companyoverview/whoweare/leadership/nilanjanadhya · https://www.businesswire.com/news/home/20251204014069/en (2026-09-14) | 강 |
| LNC-P2 | Paul Spurr | Executive Vice President, Chief Risk Officer and Chief Actuary | EB | 2026-06-01 (효력) | https://www.businesswire.com/news/home/20260601103954/en/Lincoln-Financial-Announces-Executive-Leadership-Transitions (2026-09-14) | 강 |
| LNC-P3 | Ona Lewis | Senior Vice President, Head of Strategic and Emerging Risk Management | champion | 부임일 미확인 | https://www.lincolnfinancial.com/public/aboutus/newsroom/pressreleases/lincoln-financial-group-names-ona-lewis-as-senior-vice-president-head-strategic-and-emerging-risk-management (2026-09-14) | 중 |

인물별 관련성 메모:

- LNC-P1 Adhya: 시그널 인물 (CEO 직속 신설 CAIDAO). 자사 리더십 페이지에 현직 확인. 전 BlackRock Chief Digital Officer, AI·데이터를 전사 핵심 역량으로 만드는 조직 구축 주체.
- LNC-P2 Spurr: 2026-06-01부로 CRO와 Chief Actuary 겸직(전임 Andy Rallis 은퇴). 부임 3개월 대의 신임 EB이면서 계리모델 거버넌스 라인(페르소나 b)을 동시에 소유하는 단일 창구.
- LNC-P3 Lewis: 전략·신흥 리스크 총괄로 AI 리스크가 신흥 리스크 어젠다에 얹힐 개연. 부임일·현직 범위 재확인 필요.

미확인 직책: Head of Model Risk / Model Validation 전담 미확인 (발견된 채용은 AI 프로덕트 계열).
- PO용 Sales Navigator 쿼리: `company:"Lincoln Financial" AND ("Model Risk" OR "Model Validation" OR "Actuarial Modeling" OR "AI Governance") AND location:"United States"`

---

## 7. MassMutual (US-I6)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| MM-P1 | Geoff Craddock | Chief Risk Officer | EB | 2017-10 | https://crocouncil.org/about-us/council-members/profile/geoff-craddock · https://www.prnewswire.com/news-releases/massmutual-appoints-geoff-craddock-as-chief-risk-officer-300529081.html (2026-09-14) | 강 |
| MM-P2 | Sears Merritt | Head of Enterprise Technology and Experience (CIO) | tech_buyer | CIO 2022 | https://www.businesswire.com/news/home/20220519005936/en/MassMutual-Names-Sears-Merritt-Head-of-Technology-and-Experience · https://www.linkedin.com/in/searsmerritt/ (2026-09-14) | 강 |
| MM-P3 | Lisa Walkuski | (LinkedIn 표기) Data Privacy and AI Governance, MassMutual | champion | 부임일 미확인 | https://www.linkedin.com/in/lisawalkuski/ (2026-09-14) | 후보 |

인물별 관련성 메모:

- MM-P1 Craddock: 은퇴·후임 보도 없음(2026-09-14 검색 기준)으로 현직 판단. 부임 약 9년 경과라 분기 재확인 대상.
- MM-P2 Merritt: 2013년 첫 데이터사이언티스트로 입사, 2022년 CIO 승격. 기술·사이버·데이터·AI 전략 총괄이며 업계 최초 data and AI governance program 구축 이력을 공언한 인물이라 어슈어런스 서사 접점이 직접적.
- MM-P3 Walkuski: LinkedIn에 MassMutual의 Data Privacy and AI Governance 소속으로 표기되나 정확한 직함 미확인. 동명 기능의 리더 좌석인 Head of Privacy, Data and AI Governance 공고가 활성(https://builtin.com/job/head-privacy-data-and-ai-governance/3632964 2026-09-14)이라 좌석 상태 불명, 후보로만 등재.

미확인 직책: Head of Privacy, Data and AI Governance의 확정 재직자 미확인(공고 활성 = 공석 또는 신설 개연). Head of Model Risk / Chief Actuary 산하 모델 거버넌스 리더도 미확인.
- PO용 Sales Navigator 쿼리: `company:"MassMutual" AND ("AI Governance" OR "Privacy, Data and AI" OR "Model Risk" OR "Model Validation") AND location:"United States"`

---

## 8. AllianceBernstein (US-A3)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| AB-P1 | Andrew Chin | Chief Artificial Intelligence Officer | tech_buyer | 2024-07-01 | https://alliancebernsteinholdinglp.gcs-web.com/news-releases/news-release-details/alliancebernstein-announces-andrew-chin-chief-artificial · https://www.bloomberg.com/news/videos/2026-03-03/andrew-chin-on-efficiency-use-cases-and-ai-guardrails-video (2026-09-14) | 강 |
| AB-P2 | John Schiavetta | Senior Vice President, Chief Risk Officer | EB | 부임일 미확인 | https://www.alliancebernstein.com/corporate/en/home/leadership-team.html · https://www.bloomberg.com/profile/person/2557911 (2026-09-14) | 중 |

인물별 관련성 메모:

- AB-P1 Chin: 시그널 관련 리더. 전사 AI 책임(부서 단위 아님)을 가지며 AI 리스크 거버넌스 위원회가 전 사용례를 심사하는 체제의 정점 라인. 10년+ CRO 역임이라 독립검증(3선) 언어가 통하는 창구. 2026-03-03 Bloomberg 영상으로 현직 재확인.
- AB-P2 Schiavetta: 공식 리더십 페이지·Bloomberg 프로필에 SVP, CRO로 확인. 부임일 미상이라 중, 재확인 필요.

미확인 직책: AI 리스크 거버넌스 위원회 의장의 명시적 공표는 미확인(위원회 실재는 보도 확인, Chin 조직 소관 개연). Head of Responsible AI 전담도 미확인.
- PO용 Sales Navigator 쿼리: `company:"AllianceBernstein" AND ("Responsible AI" OR "AI Governance" OR "AI Risk" OR "Model Risk") AND location:"United States"`

---

## 요약

| 구분 | 수 |
|---|---|
| 특정 완료 인물 | 21명 (기관당 2~3명) |
| 적합도 강 | 13명 (Debel, Shapiro, Bastian, Douglas, Prindiville, Armstrong, Agrawal, Srivastav, Adhya, Spurr, Craddock, Merritt, Chin) |
| 적합도 중 | 6명 (Pappas, Huls, Carter, Boerio, Lewis, Schiavetta) |
| 적합도 후보 | 2명 (Dhanani, Walkuski) |
| 미확인 직책 | 8건 (기관별 1건+: 주로 Head of Model Risk / Responsible AI 전담, Prudential Chief Actuary 후임, MassMutual AI 거버넌스 Head 재직자) |

우선 특정 지시 4건 결과: Prudential CDAIO(Bob Bastian), Lincoln CAIDAO(Nilanjan Adhya), T. Rowe AI 리더십 개편(Vinit Agrawal, Sal Dhanani), AB AI 리스크 거버넌스 관련 리더(Andrew Chin) 전건 실명 특정·현직 재확인 완료.

재확인 필요 항목:

1. TROW-P1 Ted Carter: troweprice.com 공식 bio 직접 열람 불가(프록시 차단), 부임일 미상. PO 도구 재확인 권고.
2. BEN-P1 Joe Boerio: 공식 리더십 페이지 미확인(LinkedIn·Crunchbase 의존).
3. ALL-P3 Eric Huls: 직함 표기가 출처 간 상이(CDO/CAO), 공식 출처 부재.
4. MM-P1 Geoff Craddock: 부임 9년 경과, 분기 단위 현직 재확인 대상.
5. MM-P3 Lisa Walkuski: 정확한 직함과 Head of Privacy, Data and AI Governance 좌석 충원 여부.
6. LNC-P3 Ona Lewis, AB-P2 John Schiavetta: 부임일 미상.
7. Prudential Chief Actuary 후임: Candace Woods 은퇴 확인, 후임 공표 대기.

G9 잔여: 전 레코드 email = [PO/도구] 미수집 상태이며, suppression 대조·수신 근거(CAN-SPAM) 필드 충족 전 발송 큐 진입 불가. 보류 해제·앵글 선택은 PO 전속 [G1].
