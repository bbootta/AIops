"""보고서 그룹(screens/reports.js) 카탈로그 (설계 사양 7장).

종합보고서·결재 패키지·헤드라인 추이·자본 판정·감독보고 다섯 화면이 저자로서
직접 쓴 한국어 문자열만 여기 있다. 셸이 이미 가진 어휘(ng_frag·ng_gate·
ng_capital·ng_pack·ng_trend·ng_queue·ng_close·ng_shell)는 다시 적지 않고
그대로 쓴다.

**원장에서 오는 값은 없다.** 서식 코드·서식명·편 이름·검증명·인용·요청 ID·
지문·실행 ID·결재선 성명·KPI 라벨·KRI 이름은 화면이 원문 그대로 찍으며 이
사전에 넣지 않는다. 결재 어휘(대기·승인·반려)와 제출 상태(draft·reviewed·
approved·submitted)도 원장 값이라 그대로 둔다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

# ── 종합보고서: 보드·절 제목 ────────────────────────────────────────
_t("ng_reports",
   '현재 적색||Red now',
   '차단과 이유||Blocked and why',
   '헤드라인 지표||Headline figures',
   'CRO 브리핑||CRO briefing',
   'CRO 액션 (즉시·단기 조치)||CRO actions (immediate and short term)',
   'KRI 스코어카드 (위험선호체계)||KRI scorecard (Risk Appetite Framework)',
   '자본 스택 (계층별 요구 대비 여유)||Capital stack (headroom against the requirement by tier)',
   # cap_stack 은 상품 금액과 누적 비율을 한 행에 담는다. 두 열의 성질이
   # 다르므로 표에서 이름으로 갈라 놓는다 (검수 F2 재발 방지).
   # app._kpis 가 만드는 헤드라인 카드 라벨 여섯. 원장 값이 아니라 하니스가
   # 쓴 문장이므로 영문 화면에서 한국어로 남으면 안 된다 (검수 F10).
   '보통주자본비율 (CET1)||Common equity tier 1 ratio (CET1)',
   '위기상황 CET1 저점||Stress trough CET1',
   '기대신용손실 (ECL)||Expected credit loss (ECL)',
   '유동성커버리지비율 (LCR)||Liquidity coverage ratio (LCR)',
   '자체검증||Self-validation',
   '업무보고서 대사||Supervisory form reconciliation',
   '누적 금액||Cumulative amount',
   '구성 상품||Instrument',
   '상품 금액||Instrument amount',
   ('비율은 그 상품까지 누적한 자본의 비율이고, 상품 금액은 그 계층에 더해지는 '
    '금액이다. 누적 금액은 상품 금액을 누적한 값이다'
    '||The ratio is cumulative through that instrument, the instrument amount is what that '
    'layer adds, and the cumulative amount is the running total of the instrument amounts'),
   '위험가중자산 귀속 (구성요소별 비중)||Risk-weighted asset attribution (share by component)',
   '심각 시나리오 (자본 저점)||Severe scenario (capital trough)',
   '다음 화면||Next screens',

# ── 종합보고서: 문장 ────────────────────────────────────────────────
   '위원회 배포용 한 장이다. 보드는 지금 붉은 것, 막힌 것, 달라진 것만 싣고 나머지는 화면 링크로 넘긴다.'
   '||One page for the committee. The board carries only what is red now, what is blocked and what has changed; everything else is a link to another screen.',
   '게이트 스트립이 2선·3선 집계를 이미 싣고 있어 검증 KPI 두 장은 카드로 되풀이하지 않고 보드 둘째 칸 첫 두 줄에 둔다'
   '||The gate strip already carries the second and third line tallies, so the two validation KPIs are not repeated as cards and lead the second board column instead',
   '한계 위반과 자체검증 WARN·FAIL 에서 뽑았다||Taken from appetite breaches and self-validation WARN and FAIL rows',
   'RED 는 board 한계 위반, AMBER 는 management 한계, WATCH 는 operational 조기경보, GREEN 은 한계 이내다'
   '||RED breaches the board limit, AMBER the management limit, WATCH is an operational early warning and GREEN is within limits',
   'RED {red} · AMBER {amber} · WATCH {watch} · GREEN {green} · 전체 {total}'
   '||RED {red} · AMBER {amber} · WATCH {watch} · GREEN {green} · total {total}',
   '임계는 RAF 원장에서 온다||Thresholds come from the RAF ledger',
   '요구 대비 여유는 표에 있다||The headroom against the requirement is in the table below',
   '요구 미달 계층||Tiers below the requirement',
   '배당·성과급 제한 대상||Subject to dividend and bonus restrictions',
   '묶음은 최종 RWA 구성요소이고 그 안은 원장 축이다. 합계는 공표 RWA 와 같다.'
   '||The outer cells are the final RWA components and the inner cells are ledger axes; the total equals the published RWA.',
   '칸을 누르면 해당 RWA 화면으로 간다||Selecting a cell opens the matching RWA screen',
   '이 보고서는 인쇄를 전제로 배치했다. 서명란과 제출 현황은 결재 패키지에 있다.'
   '||This report is laid out for print; the signature block and the submission status are in the approval pack.',

# ── 종합보고서: 심각 시나리오 항목 ─────────────────────────────────
   'CET1 저점||CET1 trough',
   '종료 시점 CET1||CET1 at the end of the horizon',
   '최초 침범||First breach',
   '침범 비율||Breached ratio',
   '요구 비율 침범 없음||No breach of the required ratio',
   '역스트레스 임계 심도||Reverse stress critical severity',

# ── 수치가 섞이는 조각 ─────────────────────────────────────────────
   '한도 위반 {n}건 (전량 {N}건 서버 집계)||{n} limit breaches (full {N} rows, server-side aggregate)',
   '위기상황 미통과 분기 {n}건||{n} stress quarters below the requirement',
   '연속 위반 {n}||{n} consecutive breaches',
   '서식검증 실패 {n}건||{n} failed form checks',
   '라인 {n}행||{n} lines',
   '검증 {n}건 · 실패 {k}건||{n} checks · {k} failed',

# ── 결재 패키지 ────────────────────────────────────────────────────
   '결재 상신 판정||Sign-off readiness',
   '발신 상태||Dispatch state',
   '보류 사유가 없다||No hold reason recorded',
   '검증 도메인||Check domain',
   '행을 누르면 2선 원장 행이 열린다||Selecting a row opens the second-line ledger row',
   '조건부 승인 필요||Conditional approval required',
   '조건부 승인 불필요||Conditional approval not required',
   '원장 기록 상태||Ledger record state',
   '파일 기록을 읽었다||The file record was read',
   '파일 기록을 읽지 않는다||File records are not read',
   '결재선 (원장 값)||Approval route (ledger value)',
   '서명 없음. 결재선은 원장 값이며 화면은 서명을 만들지 않는다.'
   '||Unsigned. The approval route comes from the ledger and the screen creates no signature.',
   'AIMS §5 A.9.2 결재선을 그대로 옮겼고 서명은 비워 둔다'
   '||The AIMS §5 A.9.2 approval route is carried over as recorded and the signatures are left blank',

# ── 헤드라인 추이 ──────────────────────────────────────────────────
   '추이 원장 상태||Trend ledger state',
   '추이 지표||Trend metrics',
   '헤드라인 스냅샷 (현재 실행)||Headline snapshot (current run)',
   '현재 실행의 헤드라인 수치다. 기간이 하나뿐이라 차트를 그리지 않는다.'
   '||These are the headline figures of the current run; with a single period nothing is drawn.',

# ── 자본 판정 ──────────────────────────────────────────────────────
   '스트레스 경로 (분기별 자본비율)||Stress path (capital ratios by quarter)',
   '충격 심도||Shock severity',
   '빗금 친 분기는 요구치 미달이다||Hatched quarters are below the requirement',
   '구속 계층은 잉여가 가장 작은 계층이다. 요구치는 최저 기준에 완충자본을 더한 값이다.'
   '||The binding tier is the tier with the smallest surplus, and the requirement is the minimum plus the buffers.',
   '세 상태는 일치·불일치·미보고이며, 응답 요청 ID 가 어긋난 항목은 이전 요청 응답이다'
   '||The three states are matched, mismatched and not reported; an item whose response request id differs is a response to an earlier request',

# ── 감독보고 ───────────────────────────────────────────────────────
   '제출·결재 상태||Submission and approval status',
   '금융감독원 배포 기준 업무보고서다. 라인마다 산식·규정근거·산출 모듈을 남긴다.'
   '||Supervisory business reports on the issued FSS basis. Every line records its formula, regulatory basis and calculating module.',
   '서식 식별자는 내부 코드이며 배포본 서식번호와의 대조가 남아 있다'
   '||The form identifier is an internal code and the comparison with the issued form number is still open',
   '이 서식의 제출·결재 원장 행이 없다||No submission or approval ledger row for this form',
   'FAIL 행은 붉게 칠한다. 건수는 서버 집계이고 표본 행은 확인용이다.'
   '||FAIL rows are shown in red; the counts are server-side aggregates and the sample rows are for inspection.',
   into=MESSAGES)
