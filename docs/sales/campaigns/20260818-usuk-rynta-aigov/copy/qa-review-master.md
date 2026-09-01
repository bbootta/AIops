# QA 검수 기록: RYNTA 글로벌 아웃리치 마스터 카피 6종 + 증거 카드 9장

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/qa-review-master.md`
> 검수: outreach-qa · 검수일: 2026-08-19 · 루프 회차: **1회차** (수정 주체: cold-email-writer, 구조 변경 없음)
> 기준: KB01 §13 (11항목 게이트, fail-closed), §3·§4·§9 / KB08 §11 / 증거 카드 라이브러리(docs/sales/deals/_evidence/) / icp-draft §5.2 / compliance-frame.md / compliance-frame-sg-au.md
> git 커밋 금지 대상 워킹 파일.

---

## 1. 종합 판정

**PASS_WITH_FIXES** : 시퀀스 구조(G11)와 팩트 규율은 견고하나, ① NAIC "29개 관할" 수치 부정확(팩트체크 FAIL 1건), ② T2·T3 전 세그먼트의 you:I 비율 미달(게이트 5 FAIL), ③ SG T3 "We work across Asia already" 과장 경계 등 수정안 반영 + §8 선결 조건 전건 이행을 조건으로 통과.

- 이 판정은 **QA 게이트 판정이지 발송 승인이 아니다** [G1]. 발송·터치 실행·최종 승인은 PO 몫.
- 치환자 미충전 마스터 상태의 판정이다. 계정 충전본은 터치 릴리스 전 재검수 대상 [G3][G5].

## 2. 파일별 판정 표

| 파일 | 구조(G11) | 제목줄 | 본문 길이 | CTA | 링크 | 안티패턴 | you:I | 팩트체크 | 판정 |
|---|---|---|---|---|---|---|---|---|---|
| master-us-banks.md | PASS | PASS | PASS | PASS | PASS | PASS | T2·T3 FAIL | PASS(조건부: legal-team) | PASS_WITH_FIXES |
| master-us-brokerdealers.md | PASS | PASS | PASS | PASS | PASS | PASS | T2·T3 FAIL | PASS(조건부: 카드 신설) | PASS_WITH_FIXES |
| master-us-insurance-am.md | PASS | PASS | PASS | PASS | PASS | PASS | T2·T3(A·B) FAIL | **A-T1 "29개 관할" FAIL** | **FAIL → 수정 후 재판정** |
| master-uk.md | PASS | PASS | PASS | PASS | PASS(푸터 링크 예외 인정) | PASS | T2·T3 FAIL | PASS(조건부: legal-team·LIA) | PASS_WITH_FIXES |
| master-sg.md | PASS(C1 대체 적절) | PASS | PASS | PASS | PASS | PASS | T2·T3 FAIL | PASS(조건부: 카드 신설) + T3 과장 경계 | PASS_WITH_FIXES |
| master-au.md | PASS | PASS | PASS | PASS | PASS | PASS | T2·T3 FAIL | PASS(조건부: 카드 신설·원문 확보) | PASS_WITH_FIXES |

## 3. 시퀀스 구조 검수 (G11)

| 항목 | 판정 | 근거 |
|---|---|---|
| 이메일 단독 5터치 이상 아님 | PASS | 이메일 4통 + LinkedIn 1 + 전화(또는 SG DM) 1 = 6터치 / 18일 |
| 이메일 8통 상한 | PASS | 시퀀스당 4통 |
| 같은 날 같은 채널 중복 | PASS | Day 1/5/12/18 이메일, Day 3 LinkedIn, Day 8 전화(SG: DM). 중복 없음 |
| 터치별 실행 주체 명기 | PASS | 발송 도구 / PO 전건 명기. LinkedIn·전화는 PO 전속 [G1] |
| SG C1 슬롯 대체 | PASS(조건) | 터치 추가가 아닌 동일 슬롯 채널 교체. DNC 미대조 상태의 전화 금지는 컴플라이언스 강제 사항이므로 구조적으로 타당. 조건: channel-strategist 확인 기록(파일에 이미 표기), 커넥션 미수락 시 DM 순연·소멸 허용(콜드 InMail 대체 금지) |
| 운영 주의(비차단) | 주의 | C1(전화, Day 8)과 L1 후속 DM(권장 Day 8~10)이 같은 날 겹칠 수 있음. 다른 채널이라 규칙 위반은 아니나 DM은 Day 9~10 배치 권장 |

LinkedIn·콜 스크립트에 대한 11항목 적용 범위: 제목줄·본문 50~125단어 항목은 이메일 전용 기준이므로 미적용, 시그널·증거·CTA 1개·안티패턴·과장 금지·실행 주체는 전 채널 적용으로 검수했다. LinkedIn 커넥션 노트의 자기소개성 self-reference는 채널 특성상 허용(반려 아님, 관찰 기록만).

## 4. 11항목 게이트: 터치별 상세

### 4.1 제목줄 (항목 2) : 전건 PASS

전 후보 소문자·스팸 단어 0·internal camouflage 통과. 단어 수 실측: US은행 5/4/3~4, BD 6/3/4, 보험A 4/4/3~4, 자산운용B 4/3/3, UK 3/3/4~5, SG 4/3/4~5, AU 3/3/5, T4 공통 3/4/4. 전건 2~6 구간. T2·T3의 `re:` 상속은 실제 같은 스레드 답장이므로 Re: 위장 아님(CAN-SPAM 제목 진실성 충족).

### 4.2 본문 길이 (항목 4) : 전건 PASS, 병기 수치 ±1 오차 7건 (비차단)

직접 재계수 결과 (고정부 기준, 인사말·서명 포함):

| 터치 | 파일 병기 | QA 실측 | 판정 |
|---|---|---|---|
| US은행 T1/T2/T3/T4 | 76/84/65/59 | 76/84/65/**58** | PASS |
| BD T1/T2/T3/T4 | 84/83/66/60 | **83**/83/66/**59** | PASS |
| 보험A T1/T2/T3/T4 | 88/80/60/59 | **89**/80/60/**58** | PASS |
| 자산운용B T1/T2/T3/T4 | 78/74/63/59 | **79**/74/63/**58** | PASS |
| UK T1/T2/T3/T4 | 80/79/62/58 | **81**/79/62/**57** | PASS |
| SG T1/T2/T3/T4 | 75/71/74/52 | **76**/71/74/52 | PASS |
| AU T1/T2/T3/T4 | 78/80/62/61 | **79**/80/62/**60** | PASS |

±1 오차는 "26-2"·"SS1/23" 류 토큰 계수 방식 차이. 훅(12~25단어) 합산 시 전 T1이 50~125 구간 내. 프레임워크(PAS/BAB/가치/브레이크업) 전건 식별됨. 벽 문단 없음.

### 4.3 CTA (항목 7) : 전건 PASS

메일당 정확히 1개, 전건 interest-based(미팅 요청 없음). T4의 "a one-word reply covers either"는 행동 1개(회신)로 통합된 단일 CTA로 인정. T3 reply-to-receive 방식 적정.

### 4.4 링크·이미지·첨부 (항목 10) : 전건 PASS + UK 푸터 예외 판정

- 전 이메일 본문 링크 0, 이미지·첨부 0.
- **UK T1 푸터 {{privacy_notice_url}} 예외 인정.** 근거 2중: ① UK GDPR 제14조 고지의 법정 요소로 G10 우선 [compliance-frame §2.2], ② 그와 별개로 메일 단위 링크 수 1개는 KB01 §13 항목 10의 "0~1개" 한도 자체에도 부합. T2~T4 표준 푸터는 링크 0 확인.

### 4.5 안티패턴·스팸 트리거 (항목 8) : 전건 PASS

- 자기소개 오프닝·인사치레 없음(T1 첫 문장 = {{signal_hook}} 관찰). 콜 스크립트의 발신자 신원 고지는 전화 관행상 필수 요소로 안티패턴 아님.
- 기능 나열·가치 제안 3개 이상·죄책감 유발·가짜 긴급성·과장 문구·스팸 트리거 단어: 0건.
- SG T1의 "Twelve months sounds generous until..."은 사실 서술 + 준비 관점으로 가짜 긴급성 아님. AU의 "unusually direct"는 복수 해설(Ashurst "sound the AI alarm" 등)과 정합하는 논평 수준으로 허용.
- 수신자 기관 위반 상태 단정·암시 없음(AU 주의 사항 준수).

### 4.6 you:I 비율 (항목 5) : **T2·T3 전 세그먼트 FAIL** (반려 사유 1위)

계수 기준: 2인칭(you/your) 대 1인칭(I/we/our/us). {{first_name}} 호명·제3자(Korea Exchange 등) 제외. fail-closed이므로 동수도 미달 처리(§13 항목 5 "상대 언급이 자사 언급보다 많다").

| 터치 | you : self 실측 | 판정 |
|---|---|---|
| T1 전 세그먼트 | 훅 포함 2~3 : 0~1 | PASS |
| T2: US은행 / BD / 보험A / 자산운용B / UK / SG / AU | 2:2 / 1:2 / **0:2** / 1:2 / 2:2 / **0:2** / 1:2 | **FAIL** |
| T3: US은행 / BD / 보험A / 자산운용B / UK / SG / AU | 3:3 / 2:3 / 2:3 / 2:3 / 1:3 / **1:4** / 1:3 | **FAIL** |
| T4 전 세그먼트 | 2~3 : 1 | PASS |

원인 패턴 2개: ① T2의 Before 문단이 3인칭 중립 서술("validation is periodic", "the inventory usually lives in spreadsheets")이라 상대의 현재 상태인데도 your가 없음. ② T2 신뢰 문단·T3 오프너("with or without us", "whether or not we ever talk")가 self-reference를 누적.

수정 방향 (cold-email-writer 몫, 카피 재작성은 QA 소관 아님):

1. T2 공통: Before 문단을 2인칭화(+1~2 your). 예: US은행 "a queue that grows faster than it clears" → "a queue that grows faster than your team clears it" / 보험A "when an exam letter arrives" → "when an exam letter lands on your desk" / SG "spreadsheets for the AI inventory" → "spreadsheets for your AI inventory" / AU "with the evidence already logged" → "with your evidence already logged".
2. T3 공통: 오프너의 self-reference 제거. 예: "sharing something useful whether or not we ever talk/speak" · "something useful with or without us" → "worth having either way" 계열. 노트 서술에 +1 your(예: "the evidence worth preparing before your examiners ask").
3. SG T3: 아래 4.7-3과 연동해 Minkabu 문장 처리 시 1:4 → 통과 가능.
4. 수정 후 각 터치 you > self 재확인 + 단어 수 50~125 재확인 조건.

### 4.7 증거·팩트체크 (항목 6) : 아래 §5. 시그널(항목 1)·오프닝(항목 3)·시퀀스 정합성(항목 9)·딜리버러빌리티(항목 10 잔여)·규제(항목 11)는 마스터 수준 PASS(조건부), 조건은 §8.

---

## 5. 팩트체크 결과 (전수, 2026-08-19 웹 대조)

검증 주장 12건: 일치 10건, **불일치 1건**, 경계 1건.

### 5.1 검증 완료 (일치)

| # | 카피 주장 | 위치 | 대조 결과 |
|---|---|---|---|
| 1 | SR 26-2: 2026-04-17 발효, SR 11-7 대체, 생성형·에이전틱 AI를 범위 밖에 두고 별도 거버넌스 프레임워크 지목, 전통 모델 검증 기대 유지 | US은행 T1·T3·DM·전화 | **일치.** Fed 공식 페이지(federalreserve.gov SR2602) 실재 + Baker Tilly·Sia Partners·Domino 해설 교차. "keeps independent validation expectations"는 "reaffirming core principles"와 정합 |
| 2 | FINRA 2026 보고서(2025-12): WSP에 AI 거버넌스·AI 벤더 리스크·AI 에이전트 모니터링 반영 | BD T1·T3·DM·전화 | **일치.** FINRA 원문 PDF·보도자료 + Sidley·McGuireWoods·Debevoise 교차. "asks firms to reflect"는 원문 "advises members to make sure their WSPs cover"의 적정 패러프레이즈 |
| 3 | SEC FY2026 시험 우선순위(2025-11-17 발표): AI 사용 정책·감독, AI 역량 표현 정확성, 산출물·고객 프로파일 정합성 | BD T1, 자산운용B T1·T3 | **일치.** SEC 보도자료(2025-132) + Goodwin·Mayer Brown 교차. B 변형의 "no binding model governance rule" 정직 표기도 PDA 규칙 철회(2025-06-12, research/us-a1) 정합 |
| 4 | NAIC AI Systems Evaluation Tool 12개 주 검사 파일럿, 2026-03~09 | 보험A T1·T3·DM·전화 | **일치.** Fenwick·NAIC·Monitaur·Zelle 교차 (참여 주: CA CO CT FL IA LA MD PA RI VT VA WI, 2026-11 Fall Meeting 채택 검토) |
| 5 | MAS AIRG: 컨설테이션 2025-11-13, 확정 임박(2026-08-05 국회 서면답변), 12개월 전환기간 제안, 전 금융기관 대상 | SG T1·T3·DM | **일치.** MAS 공식 컨설테이션 페이지 + 국회답변 페이지(mas.gov.sg) + KPMG·Linklaters 교차. "will be finalised soon" 확인 |
| 6 | APRA AI 서한 2026-04-30: 거버넌스·어슈어런스가 AI 도입 속도를 못 따라감("not keeping pace"), 시점·표본 기반 어슈어런스의 한계 | AU T1·T2·T3·DM·전화 | **일치(2차 교차).** 원문 페이지(apra.gov.au) 실재 확인, 단 QA 환경 프록시 차단으로 원문 직접 열람 미완. MinterEllison·Clayton Utz·Norton Rose(regulationtomorrow)·Ashurst·GRC Report 등 **복수 독립 2차 출처에서 두 문구 모두 교차 확인.** 카피가 직접 인용부호 없이 패러프레이즈한 것도 적정. **잔여 조건: EC-regwind-au-01 신설 시 원문 PDF 확보·첨부(deal-strategist·PO 채널)** |
| 7 | CPS 230 운영 리스크 국면("already reshaping operational risk") | AU T1·T3 | **일치.** 2025-07-01 시행(apra.gov.au, research/au-b4 §2) |
| 8 | KRX 경진대회: 약 233팀, 1,100개+ 모델, KRX-Bench가 평가 기준, 공동개발 | 전 세그먼트 T2, AU 노트 | **일치.** 시상 보도(네이트/파이낸셜뉴스 2024-12): 233팀·1,119개 모델 제출. 공동개발: onelineai 블로그 + KNN 보도 "KRX와 OneLineAI가 공동 개발한 KRX-Bench" 교차. 카드 승인 문구("roughly 233 teams", "over 1,100 models") 그대로 사용 확인. 유의: 일부 보도는 예선 224팀으로 표기, "roughly" 유지 필수 |
| 9 | ₩ON ACL 2025 게재, KRX 공동개발 | 자산운용B T2, SG T2, LinkedIn 노트 전반 | **일치.** 벤처스퀘어 보도("원라인에이아이·한국거래소 공동 개발 금융 특화 언어 모델, ACL 2025에 공식 등재") 교차 |
| 10 | RYNTA 서술(결정론 엔진 + AI 보조 + 인간 승인, read-only·propose-only·감사 추적) | 전 세그먼트 T1·DM | **일치.** 내부 1차 소스 실재 확인(risk_lib/rynta.py: PACKAGE_VERSION "v9.0"·GUARDRAILS·NO_AUTO_DECISION, AIMS_POLICY.md §8). 아키텍처 서술만 사용, 준수 보장·성능 주장 없음. ISO/EU/NIST 비인용이라 단서 의무 미발동 |
| 11 | 민카부: 도쿄증권거래소 상장, 상용 협업 | SG T3 | **일치.** EC-minkabu-01 [확인] 승인 짧은 문구 그대로. "독점·투자" 표현 없음 |

### 5.2 불일치 (수정 필수)

**F-1. 보험A T1: "the NAIC's AI bulletin adopted in roughly 29 jurisdictions" : FAIL**

- 실측(2026 Q2 기준, aipmo·Quarles·NAIC 채택 맵 계열): **불레틴 채택은 25개 주 + DC(= 26개 관할)**이고, "29"는 여기에 **자체 보험 AI 프레임워크를 운영하는 CA·CO·NY·TX를 합산**한 "AI 거버넌스 규제를 도입한 관할" 수다. "불레틴이 29개 관할에 채택"은 두 범주를 합쳐 채택 수를 부풀린 서술이며, 이 수치를 아는 보험 리스크 임원에게 정확히 걸리는 지점이다.
- 수정안(택1, cold-email-writer):
  - (a) `With the NAIC's AI bulletin adopted in more than 25 jurisdictions and ...` (보수, 권장)
  - (b) `With insurer AI governance rules now in force across roughly 29 jurisdictions and ...` (합산 개념을 정확히 반영한 리프레임)
- 신설 카드 EC-regwind-us-ins-01에 "채택 26개 관할(25주+DC) + 자체 프레임워크 4개 주" 구분과 확인일을 명기할 것. 채택 수는 계속 증가 중이므로 발송 시점 재확인 필드 필요.

### 5.3 경계 (수정 권고, 준수정 필수)

**F-2. SG T3: "We work across Asia already, including a live commercial collaboration with Tokyo Stock Exchange-listed Minkabu."**

- 확인된 사실은 한국 내 운영 실적 + 일본 상장사와의 상용 협업(+ 일본·SG·미국 "진출 추진" 보도)까지다. "work across Asia already"는 복수 아시아 국가에서의 운영을 암시해 EC-minkabu-01 §5("진출 완료" 금지)의 경계를 스친다. KB08 §11.2의 "미국·유럽 고객 암시 금지"와 같은 취지.
- 수정안: 문장 삭제(권장: T3의 새 가치는 노트 1개면 충분, ACL 신뢰 훅은 T2에서 이미 소진) 또는 `It draws on live commercial work with Tokyo Stock Exchange-listed Minkabu.` 수준으로 축소. 삭제 시 4.6의 you:I(1:4)도 동시 해소된다.

**F-3. 보험A T3: "the evidence worth preparing before your state joins in"**

- 파일럿은 이미 12개 주에서 진행 중이다. 수신자 소재·검사 관할이 파일럿 주(CA CO CT FL IA LA MD PA RI VT VA WI)에 해당하면 이 문장은 사실과 어긋난다. 치환 시점에 계정 도메사일·주요 검사 주 확인을 강제하거나, 계정 무관 안전 문구(`before an exam letter arrives`)로 교체 권고.

**F-4. UK 세그먼트 적용 범위 주의 (비차단, 충전 시 확인)**

- SS1/23은 규제자본 내부모형(IRB 등) 승인 보유 기관에 적용된다(EC-regwind-usuk-01 §2-2). 카피는 "applies to you"를 명시하진 않으나, 비IRB 소사이어티·챌린저 계정에 이 앵커를 그대로 쓰면 과적용이다. 계정 충전 시 research 파일에서 내부모형 지위 확인을 릴리스 조건에 추가할 것(legal-team 확인 항목에 병기 권고).

---

## 6. 영어 네이티브 관용성·톤 지적 (수정 권고)

전반 톤은 우수(플레인 텍스트, 사람 냄새, 문화권 정합: UK "the maths is unkind" 등). 지적 5건:

| # | 원문 | 위치 | 문제 | 개선 방향 |
|---|---|---|---|---|
| I-1 | `Would a comparison against how you handle this today be useful?` | 자산운용B T1 CTA | "comparison against how"는 비원어민 티가 나는 콜로케이션 + 머리 무거운 주어 | `Worth comparing with how you handle this today?` 또는 `Would it help to see how this compares with your current setup?` |
| I-2 | `on SS1/23 Principle 4 as it meets AI and ML models` | UK T3 | "as it meets"는 어색. 규정이 모델을 "만나는" 표현은 비관용적 | `as it applies to AI and ML models` 또는 `where it meets your AI and ML inventory` |
| I-3 | `Can I take thirty seconds, and you tell me if it's relevant?` | 전 세그먼트 콜 오프닝 | 구어로 어색한 등위 접속. 소리 내 읽으면 명령문처럼 들림 | `Can I take thirty seconds, and you can tell me if it's relevant?` 또는 `Give me thirty seconds, then tell me if it's off base?` |
| I-4 | `reply "opt out" and you won't again.` | UK 푸터(8.1·8.2) | "you won't again"은 생략이 과해 비문 느낌 | `reply "opt out" and you won't hear from me again.` |
| I-5 | `On credibility, since we're new to you:` | BD T2 | 문어체 헤드라인식 삽입구, 살짝 딱딱함 | `Since we're probably a new name to you:` (경미, 선택) |

비고: `Worth a look at how that maps/fits/sits ...` 구문(각 T1 CTA)은 관용 범위 내로 허용. 보이스메일의 "Nothing urgent, no need to call back" 톤은 우수. UK "ring back"·SG/AU "straight away" 등 지역 표기 정합 확인.

---

## 7. 증거 카드 9장 원출처 대조 (라이브러리 대기 항목 소거)

전 카드 "outreach-qa (원출처 대조) 대기" 상태였음. 금일 대조 결과:

| 카드 | 대조 결과 | 등급 판정 | 비고 |
|---|---|---|---|
| EC-regwind-usuk-01 | 원출처 대조 **완료** (Fed SR2602 페이지·SS1/23 실재, 복수 해설 교차) | [확인] 유지 적정 | legal-team 확인은 여전히 발송 선결. 카드 §2-1의 "SR 21-8 대체" 부분은 카피 비인용이나 Fed 원문 재확인 권고(금일 검색에서는 SR 11-7 대체만 교차됨). EU 항목은 카드 자체가 2차 출처 플래그 유지 중, 적정 |
| EC-krx-bench-01 | **완료** (233팀·1,119모델 시상 보도 + 공동개발 KNN·onelineai 교차) | [확인] 유지 적정 | 예선 224팀 표기 보도 혼재: "약/roughly" 표기 이탈 금지. KRX 보도자료 계열이 벤치마크를 "KRX 자체 개발"로 쓰는 사례가 있어 공동개발 명시 출처(KNN 기사, onelineai 블로그) 카드 §3 추가 권고 |
| EC-krx-acl2025-01 | **완료** (벤처스퀘어 보도 교차) | [확인] 유지 적정 | "최초"는 보도 인용 한정 규칙 유지 |
| EC-rynta-arch-01 | **완료** (내부 1차: risk_lib/rynta.py v9.0·GUARDRAILS·NO_AUTO_DECISION, AIMS_POLICY.md §8 실재 확인) | [확인](내부 1차) 유지 적정 | 카피는 아키텍처 서술만 사용, 금지 표현 0건 |
| EC-minkabu-01 | 부분 완료 (민카부 도쿄증권거래소 상장 사실 확인. 국내 언론 URL은 QA 환경 프록시 차단으로 직접 열람 미완, 카드 내 복수 언론 교차 기록 신뢰) | [확인] 유지 | SG T3 "across Asia" 표현이 카드 경계를 스침 → §5.3 F-2 수정과 연동 |
| EC-kmmlu-01 | **완료** (KMMLU arXiv 2402.11548 계열·Redux/Pro 2507.08924 실재, 널리 인용 사실 정합) | [확인] 유지 적정 | 이번 버전 미사용 |
| EC-founder-team-01 | 부분 완료 (국내 언론 URL 프록시 차단, 카드 교차 기록 신뢰) | [확인] 유지 | 이번 버전 미사용. "약 8년" 표기 규율 유지 |
| EC-kr-references-01 | 부분 완료 (동일 사유) | [확인] 유지 | 이번 버전 미사용. 익명 기본값·PO 실명 허락 게이트 유지 |
| EC-olaf-v2-perf-01 | 확인 (등급 규칙 심사) | **[단일 출처] 유지 적정** | "회사 발표 기준"+시점 고정 조건부 카드로 정확히 설계됨. URL 미확정 상태에서 이번 버전 링크 미사용 확인 |

카드 인덱스(00-index.md) 정합성: 이상 없음. 단 **카피 인덱스(copy/00-index.md §6)의 매핑 오류 1건**: AU LinkedIn 노트는 EC-krx-acl2025-01이 아니라 EC-krx-bench-01(짧은 형)을 사용한다. master-au §9는 정확하므로 copy/00-index §6만 수정할 것.

---

## 8. 인계 유의점 7건 판정

| # | 유의점 | 판정 |
|---|---|---|
| 1 | **T3 "two-page note" 실물 미제작** | **발송 전 실물 제작 필수(블로킹). 문구 수정으로 해소 불가.** T3는 과거형("We put together / We wrote / We keep")으로 자산의 존재를 사실 주장하며, reply-to-receive 구조상 회신 즉시 이행 의무가 생긴다. 미제작 발송 = 존재하지 않는 자산 주장(환각 훅과 동급) + 회신 SLA 불이행 리스크. 미래형 개서("I can put together...")는 허위는 면하나 가치 제공형 프레임이 무너져 비권장. **T4도 같은 자산을 참조하므로("...note is yours whenever you want it") 동일 조건이 T4까지 걸린다.** 제작물 자체도 발송 전 QA 팩트체크 대상(특히 규제 요약의 준수 보장 표현 금지) |
| 2 | **SG 전화 슬롯 DM 대체** | **적절(PASS).** §3 참조. 터치 수 불변, 컴플라이언스 강제 사유, 같은 날 같은 채널 중복 없음. 조건: channel-strategist 확인 기록, 미수락 시 슬롯 소멸 허용(콜드 InMail 대체 금지) |
| 3 | **UK 푸터 프라이버시 링크** | **예외 인정(PASS).** G10 법정 고지 요소 + 메일당 링크 1개는 §13 항목 10의 0~1 한도 내. T1 한정, T2~T4 표준 푸터 링크 0 확인 |
| 4 | T2·SG T3 you:I 경계권 정밀 판정 | **경계권이 아니라 미달로 확정(FAIL).** T2·T3 전 세그먼트. §4.6 수정 방향 참조 |
| 5 | 본문 단어 수 병기 수치 | 실측 대조 완료, ±1 오차 7건(계수 방식 차이), 전건 구간 내. 비차단 |
| 6 | 신규 규제 앵커 4종 카드 미등재 | 블로킹 유지. EC-regwind-us-bd-01 / us-ins-01(§5.2 F-1 정밀 수치 반영) / sg-01 / au-01(원문 PDF 확보 포함) 신설 전 해당 세그먼트 발송 불가 |
| 7 | EC-regwind-usuk-01 legal-team 확인 대기 | 블로킹 유지. US 은행·UK 발송 선결. QA 원출처 대조는 금일 완료로 카드 검토란 갱신 가능 |

---

## 9. 반려 사유 목록 (우선순위 순) · 루프 1회차

cold-email-writer 수정 대상 (구조 변경 없음, channel-strategist 불요):

1. **[FAIL] 보험A T1 "roughly 29 jurisdictions" 수치 수정** (§5.2 F-1, 수정안 2개 제시)
2. **[FAIL] T2·T3 전 세그먼트 you:I 비율** (§4.6, 터치당 +1~2 2인칭·self-reference 1개 제거 수준의 경수정)
3. **[수정] SG T3 "We work across Asia already" 삭제 또는 축소** (§5.3 F-2)
4. **[수정] 보험A T3 "before your state joins in"** (§5.3 F-3)
5. **[수정] 관용성 I-1~I-4** (§6. I-5는 선택)
6. **[수정] copy/00-index.md §6 매핑 1건** (AU 노트 = EC-krx-bench-01)

재제출 시 QA 재검수 범위: 수정 터치의 단어 수·CTA·you:I 재계수 + 전량 diff 확인. 2회차 FAIL 시 sales-lead 캠페인 재설계 규칙 적용.

## 10. 발송 전 선결 조건 (수정 반영과 별개, 전건 이행 전 발송 불가)

1. 본 검수 반려 사항 수정 → QA 재검수 PASS
2. EC-regwind-usuk-01 legal-team 규제 해석 확인 (US 은행·UK)
3. 신규 앵커 카드 4종 신설·등급 판정 (BD/보험·자산운용/SG/AU. AU는 APRA 원문 PDF 확보·대조 포함)
4. T3 제공 자산 실물 제작(세그먼트별 5종 + SG 체크리스트) + 자산 자체 QA 팩트체크 (T3·T4 발송 선결)
5. UK: LIA 문서 ID·보관기한·{{privacy_notice_url}} 공급, sole trader·일반 파트너십 분리 (compliance-frame §2~3)
6. UK: 계정별 SS1/23 적용 지위(내부모형 승인) 확인 절차 추가 (§5.3 F-4)
7. AU: 레코드별 증빙 5필드 + DNCR 층위 확인 (C1 전화 전)
8. SG/AU: 트랙 착수·볼륨 상한 PO 승인 (compliance-frame-sg-au §9)
9. 치환자 전건 충전(훅은 research/§5 승인 훅 한정) → 충전본 터치 릴리스 체크리스트 [G2][G5]
10. sales-compliance-officer 게이트 PASS → PO 발송 패키지 승인 + G4 보류 해제 기록 [G1]

## 11. 웹 검증 출처 (2026-08-19 접속)

- Fed SR 26-2: https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm · https://www.bakertilly.com/insights/updated-interagency-guidance-on-model-risk-management · https://www.sia-partners.com/en/insights/publications/sr-11-7-vs-sr-26-2-model-risk-management-modernization
- FINRA 2026: https://www.finra.org/sites/default/files/2025-12/2026-annual-regulatory-oversight-report.pdf · https://www.sidley.com/en/insights/newsupdates/2025/12/finra-issues-2026-regulatory-oversight-report · https://www.debevoisedatablog.com/2025/12/11/finras-2026-regulatory-oversight-report-continued-focus-on-generative-ai-and-emerging-agent-based-risks/
- SEC FY2026: https://www.sec.gov/newsroom/press-releases/2025-132-sec-division-examinations-announces-2026-priorities · https://www.goodwinlaw.com/en/insights/publications/2025/12/alerts-privateequity-pif-2026-sec-exam-priorities-for-registered-investment-advisers
- NAIC: https://www.fenwick.com/insights/publications/naic-expands-ai-systems-evaluation-tool-pilot-program-to-12-states-key-updates-for-insurers-and-ai-vendors-supporting-insurers · https://aipmo.co/naic-ai-bulletin-q2-2026-status/ · https://www.quarles.com/newsroom/publications/nearly-half-of-states-have-now-adopted-naic-model-bulletin-on-insurers-use-of-ai (29 = 채택 25주+DC와 자체 프레임워크 4주의 합산 확인)
- MAS AIRG: https://www.mas.gov.sg/publications/consultations/2025/consultation-paper-on-guidelines-on-artificial-intelligence-risk-management · https://www.mas.gov.sg/news/parliamentary-replies/2026/written-reply-to-parliamentary-question-on-agentic-ai-in-financial-services
- APRA: https://www.apra.gov.au/news-and-publications/apra-letter-industry-artificial-intelligence-ai (원문, 프록시 차단으로 열람 미완) · https://www.minterellison.com/articles/apra-sharpens-expectations-on-ai-governance-and-risk-management · https://www.claytonutz.com/insights/2026/may/apras-ai-letter-a-shift-from-framework-to-targeted-expectations · https://www.ashurst.com/en/insights/apra-and-asic-sound-the-ai-alarm-for-boards-and-executives/
- KRX 대회·KRX-Bench·ACL 2025: https://news.nate.com/view/20241220n15182 · https://www.fnnews.com/news/202412201652561491 · https://news.knn.co.kr/news/article/164250 · https://www.venturesquare.net/971372 · https://onelineai.com/blog-research/won
