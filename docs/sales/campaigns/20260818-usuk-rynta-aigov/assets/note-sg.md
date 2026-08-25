<!--
INTERNAL · PDF 변환 전 이 주석 블록 삭제 (고객 전달물 아님)
파일: assets/note-sg.md · 작성: deal-strategist · 기준일: 2026-08-19
용도: master-sg.md T3("a short readiness note on the MAS AI risk management guidelines ...
the likely scope, what a 12-month transition actually leaves time for, and a one-page evidence
checklist") 및 T4 오픈 오퍼의 실물 자산.
발송 게이트: outreach-qa 팩트체크 PASS + legal-team 규제 해석 확인(EC-regwind-sg-01 §5)
+ SG 트랙 착수 PO 승인(compliance-frame-sg-au §9) 전 발송 불가 [G1][G3]. 발송은 PO 전속.
증거 카드: EC-regwind-sg-01(MAS AIRG·정보문서 사실 전부) · EC-krx-acl2025-01 ·
EC-rynta-arch-01(About 박스)
주의: AIRG는 확정 전. "proposed/consulted/will be finalised soon" 서술만, 현재형 의무
단정 금지(카드 §5). 12개월 전환기간은 "proposed" 병기. **AIRG 확정 발표 시 이 노트 즉시
개정**(카드 §6, "확정 임박" 서술 전량 폐기). 영국식 철자(finalised, organisation). SG 세그먼트에
SR 26-2·SS1/23 인용 금지. "work across Asia" 류 표현 금지(qa-review F-2).
-->

# MAS's proposed AI risk management guidelines: a readiness note for the proposed 12-month transition

A short briefing for risk and technology risk leaders at Singapore financial institutions. Everything below describes a consultation paper and related MAS statements, not final guidelines; the word "proposed" matters throughout. Positions are stated as of August 2026.

## Where things stand

MAS published a consultation paper on proposed Guidelines on AI Risk Management on 13 November 2025, with comments closing on 31 January 2026. In a written parliamentary reply dated 5 August 2026, MAS stated that the guidelines will apply to all AI use cases, including agentic AI, and will be finalised soon. As of mid-August 2026, the final guidelines have not been issued, and details, including the transition period, may change between consultation and finalisation.

## The likely scope, as proposed

As consulted on, the guidelines would apply to all financial institutions, applied proportionately to each institution's size, AI usage, and risk profile. The proposed coverage includes:

- board and senior management oversight of AI risk;
- AI risk identification, including an AI inventory and materiality assessment;
- controls across the AI lifecycle;
- capabilities and capacity to manage AI risk.

MAS also proposed a 12-month transition period after the guidelines are issued.

There is earlier signal on substance. MAS's December 2024 information paper on AI model risk management, based on a thematic review of banks, set out good practices: cross-functional AI governance forums, AI inventories and materiality assessment, and development and deployment controls covering data management, explainability, fairness, and validation. MAS recommended these practices beyond banks. Institutions that align with the information paper now are unlikely to be starting from zero when the final guidelines arrive.

## What a 12-month transition actually leaves time for

Twelve months sounds generous until it is mapped against every AI system already in production. Our practical arithmetic, assuming the proposed transition survives finalisation broadly intact, splits it into four quarters:

- **Months 1~3: inventory and materiality.** Find every AI system in production and in build, including vendor-delivered ones, and rate the materiality of each. This is the step that cannot be compressed later, because everything else keys off it.
- **Months 4~6: gap assessment and governance design.** Compare current controls against the final text, and stand up the oversight structure: forum, approval paths, escalation routes, and board reporting.
- **Months 7~9: remediation, highest materiality first.** Lifecycle controls, documentation, and validation evidence for the systems that matter most.
- **Months 10~12: evidence assembly and a dry run.** For each material system, test whether its controls, test results, and sign-offs can be produced on request rather than reconstructed.

The reason to start the first quarter's work before finalisation is simple: inventory and materiality work is unlikely to be wasted whatever the final text says, and it is the quarter most often underestimated.

## A one-page evidence checklist

For each material AI system, being able to produce:

1. an inventory entry: what the system does, where it runs, and who owns it;
2. a materiality rating with the rationale recorded;
3. approval records: who signed off deployment and any significant change;
4. lifecycle control evidence: data management, explainability and fairness checks where relevant, and validation results, with dates and reviewer names;
5. monitoring records since deployment;
6. third-party details where the system is vendor-delivered, with the institution's own oversight documented;
7. board or senior management reporting that reflects the system's risk class.

If sign-offs and test results accumulate as a by-product of daily operation, this checklist is an export. If they do not, it is a project.

## About OneLineAI

OneLineAI is a research-driven team working on AI governance and model assurance for financial institutions. We co-developed Won, a Korean finance-specific language model, with the Korea Exchange (KRX), the operator of Korea's national securities market; the work was peer-reviewed and published at ACL 2025. Our platform, RYNTA, is a financial control execution layer: a deterministic engine computes regulatory risk figures, AI agents assist with investigation, triage, and explanation, and accountable humans approve every material outcome.

---

This note is provided for general information only. It is not legal, compliance, or regulatory advice, and it is not a substitute for advice from qualified counsel or your own legal and compliance functions in your jurisdiction. Summaries of regulatory documents are ours, not the regulators'; the original texts govern. No regulator referenced in this note has reviewed or endorsed this note or our products. Positions are stated as of August 2026 and may change. In particular, the final guidelines may differ from the consultation described here.
