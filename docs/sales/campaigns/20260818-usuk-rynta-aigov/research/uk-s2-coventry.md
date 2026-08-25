# 계정 리서치: Coventry Building Society

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/uk-s2-coventry.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Coventry Building Society (UK-S2) / Tier 1 |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-18 (유효기간: 2026-09-17까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 조건부)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 그룹 모델리스크·검증 기능(Group Head of Model Risk Management and Validation 산하)이 시니어급 검증 인력을 공개 채용하며 확대 중이고, 동시에 Co-operative Bank 통합(2027 완료 전망)으로 검증해야 할 모델 estate가 두 배가 되는 시점이기 때문이다.
- 해제 상신 조건: 채용공고(§2)의 현재 게시 상태를 자사 채용 페이지(coventrycareers.co.uk)에서 재확인할 것. 공고 종료(채용 완료) 확인 시 시그널 강도를 낮추고 재평가한다. **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.
- **선행 조건(ICP 배너)**: SOC 2 등 인증 상태 확인 전 Tier 1 보류 해제 금지.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 채용 (모델검증 시니어) | Senior Manager - Model Risk Management and Validation 채용공고. Financial and Model Risk(FaM) 기능 소속, **Group Head of Model Risk Management and Validation 직속 보고**. Coventry/Manchester/Warrington 하이브리드. MRM 프레임워크 구축·내재화 경험 요구 | 2026-01-16 게시, 2026-08 기준 구인 애그리게이터에 게시 확인(자사 페이지 재확인 필요) | https://www.ziprecruiter.co.uk/jobs/488994214-senior-manager-model-risk-management-and-validation-at-coventry-building-society |
| 채용 (모델 개발) | Lead Credit Risk Model Developer - 16개월 FTC 공고 게시 | 2026-08 기준 게시 확인 | https://restless.co.uk/job/coventry-building-society-lead-credit-risk-model-developer-16-month-ftc-coventry-8692/ |
| 조직 통합 (진행형, 맥락) | Co-operative Bank 인수(2025) 후 통합 진행. Fitch는 통합 완료를 2027년으로 전망하며 통합 실행 리스크를 등급 감시 요인으로 명시 | 2026 (Fitch 평가) | https://tradersunion.com/news/financial-news/show/2665737-fitch-affirms-coventry-cooperative-bank-rating/ |

- 유효기간 판정(KB03 §5.2): 채용공고 유효기간은 "게시~채용 완료"다. 1월 게시 공고가 8월에도 애그리게이터에 노출되나 자사 페이지 직접 확인은 미완이므로 조건부로 판정한다. Co-op Bank 통합은 2027년까지 진행형 맥락.
- 정직 표기: 신임 CRO·Responsible AI 채용·생성형 AI 발표 시그널은 이번 조사에서 발견하지 못했다.

## 3. 가설

"Group Head of Model Risk Management and Validation"이라는 직책과 그 직속 시니어 채용은 (a) 독립 MRM·검증 기능이 명시적으로 실재하고(조직 준비도 상), (b) 그 기능이 지금 확장 중임을 시사한다. Co-op Bank의 모델 estate(신용·자본 모델)를 그룹 프레임워크로 흡수해야 하는 SS1/23 부담이 채용 확대의 배경일 것이라는 가설이다. 사람을 뽑는 중이라는 것은 검증 케파가 병목이라는 뜻이므로, 채용으로 다 못 메우는 상시 검증 워크로드를 어슈어런스 계층(PRD-VAL)으로 보완하는 제안이 접점이다. 단정하지 않는다: 채용이 이미 완료되어 케파 문제가 해소됐을 수 있다([검증 필요]).

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Group Head of Model Risk Management and Validation | UK | 미수집 (PO 도구) | 채용공고에 실재가 확인된 보고라인. 챔피언 1순위 |
| (PO 특정) | Chief Risk Officer | UK | 미수집 (PO 도구) | EB. Co-op Bank 통합 리스크 총괄 |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일·LIA·보관기간 만료일은 PO(도구)·sales-compliance-officer 공급 후 충족. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 UK 확정, 법인 가입자 = building society)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: MRM&V 시니어 채용(그룹 검증 기능 확장).
- 영문 초안: `Saw Coventry is hiring a Senior Manager for Model Risk Management and Validation while absorbing the Co-operative Bank's model estate, and hiring alone rarely clears that kind of validation backlog.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: PRA 규제 빌딩소사이어티, 모델 estate·MRM 기능 실재, 관할 UK, 법인 가입자
- [x] H5 해당 없음: 경쟁사 아님
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 검증 케파 보완: 채용으로 확장 중인 검증 기능에 상시·재현 가능한 독립검증 계층을 더해 통합기 백로그 해소 (PRD-VAL) | MRM&V 시니어 채용공고 | 이메일 |
| 2 | 통합 모델 인벤토리 어슈어런스: Co-op Bank 모델 흡수 시 SS1/23 원칙 1(식별·분류)·원칙 4(독립검증)의 감사 가능 원장 구축 (PRD-VAL + PRD-AIG) | Co-op Bank 통합 2027 전망 | 이메일 / LinkedIn |
| 3 | 디자인 파트너 제안: 통합 대상 모델군 1개로 좁힌 유료 파일럿 | 복수 시그널 | 이메일 후 소개 경로 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
