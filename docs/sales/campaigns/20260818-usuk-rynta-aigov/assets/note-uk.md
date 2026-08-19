<!--
INTERNAL · PDF 변환 전 이 주석 블록 삭제 (고객 전달물 아님)
파일: assets/note-uk.md · 작성: deal-strategist · 기준일: 2026-08-19
용도: master-uk.md T3("a two-page note for heads of model validation on SS1/23 Principle 4
... where independence questions show up, and the evidence supervisors tend to ask for first")
및 T4 오픈 오퍼의 실물 자산.
발송 게이트: outreach-qa 팩트체크 PASS + legal-team 규제 해석 확인(EC-regwind-usuk-01 §5)
+ PO 승인 전 발송 불가 [G1][G3]. 발송(PDF 변환·첨부·회신)은 PO 전속.
증거 카드: EC-regwind-usuk-01(SS1/23 사실 전부) · EC-krx-acl2025-01 · EC-rynta-arch-01(About 박스)
주의: qa-review F-4 반영(적용 범위 정직 서술: 내부모형 승인 보유 기관. 비IRB 계정 과적용
방지 문단 포함). I-2 반영("as it applies to" 계열 관용 표현). 영국식 철자(behaviour,
judgement, organisation, finalised). 원칙 4 외 개별 원칙의 명칭·내용은 카드 미기재라 서술
안 함("five principles" 수준까지만).
-->

# SS1/23 Principle 4 in practice: independent validation as AI and ML models join the inventory

A two-page briefing for heads of model validation and model risk at UK firms. Positions are stated as of August 2026.

## What SS1/23 says, and to whom it applies

The PRA's supervisory statement SS1/23 on model risk management has been in force since May 2024. It sets out five principles, and Principle 4 makes independent model validation an explicit supervisory expectation.

Scope, stated plainly: SS1/23 applies to UK-incorporated banks, building societies, and PRA-designated investment firms that hold internal model approval for regulatory capital purposes. If your firm sits outside that formal scope, nothing in this note creates an obligation; the principles can still serve as a reference point when setting internal standards, but that is a choice, not a requirement.

What makes Principle 4 topical now is timing. The expectation of independent validation is meeting an inventory that is changing shape, as AI and machine learning models move from pilots into production alongside the traditional book.

## Where independence questions show up

Our practical reading: as AI and ML models join the inventory, questions about independent validation tend to concentrate in four places.

1. **Capacity against inventory growth.** More models and deeper reviews with the same headcount push validation into annual cycles where the backlog, rather than risk, decides the schedule.
2. **Independence of judgement, not just reporting lines.** Where validators rely on the development team's own tooling and outputs to check a model, independence weakens in practice even when the organisation chart says otherwise.
3. **Point-in-time conclusions on adaptive models.** A model reviewed once a year can change behaviour between reviews. For models that learn or degrade, the validation conclusion ages faster than the review cycle.
4. **Reproducibility of the conclusion.** Whether a different reviewer, months later, could reach and defend the same validation conclusion from what was recorded at the time.

## The evidence worth having ready

Framed as a practical view, in our words, not supervisory language:

- a current model inventory with risk tiers, including AI and ML entries and the rationale for how each was classified;
- documented independence arrangements: who validates, their reporting lines, and the tooling they depend on;
- validation coverage and backlog by tier, with dates, so the position on any given day is visible;
- for each material model, a record sufficient for a different person to reproduce the validation conclusion;
- monitoring results between validation cycles for models that adapt or can degrade.

## A checklist for making validation continuous rather than annual

1. **Tier the inventory** and set a review depth per tier that the team can actually sustain, rather than one it cannot.
2. **Start narrow.** Choose the material models where continuous checks are feasible and begin there, keeping periodic review for the rest.
3. **Define each check.** What is recomputed or tested, how often, and against what tolerance, agreed before the checking starts.
4. **Log results as they occur,** so that evidence accumulates as a by-product of the process instead of being assembled for each cycle.
5. **Keep humans deciding.** Continuous checking should feed reviewer judgement, not replace it; the sign-off remains a named person's.
6. **Report the shift.** Show the model risk committee which part of the inventory has moved from annual, sampled review to continuous checking, and what remains.

The order matters. Tiering and definitions cost little and clarify everything that follows; automation decisions made before them tend to get revisited.

## About OneLineAI

OneLineAI is a research-driven team working on AI governance and model assurance for financial institutions. We co-developed Won, a Korean finance-specific language model, with the Korea Exchange (KRX), the operator of Korea's national securities market; the work was peer-reviewed and published at ACL 2025. Our platform, RYNTA, is a financial control execution layer: a deterministic engine computes regulatory risk figures, AI agents assist with investigation, triage, and explanation, and accountable humans approve every material outcome.

---

This note is for general information, not legal or compliance advice. Positions are stated as of August 2026 and may change.
