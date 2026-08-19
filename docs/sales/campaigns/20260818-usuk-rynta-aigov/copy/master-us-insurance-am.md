# 마스터 시퀀스: 미국 보험(변형 A) · 자산운용(변형 B)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/master-us-insurance-am.md`
> 작성: cold-email-writer · 기준일: 2026-08-19 · 상태: 마스터 초안 (outreach-qa 검수 대기)
> **발송 불가: 이 파일은 마스터 버전이다. `{{...}}` 치환자 미충전 상태로는 어떤 터치도 발송할 수 없다.** 충전 → outreach-qa 재검수 → compliance 게이트 → PO 승인 순서를 지킨다 [G1][G3][G4]. 공통 규칙은 `00-index.md`.

## 0. 세그먼트 정의 (하위 변형 2종)

| | 변형 A: 보험 | 변형 B: 자산운용 |
|---|---|---|
| 앵커 | NAIC AI 모델 불레틴(약 29개 관할 채택) + **12개 주 AI Systems Evaluation Tool 검사 파일럿 (2026-03~09 진행 중)** | SEC FY2026 시험 우선순위 (AI 사용 정책·절차·감독, AI 역량 표현 정확성) |
| 어조 | 규제 검사 국면: 표준 어조 | **한 단계 낮춤**: 구속력 규칙 없음(SEC 예측분석 규칙 철회)을 본문에서 정직하게 인정, 긴급성 연출 금지 |
| 타깃 역할 | CRO, Head of Enterprise Risk, 계리·모델 거버넌스 라인 | CRO, CCO, Head of Investment Risk, AI 리더십 조직 |
| 세그먼트 규칙 | SR 26-2 사용 금지 (research/us-i* 상단 주의) | SR 26-2·NAIC 사용 금지, 규제 강도 과장 금지 (research/us-a* 상단 주의) |

- 앵커 검증 상태: research/us-i1 §2 (NAIC 파일럿, Fenwick 해설) · research/us-a1 §2 (SEC 시험 우선순위, Dorsey 해설). **증거 카드 미등재: 카드 신설 전 발송 금지** (00-index §5-3).
- 관할·푸터: US · CAN-SPAM (§8 공통)

## 1. 터치맵 슬롯 (G11, 변형 A·B 공통)

| 터치 | Day | 채널 | 실행 | 카피 | 스레드 |
|---|---|---|---|---|---|
| T1 | 1 | Email 1 (PAS) | 발송 도구 | §2 | 새 스레드 |
| L1 | 3 | LinkedIn 커넥션 노트 | **PO** | §6.1 | - |
| T2 | 5 | Email 2 (BAB) | 발송 도구 | §3 | 같은 스레드 (Re:) |
| C1 | 8 | 전화 → 보이스메일 | **PO** | §7 | - |
| T3 | 12 | Email 3 (가치 제공) | 발송 도구 | §4 | 같은 스레드 (Re:) |
| T4 | 18 | Email 4 (브레이크업) | 발송 도구 | §5 | 새 스레드 |

## 2. Email T1 (Day 1 · PAS · 새 스레드)

### 2-A. 보험 변형

제목줄 후보 3개:

1. `naic ai evaluation pilot` (4단어) · 선택 근거: 진행 중인 검사 파일럿이 곧 시그널. 기본 추천.
2. `ai governance before exams` (4단어) · 파일럿 미인지 수신자에게도 문제의식 전달.
3. `{{account}} ai inventory` (3~4단어) · 계정 결합형, 축약형 2단어 이하일 때만.

본문:

```
Hi {{first_name}},

{{signal_hook}}

With the NAIC's AI bulletin adopted in roughly 29 jurisdictions and a
12-state examination pilot of its AI Systems Evaluation Tool running
through September 2026, insurer AI governance is turning into an exam
item, not just a policy statement. The awkward part is evidence:
showing how each AI system is inventoried, tested, and overseen.

RYNTA is an assurance layer for that: a deterministic engine computes,
AI assists, and accountable humans approve, with an audit trail
throughout.

Is exam-ready AI evidence something your team is working toward?

{{sender_name}}
[푸터: §8]
```

<!-- 앵커 문단: NAIC 불레틴·12개 주 파일럿. 카드 신설 필요(가칭 EC-regwind-us-ins-01, 원출처 research/us-i1 §2). 카드 확정 전 발송 금지 -->
<!-- RYNTA 서술: EC-rynta-arch-01 -->

- 단어 수: 고정 88 + {{signal_hook}} 12~25 = **100~113** (50~125 충족). CTA 1개, 링크 0.

### 2-B. 자산운용 변형 (어조 한 단계 낮춤)

제목줄 후보 3개:

1. `sec 2026 exam priorities` (4단어) · 선택 근거: 이 세그먼트의 유일한 규제 접점을 그대로. 기본 추천.
2. `ai oversight question` (3단어) · 저자극 초단문.
3. `documenting ai use` (3단어) · 실무 언어, CCO 타깃.

본문:

```
Hi {{first_name}},

{{signal_hook}}

There's no binding model governance rule for asset managers, but the
SEC's FY2026 exam priorities do put AI-use policies, supervision, and
the accuracy of AI claims on the exam agenda. In practice that lands as
a documentation question: showing how AI-assisted work is overseen.

RYNTA is an assurance layer built for that: a deterministic engine
computes, AI assists, humans approve, with an audit trail throughout.

Would a comparison against how you handle this today be useful?

{{sender_name}}
[푸터: §8]
```

<!-- 앵커 문단: SEC FY2026 시험 우선순위. 카드 신설 필요(가칭 EC-regwind-us-bd-01과 공유 가능, 원출처 research/us-a1 §2). "no binding rule" 명시로 규제 강도 과장 금지 준수 -->
<!-- RYNTA 서술: EC-rynta-arch-01 -->

- 단어 수: 고정 78 + {{signal_hook}} 12~25 = **90~103**. CTA 1개(비교 제안형, 긴급성 없음), 링크 0.

## 3. Email T2 (Day 5 · BAB · 같은 스레드 Re:)

### 3-A. 보험 변형 (증거 카드: EC-krx-bench-01)

```
{{first_name}}, a different angle on this.

Today the inventory usually lives in spreadsheets, and testing evidence
is assembled by hand when an exam letter arrives. Picture the reverse:
each model and AI system carries its own controls, test results, and
sign-offs, ready to hand an examiner on any given day.

Our background is evaluation at scale: the Korea Exchange used
KRX-Bench, the benchmark we co-developed, to judge a competition where
roughly 233 teams submitted over 1,100 models.

Worth a look?
```

<!-- EC-krx-bench-01 (승인 문구 준수) -->

- 단어 수: **80**. Before(수기 취합) → After(상시 증거) → Bridge(평가 실증). CTA 1개, 링크 0.

### 3-B. 자산운용 변형 (증거 카드: EC-krx-acl2025-01)

```
{{first_name}}, a different angle on this.

Today, AI oversight often lives in a policy document, with the evidence
trail rebuilt by hand whenever a request arrives. The quieter
alternative: every AI-assisted output already tied to its checks and a
named approver, before anyone asks.

On who we are: we co-developed a finance-specific language model with
the Korea Exchange, peer-reviewed and published at ACL 2025.

Open to seeing how that would look in your setup?
```

<!-- EC-krx-acl2025-01 -->

- 단어 수: **74**. CTA 1개, 링크 0.

## 4. Email T3 (Day 12 · 가치 제공형 · 같은 스레드 Re:)

### 4-A. 보험 변형

```
{{first_name}}, something useful with or without us.

We wrote a two-page note for insurance risk teams on the NAIC AI
Systems Evaluation Tool pilot: the governance and testing questions it
puts in scope, and the evidence worth preparing before your state joins
in.

Reply "send it" and it's in your inbox: I keep links and attachments
out of cold threads.
```

<!-- NAIC 파일럿: EC-regwind-us-ins-01 예정. two-page note 실물 제작 필수 -->

- 단어 수: **60**. 링크 0, CTA 1개.

### 4-B. 자산운용 변형

```
{{first_name}}, something useful with or without us.

We wrote a two-page note for advisers and asset managers on the AI
items in the SEC's FY2026 exam priorities: what examiners are asking
about AI-use policies and supervision, and the documentation worth
having ready before your next exam.

Reply "send it" and it's in your inbox: I keep links and attachments
out of cold threads.
```

<!-- SEC 시험 우선순위: 카드 신설 필요. two-page note 실물 제작 필수 -->

- 단어 수: **63**. 링크 0, CTA 1개.

## 5. Email T4 (Day 18 · 브레이크업 · 새 스레드)

제목줄 후보 3개 (A·B 공통): 1. `closing the loop` (3단어, 기본 추천) 2. `last note from me` (4단어) 3. `parking this for now` (4단어)

### 5-A. 보험 변형

```
{{first_name}}, closing this out: it doesn't look like a priority on
your side right now, and that's a fair answer.

Two things stay open. The two-page NAIC pilot note is yours whenever
you want it, and this thread will reach me if the picture changes: a
one-word reply covers either.

Good luck with the {{role_context}} work this year.
```

- 단어 수: **59**.

### 5-B. 자산운용 변형

```
{{first_name}}, closing this out: it doesn't look like a priority on
your side right now, and that's a fair answer.

Two things stay open. The two-page SEC exam note is yours whenever you
want it, and this thread will reach me if the picture changes: a
one-word reply covers either.

Good luck with the {{role_context}} work this year.
```

- 단어 수: **59**. 죄책감 유발 없음, CTA 1개(통합형).

## 6. LinkedIn (실행: PO)

### 6.1 커넥션 노트 (Day 3, 300자 이내)

A (보험):

```
Hi {{first_name}}, with the NAIC exam pilot underway, your remit at
{{account}} overlaps with what we build: audit-ready AI governance for
insurers. Research background: work with the Korea Exchange, published
at ACL 2025. No pitch, just adjacent worlds. Glad to connect.
```

B (자산운용):

```
Hi {{first_name}}, your AI oversight remit at {{account}} overlaps with
what we build: audit-ready AI governance. Research background: work
with the Korea Exchange, published at ACL 2025. No pitch, just adjacent
worlds. Glad to connect.
```

<!-- EC-krx-acl2025-01 -->
- 치환자 충전 후 300자(공백 포함) 이내 확인.

### 6.2 후속 DM (커넥션 수락 후, 권장 Day 8~10)

A (보험):

```
Thanks for connecting, {{first_name}}. I emailed you about the NAIC's
12-state exam pilot making insurer AI governance an exam item. Short
version: we build the evidence layer, inventory, checks, and sign-offs
in one auditable place. Is exam readiness on your desk this quarter?
```

B (자산운용):

```
Thanks for connecting, {{first_name}}. I emailed you about the AI items
in the SEC's FY2026 exam priorities. Short version: we build the
documentation layer, AI-assisted work tied to its checks and a named
approver. Worth comparing notes sometime this quarter?
```

<!-- 앵커: 신설 카드 예정 · RYNTA: EC-rynta-arch-01 -->

## 7. 전화 (Day 8, 실행: PO)

### 7.1 오프닝 (15초)

A: 

```
Hi {{first_name}}, this is {{caller_name}} from OneLine AI. I emailed
you about the NAIC exam pilot and audit-ready AI governance. I have one
specific idea on exam evidence. Can I take thirty seconds, and you tell
me if it's relevant?
```

B:

```
Hi {{first_name}}, this is {{caller_name}} from OneLine AI. I emailed
you about the SEC's FY2026 exam priorities on AI use. One specific idea
on documentation that holds up in an exam. Can I take thirty seconds,
and you tell me if it's relevant?
```

### 7.2 보이스메일 (20초)

A:

```
Hi {{first_name}}, {{caller_name}} from OneLine AI. I sent you notes on
the NAIC AI exam pilot and audit-ready AI governance for insurers.
Nothing urgent, no need to call back: I'll follow up by email. Again,
{{caller_name}} at OneLine AI. Thanks.
```

B:

```
Hi {{first_name}}, {{caller_name}} from OneLine AI. I sent you notes on
the SEC's FY2026 exam priorities and documenting AI oversight. Nothing
urgent, no need to call back: I'll follow up by email. Again,
{{caller_name}} at OneLine AI. Thanks.
```

## 8. 법정 푸터 (US · CAN-SPAM · 전 이메일 T1~T4 부착)

```
OneLine AI · {{company_postal_address}}
If you'd rather not hear from me, reply "no thanks" and I won't email
you again.
```

## 9. 증거 카드 매핑

| 주장 | 위치 | 카드 |
|---|---|---|
| NAIC 불레틴 약 29개 관할 채택 + 12개 주 파일럿(2026-03~09) | A: T1, T3, DM, 전화 | **카드 신설 필요** (가칭 EC-regwind-us-ins-01, 원출처 research/us-i1 §2) |
| SEC FY2026 시험 우선순위 AI 항목 (구속력 규칙 없음 병기) | B: T1, T3, DM, 전화 | **카드 신설 필요** (원출처 research/us-a1 §2) |
| RYNTA 3층 구조·감사 추적 | T1 (A·B) | EC-rynta-arch-01 |
| KRX 경진대회 약 233팀·1,100개+ 모델 | T2-A | EC-krx-bench-01 |
| ACL 2025 게재 | T2-B, LinkedIn 노트 | EC-krx-acl2025-01 |

## 10. 자기점검 (11항목)

| # | 항목 | 판정 |
|---|---|---|
| 1 | 시그널 게이트 | 조건부: {{signal_hook}} 충전 시 research/§5 훅 사용 강제 |
| 2 | 제목줄 2~6단어·소문자·camouflage | PASS (A 4/4/3~4, B 4/3/3, T4 3~4단어) |
| 3 | 오프닝 = 상대 관찰 | PASS |
| 4 | 본문 50~125단어·프레임워크 식별 | PASS (A: 100~113/80/60/59 · B: 90~103/74/63/59) |
| 5 | you:I 비율 | PASS (경계권 터치는 QA 재확인 요청) |
| 6 | 증거 출처 확인 | 조건부: NAIC·SEC 앵커 카드 신설 전 발송 불가. "약 29개 관할"은 리서치 검증 수치 그대로(반올림 과장 없음) |
| 7 | CTA 정확히 1개·interest-based | PASS (B는 비교 제안형으로 마찰 최소화) |
| 8 | 안티패턴 스캔 | PASS (B에서 긴급성 연출 없음, "no binding rule" 정직 표기) |
| 9 | 시퀀스 정합성 | PASS |
| 10 | 링크 0~1·이미지 0·첨부 0 | PASS (본문 링크 0) |
| 11 | 규제 게이트 | 조건부: 앵커 카드, G4 해제, 주소 충전 전 발송 불가 |
