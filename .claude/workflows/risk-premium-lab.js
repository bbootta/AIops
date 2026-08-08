export const meta = {
  name: 'risk-premium-lab',
  description: '리스크프리미엄 연구실 전체 연구 사이클: 브리프 → 선행연구 → 방법론 경쟁 → 시뮬레이션 → 검증 루프 → 논문 → 피어리뷰 루프 → 후속연구·교신',
  whenToUse: '연구 질문 하나를 논문 초안까지 밀어붙일 때 실행. args: { question?: string, max_validation_rounds?: number, max_review_rounds?: number }',
  phases: [
    { title: '브리프', detail: '리드 교수가 연구 질문을 브리프로 구체화' },
    { title: '선행연구', detail: '선행연구 조사팀 병렬 심층조사 + 신규성 검증' },
    { title: '방법론', detail: '방법론 개발팀 3안 경쟁 → 리드 교수 심사·채택' },
    { title: '구현검증', detail: '시뮬레이션팀 구현 ↔ 검증팀 적대적 검증 루프' },
    { title: '논문작성', detail: '논문 작성팀 초안 집필' },
    { title: '피어리뷰', detail: '심사위원 3인 패널 ↔ 수정 루프' },
    { title: '마무리', detail: '후속연구 발굴 + 교신 문서 작성' },
  ],
}

const ROOT = '/home/user/AIops'
const DEFAULT_QUESTION =
  '한국 개별가계소비자료(가계동향조사·KLIPS·재정패널 등)를 이용한 소비기반 자산가격결정: ' +
  '제한적 주식시장 참가와 가계 이질성은 한국 주식프리미엄 퍼즐을 얼마나 설명하는가? ' +
  '(성균관대 이재준 석사논문 「개별가계소비자료를 이용한 자산가격결정」의 저널 논문 디벨롭)'

const question = (args && args.question) || DEFAULT_QUESTION
const maxValidationRounds = (args && args.max_validation_rounds) || 2
const maxReviewRounds = (args && args.max_review_rounds) || 2

const CONTEXT = `
[연구실 공통 컨텍스트]
- 연구 질문: ${question}
- 지식베이스: ${ROOT}/knowledge-base/ (시작 전 00-index.md 필독)
- 산출물 루트: ${ROOT}/research/
- git 커밋은 하지 말 것 (오케스트레이터가 처리).
`

const BRIEF_SCHEMA = {
  type: 'object',
  properties: {
    brief_file: { type: 'string' },
    research_question: { type: 'string' },
    hypotheses: { type: 'array', items: { type: 'string' } },
    lit_topics: { type: 'array', items: { type: 'string' }, minItems: 2, maxItems: 4,
      description: '선행연구 조사팀에 맡길 심층조사 주제' },
    success_criteria: { type: 'string' },
  },
  required: ['brief_file', 'research_question', 'hypotheses', 'lit_topics', 'success_criteria'],
}

const FILE_SUMMARY_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    summary: { type: 'string', description: '3-5문장 요약 (한국어)' },
    revisions_required: { type: 'string', description: '현재 연구 설계에 요구되는 수정사항. 없으면 "없음"' },
  },
  required: ['file', 'summary'],
}

const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    winner: { type: 'integer', description: '채택안 번호 (1-3)' },
    spec_file: { type: 'string', description: '통합 최종 스펙 파일 경로' },
    rationale: { type: 'string' },
  },
  required: ['winner', 'spec_file', 'rationale'],
}

const VALIDATION_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'PASS_WITH_ISSUES', 'FAIL'] },
    report_file: { type: 'string' },
    critical_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'report_file', 'critical_issues'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['ACCEPT', 'MINOR_REVISION', 'MAJOR_REVISION', 'REJECT'] },
    report_file: { type: 'string' },
    major_points: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'report_file', 'major_points'],
}

// ── 1. 브리프 ──────────────────────────────────────────────
phase('브리프')
const brief = await agent(`${CONTEXT}
연구 질문을 검증 가능한 연구 브리프로 구체화하여 ${ROOT}/research/briefs/brief.md 에 작성하세요.
브리프에는 가설, 데이터 전략, 식별 전략 초안, 성공 기준, 그리고 선행연구 조사팀에 맡길 심층조사 주제 2~4개를 포함하세요.`,
  { agentType: 'rp-lead-professor', label: '리드교수:브리프', phase: '브리프', schema: BRIEF_SCHEMA })

if (!brief) throw new Error('브리프 작성 실패')
log(`브리프 완료: ${brief.brief_file} / 조사 주제 ${brief.lit_topics.length}개`)

// ── 2. 선행연구 조사 ────────────────────────────────────────
phase('선행연구')
const litReports = (await parallel(brief.lit_topics.map((topic, i) => () =>
  agent(`${CONTEXT}
연구 브리프: ${brief.brief_file} (먼저 읽을 것)
심층조사 주제: ${topic}
조사 보고서를 ${ROOT}/research/literature/ 아래에 저장하고, 이 연구 설계의 신규성에 위협이 되는 선행연구가 있는지 반드시 확인하세요.`,
    { agentType: 'rp-literature-team', label: `선행연구:${i + 1}`, phase: '선행연구', schema: FILE_SUMMARY_SCHEMA })
))).filter(Boolean)

const litDigest = litReports.map(r => `- ${r.file}: ${r.summary} [요구 수정: ${r.revisions_required || '없음'}]`).join('\n')
log(`선행연구 조사 완료: ${litReports.length}건`)

// ── 3. 방법론 경쟁 → 심사 ──────────────────────────────────
phase('방법론')
const ANGLES = [
  '이론 충실 우선: 선호 구조와 불완전시장 이론(Constantinides-Duffie 계열)에 가장 충실한 설계',
  '데이터 현실성 우선: 한국 가계 미시데이터의 실제 제약(짧은 패널, 소비 항목, 주주 식별)에서 최대한을 뽑아내는 설계',
  '강건성·계량 엄밀성 우선: 측정오차·약식별·선택편의에 가장 강건한 추정 전략 중심 설계',
]
const proposals = (await parallel(ANGLES.map((angle, i) => () =>
  agent(`${CONTEXT}
연구 브리프: ${brief.brief_file}
선행연구 조사 결과:
${litDigest}
당신의 관점: ${angle}
이 관점에 충실한 실증 설계안을 ${ROOT}/research/methodology/proposal-${i + 1}.md 에 작성하세요.`,
    { agentType: 'rp-methodology-team', label: `방법론:제안${i + 1}`, phase: '방법론', schema: FILE_SUMMARY_SCHEMA })
))).filter(Boolean)

const judged = await agent(`${CONTEXT}
방법론 개발팀이 제출한 설계안들을 심사하세요:
${proposals.map((p, i) => `${i + 1}. ${p.file}: ${p.summary}`).join('\n')}
연구 브리프(${brief.brief_file})와 선행연구 조사 결과를 기준으로 각 안의 강약점을 평가하고,
채택안을 중심으로 (필요시 다른 안의 장점을 이식하여) 최종 통합 스펙을 ${ROOT}/research/methodology/spec.md 에 작성하세요.
심사평도 spec.md 앞부분에 포함하세요.`,
  { agentType: 'rp-lead-professor', label: '리드교수:방법론심사', phase: '방법론', schema: JUDGE_SCHEMA })

if (!judged) throw new Error('방법론 심사 실패')
log(`방법론 확정: 제안 ${judged.winner} 채택 → ${judged.spec_file}`)

// ── 4. 구현 ↔ 검증 루프 ────────────────────────────────────
phase('구현검증')
let sim = await agent(`${CONTEXT}
최종 방법론 스펙: ${judged.spec_file} (그대로 구현할 것)
${ROOT}/research/simulations/ 에 파이프라인을 구현하고 몬테카를로 검증과 보정 실험을 실행하세요.
결과 요약은 ${ROOT}/research/simulations/output/results.md 에 저장하세요.`,
  { agentType: 'rp-simulation-team', label: '시뮬레이션:구현', phase: '구현검증', schema: FILE_SUMMARY_SCHEMA })

let validation = null
for (let round = 1; round <= maxValidationRounds; round++) {
  validation = await agent(`${CONTEXT}
방법론 스펙: ${judged.spec_file}
시뮬레이션 산출물: ${ROOT}/research/simulations/ (결과 요약: ${sim ? sim.file : '결과 파일을 직접 찾을 것'})
검증 절차 전체를 수행하고 보고서를 ${ROOT}/research/validation/round-${round}.md 에 저장하세요.`,
    { agentType: 'rp-validation-team', label: `검증:라운드${round}`, phase: '구현검증', schema: VALIDATION_SCHEMA })

  if (!validation || validation.verdict !== 'FAIL') break
  log(`검증 라운드 ${round}: FAIL — 치명 이슈 ${validation.critical_issues.length}건, 수정 재구현`)
  if (round === maxValidationRounds) break
  sim = await agent(`${CONTEXT}
검증팀이 FAIL 판정을 내렸습니다. 검증 보고서: ${validation.report_file}
치명 이슈:
${validation.critical_issues.map(x => `- ${x}`).join('\n')}
${ROOT}/research/simulations/ 의 구현을 수정하고 전체 파이프라인을 재실행한 뒤 결과 요약을 갱신하세요.`,
    { agentType: 'rp-simulation-team', label: `시뮬레이션:수정${round}`, phase: '구현검증', schema: FILE_SUMMARY_SCHEMA })
}
const validationVerdict = validation ? validation.verdict : 'UNKNOWN'
log(`검증 최종 판정: ${validationVerdict}`)

// ── 5. 논문 작성 ────────────────────────────────────────────
phase('논문작성')
let draft = await agent(`${CONTEXT}
다음 산출물을 종합하여 논문 초안을 ${ROOT}/research/paper/draft-v1.md 에 작성하세요:
- 브리프: ${brief.brief_file}
- 방법론 스펙: ${judged.spec_file}
- 시뮬레이션 결과: ${ROOT}/research/simulations/output/
- 검증 보고서: ${validation ? validation.report_file : '(없음)'} (최종 판정: ${validationVerdict})
검증 판정이 PASS_WITH_ISSUES면 해당 이슈를 논문의 한계 섹션에 정직하게 반영하세요.`,
  { agentType: 'rp-paper-writing-team', label: '논문:초안', phase: '논문작성', schema: FILE_SUMMARY_SCHEMA })

if (!draft) throw new Error('논문 초안 작성 실패')

// ── 6. 피어 리뷰 ↔ 수정 루프 ───────────────────────────────
phase('피어리뷰')
const LENSES = ['계량 심사위원', '이론 심사위원', '문헌·기여 심사위원']
let reviews = []
let accepted = false
for (let round = 1; round <= maxReviewRounds; round++) {
  reviews = (await parallel(LENSES.map((lens, i) => () =>
    agent(`${CONTEXT}
심사 대상 원고: ${draft.file}
당신의 심사 관점: ${lens}
심사보고서를 ${ROOT}/research/reviews/round-${round}-referee-${i + 1}.md 에 저장하세요.`,
      { agentType: 'rp-peer-review-team', label: `리뷰R${round}:심사위원${i + 1}`, phase: '피어리뷰', schema: REVIEW_SCHEMA })
  ))).filter(Boolean)

  const positive = reviews.filter(r => r.verdict === 'ACCEPT' || r.verdict === 'MINOR_REVISION').length
  log(`리뷰 라운드 ${round}: ${reviews.map(r => r.verdict).join(' / ')} (긍정 ${positive}/${reviews.length})`)
  if (positive >= 2) { accepted = true; break }
  if (round === maxReviewRounds) break

  draft = await agent(`${CONTEXT}
피어 리뷰 결과를 반영하여 수정본을 ${ROOT}/research/paper/draft-v${round + 1}.md 에 작성하세요.
심사보고서: ${reviews.map(r => r.report_file).join(', ')}
주요 지적:
${reviews.flatMap(r => r.major_points).map(x => `- ${x}`).join('\n')}
변경 요약을 ${ROOT}/research/paper/changelog.md 에 누적 기록하세요.`,
    { agentType: 'rp-paper-writing-team', label: `논문:수정${round}`, phase: '피어리뷰', schema: FILE_SUMMARY_SCHEMA }) || draft
}

// ── 7. 후속연구 + 교신 ─────────────────────────────────────
phase('마무리')
const closing = (await parallel([
  () => agent(`${CONTEXT}
이번 사이클의 산출물(${ROOT}/research/ 전체)과 지식베이스를 채굴하여 후속연구 어젠다를
${ROOT}/research/agenda/future-research.md 에 작성/갱신하세요.`,
    { agentType: 'rp-future-research-team', label: '후속연구:어젠다', phase: '마무리', schema: FILE_SUMMARY_SCHEMA }),
  () => agent(`${CONTEXT}
최종 원고: ${draft.file}
피어 리뷰 보고서: ${reviews.map(r => r.report_file).join(', ') || '(없음)'}
${ROOT}/research/correspondence/ 에 (1) 목표 저널 투고 커버레터, (2) 심사위원 대응문(response to referees)을 작성하세요.
대응문은 논문 changelog와 대조하여 실제 수정 내역과 일치해야 합니다.`,
    { agentType: 'rp-correspondence-team', label: '교신:커버레터+대응문', phase: '마무리', schema: FILE_SUMMARY_SCHEMA }),
])).filter(Boolean)

return {
  question,
  brief: brief.brief_file,
  methodology_spec: judged.spec_file,
  validation_verdict: validationVerdict,
  final_draft: draft.file,
  review_verdicts: reviews.map(r => r.verdict),
  internally_accepted: accepted,
  closing_outputs: closing.map(c => c.file),
}
