# 계정 리서치: Judo Bank (Judo Capital Holdings)

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/au-b3-judo.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].
> 규제 프레임 주의(5차 국가 확장): 호주는 APRA 프레임(AI 서한 2026-04-30, CPS 230)·ASIC 프레임이다.

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Judo Bank (AU-B3) / Tier 2 |
| 캠페인ID | 20260818-usuk-rynta-aigov (SG/AU 확장분. 캠페인 분리 여부는 PO 결정) |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 중. AI 특정 시그널의 일자 미확정을 명기한 조건부 권고. AU 컴플라이언스 프레임 확정 전에는 상신 자체가 조건부).**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 어제(2026-08-18) FY26 결과에서 대출 A$14.7bn(+18%)·CIR 45.3%(전년 52.4%)·FY27 PBT A$210~220m 가이던스를 내놓은 SME 챌린저가, 클라우드 네이티브 코어 전환을 마친 직후 AWS와 AI 통합(콜 요약·크레딧 메모 자동화)을 다음 단계로 공언한 상태라 신용 판단 보조 AI의 통제 설계가 지금 백지 위에 있기 때문이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 실적 (신선) | FY26: 법정순이익 A$111.1m(+29%), PBT A$168.1m(+34%), 총대출 A$14.7bn(+18%), CIR 45.3%(FY25 52.4%). FY27 가이던스 PBT A$210~220m·ROE ~8% | 2026-08-18 | https://kalkinemedia.com/au/news/announcements/judo-bank-announces-fy26-results-with-18-growth-in-gross-loan-assets-and-1681-million-profit-before-tax |
| 코어 전환 완료 (technographic) | Thought Machine Vault Core 이전: 2024-07 기존 대출 고객 컷오버, 2025-04 대출·예금 전체 이전 완료, 레거시 폐기 | 2025-04 (완료. 경과, 맥락) | https://www.thoughtmachine.net/press-releases/judo-bank |
| AI 도입 계획 (technographic) | AWS와 AI 통합 검토: 콜 요약 자동화 POC, 뱅커 음성 노트의 크레딧 메모 변환. Sympera AI로 파이프라인 전환율·수익 가능성 평가 | 게재일 미확인 (2025~2026) | https://aws.amazon.com/partners/success/judo-bank-thought-machine/ |
| 관할 공통 (규제) | APRA AI 서한: AI 특정 감독 기대 첫 공표, 어슈어런스가 AI 속도를 못 따라간다 경고 | 2026-04-30 | https://www.claytonutz.com/insights/2026/may/apras-ai-letter-a-shift-from-framework-to-targeted-expectations |

- 유효기간 판정(KB03 §5.2): FY26 결과(2026-08-18)는 발생 1일, 최신. 코어 전환(2025-04)은 경과로 맥락 전용. AI 도입 계획은 게재일 미확인이라 강도를 낮춰 평가한다.
- 정직 표기: FY26 발표문 자체에서 AI 언급은 이번 조사에서 확인하지 못했다. AI 거버넌스·모델검증 채용, 신임 리스크 임원, IRB 지위도 미확인 [검증 필요]. AI 특정 시그널은 일자 미상 케이스스터디 수준임을 명기한다.

## 3. 가설

관계형 SME 대출은행이 크레딧 메모 작성·파이프라인 평가에 AI를 넣기 시작하면 "AI가 신용 판단의 입력을 만드는" 구조가 되어, 제안 전용·인간 승인·감사 추적의 통제 설계가 초기에 필요하다는 가설. 코어 전환을 막 끝낸 조직은 다음 기술 투자(AI)의 통제 계층을 함께 설계할 적기이며, 직원 규모상 자체 AI 거버넌스 플랫폼팀은 없어 디자인 파트너 적합층이라는 가설. 단정하지 않는다: AI 도입의 실제 진척(POC인지 프로덕션인지)은 미확인이다 [검증 필요].

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer | AU | 미수집 (PO 도구) | EB. 신용 판단 보조 AI의 리스크 소유 |
| (PO 특정) | Head of Credit Risk / Model Risk (실재 여부 [검증 필요]) | AU | 미수집 (PO 도구) | 신용모델·검증 실무 챔피언 후보 |
| (PO 특정) | Chief Technology Officer / Head of Data & AI | AU | 미수집 (PO 도구) | AWS AI 통합 실행 소유자 |

- [ ] [G9] 인물 레코드 0건 상태. AU 수신 근거(Spam Act 2003)는 sales-compliance-officer 프레임 확정 후 충족.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 AU 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 2026-08-18 FY26 결과(성장 지속) + 코어 전환 완료 후 AI 통합이 다음 단계라는 공언의 결합.
- 영문 초안: `Fresh off yesterday's FY26 results and a completed cloud-core migration, Judo has said AI-drafted credit memos are next, the exact point where suggest-only guardrails and human approval need to be designed in rather than retrofitted.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: APRA 인가 ADI(SME 전문, ASX 상장), 관할 AU
- [x] H5 해당 없음: 경쟁사 아님
- [x] S1·S2 검토: 자체 AI 플랫폼팀 없음(AWS·서드파티 의존). Sweet spot 부합
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 크레딧 메모 AI의 가드레일 선설계: 제안 전용·승인 우선·감사 원장 (PRD-AIG) | AWS AI 통합 계획 | 이메일 |
| 2 | 성장하는 신용 포트폴리오의 독립검증 상시화: 검증 캐파를 구조로 (PRD-VAL) | FY26 대출 +18% (2026-08-18) | 이메일 / LinkedIn |
| 3 | APRA AI 서한 국면의 챌린저 디자인 파트너: 작게 시작해 선례를 만드는 파일럿 | APRA 2026-04-30 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
