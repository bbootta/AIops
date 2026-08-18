# 리스트 빌딩 사양: 미국·영국 금융기관 (린타 / Rinta)

> 저장 경로: `docs/sales/campaigns/20260818-us-uk-rinta-fin/list-build-spec.md`
> 작성: prospect-researcher · 기준일: 2026-08-18 · 근거: KB03 §3·§4, KB09 §4·§8·§9, G9·G10

## 배너

- 이 문서는 **주소를 어떻게 채우고 검증하는지의 사양**이다. **실존 개인의 이메일 주소를 여기서 만들지 않는다.** 주소는 PO가 검증 도구로 채운다. 본 사양은 (a) G9 스키마, (b) 데이터 소스와 추출 방법, (c) 검증 절차, (d) 페르소나별 직무·직함 필터를 정의한다.
- **관할은 US·UK만.** 인물 근무지 기준으로 판정하며(KB09 §8.2), 다국적 기업은 본사가 아니라 그 사람이 앉아 있는 나라 기준. 관할 불명 레코드는 회피 등급으로 태깅해 sales-compliance-officer에 넘긴다(G2). 임의로 발송 가능 분류 금지.
- **"EU" 단일 세그먼트 금지.** 이번 캠페인은 US·UK만 다루므로 EU 레코드가 잡히면 국가 단위로 분리해 별도 심사로 이관한다(G9).

---

## 1. G9 필수 필드 스키마

빈 값이 하나라도 있으면 그 레코드는 **발송 큐 진입 불가(G9, fail-closed)**. `[PO/도구]`는 PO가 검증 도구로 채우는 값, `[compliance]`는 sales-compliance-officer가 공급하는 값, `[researcher]`는 prospect-researcher가 채우는 값이다.

| 필드 | 필수 | 값 규칙 | 담당 |
|---|---|---|---|
| company | 필수 | 법인 정식명 | [researcher] |
| domain | 필수 | 회사 도메인 | [researcher] |
| industry | 필수 | 버티컬(자산운용/시장데이터/퀀트/리서치 등) | [researcher] |
| firm_size | 필수 | 정성(대형/중대형) 또는 공개 지표. 추정치는 지어내지 않음 | [researcher] |
| icp_score | 필수 | icp-draft §8 룰 적용값 | [researcher] |
| tier | 필수 | 1/2/3 (배정 승인 sales-lead) | [researcher] |
| person_name | 필수 | 인물명. 페르소나 필터로 특정 | [PO/도구] |
| title | 필수 | 직함 | [PO/도구] |
| persona_role | 필수 | Champion / EB / Tech Validator / Gatekeeper / Sponsor (icp-draft §7) | [researcher] |
| **jurisdiction** | **필수(G9)** | **US 또는 UK.** 근무지 기준. 불명 시 회피 등급 태깅 후 제외 | [researcher] |
| email | 발송 전 필수 | **여기서 생성 금지.** PO가 검증 도구로 채움 | [PO/도구] |
| email_verification_status | 발송 전 필수 | valid / catch-all / role / invalid | [PO/도구] |
| verification_date | 발송 전 필수 | YYYY-MM-DD. 90일 경과 시 재검증 전 발송 금지(KB03 §3.4) | [PO/도구] |
| **data_source (수집 출처)** | **필수(G9)** | 벤더명 + 추출 URL/화면. 커뮤니티 소싱 여부 기록 | [PO/도구]+[researcher] |
| **collection_date (수집일)** | **필수(G9)** | YYYY-MM-DD | [PO/도구] |
| **signal_latest (시그널)** | **필수(G9)** | 최신 시그널 종류. 계정 리서치 산출물과 연동 | [researcher] |
| signal_date | 필수 | YYYY-MM-DD. 유효기간(KB03 §5.2) 내여야 함 | [researcher] |
| signal_source_url | 필수 | 시그널 출처 URL. 지어내지 않음 | [researcher] |
| **receipt_basis (수신 근거)** | **필수(G9)** | US: `CAN-SPAM opt-out (corporate B2B)`. UK: `corporate subscriber (PECR Reg22 exempt) + UK GDPR legitimate interest(LIA-ID)` | [researcher]+[compliance] |
| corporate_subscriber_flag | UK 필수 | Ltd/PLC/LLP/공공기관 확인 시 true. 개인사업자·일반 파트너십 = false → N6 배제(G9/KB09 §4.1) | [researcher] |
| **lia_doc_id** | **UK 필수(G9/G10)** | `LIA-YYYYMMDD-UK-NN`. **sales-compliance-officer가 공급** | [compliance] |
| **retention_expiry_date** | **UK 필수(G9/G10)** | 마지막 접촉 + 3년. **sales-compliance-officer가 공급** | [compliance] |
| avoid_grade_flag | 필수 | 관할 불명·회피 등급 여부. true면 콜드 큐 제외 | [researcher] |
| contact_history | 필수 | 최근 접촉·수신거부 이력. suppression 대조 결과 | [PO/도구] |

정리:
- **US 레코드**: LIA·보관기간 필드는 해당 없음(N/A). receipt_basis = CAN-SPAM 옵트아웃. 메시지 층위(물리 주소·수신거부)는 compliance-frame.md.
- **UK 레코드**: corporate_subscriber_flag=true 확인 + lia_doc_id + retention_expiry_date가 채워져야 발송 큐 진입 가능(G9·G10). 이 두 값은 **prospect-researcher가 임의 생성하지 않고 sales-compliance-officer가 공급**한다.

---

## 2. 데이터 소스와 추출 방법 (워터폴)

KB03 §4.1: 단일 소스로 커버리지·정확도·최신성을 다 만족하는 벤더는 없다. 저렴·정확한 소스 먼저, 각 단계 검증 후 다음 단계. 미발견 레코드는 버리지 않고 LinkedIn/소개 트랙으로.

| 순서 | 소스 | 용도 | US/UK 유의 |
|---|---|---|---|
| 1 | LinkedIn Sales Navigator | 인물·직함·근무지·이직 추적의 표준. 관할 판정(근무지) 1차 소스 | 이메일 미제공. 직함·근무지 확정용 |
| 2 | Cognism | EMEA(UK) 커버리지·전화 검증 강함. **UK 레코드 1차 권장** | KB09 §9.2: 고지·DNC 대조 등 컴플라이언스 문서 상대적 정비 |
| 3 | ZoomInfo | 북미(US) 엔터프라이즈 커버리지 최강. **US 레코드 1차 권장** | 컴플라이언스 문서 상대적 정비(§9.2) |
| 4 | Apollo.io | 가성비 보강. 커뮤니티 소싱 기반이라 **EU/UK 개인정보 GDPR 논란 상대적으로 큼**(§9.2) | UK 레코드는 Apollo 단독 근거로 쓰지 않음. 보강용 |
| 5 | Clay | 워터폴 허브 + 시그널(job-change) 모니터링 + AI 리서치 | 크레딧 비용·환각 주의. 훅 문장은 사람 최종 검수(KB03 §6.3) |
| 6 | Companies House (UK) | **UK 법인 가입자 확인**(Ltd/LLP/PLC). corporate_subscriber_flag 근거 | 개인사업자·일반 파트너십 걸러내기(N6) |
| 7 | 공개 소스(회사 사이트/IR/뉴스룸/arXiv/ACL/Hugging Face) | 계정 인리치먼트, 시그널, "이미 우리를 알 만한 곳" 인접성 | Tier 1~2 딥다이브 |

**직무 추출 쿼리 설계(예시, Boolean 스타일):**
- User Champion: `(title:"Head of" OR "Director" OR "Lead") AND (research OR "data science" OR quant OR "machine learning" OR NLP) AND (Asia OR APAC OR equity OR investment)`
- Economic Buyer: `title:("Chief Data Officer" OR "Head of Data" OR "Head of Innovation" OR "Head of Investment Technology")`
- Technical Validator: `title:("Head of ML Engineering" OR "Head of Data Engineering" OR "CISO" OR "Head of Model Risk")`
- Procedural Gatekeeper: `title:("Vendor Management" OR "Third-Party Risk" OR "Procurement" OR "Model Risk Management")`

각 추출 레코드에 `data_source`(벤더 + 추출 URL/화면)와 `collection_date`를 즉시 태깅(KB09 §9.2, G9 연동). 커뮤니티 소싱 여부를 기록해 UK 레코드의 GDPR 판단에 넘긴다.

---

## 3. GDPR / UK GDPR 유의점 (UK 레코드, KB09 §9)

UK 프로스펙트를 벤더에서 추출하는 순간 **우리 팀이 컨트롤러**가 된다. 벤더의 "GDPR compliant" 배지가 우리 의무를 대신하지 않는다(§9.1). 이행 사항:

1. **DPA 체결**: 사용하는 각 벤더(Cognism/ZoomInfo/Apollo/Clay)와 데이터 처리 계약. (§9.2)
2. **LIA**: UK 레코드는 PO 승인 LIA 없이 발송 큐 진입 불가(G10). 초안은 sales-compliance-officer가 `templates/sales/lia-record.md`로 작성, PO가 승인. lia_doc_id를 전 UK 레코드 필드에 기록(G9).
3. **제14조 고지**: 본인 아닌 소스에서 수집했으므로 최초 접촉 시 또는 수집 후 1개월 중 빠른 쪽에 고지. 첫 메일 푸터에 출처 + 프라이버시 노티스 링크(메시지 층위, compliance-frame.md).
4. **데이터 최소수집**: 목적(직무 관련 B2B 제안) 달성에 필요한 최소 필드만. 검증 도구에는 **이메일만** 업로드(성명 등 제외).
5. **검증 도구 역외 이전**: 미국·인도 서버 검증 도구에 UK 주소를 올리면 SCC 등 이전 장치 필요. **EU 리전 처리 옵션(ZeroBounce EU 등) 또는 데이터 미저장 도구(Dropcontact 등) 우선**, 도구와 DPA 체결(§9.3). 이 항목은 sales-compliance-officer 심사·기록 대상(게이트 A).
6. **보관기간**: 마지막 접촉 + 3년. retention_expiry_date 필드 강제, 만료 레코드는 삭제·익명화(G10).
7. **반대권**: 마케팅 반대는 절대적 권리. 즉시 중단·suppression 등록.

회피 등급 국가(특히 DE) 프로스펙트는 **추출 자체를 최소화**한다(갖고만 있어도 GDPR 의무 발생, §9.2). 이번 캠페인은 US·UK만이므로 EU 레코드가 잡히면 추출 단계에서 배제한다.

---

## 4. 검증 절차 (발송 전 게이트, KB03 §3.3 · G5)

- [ ] **이메일 전량 검증**: ZeroBounce/NeverBounce/Prospeo 등. `valid`만 1차 발송 대상. UK 레코드는 EU 리전/미저장 도구 우선(§3.5 위).
- [ ] **catch-all 분리**: catch-all 도메인 주소는 본대에서 제외하거나 별도 저볼륨 트랙(하드바운스 폭탄 방지).
- [ ] **role 계정 제거**: info@, sales@, admin@ 등 원칙 제외(답장률 낮고 신고율 높음). 검증 실패 예상 레코드(catch-all·role)는 리스트 빌드 단계에서 선제 제외.
- [ ] **바운스 상한**: 캠페인 바운스율 목표 2% 미만, 하드바운스 1% 미만. 5% 도달 시 발송 중단·재검증(G5·G6).
- [ ] **suppression 대조**: 글로벌 + 도메인 레벨 마스터 suppression 리스트 대조(기존 고객·진행 딜·최근 90일 접촉·수신거부). 우회 불가(G2·KB09 §8.4).
- [ ] **negative ICP 필터**: N1~N7 해당 계정·인물 제거(점수 무관). (UK) 개인사업자·일반 파트너십(N6) Companies House 재확인.
- [ ] **검증일 90일 규율**: 90일 경과 레코드는 재검증 전 발송 금지(KB03 §3.4).

주의: 검증 통과는 **도달성**이지 **적법성**이 아니다(KB09 §9.3). 검증 통과가 관할·LIA 게이트(A)를 대체하지 않는다.

---

## 5. 페르소나별 타깃 직무·직함 (US/UK 금융기관)

인물명은 넣지 않는다. 아래 직함으로 §2 쿼리를 돌려 특정한다. 진입은 User Champion(연구 훅), 거부권 3인(Tech Validator·Gatekeeper·Sponsor 중 보안·조달·모델리스크)을 먼저 매핑(icp-draft §7).

| 페르소나 | 직함 필터(US/UK) | 접근 우선순위 |
|---|---|---|
| User Champion (진입점) | Head of Asia Research, Head of Equity Research (Asia/EM), Head of Data Science, Quant Research Lead, Head of Investment Research, NLP/ML Research Lead | 1순위. 연구 자산(ACL·KMMLU·KRX) 훅 |
| Economic Buyer | Chief Data Officer, Head of Data & Analytics, Head of Investment Technology, Head of Innovation, COO of Research | 2순위. 디자인 파트너 KPI·사례 교환 |
| Technical Validator | Head of ML Engineering, Head of Data Engineering, CISO, Head of Information Security, Head of Model Risk | 병렬. 온프레미스·데이터 주권·모델 리스크 |
| Procedural Gatekeeper | Vendor Management, Third-Party Risk (TPRM), Procurement, Legal, Compliance, Model Risk Management | 후행. 존속성·인증(SOC 2 [확인 필요]) |
| Executive Sponsor | CTO, Chief Data Officer, Head of Investments | Tier 1 다인 커버 시 |

계정당 접촉 인원(KB03 §7.1): Tier 1 = 3~5명+(구매위원회 커버), Tier 2 = 2~3명, Tier 3 = 1~2명.

---

## 6. PO 결정 대기 항목 (이 문서 관련)

1. **시작 데이터 소스 선택**: US 1차 = ZoomInfo, UK 1차 = Cognism 권고(§2). Apollo는 UK 단독 근거 배제 권고. PO 확정.
2. **검증 도구 선택**: UK 레코드용 EU 리전/미저장 도구 확정(§3.5). DPA 체결 주체·범위.
3. **인물 특정·주소 수집 실행 승인**: 페르소나 필터(§5)로 인물 특정과 주소 채우기·검증은 PO/도구 몫(G1). prospect-researcher는 사양·직함까지만.
4. **N3 근접 퀀트 계정 접근 여부**(target-accounts §7과 연동).

**판정란(PO 전용, 비워 둠):** 소스 선택 = ______ · 검증 도구 = ______ · PO 서명 ______ · 날짜 ______
