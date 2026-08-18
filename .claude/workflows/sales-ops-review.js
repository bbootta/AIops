export const meta = {
  name: 'sales-ops-review',
  description: '세일즈 운영 리듬: weekly 모드는 주간 전체 점검(지표, 시그널, 파이프라인 위생, 격주 회고, 규제 캘린더), daily 모드는 캠페인 활성 기간의 경량 집중 점검(도달 지표, 서킷브레이커 판정, suppression 델타, 답장 분류, 터치 릴리스 게이트). 캠페인 개시와 볼륨 증량 후 3일간 daily 모드는 필수다(KB02 §6.2)',
  whenToUse: '주간 운영 점검 또는 캠페인 활성 기간 일간 점검(터치 2~N 릴리스 게이트 판정 포함) 시. args: { date: "YYYY-MM-DD", mode: "daily | weekly"(기본 weekly), campaigns: "활성 캠페인 ID 목록(daily 모드 필수)" }',
  phases: [
    { title: '지표 점검', detail: 'deliverability-engineer: 도달 지표와 서킷브레이커 판정, daily는 터치 릴리스 기술 파트(도구 동기화/잔여 한도/직전 터치 지표), weekly는 블랙리스트/Postmaster/웜업 추가' },
    { title: '답장 분류', detail: 'sales-ops-analyst: daily는 답장 로그 분류와 시퀀스 제외 목록 갱신, weekly는 3층 지표 리포트와 파이프라인 위생, 격주 회고 초안' },
    { title: '컴플라이언스 점검', detail: 'sales-compliance-officer: daily는 suppression 델타 재대조와 동기화 정합성, weekly는 수신거부 로그 감사와 EU 보관기간, 규제 모니터링' },
    { title: '시그널 스캔', detail: 'prospect-researcher: weekly만, 시그널 스캔과 티어 상향 후보' },
    { title: '운영 브리프', detail: 'sales-lead: daily는 터치 릴리스 가능/차단 현황과 서킷브레이커 발동 여부 즉시 보고, weekly는 PO가 이번 주 할 일 최상단 브리프' },
  ],
}

const DATE = args && args.date ? args.date : ''
const MODE = args && args.mode ? String(args.mode) : 'weekly'
const CAMPAIGNS = args && Array.isArray(args.campaigns) ? args.campaigns : (args && args.campaigns ? [args.campaigns] : [])
if (!DATE || !/^\d{4}-\d{2}-\d{2}$/.test(DATE)) throw new Error('args.date가 필요합니다: YYYY-MM-DD 형식')
if (MODE !== 'daily' && MODE !== 'weekly') throw new Error('args.mode는 daily 또는 weekly여야 합니다')
if (MODE === 'daily' && !CAMPAIGNS.length) throw new Error('daily 모드는 args.campaigns(활성 캠페인 ID 목록)가 필수입니다')

const DAILY = MODE === 'daily'
const COMP_DIR = 'docs/sales/compliance'
const REPORT_FILE = 'reports/sales/' + DATE + (DAILY ? '-daily-ops.md' : '-weekly-ops.md')
const CAMPAIGN_LIST = CAMPAIGNS.length ? CAMPAIGNS.join(', ') : '(활성 캠페인 목록은 docs/sales/campaigns/ 와 docs/sales/outbox/ 에서 파악)'

const METRICS_SCHEMA = {
  type: 'object', required: ['circuit_breaker', 'breaches', 'tool_autostop_confirmed', 'campaign_checks', 'record_file', 'summary'],
  properties: {
    circuit_breaker: { type: 'string', enum: ['정상', '발동'], description: '바운스율 2% 초과, 신고율 0.1% 이상, 배치율 85% 미만, 블랙리스트 등재 중 하나라도 발생하면 발동' },
    breaches: { type: 'array', items: { type: 'string' }, description: '임계 초과 항목(발동 사유). 정상이면 빈 배열' },
    tool_autostop_confirmed: { type: 'boolean', description: '발송 도구의 자동 중단 규칙 작동/설정 확인 여부' },
    campaign_checks: {
      type: 'array',
      items: {
        type: 'object', required: ['campaign_id', 'tech_release', 'reasons'],
        properties: {
          campaign_id: { type: 'string' },
          tech_release: { type: 'string', enum: ['PASS', 'FAIL'], description: '터치 릴리스 기술 파트: 도구 suppression 동기화, 잔여 일일 한도, 직전 터치 지표 이상 여부' },
          reasons: { type: 'string', description: 'FAIL 사유 또는 PASS 근거' },
        },
      },
      description: '캠페인별 기술 파트 판정(daily). weekly는 빈 배열 가능',
    },
    record_file: { type: 'string', description: '점검 기록 파일 경로' },
    summary: { type: 'string' },
  },
}

const ANALYST_SCHEMA = {
  type: 'object', required: ['record_file', 'optout_count', 'excluded_records', 'retro_file', 'summary'],
  properties: {
    record_file: { type: 'string', description: 'daily: 답장 분류 기록, weekly: 3층 지표 리포트 파일 경로' },
    optout_count: { type: 'integer', description: '수신거부성 회신 건수(즉시 sales-compliance-officer 전달 대상)' },
    excluded_records: { type: 'array', items: { type: 'string' }, description: '시퀀스 제외 목록에 새로 기록한 수신자(답장자/수신거부자)' },
    retro_file: { type: 'string', description: 'weekly 격주 회고 초안 경로(해당 없으면 빈 문자열)' },
    summary: { type: 'string' },
  },
}

const COMPLIANCE_SCHEMA = {
  type: 'object', required: ['campaign_checks', 'optout_sla_ok', 'record_file', 'summary'],
  properties: {
    campaign_checks: {
      type: 'array',
      items: {
        type: 'object', required: ['campaign_id', 'compliance_release', 'reasons'],
        properties: {
          campaign_id: { type: 'string' },
          compliance_release: { type: 'string', enum: ['PASS', 'FAIL'], description: '터치 릴리스 컴플라이언스 파트: suppression 델타 재대조, 수신거부/답장/하드바운스/신고 레코드의 전 채널 시퀀스 제외 확인' },
          reasons: { type: 'string' },
        },
      },
      description: '캠페인별 컴플라이언스 파트 판정(daily). weekly는 빈 배열 가능',
    },
    optout_sla_ok: { type: 'boolean', description: '수신거부 처리 시한(목표 24시간) 준수 여부' },
    record_file: { type: 'string', description: '점검 기록 파일 경로' },
    summary: { type: 'string' },
  },
}

const SIGNAL_SCHEMA = {
  type: 'object', required: ['scan_file', 'tier_up_candidates', 'summary'],
  properties: {
    scan_file: { type: 'string', description: '시그널 스캔 결과 파일 경로' },
    tier_up_candidates: { type: 'array', items: { type: 'string' }, description: '티어 상향 후보 계정과 근거 시그널' },
    summary: { type: 'string' },
  },
}

const BRIEF_SCHEMA = {
  type: 'object', required: ['brief_file', 'headline'],
  properties: {
    brief_file: { type: 'string', description: '저장한 브리프 파일 경로' },
    headline: { type: 'string', description: 'PO에게 전할 핵심 3문장' },
  },
}

log('세일즈 운영 리뷰 시작: ' + MODE + ' / ' + DATE + (DAILY ? ' / 캠페인: ' + CAMPAIGN_LIST : ''))

// ── 1. 지표 점검 ─────────────────────────────────────────────
const metrics = await agent([
  '도달 지표를 점검하고 서킷브레이커를 판정하라. 시작 전에 kb/sales/02-deliverability.md를 읽어라.',
  '[모드] ' + MODE + ' / [기준일] ' + DATE,
  '[대상 캠페인] ' + CAMPAIGN_LIST + ' (각 캠페인의 docs/sales/campaigns/<ID>/campaign-record.md 와 발송 도구 지표 기록을 Read로 확인)',
  '',
  '[공통] 바운스율, 스팸 신고율, 인박스 배치율, 답장률 추세를 점검하라.',
  '서킷브레이커 판정 기준(하나라도 발생 시 발동): 바운스율 2% 초과, 신고율 0.1% 이상, 배치율 85% 미만, 블랙리스트 등재.',
  '발동 시: (1) 즉시 PO 중단 실행 요청을 기록의 최상단에 명기하고, (2) 발송 도구 자동 중단 규칙 작동 여부를 확인하고, (3) templates/sales/deliverability-runbook.md의 사고 대응 절차를 개시하라. 재개 조건은 원인 제거 확인 + PO 승인이다.',
  '',
  DAILY
    ? [
      '[daily] 터치 릴리스 게이트의 기술 파트를 캠페인별로 판정하라(campaign_checks):',
      '- 발송 도구 suppression 동기화 상태(마스터 리스트와 양방향)',
      '- 잔여 일일 한도(메일박스별)',
      '- 직전 터치 지표 이상 여부(바운스/신고/배치 급변)',
      '하나라도 미충족이면 해당 캠페인 tech_release는 FAIL이다.',
    ].join('\n')
    : [
      '[weekly 추가] 블랙리스트 조회, Google Postmaster Compliance Status, 발신 계정 웜업 상태(백그라운드 웜업 유지 포함)를 점검하라. campaign_checks는 빈 배열로 둬도 된다.',
    ].join('\n'),
  '',
  '점검 기록을 reports/sales/' + DATE + '-deliverability-check.md 에 저장하라.',
].join('\n'), { label: 'deliverability:지표', phase: '지표 점검', agentType: 'deliverability-engineer', schema: METRICS_SCHEMA })

if (!metrics) throw new Error('지표 점검 실패')
log('지표: 서킷브레이커 ' + metrics.circuit_breaker + (metrics.breaches.length ? ' (' + metrics.breaches.join('; ') + ')' : ''))

// ── 2. 답장 분류 / 지표 리포트 ───────────────────────────────
const analyst = await agent([
  DAILY ? '답장 로그를 분류하고 시퀀스 제외 목록을 갱신하라.' : '주간 3층 지표 리포트를 작성하라.',
  '시작 전에 kb/sales/07-sales-team-ops.md, kb/sales/01-cold-email-craft.md, kb/sales/08-oneline-ai-context.md를 읽어라.',
  '[모드] ' + MODE + ' / [기준일] ' + DATE + ' / [대상 캠페인] ' + CAMPAIGN_LIST,
  '[지표 점검 결과] ' + metrics.record_file + ' (Read로 읽을 것)',
  '',
  DAILY
    ? [
      '[daily]',
      '- 답장 로그를 긍정/부정/OOO/수신거부성 회신으로 분류하라.',
      '- 수신거부성 회신은 sales-compliance-officer 즉시 전달 대상으로 표시하고(다음 단계가 처리), 답장자 전원을 시퀀스 제외 목록에 기록하라.',
      '- 분류 결과와 제외 목록 갱신분을 터치 릴리스 게이트 판정에 쓸 수 있게 캠페인별로 정리하라.',
      '- 긍정 답장은 deal-support 워크플로 후보로 표시하라.',
      '분류 기록을 reports/sales/' + DATE + '-reply-log.md 에 저장하라. retro_file은 빈 문자열로 둬라.',
    ].join('\n')
    : [
      '[weekly]',
      '- 3층 지표(활동/파이프라인/결과) 주간 리포트를 작성하고 벤치마크와 대조하라. 성과 판정은 발송량이 아니라 긍정 답장과 기회 생성 기준이다.',
      '- 파이프라인 위생 플래그: 다음 단계 없는 딜, 정체 딜, 싱글스레드 딜, PO 판정 대기 기회를 표시하라.',
      '- 격주 회고 주기에 해당하는 캠페인이 있으면 templates/sales/campaign-retro.md 구조로 회고 초안(가설-셋업-결과-판정 권고-배운 것)을 reports/sales/' + DATE + '-campaign-retro.md 에 작성하라(확대/폐기 최종 판정은 PO). 해당 없으면 retro_file은 빈 문자열.',
      '- A/B 실험 로그를 갱신하고 KB08 "확인 필요" 항목의 창업팀 확인 추적 상태를 기록하라.',
      '리포트를 reports/sales/' + DATE + '-weekly-metrics.md 에 저장하라.',
    ].join('\n'),
].join('\n'), { label: 'ops:' + (DAILY ? '답장분류' : '지표리포트'), phase: '답장 분류', agentType: 'sales-ops-analyst', schema: ANALYST_SCHEMA })

if (!analyst) throw new Error('답장 분류/지표 리포트 실패')
log((DAILY ? '답장 분류' : '주간 리포트') + ' 완료: 수신거부성 ' + analyst.optout_count + '건, 신규 제외 ' + analyst.excluded_records.length + '건')

// ── 3. 컴플라이언스 점검 ─────────────────────────────────────
const compliance = await agent([
  DAILY ? 'suppression 델타를 재대조하고 터치 릴리스 게이트의 컴플라이언스 파트를 판정하라.' : '주간 컴플라이언스 감사를 수행하라.',
  '시작 전에 kb/sales/09-global-outreach-compliance.md, kb/sales/06-kr-outreach-compliance.md, kb/sales/02-deliverability.md를 읽어라.',
  '[모드] ' + MODE + ' / [기준일] ' + DATE + ' / [대상 캠페인] ' + CAMPAIGN_LIST,
  '[답장 분류 결과] ' + analyst.record_file + ' (Read로 읽을 것. 수신거부성 회신 ' + analyst.optout_count + '건, 신규 제외 ' + analyst.excluded_records.length + '건)',
  '',
  DAILY
    ? [
      '[daily] 캠페인별로 판정하라(campaign_checks):',
      '- suppression 델타 재대조: 마스터 suppression 리스트 갱신분(수신거부/답장/하드바운스/스팸 신고)이 발송 큐에 반영됐는지, 해당 수신자가 전 채널 시퀀스(이메일 + LinkedIn/전화 슬롯)에서 제외됐는지 확인하라. 수신거부자 후속 발송이 최다 사고 유형이다(KB09 게이트 C).',
      '- 발송 도구 suppression 동기화 정합성을 확인하라.',
      '- 수신거부 처리 시한(목표 24시간) 준수를 점검하라.',
      '하나라도 미충족이면 해당 캠페인 compliance_release는 FAIL이다(fail-closed).',
      '점검 기록을 ' + COMP_DIR + '/' + DATE + '-suppression-delta.md 에 저장하라.',
    ].join('\n')
    : [
      '[weekly]',
      '- 수신거부 처리 로그를 감사하라(처리 시한, 해시 보관, 우회 없음).',
      '- EU 프로스펙트 보관기간(마지막 접촉 3년) 만료 도래 레코드를 찾아 삭제/익명화를 지시하고 기록하라.',
      '- 규제 개정 모니터링: 분기 주기에 해당하면 KISA 안내서, DUAA 하위 규정, 미국 주법 판결 등을 심층 점검하고 KB 갱신 제안을 남겨라. legal-team 에스컬레이션이 필요한 사안은 질의로 정리하라.',
      '감사 기록을 ' + COMP_DIR + '/' + DATE + '-weekly-audit.md 에 저장하라. campaign_checks는 빈 배열로 둬도 된다.',
    ].join('\n'),
].join('\n'), { label: 'compliance:' + (DAILY ? '델타' : '감사'), phase: '컴플라이언스 점검', agentType: 'sales-compliance-officer', schema: COMPLIANCE_SCHEMA })

if (!compliance) throw new Error('컴플라이언스 점검 실패')

// ── 4. 시그널 스캔 (weekly만) ────────────────────────────────
let signals = null
if (!DAILY) {
  signals = await agent([
    '주간 시그널 스캔을 수행하라. 시작 전에 kb/sales/03-prospecting-icp.md, kb/sales/08-oneline-ai-context.md를 읽어라.',
    '[기준일] ' + DATE,
    '- 신규 채용공고, 펀딩, 임원 이동, 챔피언 이직, 금융사 RFP/사전규격 공고를 웹으로 스캔하라. 모든 시그널에 출처와 확인일을 붙여라.',
    '- 시그널 기반 티어 상향 후보 목록을 근거와 함께 제시하라(티어 배정 승인은 sales-lead 경유 PO).',
    '스캔 결과를 reports/sales/' + DATE + '-signal-scan.md 에 저장하라.',
  ].join('\n'), { label: 'researcher:시그널', phase: '시그널 스캔', agentType: 'prospect-researcher', schema: SIGNAL_SCHEMA })
  if (!signals) throw new Error('시그널 스캔 실패')
  log('시그널 스캔: 티어 상향 후보 ' + signals.tier_up_candidates.length + '건')
}

// ── 터치 릴리스 게이트 종합 판정 (daily, fail-closed) ────────
// 기술 파트(deliverability)와 컴플라이언스 파트가 모두 PASS이고 서킷브레이커 미발동일 때만 릴리스 가능.
// 판정 기록이 없는 캠페인은 차단이다.
let touchRelease = null
if (DAILY) {
  touchRelease = CAMPAIGNS.map(id => {
    const tech = (metrics.campaign_checks || []).filter(c => c.campaign_id === id)[0]
    const comp = (compliance.campaign_checks || []).filter(c => c.campaign_id === id)[0]
    const pass = metrics.circuit_breaker !== '발동'
      && !!tech && tech.tech_release === 'PASS'
      && !!comp && comp.compliance_release === 'PASS'
    return {
      campaign_id: id,
      verdict: pass ? 'PASS' : '차단',
      tech: tech ? tech.tech_release + ' (' + tech.reasons + ')' : '판정 없음(차단)',
      compliance: comp ? comp.compliance_release + ' (' + comp.reasons + ')' : '판정 없음(차단)',
      circuit_breaker: metrics.circuit_breaker,
    }
  })
  log('터치 릴리스: ' + touchRelease.map(r => r.campaign_id + '=' + r.verdict).join(', '))
}

// ── 5. 운영 브리프 ───────────────────────────────────────────
const brief = await agent([
  DAILY ? '일간 운영 브리프를 작성하고 터치 릴리스 판정을 기록하라.' : '주간 운영 브리프를 작성하라.',
  '[모드] ' + MODE + ' / [기준일] ' + DATE,
  '[입력(전부 Read로 읽을 것)]',
  '- 지표 점검: ' + metrics.record_file + ' (서킷브레이커: ' + metrics.circuit_breaker + ')',
  '- ' + (DAILY ? '답장 분류' : '주간 리포트') + ': ' + analyst.record_file,
  '- 컴플라이언스: ' + compliance.record_file,
  signals ? '- 시그널 스캔: ' + signals.scan_file : '',
  '',
  DAILY
    ? [
      '[daily 브리프 요구사항]',
      '1) 터치 릴리스 판정을 캠페인별로 templates/sales/touch-release-checklist.md 구조에 따라 ' + COMP_DIR + '/' + DATE + '-touch-release-<캠페인ID>.md 에 기록하라. 아래 종합 판정을 그대로 기록하고, PASS 기록이 없는 터치는 발송 불가임을 명기하라(fail-closed):',
      JSON.stringify(touchRelease),
      '2) 브리프 최상단에 서킷브레이커 발동 여부를 배치하라. 발동이면 "PO 즉시 실행: 발송 중단"을 첫 줄에 쓰고 런북 절차와 재개 조건(원인 제거 + PO 승인)을 요약하라.',
      '3) 터치 릴리스 가능/차단 현황, 수신거부 처리 현황, 긍정 답장(딜 지원 후보)을 PO에 보고하라.',
    ].join('\n')
    : [
      '[weekly 브리프 요구사항]',
      '1) 최상단에 "PO가 이번 주 할 일"을 배치하라: 미팅, LinkedIn/전화 터치 캘린더, 승인 대기 발송 패키지(docs/sales/outbox/ 확인), ICP/자격검증/LIA 등 의사결정 필요 항목.',
      '2) 이어서 지표 요약, 파이프라인 위생 플래그, 컴플라이언스 감사 결과, 시그널/티어 상향 후보, 격주 회고(있으면) 순으로 종합하라.',
      '3) PO 의사결정 큐(승인 대기 항목 목록)를 갱신해 브리프에 포함하라.',
    ].join('\n'),
  '',
  '브리프를 ' + REPORT_FILE + ' 에 저장하라.',
].join('\n'), { label: 'lead:브리프', phase: '운영 브리프', agentType: 'sales-lead', schema: BRIEF_SCHEMA })

if (!brief) throw new Error('운영 브리프 작성 실패')
log('운영 브리프 완료: ' + brief.brief_file)

return {
  status: metrics.circuit_breaker === '발동' ? 'circuit_breaker_fired' : 'ok',
  mode: MODE,
  date: DATE,
  circuit_breaker: { state: metrics.circuit_breaker, breaches: metrics.breaches, tool_autostop_confirmed: metrics.tool_autostop_confirmed },
  touch_release: touchRelease,
  artifacts: {
    brief: brief.brief_file,
    deliverability_check: metrics.record_file,
    reply_or_metrics: analyst.record_file,
    compliance_record: compliance.record_file,
    signal_scan: signals ? signals.scan_file : null,
    retro: analyst.retro_file || null,
    touch_release_records: DAILY ? CAMPAIGNS.map(id => COMP_DIR + '/' + DATE + '-touch-release-' + id + '.md') : null,
  },
  headline: brief.headline,
  po_todo: [
    metrics.circuit_breaker === '발동' ? '[긴급] 발송 즉시 중단 실행(런북: templates/sales/deliverability-runbook.md 절차). 재개는 원인 제거 확인 + PO 승인 필요' : '',
    DAILY && touchRelease ? '터치 릴리스 차단 캠페인 확인: ' + (touchRelease.filter(r => r.verdict !== 'PASS').map(r => r.campaign_id).join(', ') || '없음(전부 PASS)') : '',
    DAILY ? '긍정 답장 후속 처리(deal-support 실행 여부 결정): ' + analyst.record_file + ' 참조' : '',
    !DAILY ? '브리프 최상단 "PO가 이번 주 할 일" 확인: ' + brief.brief_file : '',
    !DAILY && analyst.retro_file ? '격주 회고 확대/폐기 판정: ' + analyst.retro_file : '',
    !DAILY && signals && signals.tier_up_candidates.length ? '티어 상향 후보 승인: ' + signals.tier_up_candidates.join(' | ') : '',
    !compliance.optout_sla_ok ? '수신거부 처리 지연 확인(24시간 목표 미달): ' + compliance.record_file : '',
  ].filter(Boolean),
}
