# 한→영 번역 가이드 (Korean → English)

한국어 원문을 자연스러운 영어로 옮길 때의 핵심 변환 규칙. 목표는 "영어 원어민 비즈니스 라이터가 쓴 문서"다.

## 1. 문장 구조 재조립

한국어는 화제 중심(topic-prominent), 영어는 주어 중심(subject-prominent)이다. 문장 단위 직역이 아니라 **정보 단위로 재조립**한다.

- **생략된 주어 복원**: 한국어는 주어를 생략한다. 영어에서는 행위 주체를 명시한다.
  - 원문: "검토 후 회신드리겠습니다."
  - ✗ "It will be reviewed and replied."
  - ✓ "We will review it and get back to you."
- **긴 관형절 분해**: 한국어의 긴 수식 구조는 관계절로 직역하면 무겁다. 문장을 나누거나 재배열한다.
  - 원문: "지난달 출시된 신규 기능에 대한 고객 피드백을 반영한 개선안"
  - ✗ "an improvement plan reflecting customer feedback on the new feature launched last month"
  - ✓ "an improvement plan based on customer feedback about last month's new feature"
- **문장 순서**: 한국어는 배경→결론, 영어 비즈니스 문서는 결론→근거. 단락 안에서 핵심 문장을 앞으로 당기는 것을 허용한다(정보 누락 없이).

## 2. 명사화 해소

한국어 공문·보고서의 "~화, ~성, ~에 대한 검토, ~의 실시"는 영어에서 동사로 푼다.

- "시스템 안정화 작업의 조속한 실시가 필요함" → ✓ "We need to stabilize the system quickly."
- "개선 방안 마련 요청" → ✓ "Please propose improvements."

## 3. 격식·완곡 표현 처리

한국어의 관습적 완곡·겸양 표현은 영어로 직역하면 어색하거나 뜻이 흐려진다. **기능으로 번역**한다.

| 한국어 관습 표현 | 직역 (✗) | 기능 번역 (✓) |
|---|---|---|
| 검토 후 말씀드리겠습니다 | I will speak after review | Let me look into this and follow up |
| ~해 주시면 감사하겠습니다 | I would be grateful if... | Please ... / Could you ... |
| 수고하셨습니다 | You suffered | Thank you for your work / Great work |
| 참고 부탁드립니다 | Please refer | FYI / Please note |
| ~할 예정입니다 | It is planned to | We will / We plan to |
| 긍정적으로 검토하겠습니다 | We will review positively | We'll give it serious consideration |

- 호칭·직급: "김 부장님" → 영어 본문에서는 "Mr./Ms. Kim" 또는 이름+직함("Director Kim"). 이메일 인사말은 "Hi/Dear + 이름". 직급 대응은 용어집의 직급 표를 따른다.
- 존댓말 자체는 번역 대상이 아니다. 문서의 격식 수준(공식/준공식)으로 환산한다.

## 4. 헤징(hedging) 조정

한국어 보고서의 "~할 것으로 사료됨", "~로 판단됨", "~를 검토 중임"을 전부 "it is considered that..."으로 옮기면 책임 회피처럼 읽힌다.

- 근거 있는 판단 → 단정형: "매출 증가가 예상됨" → "We expect revenue to grow."
- 진짜 불확실 → 명시적 hedge: "may", "likely", "preliminary"
- "사료됨/판단됨/보임"의 3중 완곡은 한 번의 hedge로 축소한다.

## 5. 중복·잉여 제거

한국어에서 자연스러운 반복은 영어에서 잉여다.

- "사전에 미리", "먼저 선행되어야" → "in advance" 하나로
- "~에 대한 부분", "~와 관련된 사항" → 대부분 삭제하고 명사 직결
- "적극 협조", "성실히 수행" 같은 관용 부사는 문맥상 의미가 있을 때만 옮긴다.

## 6. 로마자 표기

- 인명: 국어의 로마자 표기법(Revised Romanization) 기본, 단 **본인이 쓰는 공식 표기가 확인되면 그것을 따른다** (예: 이 → Lee, 김 → Kim 등 관용 표기 허용). 이름 순서는 성-이름 대신 이름-성(Gildong Hong)을 기본으로 하되 문서 관례를 따른다.
- 지명·기관명: 공식 영문 명칭이 있으면 반드시 그것을 사용 (예: 국세청 → National Tax Service).
- 회사 내부 조직명: 용어집 우선. 없으면 의미 번역 후 `[TN]` 표시.

## 7. 한국 고유 개념

- 원화 금액: `style-formatting.md`의 통화 규칙 적용 (₩1.2 billion 또는 KRW 1.2 billion, 만/억 단위 환산 주의 — 1억 = 100 million).
- 회계연도, 분기 표기: "24년 3분기" → "Q3 2024".
- 고유 제도·문화 용어(전세, 연말정산, 회식 등): 확립된 영어 표현이 있으면 사용, 없으면 로마자 + 짧은 설명 1회 후 로마자만 사용.
