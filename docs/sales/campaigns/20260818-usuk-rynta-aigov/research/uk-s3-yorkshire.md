# 계정 리서치: Yorkshire Building Society

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/uk-s3-yorkshire.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Yorkshire Building Society (UK-S3) / Tier 1 |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-18 (유효기간: 2026-09-17까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고. 1차 배치 중 시그널 최강)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 2026년 6~7월 두 달 사이에 에이전틱 AI 언더라이팅(Covecta 파트너십)과 민원 처리 AI 에이전트 3종을 연달아 실전 배치했고, "AI-first 운영 모델"을 공언한 조직이 SS1/23 하에서 다음에 부딪히는 문제가 바로 이 AI들의 거버넌스·검증 상시화이기 때문이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.
- **선행 조건(ICP 배너)**: SOC 2 등 인증 상태 확인 전 Tier 1 보류 해제 금지.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 생성형·에이전틱 AI 도입 (언더라이팅) | Covecta와 파트너십 발표. 모기지 언더라이팅에 에이전틱 AI 배치(문서 검토 등 행정 업무), Accord Mortgages 포함 모기지 라이프사이클 핵심 단계 적용. "AI-first 운영 모델" 지향 공언. 최종 대출 판단은 인간 유지 강조 | 2026-06-24 | https://ibsintelligence.com/ibsi-news/yorkshire-building-society-taps-covecta-for-ai-underwriting/ |
| 생성형 AI 도입 (민원·고객 서비스) | AI 에이전트 3종(Penelope·Sam·Alf) 배치: 민원 요약, 정책·과거 사례 검색, 민원 최종 답변 초안. human-in-the-loop 명시. Sam 건당 7분, Penelope 최대 26분 절감 주장 | 2026-07 (보도) | https://www.itpro.com/business/business-strategy/yorkshire-building-society-touts-customer-service-gains-with-ai-agents , https://customerservicemanager.com/yorkshire-building-society-uses-ai-agents-to-streamline-member-services/ |
| AI 확산·거버넌스 태세 (맥락) | 약 100개 AI 유스케이스 진행, Data and AI Academy 운영(600명+ 수료), 차기 초점은 Agentic AI·지능형 워크플로. "신뢰 없이는 확장 없다" 프레임의 심층 보도 | 2026 (보도) | https://www.computing.co.uk/feature/2026/yorkshire-building-society-ai-playbook , https://ukstories.microsoft.com/features/how-yorkshire-building-society-is-using-ai-to-give-colleagues-more-time-for-members/ |

- 유효기간 판정(KB03 §5.2): Covecta(2026-06-24, 약 8주 경과)·AI 에이전트(2026-07)는 생성형 AI 도입 시그널 유효창(1~6개월) 내. 복수 시그널 스택으로 Tier 상향 요건(KB03 §5.3) 충족.
- 정직 표기: 신임 CRO/Head of Model Risk 선임·모델검증 채용공고는 이번 조사에서 발견하지 못했다.

## 3. 가설

YBS는 1차 배치 8개 계정 중 AI 실전 배치 밀도가 가장 높다. 언더라이팅(대출 판단 인접, 고위험 영역)과 민원 처리에 에이전틱 AI를 이미 넣었고 100개 유스케이스를 공언했으므로, AI 인벤토리·가드레일·감사 로그를 감사 가능하게 유지하는 부담이 급증하고 있을 것이라는 가설이다. 보도마다 human-in-the-loop을 강조하는 것은 내부적으로 그 통제를 증명해야 할 압력(PRA·소비자보호)이 있다는 방증으로 읽힌다. "승인 우선·제안 전용·Kill Switch가 코드로 구현된 가드레일"(PRD-AIG)과 "에이전트가 보조하되 결정론 엔진이 재계산하는 독립검증"(PRD-VAL)이 정면 접점이다. 단정하지 않는다: 거버넌스 체계를 Microsoft·Covecta 스택 내에서 해결하려 할 수 있다([검증 필요]).

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer 또는 Head of Model Risk | UK | 미수집 (PO 도구) | EB. 에이전틱 AI의 리스크 통제 증명 책임 |
| (PO 특정) | Chief Data/AI Officer 또는 Data & AI 조직장 | UK | 미수집 (PO 도구) | 100개 유스케이스 확장의 거버넌스 병목 소유자. 챔피언 후보 |
| (PO 특정) | Director of Customer Support (민원 AI 운영 라인) | UK | 미수집 (PO 도구) | AI 에이전트 실사용 조직. 실무 검증자 |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일·LIA·보관기간 만료일은 PO(도구)·sales-compliance-officer 공급 후 충족. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 UK 확정, 법인 가입자 = building society)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 에이전틱 AI 언더라이팅 배치(2026-06-24).
- 영문 초안: `Noticed YBS put agentic AI into mortgage underwriting in June with humans keeping the final say, which usually makes proving that oversight, model by model, the next bottleneck under SS1/23.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: PRA 규제 빌딩소사이어티, AI/ML 도입 실재(고밀도), 관할 UK, 법인 가입자
- [x] H5 해당 없음: 경쟁사 아님 (Covecta는 YBS의 벤더이지 이 계정의 성격을 바꾸지 않음. S2 "대형 AI 거버넌스 플랫폼 전사 도입 완료"에도 해당 근거 없음)
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 에이전틱 AI 가드레일 코드화: 언더라이팅·민원 AI의 human-in-the-loop 주장을 조회 전용·제안 전용·승인 우선·Kill Switch 가드레일과 감사 원장으로 증명 가능하게 (PRD-AIG) | Covecta 2026-06-24, AI 에이전트 2026-07 | 이메일 |
| 2 | 100개 유스케이스의 인벤토리·검증 상시화: 유스케이스 확산 속도를 따라가는 상시 독립검증 (PRD-VAL) | 100개 유스케이스·AI Academy 보도 | 이메일 / LinkedIn |
| 3 | 디자인 파트너 제안: 언더라이팅 AI 1개 유스케이스 어슈어런스 유료 파일럿 (미드마켓 뮤추얼 = 디자인 파트너 최적층) | 복수 시그널 스택 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
