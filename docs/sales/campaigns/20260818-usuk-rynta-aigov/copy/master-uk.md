# 마스터 시퀀스: 영국 빌딩소사이어티·챌린저 (SS1/23 원칙 4 앵커)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/master-uk.md`
> 작성: cold-email-writer · 기준일: 2026-08-19 · 상태: 마스터 수정본 v1.1 (QA 1회차 반영, outreach-qa 재검수 대기)
> **발송 불가: 이 파일은 마스터 버전이다. `{{...}}` 치환자 미충전 상태로는 어떤 터치도 발송할 수 없다.** 충전 → outreach-qa 재검수 → compliance 게이트 → PO 승인 순서를 지킨다 [G1][G3][G4]. 공통 규칙은 `00-index.md`.

## 0. 세그먼트 정의

- 앵커(Why Now): **PRA SS1/23 (2024-05-17 발효), 원칙 4 = 독립 모델검증(Independent model validation).** AI/ML 모델의 인벤토리 유입과 겹치는 국면.
- 타깃 역할: CRO, Head of Model Validation, Head of Model Risk (icp-draft §7)
- 관할·푸터: UK · PECR 법인 가입자 + UK GDPR (첫 메일 제14조 고지 필수 [G10], §8)
- 앵커 검증 상태: EC-regwind-usuk-01 [확인]. 단 **legal-team 규제 해석 확인 전 대외 발송 금지** (카드 §5).
- 발송 선결: LIA 문서 ID·보관기한(lia_document_id·lia_retention_expiry) 공급, sole trader·일반 파트너십 분리 확인 (compliance-frame §2~3).
- 영국 영어 표기(maths, finalising 등)를 유지한다.

## 1. 터치맵 슬롯 (G11)

| 터치 | Day | 채널 | 실행 | 카피 | 스레드 |
|---|---|---|---|---|---|
| T1 | 1 | Email 1 (PAS) | 발송 도구 | §2 | 새 스레드 |
| L1 | 3 | LinkedIn 커넥션 노트 | **PO** | §6.1 | - |
| T2 | 5 | Email 2 (BAB) | 발송 도구 | §3 | 같은 스레드 (Re:) |
| C1 | 8 | 전화 → 보이스메일 | **PO** | §7 | - |
| T3 | 12 | Email 3 (가치 제공) | 발송 도구 | §4 | 같은 스레드 (Re:) |
| T4 | 18 | Email 4 (브레이크업) | 발송 도구 | §5 | 새 스레드 |

## 2. Email T1 (Day 1 · PAS · 새 스레드)

제목줄 후보 3개:

1. `ss1/23 principle four` (3단어) · 선택 근거: 모델리스크 직군에게 규정 번호가 곧 내부 용어. internal camouflage 최강. 기본 추천.
2. `independent validation capacity` (3단어) · 원칙 4의 실무 pain(검증 여력)을 직격.
3. `model risk at {{account}}` (4~5단어) · 계정 결합형, 축약형 2단어 이하일 때만.

본문:

```
Hi {{first_name}},

{{signal_hook}}

SS1/23 has been in force since May 2024, and Principle 4 makes
independent model validation an explicit supervisory expectation, at
the same time as AI and ML models are joining your inventory. For most
validation teams the maths is unkind: more models, deeper reviews, same
headcount.

RYNTA approaches it as an assurance layer: a deterministic engine
recomputes, AI agents assist with investigation and explanation, and
accountable humans approve.

Worth a look at how that fits your validation agenda?

{{sender_name}}
[푸터: §8.1 첫 메일 확장판]
```

<!-- 앵커 문단: EC-regwind-usuk-01 (카드 승인 UK 문구 계열, legal-team 확인 대기) -->
<!-- RYNTA 서술: EC-rynta-arch-01 -->

- 단어 수: 고정 80 + {{signal_hook}} 12~25 = **92~105** (50~125 충족). CTA 1개, 본문 링크 0 (푸터의 프라이버시 노티스 링크는 법정 고지 요소).

## 3. Email T2 (Day 5 · BAB · 같은 스레드 Re:)

본문:

```
{{first_name}}, one more angle on this.

Right now, independent validation mostly works in annual cycles:
point-in-time reviews and a backlog that decides your schedule. The
alternative reads differently to a supervisor: material models re-run
and checked continuously, each result logged, your reviewers judging
rather than recomputing.

Our credentials are institutional: when the Korea Exchange judged a
competition of roughly 233 teams and over 1,100 models, the standard
was KRX-Bench, a benchmark we co-developed.

Is continuous validation on your roadmap?
```

<!-- 증거 문단: EC-krx-bench-01 (CRO 변형 "credentials are institutional" 계열, 승인 수치 그대로) -->
<!-- QA 1회차 반영: Before 문단 2인칭화 ("decides the schedule" → "decides your schedule", QA §4.6 수정 방향 1) -->

- 단어 수: **79** · you:self **3:2** (your schedule·your reviewers·your roadmap vs Our·we). Before(연차 주기 검증) → After(상시 재계산) → Bridge(평가 실증). CTA 1개, 링크 0.

## 4. Email T3 (Day 12 · 가치 제공형 · 같은 스레드 Re:)

본문:

```
{{first_name}}, something worth having either way.

We wrote a two-page note for heads of model validation on SS1/23
Principle 4 as it applies to AI and ML models: where independence
questions show up across your inventory, and the evidence supervisors
tend to ask your team for first.

Reply "send it" and it's in your inbox: I keep links and attachments
out of cold threads.
```

<!-- 규제 내용: EC-regwind-usuk-01. two-page note 실물 제작 필수 (00-index §5-6) -->
<!-- QA 1회차 반영: I-2 ("as it meets" → "as it applies to") + 오프너 self-reference 제거 + 노트 서술 2인칭화. SS1/23 적용 지위(내부모형 승인)는 계정 충전 시 확인, QA §5.3 F-4 릴리스 조건 -->

- 단어 수: **64** · you:self **3:2** (your inventory·your team·your inbox vs We·I). 새 가치 = 규제 시사점 요약. 링크 0 (reply-to-receive). CTA 1개.

## 5. Email T4 (Day 18 · 브레이크업 · 새 스레드)

제목줄 후보 3개: 1. `closing the loop` (3단어, 기본 추천) 2. `last note from me` (4단어) 3. `parking this for now` (4단어)

본문:

```
{{first_name}}, closing this out: it doesn't look like a priority on
your side right now, and that's a fair answer.

Two things stay open. The two-page SS1/23 note is yours whenever you
want it, and this thread will reach me if the picture changes: a
one-word reply covers either.

Good luck with the {{role_context}} work this year.
```

- 단어 수: **58**. 죄책감 유발 없음, 문 열어두기 + 마지막 가치 1개, CTA 1개(통합형).

## 6. LinkedIn (실행: PO)

### 6.1 커넥션 노트 (Day 3, 300자 이내)

```
Hi {{first_name}}, your validation remit at {{account}} overlaps with
our work on continuous, independent model validation. Research
background: a financial language model co-developed with the Korea
Exchange, published at ACL 2025. No pitch, just adjacent worlds. Glad
to connect.
```

<!-- EC-krx-acl2025-01 -->
- 치환자 충전 후 300자(공백 포함) 이내 확인.

### 6.2 후속 DM (커넥션 수락 후, 권장 Day 8~10)

```
Thanks for connecting, {{first_name}}. I emailed you about SS1/23
Principle 4 and making independent validation continuous rather than
annual. Short version: deterministic recomputation, AI-assisted
investigation, human sign-off, all logged. Is that near the top of your
list this year?
```

<!-- EC-regwind-usuk-01 · EC-rynta-arch-01 -->

## 7. 전화 (Day 8, 실행: PO)

### 7.1 오프닝 (15초)

```
Hi {{first_name}}, this is {{caller_name}} from OneLine AI. I emailed
you about SS1/23 Principle 4 and continuous independent validation. I
have one specific idea on clearing validation backlog without adding
headcount. Can I take thirty seconds, and you can tell me if it's
relevant?
```

### 7.2 보이스메일 (20초)

```
Hi {{first_name}}, {{caller_name}} from OneLine AI. I sent you a couple
of notes on SS1/23 Principle 4 and continuous, auditable model
validation. Nothing urgent, no need to ring back: I'll follow up by
email. Again, {{caller_name}} at OneLine AI. Thanks.
```

## 8. 법정 푸터 (UK · PECR + UK GDPR)

### 8.1 첫 메일 (T1) 확장판: 제14조 고지 포함 [G10]

```
{{sender_name}}, OneLine AI · {{company_registration_line}}
You're receiving this one-to-one email because your name and work
contact were sourced from {{data_source}} for outreach relevant to your
role in {{role_context}}. Our privacy notice, including your right to
object: {{privacy_notice_url}}
If you'd rather not hear from me, reply "opt out" and you won't hear
from me again.
```

- 필수 요소: 발신자 신원 + 데이터 출처 + 프라이버시 노티스 링크(법정 고지, 본문 링크 0개 원칙의 예외) + 반대권·수신거부. LIA 문서 ID 공급 전 발송 불가 (compliance-frame §2.2).

### 8.2 후속 메일 (T2~T4) 표준판

```
{{sender_name}}, OneLine AI · {{company_registration_line}}
If you'd rather not hear from me, reply "opt out" and you won't hear
from me again.
```

- 수신거부·제21조 반대권 접수 시 즉시 전 채널 suppression [G2].

## 9. 증거 카드 매핑

| 주장 | 위치 | 카드 |
|---|---|---|
| SS1/23 발효·원칙 4 독립 모델검증 | T1, T3, DM, 전화 | EC-regwind-usuk-01 (legal-team 확인 대기) |
| RYNTA 3층 구조 | T1, DM | EC-rynta-arch-01 |
| KRX 경진대회 약 233팀·1,100개+ 모델 | T2 | EC-krx-bench-01 |
| ACL 2025 게재 | LinkedIn 노트 | EC-krx-acl2025-01 |

## 10. 자기점검 (11항목)

| # | 항목 | 판정 |
|---|---|---|
| 1 | 시그널 게이트 | 조건부: {{signal_hook}} 충전 시 research/§5 훅 사용 강제 |
| 2 | 제목줄 2~6단어·소문자·camouflage | PASS (3/3/4~5단어, T4 3~4단어, 스팸 단어 0) |
| 3 | 오프닝 = 상대 관찰 | PASS |
| 4 | 본문 50~125단어·프레임워크 식별 | PASS (T1 92~105 PAS / T2 79 BAB / T3 64 / T4 58) |
| 5 | you:I 비율 | PASS (실측: T2 3:2 · T3 3:2, 동수 없음. T1·T4는 QA 1회차 실측 PASS 유지) |
| 6 | 증거 출처 확인 | PASS (수치는 EC-krx-bench-01 승인 문구 그대로) |
| 7 | CTA 정확히 1개·interest-based | PASS |
| 8 | 안티패턴 스캔 | PASS |
| 9 | 시퀀스 정합성 | PASS |
| 10 | 링크 0~1·이미지 0·첨부 0 | PASS (본문 링크 0, 푸터 법정 링크 1은 G10 요건) |
| 11 | 규제 게이트 | 조건부: 제14조 고지 요소·LIA·legal-team 확인·G4 해제 전 발송 불가 |

## 11. 변경 이력

- 2026-08-19 v1.1 (cold-email-writer, QA 1회차 반려 반영): T2 +1 your, T3 오프너 교체·I-2·2인칭화(you:self 각 3:2), 콜 오프닝 I-3, 푸터 I-4("you won't hear from me again", §8.1·§8.2), 단어 수 갱신(T3 62→64).
