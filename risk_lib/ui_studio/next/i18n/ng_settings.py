"""설정 그룹(screens/settings.js) 카탈로그 (설계 사양 7장).

설정·기관 설정·산출 방법론 세 화면이 저자로서 새로 쓴 한국어 문자열만 여기
있다. 기존 카탈로그(i18n.py)와 셸 어휘(ng_frag·ng_shell)에 이미 있는 문구는
다시 적지 않고 그대로 쓴다.

**원장에서 오는 값은 없다.** 테이블명·컬럼 물리명·카탈로그 한글명·조문 인용·
서식 코드(B2101·RM-6401)·실행 ID·요청 ID·지문·게이트 판정 문자열은 화면이
원문 그대로 찍으며 이 사전에 넣지 않는다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

_t("ng_settings",
   # ── 설정: 실은 실행 ──────────────────────────────────────────────
   '기준일 전환 대상 {n}개||{n} runs available for the as-of date switch',

   # ── 설정: 컬럼 표시명 재정의 ─────────────────────────────────────
   '(카탈로그 표시명 사용)||(uses the catalogue display name)',
   '물리명||Physical name',
   '카탈로그 표시명||Catalogue display name',
   '세션 재정의||Session override',

   # ── 설정: 서식번호 매핑 ──────────────────────────────────────────
   '서식 {n}종||{n} forms',
   '배포본 확정 {n}종||{n} confirmed against the issued form',
   '내부 배정 {n}종||{n} internally assigned',
   '새 서식번호||New form number',
   '바꿀 서식번호를 적는다||Enter the form number to change to',
   '{no} 는 형식 위반이다 (B/BA/BF+숫자(-가지) 또는 RM-####)'
   '||{no} breaks the format (B, BA or BF followed by 3 to 5 digits with an optional branch number, or RM-####)',
   '{no} 는 {fid} 가 이미 사용한다||{no} is already used by {fid}',
   '서식번호 매핑 변경||Change of the form number mapping',
   '화면에는 적용되지 않는다. 서식번호는 제출 지문에 포함된다.'
   '||Nothing is applied on the screen. The form number is part of the submission digest.',

   # ── 설정: 다른 화면으로 옮긴 설정 ────────────────────────────────
   '다른 화면에 있는 설정||Settings that live on other screens',
   '시나리오 파라미터는 위기상황 그룹의 시나리오 설정 화면에, 시장 포트폴리오 구성은 시장 그룹의 포트폴리오 설정 화면에 있다.'
   '||Scenario parameters are on the Scenario setup screen of the Stress group, and the market portfolio composition is on the Portfolio setup screen of the Market group.',

   # ── 기관 설정 ────────────────────────────────────────────────────
   '선택기에는 산출이 실린 기관만 올라간다. 원장에 있어도 산출이 실리지 않은 기관은 고를 수 없다. 실린 기준일은 그 기관에 실린 실행의 기준일 전량이다.'
   '||Only institutions with a loaded run appear in the selector. An institution that is in the ledger but has no run loaded cannot be chosen. The as-of dates loaded are all as-of dates of the runs embedded for that institution.',
   '선택 기관 자산군별 익스포저 건수||Exposure count by asset class for the selected institution',

   # ── 산출 방법론: 집합투자증권 ────────────────────────────────────
   '원장 채택값 (정보 가용성 기준)||Value adopted in the ledger (on information availability)',
   '전건 LTA 강제 (CRE60.5)||Force look-through on every fund (CRE60.5)',
   '전건 MBA 강제 (CRE60.7)||Force the mandate-based approach on every fund (CRE60.7)',
   '전건 Fallback 1250% (CRE60.9)||Force the 1250% fallback on every fund (CRE60.9)',
   'LTA 는 편입자산을 직접 보유한 것처럼, MBA 는 운용지침 한도까지 투자했다고 가정한다. 정보가 부족하면 Fallback 1250% 다.'
   '||Look-through treats the holdings as if they were held directly, and the mandate-based approach assumes investment up to the limits of the mandate. Where the information is short, the fallback is 1250%.',

   # ── 산출 방법론: 유동화 ──────────────────────────────────────────
   '원장 채택값 (CRE40.41 계층)||Value adopted in the ledger (the CRE40.41 hierarchy)',
   '전건 SEC-IRBA (가능한 건만)||Force SEC-IRBA wherever it can be calculated',
   '전건 SEC-ERBA (등급 있는 건만)||Force SEC-ERBA wherever an external rating exists',
   '전건 SEC-SA||Force SEC-SA on every tranche',
   '계층은 IRBA · ERBA · SA 순이다(CRE40.41). 위험가중 하한은 15%, STC 선순위는 10% 다(CRE44.5).'
   '||The hierarchy runs IRBA, then ERBA, then SA (CRE40.41). The risk weight floor is 15%, and 10% for senior STC positions (CRE44.5).',

   # ── 산출 방법론: 비교 지표 ───────────────────────────────────────
   '원장 채택 위험가중자산||Risk weighted assets adopted in the ledger',
   '원장 컬럼||Ledger column',
   '선택 방법 위험가중자산||Risk weighted assets under the selected approach',
   '(채택 대비)||(against the adopted value)',
   '산출 불가 {n}건은 채택값을 유지했다'
   '||{n} positions cannot be calculated under this approach and keep the adopted value',
   '원장에 이미 있는 방법별 결과를 그대로 더한 값이다. 재계산이 아니다.'
   '||The bars add up the per approach results already held in the ledger. Nothing is recalculated.',

   # ── 산출 방법론: 변경 제안 ───────────────────────────────────────
   '파생 (SA-CCR)||Derivatives (SA-CCR)',
   '변경 사유 (필수)||Reason for the change (required)',
   '변경 사유는 필수다||The reason for the change is required',
   '산출 방법론 변경||Change of the calculation methodology',
   '방법론 코드 반영||Land the methodology change in code',
   '화면은 원장에 이미 있는 대안 값을 보여줄 뿐 산출을 바꾸지 않는다.'
   '||The screen only shows alternative values already held in the ledger and changes no calculation.',
   '방법론 변경은 산출 지문을 바꾸므로 상시 독립검증 (3선) 재요청 대상이다.'
   '||A methodology change alters the output digest, so standing independent validation (third line) is requested again.',
   '집합투자증권(CRE60)과 유동화(CRE40)는 여러 산출 방법이 규정에 함께 있고, 어느 것을 쓸지는 정보 가용성과 정책이 정한다. 원장에 세 방법 결과가 모두 있으므로 방법을 바꿨을 때의 차이를 재계산 없이 본다. 화면은 값을 바꾸지 않고, 적용은 코드 반영 + 재실행 + 자체검증·상시 독립검증을 거친다.'
   '||For collective investment undertakings (CRE60) and securitisations (CRE40) the rules hold several calculation approaches at once, and information availability and policy decide which one is used. The ledger holds the result of all three approaches, so the difference a change of approach would make is read without recalculation. The screen changes no value: applying a change goes through code, a pipeline re-run, self validation and standing independent validation.',
   into=MESSAGES)
