# 마스터 시퀀스: 미국 브로커딜러·자산관리 (FINRA 2026 + SEC FY2026 앵커)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/master-us-brokerdealers.md`
> 작성: cold-email-writer · 기준일: 2026-08-19 · 상태: 마스터 수정본 v1.1 (QA 1회차 반영, outreach-qa 재검수 대기)
> **발송 불가: 이 파일은 마스터 버전이다. `{{...}}` 치환자 미충전 상태로는 어떤 터치도 발송할 수 없다.** 충전 → outreach-qa 재검수 → compliance 게이트 → PO 승인 순서를 지킨다 [G1][G3][G4]. 공통 규칙은 `00-index.md`.

## 0. 세그먼트 정의

- 앵커(Why Now): **FINRA 2026 Annual Regulatory Oversight Report** (WSP에 AI 거버넌스·AI 벤더 리스크·AI 에이전트 모니터링 반영 요구, 2025-12) + **SEC FY2026 시험 우선순위** (AI 사용 정책·절차·감독 적정성, 2025-11).
- 타깃 역할: CRO, Chief Compliance Officer(브로커딜러), CIO / Head of AI (research/us-d* §4)
- 관할·푸터: US · CAN-SPAM (§8)
- 앵커 검증 상태: 캠페인 리서치 파일에 출처 검증됨(research/us-d1 §2 등). **증거 카드 미등재: 카드 신설(가칭 EC-regwind-us-bd-01)·legal-team 확인 전 발송 금지** (00-index §5-2).
- 세그먼트 규칙: 이 세그먼트 카피에 SR 26-2를 쓰지 않는다(리서치 파일 상단 규제 프레임 주의).

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

1. `finra 2026 report and ai agents` (6단어) · 선택 근거: 앵커 명시형, CCO·리스크 직군에게 즉시 관련성이 보임. 기본 추천.
2. `ai agent supervision` (3단어) · 초단문, 자체 에이전트 배포 시그널이 강한 계정에 적합.
3. `wsp coverage for ai` (4단어) · WSP는 브로커딜러 내부 용어. internal camouflage 강함, CCO 타깃 전용.

본문:

```
Hi {{first_name}},

{{signal_hook}}

FINRA's 2026 oversight report asks firms to reflect AI governance,
vendor risk, and AI-agent monitoring in written supervisory procedures,
and the SEC's FY2026 exam priorities add AI-use policies and
supervision. The hard part is evidence: showing what an agent did, saw,
and changed.

RYNTA is built for that evidence layer: agents work read-only by
default, propose rather than decide, and every material action carries
a human approval and an audit trail.

Is agent-level auditability on your {{role_context}} list this year?

{{sender_name}}
[푸터: §8]
```

<!-- 앵커 문단: FINRA 2026 보고서·SEC FY2026 시험 우선순위. 카드 신설 필요(가칭 EC-regwind-us-bd-01), 원출처는 research/us-d1 §2 (Sidley·Akin Gump 해설, 2025-12/2025-11). 카드·legal-team 확인 전 발송 금지 -->
<!-- RYNTA 서술: EC-rynta-arch-01 (CISO 변형 문구 계열: read-only, propose-only, human approval, audit trail) -->

- 단어 수: 고정 84 + {{signal_hook}} 12~25 = **96~109** (50~125 충족)
- CTA 1개, 링크 0.

## 3. Email T2 (Day 5 · BAB · 같은 스레드 Re:)

본문:

```
{{first_name}}, one more angle on this.

Right now, your AI supervision mostly lives in policy documents, and
your agent rollout moves faster than the written procedures behind it.
The stronger position in an exam is a system of record: every agent
action logged, replayable, and tied to a named approver.

Since we're probably a new name to you: the Korea Exchange used
KRX-Bench, a benchmark we co-developed, as the judging standard for a
competition where roughly 233 teams submitted over 1,100 models.

Worth a look?
```

<!-- 증거 문단: EC-krx-bench-01 (승인 문구 준수) -->
<!-- QA 1회차 반영: Before 문단 2인칭화(+2 your, QA §4.6 수정 방향 1) + I-5 채택("On credibility, since we're new to you" → "Since we're probably a new name to you") -->

- 단어 수: **85** · you:self **3:2** (your AI supervision·your agent rollout·to you vs we're·we). Before(정책 문서 수준 감독) → After(기록 시스템) → Bridge(평가 역량 실증).
- CTA 1개, 링크 0.

## 4. Email T3 (Day 12 · 가치 제공형 · 같은 스레드 Re:)

본문:

```
{{first_name}}, one thing worth having either way.

We condensed the AI sections of FINRA's 2026 report and the SEC's
FY2026 exam priorities into a two-page note for broker-dealer risk and
compliance teams: what your written procedures are now expected to
cover, and the audit evidence worth preparing before your examiners
ask.

Reply "send it" and it's in your inbox: I keep links and attachments
out of cold threads.
```

<!-- 규제 내용: 카드 신설 필요(EC-regwind-us-bd-01 예정). 발송 전 two-page note 실물 제작 필수 -->
<!-- QA 1회차 반영: 오프너 self-reference 제거("regardless of us" → "either way") + 노트 서술에 your 추가("before your examiners ask", QA §4.6 수정 방향 2 예시 그대로) -->

- 단어 수: **68** · you:self **3:2** (your written procedures·your examiners·your inbox vs We·I). 새 가치 = 규제 시사점 요약. 링크 0 (reply-to-receive). CTA 1개.

## 5. Email T4 (Day 18 · 브레이크업 · 새 스레드)

제목줄 후보 3개: 1. `closing the loop` (3단어, 기본 추천) 2. `last note from me` (4단어) 3. `parking this for now` (4단어)

본문:

```
{{first_name}}, closing this out: it doesn't look like a priority on
your side right now, and that's a fair answer.

Two things stay open. The two-page FINRA and SEC note is yours whenever
you want it, and this thread will reach me if the picture changes: a
one-word reply covers either.

Good luck with the {{role_context}} work this year.
```

- 단어 수: **60**. 죄책감 유발 없음, 문 열어두기 + 마지막 가치 1개, CTA 1개(통합형).

## 6. LinkedIn (실행: PO)

### 6.1 커넥션 노트 (Day 3, 300자 이내)

```
Hi {{first_name}}, your remit at {{account}} touches what we build:
audit trails and guardrails for AI agents in regulated firms. Our
research background includes work with the Korea Exchange (ACL 2025).
No pitch, just adjacent worlds. Glad to connect.
```

<!-- EC-krx-acl2025-01 -->
- 치환자 충전 후 300자(공백 포함) 이내 확인.

### 6.2 후속 DM (커넥션 수락 후, 권장 Day 8~10)

```
Thanks for connecting, {{first_name}}. I emailed you about FINRA's 2026
report folding AI-agent monitoring into supervisory procedures. Short
version: we build the evidence layer, every agent action logged,
human-approved, replayable. Is that on your desk this quarter?
```

<!-- 앵커: EC-regwind-us-bd-01 예정 · RYNTA: EC-rynta-arch-01 -->

## 7. 전화 (Day 8, 실행: PO)

### 7.1 오프닝 (15초)

```
Hi {{first_name}}, this is {{caller_name}} from OneLine AI. I emailed
you about FINRA's 2026 report and AI-agent monitoring in supervisory
procedures. I have one specific idea on agent-level audit evidence.
Can I take thirty seconds, and you can tell me if it's relevant?
```

### 7.2 보이스메일 (20초)

```
Hi {{first_name}}, {{caller_name}} from OneLine AI. I sent you notes on
FINRA's 2026 report and audit-ready AI agent supervision. Nothing
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
| FINRA 2026 보고서: WSP에 AI 거버넌스·벤더 리스크·에이전트 모니터링 | T1, T3, DM, 전화 | **카드 신설 필요** (가칭 EC-regwind-us-bd-01, 원출처 research/us-d1 §2) |
| SEC FY2026 시험 우선순위: AI 사용 정책·감독 | T1, T3 | 상동 |
| RYNTA 가드레일(조회 전용·제안 전용·인간 승인·감사 추적) | T1, DM | EC-rynta-arch-01 |
| KRX 경진대회 약 233팀·1,100개+ 모델 | T2 | EC-krx-bench-01 |
| ACL 2025 게재 | LinkedIn 노트 | EC-krx-acl2025-01 |

## 10. 자기점검 (11항목)

| # | 항목 | 판정 |
|---|---|---|
| 1 | 시그널 게이트 | 조건부: {{signal_hook}} 충전 시 research/§5 훅 사용 강제 |
| 2 | 제목줄 2~6단어·소문자·camouflage | PASS (6/3/4단어, T4 3~4단어, 스팸 단어 0) |
| 3 | 오프닝 = 상대 관찰 | PASS |
| 4 | 본문 50~125단어·프레임워크 식별 | PASS (T1 96~109 PAS / T2 85 BAB / T3 68 / T4 60) |
| 5 | you:I 비율 | PASS (실측: T2 3:2 · T3 3:2, 동수 없음. T1·T4는 QA 1회차 실측 PASS 유지) |
| 6 | 증거 출처 확인 | 조건부: FINRA/SEC 앵커 카드 신설 전 발송 불가 |
| 7 | CTA 정확히 1개·interest-based | PASS |
| 8 | 안티패턴 스캔 | PASS |
| 9 | 시퀀스 정합성 | PASS (T1 규제 갭 / T2 기록 시스템+실증 / T3 요약 노트 / T4 브레이크업) |
| 10 | 링크 0~1·이미지 0·첨부 0 | PASS (본문 링크 0) |
| 11 | 규제 게이트 | 조건부: 앵커 카드·legal-team 확인, G4 해제, 주소 충전 전 발송 불가 |

## 11. 변경 이력

- 2026-08-19 v1.1 (cold-email-writer, QA 1회차 반려 반영): T2 Before 2인칭화 + I-5 채택, T3 오프너 교체·"before your examiners ask" 추가(you:self 각 3:2), 콜 오프닝 I-3, 단어 수 갱신(T2 83→85, T3 66→68).
