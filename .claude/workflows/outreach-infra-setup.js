export const meta = {
  name: 'outreach-infra-setup',
  description: '발신 인프라 구축과 점검: 도메인/메일박스 설계 → DNS 인증 → 웜업 계획 → 발송 도구 안전장치 검증 → suppression 정책 확인 → 준비 완료/미완료 판정. 캠페인 개시 최소 2~4주 전에 선행하며, 완료 판정 없이 cold-outreach-campaign은 발송 단계로 갈 수 없다',
  whenToUse: '콜드 아웃리치 발신 인프라 구축/점검 요청 시. args: { target_daily_volume: 목표 일일 콜드 발송량(숫자), providers: "Google | Microsoft | 혼합"(선택), existing_domains: "기존 보유 발신 도메인 목록"(선택), date: "YYYY-MM-DD(오늘)" }',
  phases: [
    { title: '구성 설계', detail: 'deliverability-engineer: 볼륨 역산 공식으로 도메인/메일박스 구성 설계, 브랜드 변형 네이밍, 구매 체크리스트' },
    { title: 'DNS 인증', detail: 'deliverability-engineer: SPF/DKIM/DMARC/트래킹 도메인/301 리다이렉트/Postmaster 셋업 명세와 검증 기록' },
    { title: '웜업 계획', detail: 'deliverability-engineer: 2~4주 웜업 스케줄과 콜드 램프업 계획, 웜업 지표 기준 정의' },
    { title: '안전장치 검증', detail: 'deliverability-engineer: 발송 도구 안전장치 4종 설정 명세 작성과 적용 검증. 미검증이면 인프라 미완료 판정' },
    { title: 'suppression 정책', detail: 'sales-compliance-officer: 전역 suppression 저장소와 수신거부 처리 플로우, EU 보관기간 정책 확인' },
    { title: '완료 판정', detail: 'sales-lead: 준비 완료/미완료 판정 보고서 작성, 미완료 항목은 캠페인 착수 차단 목록으로 PO 보고' },
  ],
}

const VOLUME = args && args.target_daily_volume ? Number(args.target_daily_volume) : 0
const PROVIDERS = args && args.providers ? args.providers : '(미지정: Google 기본, 필요 시 혼합 제안)'
const EXISTING = args && args.existing_domains ? args.existing_domains : '(없음: 신규 구매 전제)'
const DATE = args && args.date ? args.date : ''
if (!VOLUME || VOLUME <= 0 || !isFinite(VOLUME)) throw new Error('args.target_daily_volume이 필요합니다: 목표 일일 콜드 발송량(양의 숫자)')
if (!DATE || !/^\d{4}-\d{2}-\d{2}$/.test(DATE)) throw new Error('args.date가 필요합니다: YYYY-MM-DD 형식의 오늘 날짜')

const INFRA_DIR = 'docs/sales/infra'
const COMP_DIR = 'docs/sales/compliance'

const PLAN_SCHEMA = {
  type: 'object', required: ['plan_file', 'domains_needed', 'mailboxes_needed', 'summary'],
  properties: {
    plan_file: { type: 'string', description: '저장한 설계 문서 경로' },
    domains_needed: { type: 'integer', description: '필요 세컨더리 도메인 수' },
    mailboxes_needed: { type: 'integer', description: '필요 메일박스 수' },
    summary: { type: 'string', description: '역산 근거 요약' },
  },
}

const DNS_SCHEMA = {
  type: 'object', required: ['spec_file', 'verified_items', 'pending_items', 'summary'],
  properties: {
    spec_file: { type: 'string', description: '저장한 DNS 셋업 명세/검증 기록 경로' },
    verified_items: { type: 'array', items: { type: 'string' }, description: '검증 완료 항목' },
    pending_items: { type: 'array', items: { type: 'string' }, description: '미완료 항목(PO 조치 필요 포함)' },
    summary: { type: 'string' },
  },
}

const WARMUP_SCHEMA = {
  type: 'object', required: ['plan_file', 'warmup_weeks', 'criteria', 'summary'],
  properties: {
    plan_file: { type: 'string', description: '저장한 웜업/램프업 계획 경로' },
    warmup_weeks: { type: 'integer', description: '웜업 기간(주, 2~4)' },
    criteria: { type: 'string', description: '웜업 완료 판정 지표 기준(답장률 30~40%, 인박스율 90%)' },
    summary: { type: 'string' },
  },
}

const SAFEGUARD_SCHEMA = {
  type: 'object', required: ['spec_file', 'all_verified', 'verified', 'unverified', 'summary'],
  properties: {
    spec_file: { type: 'string', description: '저장한 안전장치 설정 명세/검증 기록 경로' },
    all_verified: { type: 'boolean', description: '4종 안전장치가 전부 적용 검증되었는가' },
    verified: { type: 'array', items: { type: 'string' }, description: '적용 검증 완료 항목' },
    unverified: { type: 'array', items: { type: 'string' }, description: '미설정/미검증 항목(각각 PO가 할 설정 조치 명시)' },
    summary: { type: 'string' },
  },
}

const SUPPRESSION_SCHEMA = {
  type: 'object', required: ['policy_file', 'record_file', 'ok', 'gaps', 'summary'],
  properties: {
    policy_file: { type: 'string', description: 'suppression 정책 문서 경로' },
    record_file: { type: 'string', description: '이번 점검 기록 경로' },
    ok: { type: 'boolean', description: '정책과 스키마 반영이 기준을 충족하는가' },
    gaps: { type: 'array', items: { type: 'string' }, description: '미충족 항목' },
    summary: { type: 'string' },
  },
}

const READINESS_SCHEMA = {
  type: 'object', required: ['report_file', 'ready', 'blockers', 'summary'],
  properties: {
    report_file: { type: 'string', description: '판정 보고서 경로' },
    ready: { type: 'boolean', description: '인프라 준비 완료 여부' },
    blockers: { type: 'array', items: { type: 'string' }, description: '캠페인 착수 차단 목록(미완료 항목)' },
    summary: { type: 'string' },
  },
}

log('발신 인프라 셋업 시작: 목표 일일 ' + VOLUME + '통 / 프로바이더 ' + PROVIDERS)

// ── 1. 구성 설계 ─────────────────────────────────────────────
const plan = await agent([
  '발신 도메인과 메일박스 구성을 설계하라. 시작 전에 kb/sales/02-deliverability.md를 읽어라.',
  '[목표 일일 콜드 발송량] ' + VOLUME + '통',
  '[프로바이더] ' + PROVIDERS,
  '[기존 보유 도메인] ' + EXISTING,
  '',
  '요구사항:',
  '- onelineai.com 루트 도메인 발송 금지를 전제로 하라(루트 도메인 보호).',
  '- 볼륨 역산 공식(메일박스당 일 20~50통 한도)으로 필요 세컨더리 도메인 수와 메일박스 수를 산출하라.',
  '- 브랜드 변형 네이밍과 TLD 후보, 구매 체크리스트(구매 주체는 PO)를 작성하라.',
  '',
  '설계 문서를 templates/sales/deliverability-runbook.md의 인프라 셋업 체크리스트(D-28~D-0) 구조를 참조해 ' + INFRA_DIR + '/' + DATE + '-domain-plan.md 에 저장하라.',
].join('\n'), { label: 'deliverability:구성설계', phase: '구성 설계', agentType: 'deliverability-engineer', schema: PLAN_SCHEMA })

if (!plan) throw new Error('구성 설계 실패')
log('구성 설계: 도메인 ' + plan.domains_needed + '개, 메일박스 ' + plan.mailboxes_needed + '개')

// ── 2. DNS 인증 ──────────────────────────────────────────────
const dns = await agent([
  'DNS 셋업 명세를 작성하고 현재 적용 상태를 검증해 기록하라. kb/sales/02-deliverability.md를 참조하라.',
  '[구성 설계] ' + plan.plan_file + ' (Read로 읽을 것)',
  '[기존 보유 도메인] ' + EXISTING,
  '',
  '명세와 검증 항목:',
  '- SPF: DNS 조회 10회 이내.',
  '- DKIM: 2048bit 키.',
  '- DMARC: 정책과 rua 수신 주소 포함.',
  '- 커스텀 트래킹 도메인, 발신 도메인에서 메인 사이트로의 301 리다이렉트.',
  '- Google Postmaster Tools 등록.',
  '실제 DNS 조회가 가능한 도메인은 Bash(dig/nslookup)로 검증하고, 미구매/미설정 도메인은 pending으로 분류해 PO 조치 항목을 명시하라.',
  '',
  '명세와 검증 기록을 ' + INFRA_DIR + '/' + DATE + '-dns-setup.md 에 저장하라.',
].join('\n'), { label: 'deliverability:DNS', phase: 'DNS 인증', agentType: 'deliverability-engineer', schema: DNS_SCHEMA })

if (!dns) throw new Error('DNS 셋업 명세 작성 실패')
log('DNS: 검증 완료 ' + dns.verified_items.length + '건, 미완료 ' + dns.pending_items.length + '건')

// ── 3. 웜업 계획 ─────────────────────────────────────────────
const warmup = await agent([
  '웜업과 콜드 램프업 계획을 수립하라. kb/sales/02-deliverability.md를 참조하라.',
  '[구성 설계] ' + plan.plan_file + ' / [DNS 상태] ' + dns.spec_file + ' (Read로 읽을 것)',
  '[목표 일일 발송량] ' + VOLUME + '통',
  '',
  '요구사항:',
  '- 2~4주 웜업 스케줄(메일박스별)과 웜업 완료 판정 지표 기준(웜업 답장률 30~40%, 인박스율 90%)을 정의하라.',
  '- 웜업 완료 후 콜드 램프업 계획(일일 한도 20~50통까지 단계 증량)과 상시 백그라운드 웜업 유지 방침을 포함하라.',
  '- 캠페인 개시 가능 시점(웜업 완료 예상일)을 명시하라. 오늘은 ' + DATE + '다.',
  '',
  '계획을 ' + INFRA_DIR + '/' + DATE + '-warmup-plan.md 에 저장하라.',
].join('\n'), { label: 'deliverability:웜업', phase: '웜업 계획', agentType: 'deliverability-engineer', schema: WARMUP_SCHEMA })

if (!warmup) throw new Error('웜업 계획 수립 실패')
log('웜업 계획: ' + warmup.warmup_weeks + '주 / 기준: ' + warmup.criteria)

// ── 4. 안전장치 검증 ─────────────────────────────────────────
const safeguard = await agent([
  '발송 도구 안전장치 설정 명세를 작성하고 적용 여부를 검증하라. kb/sales/02-deliverability.md를 참조하라.',
  '[구성 설계] ' + plan.plan_file + ' (Read로 읽을 것)',
  '',
  '명세 항목(4종, 발송 도구의 네이티브 자동 중단 기능을 PO가 설정하고 이 에이전트가 검증한다):',
  '1) 답장 감지 시 해당 수신자 시퀀스 자동 중단',
  '2) 하드바운스 자동 suppression 등록',
  '3) 마스터 suppression 리스트와 발송 도구 간 양방향 동기화',
  '4) 바운스/신고 임계 초과 시 자동 발송 중단(서킷브레이커 사전 방어선: 바운스율 2%, 신고율 0.1%, 배치율 85%)',
  '',
  '각 항목의 설정 명세(어느 도구의 어떤 설정을 어떤 값으로)와 검증 방법, 현재 적용 상태를 기록하라.',
  '적용 확인이 안 되는 항목은 unverified로 분류하고 PO가 할 설정 조치를 명시하라. 하나라도 미검증이면 all_verified는 false다(인프라 미완료 판정 사유).',
  '',
  '명세와 검증 기록을 templates/sales/deliverability-runbook.md의 안전장치 섹션 구조로 ' + INFRA_DIR + '/' + DATE + '-tool-safeguards.md 에 저장하라.',
].join('\n'), { label: 'deliverability:안전장치', phase: '안전장치 검증', agentType: 'deliverability-engineer', schema: SAFEGUARD_SCHEMA })

if (!safeguard) throw new Error('안전장치 검증 실패')
log('안전장치: ' + (safeguard.all_verified ? '4종 전부 검증 완료' : '미검증 ' + safeguard.unverified.length + '건'))

// ── 5. suppression 정책 ──────────────────────────────────────
const suppression = await agent([
  '전역 suppression 정책과 처리 플로우를 확인하라. 시작 전에 kb/sales/09-global-outreach-compliance.md, kb/sales/06-kr-outreach-compliance.md, kb/sales/02-deliverability.md를 읽어라.',
  '[안전장치 검증 기록] ' + safeguard.spec_file + ' (Read로 읽을 것)',
  '',
  '확인 기준:',
  '- 전역 suppression 저장소: 즉시 등록, 전 캠페인 공통, 우회 불가, 해시 보관, 재동의 시만 해제.',
  '- 수신거부 처리 플로우: 목표 24시간 내, 국가별 법정 상한(CAN-SPAM 10영업일 등) 준수.',
  '- EU 보관기간 정책: 마지막 접촉 기준 3년, 만료 도래 레코드 삭제/익명화가 리스트/CRM 스키마(보관기간 만료일 필드)에 반영되어 있는지 확인.',
  '',
  '정책 문서가 없으면 ' + COMP_DIR + '/suppression-policy.md 에 정책을 작성하고, 이번 점검 기록을 ' + COMP_DIR + '/' + DATE + '-suppression-policy-check.md 에 저장하라. 미충족 항목은 gaps에 담아라.',
].join('\n'), { label: 'compliance:suppression', phase: 'suppression 정책', agentType: 'sales-compliance-officer', schema: SUPPRESSION_SCHEMA })

if (!suppression) throw new Error('suppression 정책 확인 실패')
log('suppression 정책: ' + (suppression.ok ? '충족' : '미충족 ' + suppression.gaps.length + '건'))

// ── 6. 완료 판정 ─────────────────────────────────────────────
const readiness = await agent([
  '인프라 준비 완료/미완료 판정 보고서를 작성하라.',
  '[입력: 각 단계 산출물(전부 Read로 읽을 것)]',
  '- 구성 설계: ' + plan.plan_file,
  '- DNS: ' + dns.spec_file + ' (미완료 ' + dns.pending_items.length + '건)',
  '- 웜업 계획: ' + warmup.plan_file,
  '- 안전장치: ' + safeguard.spec_file + ' (전부 검증: ' + safeguard.all_verified + ')',
  '- suppression 정책: ' + suppression.record_file + ' (충족: ' + suppression.ok + ')',
  '',
  '판정 규칙(fail-closed):',
  '- DNS 미완료 항목, 안전장치 미검증 항목, suppression 정책 미충족 항목, 웜업 미완료가 하나라도 있으면 ready는 false다.',
  '- 미완료 항목 전부를 캠페인 착수 차단 목록(blockers)으로 정리하고, 항목별 담당(PO 조치인지 에이전트 재검증인지)과 해소 조건을 명시하라.',
  '- 이 워크플로의 완료 판정 없이 cold-outreach-campaign은 발송 단계(딜리버러빌리티 프리플라이트)를 통과할 수 없다는 것을 보고서에 명기하라.',
  '',
  '보고서를 reports/sales/' + DATE + '-infra-readiness.md 에 저장하라.',
].join('\n'), { label: 'lead:판정', phase: '완료 판정', agentType: 'sales-lead', schema: READINESS_SCHEMA })

if (!readiness) throw new Error('완료 판정 실패')
log('인프라 판정: ' + (readiness.ready ? '준비 완료' : '미완료 (차단 ' + readiness.blockers.length + '건)'))

return {
  status: readiness.ready ? 'ready' : 'incomplete',
  target_daily_volume: VOLUME,
  blockers: readiness.blockers,
  artifacts: {
    readiness_report: readiness.report_file,
    domain_plan: plan.plan_file,
    dns_setup: dns.spec_file,
    warmup_plan: warmup.plan_file,
    tool_safeguards: safeguard.spec_file,
    suppression_policy: suppression.policy_file,
    suppression_check: suppression.record_file,
  },
  po_todo: [
    readiness.ready ? '준비 완료 보고 확인: ' + readiness.report_file : '차단 목록 해소: ' + readiness.blockers.join(' | '),
    '도메인/메일박스 구매와 DNS 레코드 적용(명세: ' + dns.spec_file + ')',
    safeguard.all_verified ? '' : '발송 도구 안전장치 설정 적용(명세: ' + safeguard.spec_file + ') 후 재검증 요청',
    '웜업 개시와 진행 확인(계획: ' + warmup.plan_file + ')',
    readiness.ready ? '' : '차단 해소 후 outreach-infra-setup 재실행으로 완료 판정 갱신',
  ].filter(Boolean),
}
