# 마스터 시퀀스: 싱가포르 (MAS AIRG 확정 임박 앵커)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/master-sg.md`
> 작성: cold-email-writer · 기준일: 2026-08-19 · 상태: 마스터 초안 (outreach-qa 검수 대기)
> **발송 불가: 이 파일은 마스터 버전이다. `{{...}}` 치환자 미충전 상태로는 어떤 터치도 발송할 수 없다.** 충전 → outreach-qa 재검수 → compliance 게이트 → PO 승인 순서를 지킨다 [G1][G3][G4]. 공통 규칙은 `00-index.md`.

## 0. 세그먼트 정의

- 앵커(Why Now): **MAS AI 리스크 관리 가이드라인(AIRG): 컨설테이션 2025-11-13, 확정 임박(2026-08-05 국회 답변), 12개월 전환기간 제안, 전 금융기관 대상.**
- 타깃 역할: CRO, Head of Risk, Head of Technology Risk (디지털 은행·자산관리 플랫폼)
- 관할·푸터: SG · PDPA BCI 예외 + Spam Control Act 소량 트랙 (§8)
- 앵커 검증 상태: research/sg-s1 §2 (MAS 공식 컨설테이션 페이지 출처). **증거 카드 미등재: 카드 신설(가칭 EC-regwind-sg-01) 전 발송 금지** (00-index §5-4).
- **채널 제한: 전화·SMS 터치 금지** (DNC 미대조, compliance-frame-sg-au §1.1). C1 슬롯은 LinkedIn DM으로 대체. 이 파일에 전화 스크립트는 없다.
- 볼륨 감시: 시퀀스 자동화 포함 누적 발송량이 SCA 대량 기준(100/24h, 1,000/30d, 10,000/1y)의 80% 도달 시 알림. 초과 예상 시 <ADV> 요건 전면 적용 또는 볼륨 축소로 사전 전환 (§8 비고).
- 영국식 철자(finalising 등) 유지: 싱가포르 비즈니스 영어 관행.

## 1. 터치맵 슬롯 (G11, SG 조정판)

| 터치 | Day | 채널 | 실행 | 카피 | 스레드 |
|---|---|---|---|---|---|
| T1 | 1 | Email 1 (PAS) | 발송 도구 | §2 | 새 스레드 |
| L1 | 3 | LinkedIn 커넥션 노트 | **PO** | §6.1 | - |
| T2 | 5 | Email 2 (BAB) | 발송 도구 | §3 | 같은 스레드 (Re:) |
| C1 | 8 | ~~전화~~ → **LinkedIn DM으로 대체** | **PO** | §6.2 | - (전화 금지: compliance-frame-sg-au §1.1) |
| T3 | 12 | Email 3 (가치 제공) | 발송 도구 | §4 | 같은 스레드 (Re:) |
| T4 | 18 | Email 4 (브레이크업) | 발송 도구 | §5 | 새 스레드 |

- 대체는 터치 추가가 아니라 동일 슬롯의 채널 교체다 [G11]. channel-strategist 확인 요청 사항으로 표기.

## 2. Email T1 (Day 1 · PAS · 새 스레드)

제목줄 후보 3개:

1. `mas ai guidelines timeline` (4단어) · 선택 근거: 확정 임박 + 전환기간이 곧 시그널. 리스크 직군의 내부 메일처럼 읽힘. 기본 추천.
2. `airg transition planning` (3단어) · 규정 약칭 인지 수신자용 초단문.
3. `{{account}} ai risk readiness` (4~5단어) · 계정 결합형, 축약형 2단어 이하일 때만.

본문:

```
Hi {{first_name}},

{{signal_hook}}

MAS consulted on its AI risk management guidelines in November 2025 and
has signalled finalisation is near, with a 12-month transition
proposed. Twelve months sounds generous until you map it against every
AI system already in production and the evidence each one needs.

RYNTA is an assurance layer for exactly that: a deterministic engine
computes, AI agents assist, accountable humans approve, with an audit
trail throughout.

Is AIRG readiness on your agenda yet?

{{sender_name}}
[푸터: §8]
```

<!-- 앵커 문단: MAS AIRG 컨설테이션·확정 임박·12개월 전환기간. 카드 신설 필요(가칭 EC-regwind-sg-01, 원출처 research/sg-s1 §2: MAS 공식 페이지). 카드 확정 전 발송 금지 -->
<!-- RYNTA 서술: EC-rynta-arch-01 -->

- 단어 수: 고정 75 + {{signal_hook}} 12~25 = **87~100** (50~125 충족). CTA 1개, 링크 0.

## 3. Email T2 (Day 5 · BAB · 같은 스레드 Re:)

본문:

```
{{first_name}}, one more angle on this.

Most teams will meet the guidelines the manual way: spreadsheets for
the AI inventory, screenshots for the evidence, a scramble each time a
review lands. The alternative is an assurance layer where controls and
sign-offs accumulate as a by-product of daily use.

On who we are: we co-developed a finance-specific language model with
the Korea Exchange, peer-reviewed and published at ACL 2025.

Worth a look?
```

<!-- 증거 문단: EC-krx-acl2025-01 -->

- 단어 수: **71**. Before(수기 대응) → After(상시 축적) → Bridge(연구 실증). CTA 1개, 링크 0.

## 4. Email T3 (Day 12 · 가치 제공형 · 같은 스레드 Re:)

본문:

```
{{first_name}}, something useful with or without us.

We keep a short readiness note on the MAS AI risk management guidelines
for risk teams at digital-first institutions: the likely scope, what a
12-month transition actually leaves time for, and a one-page evidence
checklist. We work across Asia already, including a live commercial
collaboration with Tokyo Stock Exchange-listed Minkabu.

Reply "send it" and it's in your inbox: I keep links and attachments
out of cold threads.
```

<!-- MAS 내용: EC-regwind-sg-01 예정 · 민카부 협업: EC-minkabu-01 ("독점·투자" 표현 없음 준수) -->
<!-- 발송 전 조건: readiness note 실물 제작 필수 (00-index §5-6) -->

- 단어 수: **74**. 새 가치 = 준비 노트 + 아시아 운영 실증. 링크 0. CTA 1개.

## 5. Email T4 (Day 18 · 브레이크업 · 새 스레드)

제목줄 후보 3개: 1. `closing the loop` (3단어, 기본 추천) 2. `last note from me` (4단어) 3. `parking this for now` (4단어)

본문:

```
{{first_name}}, closing this out: it doesn't look like a priority right
now, and that's a fair answer.

Two things stay open. The AIRG readiness note is yours whenever you
want it, and this thread will reach me if the picture changes: a
one-word reply covers either.

Good luck with the transition planning.
```

- 단어 수: **52**. 죄책감 유발 없음, 문 열어두기 + 마지막 가치 1개, CTA 1개(통합형).

## 6. LinkedIn (실행: PO)

### 6.1 커넥션 노트 (Day 3, 300자 이내)

```
Hi {{first_name}}, with MAS finalising its AI risk guidelines, your
remit at {{account}} overlaps with what we build: audit-ready AI
governance. Research background: work with the Korea Exchange,
published at ACL 2025. No pitch, just adjacent worlds. Glad to connect.
```

<!-- EC-krx-acl2025-01 -->
- 치환자 충전 후 300자(공백 포함) 이내 확인.

### 6.2 LinkedIn DM (Day 8, C1 슬롯 대체 · 커넥션 수락 전이면 수락 후로 순연)

```
Thanks for connecting, {{first_name}}. I emailed you about MAS's AI
risk management guidelines and the proposed 12-month transition. Short
version: an assurance layer where controls and sign-offs accumulate as
a by-product of daily use. Is AIRG readiness on your desk yet?
```

<!-- 앵커: EC-regwind-sg-01 예정 · RYNTA: EC-rynta-arch-01 -->

## 7. 전화

**작성하지 않음.** SG 트랙은 이메일 + LinkedIn 한정. 전화·SMS 터치는 DNC 레지스트리 미대조 상태에서 금지 (compliance-frame-sg-au §1.1). 전화 필요 시 별도 심사 후 재작성.

## 8. 법정 푸터 (SG · 소량 트랙 · 전 이메일 T1~T4 부착)

```
{{sender_name}}, OneLine AI · {{company_postal_address}}
If you'd prefer not to receive further email from me, reply
"unsubscribe" (or write to {{unsubscribe_email}}) and I'll stop
straight away.
```

- 소량 1:1 트랙 기준: 발신자 식별 + 유효 연락처 + 작동하는 수신거부(영어 문구). 법정 처리 상한 10영업일이나 팀 기준 즉시.
- **대량 기준(100/24h, 1,000/30d, 10,000/1y) 초과가 예상되면 발송 전에 제목란 앞 `<ADV>` 표기 등 SCA 요건 전면 적용으로 전환한다. 소급 적용 없음(fail-closed).**
- 레코드별 `sg_bci_basis`(업무용 이메일·직함 확인) 미기입 시 발송 큐 진입 불가 (G9).

## 9. 증거 카드 매핑

| 주장 | 위치 | 카드 |
|---|---|---|
| MAS AIRG 컨설테이션·확정 임박·12개월 전환기간 | T1, T3, DM | **카드 신설 필요** (가칭 EC-regwind-sg-01, 원출처 research/sg-s1 §2) |
| RYNTA 3층 구조·감사 추적 | T1, DM | EC-rynta-arch-01 |
| KRX 공동개발 모델 ACL 2025 게재 | T2, LinkedIn 노트 | EC-krx-acl2025-01 |
| 도쿄증권거래소 상장 민카부와 상용 협업 | T3 | EC-minkabu-01 |

## 10. 자기점검 (11항목)

| # | 항목 | 판정 |
|---|---|---|
| 1 | 시그널 게이트 | 조건부: {{signal_hook}} 충전 시 research/§5 훅 사용 강제 |
| 2 | 제목줄 2~6단어·소문자·camouflage | PASS (4/3/4~5단어, T4 3~4단어, 스팸 단어 0) |
| 3 | 오프닝 = 상대 관찰 | PASS |
| 4 | 본문 50~125단어·프레임워크 식별 | PASS (T1 87~100 PAS / T2 71 BAB / T3 74 / T4 52) |
| 5 | you:I 비율 | PASS (T3는 자사 언급 2회로 경계권, QA 재확인 요청) |
| 6 | 증거 출처 확인 | 조건부: MAS 앵커 카드 신설 전 발송 불가 |
| 7 | CTA 정확히 1개·interest-based | PASS |
| 8 | 안티패턴 스캔 | PASS (12개월 전환기간을 가짜 긴급성으로 연출하지 않음: 사실 서술 + 준비 관점) |
| 9 | 시퀀스 정합성 | PASS. C1 채널 대체는 channel-strategist 확인 요청 |
| 10 | 링크 0~1·이미지 0·첨부 0 | PASS (본문 링크 0) |
| 11 | 규제 게이트 | 조건부: SG 트랙 착수 PO 승인, BCI 필드, 볼륨 카운터, 카드 신설 전 발송 불가 |
