"""리스크데이터 그룹(screens/riskdata.js) 카탈로그 (설계 사양 7장).

12개 화면(RDM · 원천·계약 · DQ·대사 · 예외·조치 · 담보·보증 · 집계 원장 ·
집합투자증권 · 파생상품 · 유동화 · 데이터모델 · 코드 마스터 · 코드 매핑)이
저자로서 직접 쓴 한국어 문자열만 여기 있다. 셸과 기존 카탈로그가 이미 가진
어휘는 다시 적지 않고 그대로 쓴다: 연결 원장, 전량 {N}행, 표본 {n}/{N}행,
전량 {N} (서버 집계), 출처: {table}, {n}건, {n}종, {n}행, 검토 안내,
소관 부서, 소관 (UI 가정), 소관 미확인, 합성데이터 · 합성 포트폴리오,
시드 {seed}, 차트는 전량 프레임에서만 그린다, 추이 원장에 기간이 하나뿐이다,
기록 없음, 비상정지 (실행 차단), 세션에 적용, 재정의 지우기, 정본 변경 제안,
예외 제안 생성, 대상여부 예외 제안, 코드그룹, 코드, 순서, 이동, 사유, 대상,
제외, 테이블, 한글명, 부문, 그레인, 컬럼, 기본키, 외래키, 행, 화면,
원장 행수, 판정, 검증 항목, 재계산 대상, 코드 모듈, 규정 근거, 하한, 출처,
미산출, 정규 데이터모델 카탈로그, 그리고 레거시 화면이 쓰던 안내문과 차트
제목(원천 시스템별 수신 행수, 담보유형별 평가액, 보증유형별 보증액,
거래상대방별 명목, 자산군별 편입 시가, 트렌치별 보유액 등).

**원장·엔진에서 오는 값은 없다.** 물리 테이블명(rdm_dq_result,
gov_exception_action, chg_change_request ...), 컬럼 물리명, 카탈로그 한글명,
코드셋 이름과 코드값, 심각도·상태·매핑 판정(중대 · 경미 · 접수 · 조치중 ·
종결 · PASS · FAIL · mapped · unmapped), 예외 ID·변경 ID·대사 ID, 재계산
대상 이름, 규정 근거 문자열, 그리고 Kill Switch 범위로 쓰는 View 부문값
('A · 리스크데이터')은 화면이 원문 그대로 찍으며 이 사전에 넣지 않는다.
번역하면 같은 값을 원장에서 다시 찾지 못하기 때문이다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

# ── RDM: 검토 안내와 데이터 스튜어드 처리대장 ────────────────────────
_t("ng_riskdata",
   '이 화면의 수치는 합성데이터를 파이프라인에 넣어 낸 산출이다. 실제 기관 수치가 아니며, 쓰기 전에 소관 부서의 검토를 거쳐야 한다. 검토 결과는 승인 원장에 남는다.'
   '||The figures on this screen are the output of running synthetic data through the pipeline. They are not the figures of a real institution, they must be reviewed by the responsible department before use, and the review is recorded in the approval ledger.',
   '데이터 스튜어드 처리대장||Data steward docket',
   '지금 붉은 것||Red now',
   '막힌 것||Blocked',
   '달라진 것||Changed',
   '데이터품질 실패 규칙 {n}종||{n} data quality rules failing',
   '대사 실패 {n}건||{n} reconciliations failing',
   '원천 계약 미통과 {n}건||{n} source contracts not passing',
   '표준코드 미매핑 {n}건||{n} source codes unmapped',
   '기한 {d}일 이내 {n}건||{n} items due within {d} days',
   '배포 불가 변경요청 {n}건||{n} change requests not deployable',
   '기간 {n}개||{n} periods',
   '추이 원장은 헤드라인 지표만 싣는다. 원장 전량의 기간 비교는 이 화면에서 하지 않는다.'
   '||The trend ledger carries the headline metrics only. This screen does not compare periods over the full ledgers.',
   '원천 계약부터 표준 매핑, 버전형 가공, 다차원 집계, DQ·대사, 승인 스냅샷까지 원장으로 통제한다. 아래 목록은 이 부문 카탈로그 전량이며, 고른 원장의 입도·기본키·외래키·차트·미리보기를 오른쪽에 편다.'
   '||From the source contract through standard mapping, versioned processing, multi dimensional aggregation, data quality and reconciliation to the approved snapshot, everything is controlled as a ledger. The list below is the full catalogue of this sector; picking a ledger opens its grain, primary key, foreign keys, chart and preview on the right.',

   # ── 원천·계약 ──────────────────────────────────────────────────────
   '미매핑 코드가 없다||No unmapped code',
   '미매핑 코드는 산출 모집단에서 빠지고 대사에도 걸리지 않는다. 표준 코드가 생겨야 산출에 들어간다.'
   '||An unmapped code drops out of the calculation population and is not caught by reconciliation either. It enters the calculation only once a standard code exists.',

   # ── DQ·대사 ────────────────────────────────────────────────────────
   'DQ 규칙과 판정, 원천·산출 대사를 한 화면에서 본다. 실패는 예외·조치 큐로 넘어간다.'
   '||Data quality rules and their verdicts, and the source to output reconciliation, in one screen. A failure moves to the exception and remediation queue.',
   '데이터품질 판정||Data quality verdicts',
   '데이터품질 실패 판정||Data quality verdicts failing',
   '실패 규칙 {n}종||{n} failing rules',
   '실패 규칙별 건수||Count by failing rule',
   '대사 판정별 건수||Count by reconciliation verdict',
   '실패 대사와 예외·조치 연결||Failing reconciliations and their remediation rows',
   '실패한 대사가 없다||No reconciliation failed',

   # ── 예외·조치 ──────────────────────────────────────────────────────
   '예외 상태 분포||Exception status distribution',
   '상태별 건수||Count by status',
   '심각도별 건수||Count by severity',
   '자동상계 금지 · 종결은 사람 승인 후||No automatic netting · closure only after human approval',
   '심각도(색조) 다음 기한 순으로 세웠다. 원장 순서가 아니다.'
   '||Ordered by severity (through the tone map) and then by due days. This is not the ledger order.',
   '경보는 제출을 막을 수 있다. 자동으로 상계하거나 종결하지 않는다. 종결은 담당 역할의 승인이 원장에 남은 뒤다.'
   '||An alert can block submission. Nothing is netted or closed automatically: closure follows the owning role approval being recorded in the ledger.',

   # ── 담보·보증 · 집계 원장 ──────────────────────────────────────────
   '담보·보증·차주 재무 원장이다. 신용위험경감과 LGD 의 원천이며, 적격 판정은 원장 컬럼 그대로 읽는다.'
   '||The collateral, guarantee and obligor financial ledgers. They are the source of credit risk mitigation and LGD, and eligibility is read straight from the ledger column.',
   '도메인마다 집계 축과 필요 컬럼이 다르므로 집계 결과를 원장으로 고정했다. 축이 다른 다섯 원장을 한 화면에서 본다.'
   '||Each domain aggregates on its own axis with its own columns, so the aggregates are pinned as ledgers. The five ledgers with their different axes are read here in one screen.',
   '자산군별 익스포저 (신용 축)||Exposure by asset class (credit axis)',
   '리프라이싱 구간별 익스포저 (ALM 축)||Exposure by repricing bucket (ALM axis)',
   '신용·ALM 집계의 EAD 합은 익스포저 원장 rdm_exposure 총계와 같다. 대사 판정은 rdm_reconciliation 원장에 남으며 화면이 다시 계산하지 않는다.'
   '||The EAD total of the credit and ALM aggregates equals the total of the exposure ledger rdm_exposure. The reconciliation verdict is recorded in the rdm_reconciliation ledger and is not recomputed by this screen.',

   # ── 선행 원장 (집합투자증권 · 파생상품 · 유동화) ────────────────────
   '모펀드 마스터와 편입자산·운용지침을 분리해 LTA·MBA 를 둘 다 산출한다. 정보가 모자라면 fallback 이며, 채택 방법과 사유는 원장에 남는다.'
   '||The fund master is kept apart from its holdings and its mandate so that both the look through and the mandate based approach are computed. Where information is short the fallback applies, and the adopted approach and its reason are recorded in the ledger.',
   '거래 마스터와 기초자산(다리)을 분리해 SA-CCR EAD 와 시장리스크 민감도를 둘 다 낸다. 기초자산 자산군이 감독계수 키가 된다.'
   '||The trade master is kept apart from its underlyings (legs) so that both the SA-CCR exposure at default and the market risk sensitivities are produced. The asset class of the underlying is the key to the supervisory factor.',
   '딜 마스터와 트렌치·기초자산 풀을 분리해 세 방법을 모두 산출하고 규정 계층으로 채택한다. 채택 방법·하한 적용 여부는 원장 컬럼 그대로다.'
   '||The deal master is kept apart from its tranches and its pool so that all three approaches are computed and the regulatory hierarchy picks one. The adopted approach and whether the floor applied are read straight from the ledger columns.',
   '채택 전 세 방법 합계||Total of the three approaches before adoption',
   '산출방법별 채택 위험가중자산||Adopted risk weighted assets by approach',
   '딜별 채택 위험가중자산||Adopted risk weighted assets by deal',
   '자산군별 다리 명목||Leg notional by asset class',
   '위험가중 하한 적용 트렌치 {n}건||Risk weight floor applied to {n} tranches',
   '상시 독립검증 (3선) 재계산 대상||Standing independent validation (3rd line) recalculation target',

   # ── 데이터모델 ─────────────────────────────────────────────────────
   '정규 데이터모델 카탈로그와 그 쓰임이다. 카탈로그는 테이블·컬럼·입도·기본키의 정본이고, 각 View 의 필드 권한과 마스킹 정책이 조회 가능 범위를 결정한다.'
   '||The normalised data model catalogue and how it is used. The catalogue is the authoritative source for tables, columns, grain and primary keys, and the field permissions and masking policy of each view decide what can be queried.',
   '카탈로그||Catalogue',
   '원장→화면||Ledger to screen',
   '수치→원장||Figure to ledger',
   '전체 부문||All sectors',
   '실체화||Materialised',
   '정규 테이블 {n}장 · 컬럼 {c}개 · 실체화 {r}행'
   '||{n} normalised tables · {c} columns · {r} materialised rows',
   '카탈로그의 모든 테이블은 이 탭 밖에 자기 화면을 하나씩 가진다. pru_income_statement 와 pru_ownership_limit 은 NCR·건전성, st_shock_axis 는 위기상황 화면이 싣는다.'
   '||Every catalogue table has a home screen outside this tab. pru_income_statement and pru_ownership_limit live on NCR and prudential, st_shock_axis on the stress screen.',
   '어느 화면이 어느 원장을 읽는지는 화면 등록부(x_screens)에서 온다. 표시 행수는 그 화면이 실제로 실은 행수이고, 원장 행수가 전량이다.'
   '||Which screen reads which ledger comes from the screen registry (x_screens). The shown count is what that screen actually carries; the ledger count is the full population.',
   '표시 행수||Shown rows',
   '수치 하나가 어느 원장의 어느 행·어느 컬럼에서 나왔고, 어느 검증 항목이 걸려 있는지의 색인이다. 값은 x_lineage 가 준다.'
   '||An index of which ledger row and column a figure came from and which checks are attached to it. The values come from x_lineage.',
   '수치 식별자||Figure id',

   # ── 코드 마스터 ────────────────────────────────────────────────────
   '정렬·표시의 정본을 코드그룹 단위로 관리한다. 왼쪽에서 그룹을 고르면 오른쪽에 그 그룹의 코드가 순서대로 뜬다. 순서 재정의는 이 화면 안에서만 적용되고, 정본 변경은 카탈로그 수정 제안으로만 한다.'
   '||The authoritative source for sorting and display is managed one code group at a time. Picking a group on the left lists its codes in order on the right. An order override applies inside this screen only; the authoritative order changes through a catalogue change proposal.',
   '그룹명 검색||Search group names',
   '코드 {n}개||{n} codes',
   '재정의됨||overridden',
   '정렬은 카탈로그 선언 순서를 따른다||The order follows the declaration order in the catalogue',
   '코드 마스터 순서 변경||Change the code master order',
   '정본은 카탈로그다. 세션 재정의는 이 화면을 벗어나면 사라진다.'
   '||The catalogue is the authoritative source. A session override disappears when this screen is left.',

   # ── 코드 매핑 ──────────────────────────────────────────────────────
   '계정·상품 코드가 어느 리스크의 모집단에 들어가는지의 매핑이다. 매핑이 없으면 그 코드는 모든 산출에서 빠지고 대사에도 걸리지 않는다.'
   '||The mapping of which risk population an account or product code belongs to. Without a mapping the code drops out of every calculation and is not caught by reconciliation either.',
   '계정코드 축||Account code axis',
   '상품코드 축||Product code axis',
   '엔진 연계 매트릭스||Engine linkage matrix',
   '대상여부는 특성에서 규칙으로 파생된다. 신용환산율·위험가중 범위는 산출 엔진 상수, 모집단은 익스포저 원장, 적용률은 산출 원장에서 읽는다.'
   '||Whether a code is in scope is derived by rule from its attributes. The credit conversion factor and risk weight range come from the calculation engine constants, the population from the exposure ledger, and the applied rates from the result ledgers.',
   '코드와 사유는 둘 다 있어야 한다||Both the code and the reason are required',
   '코드 대상여부 예외||Scope exception for a code',
   '규칙 또는 예외 등재||Record the rule or the exception',
   '파이프라인 재실행||Re-run the pipeline',
   '상시 독립검증 (3선) 재요청||Request standing independent validation (3rd line) again',
   '화면 매트릭스는 규칙 파생이다. 예외도 코드가 돼야 산출에 반영된다.'
   '||The matrix on this screen is rule derived. An exception too has to become code before it reaches the calculation.',
   into=MESSAGES)
