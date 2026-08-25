# 계정 리서치: Nationwide Building Society

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/uk-s1-nationwide.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Nationwide Building Society (UK-S1) / Tier 1 |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-18 (유효기간: 2026-09-17까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: Virgin Money·Clydesdale 은행업 전체가 2026-04-02 Part VII로 Nationwide에 이전 완료되어, 두 기관의 모델 인벤토리(IRB 포함)를 SS1/23 원칙 4(독립검증) 하에서 하나의 그룹 체계로 흡수·재검증해야 하는 시점이기 때문이다.
- 보류 해제 권고 근거: 실측 시그널 3건(§2), 그룹 모델링 조직 실재(§3). **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.
- **선행 조건(ICP 배너)**: SOC 2 등 인증 상태 확인 전 Tier 1 보류 해제 금지. 인증 확인은 PO 결정 대기 항목이다.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 조직 통합 (은행업 이전 완료) | Virgin Money·Clydesdale 은행업이 FSMA 2000 Part VII 절차로 Nationwide에 이전 완료(고등법원 승인 2026-02-23). 고객 모기지·계좌·카드·데이터·은행 계약 전체가 Nationwide 책임으로 이전 | 2026-04-02 | https://uk.virginmoney.com/nationwide-transfer/ , https://www.nationwide.co.uk/news-and-stories/bringing-nationwide-and-virgin-money-together |
| 규제기관 AI 논의 참여 | BoE·FCA AI Consortium 2026-02-09 회의에 Nationwide 멤버(Matthew Jones) 참여. 컨소시엄에서 생성형·에이전틱 AI 확산 시 기존 MRM·검증 접근의 확장 가능성 우려, SS1/23의 AI 시스템 적용이 논의됨 | 2026-02-09 | https://www.bankofengland.co.uk/minutes/2026/february/ai-consortium-minutes-9-february-2026 |
| AI 기술 도입 (강도 하향, 맥락) | Moneyhub를 AI 기반 거래 데이터 인리치먼트·분류 파트너로 선정, 1,600만 고객 대상 | 2026-01-13 | https://moneyhub.com/press-releases/nationwide-building-society-selects-moneyhub-as-its-data-enrichment-and-categorisation-partner/ , https://www.fstech.co.uk/fst/Nationwide_Announces_AI_Platform_For_Granular_Customer_Spending_Insights.php |

- 유효기간 판정(KB03 §5.2): 이전 완료(2026-04-02)는 통합 작업이 진행형이므로 유효. AI Consortium 참여(2026-02-09)는 AI 거버넌스 관여 시그널로 6~12개월 창 내 유효. Moneyhub(2026-01-13)는 도입 발표 1~6개월 창을 넘겨 강도 하향, 맥락으로만 사용.
- 정직 표기: CRO Gavin Smyth는 2020년 11월부터 재임으로 "신임 임원" 시그널이 아니다. 신임 CRO 시그널은 이 계정에 없다.

## 3. 가설

Virgin Money 은행업 흡수로 Nationwide는 자산 £370bn급 그룹이 되었고, 서로 다른 두 모델 estate(신용·자본·IRB·ML)를 단일 거버넌스로 통합해야 한다. SS1/23 원칙 1(모델 식별)·원칙 4(독립검증)가 그대로 적용되는 상황에서 검증 백로그가 구조적으로 늘었을 것이라는 가설이다. 동시에 Moneyhub AI 도입·AI Consortium 참여가 보여주듯 AI/ML 신규 유입도 진행 중이므로, 전통 모델 통합 검증(PRD-VAL)과 AI 거버넌스 계층(PRD-AIG) 양쪽 수요 가설이 성립한다. 단정하지 않는다: 통합 검증을 내부 증원 또는 컨설팅 외주로 해결 중일 수 있다([검증 필요]).

주의(ICP §6.2 S1 근접): Nationwide는 IBM Consulting과 AI Centre of Expertise, AI Council을 이미 구축했다(https://www.ibm.com/case-studies/nationwide-building-society). 대형 기관 성향으로 자체 구축 저항이 있을 수 있어 "AI 거버넌스 플랫폼" 정면 포지션보다 "독립검증 상시화 보완" 앵글이 안전하다. 그룹 모델링 조직(Group Director of Modelling 직책이 Nationwide·Virgin Money를 겸괄)이 실재해 조직 준비도는 높다.

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(실명 특정·이메일 검증은 PO 도구, list-build-spec §1.2). 직함 수준의 타깃만 제시한다.

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Group Director of Modelling 또는 Head of Model Risk / Model Validation | UK | 미수집 (PO 도구) | 그룹 모델 estate 통합·SS1/23 원칙 4 실무 소유자. 챔피언 후보 |
| (PO 특정) | Chief Risk Officer | UK | 미수집 (PO 도구) | EB. 통합 리스크 체계 책임 |
| (PO 특정) | Head of AI Governance / Responsible AI (AI Council 산하) | UK | 미수집 (PO 도구) | PRD-AIG 챔피언 후보 |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일·LIA 문서 ID·보관기간 만료일은 PO(도구)·sales-compliance-officer 공급 후 충족된다. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 UK 확정, 법인 가입자 = building society)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개만 쓴다: Virgin Money 은행업 이전 완료(2026-04-02)에 따른 모델 estate 통합.
- 영문 초안: `With Virgin Money's banking business formally transferred on 2 April, your validation team now owns two model estates under one SS1/23 framework, and I suspect Principle 4 workload is the bottleneck.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: PRA 규제 빌딩소사이어티(건전성 규제 대상), 모델·AI 도입 실재, 관할 UK, 법인 가입자
- [x] H5 해당 없음: 경쟁사(Credo AI, Holistic AI, Monitaur, ValidMind, Fairly AI, SAS MRM, Yields.io, Evalueserve) 아님
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료. 단 S1(대형 기관 성향) 근접을 §3에 명기
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 통합 검증 상시화: 두 모델 estate를 흡수하는 시기의 독립검증(3선 보조) 백로그를 결정론 재계산 + 인간 승인 구조로 상시화 (PRD-VAL) | 은행업 이전 완료 2026-04-02 | 이메일 |
| 2 | 생성형 AI 거버넌스 공백: AI Council이 만든 정책을 실행 가능한 가드레일(조회 전용·제안 전용·승인 우선·Kill Switch)로 코드화 (PRD-AIG) | AI Consortium 참여 2026-02-09, Moneyhub 도입 | 이메일 / LinkedIn |
| 3 | 디자인 파트너 제안: 신규 AI 유스케이스 1개를 대상으로 어슈어런스 계층 유료 파일럿 (로고·사례 교환) | 복수 시그널 스택 | 이메일 후 소개 경로 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
