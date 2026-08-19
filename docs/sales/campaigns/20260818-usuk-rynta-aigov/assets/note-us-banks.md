<!--
INTERNAL · PDF 변환 전 이 주석 블록 삭제 (고객 전달물 아님)
파일: assets/note-us-banks.md · 작성: deal-strategist · 기준일: 2026-08-19
용도: master-us-banks.md T3("a two-page note on SR 26-2 for validation leads: what changed
from SR 11-7, where generative and agentic AI now sit, and the questions your examiners are
likely to raise about your AI inventory first") 및 T4 오픈 오퍼의 실물 자산.
발송 게이트: outreach-qa 팩트체크 PASS + legal-team 규제 해석 확인(EC-regwind-usuk-01 §5)
+ PO 승인 전 발송 불가 [G1][G3]. 발송(PDF 변환·첨부·회신)은 PO 전속.
증거 카드: EC-regwind-usuk-01(SR 26-2 사실 전부) · EC-krx-acl2025-01 · EC-rynta-arch-01(About 박스)
주의: SR 21-8 대체 서술은 QA 재확인 전이므로 미기재(qa-review-master §7). SR 11-7은
"대체된 구 지침"으로만 언급. 체크리스트·질문은 실무 제안으로 명시(규제 문언 아님).
-->

# SR 26-2 and your AI model inventory: what changes for validation teams

A two-page briefing for model risk and validation leaders at US banks. Positions are stated as of August 2026.

## What changed

In April 2026, the US federal banking agencies (the Federal Reserve, OCC, and FDIC) issued revised supervisory guidance on model risk management. The Federal Reserve released it as SR 26-2, effective April 17, 2026. It replaces SR 11-7, and it is most relevant to banks with more than $30 billion in total assets.

For validation teams, two points carry most of the weight:

1. **Validation expectations for traditional models remain.** SR 26-2 keeps independent validation as a supervisory expectation for the models it covers. Nothing in the revision reduces the need to validate the traditional book.
2. **Generative and agentic AI now sit outside the guidance.** SR 26-2 explicitly places generative and agentic AI outside its scope and notes that they require a separate governance framework. The guidance names the gap; it does not fill it.

## What this means in practice

In our reading, the revision splits the work of a model risk function into two tracks that need different treatment:

- **The traditional track.** The inventory keeps growing as machine learning models enter production, and each material model still needs independent validation. The practical question is capacity: review depth, backlog, and whether the evidence behind each validation is reproducible when someone later asks how a conclusion was reached.
- **The separate governance track.** For generative and agentic AI, SR 26-2 does not hand banks a prescriptive framework. Each institution has to decide what its separate governance framework contains, who owns it, and how it connects to the existing model risk function. In many organizations this work lands, at least initially, on validation teams that are already at capacity.

## Questions worth being ready to answer

These are practical readiness questions, in our words. They are not a restatement of the guidance.

1. Which production systems meet your definition of a model, and where do generative and agentic AI systems sit relative to that boundary?
2. What documented rationale supports each boundary decision, and who approved it?
3. For AI systems outside the model risk framework, which governance framework applies, and who is accountable for it?
4. How current is the inventory, and does it capture AI capabilities embedded in vendor products?
5. Can you show validation coverage, backlog, and review depth for material models on any given day, rather than assembling that picture only when asked?

## A preparation checklist

1. **Re-baseline the inventory.** Review the model inventory against your SR 26-2 scope decisions, and record the rationale for every inclusion and exclusion.
2. **Classify generative and agentic AI explicitly.** Give these systems their own inventory view, even before the separate governance framework is finalized.
3. **Assign ownership of the separate framework.** Name the accountable executive and committee for generative and agentic AI governance; a framework without a named owner tends to stall.
4. **Map validation coverage against capacity.** Quantify the backlog, the review depth per model tier, and what the current team can sustain.
5. **Set evidence standards.** Define what a completed validation must contain so that its conclusion can be reproduced and reviewed later, by a different person.
6. **Include vendor-embedded AI.** Extend inventory and governance scope to AI capabilities delivered inside third-party products.
7. **Brief the committee.** Put the two-track structure, its owners, and its timeline in front of the model risk committee and, where appropriate, the board.

None of this requires new tooling to begin. It does require deciding early who owns each track, because both tracks generate evidence obligations that compound the longer they stay unassigned.

## About OneLineAI

OneLineAI is a research-driven team working on AI governance and model assurance for financial institutions. We co-developed Won, a Korean finance-specific language model, with the Korea Exchange (KRX), the operator of Korea's national securities market; the work was peer-reviewed and published at ACL 2025. Our platform, RYNTA, is a financial control execution layer: a deterministic engine computes regulatory risk figures, AI agents assist with investigation, triage, and explanation, and accountable humans approve every material outcome.

---

This note is for general information, not legal or compliance advice. Positions are stated as of August 2026 and may change.
