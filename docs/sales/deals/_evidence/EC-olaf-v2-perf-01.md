# 증거 카드: EC-olaf-v2-perf-01

> 저장 경로: `docs/sales/deals/_evidence/EC-olaf-v2-perf-01.md` (계정 무관 공용 라이브러리)
> 카피·제안서·설문 답변의 모든 사실 주장은 이 카드의 등급 규칙을 따른다. [확인] 등급만 사실로 진술할 수 있다 [G3].

| 항목 | 내용 |
|---|---|
| 카드 ID | EC-olaf-v2-perf-01 |
| 작성 에이전트 | deal-strategist |
| 검토 | outreach-qa (원출처 대조) 대기 (미실시) |
| 승인 | 해당 없음 (내부 라이브러리) |
| 기준일 | 2026-08-19 (재검증 주기: 분기) |

## 1. 카드 요약

- 주장 한 줄: 한국어 추론 모델 OLAF v2(14B/1.5B, 32K 컨텍스트)를 허깅페이스에 공개했고, 회사 발표 기준 GSM8K 91.96, Omni-MATH 36.20으로 발표 시점 GPT-4o(91.21/30.75)를 상회했다.
- **신뢰 등급 (KB08 규칙): [단일 출처]** (회사 발표 + 이를 전한 언론 보도 1건. KB08 §4.2)
- 사용 범위: **"회사 발표 기준(company-reported)" 표기와 측정·비교 시점 고정 없이는 대외 사용 금지** [G3]. 출처를 밝히고 사용하는 조건부 카드.
- 주 사용처: 기술 구매자 대상 오픈소스 실증(모델 카드 링크 아웃리치), 트러스트 패키지 부록.
- **이 쐐기(AI 거버넌스·독립검증)에서의 사용 맥락**: 성능 자랑이 아니라 "우리는 모델을 공개하고 수치에 시점·조건을 붙여 말하는 팀"이라는 정직성 신호로 쓴다. 수치 인용 자체보다 허깅페이스 공개(검증 가능성)가 이 쐐기의 포인트다.

## 2. 주장 (정확한 형태)

원라인AI는 2025년 한국어 추론 모델 OLAF v2를 허깅페이스에 공개했다(14B/1.5B 2종, 32K 컨텍스트, 생각 프로세스 + 테스트 타임 스케일링, RAG·도구 사용 친화 설계). 회사 발표 기준, 공개 시점 벤치마크에서 GSM8K 91.96, Omni-MATH 36.20을 기록해 당시 비교 대상이었던 GPT-4o(91.21/30.75)를 상회했다고 발표했다. 비교 대상과 시점이 고정된 수치이며, 이후 프론티어 모델과의 비교로 일반화할 수 없다.

## 3. 원출처

| 출처 | 유형 | URL/문서 | 확인일 | 비고 |
|---|---|---|---|---|
| AI타임스, 올라프 v2 공개 | 언론 보도 (회사 발표 전달) | https://www.aitimes.com/news/articleView.html?idxno=167331 | 2026-08-18 (KB08 기준일) | **회사 발표 기준 수치** |
| 허깅페이스 모델 카드 (OLAF v2) | 회사 공개 자산 | 허깅페이스 (정확한 URL은 발송 전 확인) | 미확인 | 링크 확정 필요 |
| KB08 §4.2, §11.1 | 내부 KB | kb/sales/08-oneline-ai-context.md | 2026-08-19 | [단일 출처] 등급 근거 |

- 단일 계열 출처(회사 발표)이므로 [단일 출처]. 독립 재현·제3자 평가가 확인되면 등급 상향 검토.

## 4. 사용 가능한 문구

- 영문 (풀 문장): `We open-sourced OLAF v2, a Korean reasoning model (14B and 1.5B, 32K context), on Hugging Face. Per our benchmark results reported at release, it scored 91.96 on GSM8K and 36.20 on Omni-MATH, above the GPT-4o figures at that time (91.21 / 30.75). Model cards and weights are public, so you can verify rather than take our word.`
- 영문 (짧은 형, 카피 삽입용): `our open-sourced reasoning model OLAF v2 (benchmarks company-reported at release, weights public on Hugging Face)`
- 국문: `OLAF v2는 회사 발표 기준 GSM8K 91.96으로 발표 시점의 GPT-4o를 상회했습니다 (허깅페이스 공개, 측정 시점 고정).`
- 페르소나별 변형:
  - 기술 구매자용: `Instead of a deck, here is the model card: OLAF v2 on Hugging Face. Benchmarks are company-reported at release; the weights are public, reproduce them yourself.`

## 5. 사용 금지 표현

- "회사 발표 기준(company-reported)" 표기 생략 (등급 규칙 위반, 즉시 FAIL)
- 현행 최신 프론티어 모델 대비 우위로 일반화 ("beats GPT-4o" 단독 사용 금지. 비교 대상·시점 고정 수치다, KB08 §11.2)
- "GPT-4o보다 뛰어난 모델을 보유" 류의 시점 없는 현재형 진술
- OLAF v2 수치를 RYNTA·OLA의 제품 성능인 것처럼 연결하는 것

## 6. 사용 이력과 유효성

| 사용처 (문서/캠페인) | 일자 | outreach-qa 대조 |
|---|---|---|
| 20260818-usuk-rynta-aigov (예정: 기술 구매자 부록) | 미발송 | 대기 |

- 허깅페이스 모델 카드 URL 확정 전에는 링크 포함 발송 불가. 원출처 소멸 시 카드 폐기.
