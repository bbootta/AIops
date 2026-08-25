# 증거 카드: EC-krx-bench-01

> 저장 경로: `docs/sales/deals/_evidence/EC-krx-bench-01.md` (계정 무관 공용 라이브러리)
> 카피·제안서·설문 답변의 모든 사실 주장은 이 카드의 등급 규칙을 따른다. [확인] 등급만 사실로 진술할 수 있다 [G3].

| 항목 | 내용 |
|---|---|
| 카드 ID | EC-krx-bench-01 |
| 작성 에이전트 | deal-strategist |
| 검토 | outreach-qa (원출처 대조) 대기 (미실시) |
| 승인 | 해당 없음 (내부 라이브러리) |
| 기준일 | 2026-08-19 (재검증 주기: 분기) |

## 1. 카드 요약

- 주장 한 줄: 금융 특화 LLM 평가 벤치마크 KRX-Bench를 한국거래소(KRX)와 공동개발했고, 제3회 KRX 금융 언어모델 경진대회(약 233팀, 1,119개 모델 제출)의 평가 기준으로 사용되었다.
- **신뢰 등급 (KB08 규칙): [확인]** (KB08 §3.1, §4.3, §5. 언론 보도 + 회사 블로그 교차)
- 사용 범위: 대외 사실 진술 가능 [G3].
- 주 사용처: 독립검증(PRD-VAL) 대화의 훅, 자체구축 반대논거 대응, 트러스트 패키지.
- **이 쐐기(AI 거버넌스·독립검증)에서의 사용 맥락**: "국가 거래소가 1,100개 이상의 모델을 심사하는 기준으로 우리 벤치마크를 썼다"는 사실은 모델 평가·독립검증 역량의 가장 구체적인 실증이다. "금융 특화 평가셋 없이는 검증 자체가 안 된다"(KB08 §7.3)는 논거의 근거 카드.

## 2. 주장 (정확한 형태)

원라인AI는 금융 특화 언어모델 평가 벤치마크 KRX-Bench를 한국거래소(KRX)와 공동개발했다. KRX-Bench는 KRX가 주최한 제3회 KRX 금융 언어모델 경진대회(2024-10~12, AWS·코스콤 협력, 약 233팀 참가, 1,119개 모델 제출)의 평가 기준으로 사용되었고, 원라인AI는 이 대회의 운영사로 참여했다. GPT-4를 활용한 벤치마크 자동 생성 연구 블로그도 공개했다.

## 3. 원출처

| 출처 | 유형 | URL/문서 | 확인일 | 비고 |
|---|---|---|---|---|
| 파이낸셜뉴스, 제3회 KRX 금융 언어모델 경진대회 개최·시상 | 언론 보도 | https://www.fnnews.com/news/202410131201014123 및 202412201652561491 | 2026-08-18 (KB08 기준일) | 참가 규모 근거 |
| AI타임스, 국제 학회 금융 LLM 벤치마크 발표 | 언론 보도 | https://www.aitimes.com/news/articleView.html?idxno=159967 | 2026-08-18 (KB08 기준일) | |
| OneLineAI 공식 블로그 (KRX-Bench 포스트) | 회사 자료 | https://onelineai.com/ 블로그 | 2026-08-18 (KB08 기준일) | 벤치마크 자동 생성 연구 |
| KB08 §3.1, §4.3, §5 | 내부 KB | kb/sales/08-oneline-ai-context.md | 2026-08-19 | [확인] 등급 부여 근거 |

- 복수의 독립 출처 교차 확인으로 [확인] 등급.

## 4. 사용 가능한 문구

- 영문 (풀 문장): `We co-developed KRX-Bench, a finance-specific LLM evaluation benchmark, with the Korea Exchange. It served as the judging standard for a KRX-hosted competition where roughly 233 teams submitted over 1,100 models.`
- 영문 (짧은 형, 카피 삽입용): `KRX-Bench, the finance-specific benchmark a national exchange used to judge 1,100+ models`
- 국문: `한국거래소와 공동개발한 KRX-Bench가 KRX 금융 언어모델 경진대회(약 233팀, 1,119개 모델)의 평가 기준으로 사용됐습니다.`
- 페르소나별 변형:
  - Head of Model Validation용: `When a national exchange needed to evaluate over 1,100 financial language models, the benchmark used was one we co-developed. Evaluation at scale is our core competence, and it is what continuous independent validation requires.`
  - CRO용: `Our validation credentials are institutional: KRX co-developed and used our benchmark as its official judging standard.`

## 5. 사용 금지 표현

- "KRX 공식 인증/공인 벤치마크" (확인된 것은 공동개발 + 대회 평가 기준 사용)
- "KRX가 원라인AI를 독점 운영사로 선정" (확인된 것은 "운영사 참여", AWS·코스콤 협력 구도)
- 참가 규모 수치 변형(반올림 과장 등). 인용 시 "약 233팀, 1,119개 모델 제출" 그대로
- KRX-Bench를 US/UK 규제 검증 기준인 것처럼 암시하는 것 (한국어·한국 금융 도메인 벤치마크다)

## 6. 사용 이력과 유효성

| 사용처 (문서/캠페인) | 일자 | outreach-qa 대조 |
|---|---|---|
| 20260818-usuk-rynta-aigov (예정: PRD-VAL 훅) | 미발송 | 대기 |

- 원출처가 소멸·변경되면 카드를 폐기하거나 등급을 강등하고, 이 카드를 인용한 산출물을 재점검한다.
