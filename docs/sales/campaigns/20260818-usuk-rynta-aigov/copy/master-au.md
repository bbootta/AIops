# 마스터 시퀀스: 호주 (APRA AI 서한 + CPS 230 앵커)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/master-au.md`
> 작성: cold-email-writer · 기준일: 2026-08-19 · 상태: 마스터 초안 (outreach-qa 검수 대기)
> **발송 불가: 이 파일은 마스터 버전이다. `{{...}}` 치환자 미충전 상태로는 어떤 터치도 발송할 수 없다.** 충전 → outreach-qa 재검수 → compliance 게이트 → PO 승인 순서를 지킨다 [G1][G3][G4]. 공통 규칙은 `00-index.md`.

## 0. 세그먼트 정의

- 앵커(Why Now): **APRA AI 서한 (2026-04-30): 거버넌스·어슈어런스가 AI 도입 속도를 못 따라간다, 시점·표본 기반 어슈어런스의 한계 지적** + **CPS 230 (운영 리스크 관리)** 국면.
- 타깃 역할: CRO, Head of Model Risk, Head of Operational Risk (APRA 인가 ADI·미드티어)
- 관할·푸터: AU · Spam Act 3요건 (동의 + 발신자 식별 + 수신거부, §8)
- 앵커 검증 상태: research/au-b1·b2·b4 §2 (MinterEllison·Clayton Utz 해설 출처, 2차 해설임에 유의). **증거 카드 미등재: 카드 신설(가칭 EC-regwind-au-01)·원문 대조 전 발송 금지** (00-index §5-5).
- 발송 선결 (레코드 단위 fail-closed): conspicuous publication 증빙 5필드(`au_publication_url` 등) 전건 기입, 벤더 주소 원 게시 재확인, 하베스팅 소스 배제 (compliance-frame-sg-au §2.4). **카피가 직무 관련성을 스스로 입증해야 하므로 {{role_context}}·{{signal_hook}}는 `au_role_relevance_note`와 정합해야 한다.**
- 주의: 감독 조치 직후 계정(예: 정비 프로그램 진행 기관)은 접근 톤·타이밍이 PO 판단 사항. 수신자 기관이 규제 위반 상태라는 단정·암시 금지.

## 1. 터치맵 슬롯 (G11)

| 터치 | Day | 채널 | 실행 | 카피 | 스레드 |
|---|---|---|---|---|---|
| T1 | 1 | Email 1 (PAS) | 발송 도구 | §2 | 새 스레드 |
| L1 | 3 | LinkedIn 커넥션 노트 | **PO** | §6.1 | - |
| T2 | 5 | Email 2 (BAB) | 발송 도구 | §3 | 같은 스레드 (Re:) |
| C1 | 8 | 전화 → 보이스메일 | **PO** | §7 | 텔레마케팅(DNCR) 층위 확인 대기 (00-index §5-8) |
| T3 | 12 | Email 3 (가치 제공) | 발송 도구 | §4 | 같은 스레드 (Re:) |
| T4 | 18 | Email 4 (브레이크업) | 발송 도구 | §5 | 새 스레드 |

- 각 이메일 터치가 독립적으로 Spam Act 3요건을 충족해야 한다: 전 메일 푸터 부착 + 터치 2~N 발송 직전 suppression 델타 재대조 [G2].

## 2. Email T1 (Day 1 · PAS · 새 스레드)

제목줄 후보 3개:

1. `apra's ai letter` (3단어) · 선택 근거: 리스크 직군 전원이 아는 문서명. 관찰형·저자극. 기본 추천.
2. `continuous assurance question` (3단어) · 서한의 핵심 개념을 직무 언어로.
3. `cps 230 and ai models` (5단어) · 운영 리스크 직군 타깃 전용.

본문:

```
Hi {{first_name}},

{{signal_hook}}

APRA's April 2026 letter was unusually direct: governance and assurance
are not keeping pace with AI adoption, and point-in-time, sample-based
assurance has limits. With CPS 230 already reshaping operational risk,
the question becomes what continuous assurance looks like in practice.

RYNTA is our answer: a deterministic engine recomputes, AI agents
assist with investigation and explanation, and accountable humans
approve, with an audit trail throughout.

Worth a look at how that sits alongside your current assurance model?

{{sender_name}}
[푸터: §8]
```

<!-- 앵커 문단: APRA AI 서한·CPS 230. 카드 신설 필요(가칭 EC-regwind-au-01, 원출처 research/au-b1·b2 §2, 2차 해설이므로 원문 대조 후 등급 판정). 카드 확정 전 발송 금지 -->
<!-- RYNTA 서술: EC-rynta-arch-01 -->

- 단어 수: 고정 78 + {{signal_hook}} 12~25 = **90~103** (50~125 충족). CTA 1개, 링크 0.

## 3. Email T2 (Day 5 · BAB · 같은 스레드 Re:)

본문:

```
{{first_name}}, one more angle on this.

Sampling-based assurance can say a control worked when it was checked.
Continuous assurance can say it is working now, for every material
model, with the evidence already logged. That difference is exactly
what APRA's letter put on the table.

Evaluation at scale is our background: the Korea Exchange used
KRX-Bench, a benchmark we co-developed, to judge roughly 233 teams and
over 1,100 models in its competition.

Is that shift something your team is weighing?
```

<!-- 증거 문단: EC-krx-bench-01 (승인 수치 그대로) · APRA 언급: EC-regwind-au-01 예정 -->

- 단어 수: **80**. Before(표본 어슈어런스) → After(상시 어슈어런스) → Bridge(평가 실증). CTA 1개, 링크 0.

## 4. Email T3 (Day 12 · 가치 제공형 · 같은 스레드 Re:)

본문:

```
{{first_name}}, something useful with or without us.

We wrote a two-page note for Australian risk teams on APRA's AI letter
read next to CPS 230: where sample-based assurance falls short for AI
models, and a practical sequence for moving specific controls to
continuous checking first.

Reply "send it" and it's in your inbox: I keep links and attachments
out of cold threads.
```

<!-- 규제 내용: EC-regwind-au-01 예정. two-page note 실물 제작 필수 (00-index §5-6) -->

- 단어 수: **62**. 새 가치 = 규제 시사점 요약. 링크 0. CTA 1개.

## 5. Email T4 (Day 18 · 브레이크업 · 새 스레드)

제목줄 후보 3개: 1. `closing the loop` (3단어, 기본 추천) 2. `last note from me` (4단어) 3. `parking this for now` (4단어)

본문:

```
{{first_name}}, closing this out: it doesn't look like a priority on
your side right now, and that's a fair answer.

Two things stay open. The two-page APRA and CPS 230 note is yours
whenever you want it, and this thread will reach me if the picture
changes: a one-word reply covers either.

Good luck with the {{role_context}} work this year.
```

- 단어 수: **61**. 죄책감 유발 없음, 문 열어두기 + 마지막 가치 1개, CTA 1개(통합형).

## 6. LinkedIn (실행: PO)

### 6.1 커넥션 노트 (Day 3, 300자 이내)

```
Hi {{first_name}}, APRA's AI letter and CPS 230 sit exactly where we
work: continuous, auditable model assurance. Research background: a
benchmark co-developed with the Korea Exchange, used to judge 1,100+
models. No pitch, just adjacent worlds. Glad to connect.
```

<!-- EC-krx-bench-01 (짧은 형 승인 문구 계열) -->
- 치환자 충전 후 300자(공백 포함) 이내 확인.

### 6.2 후속 DM (커넥션 수락 후, 권장 Day 8~10)

```
Thanks for connecting, {{first_name}}. I emailed you about APRA's point
on assurance not keeping pace with AI adoption. Short version:
continuous recomputation and logging instead of point-in-time sampling,
humans approving throughout. Is that shift under discussion at
{{account}}?
```

<!-- 앵커: EC-regwind-au-01 예정 · RYNTA: EC-rynta-arch-01 -->

## 7. 전화 (Day 8, 실행: PO · DNCR 층위 확인 대기)

### 7.1 오프닝 (15초)

```
Hi {{first_name}}, this is {{caller_name}} from OneLine AI. I emailed
you about APRA's AI letter and moving from sample-based to continuous
assurance. I have one specific idea for {{account}}. Can I take thirty
seconds, and you tell me if it's relevant?
```

### 7.2 보이스메일 (20초)

```
Hi {{first_name}}, {{caller_name}} from OneLine AI. I sent you notes on
APRA's AI letter and continuous, auditable assurance for AI models.
Nothing urgent, no need to call back: I'll follow up by email. Again,
{{caller_name}} at OneLine AI. Thanks.
```

## 8. 법정 푸터 (AU · Spam Act · 전 이메일 T1~T4 부착)

```
{{sender_name}}, OneLine AI · {{company_postal_address}} ·
{{sender_email}}
If you'd rather not hear from me, reply "unsubscribe" and you're off my
list straight away.
```

- 발신자 식별 정보는 발송 후 30일간 정확·유효해야 한다(도메인·서명 구성 확인). 수신거부 수단 30일 유효·무료, 법정 처리 상한 5영업일(팀 기준 즉시). 자연어 사절 회신도 즉시 소멸 사유로 처리.
- 레코드 단위: `au_publication_url`·캡처·확인일·사절 문구 부재·직무 관련성 메모 5필드 미기입 시 발송 금지 (G9, fail-closed).

## 9. 증거 카드 매핑

| 주장 | 위치 | 카드 |
|---|---|---|
| APRA AI 서한: 어슈어런스가 AI 속도를 못 따라감, 시점·표본 한계 | T1, T2, T3, DM, 전화 | **카드 신설 필요** (가칭 EC-regwind-au-01, 원출처 research/au-b1·b2 §2, 원문 대조 요) |
| CPS 230 운영 리스크 국면 | T1, T3 | 상동 |
| RYNTA 3층 구조·감사 추적 | T1, DM | EC-rynta-arch-01 |
| KRX 경진대회 약 233팀·1,100개+ 모델 | T2, LinkedIn 노트 | EC-krx-bench-01 |

## 10. 자기점검 (11항목)

| # | 항목 | 판정 |
|---|---|---|
| 1 | 시그널 게이트 | 조건부: {{signal_hook}} 충전 시 research/§5 훅 사용 강제 + au_role_relevance_note 정합 |
| 2 | 제목줄 2~6단어·소문자·camouflage | PASS (3/3/5단어, T4 3~4단어, 스팸 단어 0) |
| 3 | 오프닝 = 상대 관찰 | PASS |
| 4 | 본문 50~125단어·프레임워크 식별 | PASS (T1 90~103 PAS / T2 80 BAB / T3 62 / T4 61) |
| 5 | you:I 비율 | PASS (T2는 경계권, QA 재확인 요청) |
| 6 | 증거 출처 확인 | 조건부: APRA 앵커 카드 신설·원문 대조 전 발송 불가 |
| 7 | CTA 정확히 1개·interest-based | PASS |
| 8 | 안티패턴 스캔 | PASS (수신자 기관의 위반 상태 단정·암시 없음, 공포 마케팅 없음) |
| 9 | 시퀀스 정합성 | PASS |
| 10 | 링크 0~1·이미지 0·첨부 0 | PASS (본문 링크 0) |
| 11 | 규제 게이트 | 조건부: AU 증빙 5필드, 3요건 푸터, DNCR 확인, 카드 신설, G4 해제 전 발송 불가 |
