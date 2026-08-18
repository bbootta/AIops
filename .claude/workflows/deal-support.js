export const meta = {
  name: 'deal-support',
  description: '딜 지원: PO가 직접 수행하는 미팅/파일럿/제안/보안 심사의 전후방 지원. 요청 분류 → (필요 시) 계정 리서치 → 단계별 산출물 → 팩트체크 → PO 전달 패키지. 자격검증 최종 판정과 딜 전략 결정은 PO 몫이며 에이전트는 준비물, 채점 초안, 부검까지만 만든다',
  whenToUse: '미팅 준비/부검, 파일럿 헌장, ROI 케이스, 보안 설문 대응, 긍정 답장 후속 지원 요청 시. args: { account: "계정명", stage: "prep | debrief | pilot | proposal | security", ask: "구체 요청(예: 자체구축 반대논거 대응, ROI 케이스)", notes: "미팅 노트나 배경 정보(선택)", date: "YYYY-MM-DD(오늘)" }',
  phases: [
    { title: '요청 분류', detail: 'sales-lead: 단계와 산출물 정의, 계정 슬러그 확정, 담당 배정' },
    { title: '계정 리서치', detail: 'prospect-researcher: prep/proposal 시 계정 최신 시그널과 인물 리서치 갱신' },
    { title: '산출물 작성', detail: 'deal-strategist: 단계별 산출물(브리프/SPICED 채점 초안/파일럿 헌장/ROI 케이스/보안 패키지) 작성' },
    { title: '팩트체크', detail: 'outreach-qa: 대외 전달물 수치/주장 검증(KB08 등급 대조). 규제 해석 사안은 sales-compliance-officer 경유 legal-team 확인' },
    { title: '종합 전달', detail: 'sales-lead: PO가 직접 할 일 / PO 결정 대기 항목 / 에이전트가 준비한 것을 구분해 전달' },
  ],
}

const ACCOUNT = args && args.account ? args.account : ''
const STAGE = args && args.stage ? String(args.stage) : ''
const ASK = args && args.ask ? args.ask : ''
const NOTES = args && args.notes ? args.notes : '(추가 배경 없음)'
const DATE = args && args.date ? args.date : ''
if (!ACCOUNT) throw new Error('args.account가 필요합니다: 계정명')
if (['prep', 'debrief', 'pilot', 'proposal', 'security'].indexOf(STAGE) < 0) throw new Error('args.stage가 필요합니다: prep | debrief | pilot | proposal | security')
if (!ASK) throw new Error('args.ask가 필요합니다: 구체 요청 내용')
if (!DATE || !/^\d{4}-\d{2}-\d{2}$/.test(DATE)) throw new Error('args.date가 필요합니다: YYYY-MM-DD 형식의 오늘 날짜')

const STAGE_DEF = {
  prep: {
    name: '미팅 준비',
    template: 'templates/sales/discovery-prep.md',
    deliverable: '미팅 전 브리프: 계정 요약, 디스커버리 질문 8~12개, 예상 반대논거 2개와 대응, 다음 단계 제안 2개',
  },
  debrief: {
    name: '미팅 부검',
    template: 'templates/sales/meeting-debrief.md',
    deliverable: 'SPICED 5필드 기록(고객 발언 인용), 페인 3층 노트, 자격검증 채점 초안(고ACV면 MEDDPICC 16점 채점 병행)과 판정 권고, PO 최종 판정란(진행/조건부/탈락, 서명)은 비워 두기, 포워더블 후속 메일 초안(영문)',
  },
  pilot: {
    name: '파일럿 헌장',
    template: 'templates/sales/pilot-charter.md',
    deliverable: '파일럿 헌장 초안: 단일 KPI, 합격선, 측정 방법, 의사결정 규칙, 기간 6~8주 고정, 유료 조건, EB 승인란(G8: 헌장 없이는 발송 가능 상태로 전달 불가)',
  },
  proposal: {
    name: 'ROI 비즈니스 케이스',
    template: 'templates/sales/roi-business-case.md',
    deliverable: 'ROI 비즈니스 케이스: 가정 명세표(출처 표기), 보수/기본/낙관 3시나리오, TCO 전체, 리스크와 완화책',
  },
  security: {
    name: '보안 심사 대응',
    template: 'templates/sales/evidence-card.md',
    deliverable: '보안 설문 답변 패키지(답변 라이브러리 기반), 데이터 흐름도, 트러스트 패키지(연구 자산 증거 카드)',
  },
}
const DEF = STAGE_DEF[STAGE]

const TRIAGE_SCHEMA = {
  type: 'object', required: ['account_slug', 'deliverables', 'research_focus', 'po_decision_items', 'summary'],
  properties: {
    account_slug: { type: 'string', description: '계정 영문 슬러그(소문자, 숫자, 하이픈만. 예: acme-asset-mgmt)' },
    deliverables: { type: 'array', items: { type: 'string' }, description: '이번 요청에서 만들 산출물 목록' },
    research_focus: { type: 'string', description: '계정 리서치가 필요하면 조사 포인트, 불필요하면 빈 문자열' },
    po_decision_items: { type: 'array', items: { type: 'string' }, description: '이 요청에 걸린 PO 전속 결정(자격검증 판정, 딜 전략, 챔피언 판정 등)' },
    summary: { type: 'string' },
  },
}

const RESEARCH_SCHEMA = {
  type: 'object', required: ['research_file', 'signals', 'summary'],
  properties: {
    research_file: { type: 'string', description: '저장한 리서치 파일 경로' },
    signals: { type: 'array', items: { type: 'string' }, description: '최신 시그널(종류/일자/출처)' },
    summary: { type: 'string' },
  },
}

const DELIVERABLE_SCHEMA = {
  type: 'object', required: ['files', 'summary', 'po_decision_items'],
  properties: {
    files: { type: 'array', items: { type: 'string' }, description: '저장한 산출물 파일 경로' },
    summary: { type: 'string' },
    po_decision_items: { type: 'array', items: { type: 'string' }, description: 'PO 판정란/결정 대기 항목(판정 권고 포함, 최종 판정은 PO)' },
  },
}

const FACTCHECK_SCHEMA = {
  type: 'object', required: ['verdict', 'issues', 'regulatory_flags', 'record_file', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    issues: {
      type: 'array',
      items: {
        type: 'object', required: ['claim', 'problem'],
        properties: {
          claim: { type: 'string', description: '문제된 수치/주장' },
          problem: { type: 'string', description: '문제와 수정 방향(KB08 등급 미달, 출처 불명 등)' },
        },
      },
      description: '검증 실패 항목(PASS면 빈 배열)',
    },
    regulatory_flags: { type: 'array', items: { type: 'string' }, description: '규제 해석이 걸린 답변(AI기본법, 개인정보, 금융 규제). 없으면 빈 배열' },
    record_file: { type: 'string', description: '팩트체크 기록 파일 경로' },
    summary: { type: 'string' },
  },
}

const REG_REVIEW_SCHEMA = {
  type: 'object', required: ['verdict', 'held_items', 'record_file', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['이상없음', '수정필요', '회신대기'], description: '회신대기: legal-team 에스컬레이션 회신 전 해당 항목 사용 금지' },
    held_items: { type: 'array', items: { type: 'string' }, description: 'legal-team 회신 전까지 분리 보류할 답변 항목(나머지는 진행)' },
    record_file: { type: 'string', description: '심사 기록 파일 경로' },
    summary: { type: 'string' },
  },
}

log('딜 지원 시작: ' + ACCOUNT + ' / ' + STAGE + ' (' + DEF.name + ')')

// ── 1. 요청 분류 ─────────────────────────────────────────────
const triage = await agent([
  '딜 지원 요청을 분류하고 산출물을 정의하라. 시작 전에 kb/sales/07-sales-team-ops.md, kb/sales/04-sales-methodology.md, kb/sales/08-oneline-ai-context.md를 읽어라.',
  '[계정] ' + ACCOUNT + ' / [단계] ' + STAGE + ' (' + DEF.name + ')',
  '[요청] ' + ASK,
  '[배경/노트] ' + NOTES,
  '',
  '- account_slug(영문 소문자/숫자/하이픈)를 정하라. 기존 docs/sales/deals/ 아래에 이 계정 폴더가 있으면 같은 슬러그를 재사용하라(Glob으로 확인).',
  '- 이 단계의 표준 산출물(' + DEF.deliverable + ')과 요청 특수사항을 합쳐 deliverables를 확정하라.',
  '- 요청이 긍정 답장 후속 처리와 관련되면 답장 분류(긍정/부정/OOO/수신거부성) 기준 적용과 CTA 전환 문안(interest CTA에서 구체 시간 2개 제시로 전환, 영문)을 deliverables에 포함하라.',
  '- KB07 §7.3 분업표에 따라 이 요청에 걸린 PO 전속 결정(자격검증 최종 판정, 딜 전략, Commit, 챔피언 판정 등)을 po_decision_items로 분리하라.',
].join('\n'), { label: 'lead:분류', phase: '요청 분류', agentType: 'sales-lead', schema: TRIAGE_SCHEMA })

if (!triage) throw new Error('요청 분류 실패')
const SLUG = (triage.account_slug || '').toLowerCase().replace(/[^a-z0-9-]/g, '') || 'account'
const DEAL_DIR = 'docs/sales/deals/' + SLUG
log('분류 완료: ' + DEAL_DIR + ' / 산출물 ' + triage.deliverables.length + '건')

// ── 2. 계정 리서치 (prep/proposal 시) ────────────────────────
let research = null
if (STAGE === 'prep' || STAGE === 'proposal') {
  research = await agent([
    '계정의 최신 시그널과 인물 리서치를 갱신하라. 시작 전에 kb/sales/03-prospecting-icp.md, kb/sales/08-oneline-ai-context.md를 읽어라.',
    '[계정] ' + ACCOUNT + ' / [단계] ' + DEF.name,
    '[요청] ' + ASK,
    '[리서치 포인트] ' + (triage.research_focus || '(지정 없음: 표준 리서치)'),
    '[기존 산출물] ' + DEAL_DIR + '/ 아래 기존 리서치가 있으면 Read로 읽고 갱신하라.',
    '',
    'templates/sales/account-research.md 포맷(시그널: 종류/일자/출처, 가설, 타깃 인물, 훅 1문장, 배제 확인)으로 작성하고,',
    '미팅/제안에 쓸 수 있는 최신 시그널(채용, 펀딩, 임원 이동, 챔피언 이직, RFP 공고)을 웹으로 확인하라. 모든 시그널에 출처와 확인일(' + DATE + ')을 붙여라.',
    '산출물을 ' + DEAL_DIR + '/' + DATE + '-account-research.md 에 저장하라.',
  ].join('\n'), { label: 'researcher:계정', phase: '계정 리서치', agentType: 'prospect-researcher', schema: RESEARCH_SCHEMA })
  if (!research) throw new Error('계정 리서치 실패')
  log('리서치 갱신: 시그널 ' + research.signals.length + '건')
}

// ── 3. 산출물 작성 ───────────────────────────────────────────
const strategistPrompt = [
  '딜 지원 산출물을 작성하라. 시작 전에 kb/sales/04-sales-methodology.md, kb/sales/05-ai-saas-sales.md, kb/sales/08-oneline-ai-context.md를 읽어라.',
  '[계정] ' + ACCOUNT + ' / [단계] ' + STAGE + ' (' + DEF.name + ')',
  '[요청] ' + ASK,
  '[배경/노트] ' + NOTES,
  '[산출물 정의] ' + triage.deliverables.join(' | '),
  research ? '[최신 계정 리서치] ' + research.research_file + ' (Read로 읽을 것)' : '[계정 리서치] 이번 단계는 신규 리서치 없음. ' + DEAL_DIR + '/ 아래 기존 자료가 있으면 Read로 활용하라.',
  '',
  '[표준 산출물] ' + DEF.deliverable,
  '[템플릿] ' + DEF.template + ' 구조를 따르라.',
  '',
  '공통 규칙:',
  '- 대외 전달 문안(후속 메일, 제안 문구)은 영문이 기본이다.',
  '- 사실 주장은 증거 카드 라이브러리(templates/sales/evidence-card.md 포맷)와 KB08 신뢰 등급 [확인] 항목만 인용하라. 무명 해외 스타트업의 신뢰 장벽은 연구 자산(ACL 2025, KMMLU, KRX 공동개발, 민카부 상용 협업) 증거 카드로 대응하라.',
  '- 자격검증 최종 판정(진행/조건부/탈락), 딜 전략 결정, Commit, 챔피언 판정은 PO 전속이다. 너는 채점 초안과 판정 권고, 근거 정리까지만 하고 PO 판정란은 비워 둬라(G8).',
  '- 반대논거 대응이 요청되면 반대논거 플레이북(가격/타이밍/자체구축/현상유지/신뢰)과 무행동 비용 계산을 활용하라.',
  '- 긍정 답장 후속이 요청에 포함되면: 답장 분류 기준(긍정/부정/OOO/수신거부성)을 명시하고, interest CTA에서 구체 시간 2개 제시로 전환하는 영문 문안을 작성하라.',
  '',
  '산출물을 ' + DEAL_DIR + '/ 아래에 파일명 ' + DATE + '-' + STAGE + '-*.md 형태로 저장하라.',
].join('\n')

let deliverable = await agent(strategistPrompt, { label: 'strategist:' + STAGE, phase: '산출물 작성', agentType: 'deal-strategist', schema: DELIVERABLE_SCHEMA })
if (!deliverable) throw new Error('산출물 작성 실패')
log('산출물 ' + deliverable.files.length + '건: ' + deliverable.files.join(', '))

// ── 4. 팩트체크 ──────────────────────────────────────────────
let factcheck = await agent([
  '딜 지원 산출물 중 대외 전달물의 수치와 주장을 팩트체크하라. 시작 전에 kb/sales/08-oneline-ai-context.md, kb/sales/05-ai-saas-sales.md를 읽어라.',
  '[검증 대상] ' + deliverable.files.join(', ') + ' (모두 Read로 읽을 것)',
  '[계정] ' + ACCOUNT + ' / [단계] ' + DEF.name,
  '',
  '- 모든 수치, 고객명, 성과 주장, 벤치마크를 KB08 신뢰 등급([확인] 등급만 사실 진술 가능)과 원출처에 대조하라. 미검증 주장이 대외 전달물에 있으면 FAIL이다.',
  '- 영문 전달물은 네이티브 관용성과 톤도 검토하라(문법상 맞지만 어색한 영어는 반려).',
  '- 규제 해석이 걸린 답변(AI기본법, 개인정보, 금융 규제)은 판정하지 말고 regulatory_flags에 담아라(sales-compliance-officer 경유 legal-team 확인 대상).',
  '',
  '팩트체크 기록을 ' + DEAL_DIR + '/' + DATE + '-factcheck.md 에 저장하라.',
].join('\n'), { label: 'qa:팩트체크', phase: '팩트체크', agentType: 'outreach-qa', schema: FACTCHECK_SCHEMA })
if (!factcheck) throw new Error('팩트체크 실패')

// 팩트체크 FAIL이면 1회 수정 후 재검
if (factcheck.verdict === 'FAIL') {
  log('팩트체크 FAIL: ' + factcheck.issues.length + '건 수정 후 재검')
  deliverable = await agent([
    strategistPrompt,
    '',
    '[반려] outreach-qa 팩트체크에서 다음이 FAIL 판정됐다. 지적을 전부 반영해 같은 파일들을 수정 저장하라. 미검증 주장은 삭제하거나 [확인] 등급 근거로 교체하라.',
    factcheck.issues.map(i => '- ' + i.claim + ': ' + i.problem).join('\n'),
  ].join('\n'), { label: 'strategist:수정', phase: '산출물 작성', agentType: 'deal-strategist', schema: DELIVERABLE_SCHEMA })
  if (!deliverable) throw new Error('산출물 수정 실패')
  factcheck = await agent([
    '수정된 산출물을 재검하라. 이전 기록: ' + factcheck.record_file + ' (Read로 읽을 것)',
    '[검증 대상] ' + deliverable.files.join(', ') + ' (모두 Read로 읽을 것)',
    '이전 FAIL 항목이 전부 해소됐는지 확인하고, 재검 기록을 ' + DEAL_DIR + '/' + DATE + '-factcheck-2.md 에 저장하라.',
  ].join('\n'), { label: 'qa:재검', phase: '팩트체크', agentType: 'outreach-qa', schema: FACTCHECK_SCHEMA })
  if (!factcheck) throw new Error('팩트체크 재검 실패')
}
log('팩트체크: ' + factcheck.verdict + (factcheck.regulatory_flags.length ? ' / 규제 플래그 ' + factcheck.regulatory_flags.length + '건' : ''))

// 규제 해석 사안: sales-compliance-officer 경유 legal-team 확인. 회신 대기 항목만 분리 보류하고 잔여는 진행.
let regReview = null
if (factcheck.regulatory_flags.length) {
  regReview = await agent([
    '딜 지원 대외 전달물의 규제 해석 사안을 심사하라. 시작 전에 kb/sales/09-global-outreach-compliance.md, kb/sales/06-kr-outreach-compliance.md를 읽어라.',
    '[대상 산출물] ' + deliverable.files.join(', ') + ' (모두 Read로 읽을 것)',
    '[규제 플래그] ' + factcheck.regulatory_flags.join(' | '),
    '',
    '- 각 플래그를 심사해 이상없음/수정필요/legal-team 에스컬레이션 필요로 분류하라.',
    '- legal-team 확인이 필요한 경계 사안은 에스컬레이션 질의를 정리해 기록에 남기고 held_items로 분리 보류하라. 회신 대기가 전체 산출물 전달을 막지 않는다: 보류 항목을 제외한 잔여는 진행한다.',
    '- 보류 항목은 산출물 안에 "legal-team 회신 전 사용 금지" 표시가 되도록 수정 지시를 남겨라.',
    '',
    '심사 기록을 docs/sales/compliance/' + DATE + '-' + SLUG + '-deal-reg-review.md 에 저장하라.',
  ].join('\n'), { label: 'compliance:규제심사', phase: '팩트체크', agentType: 'sales-compliance-officer', schema: REG_REVIEW_SCHEMA })
  if (!regReview) throw new Error('규제 심사 실패')
  log('규제 심사: ' + regReview.verdict + (regReview.held_items.length ? ' / 보류 ' + regReview.held_items.length + '건' : ''))
}

// ── 5. 종합 전달 ─────────────────────────────────────────────
const poDecisions = (triage.po_decision_items || []).concat(deliverable.po_decision_items || [])
const finalPkg = await agent([
  '딜 지원 산출물을 종합해 PO 전달 패키지를 만들라.',
  '[계정] ' + ACCOUNT + ' / [단계] ' + DEF.name + ' / [요청] ' + ASK,
  '[산출물] ' + deliverable.files.join(', ') + ' (모두 Read로 읽을 것)',
  '[팩트체크] ' + factcheck.verdict + ' (' + factcheck.record_file + ')',
  regReview ? '[규제 심사] ' + regReview.verdict + ' / 보류: ' + (regReview.held_items.join('; ') || '없음') + ' (' + regReview.record_file + ')' : '[규제 심사] 해당 없음',
  factcheck.verdict === 'FAIL' ? '[경고] 팩트체크가 수정 후에도 FAIL이다. 해당 전달물은 "발송 불가, PO 확인 필요"로 표시하라(fail-closed).' : '',
  '',
  '패키지 상단에 세 구획을 명확히 구분해 표기하라:',
  '1) PO가 직접 할 일: 미팅 수행, 관계 구축, 자격검증 최종 판정, 딜 전략 결정, Commit 판정 등',
  '2) PO 결정 대기 항목: ' + (poDecisions.join(' | ') || '(없음)') + ' + 진행/조건부/탈락 판정란, 챔피언 판정 등 판정란 위치 안내',
  '3) 에이전트가 준비한 것: 산출물 목록과 각 파일 경로, 게이트 통과 상태',
  regReview && regReview.held_items.length ? '보류 항목(legal-team 회신 대기)은 별도 구획으로 분리하고 회신 전 사용 금지를 명기하라.' : '',
  '',
  '패키지를 ' + DEAL_DIR + '/' + DATE + '-' + STAGE + '-support.md 에 저장하고 저장 경로와 3문장 요지를 반환하라.',
].join('\n'), { label: 'lead:전달', phase: '종합 전달', agentType: 'sales-lead' })

log('딜 지원 완료: ' + DEAL_DIR + '/' + DATE + '-' + STAGE + '-support.md')

return {
  status: factcheck.verdict === 'PASS' ? 'ready_for_po' : 'ready_with_warnings',
  account: ACCOUNT,
  stage: STAGE,
  factcheck: factcheck.verdict,
  regulatory_review: regReview ? { verdict: regReview.verdict, held_items: regReview.held_items } : null,
  artifacts: {
    support_package: DEAL_DIR + '/' + DATE + '-' + STAGE + '-support.md',
    deliverables: deliverable.files,
    research: research ? research.research_file : null,
    factcheck_record: factcheck.record_file,
    reg_review_record: regReview ? regReview.record_file : null,
  },
  summary: finalPkg,
  po_todo: [
    '전달 패키지 검토: ' + DEAL_DIR + '/' + DATE + '-' + STAGE + '-support.md',
    STAGE === 'debrief' ? '자격검증 최종 판정 기록(진행/조건부/탈락, 판정란 서명). 판정 기록 없으면 다음 스테이지 이동 불가(G8)' : '',
    STAGE === 'pilot' ? '파일럿 헌장 검토와 EB 승인 추진' : '',
    factcheck.verdict === 'FAIL' ? '팩트체크 미해소 항목 직접 확인(해소 전 대외 발송 금지)' : '',
    regReview && regReview.held_items.length ? 'legal-team 회신 확인 후 보류 항목 해제 여부 결정' : '',
  ].filter(Boolean).concat(poDecisions),
}
