export const meta = {
  name: 'litigation-prep',
  description: '분쟁대응: 전략 수립 → 쟁점별 판례·법령 조사 → 상대방 시뮬레이션 → 전략메모 작성',
  whenToUse: '소송·분쟁·수사 대응 요청 시. args: { case_summary: "사안 설명", our_role: "우리 지위(원고/피고/피의자 등)", goal: "목표(선택)" }',
  phases: [
    { title: '전략 골격', detail: 'legal-litigation-strategist 초기 전략과 기간 체크' },
    { title: '조사', detail: '쟁점별 판례·법령 병렬 조사' },
    { title: '상대방 시뮬레이션', detail: 'legal-red-team이 상대방 최선 전략 구성' },
    { title: '전략 확정', detail: '시뮬레이션 반영해 전략 확정' },
    { title: '메모 작성', detail: 'legal-writer가 reports/legal/에 저장' },
  ],
}

const SUMMARY = args && args.case_summary ? args.case_summary : ''
const ROLE = args && args.our_role ? args.our_role : ''
const GOAL = args && args.goal ? args.goal : '(명시 안 됨 — 전략가가 후보 목표를 제시할 것)'
if (!SUMMARY) throw new Error('args.case_summary가 필요합니다: 분쟁 사안 설명')
if (!ROLE) throw new Error('args.our_role이 필요합니다: 우리 지위(원고/피고/피의자/신청인 등)')

const STRATEGY_SCHEMA = {
  type: 'object', required: ['deadlines', 'issues', 'strategy', 'evidence_plan', 'immediate_actions'],
  properties: {
    deadlines: { type: 'array', items: { type: 'string' }, description: '시효·불변기간·답변 기한 등 임박 기한 (최우선 확인)' },
    issues: {
      type: 'array', maxItems: 5,
      items: {
        type: 'object', required: ['id', 'title', 'our_position', 'research_notes'],
        properties: {
          id: { type: 'integer' },
          title: { type: 'string' },
          our_position: { type: 'string' },
          research_notes: { type: 'string', description: '판례·법령에서 확인할 것' },
        },
      },
    },
    strategy: { type: 'string', description: '트랙 선택(협상/조정/중재/소송)과 단계별 골격' },
    evidence_plan: { type: 'array', items: { type: 'string' } },
    immediate_actions: { type: 'array', items: { type: 'string' }, description: '보전처분·증거보전·시효중단 등 즉시 실행' },
  },
}

const FINDING_SCHEMA = {
  type: 'object', required: ['conclusion', 'basis', 'caveats'],
  properties: {
    conclusion: { type: 'string' },
    basis: { type: 'array', items: { type: 'string' }, description: '검증된 인용만, 미확인은 [사건번호 미확인]' },
    caveats: { type: 'array', items: { type: 'string' } },
  },
}

const SIM_SCHEMA = {
  type: 'object', required: ['opponent_strategy', 'attack_points', 'weaknesses', 'verdict'],
  properties: {
    opponent_strategy: { type: 'string', description: '상대방의 최선 전략' },
    attack_points: { type: 'array', items: { type: 'string' }, description: '우리에게 가장 아픈 공격 3개' },
    weaknesses: { type: 'array', items: { type: 'string' }, description: '우리 전략의 약점' },
    verdict: { type: 'string', enum: ['PASS', 'PASS_WITH_FIXES', 'FAIL'] },
  },
}

log('분쟁대응 워크플로 시작 (지위: ' + ROLE + ')')

const strategy = await agent([
  '분쟁 사안의 초기 전략을 수립하라. 임박 기한(시효·불변기간·답변서 기한) 확인이 최우선이다.',
  '[사안] ' + SUMMARY,
  '[우리 지위] ' + ROLE,
  '[목표] ' + GOAL,
  'kb/legal/kr/02-civil-law.md(민사절차), kb/legal/kr/04-criminal-law.md(형사 국면 시)를 참조하라.',
].join('\n'), { label: 'strategist:골격', phase: '전략 골격', agentType: 'legal-litigation-strategist', schema: STRATEGY_SCHEMA })

if (strategy.deadlines.length) log('⚠️ 임박 기한: ' + strategy.deadlines.join(' / '))

const researched = await pipeline(
  strategy.issues,
  issue => {
    const base = [
      '[사안] ' + SUMMARY,
      '[우리 지위] ' + ROLE,
      '[쟁점] ' + issue.title,
      '[우리 주장] ' + issue.our_position,
      '[조사 지침] ' + issue.research_notes,
    ].join('\n')
    return parallel([
      () => agent(base + '\n이 쟁점의 확립 법리, 유리한 판례와 불리한 판례를 모두 조사하라.', { label: 'case:쟁점' + issue.id, phase: '조사', agentType: 'legal-case-researcher', schema: FINDING_SCHEMA }),
      () => agent(base + '\n요건사실과 절차 규정(관할, 입증책임, 기간)을 확인하라.', { label: 'statute:쟁점' + issue.id, phase: '조사', agentType: 'legal-statute-researcher', schema: FINDING_SCHEMA }),
    ]).then(r => ({ issue: issue, findings: r.filter(Boolean) }))
  },
)

const caseText = researched.filter(Boolean).map(r => [
  '### 쟁점 ' + r.issue.id + ': ' + r.issue.title,
  '우리 주장: ' + r.issue.our_position,
  r.findings.map(f => '- ' + f.conclusion + '\n  근거: ' + f.basis.join('; ') + '\n  유의: ' + f.caveats.join('; ')).join('\n'),
].join('\n')).join('\n\n')

const sim = await agent([
  '너는 지금부터 상대방 측 대리인이다. 아래 사안에서 상대방(우리의 반대 당사자)의 최선 전략을 구성하고, 우리 전략의 약점을 공격하라.',
  '[사안] ' + SUMMARY,
  '[상대방이 공격할 대상 = 우리 지위] ' + ROLE,
  '[우리 전략 골격] ' + strategy.strategy,
  '', '[쟁점별 조사 결과]', caseText,
].join('\n'), { label: 'red-team:상대방', phase: '상대방 시뮬레이션', agentType: 'legal-red-team', schema: SIM_SCHEMA })

const finalStrategy = await agent([
  '상대방 시뮬레이션 결과를 반영해 최종 전략을 확정하라. 각 공격 포인트에 대한 대비책을 포함하라.',
  '[사안] ' + SUMMARY, '[우리 지위] ' + ROLE, '[목표] ' + GOAL,
  '[초기 전략] ' + strategy.strategy,
  '[즉시 실행] ' + strategy.immediate_actions.join('; '),
  '[임박 기한] ' + strategy.deadlines.join('; '),
  '', '[쟁점별 조사]', caseText,
  '', '[상대방 최선 전략] ' + sim.opponent_strategy,
  '[공격 포인트] ' + sim.attack_points.join(' | '),
  '[우리 약점] ' + sim.weaknesses.join(' | '),
  '', '최종 텍스트로 전략 전문을 반환하라(승소 전망, 예상 반박과 재반박, 단계별 로드맵, 즉시 실행 사항 포함).',
].join('\n'), { label: 'strategist:확정', phase: '전략 확정', agentType: 'legal-litigation-strategist' })

const report = await agent([
  'templates/legal/litigation-strategy-memo.md 구조에 따라 전략메모를 완성해 reports/legal/에 저장하라.',
  '파일명: 오늘 날짜로 YYYY-MM-DD-{사건-슬러그}-strategy.md',
  '[임박 기한 — 메모 상단에 강조] ' + strategy.deadlines.join('; '),
  '[전략 전문 — 이 내용만 사용]', finalStrategy,
  '', '저장 경로와 3문장 요지를 반환하라.',
].join('\n'), { label: 'writer:메모', phase: '메모 작성', agentType: 'legal-writer' })

return { deadlines: strategy.deadlines, simulation: sim, report: report }
