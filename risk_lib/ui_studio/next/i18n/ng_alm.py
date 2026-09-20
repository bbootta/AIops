"""ALM·유동성 그룹(screens/alm.js) 카탈로그 (설계 사양 7장).

ALM · 금리리스크 · 국내 금리리스크 · 현금흐름 원장 · 유동성 사다리 ·
유동성리스크 · 생존기간 · ALM 계수 원장 여덟 화면이 저자로서 새로 쓴 한국어
문자열만 여기 있다. 기존 카탈로그(i18n.py)와 셸 어휘(ng_frag·ng_gate·
ng_shell)에 이미 있는 문구는 다시 적지 않고 그대로 쓴다.

**원장에서 오는 값은 없다.** 테이블명·컬럼 물리명·카탈로그 라벨(산출기준·
시간버킷·가중 후 금액 등)·조문 인용·계정명(별표9의1_2026)·시나리오 코드
(parallel_up)·상태 문자열(현행·직전·폐지·원문확인·2차자료·미확인)·LCR 대사
상태(reconciled)는 화면이 원문 그대로 찍으며 이 사전에 넣지 않는다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

_t("ng_alm",
   # ── 공통: 연결 원장·근거 판정 ────────────────────────────────────
   '모집단과 탑재량은 서버 집계다||Population and loaded rows are server-side aggregates',
   '표본 프레임이라 근거 판정을 세지 않은 원장'
   '||Ledgers whose evidence status was not counted because the frame is a sample',
   '아래는 이 부문 카탈로그 전량이다. 고른 원장의 입도·기본키·외래키·차트·미리보기가 오른쪽에 열린다.'
   '||Below is the full catalogue of this domain. Picking a ledger opens its grain, primary key, foreign keys, chart and preview on the right.',

   # ── LCR 대사 (ALM · 유동성리스크) ────────────────────────────────
   'LCR 대사 (원장 합계 대 결과 원장)||LCR reconciliation (ledger sums against the result ledger)',
   '대사 판정||Reconciliation state',
   '대사 대상||Reconciled source',
   '고유동성자산||High quality liquid assets',
   '총유출||Total outflows',
   '인정 유입||Recognised inflows',
   '항목 원장 합계||Item ledger sum',
   '유출입 원장 합계||Flow ledger sum',
   '결과 원장||Result ledger',
   '적용 상한||Applied caps',
   '허용오차||Tolerance',

   # ── 금리리스크 (IRRBB) ───────────────────────────────────────────
   '판정 미통과 {n}/{t} 시나리오||{n}/{t} scenarios fail the test',
   '최대는 {b} 기준 {s}||The largest is {s} on the {b} basis',
   '프록시 대용||Proxy substitution',
   '그 통화의 ΔEVE는 자기 계정 충격폭으로 낸 값이 아니다.'
   '||The ΔEVE for that currency is not produced with the shock sizes of its own set.',
   '폐지 계정 {v} 의 충격폭 {n}칸이 비어 있다. 그 체계에는 통화별 금리충격표가 없다. 이력 보존용이며 산출에 쓰지 않는다.'
   '||The shock sizes of the repealed set {v} are empty in {n} cells. That framework carries no per-currency interest rate shock table, and the rows are kept for history rather than used in the calculation.',
   '충격폭 공란 {v}. 1차자료를 확인하지 못했으므로 값을 지어 채우지 않는다.'
   '||Shock sizes are empty for {v}. The primary source could not be verified, so no value is invented to fill them.',
   '감소액 {a} / 기본자본 {b} = {p}||Decline {a} over tier 1 capital {b} equals {p}',
   '감소가 아닌 시나리오는 0으로 둔다. 아웃라이어 판정 기준값은 원장에 없다.'
   '||Scenarios that are not a decline are left at zero. The outlier threshold value is not in the ledger.',
   '시나리오별 ΔEVE||ΔEVE by scenario',
   '충격 출처||Shock source',
   '시작은 충격 전 순현재가치이고 각 막대는 그 버킷의 충격 전후 차이다. 자산과 부채를 합한 순액이다.'
   '||The start is the net present value before the shock and each bar is the difference before and after the shock for that bucket, netted across assets and liabilities.',
   '정의 원장이 ΔNII 대상으로 표시한 시나리오 {n}개'
   '||{n} scenarios are marked in the definition ledger as in scope for ΔNII',
   'ΔNII에는 산출기준(계약·행동조정) 축이 없다. 재가격 시뮬레이션이라 EVE 현금흐름을 재활용하지 않는다.'
   '||ΔNII has no calculation basis axis (contractual or behaviourally adjusted). It is a repricing simulation and does not reuse the EVE cash flows.',

   # ── 국내 금리리스크 [별표 9-1] ───────────────────────────────────
   'BCBS 계정으로 낸 산출은 금리리스크 화면에 있다. 두 화면은 같은 엔진을 쓰되 적용 계정이 다르므로 섞어 읽지 않는다.'
   '||The figures produced under the BCBS set are on the interest rate risk screen. Both screens use the same engine but a different applied set, so they are not read together.',
   '미등재||Not registered',
   '폐지 계정의 근거||Basis for the repealed set',
   '막대는 구간별 자산에서 부채를 뺀 값이다. 음수는 부채가 먼저 재설정되는 구간이다.'
   '||Each bar is assets less liabilities for the bucket. A negative value is a bucket where liabilities reprice first.',
   '{n}구간||{n} buckets',
   '요건 이행||Requirement performed',
   '요건 미이행||Requirement not performed',
   '공란 {n}칸||{n} empty cells',
   '{n}칸||{n} cells',
   '이 양식은 자체 조정이 금지된 칸 {n}개를 포함한다 (제22항 나).'
   '||This form contains {n} cells that the bank may not adjust (제22항 나).',
   '선택 항목||Optional item',
   '필수 항목||Mandatory item',
   '공시 작성||Disclosure drafted',
   '공시 미작성||Disclosure not drafted',
   '공시 승인||Disclosure approved',
   '공시 미승인||Disclosure not approved',

   # ── 현금흐름 원장 ────────────────────────────────────────────────
   '현금흐름 구성||Cash flow composition',
   '행동모형별 조정액||Adjustment by behavioural model',
   '행동조정액 (행동에서 계약을 뺀 값)||Behavioural adjustment (behavioural less contractual)',
   '원장 {t} 전량 집계 {r}행 · 계약 {k}건'
   '||Aggregated over the whole ledger {t}, {r} rows and {k} contracts',
   '조정액은 원장 adjustment_cf 를 그대로 더한 값이다.'
   '||The adjustment is the sum of the ledger column adjustment_cf as it stands.',

   # ── 유동성 사다리 ────────────────────────────────────────────────
   '버킷별 유입·유출||Inflows and outflows by bucket',
   '전 버킷 합계||Sum over all buckets',
   '최대 누적부족||Largest cumulative shortfall',
   '최저점||lowest point',
   '차감 후 잔량||Remaining after offset',
   '두 원장 컬럼의 합 (소진 경로는 생존기간 화면이 낸다)'
   '||The sum of two ledger columns (the depletion path is produced on the survival horizon screen)',

   # ── 유동성리스크 (LCR·NSFR) ─────────────────────────────────────
   '구분 소계||Category subtotal',
   '미구속||Not binding',
   '대조 규칙이 없는 상한||Caps with no comparison rule',
   '원장에는 있으나 화면이 대상 집계를 정하지 못한다.'
   '||They are in the ledger, but the screen cannot determine the aggregate they apply to.',
   '계수 공란||Empty factors',
   '국내 채택값을 확인하지 못해 비워 두었고, 그 항목은 산출에 들어가지 않는다.'
   '||The domestic adopted value could not be verified, so the cell is left empty and the item does not enter the calculation.',

   # ── 생존기간 ─────────────────────────────────────────────────────
   '{n}일차 소진||depleted on day {n}',
   '관측 구간 내 미소진||not depleted within the observed period',
   '경로가 없는 스트레스 {s}||Stresses with no path: {s}',
   '유출률이 원장에서 비어 있어(근거 미확인) 엔진이 산출을 건너뛰었다. 0으로 채우지 않는다.'
   '||The outflow rate is empty in the ledger (evidence unconfirmed), so the engine skipped the calculation. It is not filled with zero.',
   into=MESSAGES)
