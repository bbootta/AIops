export const meta = {
  name: 'contract-review',
  description: '계약검토: 조항 분석 → 전문 쟁점 심화검토 → 반대검증 → 계약검토보고서 작성',
  whenToUse: '계약서/약관/투자계약 검토 요청 시. args: { contract_path: "계약서 파일 경로", party: "의뢰인 지위(예: 을/수급인/매수인)", background: "거래 배경(선택)" }',
  phases: [
    { title: '조항 분석', detail: 'legal-contract-reviewer 전체 검토' },
    { title: '전문 검토', detail: '발견된 영역별 쟁점을 전문가가 심화 검토' },
    { title: '반대검증', detail: 'legal-red-team 품질 게이트' },
    { title: '보고서 작성', detail: 'legal-writer가 reports/legal/에 저장' },
  ],
}

const PATH = args && args.contract_path ? args.contract_path : ''
const PARTY = args && args.party ? args.party : ''
const BG = args && args.background ? args.background : '(추가 배경 없음)'
if (!PATH) throw new Error('args.contract_path가 필요합니다: 검토할 계약서 파일 경로')
if (!PARTY) throw new Error('args.party가 필요합니다: 의뢰인이 어느 당사자인지')

const DOMAIN_AGENT = {
  corporate: 'legal-corporate-advisor',
  compliance: 'legal-compliance-officer',
  labor: 'legal-labor-advisor',
  ip_tech: 'legal-ip-tech-advisor',
  international: 'legal-international-counsel',
  litigation: 'legal-litigation-strategist',
}

const REVIEW_SCHEMA = {
  type: 'object', required: ['overview', 'verdict', 'findings', 'missing_clauses', 'negotiation', 'specialist_domains'],
  properties: {
    overview: { type: 'string', description: '계약 구조와 리스크 배분 요약' },
    verdict: { type: 'string', enum: ['체결 가능', '수정 후 체결 가능', '재협상 필요', '체결 불가'] },
    findings: {
      type: 'array',
      items: {
        type: 'object', required: ['clause', 'issue', 'grade', 'fix'],
        properties: {
          clause: { type: 'string' },
          issue: { type: 'string' },
          grade: { type: 'string', enum: ['치명', '중대', '경미'] },
          fix: { type: 'string', description: '수정 문안' },
        },
      },
    },
    missing_clauses: { type: 'array', items: { type: 'string' } },
    negotiation: { type: 'string', description: '협상 전략 요지' },
    specialist_domains: {
      type: 'array', maxItems: 4,
      items: {
        type: 'object', required: ['domain', 'question'],
        properties: {
          domain: { type: 'string', enum: ['corporate', 'compliance', 'labor', 'ip_tech', 'international', 'litigation'] },
          question: { type: 'string', description: '전문가에게 넘길 구체 질문' },
        },
      },
      description: '심화 검토가 필요한 전문 영역 (없으면 빈 배열)',
    },
  },
}

const FINDING_SCHEMA = {
  type: 'object', required: ['conclusion', 'basis', 'clause_fixes'],
  properties: {
    conclusion: { type: 'string' },
    basis: { type: 'array', items: { type: 'string' } },
    clause_fixes: { type: 'array', items: { type: 'string' }, description: '추가/수정 권고 문안' },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', required: ['verdict', 'reason', 'fixes'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'PASS_WITH_FIXES', 'FAIL'] },
    reason: { type: 'string' },
    fixes: { type: 'array', items: { type: 'string' } },
  },
}

log('계약검토 시작: ' + PATH + ' (의뢰인 지위: ' + PARTY + ')')

const review = await agent([
  '계약서를 전체 검토하라.',
  '[계약서 파일] ' + PATH + ' (Read로 읽을 것)',
  '[의뢰인 지위] ' + PARTY,
  '[거래 배경] ' + BG,
  'kb/legal/kr/02-civil-law.md와 kb/legal/kr/06-fair-trade.md를 참조하고, 특별법(약관규제/하도급/가맹 등) 적용 여부를 점검하라.',
  '모든 지적에 수정 문안을 붙이고, 심화 검토가 필요한 전문 영역이 있으면 specialist_domains에 구체 질문과 함께 담아라.',
].join('\n'), { label: 'reviewer:전체검토', phase: '조항 분석', agentType: 'legal-contract-reviewer', schema: REVIEW_SCHEMA })

log('판정: ' + review.verdict + ' — 치명 ' + review.findings.filter(f => f.grade === '치명').length + '건, 중대 ' + review.findings.filter(f => f.grade === '중대').length + '건')

const specialist = await parallel(review.specialist_domains.map(d => () =>
  agent([
    '계약서의 전문 영역 쟁점을 심화 검토하라.',
    '[계약서 파일] ' + PATH + ' (Read로 읽을 것)',
    '[의뢰인 지위] ' + PARTY,
    '[질문] ' + d.question,
    '결론과 근거, 계약 문안 수정 권고를 반환하라.',
  ].join('\n'), { label: d.domain + ':심화', phase: '전문 검토', agentType: DOMAIN_AGENT[d.domain], schema: FINDING_SCHEMA })
    .then(f => ({ domain: d.domain, question: d.question, finding: f }))
))

const specialistText = specialist.filter(Boolean).map(s =>
  '### [' + s.domain + '] ' + s.question + '\n결론: ' + s.finding.conclusion + '\n근거: ' + s.finding.basis.join('; ') + '\n권고 문안: ' + s.finding.clause_fixes.join(' | ')
).join('\n\n')

const reviewText = [
  '판정: ' + review.verdict,
  '개요: ' + review.overview,
  '지적사항:',
  review.findings.map(f => '- [' + f.grade + '] ' + f.clause + ': ' + f.issue + ' → 수정안: ' + f.fix).join('\n'),
  '누락 조항: ' + review.missing_clauses.join('; '),
  '협상 전략: ' + review.negotiation,
  specialistText ? '\n[전문가 심화 검토]\n' + specialistText : '',
].join('\n')

const verdict = await agent([
  '아래 계약검토 결과를 반대검증하라. 특히: 지적이 의뢰인 지위(' + PARTY + ')에서 타당한가, 상대방이 수정안을 거부할 때의 대안이 있는가, 놓친 독소조항이나 교차 쟁점(조세·노동·개인정보 등)은 없는가.',
  '[계약서 파일] ' + PATH + ' (직접 Read로 대조할 것)',
  '', reviewText,
].join('\n'), { label: 'red-team', phase: '반대검증', agentType: 'legal-red-team', schema: VERDICT_SCHEMA })

const report = await agent([
  'templates/legal/contract-review-report.md 구조에 따라 계약검토보고서를 완성해 reports/legal/에 저장하라.',
  '파일명: 오늘 날짜와 계약명으로 YYYY-MM-DD-{계약명-슬러그}-review.md',
  '[의뢰인 지위] ' + PARTY,
  '[반대검증] ' + verdict.verdict + ' — 반영할 지적: ' + verdict.fixes.join(' | '),
  '[검토 결과 — 이 내용만 사용]',
  reviewText,
  '', '저장 경로와 3문장 요지를 반환하라.',
].join('\n'), { label: 'writer:보고서', phase: '보고서 작성', agentType: 'legal-writer' })

return { verdict: review.verdict, red_team: verdict, report: report }
