export const meta = {
  name: 'cold-outreach-campaign',
  description: '글로벌 콜드 아웃리치 캠페인 파이프라인: 브리프 → 리스트 → 멀티채널 터치맵 → 전 채널 영문 카피 → QA/컴플라이언스/딜리버러빌리티 3중 fail-closed 게이트 → PO 승인 대기 발송 패키지 조립',
  whenToUse: '콜드 아웃리치 캠페인 기획과 발송 준비 요청 시. args: { region: "US | EU-<국가코드> | UK | JP | SG | AU | KR", segment: "타깃 세그먼트 설명(예: 미국 자산운용사의 리서치 조직)", tier: 1|2|3, goal: "목표(예: 4주 내 미팅 5건)", list_source: "리스트 출처(선택)", date: "YYYY-MM-DD(오늘)" }',
  phases: [
    { title: '캠페인 브리프', detail: 'sales-lead: 착수 조건 검사(ICP PO 승인 확인, 회피 등급 분기 선언)와 캠페인 브리프 작성' },
    { title: '리스트 구축', detail: 'prospect-researcher: 리스트 구축/검증, 레코드별 jurisdiction/출처/증빙 태깅, Tier 1~2 계정 리서치, 시그널 없는 계정 발송 보류' },
    { title: '터치맵 설계', detail: 'channel-strategist: Day-by-Day 멀티채널 터치맵(이메일 3~4통 + LinkedIn/전화 슬롯), 회피 등급 레코드 alt-channel-play 이관' },
    { title: '카피 작성', detail: 'cold-email-writer: 터치맵 전 채널 영문 카피(이메일, LinkedIn 노트/DM, 콜/보이스메일 스크립트)' },
    { title: 'QA 게이트', detail: 'outreach-qa: 11항목 게이트 + 시퀀스 구조 + 영어 네이티브 관용성/톤 검수. FAIL 시 카피 반려 루프 최대 2회, 최종 FAIL이면 sales-lead 재설계 보고 후 실패 반환' },
    { title: '컴플라이언스 게이트', detail: 'sales-compliance-officer: 게이트 A(리스트)/B(메시지)/C(운영) 심사, LIA 초안, 제외 레코드는 큐에서 제거, 경계 사안은 분리 보류 후 잔여 레코드로 부분 진행' },
    { title: '딜리버러빌리티 프리플라이트', detail: 'deliverability-engineer: 웜업/한도/바운스 예측 점검, 발송 도구 안전장치 설정 검증, 발송 스케줄 배정. 미충족이면 발송 스케줄 배정 불가' },
    { title: '발송 패키지 조립', detail: 'sales-lead: 게이트 통과 기록과 터치 2~N 릴리스 조건을 포함한 발송 패키지를 docs/sales/outbox/<캠페인ID>/에 조립하고 PO 승인 요청' },
    { title: '터치 릴리스 조건', detail: '터치 2~N 릴리스 게이트는 워크플로 1회 실행 안에서 반복할 수 없다. 릴리스 조건을 발송 패키지에 포함하고, 실제 게이트 판정은 sales-ops-review daily 모드가 수행한다' },
    { title: '캠페인 레코드', detail: 'sales-ops-analyst: 캠페인 레코드 생성, 지표 추적과 격주 회고 일정 세팅' },
  ],
}

const REGION = args && args.region ? String(args.region) : ''
const SEGMENT = args && args.segment ? args.segment : ''
const TIER = args && args.tier ? args.tier : null
const GOAL = args && args.goal ? args.goal : ''
const LIST_SOURCE = args && args.list_source ? args.list_source : '(미지정: 글로벌 워터폴 또는 한국 자체 소스 조합으로 제안)'
const DATE = args && args.date ? args.date : ''
if (!REGION) throw new Error('args.region이 필요합니다: US | EU-<국가코드> | UK | JP | SG | AU | KR')
if (!/^(US|UK|JP|SG|AU|KR|EU-[A-Z]{2})$/.test(REGION)) throw new Error('region 형식 오류: US | EU-<국가코드 2자리 대문자> | UK | JP | SG | AU | KR 중 하나여야 합니다 (예: EU-FR). EU 단일 세그먼트는 금지, 반드시 국가 단위로 지정')
if (!SEGMENT) throw new Error('args.segment가 필요합니다: 타깃 세그먼트 설명')
if (TIER !== 1 && TIER !== 2 && TIER !== 3) throw new Error('args.tier가 필요합니다: 1 | 2 | 3')
if (!GOAL) throw new Error('args.goal이 필요합니다: 캠페인 목표')
if (!DATE || !/^\d{4}-\d{2}-\d{2}$/.test(DATE)) throw new Error('args.date가 필요합니다: YYYY-MM-DD 형식의 오늘 날짜')

const DATE8 = DATE.replace(/-/g, '')
const REGION_LC = REGION.toLowerCase()
// KB09 회피 등급 국가(콜드 메일 금지, 대체 채널만). 한국은 G7에 따라 기본값이 대체 채널.
const AVOID_REGIONS = ['EU-DE', 'EU-AT', 'EU-IT', 'EU-ES', 'EU-PL']
const FORCE_ALT = AVOID_REGIONS.indexOf(REGION) >= 0

const BRIEF_SCHEMA = {
  type: 'object', required: ['campaign_slug', 'icp_status', 'track', 'brief_file', 'summary', 'po_queue'],
  properties: {
    campaign_slug: { type: 'string', description: '캠페인 영문 슬러그(소문자, 숫자, 하이픈만. 예: us-asset-mgmt-research)' },
    icp_status: { type: 'string', enum: ['PO승인', '초안', '없음'], description: 'ICP 문서에 PO 승인 서명과 승인일이 있는가' },
    track: { type: 'string', enum: ['cold-email', 'alt-channel'], description: '콜드 메일 트랙 또는 대체 채널 트랙' },
    brief_file: { type: 'string', description: '저장한 브리프 파일 경로' },
    summary: { type: 'string', description: '브리프 요지(목표, 플레이북, 티어, 성공 지표)' },
    po_queue: { type: 'array', items: { type: 'string' }, description: 'PO 의사결정 대기 항목(ICP 관련, 앵글 선택 등)' },
  },
}

const LIST_SCHEMA = {
  type: 'object', required: ['list_file', 'record_count', 'held_count', 'research_files', 'angle_candidates', 'summary'],
  properties: {
    list_file: { type: 'string', description: '저장한 리스트 파일 경로' },
    record_count: { type: 'integer', description: '검증 통과 레코드 수' },
    held_count: { type: 'integer', description: '시그널 없음으로 발송 보류 판정한 레코드 수(해제는 PO만 가능)' },
    research_files: { type: 'array', items: { type: 'string' }, description: 'Tier 1~2 계정 리서치 산출물 경로' },
    angle_candidates: { type: 'array', items: { type: 'string' }, description: '공략 앵글 후보(선택은 PO)' },
    summary: { type: 'string' },
  },
}

const TOUCHMAP_SCHEMA = {
  type: 'object', required: ['touchmap_file', 'email_touches', 'other_slots', 'moved_to_alt', 'alt_play_file', 'summary'],
  properties: {
    touchmap_file: { type: 'string', description: '저장한 터치맵 파일 경로' },
    email_touches: { type: 'integer', description: '이메일 터치 수(3~4가 표준)' },
    other_slots: { type: 'integer', description: 'LinkedIn/전화 슬롯 수' },
    moved_to_alt: { type: 'integer', description: '대체 채널 플레이로 이관한 레코드 수' },
    alt_play_file: { type: 'string', description: 'alt-channel-play 파일 경로(없으면 빈 문자열)' },
    summary: { type: 'string' },
  },
}

const COPY_SCHEMA = {
  type: 'object', required: ['copy_file', 'summary', 'evidence_notes'],
  properties: {
    copy_file: { type: 'string', description: '저장한 카피 파일 경로' },
    summary: { type: 'string', description: '카피 구성 요약(터치별 채널과 앵글)' },
    evidence_notes: { type: 'array', items: { type: 'string' }, description: '인용한 증거 카드/출처와 KB08 신뢰 등급' },
  },
}

const QA_SCHEMA = {
  type: 'object', required: ['verdict', 'failures', 'record_file', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    failures: {
      type: 'array',
      items: {
        type: 'object', required: ['item', 'reason'],
        properties: {
          item: { type: 'string', description: '실패 항목(11항목/구조/팩트체크/네이티브 톤)' },
          reason: { type: 'string', description: '반려 사유와 수정 방향' },
        },
      },
      description: 'FAIL 사유 목록(PASS면 빈 배열)',
    },
    record_file: { type: 'string', description: '저장한 검수 기록 파일 경로' },
    summary: { type: 'string' },
  },
}

const COMPLIANCE_SCHEMA = {
  type: 'object', required: ['verdict', 'gate_a', 'gate_b', 'gate_c', 'excluded', 'held_for_legal', 'remaining_count', 'lia_file', 'record_file', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'PARTIAL', 'FAIL'], description: 'PASS: 전건 통과, PARTIAL: 제외/보류 후 잔여 레코드로 부분 진행, FAIL: 캠페인 중단' },
    gate_a: { type: 'string', enum: ['PASS', 'FAIL'], description: '게이트 A(리스트): 관할 매트릭스, 증빙, 보관기간, EU 역외 이전 체크' },
    gate_b: { type: 'string', enum: ['PASS', 'FAIL'], description: '게이트 B(메시지): 국가별 필수 표기, GDPR 제14조 고지, 푸터' },
    gate_c: { type: 'string', enum: ['PASS', 'FAIL'], description: '게이트 C(운영): suppression 대조, 수신거부 처리 플로우' },
    excluded: {
      type: 'array',
      items: {
        type: 'object', required: ['record', 'reason'],
        properties: {
          record: { type: 'string', description: '제외 레코드 식별자' },
          reason: { type: 'string', description: '제외 사유(회피 등급/관할 불명/증빙 누락/보관기간 만료/suppression 등재 등)' },
        },
      },
      description: '발송 큐에서 제외한 레코드(없으면 빈 배열)',
    },
    held_for_legal: {
      type: 'array',
      items: {
        type: 'object', required: ['record', 'issue'],
        properties: {
          record: { type: 'string' },
          issue: { type: 'string', description: 'legal-team 에스컬레이션 쟁점' },
        },
      },
      description: '경계 사안으로 분리 보류한 레코드(legal-team 회신 전 발송 금지, 없으면 빈 배열)',
    },
    remaining_count: { type: 'integer', description: '제외/보류 후 발송 큐에 남은 레코드 수' },
    lia_file: { type: 'string', description: 'EU/영국 레코드 포함 시 작성한 LIA 초안 경로(해당 없으면 빈 문자열)' },
    record_file: { type: 'string', description: '게이트 판정 기록 파일 경로(docs/sales/compliance/)' },
    summary: { type: 'string' },
  },
}

const PREFLIGHT_SCHEMA = {
  type: 'object', required: ['verdict', 'safeguards_verified', 'blockers', 'schedule_file', 'record_file', 'summary'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    safeguards_verified: { type: 'boolean', description: '발송 도구 안전장치 4종(답장 자동 중단/하드바운스 자동 억제/suppression 동기화/임계 초과 자동 중단) 설정 검증 여부' },
    blockers: { type: 'array', items: { type: 'string' }, description: 'FAIL 사유(웜업 미완, 한도 부족, 바운스 예측 2% 이상, 안전장치 미설정 등)' },
    schedule_file: { type: 'string', description: '발송 스케줄 파일 경로(FAIL이면 빈 문자열)' },
    record_file: { type: 'string', description: '프리플라이트 점검 기록 파일 경로' },
    summary: { type: 'string' },
  },
}

log('콜드 아웃리치 캠페인 시작: ' + REGION + ' / ' + SEGMENT + ' / Tier ' + TIER + (FORCE_ALT ? ' [회피 등급 국가: 대체 채널 트랙 강제]' : ''))

// ── 1. 캠페인 브리프 ─────────────────────────────────────────
const brief = await agent([
  '콜드 아웃리치 캠페인 브리프를 작성하라. 시작 전에 kb/sales/07-sales-team-ops.md, kb/sales/08-oneline-ai-context.md, kb/sales/04-sales-methodology.md, kb/sales/09-global-outreach-compliance.md를 읽어라.',
  '[지역] ' + REGION + ' / [세그먼트] ' + SEGMENT + ' / [티어] ' + TIER + ' / [목표] ' + GOAL,
  '[리스트 출처] ' + LIST_SOURCE,
  '[오늘] ' + DATE,
  '',
  '착수 조건 검사(모두 브리프에 기록):',
  '1) ICP 문서 확인: docs/sales/ 또는 kb/sales/03-prospecting-icp.md 기반 ICP 문서에 PO 승인 서명과 승인일이 있는지 확인하라. 초안 상태면 icp_status를 "초안"으로 판정하라(착수 중단 사유).',
  '2) 트랙 분기: region이 회피 등급 국가(독일, 오스트리아, 이탈리아, 스페인, 폴란드)이거나 한국이면 콜드 메일 트랙 대신 대체 채널 트랙(alt-channel)을 선언하라. 한국은 G7에 따라 기본값이 대체 채널이며, KB06 A/B 유형(1:1 제휴 문의) 소량 수동 발송만 예외 후보다.',
  FORCE_ALT ? '주의: 이 region은 회피 등급 국가다. track은 반드시 alt-channel이어야 한다.' : '',
  '',
  'campaign_slug(영문 소문자/숫자/하이픈)를 정하고, 브리프를 templates/sales/campaign-brief.md 구조로',
  'docs/sales/campaigns/' + DATE8 + '-' + REGION_LC + '-<campaign_slug>/campaign-brief.md 에 저장하라.',
  '지역 플레이북 선택, 티어 배정, 성공 지표를 포함하고, PO 의사결정 대기 항목(ICP 확정, 앵글 선택 등)을 po_queue에 담아라.',
].join('\n'), { label: 'lead:브리프', phase: '캠페인 브리프', agentType: 'sales-lead', schema: BRIEF_SCHEMA })

if (!brief) throw new Error('캠페인 브리프 작성 실패')

const SLUG = (brief.campaign_slug || '').toLowerCase().replace(/[^a-z0-9-]/g, '') || 'campaign'
const CAMPAIGN_ID = DATE8 + '-' + REGION_LC + '-' + SLUG
const CAMP_DIR = 'docs/sales/campaigns/' + CAMPAIGN_ID
const OUTBOX_DIR = 'docs/sales/outbox/' + CAMPAIGN_ID
const COMP_DIR = 'docs/sales/compliance'
const ALT_TRACK = FORCE_ALT || brief.track === 'alt-channel'

log('캠페인 ID: ' + CAMPAIGN_ID + ' / 트랙: ' + (ALT_TRACK ? 'alt-channel' : 'cold-email') + ' / ICP: ' + brief.icp_status)

// 착수 조건 fail-closed: PO 승인 서명 없는 ICP는 캠페인 착수 불가
if (brief.icp_status !== 'PO승인') {
  log('착수 중단: ICP 문서가 PO 승인 상태가 아님(' + brief.icp_status + ')')
  return {
    status: 'blocked',
    campaign_id: CAMPAIGN_ID,
    reason: 'ICP 문서가 ' + brief.icp_status + ' 상태다. PO 승인 서명이 있는 ICP 없이는 캠페인 착수 조건 불충족(G1).',
    artifacts: { brief: brief.brief_file },
    po_todo: [
      'ICP 문서 검토 후 승인 서명과 승인일 기록 (prospect-researcher 초안 기준)',
      '승인 후 cold-outreach-campaign 재실행',
    ].concat(brief.po_queue || []),
  }
}

// ── 2. 리스트 구축 ───────────────────────────────────────────
const list = await agent([
  '캠페인 리스트를 구축하고 검증하라. 시작 전에 kb/sales/03-prospecting-icp.md, kb/sales/09-global-outreach-compliance.md, kb/sales/08-oneline-ai-context.md를 읽어라.',
  '[캠페인 브리프] ' + brief.brief_file + ' (Read로 읽을 것)',
  '[브리프 요지] ' + brief.summary,
  '[지역] ' + REGION + ' / [세그먼트] ' + SEGMENT + ' / [티어] ' + TIER,
  '[리스트 출처] ' + LIST_SOURCE,
  '',
  '요구사항:',
  '- 모든 레코드에 jurisdiction(국가 단위, EU 단일 세그먼트 금지), 수집 출처, 수집일, 시그널 필드를 태깅하라(G9 스키마 게이트). 필드가 빈 레코드는 리스트에 넣지 마라.',
  '- 전역 suppression 리스트(docs/sales/compliance/ 아래)와 대조해 등재 레코드를 제외하라.',
  '- Anti-ICP 필터를 적용하라(제외 규칙의 신설/변경은 PO 승인 항목이므로 제안만 하라).',
  '- Tier 1~2 계정 전건에 templates/sales/account-research.md 포맷(시그널, 가설, 타깃 인물, 훅 1문장, 배제 확인)으로 리서치 산출물을 작성하라. 시그널 없는 계정은 발송 보류로 판정하라(보류 해제는 PO만 가능, G4).',
  '- 공략 앵글 후보를 제시하라. 앵글 선택은 PO 몫이다.',
  '',
  '리스트는 ' + CAMP_DIR + '/prospect-list.md 에, 계정 리서치는 ' + CAMP_DIR + '/research/ 아래에 저장하라.',
].join('\n'), { label: 'researcher:리스트', phase: '리스트 구축', agentType: 'prospect-researcher', schema: LIST_SCHEMA })

if (!list) throw new Error('리스트 구축 실패')
log('리스트: 검증 통과 ' + list.record_count + '건, 시그널 보류 ' + list.held_count + '건')

// ── 3. 터치맵 설계 ───────────────────────────────────────────
const touchmap = await agent([
  '캠페인 멀티채널 터치맵을 설계하라. 시작 전에 kb/sales/01-cold-email-craft.md, kb/sales/09-global-outreach-compliance.md, kb/sales/06-kr-outreach-compliance.md, kb/sales/08-oneline-ai-context.md를 읽어라.',
  '[캠페인 브리프] ' + brief.brief_file + ' / [리스트] ' + list.list_file + ' (모두 Read로 읽을 것)',
  '[지역] ' + REGION + ' / [트랙] ' + (ALT_TRACK ? 'alt-channel(콜드 메일 금지)' : 'cold-email'),
  '',
  ALT_TRACK
    ? [
      '이 캠페인은 대체 채널 트랙이다. templates/sales/alt-channel-play.md 구조로 대체 채널 플레이를 작성하라:',
      '- LinkedIn 커넥션/InMail 시퀀스, 전시회/이벤트 접점, 파트너 루트(핑거, 민카부 등 KB08 파트너 채널 계정 맵 반영), 콜드 메일 금지 근거 표기.',
      REGION === 'KR' ? '- 한국: 소개 요청 시스템화, NextRise/AI EXPO 리드 파이프라인, 정부 바우처/조달 공고 연계, SI/클라우드 마켓플레이스 파트너십을 포함하라.' : '',
      REGION === 'JP' ? '- 일본: 민카부 채널 우선, 콜드메일 단독 모션 지양 원칙(KB08)을 반영하라.' : '',
      '- 실행 주체는 전부 PO이며, 수신자 현지 업무시간 창을 반영한 PO 실행 캘린더를 포함하라.',
      '산출물을 ' + CAMP_DIR + '/alt-channel-play.md 에 저장하고, touchmap_file에도 같은 경로를 넣어라.',
    ].join('\n')
    : [
      'templates/sales/multichannel-sequence.md 구조로 Day-by-Day 터치맵을 작성하라(G11 시퀀스 구조 게이트):',
      '- 이메일 3~4통 + LinkedIn/전화 슬롯이 표준. 이메일 단독 5터치 이상은 금지.',
      '- 첫 5일 집중 배치, 답장 없는 상대 이메일 8통 상한, 같은 날 같은 채널 중복 금지.',
      '- 터치별 실행 주체를 명기하라: 이메일=발송 도구, LinkedIn/전화=PO.',
      '- LinkedIn/전화 터치는 수신자 현지 업무시간 창에 배치한 PO 실행 캘린더를 포함하라.',
      '- 리스트에 회피 등급 국가 레코드가 섞여 있으면 alt-channel-play(' + CAMP_DIR + '/alt-channel-play.md, templates/sales/alt-channel-play.md 구조)로 이관하고 콜드 메일 큐에서 제거하라.',
      REGION === 'JP' ? '- 일본: 민카부 파트너 채널을 우선 접점으로 반영하고 콜드메일 단독 모션은 지양하라(KB08).' : '',
      '터치맵을 ' + CAMP_DIR + '/touchmap.md 에 저장하라.',
    ].join('\n'),
].join('\n'), { label: 'strategist:터치맵', phase: '터치맵 설계', agentType: 'channel-strategist', schema: TOUCHMAP_SCHEMA })

if (!touchmap) throw new Error('터치맵 설계 실패')
log('터치맵: 이메일 ' + touchmap.email_touches + '통 + 기타 슬롯 ' + touchmap.other_slots + ', alt 이관 ' + touchmap.moved_to_alt + '건')

// ── 4~5. 카피 작성 → QA 게이트 (반려 루프 최대 2회) ─────────
const copyPromptBase = [
  '터치맵의 전 채널 카피를 작성하라. 시작 전에 kb/sales/01-cold-email-craft.md, kb/sales/09-global-outreach-compliance.md, kb/sales/08-oneline-ai-context.md, kb/sales/05-ai-saas-sales.md를 읽어라.',
  '[터치맵] ' + touchmap.touchmap_file + ' / [리스트] ' + list.list_file + ' / [계정 리서치] ' + CAMP_DIR + '/research/ (모두 Read로 읽을 것)',
  '[지역] ' + REGION + ' / [앵글 후보] ' + (list.angle_candidates || []).join(' | '),
  '',
  '작성 범위(터치맵의 모든 슬롯):',
  '- 영문 이메일: 제목줄 후보 3개(2~6단어, internal camouflage), 본문 50~125단어(PAS/BAB/브레이크업), interest-based CTA 정확히 1개, 링크 0~1개.',
  '- LinkedIn 커넥션 노트와 DM, 콜 오프닝과 20초 보이스메일 스크립트.',
  '- 스레드 전략(전반부 스레드 유지, 브레이크업/앵글 전환 시 새 스레드), 국가별 푸터 변형(미국 물리 주소, EU 첫 메일 GDPR 제14조 고지 + 프라이버시 노티스 링크, 일본 법인 정식명).',
  REGION === 'KR' ? '- 한국 수신자 카피는 국가별 템플릿 변형이 아니다: A/B 유형(1:1 제휴 문의)도 수신자 1명당 건별 개별 작성을 강제한다. 리서치 산출물 기반으로 수신자별로 따로 써라.' : '',
  '- A/B 테스트 변형은 단일 변수로만.',
  '- 사실 주장(수치, 고객명, 성과)은 templates/sales/evidence-card.md 기반 검증된 증거 카드와 KB08 [확인] 등급만 인용하라. 미검증 주장은 쓰지 마라.',
  '',
  '카피를 templates/sales/multichannel-sequence.md의 카피 섹션 구조로 ' + CAMP_DIR + '/copy.md 에 저장하라.',
].join('\n')

let copy = await agent(copyPromptBase, { label: 'writer:카피', phase: '카피 작성', agentType: 'cold-email-writer', schema: COPY_SCHEMA })
if (!copy) throw new Error('카피 작성 실패')

const qaPrompt = function (attempt) {
  return [
    '발송 전 QA 게이트를 fail-closed로 판정하라. 시작 전에 kb/sales/01-cold-email-craft.md, kb/sales/08-oneline-ai-context.md, kb/sales/05-ai-saas-sales.md를 읽어라.',
    '[검수 대상 카피] ' + copy.copy_file + ' / [터치맵] ' + touchmap.touchmap_file + ' (모두 Read로 읽을 것)',
    '[검수 회차] ' + attempt,
    '',
    '판정 기준(하나라도 미달이면 FAIL):',
    '- KB01 §13 11항목 게이트: 시그널 존재, 제목줄 2~6단어, 본문 50~125단어, you:I 비율, CTA 정확히 1개, 안티패턴 0건, 링크 0~1개 등. 전 채널 카피(이메일, LinkedIn 노트/DM, 콜/보이스메일 스크립트) 대상.',
    '- 시퀀스 구조: 이메일 단독 5터치 이상이면 구조 자체를 반려, 이메일 8통 상한, 같은 날 같은 채널 중복 검사.',
    '- 팩트체크: 모든 수치/고객명/성과 주장을 KB08 신뢰 등급([확인] 등급만 사실 진술 가능)과 원출처에 대조. 미검증 수치 1개라도 있으면 FAIL. 환각 훅(존재하지 않는 보도 인용 등) 검증.',
    '- 영어 네이티브 관용성과 톤: 문법상 맞지만 어색한 영어는 반려하라.',
    '',
    '검수 기록을 ' + CAMP_DIR + '/qa-review-' + attempt + '.md 에 저장하라. FAIL이면 항목별 반려 사유와 수정 방향을 failures에 담아라.',
  ].join('\n')
}

let qa = await agent(qaPrompt(1), { label: 'qa:1차', phase: 'QA 게이트', agentType: 'outreach-qa', schema: QA_SCHEMA })
if (!qa) throw new Error('QA 게이트 판정 실패')

let rewrites = 0
while (qa && qa.verdict === 'FAIL' && rewrites < 2) {
  rewrites += 1
  log('QA FAIL(' + rewrites + '차 반려): ' + qa.failures.map(f => f.item).join(', ') + ' / 카피 수정 재작성')
  copy = await agent([
    copyPromptBase,
    '',
    '[반려] outreach-qa가 다음 사유로 FAIL 판정했다(' + rewrites + '차 반려). 지적을 전부 반영해 카피를 수정하고 같은 경로에 다시 저장하라. 검수 기록도 읽어라: ' + qa.record_file,
    qa.failures.map(f => '- [' + f.item + '] ' + f.reason).join('\n'),
  ].join('\n'), { label: 'writer:수정' + rewrites, phase: '카피 작성', agentType: 'cold-email-writer', schema: COPY_SCHEMA })
  if (!copy) throw new Error('카피 수정 실패')
  qa = await agent(qaPrompt(rewrites + 1), { label: 'qa:' + (rewrites + 1) + '차', phase: 'QA 게이트', agentType: 'outreach-qa', schema: QA_SCHEMA })
  if (!qa) throw new Error('QA 게이트 재판정 실패')
}

if (qa.verdict === 'FAIL') {
  log('QA 최종 FAIL: 반려 루프 2회 소진, 캠페인 재설계로 전환')
  const redesign = await agent([
    'QA 게이트가 반려 루프 2회 후에도 FAIL이다. 캠페인 재설계 보고를 작성하라.',
    '[브리프] ' + brief.brief_file + ' / [터치맵] ' + touchmap.touchmap_file + ' / [최종 카피] ' + copy.copy_file + ' / [QA 기록] ' + qa.record_file + ' (모두 Read로 읽을 것)',
    '[최종 FAIL 사유] ' + qa.failures.map(f => '[' + f.item + '] ' + f.reason).join(' | '),
    '',
    '반복 FAIL의 구조적 원인(세그먼트/앵글/증거 부족/시퀀스 설계)을 진단하고, 재설계 방향(타깃 조정, 앵글 교체, 증거 카드 보강, 트랙 전환)을 제시하라.',
    '보고서를 ' + CAMP_DIR + '/redesign-report.md 에 저장하고 저장 경로와 3문장 요지를 반환하라.',
  ].join('\n'), { label: 'lead:재설계', phase: 'QA 게이트', agentType: 'sales-lead' })
  return {
    status: 'failed',
    campaign_id: CAMPAIGN_ID,
    reason: 'QA 게이트 최종 FAIL(반려 2회 소진). 발송 패키지는 조립되지 않았다(fail-closed).',
    qa_failures: qa.failures,
    artifacts: { brief: brief.brief_file, list: list.list_file, touchmap: touchmap.touchmap_file, copy: copy.copy_file, qa_record: qa.record_file, redesign_report: CAMP_DIR + '/redesign-report.md' },
    redesign: redesign,
    po_todo: [
      '재설계 보고(' + CAMP_DIR + '/redesign-report.md) 검토 후 재설계 방향 승인',
      '승인 후 cold-outreach-campaign 재실행',
    ],
  }
}
log('QA 게이트 PASS (반려 ' + rewrites + '회)')

// ── 6. 컴플라이언스 게이트 ───────────────────────────────────
const compliance = await agent([
  '발송 전 3층 컴플라이언스 게이트를 fail-closed로 심사하라. 시작 전에 kb/sales/09-global-outreach-compliance.md, kb/sales/06-kr-outreach-compliance.md, kb/sales/02-deliverability.md를 읽어라.',
  '[리스트] ' + list.list_file + ' / [터치맵] ' + touchmap.touchmap_file + ' / [카피] ' + copy.copy_file + ' (모두 Read로 읽을 것)',
  '[지역] ' + REGION + ' / [오늘] ' + DATE,
  '',
  '심사 항목:',
  '- 게이트 A(리스트): 국가별 가능/조건부/회피 매트릭스 판정, 레코드별 관할/출처/증빙 확인, EU 프로스펙트 보관기간(마지막 접촉 3년) 내 데이터인지 확인하고 만료 도래 레코드는 삭제/익명화 지시. EU 레코드의 역외 이전 체크: 이메일 검증 도구 사용 시 EU 리전 처리 또는 SCC, DPA 체결 확인.',
  '- 게이트 B(메시지): 관할별 필수 표기(CAN-SPAM 물리 주소/수신거부, EU 첫 메일 GDPR 제14조 고지 요소, PECR, 일본 특정전자메일법 표기), 카피의 국가별 푸터 확인.',
  '- 게이트 C(운영): 전역 suppression 대조 완료, 수신거부 처리 플로우, 우회 불가 원칙.',
  '- 한국 수신자가 1명이라도 있으면 KB06 §8 게이트를 별도 적용하라: 템플릿 대량 발송(C/D 유형)은 무조건 반려, A/B 유형(1:1 제휴 문의)만 소량 수동 발송 후보.',
  '- EU/영국 레코드가 있으면 templates/sales/lia-record.md 구조로 LIA 초안(3단 테스트: 목적 정당성/필요성/이익형량)을 ' + COMP_DIR + '/' + CAMPAIGN_ID + '-lia.md 에 작성하고 PO 승인 상신 항목으로 표시하라. LIA 없음을 이유로 게이트를 형식 통과시키는 것은 금지다(G10).',
  '',
  '판정 규칙:',
  '- 회피 등급/관할 불명/증빙 누락/보관기간 만료/suppression 등재 레코드는 발송 큐에서 제외하라(excluded에 사유와 함께 기록). 회피 등급 레코드는 channel-strategist의 alt-channel-play 이관 대상으로 표시하라.',
  '- 경계 사안(규제 해석이 갈리는 레코드/문안)은 legal-team 에스컬레이션 대상으로 held_for_legal에 분리 보류하라. 회신 대기가 캠페인 전체를 막지 않는다: 잔여 레코드로 부분 진행(PARTIAL)한다.',
  '- 잔여 레코드가 0이거나 게이트 B/C가 구조적으로 FAIL이면 verdict를 FAIL로 하라.',
  '',
  '게이트 판정 기록을 templates/sales/compliance-gate.md 구조로 ' + COMP_DIR + '/' + CAMPAIGN_ID + '-gate.md 에 저장하라(감사 대비 보존).',
].join('\n'), { label: 'compliance:게이트', phase: '컴플라이언스 게이트', agentType: 'sales-compliance-officer', schema: COMPLIANCE_SCHEMA })

if (!compliance) throw new Error('컴플라이언스 게이트 심사 실패')
log('컴플라이언스: ' + compliance.verdict + ' (A ' + compliance.gate_a + ' / B ' + compliance.gate_b + ' / C ' + compliance.gate_c + ') 제외 ' + compliance.excluded.length + '건, 보류 ' + compliance.held_for_legal.length + '건, 잔여 ' + compliance.remaining_count + '건')

if (compliance.verdict === 'FAIL' || compliance.remaining_count === 0) {
  return {
    status: 'failed',
    campaign_id: CAMPAIGN_ID,
    reason: '컴플라이언스 게이트 FAIL 또는 잔여 레코드 0건. 발송 패키지는 조립되지 않았다(fail-closed, G2).',
    compliance: { verdict: compliance.verdict, gate_a: compliance.gate_a, gate_b: compliance.gate_b, gate_c: compliance.gate_c, excluded: compliance.excluded, held_for_legal: compliance.held_for_legal },
    artifacts: { brief: brief.brief_file, list: list.list_file, touchmap: touchmap.touchmap_file, copy: copy.copy_file, gate_record: compliance.record_file, lia: compliance.lia_file },
    po_todo: [
      '게이트 판정 기록(' + compliance.record_file + ') 검토',
      compliance.held_for_legal.length ? 'legal-team 에스컬레이션 회신 확인 후 보류 레코드 처리' : '',
      '제외 사유 해소(리스트 재구축 또는 대체 채널 전환) 후 재실행',
    ].filter(Boolean),
  }
}

// ── 7. 딜리버러빌리티 프리플라이트 (콜드 메일 트랙만) ────────
let preflight = null
if (!ALT_TRACK) {
  preflight = await agent([
    '캠페인 발송 프리플라이트를 점검하라. 시작 전에 kb/sales/02-deliverability.md, kb/sales/01-cold-email-craft.md를 읽어라. 최신 인프라 상태는 docs/sales/infra/ 와 reports/sales/ 의 인프라 준비 보고를 참조하라.',
    '[리스트] ' + list.list_file + ' / [터치맵] ' + touchmap.touchmap_file + ' / [컴플라이언스 잔여 레코드] ' + compliance.remaining_count + '건 (게이트 기록: ' + compliance.record_file + ')',
    '',
    '점검 항목(하나라도 미충족이면 FAIL, 발송 스케줄 배정 불가):',
    '- 발신 계정 웜업 완료 상태, 일일 한도 잔여(메일박스당 20~50통).',
    '- 리스트 100% 검증: 예상 바운스 2% 미만, catch-all/role 계정 제외.',
    '- mail-tester/배치 테스트 결과, 플레인 텍스트/첨부 0.',
    '- 발송 도구 안전장치 설정 검증: 답장 감지 시 해당 수신자 시퀀스 자동 중단, 하드바운스 자동 suppression 등록, 마스터 suppression 리스트와 양방향 동기화, 바운스/신고 임계 초과 시 자동 발송 중단. 설정 적용은 PO 몫이고 검증은 네 몫이다. 미설정/미검증이면 FAIL.',
    '',
    'PASS면 수신자 시간대 평일 업무시간 기준 발송 스케줄을 ' + CAMP_DIR + '/send-schedule.md 에 작성하라.',
    '점검 기록을 ' + CAMP_DIR + '/preflight.md 에 저장하라.',
  ].join('\n'), { label: 'deliverability:프리플라이트', phase: '딜리버러빌리티 프리플라이트', agentType: 'deliverability-engineer', schema: PREFLIGHT_SCHEMA })

  if (!preflight) throw new Error('프리플라이트 점검 실패')
  log('프리플라이트: ' + preflight.verdict + (preflight.blockers.length ? ' / 차단: ' + preflight.blockers.join('; ') : ''))

  if (preflight.verdict === 'FAIL') {
    return {
      status: 'failed',
      campaign_id: CAMPAIGN_ID,
      reason: '딜리버러빌리티 프리플라이트 FAIL. 발송 스케줄 미배정, 발송 패키지는 조립되지 않았다(fail-closed, G5).',
      blockers: preflight.blockers,
      artifacts: { brief: brief.brief_file, list: list.list_file, touchmap: touchmap.touchmap_file, copy: copy.copy_file, gate_record: compliance.record_file, preflight_record: preflight.record_file },
      po_todo: [
        '차단 항목 해소: ' + preflight.blockers.join(' | '),
        '인프라 미비면 outreach-infra-setup 워크플로 실행/재점검',
        '발송 도구 안전장치 4종 설정 적용(적용 후 deliverability-engineer 재검증 필요)',
        '해소 후 cold-outreach-campaign 재실행',
      ],
    }
  }
} else {
  log('대체 채널 트랙: 콜드 메일 발송이 없으므로 딜리버러빌리티 프리플라이트 생략')
}

// ── 8. 발송 패키지 조립 ──────────────────────────────────────
// 터치 2~N 릴리스 조건: 워크플로 1회 실행 안에서 터치별 게이트를 반복할 수 없으므로
// 조건을 패키지에 명문화하고, 실제 판정은 sales-ops-review daily 모드가 수행한다.
const RELEASE_CONDITIONS = [
  '터치 2~N 릴리스 조건(각 후속 터치 발송 예정일마다, 워크플로가 아니라 sales-ops-review daily 모드로 판정):',
  '1) sales-ops-analyst: 답장 로그 분류(긍정/부정/OOO/수신거부성) 갱신과 시퀀스 제외 목록 반영',
  '2) sales-compliance-officer: suppression 델타 재대조. 수신거부/답장/하드바운스/스팸 신고 발생 레코드의 전 채널 시퀀스 제외 확인',
  '3) deliverability-engineer: 발송 도구 suppression 동기화 상태, 잔여 일일 한도, 직전 터치 지표 이상 여부 확인',
  '4) templates/sales/touch-release-checklist.md 기반 PASS 기록이 ' + COMP_DIR + '/ 에 남지 않은 터치는 발송 불가(fail-closed)',
  '5) 캠페인 개시와 볼륨 증량 후 3일간 sales-ops-review daily 모드 필수 실행(KB02 §6.2)',
].join('\n')

const pkg = await agent([
  '발송 패키지를 조립하고 PO 승인 요청 상태로 만들라. templates/sales/send-package.md 구조를 따르라.',
  '게이트 3종 판정: QA PASS(반려 ' + rewrites + '회) / 컴플라이언스 ' + compliance.verdict + ' / 딜리버러빌리티 ' + (ALT_TRACK ? '해당 없음(alt-channel 트랙)' : preflight.verdict),
  '',
  '포함할 것(각 파일을 Read로 확인하고 요약/링크로 조립):',
  '- 최종 카피(전 채널): ' + copy.copy_file,
  '- 터치맵: ' + touchmap.touchmap_file + (touchmap.alt_play_file ? ' / alt-channel-play: ' + touchmap.alt_play_file : ''),
  '- 리스트 요약: ' + list.list_file + ' (잔여 ' + compliance.remaining_count + '건, 제외 ' + compliance.excluded.length + '건, legal 보류 ' + compliance.held_for_legal.length + '건, 시그널 보류 ' + list.held_count + '건)',
  '- 게이트 통과 기록: QA ' + qa.record_file + ' / 컴플라이언스 ' + compliance.record_file + (preflight ? ' / 프리플라이트 ' + preflight.record_file : ''),
  compliance.lia_file ? '- LIA 초안(PO 승인 대기): ' + compliance.lia_file : '',
  preflight ? '- 발송 스케줄: ' + preflight.schedule_file : '- 발송 스케줄: 해당 없음(alt-channel 트랙, PO 실행 캘린더는 터치맵 참조)',
  '',
  '[터치 2~N 릴리스 조건: 패키지에 그대로 수록할 것]',
  RELEASE_CONDITIONS,
  '',
  'PO 승인란(캠페인 발송 승인, LIA 승인, 보류 레코드 판정)을 비워 두고, 실제 발송과 LinkedIn/전화 터치 실행은 PO가 한다는 것을 명기하라.',
  '패키지를 ' + OUTBOX_DIR + '/send-package.md 에 저장하고 저장 경로와 3문장 요지를 반환하라.',
].join('\n'), { label: 'lead:패키지', phase: '발송 패키지 조립', agentType: 'sales-lead' })

// ── 10. 캠페인 레코드 ────────────────────────────────────────
const record = await agent([
  '캠페인 레코드를 생성하고 지표 추적을 세팅하라. kb/sales/07-sales-team-ops.md를 참조하라.',
  '[캠페인 ID] ' + CAMPAIGN_ID + ' / [발송 패키지] ' + OUTBOX_DIR + '/send-package.md (Read로 읽을 것)',
  '[목표] ' + GOAL + ' / [잔여 레코드] ' + compliance.remaining_count + '건',
  '',
  '할 일:',
  '- 캠페인 레코드(필수 필드: 관할, 수집 출처, 동의/수신 근거, 시그널, 검증일, LIA ID, 보관기간 만료일)를 ' + CAMP_DIR + '/campaign-record.md 에 생성하라.',
  '- 3층 지표(활동/파이프라인/결과) 추적 항목과 A/B 실험 로그 틀을 세팅하라. 성과 판정 기준은 발송량이 아니라 긍정 답장과 기회 생성이다.',
  '- 격주 회고 일정(templates/sales/campaign-retro.md 사용 예정)과 발송 활성 기간 매 영업일 sales-ops-review daily 실행 일정을 기록하라.',
  '저장 경로와 세팅 요약을 반환하라.',
].join('\n'), { label: 'ops:레코드', phase: '캠페인 레코드', agentType: 'sales-ops-analyst' })

log('캠페인 준비 완료: PO 승인 대기 (' + OUTBOX_DIR + '/send-package.md)')

return {
  status: 'ready_for_po_approval',
  campaign_id: CAMPAIGN_ID,
  track: ALT_TRACK ? 'alt-channel' : 'cold-email',
  gates: {
    qa: 'PASS (반려 ' + rewrites + '회)',
    compliance: compliance.verdict + ' (제외 ' + compliance.excluded.length + '건, legal 보류 ' + compliance.held_for_legal.length + '건, 잔여 ' + compliance.remaining_count + '건)',
    deliverability: ALT_TRACK ? '해당 없음(alt-channel)' : preflight.verdict,
  },
  artifacts: {
    send_package: OUTBOX_DIR + '/send-package.md',
    brief: brief.brief_file,
    list: list.list_file,
    touchmap: touchmap.touchmap_file,
    alt_channel_play: touchmap.alt_play_file || null,
    copy: copy.copy_file,
    qa_record: qa.record_file,
    compliance_gate_record: compliance.record_file,
    lia: compliance.lia_file || null,
    preflight_record: preflight ? preflight.record_file : null,
    send_schedule: preflight ? preflight.schedule_file : null,
    campaign_record: CAMP_DIR + '/campaign-record.md',
  },
  touch_release_guidance: '후속 터치(터치 2~N) 릴리스는 이 워크플로에서 반복 실행할 수 없다. 각 후속 터치 발송 예정일마다 sales-ops-review를 daily 모드로 실행해 터치 릴리스 게이트(suppression 델타 재대조, 발송 도구 동기화, 잔여 일일 한도, 직전 터치 지표)를 판정하라. touch-release-checklist PASS 기록 없이 해당 터치는 발송 불가이며, 캠페인 개시와 볼륨 증량 후 3일간 daily 모드는 필수다(KB02 §6.2).',
  po_todo: [
    '발송 패키지 검토와 발송 승인: ' + OUTBOX_DIR + '/send-package.md',
    compliance.lia_file ? 'LIA 승인: ' + compliance.lia_file : '',
    '발송 실행(발송 도구) 및 LinkedIn/전화 터치 실행(터치맵의 PO 실행 캘린더 참조)',
    list.held_count ? '시그널 보류 ' + list.held_count + '건 해제 여부 판정(보류 해제는 PO만 가능)' : '',
    compliance.held_for_legal.length ? 'legal-team 에스컬레이션 회신 확인 후 보류 레코드 ' + compliance.held_for_legal.length + '건 처리' : '',
    '공략 앵글 확정: ' + (list.angle_candidates || []).join(' | '),
    '개시 후 3일간 매 영업일 sales-ops-review daily 모드 실행(campaigns: ["' + CAMPAIGN_ID + '"])',
  ].filter(Boolean).concat(brief.po_queue || []),
}
