export const meta = {
  name: 'legal-consult',
  description: '법률자문: 질의를 쟁점으로 분해하고 법령·판례·전문가 검토 후 반대검증을 거쳐 의견서를 작성',
  whenToUse: '법률 질의/자문 요청 시. args: { question: "질의 내용", context: "배경 사실(선택)" }',
  phases: [
    { title: '쟁점 정리', detail: 'legal-lead가 쟁점 분해와 검토 계획 수립' },
    { title: '조사', detail: '쟁점별로 법령·판례·영역 전문가 병렬 조사' },
    { title: '종합', detail: 'legal-lead가 쟁점별 결론 종합' },
    { title: '반대검증', detail: 'legal-red-team 품질 게이트' },
    { title: '의견서 작성', detail: 'legal-writer가 reports/legal/에 저장' },
  ],
}

const QUESTION = args && args.question ? args.question : ''
const CONTEXT = args && args.context ? args.context : '(추가 배경 없음)'
if (!QUESTION) throw new Error('args.question이 필요합니다: 자문 질의 내용')

const DOMAIN_AGENT = {
  corporate: 'legal-corporate-advisor',
  compliance: 'legal-compliance-officer',
  labor: 'legal-labor-advisor',
  ip_tech: 'legal-ip-tech-advisor',
  litigation: 'legal-litigation-strategist',
  international: 'legal-international-counsel',
  contract: 'legal-contract-reviewer',
  civil: null, // 법령·판례 조사로 충분
}

const ISSUES_SCHEMA = {
  type: 'object', required: ['summary', 'issues', 'facts_needed'],
  properties: {
    summary: { type: 'string', description: '사안 요지와 의뢰인 지위' },
    issues: {
      type: 'array', maxItems: 6,
      items: {
        type: 'object', required: ['id', 'title', 'domain', 'severity', 'research_notes'],
        properties: {
          id: { type: 'integer' },
          title: { type: 'string' },
          domain: { type: 'string', enum: ['corporate', 'compliance', 'labor', 'ip_tech', 'litigation', 'international', 'contract', 'civil'] },
          severity: { type: 'string', enum: ['치명', '중대', '경미'] },
          research_notes: { type: 'string', description: '이 쟁점에서 조사할 것' },
        },
      },
    },
    facts_needed: { type: 'array', items: { type: 'string' }, description: '추가 확인이 필요한 사실' },
  },
}

const FINDING_SCHEMA = {
  type: 'object', required: ['conclusion', 'basis', 'caveats'],
  properties: {
    conclusion: { type: 'string', description: '이 관점에서의 결론' },
    basis: { type: 'array', items: { type: 'string' }, description: '근거(조문/판례 — 검증된 것만, 미확인은 [사건번호 미확인])' },
    caveats: { type: 'array', items: { type: 'string' } },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', required: ['verdict', 'reason', 'fixes'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'PASS_WITH_FIXES', 'FAIL'] },
    reason: { type: 'string' },
    fixes: { type: 'array', items: { type: 'string' }, description: '반영해야 할 수정사항' },
  },
}

log('법률자문 워크플로 시작')

const plan = await agent([
  '다음 법률 질의의 쟁점을 정리하라. kb/legal/00-index.md에서 관련 KB를 찾아 읽고 시작하라.',
  '[질의] ' + QUESTION,
  '[배경] ' + CONTEXT,
  '쟁점은 6개 이하로, 각 쟁점에 가장 적합한 영역(domain)과 심각도를 매겨라.',
].join('\n'), { label: 'lead:쟁점정리', phase: '쟁점 정리', agentType: 'legal-lead', schema: ISSUES_SCHEMA })

log('쟁점 ' + plan.issues.length + '개 식별: ' + plan.issues.map(i => i.title).join(' / '))

const researched = await pipeline(
  plan.issues,
  issue => {
    const base = [
      '[사안] ' + plan.summary,
      '[질의] ' + QUESTION,
      '[배경] ' + CONTEXT,
      '[담당 쟁점] ' + issue.title + ' (심각도: ' + issue.severity + ')',
      '[조사 지침] ' + issue.research_notes,
      'kb/legal/00-index.md에서 관련 KB 문서를 먼저 읽고, 최신 변경 가능성이 있는 부분만 웹으로 보강하라.',
    ].join('\n')
    const jobs = [
      () => agent(base + '\n이 쟁점에 적용되는 법령과 조문을 확인하라.', { label: 'statute:쟁점' + issue.id, phase: '조사', agentType: 'legal-statute-researcher', schema: FINDING_SCHEMA }),
      () => agent(base + '\n이 쟁점의 확립 법리와 최신 판례를 조사하라. 사건번호는 실재 확인된 것만.', { label: 'case:쟁점' + issue.id, phase: '조사', agentType: 'legal-case-researcher', schema: FINDING_SCHEMA }),
    ]
    const expert = DOMAIN_AGENT[issue.domain]
    if (expert) {
      jobs.push(() => agent(base + '\n전문 영역 관점에서 이 쟁점을 실무적으로 검토하라.', { label: issue.domain + ':쟁점' + issue.id, phase: '조사', agentType: expert, schema: FINDING_SCHEMA }))
    }
    return parallel(jobs).then(r => ({ issue: issue, findings: r.filter(Boolean) }))
  },
)

const findingsText = researched.filter(Boolean).map(r => [
  '### 쟁점 ' + r.issue.id + ': ' + r.issue.title + ' [' + r.issue.severity + ']',
  r.findings.map(f => '- 결론: ' + f.conclusion + '\n  근거: ' + f.basis.join('; ') + '\n  유의: ' + f.caveats.join('; ')).join('\n'),
].join('\n')).join('\n\n')

let synthesis = await agent([
  '전문가 조사 결과를 종합해 쟁점별 최종 결론을 내려라. 결론 간 모순이 있으면 해소하고, 리스크 등급과 권고 조치를 확정하라.',
  '[질의] ' + QUESTION,
  '[사안 요지] ' + plan.summary,
  '[추가 확인 필요 사실] ' + plan.facts_needed.join('; '),
  '', '[조사 결과]', findingsText,
  '', '최종 텍스트로 종합 검토 의견 전문을 반환하라(쟁점별 결론, 근거, 리스크 등급, 권고, 전제와 한계 포함).',
].join('\n'), { label: 'lead:종합', phase: '종합', agentType: 'legal-lead' })

let verdict = await agent([
  '아래 법률자문 결론을 반대검증하라. 인용 표본 검증, 반대논거 구성, 누락 쟁점 점검을 수행하라.',
  '[질의] ' + QUESTION, '', synthesis,
].join('\n'), { label: 'red-team', phase: '반대검증', agentType: 'legal-red-team', schema: VERDICT_SCHEMA })

if (verdict.verdict !== 'PASS') {
  log('반대검증: ' + verdict.verdict + ' — 수정 반영 후 재작성')
  synthesis = await agent([
    '반대검증에서 다음 지적이 나왔다. 지적을 반영해 종합 의견을 수정하라. 지적이 타당하지 않으면 반박 근거를 명시하고 유지하라.',
    '[지적사항] ' + verdict.fixes.join(' | '),
    '[사유] ' + verdict.reason,
    '', '[기존 의견]', synthesis,
  ].join('\n'), { label: 'lead:수정', phase: '반대검증', agentType: 'legal-lead' })
}

const report = await agent([
  'templates/legal/legal-opinion.md 구조에 따라 법률자문의견서를 완성해 reports/legal/에 저장하라.',
  '파일명: 오늘 날짜와 주제로 YYYY-MM-DD-{주제-슬러그}.md',
  '반대검증 판정: ' + verdict.verdict,
  '[질의] ' + QUESTION,
  '[종합 의견 — 이 내용만 사용하고 인용을 새로 만들지 말 것]',
  synthesis,
  '', '저장 경로와 3문장 요지를 반환하라.',
].join('\n'), { label: 'writer:의견서', phase: '의견서 작성', agentType: 'legal-writer' })

return { plan: plan, verdict: verdict, report: report }
