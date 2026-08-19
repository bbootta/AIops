# 계정 리서치: Robinhood Markets

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/us-d4-robinhood.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].
> 규제 프레임 주의(4차 배치 확정): 브로커딜러는 SR 26-2가 아니라 FINRA·SEC 프레임이다.

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Robinhood Markets (US-D4) / Tier 2 |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 강)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 리테일 100만 명 규모에 배포된 생성형 AI "Cortex"를 2026-06-03 어드바이저(RIA) 채널까지 확장하면서 정작 경영진 스스로 "규제 제약 때문에 AI가 자산을 직접 운용할 수 없다"고 선을 긋는 지금이, 그 선(가드레일)을 코드와 감사 기록으로 증명해야 하는 FINRA·SEC의 2026 AI 감독 첫 사이클이기 때문이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| AI 채널 확장 | SYNERGY26(6/2~4, 워싱턴 D.C.)에서 "Robinhood Cortex for Advisors" 발표: 리테일 ~100만 명에 배포된 Cortex AI를 TradePMR Fusion 플랫폼의 RIA에 무상 제공. Advisor Network(고객-RIA 연결)도 동시 발표 | 2026-06-03 | https://robinhood.com/us/en/newsroom/robinhood-tradepmr-synergy26/ · https://www.investmentnews.com/transformation/robinhood-brings-ai-powered-cortex-to-rias-on-tradepmr/266861 |
| AI 정책 공표 (거버넌스 스탠스) | "AI in Financial Services" 정책 페이지 갱신: AI 활용 원칙·한계 공개. 경영진은 "규제 제약상 AI의 직접 자산 운용 불가" 입장을 공개 언급 | 2026-01 (월 단위, 페이지 Last Updated 기준) | https://robinhood.com/us/en/policy/ai-in-financial-services |
| 세그먼트 공통 (규제) | FINRA 2026 Annual Regulatory Oversight Report: GenAI 거버넌스(정확도·편향 테스트, 프롬프트·출력 로깅), WSP에 AI 에이전트 모니터링 반영 요구. SEC FY2026 시험 우선순위: AI 사용 정책·절차·감독 적정성 | 2025-12 / 2025-11 | https://www.sidley.com/en/insights/newsupdates/2025/12/finra-issues-2026-regulatory-oversight-report · https://www.akingump.com/en/insights/alerts/sec-announces-2026-exam-priorities |

- 유효기간 판정(KB03 §5.2): Cortex for Advisors 발표는 약 11주 경과로 유효창 내. 리테일 대규모 배포 + 어드바이저 채널 확장의 연속 확대 = 강.
- 정직 표기: AI 거버넌스 직책 신설 채용, 신임 리스크 임원, AI 관련 감독 지적은 이번 조사에서 발견하지 못했다. 에이전틱 트레이딩의 거버넌스·책임 논쟁은 외부 분석(fintechlaw.ai, 게재일 미확인)으로 맥락으로만 취급한다.

## 3. 가설

리테일 100만 명 + RIA 채널에 확장된 생성형 AI가 투자 아이디어를 생성하는 구조는 적합성·감독·기록보존·편향 테스트 의무가 정면으로 걸리는 표면이며, "AI는 운용하지 않는다"는 경계선을 규제자에게 증명하려면 조회 전용·제안 전용·승인 우선 가드레일과 출력 로깅이 코드 수준에서 감사 가능해야 한다. 급성장 디지털 브로커 특성상 이 어슈어런스 계층이 확산 속도를 못 따라갈 개연이 있다는 가설. 단정하지 않는다: 내부 통제 현황은 미확인이다.

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer / Head of Risk | US | 미수집 (PO 도구) | EB. Cortex 확산 리스크 소유 |
| (PO 특정) | Chief Compliance Officer (브로커딜러) | US | 미수집 (PO 도구) | FINRA GenAI 거버넌스·로깅 요구 대응 |
| (PO 특정) | Head of AI / ML Platform (Cortex 소유 조직) | US | 미수집 (PO 도구) | 기술 구매자. 가드레일·로깅 구현 접점 |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일은 PO(도구) 공급 후 충족. US 수신 근거: CAN-SPAM 옵트아웃 기준. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 US 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: Cortex for Advisors 발표(2026-06-03, RIA 채널 확장).
- 영문 초안: `Robinhood just extended Cortex from a million retail users to RIAs, while telling the press that regulation still keeps AI from managing assets directly; proving that boundary in code and audit logs is exactly what FINRA's 2026 report asks for.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: SEC/FINRA 규제 디지털 브로커딜러(국법은행 인가 절차 상태는 [검증 필요]), 관할 US
- [x] H5 해당 없음: 경쟁사 아님 (Cortex는 자사 소비자·어드바이저 기능이며 AI 거버넌스 SaaS 아님)
- [x] S1·S2 검토: 자체 AI 개발 역량 높음. 단 AI "거버넌스·독립검증" 플랫폼 도입 증거 없음
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | "AI는 운용하지 않는다" 경계선의 코드화: 제안 전용·승인 우선 가드레일 + 출력 로깅 감사 원장 (PRD-AIG) | Cortex for Advisors (2026-06-03) + AI 정책 페이지 (2026-01) | 이메일 |
| 2 | GenAI 정확도·편향 테스트의 상시 독립검증: FINRA 2026 기대 대응 (PRD-VAL) | FINRA 2025-12 | 이메일 / LinkedIn |
| 3 | 디자인 파트너: 최대 리테일 AI 배포 사례의 거버넌스 선례 | 리테일 ~100만 배포 + RIA 확장 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
