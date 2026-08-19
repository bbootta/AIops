# 마스터 시퀀스: 미국 은행 (SR 26-2 앵커)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/master-us-banks.md`
> 작성: cold-email-writer · 기준일: 2026-08-19 · 상태: 마스터 초안 (outreach-qa 검수 대기)
> **발송 불가: 이 파일은 마스터 버전이다. `{{...}}` 치환자 미충전 상태로는 어떤 터치도 발송할 수 없다.** 충전 → outreach-qa 재검수 → compliance 게이트 → PO 승인 순서를 지킨다 [G1][G3][G4]. 공통 규칙은 `00-index.md`.

## 0. 세그먼트 정의

- 앵커(Why Now): **연준 SR 26-2 (2026-04-17 발효, SR 11-7 대체).** 생성형·에이전틱 AI를 지침 범위 밖에 두고 별도 거버넌스 프레임워크 필요를 명시. 전통 모델 독립검증 기대는 유지.
- 타깃 역할: CRO, Head of Model Risk, Head of Model Validation, Head of AI Governance / Responsible AI (icp-draft §7)
- 관할·푸터: US · CAN-SPAM (물리 주소 + 수신거부, §8)
- 앵커 검증 상태: EC-regwind-usuk-01 [확인]. 단 **legal-team 규제 해석 확인 전 대외 발송 금지** (카드 §5).

## 1. 터치맵 슬롯 (G11)

| 터치 | Day | 채널 | 실행 | 카피 | 스레드 |
|---|---|---|---|---|---|
| T1 | 1 | Email 1 (PAS) | 발송 도구 | §2 | 새 스레드 |
| L1 | 3 | LinkedIn 커넥션 노트 | **PO** | §6.1 | - |
| T2 | 5 | Email 2 (BAB) | 발송 도구 | §3 | 같은 스레드 (Re:) |
| C1 | 8 | 전화 → 보이스메일 | **PO** | §7 | - |
| T3 | 12 | Email 3 (가치 제공) | 발송 도구 | §4 | 같은 스레드 (Re:) |
| T4 | 18 | Email 4 (브레이크업) | 발송 도구 | §5 | 새 스레드 |

이메일 4통 + LinkedIn 1 + 전화 1 = 6터치 / 18일. 이메일 단독 5터치 아님 [G11].

## 2. Email T1 (Day 1 · PAS · 새 스레드)

제목줄 후보 3개 (전부 소문자, internal camouflage):

1. `sr 26-2 and model inventory` (5단어) · 선택 근거: 규제 레터명이 곧 시그널 키워드. 동료가 보낸 내부 메일처럼 읽힘. 기본 추천.
2. `generative ai governance question` (4단어) · 앵커를 모르는 수신자에게도 직무 관련성이 즉시 보임.
3. `{{account}} model validation` (3~4단어) · 계정명 결합형. 계정 축약형이 2단어 이하일 때만 사용.

본문:

```
Hi {{first_name}},

{{signal_hook}}

SR 26-2, in force since April 2026, keeps independent validation
expectations for your traditional models and places generative and
agentic AI outside its scope, pointing to a separate governance
framework. That gap tends to land on validation teams already at
capacity.

We build RYNTA for exactly this layer: a deterministic engine computes,
AI agents assist, and accountable humans approve every material outcome.

Worth a look at how that maps to your {{role_context}} agenda?

{{sender_name}}
[푸터: §8]
```

<!-- 앵커 문단: EC-regwind-usuk-01 (legal-team 확인 대기) -->
<!-- RYNTA 서술: EC-rynta-arch-01 (아키텍처 서술만, 성능·준수 보장 주장 없음) -->

- 단어 수: 고정 76 + {{signal_hook}} 12~25 = **88~101** (50~125 충족)
- CTA 1개 (interest-based, 미팅 요청 아님). 링크 0.

## 3. Email T2 (Day 5 · BAB · 같은 스레드 Re:)

제목줄: `re:` (T1 선택 제목 상속)

본문:

```
{{first_name}}, one more angle on this.

Right now, validation is periodic: sampled outputs, point-in-time
reviews, a queue that grows faster than it clears. Imagine each
material model rerun and checked continuously, every result logged for
audit, your reviewers deciding instead of recomputing.

Evaluation at that scale is our background: when the Korea Exchange ran
its financial language model competition, roughly 233 teams submitted
over 1,100 models, judged on KRX-Bench, the benchmark we co-developed
with the exchange.

Is continuous validation on your roadmap this year?
```

<!-- 증거 문단: EC-krx-bench-01 (카드 승인 영문 문구 준수: "roughly 233 teams", "over 1,100 models") -->

- 단어 수: **84**. Before(현재 주기적 검증) → After(상시 재계산·로깅) → Bridge(평가 역량 실증). 새 가치 = 제3자 검증 증거.
- CTA 1개, 링크 0.

## 4. Email T3 (Day 12 · 가치 제공형 · 같은 스레드 Re:)

본문:

```
{{first_name}}, sharing something useful whether or not we ever talk.

We put together a two-page note on SR 26-2 for validation leads: what
changed from SR 11-7, where generative and agentic AI now sit, and the
questions your examiners are likely to raise about your AI inventory
first.

Reply "send it" and it's in your inbox: I keep links and attachments
out of cold threads.
```

<!-- 규제 내용: EC-regwind-usuk-01 (SR 11-7은 "대체된 구 지침"으로만 언급, 현행 인용 아님) -->
<!-- 발송 전 조건: two-page note 실물 제작 필수 (00-index §5-6) -->

- 단어 수: **65**. 새 가치 = 규제 시사점 요약 제공. 링크 0 (reply-to-receive).
- CTA 1개 (자료 수신 여부 확인).

## 5. Email T4 (Day 18 · 브레이크업 · 새 스레드)

제목줄 후보 3개: 1. `closing the loop` (3단어, 기본 추천: 관용적·저마찰) 2. `last note from me` (4단어) 3. `parking this for now` (4단어)

본문:

```
{{first_name}}, closing this out: it doesn't look like a priority on
your side right now, and that's a fair answer.

Two things stay open. The two-page SR 26-2 note is yours whenever you
want it, and this thread will reach me if the picture changes: a
one-word reply covers either.

Good luck with the {{role_context}} work this year.
```

- 단어 수: **59**. 죄책감 유발 문구 없음 ("여러 번 연락드렸는데" 류 금지 준수). 문 열어두기 + 마지막 가치 1개. CTA 1개(통합형).

## 6. LinkedIn (실행: PO)

### 6.1 커넥션 노트 (Day 3, 300자 이내)

```
Hi {{first_name}}, your remit at {{account}} touches what we work on:
auditable AI governance and continuous model validation. We
co-developed a financial language model with the Korea Exchange
(ACL 2025). No pitch, just adjacent worlds. Glad to connect.
```

<!-- EC-krx-acl2025-01 -->
- 치환자 충전 후 300자(공백 포함) 이내 확인. 계정명이 길면 "your remit" 뒤 문구를 줄인다.

### 6.2 후속 DM (커넥션 수락 후, 권장 Day 8~10)

```
Thanks for connecting, {{first_name}}. I emailed you about the separate
governance framework SR 26-2 expects for generative and agentic AI.
Short version: a deterministic engine computes, AI assists, accountable
humans approve, everything logged. Is that a live topic for your team
this quarter?
```

<!-- EC-regwind-usuk-01 · EC-rynta-arch-01 -->

## 7. 전화 (Day 8, 실행: PO)

### 7.1 오프닝 (15초)

```
Hi {{first_name}}, this is {{caller_name}} from OneLine AI. I emailed
you about SR 26-2 and the governance gap it flagged for generative and
agentic AI. I have one specific idea on continuous, auditable
validation. Can I take thirty seconds, and you tell me if it's
relevant?
```

### 7.2 보이스메일 (20초)

```
Hi {{first_name}}, {{caller_name}} from OneLine AI. I sent you a couple
of notes on SR 26-2 and making model validation continuous and
auditable. Nothing urgent, no need to call back: I'll follow up by
email. Again, {{caller_name}} at OneLine AI. Thanks.
```

## 8. 법정 푸터 (US · CAN-SPAM · 전 이메일 T1~T4 부착)

```
OneLine AI · {{company_postal_address}}
If you'd rather not hear from me, reply "no thanks" and I won't email
you again.
```

- 물리 주소 필수, 수신거부 수단 발송 후 30일 유효, 처리 10영업일 이내(팀 기준 즉시). 헤더·제목 진실성(주법 소송 리스크) 준수: Re: 위장 없음(T2·T3는 실제 같은 스레드 답장).

## 9. 증거 카드 매핑

| 주장 | 위치 | 카드 |
|---|---|---|
| SR 26-2 발효·범위·별도 거버넌스 지목 | T1, T3, DM, 전화 | EC-regwind-usuk-01 (legal-team 확인 대기) |
| RYNTA 3층 구조(결정론 엔진 + AI 보조 + 인간 승인) | T1, DM | EC-rynta-arch-01 |
| KRX 경진대회 약 233팀·1,100개+ 모델, KRX-Bench 공동개발 | T2 | EC-krx-bench-01 |
| KRX 공동개발 모델 ACL 2025 게재 | LinkedIn 노트 | EC-krx-acl2025-01 |

## 10. 자기점검 (11항목, KB01 §13)

| # | 항목 | 판정 |
|---|---|---|
| 1 | 시그널 게이트 | 조건부: {{signal_hook}} 충전 시 research/§5 훅 사용 강제. 미충전 발송 불가 |
| 2 | 제목줄 2~6단어·소문자·camouflage | PASS (T1 5/4/3~4단어, T4 3~4단어, 스팸 단어 0) |
| 3 | 오프닝 = 상대 관찰 | PASS (T1 첫 문장 {{signal_hook}}, 자기소개·인사치레 없음) |
| 4 | 본문 50~125단어·프레임워크 식별 | PASS (T1 88~101 PAS / T2 84 BAB / T3 65 가치 / T4 59 브레이크업) |
| 5 | you:I 비율 (상대 > 자사) | PASS (터치별 your/you ≥ we/I, T2·T3 경계권이라 QA 재확인 요청) |
| 6 | 증거: 수치·사례 출처 확인 | PASS (수치는 EC-krx-bench-01 승인 문구 그대로) |
| 7 | CTA 정확히 1개·interest-based | PASS |
| 8 | 안티패턴 스캔 (KB01 §9) | PASS (과장·스팸 트리거·죄책감 유발·기능 나열 없음) |
| 9 | 시퀀스 정합성 (터치당 새 가치 1개) | PASS (T1 규제 갭 / T2 검증 실증 / T3 요약 노트 / T4 브레이크업) |
| 10 | 링크 0~1·이미지 0·첨부 0 | PASS (본문 링크 0) |
| 11 | 규제 게이트 | 조건부: legal-team 확인(EC-regwind-usuk-01), G4 보류 해제, 물리 주소 충전 전 발송 불가 |
