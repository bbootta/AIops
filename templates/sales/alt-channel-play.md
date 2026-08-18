# 대체 채널 플레이: {지역 또는 캠페인ID}

> 저장 경로: `docs/sales/campaigns/{캠페인ID}/alt-channel-play.md`
> 용도: 회피 등급 국가(독일, 오스트리아, 이탈리아, 스페인, 폴란드 등)와 한국. 회피 등급 레코드는 이메일 시퀀스 투입이 금지되며 이 플레이북으로만 접근한다 [G11].

| 항목 | 내용 |
|---|---|
| 캠페인ID / 대상 지역 | {YYYYMMDD-<region>-<슬러그>} / {국가} |
| 작성 에이전트 | channel-strategist |
| 검토 | sales-compliance-officer (채널 적법성) {확인/보류} |
| 승인 | PO (실행 주체) {서명/날짜 또는 미승인} |
| 기준일 | {YYYY-MM-DD} |

## 1. 요약

- 대상: {국가/세그먼트}, 레코드 {n}건
- **콜드 메일 금지 근거 (명기 필수)**: {예: 독일 UWG 제7조 2항 2호, 사전 동의 없는 이메일 광고는 B2B에도 금지 (kb/sales/09 §3.3) / 한국 정보통신망법 제50조 옵트인 원칙 (kb/sales/06 §2)} [G2][G7][G11]
- 주력 플레이: {LinkedIn / 전시회 / 파트너 / 인바운드 우회 중 우선순위}
- 이관 기록: 콜드 메일 큐에서 제외된 레코드 목록 {경로}, 이관일 {YYYY-MM-DD}, 이관 지시: sales-compliance-officer → channel-strategist [G2]

## 2. LinkedIn 커넥션/InMail 시퀀스 (실행: PO)

| 스텝 | Day | 액션 | 카피 참조 |
|---|---|---|---|
| 1 | 1 | 프로필 조회 + 포스트 반응 | 없음 |
| 2 | 2 | 커넥션 요청 (노트 포함) | 아래 노트 |
| 3 | {5} | 수락 시 DM / 미수락 시 InMail | 아래 DM/InMail |
| 4 | {10} | 상대 포스트에 실질 코멘트 또는 2차 DM | {…} |

- 커넥션 노트 {예시}: `Hi {FirstName}, enjoyed your panel at {event} on AI in banking. We build Korean financial LLMs (co-developed with the Korea Exchange, ACL 2025) and I'd value staying connected with practitioners in the {country} market.`
- InMail (50~125단어, interest CTA) {예시}: `Hi {FirstName}, I'm reaching out here rather than by email out of respect for {country} outreach rules. Your team's {signal} suggests model evaluation is becoming a bottleneck. We co-developed a finance-specific Korean model with the Korea Exchange (ACL 2025) and helped {SimilarCo} cut eval cycles from weeks to days. Would a short case note be relevant to what you're building?`
- 주의: 스크래핑·자동화 도구 금지(플랫폼 약관 리스크), 일일 커넥션 요청 상한 준수. LinkedIn 카피도 outreach-qa 검수 대상 [G3].

## 3. 전시회/이벤트 접점 계획

| 이벤트 | 시기 | 목적 | 준비물 | 실행 주체 |
|---|---|---|---|---|
| {예: NextRise, AI EXPO KOREA, 현지 핀테크 컨퍼런스} | {…} | {리드 수집(동의 기반) / 미팅 확보} | {데모, 원페이저, 동의 수집 양식} | PO |

- 한국: 전시회는 동의 기반 리드 수집의 최대 창구다 (kb/sales/06 §7.1). 명함·리드의 후속은 "행사 관련 개별 후속 1통 → 마케팅 수신동의 요청" 경로로 전환한다 [G7].

## 4. 파트너 루트

| 파트너 | 유형 | 대상 계정 | 합동 영업 기회 | 다음 액션 |
|---|---|---|---|---|
| {예: 핑거} | 컨소시엄/리셀 | {…} | {…} | {…} |
| {예: 민카부} | 채널 파트너 | {일본 증권사 등} | {합동 영업 일정} | {…} |

- 일본 캠페인은 민카부 채널 우선, 콜드메일 단독 모션 지양 (kb/sales/08 §9.2).
- 한국: 소개 요청 시스템화, 정부 바우처/조달 공고 연계, SI/클라우드 마켓플레이스 파트너십 (kb/sales/06 §7.3~7.4).

## 5. 실행 캘린더 (실행 주체: PO)

| 주차 | 액션 | 채널 | 대상 | 수신자 현지 시간 윈도 (KST 환산) | 상태 |
|---|---|---|---|---|---|
| {W1} | {…} | {LinkedIn/전화/이벤트} | {…} | {…} | {예정/완료} |

- LinkedIn/전화 터치는 수신자 현지 업무시간 창에 배치한다. 실행은 전부 PO다 [G1].

## 6. 성과 측정

- 판정 지표: 커넥션 수락률, InMail 답장률, 이벤트 리드 수(동의 확보 건수), 파트너 소개 건수 → 미팅 전환 → 기회 생성
- 기록: 주간 리포트(`reports/sales/`)에 sales-ops-analyst가 반영
