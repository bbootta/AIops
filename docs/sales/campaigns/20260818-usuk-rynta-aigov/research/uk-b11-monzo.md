# 계정 리서치: Monzo Bank

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/uk-b11-monzo.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Monzo Bank (UK-B11) / Tier 2 |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 중간 강도)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: Monzo는 FCA AI Live Testing 1기(2025-12 개시) 참여 은행이고 FCA가 참여사 AI 활용의 good/poor practice를 담은 보고서 발간을 예고한 상태라, 자사 AI 통제가 감독자의 공개 기준 사례가 되기 전 통제·검증 체계를 정비할 유인이 지금 걸려 있기 때문이다.
- 강도 판단의 정직 표기: 1기 참여 개시(2025-12)는 8개월 경과이나 FCA 보고서 발간이 예정된 진행형 이벤트다. 보고서 발간 시점의 정확한 일자는 미확정 [확정 필요].
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 규제 AI 프로그램 참여 | FCA AI Live Testing 1기 참여(NatWest, Santander, Scottish Widows 등과 함께 약 6개월 테스트). FCA는 AI 활용 good/poor practice 보고서를 2026년 중 발간 예고, 2기 평가 보고서는 2027 Q1 | 2025-12 (1기 개시) | https://www.fca.org.uk/news/press-releases/fca-helps-firms-test-ai-safely , https://www.fstech.co.uk/fst/NatWest_Monzo_And_Santander_Amongst_First_To_Join_FCA_AI_Live_Testing_Scheme.php |
| 연차 실적 (규모·성장) | FY2026(2026-03-31 종료) 연차보고서: 매출 £1.7bn(+39%), 조정 세전이익 £172.6m(+20%), 고객 15.2m(+3.0m), 예금 £25.7bn(+55%) | 2026-05-19 (공개) | https://monzo.com/annual-report |
| 감독 이력 (맥락) | FCA £21.1m 벌금: 금융범죄 시스템·통제 결함(과거 기간 대상) | 2025-07 | https://www.fca.org.uk/publication/final-notices/monzo-bank-limited.pdf |

- 유효기간 판정(KB03 §5.2): AI Live Testing은 발간 예정 보고서 기준 진행형. 연차보고서(2026-05-19)는 3개월 경과로 참고 유효. 벌금(2025-07)은 맥락 전용.
- 정직 표기: AI 거버넌스·모델리스크 채용공고, 신임 리스크 임원은 이번 조사에서 발견하지 못했다. Monzo가 Live Testing에서 테스트한 AI 유스케이스의 구체 내용은 공개 자료에서 미확인 [검증 필요].

## 3. 가설

감독자의 AI 실증 프로그램에 1기로 들어간 은행은 AI 활용을 확대할 의지가 분명하고, 동시에 그 활용이 감독자 문서에 사례로 남는다는 압력을 받는다는 가설. 15.2m 고객 규모의 급성장 + 2025년 금융범죄 통제 벌금 이력은 "성장 속도를 통제가 따라가야 한다"는 서사를 강화한다. ML 밀도 높은 디지털 은행이나 사내 AI 거버넌스 플랫폼을 자체 구축·판매하지 않아 진입 여지가 있다. 단정하지 않는다: 내부 모델검증 조직의 실재·성숙도는 미확인이다 [검증 필요].

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer | UK | 미수집 (PO 도구) | EB. AI 실증·감독 대응 책임 |
| (PO 특정) | Head of Model Risk / Machine Learning 리더십 | UK | 미수집 (PO 도구) | AI Live Testing 실무 접점. 챔피언 후보 |
| (PO 특정) | Compliance / 금융범죄 통제 라인 임원 | UK | 미수집 (PO 도구) | 벌금 후 통제 상향의 관문(Blocker) 겸 우군 후보 |

- [ ] [G9] 인물 레코드 0건 상태. UK 레코드는 LIA 문서 ID·보관기간 만료일 필드를 sales-compliance-officer 공급 후 충족해야 발송 큐 진입 가능.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 UK 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: FCA AI Live Testing 1기 참여 + 참여사 AI 활용 good/poor practice 보고서 발간 예고.
- 영문 초안: `Monzo went through the FCA's first AI live-testing cohort, and the regulator's good-and-poor-practice report due later this year will put every participant's AI controls on the record.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: PRA/FCA 인가 은행(limited company), AI 도입 실재, 관할 UK
- [x] H5 해당 없음: 경쟁사 아님
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 감독자 보고서 대비 어슈어런스: Live Testing 유스케이스의 감사 가능한 통제·검증 산출물 (PRD-AIG + PRD-VAL) | AI Live Testing 1기 + 보고서 예고 | 이메일 |
| 2 | 급성장 은행의 검증 상시화: 15.2m 고객 규모 ML estate의 상시 독립검증 (PRD-VAL) | 연차보고서 2026-05-19 | 이메일 / LinkedIn |
| 3 | 통제 상향 서사: 벌금 이력 이후의 통제 투자 흐름에 AI 가드레일 얹기 (신중한 톤 필수) | FCA 벌금 2025-07 (맥락) | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
