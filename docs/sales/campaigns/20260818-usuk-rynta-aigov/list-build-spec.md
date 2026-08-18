# 리스트 구축 사양 - US/UK · RYNTA AI거버넌스·독립검증 쐐기

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/list-build-spec.md`
> 작성: prospect-researcher · 기준일: 2026-08-18 · 상태: 초안
> 근거: kb/sales/03 §3~4(소스·워터폴), §3.3(검증), kb/sales/09 §8.2(관할), §9(벤더·검증 도구)

## 0. 원칙

- **에이전트는 개인 주소를 지어내지 않는다.** 이 문서는 "무엇을, 어느 필드로, 어떤 쿼리로 채우는가"의 사양이다. 실제 개인 이메일은 PO가 검증 도구로 채운다.
- **필수 필드(G9)가 빈 레코드는 발송 큐에 진입할 수 없다.** jurisdiction, 수집 출처, 수집일, 시그널, (UK) 수신 근거·LIA·보관기간 만료일이 그것이다.
- **관할은 국가 단위(US / UK).** "EU" 세그먼트 금지(G9). 관할 불명은 회피 등급으로 태깅해 sales-compliance-officer에 넘긴다(G2).

---

## 1. 레코드 스키마 (G9 필수 필드)

계정 레코드와 인물 레코드를 분리하되, 발송 큐 진입 판정은 인물 레코드 기준이다.

### 1.1 계정 레코드

| 필드 | 필수 | 값/규칙 | 채우는 주체 |
|---|---|---|---|
| account_id | Y | 내부 ID (예: US-B1) | researcher |
| legal_name | Y | 법인 정식명 | researcher |
| entity_type | Y | bank / building_society / broker_dealer / asset_manager / insurer | researcher |
| jurisdiction | Y | `US` 또는 `UK` (국가 단위, EU 금지) | researcher |
| uk_entity_form | UK만 | limited_company / LLP / public_body / **sole_trader** / general_partnership | researcher (Companies House) |
| corporate_subscriber_flag | UK만 | Y(법인 가입자) / N(개인 가입자=sole_trader·일반 파트너십) | researcher |
| regulator_status | Y | US: 감독기관·자산규모 밴드 / UK: PRA 규제·내부모형 승인 여부 | researcher [검증 필요] |
| tier | Y | 1 / 2 / 3 | researcher |
| signal_type | Y | §4 시그널 유형 (없으면 발송 보류) | researcher |
| signal_date | 조건부 | 실측 시그널 발생일 (없으면 공란 + 보류) | researcher |
| signal_source_url | 조건부 | 실측 출처 URL | researcher |
| negative_icp_checked | Y | Y + 확인자 (icp-draft §6 대조) | researcher |
| research_artifact_path | Tier1~2 | 계정 리서치 산출물 경로(30일 이내) | researcher |
| hold_status | Y | hold / released (해제는 PO만) | researcher / PO |

### 1.2 인물 레코드

| 필드 | 필수 | 값/규칙 | 채우는 주체 |
|---|---|---|---|
| person_id | Y | 내부 ID | researcher |
| account_id | Y | 소속 계정 | researcher |
| full_name | Y | 실명 | PO(도구) / researcher |
| title | Y | 직함 (§3 페르소나 필터) | researcher |
| persona_role | Y | EB / champion / tech_buyer / gatekeeper | researcher |
| jurisdiction | Y | `US` / `UK` (근무지 기준, 본사 아님. KB09 §8.2) | researcher |
| email | 발송 전 | **researcher가 지어내지 않음.** PO가 검증 도구로 채움 | **PO(도구)** |
| email_status | 발송 전 | valid / catch-all / invalid / role (검증 결과) | PO(도구) |
| email_verified_date | 발송 전 | 검증일 (90일 초과 시 재검증, KB03 §3.4) | PO(도구) |
| data_source | Y | 벤더명·추출 경로 (US: ZoomInfo / UK: Cognism 등) | PO(도구) |
| collected_date | Y | 수집일 | PO(도구) |
| consent_basis | Y | US: CAN-SPAM(옵트아웃, 근거=상업적 메시지) / UK: legitimate_interest(LIA) | researcher / compliance-officer |
| lia_document_id | UK만 | LIA 문서 ID (**sales-compliance-officer 공급**) | **compliance-officer** |
| lia_retention_expiry | UK만 | 보관기간 만료일 (**compliance-officer 공급**) | **compliance-officer** |
| suppression_checked | 발송 전 | Y + 대조 일시 (전역 + 도메인 레벨) | PO(도구) / researcher |

**발송 큐 진입 게이트(G9):** jurisdiction, data_source, collected_date, signal_type이 비면 진입 불가. UK 레코드는 추가로 corporate_subscriber_flag=Y, lia_document_id, lia_retention_expiry가 채워져야 한다. 관할 불명은 진입 불가(회피 등급 → compliance-officer).

---

## 2. 워터폴 (데이터 소스 순서)

단일 소스로 커버리지·정확도·최신성을 다 만족하는 벤더는 없다(KB03 §3.1, §4.1). 국가별로 강점 소스를 앞세운다.

### 2.1 US 워터폴

1. **ZoomInfo** (1차): 북미 엔터프라이즈·금융기관 커버리지 최강(KB03 §3.1). 직함·부서·회사 firmographic 확보.
2. 보강: LinkedIn Sales Navigator로 직함·부임 시기·인물 이동 교차 확인(이메일 미제공, KB03 §3.1).
3. 미발견 레코드: 버리지 말고 전화·LinkedIn·소개 트랙으로 이관(KB03 §4.1).
4. 각 단계 결과는 다음 단계 전에 이메일 검증(§5)으로 확인.

### 2.2 UK 워터폴

1. **Cognism** (1차): EMEA 강점, 전화 검증 모바일(KB03 §3.1). UK 금융기관 인물·직함 확보.
2. 보강: Companies House로 법인 형태(limited/LLP/sole_trader) 확인 → corporate_subscriber_flag 결정.
3. 보강: LinkedIn Sales Navigator로 근무지(jurisdiction)·직함 교차 확인.
4. 미발견 레코드: LinkedIn 커넥션·소개·이벤트 트랙으로 이관.

주의: 어느 소스든 10% 내외는 죽은 데이터다(KB03 §3.1). 벤더 유효율 수치를 절대값으로 믿지 않는다.

---

## 3. 페르소나별 직함 필터 (Boolean 쿼리 예시)

icp-draft §7 구매위원회 직함으로 검색한다. 아래는 도구 검색용 예시이며, 실제 실행·개인 특정은 PO다.

### 3.1 경제적 구매자 (CRO)
```
("Chief Risk Officer" OR "Group CRO" OR "Deputy CRO" OR "Head of Risk")
```

### 3.2 사용자 챔피언 - 모델리스크·독립검증
```
("Head of Model Risk" OR "Head of Model Risk Management" OR "Model Risk Management"
 OR "Head of Model Validation" OR "Head of Independent Validation"
 OR "Model Validation" OR "Independent Model Review")
```

### 3.3 사용자 챔피언 - AI 거버넌스
```
("Head of AI Governance" OR "AI Governance" OR "Responsible AI"
 OR "Head of Responsible AI" OR "AI Risk" OR "AI Assurance")
```

### 3.4 기술 구매자 (CDO/CDAO·IT)
```
("Chief Data Officer" OR "Chief Data and Analytics Officer" OR "CDAO"
 OR "Head of Data Science" OR "Head of Analytics")
```

### 3.5 절차 관문 (CISO·Compliance)
```
("CISO" OR "Chief Information Security Officer" OR "Head of Information Security"
 OR "Chief Compliance Officer" OR "Head of Compliance")
```

### 3.6 결합 필터 (계정 한정 + 페르소나)
```
company:("Nationwide Building Society")
AND ( [§3.1] OR [§3.2] OR [§3.3] OR [§3.4] OR [§3.5] )
AND location:("United Kingdom")   # jurisdiction 근무지 기준
```

멀티스레딩(KB03 §7.1): Tier 1은 거부권 보유자(CRO·CISO·Compliance) 포함 3~5명, Tier 2는 2~3명. 역할이 겹치면 더 엄격한 관문 우선.

---

## 4. 시그널 필드 채우기

- signal_type은 icp-draft §4의 6종(신임 CRO/Head of Model Risk, Responsible AI 채용, SR 26-2/SS1/23 대응, AI Act/AI 거버넌스 언급, 생성형 AI 도입, 감독 지적) 중 실측된 것.
- 실측 전에는 signal_type=`to_verify`, signal_date·signal_source_url 공란, hold_status=`hold`.
- 탐지 소스: LinkedIn Jobs·기관 채용 페이지(채용), 보도·IR·뉴스룸(임원·규제·생성형 AI), 감독기관 공표(지적). 시그널 발생 시 계정 레코드에 (유형·일자·출처)를 적재(KB03 §5.3).

---

## 5. 이메일 검증 절차 (발송 전 게이트, KB03 §3.3)

1. 전량 검증 도구(ZeroBounce/NeverBounce/MillionVerifier 등) 통과. `valid`만 1차 발송 대상.
2. catch-all 분리: 콜드 본대에서 제외하거나 별도 저볼륨 트랙.
3. role 계정 제거: info@·compliance@·riskoffice@ 등 원칙 제외.
4. 중복·경합 제거: 기존 고객·진행 딜·최근 90일 접촉·동료 담당 계정 대조.
5. negative ICP 필터(icp-draft §6.1) 적용 후 제거.
6. 바운스 상한: 캠페인 바운스 2% 미만, 하드바운스 1% 미만. 5% 도달 시 발송 중단·재검증.
7. **검증 도구의 GDPR 유의(KB09 §9.3): UK(및 EU) 주소를 미국·인도 서버 도구에 올리면 개인정보 처리 위탁 + 역외 이전이다.** EU 리전 처리 옵션 또는 무저장 방식 도구를 우선하고, 업로드 파일은 이메일 최소 필드로 줄이며, 도구와 DPA를 체결한다. 이 판단은 PO·compliance-officer 항목이다.

---

## 6. GDPR·벤더 유의점 (KB09 §9, UK 레코드)

- 벤더(Cognism 등)에서 UK 프로스펙트를 추출하는 순간 **우리 팀이 컨트롤러**다. 벤더의 "GDPR compliant" 배지가 우리 의무를 대신하지 않는다(KB09 §9.1).
- 우리가 이행할 것: (a) 자체 LIA(compliance-officer 공급), (b) UK GDPR 제14조 고지(1개월 또는 최초 접촉 중 빠른 쪽), (c) 보관기간 관리(lia_retention_expiry), (d) 반대·삭제 요청 대응, (e) 벤더 DPA 체결.
- 벤더 선정 체크(KB09 §9.2): 커뮤니티 소싱 기반 데이터(Apollo·Lusha 계열)는 GDPR 논란이 크고, ZoomInfo·Cognism은 컴플라이언스 문서가 상대적으로 정비된 편(업계 평가). 추출 데이터에 수집일·출처 필드를 강제한다.

---

## 7. suppression 대조

- 전역 마스터 + 도메인 레벨 억제 리스트와 대조(KB09 §8.4). 도구별 개별 관리 금지(사고 최다 유형).
- 수신거부·바운스·퇴사 확인·스팸 신고 주소는 삭제가 아니라 suppression 처리.
- 대조 완료 시 suppression_checked=Y + 일시 기록. 미대조 레코드는 발송 큐 진입 불가.

---

## 8. PO / compliance-officer 결정 대기

- [ ] 데이터 소스·검증 도구 선택 확정(US ZoomInfo / UK Cognism 및 검증 도구, DPA 포함) - PO
- [ ] UK LIA 승인 및 lia_document_id·lia_retention_expiry 공급 - sales-compliance-officer
- [ ] 개인 이메일 채우기 실행(검증 도구) - PO
- [ ] 검증 도구 역외 이전 적법화(EU 리전/무저장/SCC) 판정 - PO·compliance-officer
