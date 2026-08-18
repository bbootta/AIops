# 멀티채널 시퀀스: {캠페인ID}

> 저장 경로: `docs/sales/campaigns/{캠페인ID}/sequence.md`
> 표준 구조: 이메일 3~4통 + LinkedIn/전화 슬롯, 첫 5일 집중 배치. 이메일 단독 5터치 이상 시퀀스는 구조 자체가 반려된다 [G11].

| 항목 | 내용 |
|---|---|
| 캠페인ID | {YYYYMMDD-<region>-<슬러그>} |
| 작성 에이전트 | channel-strategist (터치맵 §1~2, §7~8) / cold-email-writer (카피 §3~6, §9) |
| 검토 | outreach-qa {PASS/FAIL, 판정일, 기록 경로} |
| 승인 | PO (발송 패키지 승인 시 일괄) {서명/날짜 또는 미승인} |
| 기준일 | {YYYY-MM-DD} |

## 1. 시퀀스 요약과 구조 자가 점검

- 구조: 이메일 {3~4}통 + LinkedIn {n}회 + 전화 {n}회, 총 {n}터치 / {14}일
- 프레임워크 배치: Email 1 {PAS/AIDA} → Email 2 {BAB + 새 증거} → Email 3 {가치 제공형} → Email 4 {브레이크업}. 전 메일 BBB 검수.

- [ ] [G11] 이메일 단독 5터치 이상 아님 (LinkedIn/전화 슬롯 포함 확인)
- [ ] [G11] 답장 없는 상대에게 이메일 총 {n}통 ≤ 8통
- [ ] [G11] 같은 날 같은 채널 중복 터치 없음 (같은 날 이메일 + LinkedIn은 허용)
- [ ] [G11] 터치별 실행 주체 명기: 이메일 = 발송 도구, LinkedIn/전화 = PO
- [ ] 첫 5일 집중 배치, 터치 간격 후반으로 갈수록 확대 (kb/sales/01 §7.2)
- [ ] [G11] 회피 등급 국가 레코드 없음 (있으면 `alt-channel-play.md` 이관)

## 2. Day-by-Day 터치맵

| 터치 | Day | 채널 | 실행 주체 | 카피 참조 | 비고 |
|---|---|---|---|---|---|
| T1 | 1 | LinkedIn 프로필 조회 (+커넥션 요청) | PO | §4.1 | 무언 또는 노트 |
| T2 | 1 | Email 1 | 발송 도구 | §3.1 | PAS, 시그널 훅, interest CTA |
| T3 | 3 | Email 2 | 발송 도구 | §3.2 | 같은 스레드, BAB + 새 증거 1개 |
| T4 | 5 | 전화 1 | PO | §5.1~5.2 | 부재 시 보이스메일 |
| T5 | 8 | LinkedIn DM 또는 포스트 코멘트 | PO | §4.2 | |
| T6 | 10 | Email 3 | 발송 도구 | §3.3 | 같은 스레드, 새 가치 1개 |
| T7 | 13 | 전화 2 | PO | §5.1 | 시간대 바꿔서 |
| T8 | 14 | Email 4 | 발송 도구 | §3.4 | 브레이크업, 새 스레드 허용 |

- 터치 2~N은 각 발송 예정일에 `templates/sales/touch-release-checklist.md` PASS 기록이 있어야 릴리스된다 [G2][G5].
- 한 터치 = 한 가지 새로운 가치. "혹시 못 보셨을까 봐" 후속 금지.

## 3. 영문 이메일 카피

작성 규칙: 제목줄 2~6단어 소문자(internal camouflage), 본문 50~125단어, 링크 0~1개, 이미지·첨부 0, 플레인 텍스트, CTA 정확히 1개(콜드 단계는 interest-based). 사실 주장은 `evidence-card.md`의 [확인] 등급만 인용 [G3].

### 3.1 Email 1 (Day 1, PAS)

제목줄 후보 3개:

1. {예시} `hiring for llm evals?`
2. {예시} `{company} + korean market data`
3. {예시} `saw the {구체적 시그널 이벤트}`

본문:

{예시}
```
Hi {FirstName},

Noticed {Company} posted three research-engineer openings focused on
LLM evaluation last month. Teams at that stage usually hit the same
wall: generic benchmarks miss what matters in Korean-language
financial text, so review cycles drag on for weeks.

We co-developed a finance-specific Korean model with the Korea
Exchange (published at ACL 2025), and {SimilarCo} used our eval set
to cut review cycles from weeks to days.

Is slow eval turnaround something your team is running into? Happy
to send a two-page summary of how they set it up.

{Sender name}
{국가별 푸터: §6}
```

### 3.2 Email 2 (Day 3, 같은 스레드, BAB)

{예시}
```
{FirstName}, one more angle on this.

Most teams we talk to still benchmark Korean financial models with
translated English sets. The result: scores look fine, but production
answers keep missing regulatory nuance.

After switching to a domain-native benchmark, {SimilarCo}'s reviewers
stopped re-checking every output and now sample one in ten.

We wrote up the before and after in a short case note. Want me to
send it over?
```

### 3.3 Email 3 (Day 10, 같은 스레드, 가치 제공형)

{예시}
```
{FirstName}, sharing something useful with or without us.

KMMLU, the open Korean LLM benchmark our team first-authored, is
what several labs run as a sanity check before building their own
domain evals. It's free on Hugging Face.

If evaluation is on your roadmap this quarter, I can also send the
one-page checklist {SimilarCo} used to structure theirs. Useful
either way?
```

### 3.4 Email 4 (Day 14, 브레이크업, 새 스레드 허용)

제목줄: {예시} `closing the loop`

{예시}
```
{FirstName}, sounds like this isn't a priority right now, so I'll
stop here.

If Korean-market model quality comes back on your roadmap, just
reply to this thread. Leaving the {SimilarCo} case note in case
it's ever useful: {link}.

Thanks for your time.
```

- 죄책감 유발 금지 ("여러 번 연락드렸는데" 류). 문은 열어두고 마지막 가치 1개를 남긴다.

## 4. LinkedIn 카피 (실행: PO)

### 4.1 커넥션 노트 (300자 이내)

{예시} `Hi {FirstName}, I follow your team's work on {topic}. We co-developed a Korean financial LLM with the Korea Exchange (ACL 2025). No pitch, just adjacent worlds. Glad to connect.`

### 4.2 DM (커넥션 수락 후, Day 8)

{예시} `Thanks for connecting, {FirstName}. I emailed you last week about eval turnaround for Korean financial models. Short version: {SimilarCo} cut review cycles from weeks to days with a domain-native benchmark. Is that a live problem on your side this quarter?`

## 5. 콜 스크립트 (실행: PO)

### 5.1 오프닝 (30초)

{예시} `Hi {FirstName}, this is {PO name} from OneLine AI in Seoul. I sent you a note about the LLM evaluation roles you're hiring for, and I have one specific idea on eval turnaround. Do you have 30 seconds for me to explain why I called, and you can tell me if it's relevant?`

### 5.2 보이스메일 (20초)

{예시} `Hi {FirstName}, {PO name} from OneLine AI. I emailed you about Korean-market model evaluation and how {SimilarCo} cut review cycles. No need to call back, I'll follow up by email. Again, {PO name}, OneLine AI.`

## 6. 국가별 푸터 변형

| 관할 | 필수 요소 | 푸터 문안 |
|---|---|---|
| 미국 | 물리 주소 + 수신거부 수단 | {예시} `OneLine AI Inc., {street}, {city, state ZIP}. If you'd rather not hear from me, reply "no thanks" and I won't email again.` |
| EU 조건부 국가 (첫 메일) [G10] | 제14조 고지(데이터 출처 + 프라이버시 노티스 링크) + 반대권 안내 | {예시} `You're receiving this one-to-one email because your name and work email were sourced from {source} for outreach relevant to your role. Details and your rights: {privacy notice URL}. Reply "opt out" and you won't hear from us again.` |
| 영국 (법인 가입자) | 발신자 신원 + 유효 회신 주소 + 수신거부 + 제14조 요소 | {EU 문안 준용 + 회사 등록 정보} |
| 일본 | 법인 정식명 + 주소 + 수신거부 표시 의무 | {예: `(주)원라인에이아이 (OneLine AI Inc.), {주소}` + 수신거부 안내} |
| 한국 | **국가별 템플릿 변형이 아니다.** | A/B 유형(1:1 제휴 문의)만 후보이고, 그 경우에도 수신자 1명당 건별 개별 작성을 강제한다 [G7] (kb/sales/06 §2.3, §4.2). 이 시퀀스 템플릿을 한국 수신자에게 재사용하지 않는다. |

## 7. 스레드 전략

- 기본: Email 1~3은 같은 스레드 유지(Re:). 맥락 유지가 오픈·답장에 유리하다.
- 새 스레드 허용: 브레이크업(Email 4) 또는 완전한 앵글 전환 시.
- 리셋 트리거: 1통째 스팸함 착지 신호(오픈 급락 + 답장 소멸) 시 스레드 리셋 판단을 deliverability-engineer와 협의하고 기록한다: {기록}

## 8. 수신자 시간대 발송 윈도

| 관할/시간대 | 발송 윈도 (수신자 현지) | 이메일 (발송 도구 스케줄) | LinkedIn/전화 (PO 캘린더, KST 환산) |
|---|---|---|---|
| {예: US-East (ET)} | 화~목 09:00~11:30 | {도구 설정값} | {KST 22:00~00:30 등} |

- 평일 업무시간만. 같은 날 같은 채널 중복 금지 [G11]. PO 실행 캘린더는 channel-strategist가 준비한다.

## 9. 답장 처리 규칙 (deal-support 연계)

- 분류(매 영업일, sales-ops-analyst): **긍정 / 부정 / OOO / 수신거부성 회신**
- 수신거부성 회신·하드바운스·스팸 신고: 즉시 suppression 등록 + 전 채널 시퀀스 제외 [G2]
- 답장자(긍정·부정 불문): 발송 도구의 시퀀스 자동 중단 작동 확인 [G5]
- 긍정 답장: interest CTA에서 **구체 시간 2개 제시**로 전환한다 (kb/sales/01 §4.2). {예시} `Great. Would Tuesday 10am or Wednesday 4pm your time work for a 25-minute call? I'll send an invite.`

## 10. QA·게이트 기록

- [ ] [G3] outreach-qa 11항목 게이트 (전 채널 카피: 이메일 + LinkedIn 노트/DM + 콜/보이스메일): {PASS/FAIL, 기록 경로}
- [ ] [G3] 영어 네이티브 관용성·톤 검토 (문법상 맞지만 어색한 영어는 반려): {PASS/FAIL}
- [ ] [G3] 수치·고객명 전건 KB08 [확인] 등급 또는 원출처 확인: {결과}
- [ ] [G11] 시퀀스 구조 검수: {PASS/FAIL}
