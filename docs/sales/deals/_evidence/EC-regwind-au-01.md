# 증거 카드: EC-regwind-au-01

> 저장 경로: `docs/sales/deals/_evidence/EC-regwind-au-01.md` (계정 무관 공용 라이브러리)
> 카피·제안서·설문 답변의 모든 사실 주장은 이 카드의 등급 규칙을 따른다. [확인] 등급만 사실로 진술할 수 있다 [G3].
> **주의 1: 규제 해석이 걸린 카드다. 대외 사용 전 sales-compliance-officer 경유 legal-team 확인 필수 [G3].**
> **주의 2 (원문 대조 상태): APRA 서한의 1차 출처 URL은 특정·존재 확인됐으나, 원문 전문의 직접 열람은 네트워크 프록시 차단으로 이번 검증에서 실패했다. 따라서 이 카드의 모든 영문 문구는 APRA 직접 인용(따옴표)이 아닌 요약 서술이다. outreach-qa가 원문 전문을 대조하기 전까지 APRA 발언의 따옴표 인용을 금지한다.**

| 항목 | 내용 |
|---|---|
| 카드 ID | EC-regwind-au-01 |
| 작성 에이전트 | deal-strategist |
| 검토 | outreach-qa (원출처 대조) 대기 (**필수: apra.gov.au 원문 전문 대조. 특히 어슈어런스 문장의 verbatim 확인**) + **legal-team (규제 해석) 대기** |
| 승인 | sales-compliance-officer 경유 legal-team 확인 후 사용 |
| 기준일 | 2026-08-19 (재검증 주기: 분기. APRA 후속 지침·기준서 발표 시 즉시) |

## 1. 카드 요약

- 주장 한 줄: AU 규제 순풍(Why Now): APRA가 최초의 AI 특정 산업 서한(2026-04-30)에서 거버넌스·리스크 관리·어슈어런스·운영 복원력이 AI 도입의 규모·속도·복잡성을 못 따라간다고 경고했고(표적 감독 검토 기반), 시점(point-in-time)·표본 기반 어슈어런스가 학습·적응·열화하는 확률적 모델에 부적합하다는 관찰을 담았다(2차 소스 교차 확인, 원문 verbatim 미대조). CPS 230(2025-07-01 시행)은 기존 중요 서비스 제공자 계약 전환기간이 2026-07-01 종료되어 전면 적용 국면이다.
- **신뢰 등급 (KB08 규칙): 서한의 존재·일자·상위 메시지 = [확인]** (APRA 공식 페이지 2건 URL 특정 + 독립 2차 복수 교차). **어슈어런스 세부 서술(시점·표본 부적합) = [확인] (2차 복수 교차)이되 원문 verbatim 미대조 → 요약 서술만 허용, 직접 인용 금지.**
- 사용 범위: **시장 맥락으로만.** legal-team 확인 전 대외 발송 금지. AU는 조건부 국가로 컴플라이언스 프레임(Spam Act 동의 요건) 확정 전 전건 발송 보류(G9).
- 주 사용처: `copy/master-au.md` T1·T2·T3·DM·전화의 앵커 문단, APRA + CPS 230 two-page note(T3 배포물).
- **이 쐐기(AI 거버넌스·독립검증)에서의 사용 맥락**: 서한의 "시점·표본 어슈어런스의 한계" 관찰은 PRD-VAL(상시 독립검증)의 정면 매핑이고, 거버넌스·에이전틱 워크플로 평가 역량 요구는 PRD-AIG 접점이다. APRA에는 SR 26-2/SS1/23형 모델리스크 전용 기준서가 없다: 기대는 CPS 220·CPS 230·AI 서한의 조합으로 작동한다.

## 2. 주장 (정확한 형태)

1. **APRA Letter to Industry on AI (2026-04-30)**: APRA 최초의 AI 특정 감독 기대 공표. 전 규제 산업(은행·보험·수퍼애뉴에이션) 대상 표적 감독 검토 결과에 기반해, 거버넌스·리스크 관리·어슈어런스·운영 복원력 관행이 AI 도입의 규모·속도·복잡성을 따라가지 못하고 있다고 경고했다. AI 리스크가 운영리스크·사이버·데이터 거버넌스·모델리스크·컴플라이언스·서드파티 의존 등 복수 도메인을 가로지른다고 관찰했다.
2. **어슈어런스 관련 서술 (요약, 원문 verbatim 미대조)**: 서한은 시점(point-in-time)·표본 기반 어슈어런스 방식에 대한 의존을 관찰하고, 이런 방식이 학습·적응하며 시간에 따라 열화하는 확률적 모델에 부적합하다는 취지를 담은 것으로 복수의 독립 2차 소스(Clayton Utz, MinterEllison, 기타 해설)가 일치되게 전한다. **이 문장을 APRA의 직접 발언으로 따옴표 인용하는 것은 원문 대조 전 금지.**
3. **CPS 230 Operational Risk Management (2025-07-01 시행)**: 기술·벤더 중립 운영리스크 기준. 기존(pre-existing) 중요 서비스 제공자 계약의 전환기간은 차기 갱신일 또는 2026-07-01 중 이른 시점까지였고, **2026-07-01자로 종료되어 현재 전면 적용**이다.
4. (보조) ASIC도 REP 798(2024-10-29, AI 거버넌스 갭 경고) 등으로 행위 측면을 감독한다. AU는 APRA(건전성)·ASIC(행위) 이원 프레임이다.

## 3. 원출처

| 출처 | 유형 | URL/문서 | 확인일 | 비고 |
|---|---|---|---|---|
| APRA, Letter to Industry on Artificial Intelligence (AI) | 규제기관 공식 (1차) | https://www.apra.gov.au/apra-letter-to-industry-on-artificial-intelligence-ai | 2026-08-19 (apra.gov.au 도메인 한정 웹 검색으로 존재·일자·주제 확인) | **원문 전문 직접 열람 실패 (프록시 차단). outreach-qa 원문 대조 필수** |
| APRA 뉴스 릴리스 (step-change 촉구) | 규제기관 공식 (1차) | https://www.apra.gov.au/news-and-publications/apra-calls-for-a-step-change-ai-related-risk-management-and-governance | 2026-08-19 (동일 방식 확인) | 서한 상위 메시지 교차 |
| APRA, CPS 230 Operational Risk Management | 규제기관 공식 (1차) | https://www.apra.gov.au/operational-risk-management | 2026-08-18 (캠페인 검증 URL) | 시행 2025-07-01 |
| Clayton Utz 해설 (캠페인 원 근거) | 2차 해설 | https://www.claytonutz.com/insights/2026/may/apras-ai-letter-a-shift-from-framework-to-targeted-expectations | 2026-08-19 | 서한 내용·어슈어런스 서술 교차 |
| MinterEllison 해설 (캠페인 원 근거 + 추가) | 2차 해설 | https://www.minterellison.com/articles/apra-ai-letter-third-party-suppliers · https://www.minterellison.com/articles/apra-sharpens-expectations-on-ai-governance-and-risk-management | 2026-08-19 | 서한 내용 교차 |
| CPS 230 전환기간 종료 해설 | 2차 해설 (교차) | https://www.dwyerharris.com/blog/cps-230-and-material-service-providers-what-you-need-to-do-before-1-july-2026 외 | 2026-08-19 | 기존 계약 2026-07-01 기한 교차 |
| target-accounts §9.0 (관할 공통 Why Now) | 캠페인 문서 | docs/sales/campaigns/20260818-usuk-rynta-aigov/target-accounts.md | 2026-08-19 | 5차 확정, 실측 |

## 4. 사용 가능한 문구

**전부 요약 서술이다. APRA 원문 직접 인용(따옴표) 아님. outreach-qa의 원문 verbatim 대조 전까지 이 원칙을 유지한다.**

- 영문 (풀 문장, 마스터 카피 T1과 정합, 요약 서술): `APRA's April 2026 letter was direct: governance and assurance are not keeping pace with AI adoption, and point-in-time, sample-based assurance has limits. With CPS 230 already reshaping operational risk, the question becomes what continuous assurance looks like in practice.`
- 영문 (짧은 형, 카피 삽입용): `APRA's point on assurance not keeping pace with AI adoption`
- 영문 (T2 정합, 요약 서술): `That difference is exactly what APRA's letter put on the table.`
- 국문 (내부용): `APRA 2026-04-30 서한은 거버넌스·어슈어런스가 AI 도입 속도를 못 따라가고, 시점·표본 기반 어슈어런스에 한계가 있다는 관찰을 담았다(요약). CPS 230은 2026-07-01부로 기존 계약 전환기간이 끝나 전면 적용 국면이다.`
- 표현 수위 주석: 마스터 카피 T1의 `unusually direct`는 발신자 평가(opinion)로 허용 범위이나, 원문 대조 후 어조가 다르면 `direct`로 완화한다(위 풀 문장은 완화형 기준).

## 5. 사용 금지 표현

- "규제가 우리 제품(RYNTA)을 요구한다", "APRA가 상시 어슈어런스 솔루션 도입을 의무화했다", "RYNTA를 쓰면 APRA 기대/CPS 230을 준수하게 된다" 류 단정 (서한은 감독 기대·관찰이지 제품 요구가 아니다)
- **APRA 원문 verbatim 확인 전, 서한 문장의 따옴표 직접 인용** (예: APRA said "..." 형식 금지. 요약 서술만)
- "호주판 SR 26-2" 류 표현 (APRA에는 모델리스크 전용 기준서가 없다. target-accounts §9.0)
- 이 세그먼트 카피에 SR 26-2·SS1/23 인용
- CPS 230을 AI 전용 규제로 서술 (기술·벤더 중립 기준이다. "AI가 중요 운영을 뒷받침할 때 포착되는" 수준으로만)
- 서한을 근거로 수신자 기관이 지적·위반 상태라는 단정·암시 (특히 AU-B1 Bendigo처럼 감독 조치 직후 계정에 공포 마케팅 금지, 타이밍은 PO 판단)
- legal-team 확인 전 대외 발송물에 인용

## 6. 사용 이력과 유효성

| 사용처 (문서/캠페인) | 일자 | outreach-qa 대조 |
|---|---|---|
| copy/master-au.md (T1·T2·T3·DM·전화 앵커, two-page note) | 미발송 | 대기 (**원문 verbatim 대조 + AU 컴플라이언스 프레임 확정 + legal-team 확인 선행**) |

- outreach-qa가 APRA 원문 전문 대조에 성공하면: (a) 어슈어런스 서술의 verbatim을 §2-2에 추가하고 직접 인용 허용 여부를 갱신, (b) 요약 서술 제한 문구를 완화 개정한다. 실패가 지속되면 요약 서술 원칙을 유지한다.
- APRA 후속 지침·기준서(모델리스크·AI 특정) 발표 시 즉시 재검증한다.
