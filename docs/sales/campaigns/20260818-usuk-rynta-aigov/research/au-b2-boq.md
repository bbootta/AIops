# 계정 리서치: Bank of Queensland (BOQ Group)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/au-b2-boq.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].
> 규제 프레임 주의(5차 국가 확장): 호주는 APRA 프레임(AI 서한 2026-04-30, CPS 230)·ASIC 프레임이다.

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Bank of Queensland (AU-B2) / Tier 1 |
| 캠페인ID | 20260818-usuk-rynta-aigov (SG/AU 확장분. 캠페인 분리 여부는 PO 결정) |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 중). AU 컴플라이언스 프레임 확정 전에는 상신 자체가 조건부다.**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 2026-06-24 공개된 대로 BOQ·Virgin Money AU·ME 3개 브랜드의 주택대출을 단일 실시간 대출 엔진으로 통합해 승인이 몇 시간대로 내려가고 무조건부 승인 최대 60%가 3일 내 처리되는 구조에서, "AI 주도 검증(AI-led verification)"을 다음 과제로 공식화했기 때문에 자동화된 대출 의사결정의 통제·검증 계층이 지금 설계 대상이기 때문이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 대출 자동화 전환 | 3개 브랜드 주택대출을 단일 실시간 대출 엔진으로 재구축: 승인 수주→수시간, 원가 1/3 절감, 디지털 뱅크 경유 플로우 75%, 3일 내 무조건부 승인 최대 60%. AI-led verification을 향후 핵심 과제로 명시 | 2026-06-24 | https://www.mi-3.com.au/24-06-2026/bank-queensland-says-it-has-rebuilt-home-lending-across-boq-virgin-money-and-me-b-brands |
| 코어 전환 (technographic) | ME Bank 레거시 코어 고객의 80~85%를 Temenos 기반 신규 코어로 이전, 레거시 폐기(decommissioning) 단계 진입 | 2026 (게재일 미확인, 최근) | https://www.itnews.com.au/news/boq-looks-to-legacy-decommissioning-as-core-consolidation-gains-pace-625293 |
| AI 도입 (보조) | Microsoft 365 Copilot 전사 채택(AI 진입 기반), Capgemini와 디지털 전환·AI 역량 파트너십 보도 | 게재일 미확인 | https://www.microsoft.com/en/customers/story/20729-bank-of-queensland-azure |
| 관할 공통 (규제) | APRA AI 서한: 거버넌스·어슈어런스가 AI 도입 속도를 못 따라간다 경고, 시점·표본 기반 어슈어런스의 한계 지적 | 2026-04-30 | https://www.claytonutz.com/insights/2026/may/apras-ai-letter-a-shift-from-framework-to-targeted-expectations |

- 유효기간 판정(KB03 §5.2): 대출 엔진 통합 공개(2026-06-24)는 약 8주로 유효창 내. Copilot·Capgemini는 게재일 미확인이라 보조로만 쓴다.
- 정직 표기: 신임 리스크 임원·모델검증 채용·감독 지적은 발견하지 못했다 [검증 필요]. "AI-led verification"의 구체 설계(모델 종류·자동화 수준)는 미확인.

## 3. 가설

주택대출 의사결정을 시간 단위 자동 승인으로 옮긴 은행은 신용·검증·사기 모델의 오류가 곧바로 대량·고속으로 증폭되는 구조가 되고, APRA AI 서한이 요구하는 "AI 속도에 맞는 어슈어런스"와 CPS 230(중요 운영을 뒷받침하는 기술의 운영리스크)이 이 지점에 정확히 걸린다는 가설. 자체 AI 플랫폼 조직 대신 외부 파트너(Temenos·Microsoft·Capgemini) 조합으로 가는 미드티어라 sweet spot 부합 가설. 단정하지 않는다: BOQ의 모델검증 기능 규모·내부 통제 현황은 미확인이다 [검증 필요].

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer | AU | 미수집 (PO 도구) | EB. 자동 승인 확대의 리스크 소유 |
| (PO 특정) | Head of Model Risk / Credit Risk Analytics | AU | 미수집 (PO 도구) | 대출 모델 검증 실무. 챔피언 후보 |
| (PO 특정) | Chief Information Officer / 대출 플랫폼 총괄 | AU | 미수집 (PO 도구) | AI-led verification 설계 소유자 |

- [ ] [G9] 인물 레코드 0건 상태. AU 수신 근거(Spam Act 2003)는 sales-compliance-officer 프레임 확정 후 충족.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 AU 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 2026-06-24 "3개 브랜드 주택대출 단일 실시간 엔진 + AI-led verification 다음 과제" 공개.
- 영문 초안: `BOQ now approves up to 60% of home loans unconditionally within three days on one real-time engine and says AI-led verification is next, which is precisely the decision surface APRA's April letter wants assured at machine speed.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: APRA 인가 ADI(~A$100bn급, ME·Virgin Money AU 브랜드 보유), 상장사, 관할 AU
- [x] H5 해당 없음: 경쟁사 아님
- [x] S1·S2 검토: 자체 대형 AI 플랫폼팀 증거 없음(외부 파트너 중심). Sweet spot 부합
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 시간 단위 자동 승인의 어슈어런스: 대출 의사결정 모델의 상시 독립검증·재현성 (PRD-VAL) | 대출 엔진 통합 2026-06-24 | 이메일 |
| 2 | AI-led verification 설계 단계에 가드레일 내장: 제안 전용·승인 우선·감사 원장 (PRD-AIG) | AI-led verification 공식화 | 이메일 / LinkedIn |
| 3 | APRA AI 서한 + CPS 230 국면의 디자인 파트너: 미드티어 은행 AI 어슈어런스 선례 | APRA 2026-04-30 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
