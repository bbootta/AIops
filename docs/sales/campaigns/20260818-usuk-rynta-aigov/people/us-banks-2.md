# 인물 특정: US 은행 2차 (prospect-list-summary §1 미국 11~19번)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/people/us-banks-2.md`

| 항목 | 내용 |
|---|---|
| 기준일 (확인일) | 2026-09-14 |
| 작성 에이전트 | prospect-researcher |
| 방법 | 기존 계정 리서치 산출물(research/) 재활용 후, 기관 공식 리더십 페이지, 보도자료, IR/SEC 공시, 뉴스, 공개 LinkedIn 프로필 등 공개 출처만으로 WebSearch 재확인. 비공개 정보 수집 없음 |
| 대상 | 9개 기관 (20번 Ally는 재상신 대기로 제외) |
| 타깃 직책 | (a) CRO 계열 = EB, (b) Model Risk 리더 = champion, (c) AI Governance / Responsible AI 리더 = champion, (d) CDO / CDAO / Chief AI Officer = tech_buyer (list-build-spec §3) |

공통 규칙:

- email 필드는 전 레코드 "[PO/도구]". 이메일 주소는 어떤 형태로도 추정, 생성, 기재하지 않았다.
- jurisdiction은 전 레코드 US. 수집 출처와 수집일은 각 표의 출처 열(확인일 2026-09-14)이 담당한다. US 수신 근거는 CAN-SPAM 옵트아웃 기준으로 발송 단계에서 PO가 확정한다.
- 확인되지 않은 직책은 "미확인"으로 남기고 PO용 LinkedIn Sales Navigator 쿼리를 기재했다.
- 발송 투입 여부와 무관: 각 계정의 G4 발송 보류 판정은 research/ 산출물 기준이 유지되며, 보류 해제는 PO만 할 수 있다.

---

## 1. Truist Financial (US-B10)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| TRU-P1 | Brad Bender | SEVP, Chief Risk Officer | EB | 2024-11 | https://media.truist.com/Brad_Bender ; https://www.prnewswire.com/news-releases/truist-announces-retirement-of-vice-chair-and-chief-risk-officer-clarke-r-starnes-iii-and-appointment-of-brad-bender-as-successor-302304704.html (확인일 2026-09-14) | 강 |
| TRU-P2 | Chandra Kapireddy | Head of Generative AI, ML and Analytics | champion | 미상 (2025년 이전 부임 보도 확인) | https://sloanreview.mit.edu/audio/overcoming-ai-hallucinations-truists-chandra-kapireddy/ ; https://www.ciodive.com/news/banking-ai-tech-lloyds-natwest-truist-evident-insights/750366/ (확인일 2026-09-14) | 강 |

- TRU-P1 메모: Starnes 은퇴 승계로 2024-11 CRO 취임, 20년 재직자로 크레딧, 운영, 기술 리스크 전반 관장. AI 파이프라인의 프로덕션 게이트(앵글 1) 논의의 EB.
- TRU-P2 메모: 전 JPMC Head of AI/ML Products. "AI 거버넌스와 혁신은 대립할 수 없다" 담론(research 파일 시그널 3)의 실무 소유자로 responsible AI, 인간 감독을 공개 발언. 2025~2026 보도에서 활동 확인.
- 미확인: Head of Model Risk Management / Model Validation 실명 미확인. LinkedIn에서 Alex Shenkar(SVP, 모델검증 팀 리드급)가 검색되나 기능 총괄 여부 미확인이라 미기재. SalesNav 쿼리: `Current company: "Truist" AND Title: ("Head of Model Risk" OR "Model Risk Management" OR "Chief Model Risk Officer" OR "Head of Model Validation") AND Seniority: Director+`

## 2. PNC Financial Services (US-B11, 좁은 접근 전제)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| PNC-P1 | Amy Wierenga | EVP, Chief Risk Officer | EB | 2025-09-08 (CRO) | https://www.pnc.com/en/about-pnc/company-profile/leadership-team/amy-wierenga.html ; https://pnc.mediaroom.com/2025-08-12-PNC-Announces-Leadership-Changes-in-Risk-and-Legal-Organizations (확인일 2026-09-14) | 강 |
| PNC-P2 | Ned Carroll | EVP, Head of Enterprise Data and Automation | tech_buyer | 2024-07 (PNC 합류) | https://digital-banking.americanbanker.com/profile/ned-carroll-2/ ; https://www.linkedin.com/in/ned-carroll-1a65a51a1/ (확인일 2026-09-14) | 강 |

- PNC-P1 메모: CRO 승진 직전 직책이 Head of Financial and Model Risk(chief model risk officer 조직 관장)라 모델리스크 어젠다를 직접 아는 EB. FirstBank 전환 후 재검증 국면(훅)과 정확히 접점.
- PNC-P2 메모: 전 TIAA CDO. 전행 AI 적용 책임(공개 프로필 명시). 좁은 접근 전제에서 데이터, 자동화 라인의 기술 구매자.
- 미확인: Chief Model Risk Officer 실명 미확인(Wierenga 승진 후 Financial and Model Risk 후임 포함 공개 발표 없음). 검색 중 나온 Alan Kaplan은 Citigroup 소속으로 확인되어 배제. SalesNav 쿼리: `Current company: "PNC" AND Title: ("Chief Model Risk Officer" OR "Model Risk" OR "Head of Financial and Model Risk") AND Seniority: VP+`

## 3. First Citizens BancShares (US-B13)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| FCB-P1 | Tom Eklund | EVP, Chief Risk Officer | EB | 2026-06-01 | https://newsroom.firstcitizens.com/2026-01-14-First-Citizens-BancShares,-Inc-Announces-Chief-Risk-Officer-Transition,-Names-Successor ; https://www.sec.gov/Archives/edgar/data/798941/000079894126000007/chiefriskofficertransiti.htm (확인일 2026-09-14) | 강 |
| FCB-P2 | Scott Richardson | Chief Data and Analytics Officer | tech_buyer | 미상 | https://newsroom.firstcitizens.com/2026-09-03-A-Q-A-With-Scott-Richardson-AI-at-First-Citizens-Bank ; https://www.cdomagazine.tech/leadership-moves/first-citizens-bank-appoints-scott-richardson-as-cdao (확인일 2026-09-14) | 강 |
| FCB-P3 | Ash Kaduskar | Head of AI (AI and Advanced Analytics) | champion | 미상 | https://finai.events/finai-banking-summit/first-citizens-bank-head-of-ai-ash-kaduskar-to-join-finai-banking-summit-as-fireside-speaker/ (확인일 2026-09-14) | 중 |

- FCB-P1 메모: 전임 Lorie Rupp 은퇴(2026-01-14 발표) 승계, 2026-06-01 부임. 기준일 현재 부임 약 105일로 신임 임원 유효창(30~120일) 내. 20년 재직 전 Treasurer.
- FCB-P2 메모: 전 Ally CIO of Enterprise Data, Analytics and AI, 전 Fannie Mae CDO. 2026-09-03 자사 뉴스룸 AI Q&A 게재로 현직과 AI 어젠다 소유 동시 확인. Applied AI 채용 시그널의 조직 상급자 개연.
- FCB-P3 메모: Richardson 산하 AI 팀 리드로 보도. 단일 제3자 출처라 적합도 중, 발송 전 LinkedIn 현직 재확인 권고.
- 미확인: Head of Model Risk 실명 미확인. SalesNav 쿼리: `Current company: "First Citizens Bank" AND Title: ("Model Risk" OR "Model Validation") AND Seniority: Director+`

## 4. Old National Bancorp (US-B21)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| ONB-P1 | Scott J. Evernham | EVP, Chief Risk Officer | EB | 미상 (2003년 입사, CRO 취임 시기 미확인) | https://www.oldnational.com/about-us/leadership-team/scott-evernham/ ; https://www.globenewswire.com/news-release/2026/07/22/3331230/5764/en/Old-National-Bancorp-Reports-Record-Second-Quarter-2026-Results-Announces-Enhanced-Executive-Leadership-Structure.html (확인일 2026-09-14) | 강 |
| ONB-P2 | Matt Keen | Chief Information Officer | tech_buyer | 2025-07-01 | https://www.globenewswire.com/news-release/2025/07/01/3108691/5764/en/old-national-names-matt-keen-chief-information-officer.html (확인일 2026-09-14) | 강 |

- ONB-P1 메모: 공식 리더십 페이지에서 현직 확인, 2026-07-22 Q2 실적 발표(경영 구조 개편 포함)에도 CRO로 등장. 통합 후 리스크 체계 책임의 EB.
- ONB-P2 메모: 전 Bremer Bank CIO로, Bremer의 Old National 편입(2025-05-01)과 함께 본체 CIO로 선임. Q2 콜의 "기술, AI, 프로세스 개선 투자" 발언의 실행 라인이자 통합 시스템 사정을 양쪽에서 아는 인물.
- 미확인: Head of Model Risk 실명 미확인(미드사이즈라 Director급 개연). SalesNav 쿼리: `Current company: "Old National Bank" AND Title: ("Model Risk" OR "Model Validation" OR "Capital Stress Testing") AND Seniority: Director+`

## 5. Charles Schwab (US-D5, 좁은 접근 전제)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| SCHW-P1 | Nigel Murtagh | MD, Chief Risk Officer | EB | 미상 (2000년 입사, 리스크 총괄 2009년부터) | https://www.aboutschwab.com/leadership ; https://www.linkedin.com/in/nigel-murtagh-b45b0b4/ ; https://www.investing.com/news/insider-trading-news/schwab-chief-risk-officer-nigel-murtagh-sells-29m-in-stock-93CH-4850732 (확인일 2026-09-14) | 강 |
| SCHW-P2 | Dennis Howard | Chief Technology, Operations and Data Officer | tech_buyer | 2026-01-29 (확대 직책) | https://www.sec.gov/Archives/edgar/data/316709/000119312526029376/d57309dex991.htm (확인일 2026-09-14) | 강 |
| SCHW-P3 | Tom Zick | Director of Responsible AI | champion | 미상 | https://www.linkedin.com/in/tom-zick/ ; https://cyber.harvard.edu/people/tom-zick (확인일 2026-09-14) | 중 |

- SCHW-P1 메모: 2026 회계연도 공시와 인사이더 거래 보도에서 CRO 현직 확인. 좁은 접근 전제에서는 직접 타깃보다 최종 EB.
- SCHW-P2 메모: 2026-01-29 기술, 운영, 데이터 통합 관장 직책으로 확대 임명(8-K). Portfolio Insights(2026-05-05 출시) 이후 프로덕션 GenAI의 기술, 데이터 거버넌스 접점.
- SCHW-P3 메모: Responsible AI 거버넌스 프레임워크 실무(기술, 절차) 담당으로 공개 프로필 확인. 직급이 Director라 EB는 아니나 좁은 접근(AI 거버넌스 기능 단위) 전제의 챔피언 후보로 부합. 발송 전 현직 재확인 권고.
- 미확인: Head of Model Risk와 브로커딜러 Chief Compliance Officer 실명 미확인. SalesNav 쿼리: `Current company: "Charles Schwab" AND Title: ("Model Risk" OR "Model Governance" OR "Chief Compliance Officer") AND Seniority: Director+`

## 6. Edward Jones (US-D8)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| EDJ-P1 | Frank LaQuinta | Principal, Head of Digital, Data and Operations (Technology, Digital Product, Operations, AI, Data 관장) | tech_buyer | 미상 (2018 CIO 취임 후 확대) | https://www.edwardjones.com/us-en/why-edward-jones/news-media/thought-leadership/firm-leadership/frank-laquinta (확인일 2026-09-14) | 강 |
| EDJ-P2 | Kevin Adams | Chief Information Officer / Head of Technology | tech_buyer | 미상 (2021-01 입사, 현 직책 시기 미확인) | https://www.linkedin.com/in/kevinpadams/ ; https://moderncto.io/kevin-adams/ (확인일 2026-09-14) | 중 |

- EDJ-P1 메모: 공식 사이트 리더십 소개에서 AI와 Data를 직무 범위로 명시. "자체 시스템 AI 내재화" 시그널(Q1 2026 업데이트)의 조직 소유자. 챔피언 겸 기술 구매자 성격.
- EDJ-P2 메모: LaQuinta 산하 기술 총괄로 보도(출처 간 직함 표기가 CIO와 Head of Technology로 혼재). 발송 전 직함 재확인 권고.
- 미확인 (1): Chief Risk Officer. 전임 Christopher Van Buren이 2024-06 은퇴한 사실만 확인되고(출처: https://www.fundfornj.org/about/leadership-staff/christopher-van-buren 확인일 2026-09-14) 후임 공개 발표를 찾지 못했다. 비상장 파트너십이라 공개 정보 밀도가 낮다. SalesNav 쿼리: `Current company: "Edward Jones" AND Title: ("Chief Risk Officer" OR "Enterprise Risk") AND Seniority: CXO OR Partner`
- 미확인 (2): 브로커딜러 Chief Compliance Officer 미탐색. SalesNav 쿼리: `Current company: "Edward Jones" AND Title: ("Chief Compliance Officer") `

## 7. U.S. Bancorp (US-B12, 좁은 접근 전제)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| USB-P1 | Jodi Richard | Vice Chair, Chief Risk Officer | EB | 2018 (CRO) | https://www.usbank.com/about-us-bank/company-blog/article-library/us-bank-names-jodi-richard-vice-chair-and-chief-risk-officer.html ; https://www.bloomberg.com/profile/person/20742246 (확인일 2026-09-14) | 강 |
| USB-P2 | Prashant Mehrotra | EVP, Chief AI Officer | tech_buyer | 미상 | https://www.cxotalk.com/bio/prashant-mehrotra-chief-ai-officer-u-s-bank (확인일 2026-09-14) | 중 |

- USB-P1 메모: 직무 범위에 model risk가 명시된 CRO(공식 블로그 소개). "전 사업 라인 AI 에이전트 배포"(2026-05 AWS 발표)와 SR 26-2 별도 거버넌스 공백을 잇는 EB. 좁은 접근 전제에서는 산하 모델리스크 기능이 1차 접점.
- USB-P2 메모: 전사 AI 전략, 실행 총괄. 전 Allstate AI CoE 총괄. 페르소나 (d) Chief AI Officer에 정확히 부합하나 공식 리더십 페이지 확인은 미완이라 적합도 중, 발송 전 재확인 권고.
- 미확인 (1): Head of Model Risk 실명 미확인. SalesNav 쿼리: `Current company: "U.S. Bank" AND Title: ("Model Risk" OR "Model Validation" OR "Chief Model Risk Officer") AND Seniority: SVP+`
- 재확인 필요: Chief Digital Officer는 Dominic Venturo로 알려져 있으나 이번 세션에서 1차 출처 확인을 마치지 못해 표에 넣지 않았다(검색 도구 예산 소진). PO 재확인 항목.

## 8. Western Alliance Bancorporation (US-B15)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| WAL-P1 | Emily Nachlas | Chief Risk Officer | EB | 2019 | https://www.westernalliancebancorporation.com/find-a-banker/emily-nachlas ; https://www.sec.gov/Archives/edgar/data/0001212545/000119312526170399/wal-20260422.htm (확인일 2026-09-14) | 강 |
| WAL-P2 | Sonny Sonnenstein | Chief Information Officer | tech_buyer | 미상 | https://www.westernalliancebancorporation.com/find-a-banker/sonny-sonnenstein (확인일 2026-09-14) | 강 |
| WAL-P3 | Michael Lynch | Chief Technology Officer | tech_buyer | 2021-05 | https://theorg.com/org/western-alliance-bank/org-chart/michael-lynch (확인일 2026-09-14) | 후보 |

- WAL-P1 메모: $50bn 규제 문턱 통과기의 리스크 체계 구축을 이끈 CRO(2019부터). 인베스터 데이의 "리스크 관리 = 경쟁 우위" 서사 소유자로 훅과 직결.
- WAL-P2 메모: 공식 사이트에서 CIO 현직 확인(전 M&T 그룹 CIO, 전 First Horizon 부CIO). 인베스터 데이 기술 어젠다의 실행 라인. 참고: 회사 사이트에 John Peckham도 EVP CIO로 병기된 페이지가 있어 조직 구분(지주 vs 은행 또는 전현직) 재확인 권고.
- WAL-P3 메모: 전 Chief Data Officer 이력에 GenAI 이니셔티브 인큐베이션이 언급되나 제3자 출처(theorg)뿐이라 후보 등급. 발송 전 재확인 필수.
- 미확인: Head of Model Risk 실명 미확인. SalesNav 쿼리: `Current company: "Western Alliance Bank" AND Title: ("Model Risk" OR "Model Validation") AND Seniority: Director+`

## 9. First Horizon (US-B16, 2026-07-23 AI 명시 리더 우선)

| person_id | 이름 | 직함 | 페르소나 | 부임 | 출처 (URL, 확인일) | 적합도 |
|---|---|---|---|---|---|---|
| FHN-P1 | Scott Serpico | SVP, Head of Product | champion | 2026-07-23 (발표) | https://www.prnewswire.com/news-releases/first-horizon-hires-scott-serpico-as-senior-vice-president-head-of-product-302833732.html (확인일 2026-09-14) | 강 |
| FHN-P2 | Catherine Wood | SVP, Head of Commercial Banking Strategy | champion | 2026-07 (승진 발표 2026-07-17) | https://www.prnewswire.com/news-releases/catherine-wood-promoted-to-head-of-commercial-banking-strategy-for-first-horizon-bank-302828633.html (확인일 2026-09-14) | 강 |
| FHN-P3 | Ashley Argo | SEVP, Chief Risk Officer | EB | 미상 (2020 Deputy CRO, 이후 승진) | https://www.firsthorizon.com/first-horizon-corporation/leadership/ashley-argo (확인일 2026-09-14) | 강 |

- FHN-P1 메모: 시그널 당사자(카드, 수신, 여신, 이머징 페이먼트 제품 전략 총괄, AI 활용 명시). 전 USAA 소비자여신 총괄, Ally, Chase, SunTrust 이력. 부임 후 약 7주로 신임 임원 유효창 내. 페르소나 정의(a~d) 밖의 제품 리더이나 캠페인 시그널의 당사자라 champion 후보로 등재, 최종 페르소나 판단은 PO.
- FHN-P2 메모: 시그널 당사자. 상업은행 온보딩, 오리지네이션, 언더라이팅, 서비싱 전반의 고임팩트 AI, 기술 기회 발굴이 직무로 명시된 내부 승진자(15년 이상 재직). FHN-P1과 동일하게 페르소나는 PO 판단.
- FHN-P3 메모: 공식 리더십 페이지에서 CRO 현직 확인(2004년 입사, 2020년부터 Deputy CRO 역임 후 승진). 신임 리더 2인의 AI 유스케이스에 대한 통제 책임의 EB.
- 미확인: Head of Model Risk 실명 미확인(자체 스트레스테스트 모델 체계는 확인됨). SalesNav 쿼리: `Current company: "First Horizon Bank" AND Title: ("Model Risk" OR "Model Validation" OR "Stress Testing") AND Seniority: Director+`

---

## 요약

| 항목 | 수치 |
|---|---|
| 특정 완료 인물 (표 기재) | 22명 (기관당 2~3명, 9개 기관 전부 최소 2명 충족) |
| 적합도 강 | 17명 |
| 적합도 중 | 4명 (FCB-P3, SCHW-P3, EDJ-P2, USB-P2) |
| 적합도 후보 | 1명 (WAL-P3) |
| 미확인 직책 | 10건: 모델리스크 리더 7건 (Truist, PNC, First Citizens, Old National, Schwab, U.S. Bancorp, Western Alliance, First Horizon 중 Schwab 포함 시 8건에서 PNC는 CMRO로 계상, 정확히는 TRU/PNC/FCB/ONB/SCHW/USB/WAL/FHN 8건), Edward Jones CRO 1건, 브로커딜러 CCO 2건 (Schwab, Edward Jones; SCHW는 모델리스크와 합산 중복 없음) |
| 미확인 총계 (직책 기준) | 모델리스크 8건 + Edward Jones CRO 1건 + CCO 2건 = 11건 (전건 SalesNav 쿼리 기재) |

재확인 필요 항목 (PO 또는 차기 세션):

1. U.S. Bancorp Chief Digital Officer (Dominic Venturo로 알려짐): 1차 출처 확인 미완으로 미기재. 확인 시 USB 3인째로 추가.
2. USB-P2 Mehrotra, FCB-P3 Kaduskar, SCHW-P3 Zick, EDJ-P2 Adams, WAL-P3 Lynch: 제3자 출처 중심이라 발송 전 LinkedIn 현직, 직함 재확인.
3. Western Alliance CIO 표기 병존(Sonnenstein vs Peckham 페이지): 조직 구분 확인.
4. Truist Kapireddy: 2025~2026 보도 기준 현직으로 판단했으나 2026년 하반기 단독 확인 출처는 없음.
5. 신임 임원 유효창 관리: FCB-P1 Eklund(2026-06-01 부임)는 부임 105일째로 유효창(30~120일) 마감 임박. 우선 처리 권고.

G1/G4/G9 관련:

- 본 문서는 인물 특정 산출물이며 발송 승인, 앵글 선택, 보류 해제와 무관하다. 해당 결정은 전부 PO 전속.
- email 필드: 전 레코드 [PO/도구]. 이메일 추정치 없음.
- 각 계정의 발송 보류 판정(research/ 산출물)은 이 문서로 변경되지 않는다.
