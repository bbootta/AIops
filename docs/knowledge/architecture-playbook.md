# 에이전트·시스템 아키텍처 플레이북

> System Architect 에이전트의 지식 기반. 2025-26 웹 리서치 결과를 요약·영구화한 문서.
> 대상: 원라인AI 제품의 에이전트/시스템 아키텍처 설계, 기술 스펙, 개발 계획.

## 1. 핵심 원칙

### "워크플로우 우선, 에이전트는 필요할 때만" (2025-26 업계 합의)
- Anthropic [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents): 프롬프트 체이닝 · 라우팅 · 병렬화 · 오케스트레이터-워커 · 평가자-최적화자 5개 워크플로우 패턴. 복잡한 프레임워크보다 "단순하고 조합 가능한 패턴"으로 시작.
- OpenAI [A Practical Guide to Building Agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf): 싱글 에이전트로 시작, 한계에 부딪힐 때만 멀티 에이전트(Manager 패턴 / Decentralized 핸드오프)로 확장.
- **권고 에스컬레이션 순서**: ① raw API + 구조화 출력 → ② 워크플로우 패턴 → ③ 싱글 에이전트 → ④ 멀티 에이전트 (병렬 분해 가능성 입증 시에만).

### 멀티 에이전트의 경제학
- 멀티 에이전트는 일반 채팅 대비 토큰 약 **15배** 소모 (Anthropic 실측).
- Sonnet 서브에이전트 병렬 구조가 단일 Opus 대비 리서치 평가에서 90.2% 우위. 성능 분산의 ~80%가 토큰 사용량으로 설명됨.
- 결론: **breadth-first로 병렬 분해 가능한 작업에만** 멀티 에이전트가 정당화됨. 그 외에는 싱글 에이전트 + 컨텍스트 엔지니어링.

### 컨텍스트 엔지니어링 > 프롬프트 엔지니어링
- 원칙: "최소한의 고신호 토큰 집합" ([Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).
- 표준 기법: 컴팩션(요약 후 재시작), 서브에이전트 컨텍스트 격리, 메모리 도구, programmatic tool calling.
- 도구 설계: "사람 엔지니어가 어떤 도구를 쓸지 확답 못 하면 에이전트도 못 한다" — 도구 중복 금지 ([Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)).

### MCP는 사실상 표준
- 2024.11 출시 → 2025.3 OpenAI 채택 → 2025.12 Linux Foundation 기부 → 2026.3 월 9,700만 다운로드. Fortune 500의 28%가 MCP 서버 구축.
- **새 통합은 MCP 기반이 기본값.**

## 2. 프로덕션 스택 표준

### RAG 파이프라인
- 하이브리드 검색(BM25 + 벡터, RRF 융합)이 단일 방식 대비 일관 우위 (WANDS NDCG 0.7497, +7.4%).
- 표준 파이프라인: **top-50 하이브리드 검색 → 크로스인코더 리랭킹 top-5 → LLM**. RAGAS 기준 답변 품질 15-30% 개선.
- 청킹: 질문 표현과 정렬된 헤더/메타데이터 포함이 핵심.

### 비용 엔지니어링 레버 (정량)
| 레버 | 절감폭 | 비고 |
|---|---|---|
| 프롬프트(프리픽스) 캐싱 | 비용 최대 90%, 지연 85% | 캐시 쓰기 +25%, 읽기 10%. 2회 이상 히트 시 손익분기 |
| Batch API | 50% 고정 | 비실시간 작업 전부 |
| 모델 라우팅/캐스케이드 | 40-70% | 요청의 60-80%는 저가 모델로 충분 |
| 시맨틱 캐싱 결합 | 총 47-80% | 현실적 플레이북 |

### 관측/평가 스택 3강
- **Langfuse**: 오픈소스, 셀프호스팅 최강 → 데이터 주권/망분리 환경. **한국 엔터프라이즈 납품 기본 후보.**
- **LangSmith**: LangChain/LangGraph 스택 밀착.
- **Braintrust**: 평가 중심, CI/CD 품질 게이트.
- 트레이싱(요청 단위)과 세션 단위(에이전트 전체 궤적) 분석을 구분해 요구할 것.

### 가드레일: 다층 방어(defense-in-depth)가 정석
- OWASP LLM Top 10 최상위: 프롬프트 인젝션 · 정보 유출.
- 수렴 중인 스택: Presidio(PII) → Prompt Guard 2(인젝션 탐지) → NeMo Guardrails(레일 오케스트레이션) → Llama Guard 4(출력 분류) → 스키마 검증기.
- **단일 가드레일 금지** — 입력 → 대화 정책 → 출력 → 행동 게이팅(고위험 도구는 human-in-the-loop) 4계층.

### 에이전트 메모리 (필요 시)
- Mem0(추출-업데이트 2단계, p95 검색 0.2초, 풀컨텍스트 26,031토큰 대비 ~1,764토큰), Letta/MemGPT(OS식 페이징), Zep(시간적 지식그래프).
- 시간 추론 중요 시 그래프 기반 우위 (Mem0g 58.13% vs OpenAI 21.71%).

### 프레임워크 선택
- 동일 모델에서 스캐폴드에 따라 GAIA 점수 최대 30%p 차이 (64.9% vs 57.6%).
- LangGraph(프로덕션 성숙 Tier 1) / OpenAI Agents SDK(단순함) / Claude Agent SDK(라이프사이클 제어).
- 도구 1-2개짜리 단순 작업은 프레임워크 없이 raw API 권장.

## 3. 의사결정 프레임워크

### 프롬프팅 → RAG → 파인튜닝 에스컬레이션
1. 항상 프롬프트 엔지니어링부터 (시간 단위 비용).
2. 실시간/사내 지식 필요 → RAG (월 $70-1,000).
3. 스타일·형식·도메인 특화 행동만 → LoRA/QLoRA 파인튜닝.
- **"새 사실 주입은 파인튜닝이 아니라 RAG의 일"** — 파인튜닝 요청이 지식 주입 목적이면 RAG로 반려.

### 빌드 vs 바이
- 저가 오픈웨이트 API 등장으로 셀프호스팅 손익분기가 월 수십억 토큰 수준까지 밀려남.
- GPU 비용의 2.5-3배 숨은 비용 + 엔지니어링 인건비(연 $500K+ 상당)가 실질 변수.
- 기본 경로: **API로 시작 → 규모/규제 요건에서 하이브리드**. 단, 한국은 규제가 비용보다 먼저 셀프호스팅을 강제하는 경우가 많음.

### 한국 시장 규제 지형 (아키텍처 결정 트리 최상단)
- **AI 기본법 2026.1 시행** — 고영향 AI 해당 여부 확인 필수.
- 금융위 망분리 규제 개선: 2026.4 전자금융감독규정시행세칙 개정으로 내부망 SaaS 이용 허용, 생성형 AI 망분리 예외 순차 확대.
- 금융 AI 가이드라인 7대 원칙: 거버넌스 · 합법성 · 보조수단성 · 신뢰성 · 금융안정성 · 신의성실 · 보안성.
- 금융·공공·의료·국방 고객 → 기본 스택: **온프레미스/VPC + 오픈웨이트(EXAONE, Solar, A.X 등 국산 모델 포함) + Langfuse 셀프호스팅**.
- 소버린 AI: 정부 독자 AI 파운데이션 모델 프로젝트(2,136억원) — 2025.12 1차 평가에서 LG(EXAONE) · SKT(A.X) · 업스테이지(Solar) 2차 진출.

## 4. 문서화 표준

### ADR (Architecture Decision Record)
- 결정마다 맥락/결정/대안/결과를 마크다운으로 번호 매겨 불변 기록. 상태(제안/승인/폐기) 추적.
- C4 다이어그램(Context → Container → Component → Code, Mermaid로 작성)과 링크해 "결정이 어디에 영향을 주는지" 탐색 가능하게.

### AI 테크스펙 필수 5개 섹션
1. **평가 계획**: 오프라인 벤치마크 + 레드팀 + A/B, 수용 임계값 명시.
2. **환각/오류 허용 한도**와 사용자 노출 정책.
3. **폴백 체인**: 모델 장애·저품질 응답 시 캐스케이드/거부/인간 이관.
4. **비용 예산과 지연 SLO**: 예상 월 토큰량, 캐싱 적중률 가정, 라우팅 비율, 배치 가능 비율.
5. **가드레일 계층 설계**.
- 리뷰 규칙: **"success metric이 '잘 작동'이면 반려."**

### 프로덕션 준비도: Google ML Test Score 확장
- 데이터/모델/인프라/모니터링 4개 영역 28개 테스트 루브릭을 LLM용으로 확장:
  평가 데이터셋 존재, LLM-as-judge 루브릭의 인간 캘리브레이션, 프로덕션 실패 사례의 평가셋 환류.
- 원칙: **"관측 없는 AI 기능은 미완성."**

## 5. 시스템 디자인 리뷰 체크리스트 (요약)

- [ ] 이 기능에 정말 멀티 에이전트/프레임워크/파인튜닝이 필요한가? (에스컬레이션 순서 준수)
- [ ] 정량 비용 모델 포함? (월 토큰량, 캐싱 적중률, 라우팅 비율, 배치 비율)
- [ ] 규제 체크: 고객이 금융/공공/의료/국방인가? → 망분리·AI기본법·데이터 이전 확인
- [ ] 평가 계획 + 관측 스택 선정 + 실패→평가셋 환류 경로 존재?
- [ ] 폴백 체인 정의? (모델 장애, 저품질, 비용 초과)
- [ ] 가드레일 4계층 설계?
- [ ] 컨텍스트 예산: 시스템 프롬프트 크기, 도구 응답 상한, 컴팩션 전략, 메모리 계층
- [ ] 도구/MCP: 중복 없는 도구 세트, 토큰 효율적 응답, MCP 우선
- [ ] ADR 작성 + C4 다이어그램 링크

## 주요 출처
Anthropic Building Effective Agents / Effective Context Engineering / Writing Tools for Agents · OpenAI A Practical Guide to Building Agents · MCP 2026 Roadmap · Denser/StackAI RAG Best Practices · Latitude 관측도구 비교 · Mavik Labs LLM Cost Optimization · ClickHouse LLM Guardrails · Mem0 논문 · Agent Frameworks 2026 비교 · Cloudzy Self-Hosting Cost · Google ML Test Score · 금융위 망분리 규제 개선 · 바이라인네트워크 독자 AI 파운데이션 모델
