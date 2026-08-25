# 계정 리서치: Interactive Brokers

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/us-d6-interactive-brokers.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].
> 규제 프레임 주의(4차 배치): 브로커딜러는 SR 26-2가 아니라 FINRA·SEC 프레임이다.

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Interactive Brokers (US-D6) / Tier 2 |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 강)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 2026-06-01 Claude 연동 에이전틱 트레이딩을 시작으로 6월 ChatGPT·Grok, 7월 28일 MCP 표준 전면 개방까지 3개월 연속으로 "서드파티 AI 에이전트가 고객 계정에 주문 지시를 넣는" 표면을 확대했고, FINRA 2026 보고서가 WSP에 "AI 에이전트 모니터링"을 정면으로 요구하는 첫 검사연도이기 때문이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 에이전틱 AI 프로덕션 (1) | Claude 직접 연동 에이전틱 트레이딩 공개: 고객이 AI로 계정 관리·170+ 시장 접근, "informed by agentic technology, controlled by the client" | 2026-06-01 | https://www.interactivebrokers.com/en/general/about/mediaRelations/6-1-26.php |
| 에이전틱 AI 프로덕션 (2) | ChatGPT·Grok 추가, 주문 지시 대상 상품을 옵션·선물·선물옵션까지 확대 | 2026-06-22 | https://www.interactivebrokers.com/en/general/about/mediaRelations/6-22-26.php |
| 에이전틱 AI 프로덕션 (3) | MCP 표준 기반 도구 전면 개방: Claude Code, Cursor, Perplexity 등 사실상 임의의 MCP 호환 AI 도구에서 계정 연결 | 2026-07-28 | https://www.interactivebrokers.com/en/general/about/mediaRelations/7-28-26.php |
| 세그먼트 공통 (규제) | FINRA 2026 Annual Regulatory Oversight Report: WSP에 AI 거버넌스·AI 벤더 리스크·**AI 에이전트 모니터링** 반영 요구, GenAI에도 감독·기록·공정거래 규칙 전면 적용 | 2025-12 (발행) | https://www.mcguirewoods.com/client-resources/alerts/2025/12/finras-2026-annual-regulatory-oversight-report-same-priorities-new-focus-on-ai-and-cybersecurity/ |

- 유효기간 판정(KB03 §5.2): 3건 모두 1~3개월 내 실측, 유효창 정중앙. 3개월 연속 확대 = 일회성 발표가 아니라 전략 방향. 복수 시그널 겹침 = 티어 상향 후보 요건(icp-draft §4).
- 정직 표기: AI 거버넌스 조직·모델검증 채용, 감독 지적은 이번 조사에서 발견하지 못했다. IBKR가 이 표면을 내부에서 어떻게 통제하는지는 미확인 [검증 필요].

## 3. 가설

서드파티 AI 에이전트(자사 통제 밖 모델)가 고객 계정에서 주문 지시까지 수행하는 구조는 감독·기록보존·적합성·시장 접근 통제 의무가 곧바로 걸리는 신규 리스크 표면이며, MCP 전면 개방으로 그 표면이 "임의의 도구"로 넓어졌다. 가드레일(조회 전용, 제안 전용, 승인 우선, 최소 권한, Kill Switch)을 코드로 강제하고 에이전트 행위를 감사 원장에 남기는 계층에 대한 수요가 생겼을 것이라는 가설. RYNTA의 가드레일 5종·자동확정 금지 구조와 문제 정의가 정확히 겹친다. 단정하지 않는다: 내부 통제 현황은 미확인이다.

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer / Head of Risk | US | 미수집 (PO 도구) | EB. 에이전틱 채널 리스크 소유 |
| (PO 특정) | Chief Compliance Officer (브로커딜러) | US | 미수집 (PO 도구) | FINRA WSP·AI 에이전트 모니터링 의무 대응 |
| (PO 특정) | CTO / Head of AI (에이전틱 플랫폼 소유 조직) | US | 미수집 (PO 도구) | 기술 구매자·가드레일 구현 접점 |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일은 PO(도구) 공급 후 충족. US 수신 근거: CAN-SPAM 옵트아웃 기준. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 US 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 2026-07-28 MCP 전면 개방(임의의 AI 에이전트가 계정 연결).
- 영문 초안: `Interactive Brokers just opened client accounts to any MCP-compatible AI agent, weeks after FINRA's 2026 report told firms their supervisory procedures now need to cover monitoring of AI agents.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: SEC/FINRA 규제 전자 브로커딜러, 알고·모델 밀도 최상급, 관할 US
- [x] H5 해당 없음: 경쟁사 아님 (자사 트레이딩 플랫폼이며 AI 거버넌스 SaaS 판매사 아님)
- [x] S1·S2 검토: 자체 기술 역량은 높으나 AI "거버넌스·독립검증" 플랫폼 전사 도입 증거 없음
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 에이전틱 채널 가드레일의 코드화: 조회 전용·제안 전용·승인 우선·Kill Switch를 감사 가능하게 (PRD-AIG) | MCP 개방 2026-07-28 | 이메일 |
| 2 | FINRA "AI 에이전트 모니터링" WSP 요건 대응: 에이전트 행위 감사 원장 + 상시 독립검증 (PRD-VAL) | FINRA 2025-12 + 3연속 확대 | 이메일 / LinkedIn |
| 3 | 디자인 파트너: 업계에서 가장 공격적인 에이전틱 개방 사례의 통제 계층 선례 만들기 | 6-1/6-22/7-28 연속 발표 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
