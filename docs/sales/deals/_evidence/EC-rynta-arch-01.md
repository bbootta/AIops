# 증거 카드: EC-rynta-arch-01

> 저장 경로: `docs/sales/deals/_evidence/EC-rynta-arch-01.md` (계정 무관 공용 라이브러리)
> 카피·제안서·설문 답변의 모든 사실 주장은 이 카드의 등급 규칙을 따른다. [확인] 등급만 사실로 진술할 수 있다 [G3].

| 항목 | 내용 |
|---|---|
| 카드 ID | EC-rynta-arch-01 |
| 작성 에이전트 | deal-strategist |
| 검토 | outreach-qa (원출처 대조) 대기 (미실시) |
| 승인 | 해당 없음 (내부 라이브러리) / 커버리지·구현 상태 관련 문구는 PO 확인 |
| 기준일 | 2026-08-19 (재검증 주기: 분기) |

## 1. 카드 요약

- 주장 한 줄: RYNTA v9.0은 결정론적 엔진이 계산하고, AI 에이전트가 조사·분류·설명·워크플로 조정을 보조하며, 중요한 결과는 인간이 승인하는 Financial Control Execution Layer이고, 5대 AI 가드레일과 자동확정 금지 목록, ISO/IEC 42001 주 기준 + EU AI Act + NIST AI RMF 교차 참조로 설계되었다.
- **신뢰 등급 (KB08 규칙): [확인]** (1차 소스: 내부 저장소 AIMS_POLICY.md §8, risk_lib/rynta.py. KB08 §4.6이 이를 [확인]으로 인정. 제품 아키텍처 서술이며 성과·성능 주장이 아님)
- 사용 범위: 아키텍처·설계 원칙 서술로만 대외 사용 가능. 구현 완성도·성능·도입 성과 주장으로 확장 금지 [G3].
- 주 사용처: 콜드메일 본문(제품 한 줄), 디스커버리, 트러스트 패키지, 보안 설문.
- **이 쐐기(AI 거버넌스·독립검증)에서의 사용 맥락**: "우리 스스로 이 구조로 운영한다. AI 에이전트가 이 아웃리치를 준비했지만 발송은 인간이 승인했다(이 메일 자체가 human-approval gate의 증거)"는 메타 증거. 말이 아니라 운영으로 보여주는 카드.

## 2. 주장 (정확한 형태)

RYNTA v9.0("Risk Yard with Neural Trustworthy Architecture")은 Financial Control Execution Layer로:

1. **3층 구조**: 결정론적 엔진이 규제 리스크 수치를 계산하고, AI 에이전트는 조사·분류·설명·워크플로 조정을 지원하며, 중요한 결과는 책임 있는 사람이 승인한다.
2. **5대 AI 가드레일** (BRD AIG 요건): 조회 전용(AIG-002), 제안 전용·자동확정 금지(AIG-003), 승인 우선(AIG-004), 최소 권한(AIG-005), Kill Switch(AIG-009).
3. **AI 자동확정 금지 목록**: 신용등급·여신승인, 가격·거래, PD·LGD·EAD, ECL·충당금·회계전표, RWA·NCR·BIS 비율, 감독제출·공시, 경영조치, 운영코드·모형 배포. 에이전트는 산출·권고까지만 하고 확정은 인간이 한다.
4. **준거 기준**: ISO/IEC 42001:2023을 주 기준으로 EU AI Act(Regulation (EU) 2024/1689), EU Trustworthy AI Ethics Guidelines, NIST AI RMF 1.0을 통제 설계 교차 참조로 사용한다. **자동 준수·인증·법률자문을 의미하지 않는다** (이 단서는 대외 문구에서 생략 불가).
5. **구성**: 12개 canonical 제품 / 6개 상업 suite. 이번 쐐기 제품(PRD-AIG "AI Governance & Agentic", PRD-VAL "Continuous & Independent Validation Assurance")은 Foundation & Assurance(RYNTA-FND) suite 소속.

## 3. 원출처

| 출처 | 유형 | URL/문서 | 확인일 | 비고 |
|---|---|---|---|---|
| AIMS_POLICY.md §8 (8-1 가드레일, 8-2 자동확정 금지, 8-3 준거 기준) | 내부 1차 소스 | /home/user/AIops/AIMS_POLICY.md | 2026-08-19 | |
| risk_lib/rynta.py (PACKAGE_NAME, GUARDRAILS, NO_AUTO_DECISION, AI_STANDARDS, PRODUCTS, SUITES) | 내부 1차 소스 (코드) | /home/user/AIops/risk_lib/rynta.py | 2026-08-19 | 이 저장소 자체가 RYNTA 구현체 |
| KB08 §4.6 | 내부 KB | kb/sales/08-oneline-ai-context.md | 2026-08-19 | [확인] 등급 부여 근거 |
| ICP §0 (제품 정의, PO 확정) | 캠페인 문서 | docs/sales/campaigns/20260818-usuk-rynta-aigov/icp-draft.md | 2026-08-19 | |

## 4. 사용 가능한 문구

- 영문 (풀 문장): `RYNTA v9.0 is a Financial Control Execution Layer: a deterministic engine computes regulatory risk figures, AI agents assist with investigation, triage, explanation, and workflow orchestration, and accountable humans approve every material outcome. Agents never auto-finalize credit ratings, risk parameters, provisions, capital ratios, or regulatory submissions.`
- 영문 (짧은 형, 카피 삽입용): `deterministic engine + AI assist + human approval, with read-only-by-default, propose-only, approval-first, least-privilege, and kill-switch guardrails`
- 영문 (준거 기준, 단서 포함 필수): `Controls are cross-referenced to ISO/IEC 42001:2023 (primary), the EU AI Act (Regulation (EU) 2024/1689), and NIST AI RMF 1.0. This is a control-design mapping; it does not imply automatic compliance, certification, or legal advice.`
- 영문 (메타 증거, 이 캠페인 전용): `We run our own operations on these guardrails: AI agents drafted and researched this outreach, and a named human reviewed and approved it before it reached you. The architecture we sell is the one we operate.`
- 국문: `RYNTA는 결정론 엔진이 계산하고 AI가 보조하며 인간이 승인하는 금융 통제 실행 계층입니다. 에이전트는 산출·권고까지만 하고 확정은 사람이 합니다.`
- 페르소나별 변형:
  - CISO/Compliance용: `Agents start read-only, operate under least privilege with scoped tools, propose rather than decide, and can be halted per scope via kill switch; every material change passes a human approval gate with an audit trail.`
  - Head of AI Governance용: `The no-auto-decision list is explicit and enforced: ratings, pricing, PD/LGD/EAD, ECL, RWA and capital ratios, regulatory filings, management actions, and model deployment are human-approved, always.`

## 5. 사용 금지 표현

- "EU AI Act compliant", "ISO/IEC 42001 certified", "NIST AI RMF 준수 보장" (교차 참조 설계이지 인증·자동 준수가 아님. AIMS_POLICY §8-3 단서 생략 금지)
- "12개 제품 전부 즉시 배포 가능/완성" (요건 커버리지에 partial·backlog가 존재. 커버리지 수치의 대외 인용은 PO 확인 후)
- RYNTA의 성능 수치·도입 성과·고객 수 (존재하지 않음. IBK·하나 사례는 OLA/데이터 라인이며 RYNTA 도입 사례가 아니다)
- "규제 리스크를 자동으로 해결", "검증을 자동화해 인간 검토가 불필요" (설계 철학과 정반대)
- "환각 없음", "100% 정확" 류 절대 주장 (KB08 §11.2)

## 6. 사용 이력과 유효성

| 사용처 (문서/캠페인) | 일자 | outreach-qa 대조 |
|---|---|---|
| 20260818-usuk-rynta-aigov (예정: 제품 한 줄 + 메타 증거) | 미발송 | 대기 |

- 원출처(AIMS_POLICY, rynta.py)가 버전업되면 카드를 재검증한다. v9.0 버전 표기는 원출처와 동기화한다.
