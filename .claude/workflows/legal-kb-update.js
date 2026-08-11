export const meta = {
  name: 'legal-kb-update',
  description: 'KB 갱신: 선택한 분야의 KB 문서를 최신 법령·판례로 재조사해 갱신하고 검증',
  whenToUse: '분기별 또는 큰 입법·판례 이벤트 후 KB 갱신 시. args: { date: "YYYY-MM-DD(오늘)", topics: ["kr-corporate", ...] (생략 시 전체 13개) }',
  phases: [
    { title: '갱신', detail: '분야별로 기존 KB를 읽고 변경사항 반영' },
    { title: '검증', detail: '갱신 내용의 인용·시행일 재검증' },
  ],
}

const DATE = args && args.date ? args.date : null
if (!DATE) throw new Error('args.date가 필요합니다: 오늘 날짜 YYYY-MM-DD (워크플로 안에서는 현재 시각을 알 수 없음)')

const ROOT = '/home/user/AIops'
const ALL = {
  'kr-legal-system': ROOT + '/kb/legal/kr/01-legal-system.md',
  'kr-civil': ROOT + '/kb/legal/kr/02-civil-law.md',
  'kr-corporate': ROOT + '/kb/legal/kr/03-corporate-law.md',
  'kr-criminal': ROOT + '/kb/legal/kr/04-criminal-law.md',
  'kr-labor': ROOT + '/kb/legal/kr/05-labor-law.md',
  'kr-fair-trade': ROOT + '/kb/legal/kr/06-fair-trade.md',
  'kr-privacy-data': ROOT + '/kb/legal/kr/07-privacy-data-ai.md',
  'kr-finance': ROOT + '/kb/legal/kr/08-finance-securities.md',
  'kr-ip': ROOT + '/kb/legal/kr/09-ip.md',
  'kr-tax-admin': ROOT + '/kb/legal/kr/10-tax-admin.md',
  'global-us': ROOT + '/kb/legal/global/11-us-law.md',
  'global-eu-asia': ROOT + '/kb/legal/global/12-eu-asia-law.md',
  'global-intl': ROOT + '/kb/legal/global/13-intl-trade-arbitration.md',
}

const keys = args && Array.isArray(args.topics) && args.topics.length ? args.topics : Object.keys(ALL)
const bad = keys.filter(k => !ALL[k])
if (bad.length) throw new Error('알 수 없는 분야: ' + bad.join(', ') + ' (가능: ' + Object.keys(ALL).join(', ') + ')')

const UPDATE_SCHEMA = {
  type: 'object', required: ['file', 'changes_applied', 'no_change_reason'],
  properties: {
    file: { type: 'string' },
    changes_applied: { type: 'array', items: { type: 'string' }, description: '반영한 변경사항(없으면 빈 배열)' },
    no_change_reason: { type: 'string', description: '변경이 없으면 그 판단 근거' },
  },
}

const VERIFY_SCHEMA = {
  type: 'object', required: ['file', 'claims_checked', 'corrections'],
  properties: {
    file: { type: 'string' },
    claims_checked: { type: 'integer' },
    corrections: { type: 'array', items: { type: 'string' } },
  },
}

log('KB 갱신 시작: ' + keys.length + '개 분야')

const results = await pipeline(
  keys,
  k => agent([
    '법무 KB 문서를 최신 상태로 갱신하라.',
    '[대상 파일] ' + ALL[k] + ' (Read로 읽을 것)',
    '[오늘 날짜] ' + DATE,
    '절차:',
    '1) 문서의 "최종 갱신" 날짜 이후 이 분야의 법 개정(공포·시행), 대법원 전원합의체 판결, 주요 하위법령 제정을 WebSearch로 조사하라.',
    '2) 변경이 있으면 해당 섹션을 Edit로 수정하고, "최근 개정·입법 동향" 섹션을 갱신하라. 시행일과 부칙 적용례를 명시하라.',
    '3) 문서 헤더의 "최종 갱신" 날짜를 ' + DATE + '로 바꿔라(변경이 없어도 확인일 갱신).',
    '4) 사건번호·조문은 검색으로 확인된 것만 기재. 문서 전체를 다시 쓰지 말고 변경 부분만 수정하라.',
  ].join('\n'), { label: 'update:' + k, phase: '갱신', agentType: 'legal-statute-researcher', schema: UPDATE_SCHEMA }),
  (r, k) => {
    if (!r || !r.changes_applied || !r.changes_applied.length) return { update: r, verify: null }
    return agent([
      'KB 갱신 내용을 검증하라.',
      '[대상 파일] ' + ALL[k] + ' (Read로 읽을 것)',
      '[방금 반영된 변경] ' + r.changes_applied.join(' | '),
      '각 변경사항의 사실 여부(개정 내용, 시행일, 사건번호)를 WebSearch로 재확인하고, 틀린 것은 Edit로 바로잡아라.',
    ].join('\n'), { label: 'verify:' + k, phase: '검증', agentType: 'legal-case-researcher', schema: VERIFY_SCHEMA })
      .then(v => ({ update: r, verify: v }))
  },
)

const done = results.filter(Boolean)
return {
  updated: done.filter(d => d.update && d.update.changes_applied && d.update.changes_applied.length).map(d => d.update),
  unchanged: done.filter(d => d.update && (!d.update.changes_applied || !d.update.changes_applied.length)).map(d => d.update && d.update.file),
}
