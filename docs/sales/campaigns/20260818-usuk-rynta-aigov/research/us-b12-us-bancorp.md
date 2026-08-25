# 계정 리서치: U.S. Bancorp

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/us-b12-us-bancorp.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | U.S. Bancorp (US-B12) / Tier 2 (규모 ~$680bn, ICP 상한 경계·S1 근접) |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 중. 상한·S1 근접 조건부)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 2026-05 AWS 협력 확대로 수백 개 미션크리티컬 앱을 이전하며 전 사업 라인에 AI 에이전트를 배포하겠다고 발표했고("AI-native organization" CEO 발언, 2026-04 Q1 콜), SR 26-2(2026-04-17 발효)가 생성형·에이전틱 AI를 모델 지침 밖에 두고 별도 거버넌스 프레임워크를 요구한 첫 해이기 때문이다.
- **상한·S1 근접 조건부**: ~$680bn으로 ICP 규모 상한 경계이며 사내 기술 조직이 크다. PNC(US-B11) 선례처럼 검증·거버넌스 기능 단위의 좁은 접근을 전제로 상신하며, 전제 승인은 PO다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 클라우드·AI 인프라 확대 | AWS 협력 확대 발표: 수백 개 미션크리티컬 앱 이전, 결제·자산관리 플랫폼 개편, Amazon Bedrock 기반 생성형 AI, **전 사업 라인(자산관리·상업은행 포함) AI 에이전트 구축·배포** 계획 | 2026-05 (프레스룸 게시, 보도 2026-05-11 전후) | https://press.aboutamazon.com/aws/2026/5/u-s-bank-expands-collaboration-with-aws-to-accelerate-progressive-technology-transformation-and-ai-driven-customer-experience-innovation |
| 경영진 AI 방향 선언 | Q1 2026 어닝콜에서 CEO가 "AI-native organization"으로의 여정을 명시. 펀드 서비스·기업 신탁 등 복잡 운영 단순화에 AI를 공세적 도구로 규정 | 2026-04 (Q1 어닝콜) | https://www.bankingdive.com/news/us-bank-shifts-critical-apps-aws-ai-push/819964/ |

- 유효기간 판정(KB03 §5.2): AWS 발표(2026-05)는 도입 시그널 유효창(1~6개월) 내, Q1 콜(2026-04)도 유효창 내. 복수 시그널 겹침.
- 정직 표기: AI 거버넌스 직책 신설 채용·신임 리스크 임원·감독 지적은 이번 조사에서 발견하지 못했다. AWS 발표의 정확한 일자는 소스 간 표기가 달라 월 단위(2026-05)로 기재한다.

## 3. 가설

"전 사업 라인에 AI 에이전트 배포"는 SR 26-2가 명시적으로 모델 지침 범위 밖에 두고 별도 거버넌스를 요구한 바로 그 영역이다. 인프라(AWS·Bedrock)와 배포 의지는 확정됐으나 에이전트 거버넌스·감사 계층의 공개 흔적은 없어, 배포 속도와 통제 체계 사이 갭이 커지는 시기라는 가설. 대형 은행이므로 전사 접근은 부적합하고, 모델리스크·독립검증 기능 단위의 좁은 어슈어런스 보완 여지를 본다. 단정하지 않는다: 사내 거버넌스 플랫폼 자체 구축 가능성(S1)이 상존한다.

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Head of Model Risk Management / Model Validation | US | 미수집 (PO 도구) | 좁은 접근의 1차 접점 (PRD-VAL) |
| (PO 특정) | Head of AI Governance / Responsible AI | US | 미수집 (PO 도구) | 에이전트 거버넌스 실무 챔피언 |
| (PO 특정) | Chief Risk Officer | US | 미수집 (PO 도구) | EB (기능 단위 접근 후 확장 시) |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일은 PO(도구) 공급 후 충족. US 수신 근거: CAN-SPAM 옵트아웃 기준. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 US 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 2026-05 AWS 확대(전 사업 라인 AI 에이전트 배포 계획).
- 영문 초안: `U.S. Bank is migrating hundreds of mission-critical apps to AWS to deploy AI agents across its lines of business, while SR 26-2 explicitly leaves agentic AI outside the model rule and tells banks to build a separate governance framework for it.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: 연방 감독 슈퍼리저널 은행, AI 도입 실측, 관할 US
- [x] H5 해당 없음: 경쟁사 아님
- [!] S1 근접: §1.4 금지 목록(메가뱅크 6사)에는 없으나 규모 상한 경계. 기능 단위 좁은 접근 전제(전제 승인은 PO)
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 에이전트 배포의 별도 거버넌스(SR 26-2 지목 공백): 가드레일·감사 원장 코드화 (PRD-AIG) | AWS 발표 2026-05 | 이메일 |
| 2 | 클라우드 전환기 모델 인벤토리·계보 재정비 + 독립검증 상시화 (PRD-VAL) | 수백 개 앱 이전 | 이메일 / LinkedIn |
| 3 | 검증 기능 단위 디자인 파트너: 전사 아닌 모델검증실 좁은 진입 (PNC 선례) | AI-native 선언 2026-04 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
