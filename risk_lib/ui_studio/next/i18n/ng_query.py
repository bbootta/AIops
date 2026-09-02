"""조회·컴포저 그룹(screens/query.js) 카탈로그 (설계 사양 7장).

정형 조회·비정형 UI 두 화면이 저자로서 직접 쓴 한국어 문자열만 여기 있다.
셸이 이미 가진 어휘(ng_frag·ng_shell·기존 i18n.py 카탈로그)는 다시 적지 않고
그대로 쓴다: 고정 컬럼 결과, Read-only 실행, 비상정지 (실행 차단), 차단,
미리보기 생성, 승인 적용, 미리보기 · 승인 대기, 미리보기 (운영 반영 전),
제안 레이아웃, 통과·미통과, 승인 View 마스터, 필드 권한·마스킹 정책,
출처: {table}, 전량 {N}행, 표본 {n}/{N}, {n}건, {n}행, 건수, 정렬, 내림차순,
원장 행 없음, Read-only · 조건·출력 마스킹, 표시 단계에서 마스킹 컬럼 ...

**원장·엔진에서 오는 값은 없다.** View 식별자·View 명·부문·연결 정규 테이블·
필드 물리명·필드 한글명·마스킹 값(none·mask)·계획 ID·조회 지문·AST·차단 사유·
제안 ID·레이아웃 문자열·블록 제목(기여도·추이·검토 표·핵심 지표)은 화면이
원문 그대로 찍으며 이 사전에 넣지 않는다.

조회 문장과 프롬프트도 마찬가지다. engine.js(RY)의 문법이 한국어라
'이상·초과·그리고·기여도·추이·카드·표'를 번역하면 같은 문장을 다시 해석하지
못한다. 그래서 예시 문장은 원문 그대로 두고, 그 사실을 알리는 안내문만
번역한다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

# ── 정형 조회: 문장·프리셋·View 카드 ──────────────────────────────────
_t("ng_query",
   '조회 문장||Query sentence',
   '조회 대상 View||Queried view',
   '조회 엔진(engine.js)을 불러오지 못해 이 화면을 그릴 수 없다.'
   '||The query engine (engine.js) could not be loaded, so this screen cannot be drawn.',
   '조회 문장은 engine.js 의 한국어 문법으로 해석한다. 이상·초과·이하·미만·그리고 같은 키워드는 화면 언어를 바꿔도 번역하지 않는다.'
   '||The query sentence is parsed with the Korean grammar of engine.js. Its keywords (이상 at least, 초과 above, 이하 at most, 미만 below, 그리고 and) are never translated, whatever the interface language is.',
   '차단 시연||blocked, for demonstration',
   '전부 다 보여줘||Show me everything',
   '조건 가능 필드 {n}/{N} · 마스킹 필드 {m}'
   '||Fields usable as a condition {n}/{N} · masked fields {m}',
   '행 상한 {n}||Row limit {n}',
   '조건 사용||Usable as a condition',

# ── 정형 조회: 조회계획 다섯 단계와 판정 ───────────────────────────────
   '01 의도||01 Intent',
   '02 기준일||02 As-of date',
   '03 모집단||03 Population',
   '04 조건||04 Conditions',
   '05 정책||05 Policy',
   '조회 지문 {hash} · 계획 {plan}||Query digest {hash} · plan {plan}',
   '차단 사유||Block reason',
   'Kill Switch가 걸려 있어 신규 조회를 실행하지 않는다. 진행 중이던 결정론적 계산은 완료 후 중단된다.'
   '||The kill switch is engaged, so no new query is executed. A deterministic calculation already under way finishes and then stops.',
   '모집단 {n}건||population {n} rows',
   '조건 통과 (화면 내 행 기준)||Rows matching the conditions (of the rows carried in the page)',
   '화면에 실린 {n}행 범위에서 센 건수다. 원장 전량은 {N}행이다.'
   '||The count is taken over the {n} rows carried in the page. The full ledger holds {N} rows.',
   '원장 전량 {N}행에서 센 건수다.||The count is taken over the full ledger of {N} rows.',

# ── 비정형 UI: 프롬프트·정책검증·승인 ─────────────────────────────────
   '프롬프트||Prompt',
   '사용 가능한 열||Columns available',
   '프롬프트는 engine.js 의 한국어 문법으로 해석한다. 기여도·추이·카드·표 같은 블록 키워드는 화면 언어를 바꿔도 번역하지 않는다.'
   '||The prompt is parsed with the Korean grammar of engine.js. Its block keywords (기여도 contribution, 추이 trend, 카드 card, 표 table) are never translated, whatever the interface language is.',
   '필드 권한||Field permission',
   '스키마·단위||Schema and unit',
   '집계 최소단위||Minimum aggregation unit',
   '사람 적용승인||Human approval to apply',
   '승인 적용 화면||Applied view (approved)',
   '정책 거부||Rejected by policy',
   '승인 거부||Approval refused',
   '리스크관리부장||Head of risk management',
   '승인자는 화면 가정값이며 원장에서 오지 않는다. 승인 상태는 실행(기관·기준일)마다 따로 남고 어느 원장에도 쓰지 않는다.'
   '||The approver is an assumption of this screen and does not come from a ledger. The approved state is held per run (institution and as-of date) and is written to no ledger.',
   'Kill Switch가 걸려 있어 미리보기·승인을 실행하지 않는다.'
   '||The kill switch is engaged, so neither preview nor approval is executed.',

# ── 비정형 UI: 거부 사유와 블록 격자 ──────────────────────────────────
   '차단된 열||Blocked columns',
   '미승인 필드는 레이아웃에 세울 수 없다||an unapproved field cannot be placed in a layout',
   '집계 최소단위 위반 (마스킹 필드를 행 단위 열로 세울 수 없다)'
   '||Minimum aggregation unit violated (a masked field cannot be placed as a row level column)',
   '승인된 열을 하나도 짚지 못했다. 아래 사용 가능한 열의 이름을 문장에 포함할 것'
   '||No approved column was named. Include one of the available column names below in the sentence.',
   '정책검증 미통과. 미리보기를 그리지 않는다.||Policy validation did not pass. No preview is drawn.',
   '평균 {avg} · 최대 {max}||average {avg} · maximum {max}',
   '그 외 {n}건||{n} others',
   '값 열이 문장에 없어 이 View 의 기본 값 열({col})로 그렸다. 다른 열은 문장에 이름을 적으면 된다.'
   '||The sentence named no value column, so the default value column of this view ({col}) was drawn. Name another column in the sentence to use it instead.',
   '숫자 열이 없어 그리지 않는다. 문장에 값 열 이름({cols})을 적으면 그린다.'
   '||Nothing is drawn because there is no numeric column. Name a value column ({cols}) in the sentence and it will be drawn.',
   '원장 {table} · 화면 내 {n}행 / 원장 {N}행 · 정렬 {sort}'
   '||Ledger {table} · {n} rows in the page of {N} rows in the ledger · sorted by {sort}',
   '원장 순||ledger order',
   into=MESSAGES)
