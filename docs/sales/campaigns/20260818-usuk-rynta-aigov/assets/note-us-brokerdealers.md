<!--
INTERNAL · PDF 변환 전 이 주석 블록 삭제 (고객 전달물 아님)
파일: assets/note-us-brokerdealers.md · 작성: deal-strategist · 기준일: 2026-08-19
용도: master-us-brokerdealers.md T3("We condensed the AI sections of FINRA's 2026 report and
the SEC's FY2026 exam priorities into a two-page note ... what your written procedures are now
expected to cover, and the audit evidence worth preparing early") 및 T4 오픈 오퍼의 실물 자산.
발송 게이트: outreach-qa 팩트체크 PASS + legal-team 규제 해석 확인(EC-regwind-us-bd-01 §5)
+ PO 승인 전 발송 불가 [G1][G3]. 발송(PDF 변환·첨부·회신)은 PO 전속.
증거 카드: EC-regwind-us-bd-01(FINRA·SEC 사실 전부) · EC-krx-acl2025-01 · EC-rynta-arch-01(About 박스)
주의: 프롬프트·출력 로깅을 FINRA 권고로 서술 금지(카드 §2-3, 원문 대조 전). 체크리스트
7번은 "우리 실무 제안"으로만 프레이밍했고 FINRA에 귀속하지 않음. "requires/rule" 격상 금지,
"asks/recommends/observes" 유지(카드 §5). SR 26-2 인용 금지 세그먼트. 미국 고객·시험 대응
경험 암시 표현 금지(KB08 §11.2-5).
-->

# AI in FINRA's 2026 report and the SEC's FY2026 exam priorities: a WSP readiness view for broker-dealers

A two-page briefing for broker-dealer risk and compliance leaders. Positions are stated as of August 2026.

## What the two documents say

**FINRA.** FINRA's 2026 Annual Regulatory Oversight Report, published in December 2025, asks member firms to reflect three AI topics in their written supervisory procedures (WSPs): AI governance, AI vendor risk management, and AI-agent monitoring. On generative AI governance, the report's recommendations include firm-wide supervision processes, mitigating hallucination and bias risks, testing outputs for reliability and accuracy, and documentation. It is also the first of FINRA's annual reports to include observations on AI agents, meaning systems that carry out tasks autonomously.

One framing point worth keeping straight when briefing internally: the report sets out observations and effective practices, not a new rulebook. The accurate verbs are "asks" and "recommends," not "requires."

**SEC.** The SEC's Division of Examinations announced its FY2026 examination priorities on November 17, 2025. On AI, the priorities include the adequacy of policies, procedures, and oversight around the use of AI, automated tools, and algorithms; the accuracy of statements firms make about their AI capabilities; and whether AI-assisted outputs are consistent with client profiles and disclosures.

## What this means in practice

In our reading, the common thread across both documents is evidence of supervision. AI adoption inside firms tends to move faster than the written procedures behind it, and the gap surfaces in an exam as a simple question: for this AI-assisted activity, where is the procedure that covers it, and how do you show that the supervision happened? For AI agents the question sharpens, because the activity itself is autonomous: what did the agent do, who permitted it, and who reviewed the outcome?

Answering from records is a different position than answering from reconstruction. The preparation below is aimed at the first position.

## A WSP reflection checklist

These are practical preparation steps, in our words. They are not a restatement of FINRA or SEC language.

1. **Inventory AI use across the firm.** Include vendor-delivered tools and any agentic systems, and note which business lines depend on each.
2. **Map each use to a WSP section.** Flag every AI use that no written procedure currently covers; the unmapped items are the priority list.
3. **Write the governance procedure.** Who approves a new AI use, on what criteria, and how firm-wide supervision works once it is live.
4. **Cover vendor risk explicitly.** Due diligence, contractual terms, and ongoing monitoring for third-party AI tools, treated with the same discipline as other critical vendors.
5. **Define AI-agent monitoring.** What autonomous actions are permitted, who reviews them and at what cadence, and how exceptions escalate to a person.
6. **Check AI claims against reality.** Align marketing, disclosures, and client communications with what your AI actually does; the accuracy of AI capability statements is on the SEC's exam agenda.
7. **Decide what record the firm keeps.** Choose what evidence of AI-assisted work and its supervision is retained, and for how long, so that an examiner's question is answered from records rather than memory. This last item is our practical suggestion rather than regulator language, but it is the item most likely to spare your team reconstruction work later.

## The audit evidence worth preparing early

If you prepare only three artifacts this quarter, we would suggest: the AI-use inventory with owners named; the mapping of each use to its WSP coverage, including the honest gaps; and a written definition of permitted autonomous actions for any agentic system in production. Each is inexpensive to produce now and expensive to reconstruct later.

## About OneLineAI

OneLineAI is a research-driven team working on AI governance and model assurance for financial institutions. We co-developed Won, a Korean finance-specific language model, with the Korea Exchange (KRX), the operator of Korea's national securities market; the work was peer-reviewed and published at ACL 2025. Our platform, RYNTA, is a financial control execution layer: a deterministic engine computes regulatory risk figures, AI agents assist with investigation, triage, and explanation, and accountable humans approve every material outcome.

---

This note is provided for general information only. It is not legal, compliance, or regulatory advice, and it is not a substitute for advice from qualified counsel or your own legal and compliance functions in your jurisdiction. Summaries of regulatory documents are ours, not the regulators'; the original texts govern. No regulator referenced in this note has reviewed or endorsed this note or our products. Positions are stated as of August 2026 and may change.
