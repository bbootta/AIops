<!--
INTERNAL · PDF 변환 전 이 주석 블록 삭제 (고객 전달물 아님)
파일: assets/note-au.md · 작성: deal-strategist · 기준일: 2026-08-19
용도: master-au.md T3("a two-page note for Australian risk teams on APRA's AI letter read
next to CPS 230: where sample-based assurance falls short for AI models, and a practical
sequence for moving specific controls to continuous checking first") 및 T4 오픈 오퍼의 실물 자산.
발송 게이트: outreach-qa 팩트체크(특히 APRA 원문 verbatim 대조) PASS + legal-team 규제
해석 확인(EC-regwind-au-01 §5) + AU 컴플라이언스 프레임 확정 전 발송 불가 [G1][G3]. 발송은 PO 전속.
증거 카드: EC-regwind-au-01(APRA 서한·CPS 230·ASIC REP 798 사실 전부) · EC-krx-acl2025-01 ·
EC-rynta-arch-01(About 박스)
주의: **EC-regwind-au-01 규칙: APRA 서한 직접 인용(따옴표) 절대 금지, 요약 서술만.** 본문에
"our summary, not APRA's text" 명시로 이중 방어. "호주판 SR 26-2" 표현 금지, SR 26-2·SS1/23
인용 금지. CPS 230을 AI 전용 규제로 서술 금지. 수신자 기관 위반·미준비 단정 금지(감독 조치
직후 계정은 PO 타이밍 판단). 호주/영국식 철자(organisation, prioritise).
-->

# APRA's AI letter and CPS 230: a practical view on moving towards continuous assurance

A two-page briefing for risk leaders at APRA-regulated institutions. Wording throughout is our summary, not APRA's text. Positions are stated as of August 2026.

## What APRA said, in summary

On 30 April 2026, APRA published its first AI-specific letter to industry, drawing on targeted supervision reviews across banking, insurance, and superannuation. In our words rather than APRA's: the letter warned that governance, risk management, assurance, and operational resilience practices are not keeping pace with the scale, speed, and complexity of AI adoption. It observed that AI risk cuts across several domains at once: operational risk, cyber, data governance, model risk, compliance, and third-party dependencies.

The letter also addressed assurance directly, in substance making the point that point-in-time, sample-based assurance has limits for probabilistic models, which learn, adapt, and can degrade over time.

For completeness, the conduct side is active too: ASIC's Report 798 (October 2024) flagged AI governance gaps from the conduct regulator's perspective. AI supervision in Australia runs on both tracks, APRA on prudence and ASIC on conduct.

## CPS 230, read next to the letter

CPS 230, APRA's prudential standard on operational risk management, took effect on 1 July 2025. The transition period for pre-existing material service provider arrangements ended on 1 July 2026, so the standard now applies in full. CPS 230 is technology-neutral and vendor-neutral: it is not an AI standard, but it applies where AI underpins critical operations.

Read together, the two documents frame the same practical question from different angles. CPS 230 asks whether critical operations stay within tolerance; the AI letter asks whether your assurance over AI keeps up with what the AI is doing. Neither mandates a particular tool or method. Both make "we checked it last year" a weaker answer than it used to be.

## Where sample-based assurance falls short for AI models

Our practical reading. A sample-based review can say a control worked when it was checked. For a static system, that statement travels reasonably well across the year. For a model that learns, adapts, or degrades, it does not: the conclusion ages quickly, the annual cycle leaves most of the year unobserved, and the evidence for each review is assembled by hand after the fact rather than accumulated as the system runs. Continuous assurance inverts each of those properties: the check runs on a schedule matched to the model, results are logged as they occur, and the evidence exists before anyone asks for it.

None of this means every control should become continuous. It means the controls guarding material, adaptive models are the wrong place for once-a-year sampling.

## A practical sequence for moving specific controls first

1. **Start narrow.** Pick a small set of material models or controls where a failure would matter most and where recomputation or automated checking is feasible.
2. **Define "working now" for each.** The check to run, its frequency, and the tolerance that separates pass from escalation, agreed before anything is automated.
3. **Automate the checking where the logic is deterministic.** Recompute and compare where you can; keep people approving outcomes and owning the sign-off.
4. **Log every check and result.** Assurance evidence should accumulate as a by-product of operation, not be assembled per review.
5. **Report the shift.** Show the board or risk committee which controls have moved from sampled, point-in-time review to continuous checking, and what remains on the old cycle.
6. **Expand tier by tier.** Retain periodic review for everything not yet continuous; the goal is a deliberate migration, not a big bang.

Steps 1 and 2 cost little and can start this quarter. They also produce the artefact most useful in any supervisory conversation: a written, prioritised view of which assurance is continuous, which is periodic, and why.

## About OneLineAI

OneLineAI is a research-driven team working on AI governance and model assurance for financial institutions. We co-developed Won, a Korean finance-specific language model, with the Korea Exchange (KRX), the operator of Korea's national securities market; the work was peer-reviewed and published at ACL 2025. Our platform, RYNTA, is a financial control execution layer: a deterministic engine computes regulatory risk figures, AI agents assist with investigation, triage, and explanation, and accountable humans approve every material outcome.

---

This note is for general information, not legal or compliance advice. Positions are stated as of August 2026 and may change.
