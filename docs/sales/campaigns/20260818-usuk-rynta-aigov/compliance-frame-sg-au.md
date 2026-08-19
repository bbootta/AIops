# 컴플라이언스 프레임 - SG/AU 국가 확장 · RYNTA AI거버넌스·독립검증 쐐기

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/compliance-frame-sg-au.md`
> 작성: sales-compliance-officer · 기준일: 2026-08-19 · 상태: 초안 (PO 확장 결정에 따른 착수 문서)
> 근거: kb/sales/09 §6(호주 Spam Act), §7.1(싱가포르), §7.2(일본), §8(게이트·매트릭스), §9(벤더), kb/sales/08 §9.2(일본 파트너 채널), harness/sales/team.yaml(G2/G9). KB 부족분은 웹 출처로 보강(§8 출처).
> **이 문서는 법률자문이 아니다.** 내부 게이트 운용 기준이며, 경계 사안은 legal-team 회신 전까지 발송 금지다(fail-closed).

## 0. 판정 요약과 관할 원칙

| 관할 | 판정 | 핵심 조건 |
|---|---|---|
| **싱가포르(SG)** | **가능 (조건 충족 시)** | PDPA 업무 연락처(BCI) 예외 + Spam Control Act 대량(bulk) 기준 밖의 소량 1:1 발송. 대량 도달 시 <ADV> 등 SCA 요건 전면 적용 |
| **호주(AU)** | **조건부 (주소별 증빙 필수)** | conspicuous publication 3요건 충족을 주소 단위로 증빙. 증빙 없는 주소는 발송 금지. 수신거부 5영업일 상한 |
| **일본(JP)** | **콜드 메일 트랙 아님** | 팀 전략상 파트너 채널(민카부) 트랙. §3 참조. channel-strategist 이관 |

- **수신자 소재지(근무지) 법이 기준이다**(KB09 §8.2). 다국적 기관이면 본사가 아니라 그 사람이 앉아 있는 나라. SG / AU 국가 단위로 분리하고 "APAC" 같은 묶음 세그먼트는 금지(G9의 "EU" 금지 규칙과 동일 취지).
- 호주 Spam Act는 "Australian link"(호주에서 접속·수신되는 메시지 등)가 있으면 해외 발송자에게도 적용되고, 싱가포르 SCA도 싱가포르 발신·수신 메시지에 적용된다. 우리(해외 발송자)도 적용 대상이라는 전제로 운용한다.
- 관할 불명 레코드는 회피 등급(fail-closed) 태깅 후 sales-compliance-officer 판정으로 넘긴다(G2). 뉴질랜드 수신자가 혼입되면 호주 기준으로 임시 처리하지 말고 별도 확인한다(KB09 §6.4는 "대체로 정합적"이라 하나 개별 확인 요건이다).

---

## 1. 싱가포르: PDPA + Spam Control Act (두 겹)

### 1.1 PDPA: business contact information(BCI) 예외

- PDPA는 성명·직함·업무용 전화·업무용 이메일·업무용 주소 등 **개인이 업무 목적으로 제공한 연락처(business contact information)를 동의·고지 등 주요 의무(Parts 3~6 층위)의 적용에서 제외**한다(PDPA 제4조 제5항). 이것이 B2B 아웃리치의 법적 통로다(KB09 §7.1).
  - 출처: PDPC 자료·해설 https://www.pdpc.gov.sg/-/media/Files/PDPC/PDF-Files/Advisory-Guidelines/advisoryguidelinesonrequiringconsentformarketing8may2015.pdf , https://sageshield.com/what-is-considered-personal-data-under-pdpa/
- **한계 1: BCI 해당성이 전제다.** "개인이 업무 목적으로 제공한" 연락처여야 한다. 개인 지메일, 업무·개인 혼용 주소, 업무 목적 제공 정황이 불명한 주소는 BCI로 단정하지 않는다(fail-closed로 제외 또는 legal-team 질의).
- **한계 2: PDPA 예외는 SCA를 면제하지 않는다.** 발송 행위 규제(SCA)는 별개 층이다(§1.2).
- **참고: 싱가포르 DNC 레지스트리는 싱가포르 전화번호 대상(음성·SMS·팩스)이며 이메일에는 적용되지 않는다.** 전화·SMS 터치를 넣는 순간 DNC 대조 의무가 생기므로, 이 캠페인의 SG 트랙은 이메일+LinkedIn으로 한정하고 전화 터치는 별도 심사 전 금지한다.
  - 출처: https://marketingagency.sg/pdpa-email-marketing-singapore/

### 1.2 Spam Control Act 2007: "대량(bulk)" 상업 이메일 규제

- 적용 대상은 **대량 발송되는 비청탁 상업 전자 메시지**다. 대량 기준(KB09 §7.1): 동일·유사 내용을 **24시간 내 100통 초과, 30일 내 1,000통 초과, 1년 내 10,000통 초과** 중 하나라도 해당.
  - 출처: 법령 원문 https://sso.agc.gov.sg/Act/SCA2007
- 대량 해당 시 요건(Second Schedule):
  1. 제목란 앞에 **<ADV> 표기**(제목란이 없으면 본문 첫 부분에).
  2. 제목·헤더의 진실성(내용 오인 유발 금지, 헤더 위장 금지).
  3. 발신자에게 실제로 연락 가능한 **정확·유효한 이메일 주소 또는 전화번호**, 유효한 연락처 정보.
  4. **수신거부(unsubscribe) 접수용 이메일 주소 제공**, 수신거부 문구는 영어 포함.
  5. **수신거부 요청 후 10영업일이 지나면 재발송 금지**(법정 상한. 팀 기준은 즉시 처리, §5 게이트 C).
  - 출처: https://singaporelegaladvice.com/law-articles/email-newsletters-comply-singapore-law/ , https://marketingagency.sg/spam-control-act-singapore/
- 제재: SCA는 **민사 소권(법정손해) 구조**를 두고 있어 수신자 측 소 제기가 가능하다. 규모·요건은 확인 필요 항목(§7)으로 관리한다.
  - 출처: https://v1.lawgazette.com.sg/2007-8/feature2.htm

### 1.3 실무 결론과 발송 전 체크리스트 (SG)

**결론: 소량·1:1 맞춤 콜드 메일은 "SCA 대량 기준 밖 + PDPA BCI 예외"로 가능 분류(KB09 §7.1, §8.1). 단 다음 전부 충족이 조건이다.**

- [ ] 수신 주소가 BCI(업무용 이메일·직함 확인)임을 레코드별 확인, 비업무 주소 제외 (G9 필드: `sg_bci_basis`, §4)
- [ ] 시퀀스 자동화 포함 **누적 발송량이 대량 기준(100/24h, 1,000/30d, 10,000/1y)에 접근하는지 모니터링**. "동일·유사 내용" 판단은 문안 변형이 아니라 실질 유사성 기준으로 보수적으로 계산한다
- [ ] 대량 기준 초과가 예상되면 발송 전에 <ADV> 표기 등 §1.2 요건 전면 적용으로 전환하거나 볼륨을 낮춘다. "초과 후 소급 적용"은 없다(fail-closed)
- [ ] 대량 여부와 무관하게 헤더·제목 진실성, 발신자 식별, 유효 연락처, 작동하는 수신거부 수단은 기본 탑재(글로벌 위생 기준)
- [ ] 수신거부 처리: 법정 상한 10영업일이지만 팀 기준 즉시(자동화), 글로벌 통일 상한 5영업일 이하(KB09 §1.6, §6.3)
- [ ] 전화·SMS 터치 금지(DNC 미대조 상태), LinkedIn 터치는 플랫폼 약관 층위로 별도 관리

---

## 2. 호주: Spam Act 2003 (동의 + 식별 + 수신거부)

### 2.1 3요건 체제

상업적 전자 메시지 1통 단위로 **(a) 동의(consent), (b) 발신자 식별, (c) 작동하는 수신거부 수단** 전부 충족(KB09 §6.1). 동의는 명시적(express) 또는 추정적(inferred)이며, **동의 존재의 입증 책임은 발송자에게 있다.**
- 출처: ACMA https://www.acma.gov.au/avoid-sending-spam

### 2.2 inferred consent: conspicuous publication의 정확한 요건과 한계

콜드 메일에서 쓸 수 있는 통로는 사실상 conspicuous publication 하나다(Spam Act Schedule 2). 성립 요건 3가지를 **모두** 충족해야 한다(KB09 §6.2):

1. 수신자의 **업무용 이메일 주소가 눈에 띄게 공개**되어 있다(회사 웹사이트, 공개 디렉토리 등). 임직원·이사 등 **직책 보유자의 업무 주소**에 한정된다.
2. 게시에 **"비청탁 상업 메시지 사절" 류의 문구가 붙어 있지 않다.**
3. 메시지 주제가 **그 사람의 역할·직무와 직접 관련(directly related to the role or function)** 된다.
- 출처: ACMA https://www.acma.gov.au/avoid-sending-spam , https://www.nortonrosefulbright.com/en/knowledge/publications/5615dd36/dont-filter-this-out-are-you-spam-act-compliant , https://smtpedia.com/spam-act-2003/

**한계(전부 게이트에 반영):**

- **주소 단위 증빙 의무**: "공개돼 있었다"를 주소별로 출처 URL·캡처·수집일·직무 관련성 메모로 문서화한다. 기록 없으면 예외를 주장할 수 없다(KB09 §1.5, §6.4). 증빙 필드가 빈 레코드는 자동 제외(G9).
- **벤더 리스트의 함정**: ZoomInfo·Cognism 등에서 내려받은 주소는 "본인 또는 권한자가 공개 게시"했는지 벤더 데이터만으로 입증되지 않는다. **원 게시 위치(회사 웹사이트 등)를 직접 재확인해 URL·캡처를 채우지 못하면 그 주소는 발송 금지**다.
- **주소 하베스팅 금지**: 주소 수집 소프트웨어(harvesting)로 모은 주소는 사용 금지 대상이다. 소스 계보가 불명하면 하베스팅 여부를 확인할 수 없으므로 제외한다.
- **직무 관련성은 좁게 본다**: 이 캠페인이라면 문안(RYNTA 독립검증·AI 거버넌스)이 수신자의 공개된 역할(CRO, Head of Model Risk, AI Governance 등)과 직접 관련됨을 카피가 스스로 입증해야 한다. 관련성이 한 문장으로 설명되지 않는 직책은 대상에서 뺀다.
- **지속 조건**: 이 유형의 inferred consent는 게시가 철회되거나 사절 문구가 붙거나 수신거부 의사가 오면 소멸한다. 터치 2~N마다 suppression 델타 재대조(G2)가 그래서 필수다.

### 2.3 메일 요건과 제재

- **발신자 식별 정보는 발송 후 30일간 정확·유효**해야 한다(KB09 §6.3).
- **수신거부: 5영업일 이내 처리**(미국 10영업일보다 짧다). 수신거부 수단은 발송 후 최소 30일 유효, 무료(통상 요금 외 비용 금지). 글로벌 자동화 상한을 5영업일 이하로 맞춘다(팀 기준 즉시).
- 제재: 법원 벌금은 벌금 단위(penalty unit)에 연동되며, 2024년 기준 자료로 전과 없는 법인 일 최대 약 63만 호주달러, **반복 위반 법인 일 최대 약 313만 호주달러** 수준(벌금 단위 인상에 따라 변동, KB09 §6.3의 "단일 위반 22만 호주달러"는 구 단가 기준으로 읽는다).
  - 출처: https://privacy108.com.au/insights/top-acma-penalties-2024-2025/ , https://www.holdingredlich.com/time-to-revisit-your-marketing-settings-recent-penalties-for-breaching-spam-law
- 집행 실적: Commonwealth Bank 750만 호주달러(2024-10, 2023년 355만에 이은 2차 제재), Latitude Finance 396만(2025), Kmart 130만(2023). **ACMA 집행 패턴은 "동의 없는 발송"보다 수신거부 미처리·수신거부 후 재발송에서 터진다**(KB09 §6.3). suppression 자동화가 핵심 방어선이다.
  - 출처: https://www.acma.gov.au/articles/2024-10/commonwealth-bank-pays-75m-more-spam-breaches , https://www.acma.gov.au/articles/2023-11/kmart-pays-13m-penalty-spam-breaches , https://www.businessnewsaustralia.com/articles/latitude-finance-hit-with-4-million-penalty-for-breaching-spam-laws.html

### 2.4 실무 판단: AU B2B 콜드 메일이 "조건부 가능"이 되는 정확한 조건

아래 6개 전부 충족 시에만 발송 후보다. 하나라도 미충족이면 해당 레코드는 발송 금지(레코드 단위 fail-closed)다.

1. 주소가 **회사 웹사이트 등 공개 위치에 본인·권한자에 의해 게시된 직책 보유자의 업무용 주소**이고, 원 게시 위치를 우리가 직접 확인했다(`au_publication_url` + 캡처).
2. 게시 위치에 **상업 메시지 사절 문구가 없음을 확인**하고 확인일을 기록했다(`au_no_optout_confirmed`, `au_publication_checked_date`).
3. 문안 주제가 수신자의 **공개된 역할·직무와 직접 관련**되며, 관련성 한 줄 메모가 레코드에 있다(`au_role_relevance_note`).
4. 메일 1통 단위로 발신자 식별(30일 정확·유효)과 무료 수신거부 수단(30일 유효)이 들어 있다.
5. 수신거부·답장·하드바운스·신고 발생 시 **즉시 전 채널 시퀀스 제외**가 자동화되어 있고(상한 5영업일, 목표 즉시), 터치 2~N마다 suppression 델타 재대조를 통과한다(G2).
6. 소스 계보가 깨끗하다: 하베스팅·스크래핑 소스 배제, 벤더 주소는 원 게시 재확인 완료.

**시퀀스 운용 주의**: 각 터치가 독립적으로 3요건을 충족해야 한다. 무응답 상대에 대한 터치 수는 터치맵 표준(이메일 3~4통, G11) 안에서 보수적으로 운용하고, 사절 신호(자연어 회신 포함)는 즉시 소멸 사유로 처리한다.

---

## 3. 일본 참고 절: 콜드 메일 트랙이 아니다

- 일본은 team.yaml상 조건부 국가이고 KB09 §7.2상 공표 주소 예외로 "조건부 가능"이지만, **팀 전략상 일본은 콜드 메일 트랙이 아니라 파트너 채널 트랙이다**(KB08 §9.2): 원라인AI의 일본 모션은 민카부(도쿄증권거래소 상장) 채널 주도이며, 일본은 전시회·대면 신뢰 중심 문화라 콜드메일 단독 모션은 비효율이라는 것이 팀 판단이다.
- 따라서 이 캠페인(및 후속 확장)에서 **JP 레코드가 콜드 메일 큐에 들어오면 발송하지 않고 channel-strategist의 파트너 채널 플레이(민카부 소개 기반 미팅, 전시회)로 이관**한다. 특정전자메일법 게이트 설계는 파트너 채널로도 해소되지 않는 예외 수요가 실제 발생할 때 별도 문서로 착수한다.

---

## 4. G9 스키마 추가 필드 (SG/AU 레코드)

list-build-spec §1.2 인물 레코드에 다음을 추가한다. **빈 필드 레코드는 발송 큐 진입 불가(G9).** SG/AU는 GDPR 관할이 아니므로 LIA(G10) 대상은 아니지만, 그 대신 아래 수신 근거·증빙 필드가 같은 강도로 요구된다.

### 4.1 공통

| 필드 | 필수 | 값/규칙 | 채우는 주체 |
|---|---|---|---|
| jurisdiction | Y | `SG` / `AU` (근무지 기준) 값 허용 추가 | researcher |
| consent_basis | Y | SG: `pdpa_bci_sca_smallvolume` / AU: `inferred_conspicuous_publication` (express 동의 확보 시 `express`) | researcher / compliance-officer |
| data_source · collected_date | Y | 기존 필드 그대로. 하베스팅·계보 불명 소스는 기입 불가 = 제외 | PO(도구) / researcher |

### 4.2 SG 전용

| 필드 | 필수 | 값/규칙 |
|---|---|---|
| sg_bci_basis | Y | 업무용 연락처(BCI) 판단 근거 한 줄: 업무용 도메인 + 직함 + 업무 목적 제공 정황. 불명이면 공란 = 제외 |
| sg_bulk_counter_ref | Y | 캠페인 누적 발송량 카운터 참조(게이트 C 볼륨 모니터링 연결) |

### 4.3 AU 전용 (증빙 5종, 하나라도 비면 제외)

| 필드 | 필수 | 값/규칙 |
|---|---|---|
| au_publication_url | Y | 주소가 공개 게시된 페이지 URL(본인·권한자 게시, 벤더 페이지 불인정) |
| au_publication_capture | Y | 게시 화면 캡처 파일 경로 |
| au_publication_checked_date | Y | 게시·사절 문구 부재 확인일(발송 시점과 간격이 크면 재확인) |
| au_no_optout_confirmed | Y | "상업 메시지 사절" 문구 부재 확인 Y |
| au_role_relevance_note | Y | 직무 관련성 한 줄(문안 앵글과 연결) |

---

## 5. 게이트 A/B/C 체크리스트: SG/AU 행 추가안

기준은 KB09 §8.3·G2의 3층 게이트(A 리스트 / B 메시지 / C 운영)다. US/UK 프레임(compliance-frame.md §4)은 리서치 층위를 게이트 C로 두고 운영을 D로 표기했으므로, 그 문서 체계에 편입할 때 아래 "게이트 C(운영)" 행은 게이트 D에 넣는다.

### 게이트 A: 리스트 층위 (추가 행)
- [ ] SG/AU: jurisdiction 근무지 기준 태깅, 묶음 세그먼트 부재, 관할 불명 0건(있으면 회피 등급 이관)
- [ ] SG: sg_bci_basis 전건 기입(비업무 주소·불명 주소 제외)
- [ ] AU: 증빙 5필드(§4.3) 전건 기입, 빈 레코드 자동 제외
- [ ] AU: 벤더 추출 주소의 원 게시 위치 재확인 완료(재확인 불가 주소 제외)
- [ ] SG/AU: 하베스팅·스크래핑 소스 배제 확인(data_source 계보 점검)
- [ ] SG/AU: 전역 + 도메인 레벨 suppression 대조 완료
- [ ] NZ 등 인접 관할 혼입 여부 점검(있으면 분리 후 개별 확인)

### 게이트 B: 메시지 층위 (추가 행)
- [ ] 공통: 헤더·제목 진실성, 발신자 실명·회사명, 유효 연락처(이메일 또는 전화)
- [ ] SG: 대량 기준 초과 계획 시 <ADV> 표기 + 물리 주소·연락처 + 영어 수신거부 문구(§1.2). 소량 트랙이면 <ADV>는 불요하나 수신거부 수단은 탑재
- [ ] AU: 발신자 식별 정보가 발송 후 30일간 정확·유효하도록 도메인·서명 구성 확인
- [ ] AU: 문안이 수신자 역할과의 직접 관련성을 스스로 입증(au_role_relevance_note와 대조)

### 게이트 C: 운영 층위 (추가 행)
- [ ] 수신거부 자동 처리: 목표 즉시, 글로벌 상한 5영업일 이하(AU 5영업일 < SG 10영업일 법정 상한)
- [ ] AU: 수신거부 수단 발송 후 30일 유효 확인
- [ ] SG: 누적 발송량 모니터링(100/24h, 1,000/30d, 10,000/1y). 임계 80% 도달 시 알림, 초과 예상 시 사전 전환 판단
- [ ] 터치 2~N: 발송 직전 suppression 델타 재대조, 수신거부·답장·하드바운스·신고 레코드 전 채널 제외(G2)
- [ ] 게이트 통과 기록 docs/sales/compliance/ 보존(감사 대비)

**게이트는 fail-closed다.** 하나라도 미충족이면 발송 불가. 발송·터치 실행은 PO 몫이며 에이전트는 발송하지 않는다(G1).

---

## 6. 요건 조견표 (SG / AU)

| 항목 | 싱가포르 | 호주 |
|---|---|---|
| 사전 동의 | 불요(PDPA BCI 예외 + SCA 대량 기준 밖) | 필요(conspicuous publication으로 추정 가능) |
| 수신 근거 증빙 | BCI 판단 근거(권장을 넘어 팀 필수) | **주소별 증빙 5종 필수** |
| 광고 표기 | <ADV>(대량 해당 시) | 없음 |
| 물리 주소·연락처 | 유효 연락처 필수(대량 시 명시 요건) | 발신자 식별 정보 필수(30일 유효) |
| 수신거부 처리 | 법정 10영업일(팀 기준 즉시) | **법정 5영업일**(팀 기준 즉시) |
| 위반 리스크 | 벌금 + 민사 소권(법정손해) | 반복 위반 법인 일 최대 약 313만 AUD, ACMA 집행 활발 |

---

## 7. 미해결·경계 사안 (legal-team 에스컬레이션 후보)

경계 사안에 걸린 레코드만 분리 보류하고 잔여 레코드로 부분 진행한다. 보류 레코드는 회신 전 발송 금지.

| # | 사안 | 관할 | 처리 |
|---|---|---|---|
| 1 | **LinkedIn 프로필에만 공개된 주소가 conspicuous publication에 해당하는지**(플랫폼 로그인 장벽·약관 층위 문제 포함) | AU | 해당 레코드 보류, legal-team 질의 |
| 2 | **벤더 제공 주소의 inferred consent 성립 여부**: 원 게시 재확인이 안 되는 주소를 벤더의 "공개 소스" 주장만으로 쓸 수 있는가. 팀 기본값은 불가(발송 금지)이며, 예외 필요 시에만 질의 | AU | 기본 제외. 예외 수요 시 legal-team |
| 3 | SCA "동일·유사 내용" 판단 단위: 시퀀스 자동화의 문안 변형(A/B, 터치별 변형)이 대량 산정에서 하나로 합산되는지 | SG | 보수적 합산으로 운용하되 legal-team 확인 |
| 4 | SCA 민사 소권·법정손해의 요건과 규모(해외 발송자 상대 집행 가능성 포함) | SG | 리스크 평가용 질의(발송 차단 사유는 아님) |
| 5 | 벤더 수집 주소의 PDPA BCI 해당성: "개인이 업무 목적으로 제공한" 요건을 벤더 경유 수집이 충족하는지 | SG | 업무용 도메인+직함 확인으로 운용하되 경계 사례 발생 시 질의 |
| 6 | 뉴질랜드(UEMA 2007) 수신자 혼입 시 취급: 호주 기준 준용 가능 범위 | NZ | 혼입 발생 시 분리 보류 후 질의(KB09 §6.4) |
| 7 | 호주 벌금 단위 현행 단가와 상한 최신화(2026년 기준 재확인) | AU | 규제 모니터링 항목, 분기 갱신 |

---

## 8. 이 문서에서 보강한 출처 (2026-08-19 검색 기준)

**싱가포르**
- Spam Control Act 2007 원문(Singapore Statutes Online): https://sso.agc.gov.sg/Act/SCA2007
- 이메일 뉴스레터와 싱가포르법(SingaporeLegalAdvice): https://singaporelegaladvice.com/law-articles/email-newsletters-comply-singapore-law/
- Spam Control Act 가이드(Marketing Agency SG): https://marketingagency.sg/spam-control-act-singapore/
- PDPA 이메일 마케팅(Marketing Agency SG): https://marketingagency.sg/pdpa-email-marketing-singapore/
- PDPC 마케팅 동의 자문 가이드라인(PDF): https://www.pdpc.gov.sg/-/media/Files/PDPC/PDF-Files/Advisory-Guidelines/advisoryguidelinesonrequiringconsentformarketing8may2015.pdf
- PDPA 개인정보 범위 해설(SageShield): https://sageshield.com/what-is-considered-personal-data-under-pdpa/
- SCA 2007 해설(Law Gazette): https://v1.lawgazette.com.sg/2007-8/feature2.htm

**호주**
- ACMA 공식 가이드(Avoid sending spam): https://www.acma.gov.au/avoid-sending-spam
- Spam Act 컴플라이언스(Norton Rose Fulbright): https://www.nortonrosefulbright.com/en/knowledge/publications/5615dd36/dont-filter-this-out-are-you-spam-act-compliant
- Spam Act 2003 가이드(SMTPedia): https://smtpedia.com/spam-act-2003/
- ACMA, Commonwealth Bank 750만 호주달러(2024-10): https://www.acma.gov.au/articles/2024-10/commonwealth-bank-pays-75m-more-spam-breaches
- ACMA, Kmart 130만 호주달러(2023-11): https://www.acma.gov.au/articles/2023-11/kmart-pays-13m-penalty-spam-breaches
- Latitude Finance 396만 호주달러(Business News Australia): https://www.businessnewsaustralia.com/articles/latitude-finance-hit-with-4-million-penalty-for-breaching-spam-laws.html
- ACMA 제재 상위 사례 2024~2025(Privacy108): https://privacy108.com.au/insights/top-acma-penalties-2024-2025/
- 최근 Spam Act 제재 동향(Holding Redlich): https://www.holdingredlich.com/time-to-revisit-your-marketing-settings-recent-penalties-for-breaching-spam-law

---

## 9. compliance-officer / PO 결정 대기

- [ ] SG/AU 트랙 착수 승인과 볼륨 상한(SG 대량 기준 대비 목표 볼륨) 확정 - PO
- [ ] AU 증빙 수집 절차(원 게시 재확인) 리소스 배정 - PO·prospect-researcher
- [ ] 경계 사안 §7-1, 2, 3 legal-team 질의 발송 - sales-compliance-officer(초안) → PO
- [ ] JP 레코드 파트너 채널 이관 - channel-strategist
- [ ] 발송 실행·수신거부 파이프라인 운영(상한 5영업일, 목표 즉시) - PO
