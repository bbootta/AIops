# PO 결정 대기 항목 - US/UK · RYNTA AI거버넌스·독립검증 쐐기

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/po-decisions.md`
> 작성: prospect-researcher · 기준일: 2026-08-18
> 이 문서의 판정란은 비어 있다. 아래는 PO 전속 결정이며 에이전트는 초안·권고까지만 한다(G1).

## 0. 전제 (확정됨, PO 결정 대상 아님)

- **RYNTA v9.0 제품 정의는 확정이다**(AIMS_POLICY §8, risk_lib/rynta.py). 이전 패키지의 "제품 정의 확정" 항목은 이번 문서에서 삭제한다.
- **쐐기는 AI Governance(PRD-AIG) + Independent Validation(PRD-VAL)으로 PO가 확정했다.** 이 문서의 결정 항목은 그 쐐기의 실행 조건에 관한 것이다.

---

## 1. ICP 확정 (icp-draft.md)

- 권고: icp-draft §1~§8을 이 쐐기의 US/UK ICP로 확정. Firmographic sweet spot은 "MRM/독립검증 기능은 있으나 대형 사내 AI 플랫폼팀은 없는 슈퍼리저널·미드마켓·챌린저 층".
- **판정(PO):** [x] 확정 / [ ] 수정 요청  서명·날짜: PO jjlee@onelineai.com (Claude Code 세션 대화 승인) · 2026-08-18

## 2. Negative ICP 승인 (경쟁사 목록 포함, icp-draft §6)

- 권고: 탈락 기준 H1~H5, 감점 S1~S4 승인.
- **경쟁사 매핑(§6.3)을 negative ICP로 확정**: AI 거버넌스 = Credo AI, Holistic AI, Monitaur, ValidMind, Fairly AI / 모델검증 = SAS Model Risk Management, Yields.io, Evalueserve. 이들은 발송 대상이 아니라 경쟁 맥락(배틀카드)으로만 다룬다. ValidMind는 SS1/23·SR 26-2를 정면 마케팅하는 직접 경쟁자로 확인됨.
- **판정(PO):** [x] 승인 / [ ] 수정  서명·날짜: PO jjlee@onelineai.com (Claude Code 세션 대화 승인) · 2026-08-18

## 3. 대형 기관 부서 단위 접근 승인 (icp-draft §6.2 S1, target-accounts §1.4·§2.3)

- 권고: 메가뱅크(US: JPM·BofA·Citi·Wells·Goldman·Morgan Stanley 등 / UK: Barclays·HSBC UK·Lloyds·NatWest·StanChart·Santander UK 등)는 전사 타깃 금지. 특정 모델검증실·AI위원회 단위 접근은 PO 승인 시에만.
- **판정(PO):** [ ] 부서 단위 접근 허용(대상 명시) ____________________ / [ ] 전면 제외  서명·날짜: __________

## 4. SOC 2 / 인증 상태 확인 (icp-draft §6.4, KB08 §10.1·§12)

- 근거: SOC 2 등 인증 보유 여부는 [확인 필요]. 미보유 시 US/UK 금융사 직판은 사실상 막힌다(KB08 §10.1). 절차 관문(CISO·Compliance)의 첫 질문이다.
- 권고: 인증 상태를 확인해 (a) 보유 시 어슈어런스 패키지에 명시, (b) 미보유 시 디자인 파트너 계약 구조(파일럿·NDA·데이터 처리 범위 제한)로 우회 설계. **인증 상태 확인 전 Tier 1 발송 보류 해제 금지.**
- **판정(PO):** 인증 현황: SOC 2 등 보안 인증 미보유 (PO 확인) / 접근 영향: 인증을 입장권으로 요구하는 대기업 정면 돌파 지양, 디자인 파트너 구조(유료 파일럿 + NDA + 데이터 처리 범위 제한)로 접근. 어슈어런스 산출물 자체(감사 추적, 인간 승인 게이트)를 신뢰 근거로 제시  서명·날짜: PO jjlee@onelineai.com (세션 대화 확인) · 2026-08-18

## 5. 데이터 소스·검증 도구 선택 (list-build-spec §2·§5)

- 권고: US = ZoomInfo 1차, UK = Cognism 1차 워터폴. 이메일 검증 도구는 UK 레코드 역외 이전 유의(KB09 §9.3) 때문에 EU 리전 처리/무저장 옵션 우선. 모든 벤더·검증 도구와 DPA 체결.
- **판정(PO):** 소스 ____________________ / 검증 도구 ____________________ / DPA ____________________  서명·날짜: __________

## 6. UK LIA 승인 (compliance-frame §2.2, G10)

- 권고: sales-compliance-officer가 LIA 3단 테스트를 작성·공급하고, lia_document_id·lia_retention_expiry를 스키마에 채운다. PO는 LIA 기반 발송을 승인한다.
- **판정(PO):** [ ] LIA 승인(문서 ID ____________________) / [ ] 보류  서명·날짜: __________
- **compliance-officer 공급:** lia_document_id __________ / lia_retention_expiry __________

## 7. 발송 보류 해제 (target-accounts §4, G4·G1)

- 현재: Tier 1~2 후보 전건(25+개)이 발송 보류. 해제 조건: 실측 시그널 확인 + 30일 이내 계정 리서치 산출물 + 필수 필드(G9) 충족 + 인증 상태(§4)가 진입을 막지 않을 것.
- **보류 해제는 PO 전속이다.** 에이전트는 해제하지 않는다.
- **판정(PO):** 계정별 해제 목록 ____________________  서명·날짜: __________

---

## 8. 결정 요약 표

| # | 결정 항목 | 소관 | 상태 |
|---|---|---|---|
| 1 | ICP 확정 | PO | 대기 |
| 2 | Negative ICP 승인(경쟁사 포함) | PO | 대기 |
| 3 | 대형 기관 부서 단위 접근 | PO | 대기 |
| 4 | SOC 2/인증 상태 확인 | PO | 대기 |
| 5 | 데이터 소스·검증 도구 선택 | PO | 대기 |
| 6 | UK LIA 승인 | PO + compliance-officer | 대기 |
| 7 | 발송 보류 해제 | PO | 대기 |

전 항목 미결 상태에서는 캠페인 착수 조건 미충족(G1·G4). 이 문서는 판정란을 비워 상신한다.
