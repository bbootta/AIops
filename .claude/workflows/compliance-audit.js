export const meta = {
  name: 'compliance-audit',
  description: '컴플라이언스 점검: 선택한 규제 영역을 병렬 점검하고 통합 점검 보고서를 작성',
  whenToUse: '규제 준수 점검/신사업 규제 검토 요청 시. args: { domains: ["privacy","fair_trade","labor","finance","anticorruption","ai"], scope: "점검 대상 설명" }',
  phases: [
    { title: '점검 계획', detail: 'legal-compliance-officer가 영역별 점검 항목 확정' },
    { title: '영역 점검', detail: '영역별 병렬 점검(규정 확인 포함)' },
    { title: '통합', detail: '발견사항 통합과 우선순위 결정' },
    { title: '보고서 작성', detail: 'legal-writer가 reports/legal/에 저장' },
  ],
}

const DOMAINS = args && Array.isArray(args.domains) && args.domains.length ? args.domains : null
const SCOPE = args && args.scope ? args.scope : ''
if (!DOMAINS) throw new Error('args.domains가 필요합니다: ["privacy","fair_trade","labor","finance","anticorruption","ai"] 중 선택')
if (!SCOPE) throw new Error('args.scope가 필요합니다: 점검 대상(회사/서비스/프로세스) 설명')

const DOMAIN_DEF = {
  privacy: { name: '개인정보·데이터', kb: 'kb/legal/kr/07-privacy-data-ai.md', focus: '수집·이용 동의, 위탁·제3자 제공, 국외이전, 유출 대응 체계, 처리방침, 안전성 확보조치, 가명처리' },
  ai: { name: 'AI 규제', kb: 'kb/legal/kr/07-privacy-data-ai.md', focus: 'AI기본법상 고영향 AI 해당 여부, 생성형 AI 표시의무, 학습데이터 적법성(저작권·개인정보), EU AI Act 역외적용' },
  fair_trade: { name: '공정거래·하도급', kb: 'kb/legal/kr/06-fair-trade.md', focus: '거래상 지위 남용, 하도급 서면·대금, 표시광고, 내부거래, 기업결합 신고 누락, 약관' },
  labor: { name: '노동·중대재해', kb: 'kb/legal/kr/05-labor-law.md', focus: '근로시간·연장근로, 통상임금 산입, 취업규칙, 도급·파견 적법성, 중대재해 안전보건 확보의무' },
  finance: { name: '금융·자본시장', kb: 'kb/legal/kr/08-finance-securities.md', focus: '공시 의무, 미공개정보 관리, 금소법 판매규제, 외국환 신고, 가상자산 규제' },
  anticorruption: { name: '부패방지', kb: 'kb/legal/kr/04-criminal-law.md', focus: '청탁금지법, 뇌물·배임수증재, 해외 거래 FCPA 리스크, 접대·선물 정책, 내부신고 체계' },
}

const unknown = DOMAINS.filter(d => !DOMAIN_DEF[d])
if (unknown.length) throw new Error('알 수 없는 영역: ' + unknown.join(', ') + ' (가능: ' + Object.keys(DOMAIN_DEF).join(', ') + ')')

const AUDIT_SCHEMA = {
  type: 'object', required: ['domain', 'findings', 'upcoming_regs'],
  properties: {
    domain: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object', required: ['item', 'rule', 'status', 'grade', 'action', 'exposure'],
        properties: {
          item: { type: 'string', description: '점검 항목' },
          rule: { type: 'string', description: '근거 규정(확인된 조문·고시)' },
          status: { type: 'string', description: '현황 판단(제공된 scope 기준, 확인 불가 시 확인 필요 항목으로)' },
          grade: { type: 'string', enum: ['치명', '중대', '권고', '적정', '확인필요'] },
          action: { type: 'string', description: '시정·개선 조치' },
          exposure: { type: 'string', description: '위반 시 제재 노출(행정/형사/민사)' },
        },
      },
    },
    upcoming_regs: { type: 'array', items: { type: 'string' }, description: '시행 예정 규제 중 영향 있는 것' },
  },
}

log('컴플라이언스 점검 시작: ' + DOMAINS.map(d => DOMAIN_DEF[d].name).join(', '))

const audits = await pipeline(
  DOMAINS,
  d => agent([
    '컴플라이언스 점검을 수행하라.',
    '[점검 대상] ' + SCOPE,
    '[점검 영역] ' + DOMAIN_DEF[d].name,
    '[중점 항목] ' + DOMAIN_DEF[d].focus,
    '[기본 참조 KB] ' + DOMAIN_DEF[d].kb + ' (Read로 읽고, 최신 개정은 웹으로 재확인)',
    '점검 항목별로 근거 규정을 확인하고, 제공된 대상 설명만으로 판단이 안 되는 항목은 grade를 "확인필요"로 두고 확인할 질문을 status에 적어라.',
    '제재 노출은 과징금 산정 기준(관련 매출액/전체 매출액/정액)까지 명시하라.',
  ].join('\n'), { label: 'audit:' + d, phase: '영역 점검', agentType: 'legal-compliance-officer', schema: AUDIT_SCHEMA }),
)

const auditText = audits.filter(Boolean).map(a => [
  '## ' + a.domain,
  a.findings.map(f => '- [' + f.grade + '] ' + f.item + ' | 근거: ' + f.rule + ' | 현황: ' + f.status + ' | 조치: ' + f.action + ' | 노출: ' + f.exposure).join('\n'),
  a.upcoming_regs.length ? '시행 예정: ' + a.upcoming_regs.join('; ') : '',
].join('\n')).join('\n\n')

const consolidated = await agent([
  '영역별 점검 결과를 통합하라: 영역 간 중복·모순 제거, 전사 우선순위(치명→중대→권고) 결정, 종합 판정(적정/개선 필요/중대 위반 우려), 이행 로드맵 초안 작성.',
  '[점검 대상] ' + SCOPE,
  '', auditText,
  '', '최종 텍스트로 통합 점검 결과 전문을 반환하라.',
].join('\n'), { label: 'lead:통합', phase: '통합', agentType: 'legal-lead' })

const report = await agent([
  'templates/legal/compliance-checklist.md 구조에 따라 점검 보고서를 완성해 reports/legal/에 저장하라.',
  '파일명: 오늘 날짜로 YYYY-MM-DD-compliance-audit.md',
  '[통합 결과 — 이 내용만 사용]', consolidated,
  '', '저장 경로와 3문장 요지를 반환하라.',
].join('\n'), { label: 'writer:보고서', phase: '보고서 작성', agentType: 'legal-writer' })

return { domains: DOMAINS, report: report }
