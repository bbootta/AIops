"""검증·거버넌스 그룹(screens/governance.js) 카탈로그 (설계 사양 7장).

검증·요건 추적·에이전트·비상정지·변경·오버레이·변경통제·접근통제·직무분리·
AI 거버넌스·실행 감사추적·조회 거버넌스 열한 화면이 저자로서 새로 쓴 한국어
문자열만 여기 있다. 기존 카탈로그(i18n.py)와 셸 어휘(ng_frag·ng_gate·ng_kill·
ng_shell·ng_close)에 이미 있는 문구는 다시 적지 않고 그대로 쓴다.

**원장에서 오는 값은 없다.** 검증명(check_name)·요청 식별자(IVR-)·실행
식별자(RUN-)·지문·조문 인용·재계산 대상 키·카탈로그 한글명·컬럼 물리명·
판정 문자열(PASS·WARN·FAIL·적합·부적합·조건부·응답대기·승인·대기·반려·
일치·불일치·미보고·이전 요청 응답)은 화면이 원문 그대로 찍으며 이 사전에
넣지 않는다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

_t("ng_governance",
   # ── 검증: 도켓·3선 게이트·재계산·가정 ────────────────────────────
   '집계에서 제외한다||Excluded from every tally',
   '요청과 응답의 식별자가 다르면 이전 요청에 대한 응답이다'
   '||When the request identifier and the response identifier differ, the response belongs to an earlier request',
   '가정 검색||Search assumptions',
   '독립검증 요청 패키지||Independent validation request package',
   '가정 목록이 비어 있다. 독립검증 요청 패키지가 만들어지지 않았다.'
   '||The assumption list is empty, which means no independent validation request package was built.',
   '판정이 조건부일 때만 기록을 요구한다||A record is required only when the verdict is conditional',
   '현재 상태||Current state',
   '발동 중||Engaged',
   '미발동||Not engaged',

   # ── 요건 추적 ────────────────────────────────────────────────────
   '요건 {n}건||{n} requirements',
   '이 화면의 상태 어휘는 x_severity 에 없다. 색을 붙이지 않고 값만 적는다.'
   '||The status vocabulary on this screen is not in x_severity, so no colour is applied and the values are printed as recorded.',

   # ── 에이전트·비상정지 ────────────────────────────────────────────
   '비상정지||Emergency stop',
   '권한 모드별 에이전트 수||Agents by permission mode',
   '사람 승인 전에는 운영 반영 권한을 켜지 않는다||Write access stays off until a person approves',
   '최종 인간 게이트 행은 활동 원장의 마지막 순번이다'
   '||The final human gate row is the last sequence number in the activity ledger',
   '2차 확인 미완료||Second confirmation outstanding',
   '두 번째 확인자가 없는 행은 2차 확인이 남아 있다'
   '||A row without a second confirmer still has its second confirmation outstanding',
   '이 가드는 화면 안의 조회와 제안만 막는다. 런타임이나 원장에 아무 사건도 쓰지 않는다. AIMS AIG-009 는 런타임 정지를 오케스트레이션 계층에 둔다.'
   '||This guard blocks queries and proposals inside the screen only. It writes no runtime event and no ledger record. AIMS AIG-009 places the runtime stop in the orchestration layer.',
   '비상정지 발동 · 해제||Engage or release the emergency stop',
   '이 화면에서 발동·해제하면 머리말 표시줄과 같은 상태를 쓴다. 사유와 2차 확인자를 모두 채워야 한다.'
   '||Engaging or releasing here writes the same state as the header bar. Both the reason and the second confirmer are required.',

   # ── 변경 ─────────────────────────────────────────────────────────
   '배포는 화면이 아니라 파이프라인 재실행이 한다||Deployment is done by a pipeline re-run, never by the screen',
   '회귀테스트 상태별 건수||Regression tests by status',

   # ── 오버레이 ─────────────────────────────────────────────────────
   '수동조정 증감||Manual adjustment deltas',
   '수동조정 원장 (엔진 결합 · 사유·증빙 포함)'
   '||Manual adjustment ledger (engine join, with reason and evidence)',
   '결재 기록을 표본에서 찾지 못했다. 4-Eyes 원장이 표본이라 조정 식별자로 잇지 못한 행이 있다.'
   '||The approval record was not found in the sample. The four-eyes ledger is a sample, so some adjustment identifiers cannot be joined.',
   '수정값||Adjusted value',
   '사유 (필수, 데이터 지연·일회성 사건·모형 한계 등)'
   '||Reason (required: data lag, one-off event, model limitation and so on)',
   '증빙 참조||Evidence reference',
   '증빙 참조 (필수, 문서번호·티켓)||Evidence reference (required: document number or ticket)',
   '사유와 증빙 참조는 필수다||A reason and an evidence reference are both required',
   '수정값이 비어 있다||The adjusted value is empty',
   '수동조정(오버레이)||Manual adjustment (overlay)',
   '원장 등재(승인자·만료일 포함)||Ledger registration (with approver and expiry date)',
   '4-Eyes 승인||Four-eyes approval',
   '화면 값은 바뀌지 않는다.||The value on the screen does not change.',
   '적용 경로는 원장 등재 → 4-Eyes 승인 → 파이프라인 재실행 → 2선 → 3선 재요청이다. 화면은 제안서만 만든다.'
   '||The path to applying it is ledger registration, four-eyes approval, a pipeline re-run, second line validation and a fresh third line request. The screen only writes the proposal.',

   # ── 변경통제·접근통제·AI 거버넌스 ────────────────────────────────
   '변경 배포 게이트 원장에 행이 없다. 배포 판정이 아직 없다는 뜻이다.'
   '||The change deployment gate ledger holds no row, which means no deployment decision has been made yet.',
   '접근 판정별 건수||Access decisions by outcome',
   '단계별 추적 기록 수||Trace records by phase',
   '단계 값은 x_severity 에 어휘가 없어 색을 붙이지 않는다. 게이트만 톤을 받는다.'
   '||Phase values are not in the x_severity vocabulary, so they carry no colour. Only the gate is toned.',
   '이 화면은 읽기만 한다. 제안은 오버레이 화면이 만든다.'
   '||This screen only reads. Proposals are written on the overlay screen.',

   # ── 실행·감사추적 ────────────────────────────────────────────────
   '실행이 완결이 아니면 산출물은 부분이다. 판정은 원장 값 그대로다.'
   '||When the run is not complete the output is partial. The determination is the ledger value as recorded.',
   '해시체인 연속||Hash chain continuous',
   '기록 수||Records',
   '첫 불연속||First break',
   '이슈 종류별 건수||Run issues by kind',
   '이슈 없음||No issues',
   '이슈 종류는 x_severity 에 어휘가 없어 색을 붙이지 않는다.'
   '||Issue kinds are not in the x_severity vocabulary, so they carry no colour.',
   '계보 드로어의 근거 탭이 이 원장을 읽는다.||The evidence tab of the lineage drawer reads this ledger.',

   # ── 조회 거버넌스 ────────────────────────────────────────────────
   '조회계획 상태별 건수||Query plans by status',
   '조회계획 상태는 x_severity 에 어휘가 없어 색을 붙이지 않는다.'
   '||Query plan statuses are not in the x_severity vocabulary, so they carry no colour.',
   '사람이 승인한 제안만 적용한다||Only a proposal a person approved is applied',
   into=MESSAGES)
