# 계정 리서치: Bendigo and Adelaide Bank

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/au-b1-bendigo.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].
> 규제 프레임 주의(5차 국가 확장): 호주는 APRA 프레임(AI 서한 2026-04-30, CPS 230)·ASIC 프레임이다. 카피에 US/UK 규제를 쓰지 않는다.

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Bendigo and Adelaide Bank (AU-B1) / Tier 1 |
| 캠페인ID | 20260818-usuk-rynta-aigov (SG/AU 확장분. 캠페인 분리 여부는 PO 결정) |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 강. 단 감독 조치 직후 국면 주의: 접근 타이밍·톤은 PO 판단. AU 컴플라이언스 프레임 확정 전에는 상신 자체가 조건부).**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 어제(2026-08-18) APRA가 비재무 리스크 관리 실패로 라이선스 조건을 부과했고, 은행은 3년·A$70m 정비 계획과 "독립 검토자(independent reviewer)" 선임을 이행해야 하는데, 이는 ICP 시그널 우선순위 6(감독당국 지적, 가장 강한 강제 트리거)의 정면 사례이기 때문이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 감독당국 지적 (최강 트리거) | APRA가 비재무 리스크 관리 관련 라이선스 조건 부과: 정비(rectification) 계획 수립, **독립 검토자 선임**, 이행 의무. 약 3년·초기 추정 A$70m. 발단: 2025-11 자체 AML/CTF 검토 → 2025-12 APRA 요구 비재무 리스크 루트코즈 분석 | 2026-08-18 | https://kalkine.com.au/news/announcements/bendigo-and-adelaide-bank-faces-apra-licence-conditions-discloses-70-million-rectification-plan-and-unaudited-fy26-results |
| ASX 공시 (1차 소스) | "Regulatory matters and unaudited FY26 results": FY26 현금이익 A$530.2m, 법정순이익 A$375.1m(미감사), CET1 11.34%. 확정 실적 2026-08-24 발표 예정 | 2026-08-18 | https://wcsecure.weblink.com.au/pdf/BEN/03122115.pdf |
| AML 제재 비용 (맥락) | AUSTRAC 관련 약 A$90m 비용 반영 보도 | 2026-08-18 (보도) | https://stocksdownunder.com/bendigo-bank-austrac-risk/ |
| 기술·AI 투자 | Infosys(7년, 소프트웨어 엔지니어링·AI 인력)·Genpact(6년, 프로세스·리스크 관리) 파트너십 발표 | 2026-04 | https://ia.acs.org.au/article/2026/tech-workers-face-new-layoffs-at-bendigo-bank.html |
| AI 도입 (technographic) | Google Cloud 파트너십 심화: 금융범죄 탐지용 커스텀 AI 모델, 생성형 AI 데이터 조회, BigQuery·Security Operations 이전 | 게재일 미확인 (2025~2026 추정) | https://www.itnews.com.au/news/bendigo-bank-taps-google-cloud-for-first-major-ai-project-622004 |

- 유효기간 판정(KB03 §5.2): 감독 조치(2026-08-18)는 발생 1일, 최신. ICP §4는 감독 지적의 유효기간을 발생 후 6~18개월로 본다. Infosys/Genpact(2026-04)는 4개월 경과, 보조.
- 정직 표기: 신임 CRO·모델검증 채용은 이번 조사에서 발견하지 못했다 [검증 필요]. Google Cloud 발표 일자 미확정. 라이선스 조건의 구체 문언(모델리스크 포함 여부)은 1차 공시 원문 확인 필요 [검증 필요].

## 3. 가설

라이선스 조건·독립 검토자·3년 정비 프로그램이 걸린 은행은 (a) 비재무 리스크(운영·컴플라이언스·모델) 통제의 증거화 수요가 즉시 생기고, (b) 동시에 금융범죄 AI 등 커스텀 AI 모델을 늘리고 있어 "AI를 늘리면서 통제 실패를 정비해야 하는" 이중 압력에 있다는 가설. APRA AI 서한(2026-04-30)이 지적한 "표본·시점 기반 어슈어런스의 한계"가 이 은행의 정비 프로그램 설계에 직결된다는 가설. 단정하지 않는다: 정비 프로그램의 범위에 모델·AI 통제가 포함되는지는 미확인이다. 주의: 감독 조치 직후는 대형 컨설팅펌이 선점하는 국면이기도 하며, 무명 벤더 접근의 수용성은 낮을 수 있다(KB08 §10.1). 접근하더라도 정비 본체가 아니라 "AI·모델 어슈어런스의 좁은 층"으로 들어가야 한다.

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer | AU | 미수집 (PO 도구) | EB. 정비 계획·라이선스 조건 이행 소유 |
| (PO 특정) | Head of Model Risk / Model Validation (실재 여부 [검증 필요]) | AU | 미수집 (PO 도구) | 검증 실무 챔피언 후보 |
| (PO 특정) | Chief Information Officer / Head of AI·Data | AU | 미수집 (PO 도구) | Google Cloud AI·Infosys 프로그램 접점 |

- [ ] [G9] 인물 레코드 0건 상태. AU 수신 근거(Spam Act 2003 동의 요건: 명시적/추정적)는 sales-compliance-officer의 AU 프레임 확정 후 충족해야 발송 큐 진입 가능.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 AU 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 2026-08-18 APRA 라이선스 조건 + 3년·A$70m 정비 + 독립 검토자 요건.
- 영문 초안: `APRA's new licence conditions hand Bendigo a three-year rectification program with an independent reviewer, at the same time the bank is scaling custom AI models for financial crime, two workstreams that meet exactly at auditable model assurance.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: APRA 인가 ADI(~A$100bn급), AI 도입 실재, 상장사, 관할 AU
- [x] H5 해당 없음: 경쟁사 아님
- [x] S1·S2 검토: 자체 AI 플랫폼팀 대형 아님(외부 파트너 의존: Google·Infosys·Genpact). Sweet spot 부합
- [x] S3 주의: 정비 국면의 비용 압박으로 무료 PoC 요구 가능성. 유료 원칙 조기 확인 필요
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 정비 프로그램의 증거화 계층: 통제·검증 활동을 감사 원장으로 상시 기록 (PRD-VAL) | APRA 라이선스 조건 2026-08-18 | 이메일 |
| 2 | "AI를 늘리며 정비한다": 금융범죄 AI 등 신규 모델의 수명주기 통제·가드레일 (PRD-AIG) | Google Cloud AI + 정비 병행 | 이메일 / LinkedIn |
| 3 | APRA AI 서한(2026-04-30) 대응: 시점·표본 어슈어런스에서 상시 어슈어런스로 | APRA 서한 + 독립 검토자 요건 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
