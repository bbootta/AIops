"""ALM 계수 원장 — 현금흐름 엔진이 읽는 파라미터의 **유일한 출처**.

**왜 원장인가.** 현행 ALM은 계수를 소스에 박아 둔다: 버킷 9개는
`balance_sheet.py`의 리스트 리터럴, 시나리오 계수 −0.65/0.90/0.80/−0.60은
`irrbb.py` 함수 본문, NSFR 만기 분할 0.4/0.6은 산식 한가운데다. 박혀 있는
값은 화면에 나오지 않고, 화면에 없으면 검증도 결재도 그 값을 보지 못한다.
사용자 지시 — "화면은 반드시 연결되는 테이블이 있어야 하고, 그 테이블은
산출/수기 프로세스에서 만들어져야 한다" — 가 걸리는 자리가 정확히 여기다.

**빈 칸을 채우지 않는다.** 이 저장소 규약은 "값·계수를 지어내지 않는다"이다.
BCBS d368은 조기상환 기준율(CPR₀)·중도해지 기준율(TDRR₀)을 **주지 않는다** —
상품·통화별 은행 자체추정에 감독승인이다. 따라서 이 원장의 여러 칸은
`NULL` + `evidence_status='미확인'` 으로 **존재하되 비어 있다**. 엔진은 빈 칸을
만나면 조용히 기본값을 쓰지 않고 경고(`ParamWarning`)를 남기고 해당 조정을
건너뛴다. 비어 있음이 산출물에 보이는 것이 이 설계의 목적이다.

**빌더가 곧 수기입력 프로세스다.** "소스에 데이터를 하드코딩하지 않는다"는
*엔진*에 대한 규약이다. 규제표·승인값을 원장에 적재하는 곳은 한 군데여야 하고
그곳이 이 모듈의 `build_*` 함수다. 엔진(`cashflow`·`behaviour`)에는 계수가
한 개도 없다.

**미등록 상태.** 아래 TableSpec은 아직 `datamodel.catalog.ALL_TABLES`에 넣지
않았다. 카탈로그 등재는 `test_every_catalog_table_is_materialized_or_declared`
(실체화 필수)와 `test_architecture_doc_table_and_column_counts_match_the_catalog`
(ARCHITECTURE.md 수치 일치)를 동시에 만족해야 하므로, 파이프라인 배선 단계에서
`build_studio` 산출과 함께 등재한다. 스펙 품질 기준(grain·PK·float unit·
FK 대상 존재)은 지금부터 지킨다.

출처 표기 규칙
  citation          규정·문헌 조항
  evidence_status   원문확인 / 2차자료 / 원문미확인·현행계승 / 미확인
                    — 검색 스니펫만 본 값을 "확인"이라 적지 않는다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
# 버킷 경계는 이미 balance_sheet가 갖고 있다. 여기 다시 적으면 사다리가 두 벌이
# 되고, 규약("규제 상수는 별사본 금지")이 깨진다. import 해서 원장으로 옮긴다.
from risk_lib.alm.balance_sheet import REPRICING_BUCKETS as _HOUSE_BUCKETS
from risk_lib.alm.daycount import DAY_COUNTS
from risk_lib.alm.schedule import AMORT_TYPES, PAY_FREQS

__all__ = [
    "EVIDENCE_STATUS", "INPUT_SOURCES", "BEHAVIOUR_CLASSES", "RATE_TYPES",
    "NMD_CATEGORIES", "COUNTERPARTY_TYPES", "IRRBB_SCENARIOS", "SIDES",
    "BUCKET_FRAMEWORKS", "HEADLINE_BUCKET_FRAMEWORK", "OVERNIGHT_BUCKET_LABEL",
    "TIME_BUCKET", "PRODUCT_TERMS", "BEHAVIOUR_PARAM", "PREPAY_SCURVE_PARAM",
    "BEHAVIOUR_SCENARIO_MULT", "NMD_PARAM", "PARAM_TABLES",
    "build_time_bucket_ledger", "build_time_buckets", "build_product_terms",
    "build_behaviour_param",
    "build_prepay_scurve_param", "build_behaviour_scenario_mult",
    "build_nmd_param", "build_param_ledgers",
]

# ---------------------------------------------------------------- 어휘

# '재량·미규정' — 원문을 읽었고, 그 원문이 값을 정하지 않는다는 것까지 확인한
# 상태다. '미확인'(원문을 못 봤다)과 다른 사건이므로 어휘를 나눈다.
EVIDENCE_STATUS: tuple[str, ...] = (
    "원문확인", "2차자료", "원문미확인·현행계승", "재량·미규정", "미확인")
INPUT_SOURCES: tuple[str, ...] = (
    "자체추정", "표준벤치마크", "감독제시", "감독상한대체", "미확정")
BEHAVIOUR_CLASSES: tuple[str, ...] = (
    "none", "prepayment", "early_redemption", "nmd")
RATE_TYPES: tuple[str, ...] = ("fixed", "floating", "administered")
SIDES: tuple[str, ...] = ("asset", "liability", "off_balance")
# NMD 범주 어휘 = [별표 9-1] <표3>의 세 범주(소매/거래 · 소매/비거래 · 도매).
# BCBS d368 Annex 2 Table 2도 같은 세 줄이다. 계약의 counterparty_type과
# **같은 어휘**여야 조인이 성립한다.
NMD_CATEGORIES: tuple[str, ...] = (
    "retail_transactional", "retail_non_transactional", "wholesale_nonfin")
# 계약원장이 기록하는 거래상대 구분은 NMD 범주보다 넓다. 금융기관 예치금은
# 제8항 가(5)("(2)∼(4)에 해당하지 않는 비만기성예금은 도매예금")에 따라 도매로
# 귀속되므로 <표3>의 별도 범주가 아니다. 어휘를 분리해 두면 계약원장은 원천
# 구분을 잃지 않고, <표3> 원장은 원문에 없는 네 번째 줄을 만들지 않는다.
COUNTERPARTY_TYPES: tuple[str, ...] = NMD_CATEGORIES
IRRBB_SCENARIOS: tuple[str, ...] = (
    "parallel_up", "parallel_down", "steepener", "flattener",
    "short_up", "short_down")
BEHAVIOUR_MODELS: tuple[str, ...] = ("CPR", "TDRR")
SLOTTING_METHODS: tuple[str, ...] = (
    "linear", "decay_table", "replicating_portfolio")
BASE_MODELS: tuple[str, ...] = ("psa_100", "constant", "미확정")

_HOUSE = "house_9"
# 계정명을 'bcbs_19'에서 '표2_19'로 바꾼다. 이 사다리의 국내 근거는 [별표 9-1]
# <표2>이고 BCBS는 같은 값을 주는 두 번째 근거다. 계정명이 국제기준만 가리키면
# 국내 산출의 근거가 화면·서식에서 국제기준으로 읽힌다.
_TABLE2 = "표2_19"
BUCKET_FRAMEWORKS: tuple[str, ...] = (_HOUSE, _TABLE2)
# 헤드라인 계정. 원장의 is_headline 컬럼이 이 값에서 나오고, 엔진에 들어가는
# 버킷 뷰의 기본값이 된다. 현행 규정이 19구간이므로 헤드라인은 표2_19다.
# house_9(자체 집계 9구간)는 이력으로만 남긴다.
HEADLINE_BUCKET_FRAMEWORK: str = _TABLE2


# ---------------------------------------------------------------- 스펙

TIME_BUCKET = TableSpec(
    name="alm_time_bucket", korean="ALM 시간버킷 정의", product="PRD-ALM",
    grain="계정(framework_version) × 버킷 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False,
          allowed=BUCKET_FRAMEWORKS),
        C("seq", "int", "순서", nullable=False, min_value=1),
        C("label", "string", "버킷", nullable=False),
        C("lower_years", "float", "하한", nullable=False, unit="years",
          min_value=0.0),
        C("upper_years", "float", "상한", nullable=False, unit="years",
          min_value=0.0),
        C("t_mid_years", "float", "중점", nullable=False, unit="years",
          min_value=0.0),
        C("is_headline", "bool", "헤드라인 계정", nullable=False,
          note="산출에 실제로 쓰는 계정을 원장이 지정한다. 계정 전환은 이 "
               "컬럼과 build_time_buckets(framework_version=…)로 이뤄지며 "
               "소비처가 계정명을 소스에 박지 않는다"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "seq"),
    note="버킷 개수 K를 소스에서 뺀다 — 엔진은 K에 무관하게 동작한다. "
         "표2_19는 [별표 9-1] <표2>의 19구간이며 BCBS d578·d368의 시간버킷과 "
         "같다. house_9는 자체 집계 9구간이고 이력으로만 둔다. 두 계정이 한 "
         "원장에 있고 is_headline이 산출 계정을 정한다.",
)

PRODUCT_TERMS = TableSpec(
    name="alm_product_terms", korean="상품별 상환·이자 관행", product="PRD-ALM",
    grain="상품코드 1개당 1행",
    columns=(
        C("product_code", "string", "상품코드", nullable=False),
        C("korean", "text", "상품명", nullable=False),
        C("side", "string", "측", nullable=False, allowed=SIDES),
        C("amort_type", "string", "상환방식", nullable=False,
          allowed=AMORT_TYPES,
          citation="상환방식은 계약조건이며 현금흐름 형태를 결정한다"),
        C("pay_freq_per_year", "int", "연 지급횟수", nullable=False,
          allowed=PAY_FREQS),
        C("day_count", "string", "이자계산 관행", nullable=False,
          allowed=DAY_COUNTS, citation="ISDA 2006 Definitions §4.16"),
        C("rate_type", "string", "금리유형", nullable=False, allowed=RATE_TYPES),
        C("reset_freq_months", "int", "리프라이싱 주기", nullable=True,
          min_value=1, note="rate_type='floating'일 때만 의미가 있다"),
        C("grace_months", "int", "거치기간", nullable=False, min_value=0),
        C("balloon_ratio", "float", "만기 잔액 비율", nullable=False,
          unit="ratio", min_value=0.0, max_value=0.999),
        C("behaviour_class", "string", "행동모형 구분", nullable=False,
          allowed=BEHAVIOUR_CLASSES,
          citation="EBA/RTS/2022/09 — 표준방법이 인정하는 행동적 현금흐름 3종"),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("product_code",),
    note="원천 포트폴리오 28컬럼에 product_code·rate_type·day_count·amort_type이 "
         "하나도 없다 — 이 표는 합성 상품 카탈로그이며 실측이 아니다.",
)

BEHAVIOUR_PARAM = TableSpec(
    name="alm_behaviour_param", korean="행동모형 기준 파라미터", product="PRD-ALM",
    grain="기준일 × 파라미터셋 × 상품군 × 통화 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("param_set_id", "string", "파라미터셋", nullable=False),
        C("product_group", "string", "상품군", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("model", "string", "모형", nullable=False, allowed=BEHAVIOUR_MODELS),
        C("base_model", "string", "기준율 함수형", nullable=False,
          allowed=BASE_MODELS,
          citation="PSA 100%: CPR(m)=min(0.06, 0.002·m) — SIFMA Standard Formulas"),
        C("base_rate_annual", "float", "기준율(연율)", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="base_model='constant'일 때만 사용. PSA는 상품연령 함수라 스칼라가 아니다"),
        C("estimation_window_start", "date", "추정구간 시작", nullable=True),
        C("estimation_window_end", "date", "추정구간 종료", nullable=True),
        C("estimation_method", "text", "추정방법", nullable=True),
        C("backtest_mae_pp", "float", "백테스트 MAE", nullable=True, unit="%p",
          min_value=0.0,
          citation="SR 11-7 outcomes analysis — 실무기준 MAE ≤ 1~2%p"),
        C("input_source", "string", "입력출처", nullable=False,
          allowed=INPUT_SOURCES),
        C("entered_by", "string", "입력자", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_on", "date", "승인일", nullable=True),
        C("evidence_ref", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "param_set_id", "product_group", "ccy"),
    note="BCBS d368은 CPR₀·TDRR₀ 기준율을 주지 않는다 — 은행 자체추정 + 감독승인. "
         "따라서 이 표는 구조상 수기입력이며 값을 지어내면 규제 위반이다.",
)

PREPAY_SCURVE_PARAM = TableSpec(
    name="alm_prepay_scurve_param", korean="조기상환 S-curve 계수",
    product="PRD-ALM",
    grain="기준일 × 파라미터셋 × 상품군 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("param_set_id", "string", "파라미터셋", nullable=False),
        C("product_group", "string", "상품군", nullable=False),
        C("functional_form", "text", "함수형", nullable=False,
          citation="Richard & Roll (1989) — RI = a + b·arctan(c·(x − d)), "
                   "x = 리파이낸싱 인센티브. 함수형은 공표, 계수는 미확인"),
        C("coef_a", "float", "계수 a", nullable=True, unit="ratio"),
        C("coef_b", "float", "계수 b", nullable=True, unit="ratio"),
        C("coef_c", "float", "계수 c", nullable=True, unit="1/ratio"),
        C("coef_d", "float", "계수 d", nullable=True, unit="ratio"),
        C("refi_rate_ref", "string", "시장 리파이낸싱 금리 참조", nullable=True,
          note="어느 시장금리를 인센티브 기준으로 쓰는지 — 값이 아니라 출처"),
        C("refi_rate", "float", "시장 리파이낸싱 금리", nullable=True, unit="ratio",
          note="curve.py가 mkt_risk_factor를 연결하면 커브에서 온다. "
               "그전까지는 수기입력이며 미입력이면 NULL"),
        C("deduct_prepay_fee", "bool", "중도상환수수료 차감", nullable=False,
          note="수수료를 인센티브에서 차감하는 방식(일시금 대 연환산)에 규제 근거 없음"),
        C("enabled", "bool", "사용", nullable=False,
          note="False면 엔진은 S-curve를 쓰지 않고 표준방법 승수로 간다"),
        C("input_source", "string", "입력출처", nullable=False,
          allowed=INPUT_SOURCES),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("asof", "param_set_id", "product_group"),
    note="국내 MBS 실증에서 조기상환은 금리갭 2%p 초과 구간부터 오히려 하락하는 "
         "단봉형으로 보고된다 — 미국식 단조 arctan을 이식하면 고금리갭을 "
         "과대추정한다. 계수를 비워 두는 것은 결함이 아니라 이 사실의 표시다.",
)

BEHAVIOUR_SCENARIO_MULT = TableSpec(
    name="alm_behaviour_scenario_mult", korean="행동모형 시나리오 승수",
    product="PRD-ALM",
    grain="모형 × 시나리오 1행",
    columns=(
        C("model", "string", "모형", nullable=False, allowed=BEHAVIOUR_MODELS),
        C("scenario", "string", "시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS),
        C("multiplier", "float", "승수", nullable=True, unit="배", min_value=0.0,
          citation="[별표 9-1] <표4> — CPR_{i,k}=min(1, γ_i·CPR_{0,k}) 제9항 "
                   "다(2) / TDRR_i=min(1, u_i·TDRR_0) 제10항 다(2)"),
        C("direction_rule", "text", "방향성", nullable=False),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("model", "scenario"),
    note="12행 전건이 <표4>의 값이다. 평행·단기 축에서만 두 승수의 방향이 "
         "반대이고, 회전(스티프너·플래트너) 축은 두 승수가 같은 값이다. "
         "중도해지 현금흐름은 만기 '1일' 구간에 배분한다(제10항 라).",
)

NMD_PARAM = TableSpec(
    name="alm_nmd_param", korean="비만기예금 코어 분해", product="PRD-ALM",
    grain="기준일 × NMD 범주 × 통화 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("nmd_category", "string", "NMD 범주", nullable=False,
          allowed=NMD_CATEGORIES,
          citation="[별표 9-1] <표3> 비만기성예금의 범주별 핵심예금비율 및 "
                   "평균만기의 상한 (개정 2026.1.29) — 소매/거래 · 소매/비거래 · "
                   "도매 세 줄. BCBS d368 Annex 2 Table 2도 같은 세 줄이다"),
        C("korean", "text", "범주명", nullable=False,
          note="<표3>이 쓰는 국문 표기 그대로. 서식·화면이 범주명을 다시 "
               "번역하면 원문과 어긋난다"),
        C("category_rule", "text", "범주 판정 기준", nullable=False,
          citation="[별표 9-1] 제8항 가 (1)~(5) — 범주를 무엇으로 가르는지가 "
                   "상한값만큼이나 산출을 바꾼다. 판정 기준이 원장에 없으면 "
                   "슬로팅 결과를 재현할 수 없다"),
        C("sme_lookthrough_krw", "float", "소매 유사 간주 기준", nullable=True,
          unit="KRW", min_value=0.0,
          citation="[별표 9-1] 제8항 가(3) — 중소기업이 예치한 예금 중 소매계정 "
                   "으로 관리하고 해당 중소기업으로부터의 자금조달 총액이 "
                   "15억원(연결기준) 미만이면 소매예금과 유사한 것으로 간주. "
                   "도매 범주에는 해당 조항이 없어 NULL이다"),
        C("ccy", "string", "통화", nullable=False),
        C("stable_ratio", "float", "안정예금 비율", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="core ⊆ stable — 은행 자체추정 필요. 미추정이면 NULL"),
        C("core_ratio", "float", "코어 비율", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("core_ratio_cap", "float", "코어 비율 상한", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 9-1] <표3> — 소매/거래 90% · 소매/비거래 70% · "
                   "도매 50%. 원문 <표3>은 이 세 줄뿐이며 금융기관 범주가 없다"),
        C("avg_maturity_years", "float", "평균만기", nullable=True, unit="years",
          min_value=0.0),
        C("avg_maturity_cap_years", "float", "평균만기 상한", nullable=False,
          unit="years", min_value=0.0,
          citation="[별표 9-1] <표3> — 5년 · 4.5년 · 4년"),
        C("slotting_method", "string", "슬로팅 방법", nullable=False,
          allowed=SLOTTING_METHODS,
          citation="[별표 9-1] 제8항 다(1) — 범주별 핵심예금은 <표3>의 평균만기 "
                   "상한을 고려해 <표2>의 적절한 만기구간에 배분한다"),
        C("non_core_bucket_label", "string", "비핵심예금 배분 구간",
          nullable=False,
          citation="[별표 9-1] 제8항 다(2) — 비핵심예금은 익일물예금으로 "
                   "간주되며 만기 '1일' 구간에 배분한다. <표1>도 비핵심예금과 "
                   "MMDA를 1일로 분류한다"),
        C("pass_through_beta", "float", "예금베타", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("input_source", "string", "입력출처", nullable=False,
          allowed=INPUT_SOURCES),
        C("entered_by", "string", "입력자", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_on", "date", "승인일", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "nmd_category", "ccy"),
    note="<표3>의 세 범주가 전부다. 금융기관 예금을 별도 범주로 두거나 코어 0%로 "
         "못박는 행은 국내기준에도 국제기준에도 없다 — 제8항 가(5)가 "
         "'(2)∼(4)에 해당하지 않는 비만기성예금은 도매예금으로 구분한다'고 "
         "적으므로 금융기관 예치금은 도매로 귀속된다. "
         "잔액은 여기 두지 않는다 — 계약원장(alm_contract)이 원본이다.",
)

PARAM_TABLES: tuple[TableSpec, ...] = (
    TIME_BUCKET, PRODUCT_TERMS, BEHAVIOUR_PARAM, PREPAY_SCURVE_PARAM,
    BEHAVIOUR_SCENARIO_MULT, NMD_PARAM,
)


# ---------------------------------------------------------------- 빌더

def _as_float(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    """전량 NULL인 실수 컬럼을 float64로 고정한다.

    pandas는 전부 None인 컬럼을 object로 만든다. 그대로 두면 스펙 검증이
    dtype 위반으로 잡는다 — "비어 있음"과 "타입이 틀림"은 다른 사건이고,
    후자로 위장되면 전자가 안 보인다.
    """
    return df.astype({c: "float64" for c in cols})


# [별표 9-1] <표2> 만기구간 19구간. BCBS d578·d368의 시간버킷과 동일하다.
# 경계 규약은 (하한, 상한] 이며 원문이 `1일 < t ≤ 1M` 형식으로 적는다
# (1차자료 §B-2). 중점은 원문 괄호 안의 값을 그대로 옮긴다.
# (라벨, 하한, 상한, 중점) — 상한·중점 단위는 년.
_M, _D = 1.0 / 12.0, 0.0028      # 1개월, 익일물 중점(원문 표기 0.0028년)
_BCBS19_BUCKETS: tuple[tuple[str, float, float, float], ...] = (
    # 첫 구간의 라벨은 원문 표기 '1일(O/N)'을 쓴다. 제8항 다(2)·제10항 라가
    # 비핵심예금과 중도해지 현금흐름을 만기 '1일' 구간에 배분하라고 이름으로
    # 지시하므로, 라벨이 그 이름과 다르면 원장 조인이 규정 문구와 끊긴다.
    ("1일(O/N)",  0.0,    _D,     _D),
    ("1일-1M",    _D,     1 * _M,  0.0417),
    ("1M-3M",     1 * _M, 3 * _M,  0.1667),
    ("3M-6M",     3 * _M, 6 * _M,  0.375),
    ("6M-9M",     6 * _M, 9 * _M,  0.625),
    ("9M-1Y",     9 * _M, 1.0,     0.875),
    ("1Y-1.5Y",   1.0,    1.5,     1.25),
    ("1.5Y-2Y",   1.5,    2.0,     1.75),
    ("2Y-3Y",     2.0,    3.0,     2.5),
    ("3Y-4Y",     3.0,    4.0,     3.5),
    ("4Y-5Y",     4.0,    5.0,     4.5),
    ("5Y-6Y",     5.0,    6.0,     5.5),
    ("6Y-7Y",     6.0,    7.0,     6.5),
    ("7Y-8Y",     7.0,    8.0,     7.5),
    ("8Y-9Y",     8.0,    9.0,     8.5),
    ("9Y-10Y",    9.0,    10.0,    9.5),
    ("10Y-15Y",   10.0,   15.0,    12.5),
    ("15Y-20Y",   15.0,   20.0,    17.5),
    # 마지막 버킷은 개방구간(tCF > 20Y)이다. 원문이 주는 것은 중점 t_K = 25년뿐
    # 이므로 상한도 25년으로 적는다 — 상한을 임의로 늘리면 원문에 없는 경계를
    # 만드는 것이고, 비워 두면 사다리가 끊긴다. 개방구간이라는 사실은 citation에
    # 남긴다.
    ("20Y+",      20.0,   25.0,    25.0),
)

_BCBS19_CITATION = (
    "은행업감독업무시행세칙 [별표 9-1] <표2> 만기구간 (개정 2026.1.29) — "
    "19개 구간과 중간시점. 경계 규약 (하한, 상한]. 마지막 구간은 t > 20Y "
    "개방구간이며 중점 25년. BCBS d578 [SRP31.89] · d368 Annex 2 Table 1의 "
    "시간버킷과 동일하다 (1차자료 §B-2)")

# 비핵심예금·중도해지 현금흐름이 배분되는 구간의 라벨. 원장의 첫 행에서 뽑아
# 두 곳(버킷 사다리와 NMD 원장)이 같은 문자열을 쓰게 한다.
OVERNIGHT_BUCKET_LABEL: str = _BCBS19_BUCKETS[0][0]


def build_time_bucket_ledger() -> pd.DataFrame:
    """시간버킷 원장 전량 — 자체 집계 9개 + <표2> 19개.

    두 계정을 한 원장에 둔다. 어느 쪽으로 산출하는지는 `is_headline`이 정하고,
    엔진에 들어가는 프레임은 `build_time_buckets`가 그 컬럼으로 골라 준다.
    계정명이 소비처 소스에 박히지 않아야 전환이 배선 한 곳에서 끝난다.

    **헤드라인이 표2_19다.** [별표 9-1] <표2>가 19구간을 규정하므로 자체 집계
    9구간을 헤드라인에 두면 산출 축이 규정과 어긋난다. house_9는 이력 보존과
    시계열 단절 설명 용도로만 남긴다.

    **citation 정정.** `catalog.REPRICING_GAP.bucket`은 자체집계 9개에
    "SRP31.94 표준 만기 구간"이라는 근거를 달고 있으나 규정 구간은 19개다.
    9개 자체집계에 표준 조항을 다는 것은 감사에서 그대로 읽히는 자리의 허위
    표기이므로 house_9 행의 근거는 자체집계로 적는다.
    """
    rows, lower = [], 0.0
    for seq, (label, t_mid, upper) in enumerate(_HOUSE_BUCKETS, start=1):
        rows.append({
            "framework_version": _HOUSE, "seq": seq, "label": label,
            "lower_years": lower, "upper_years": float(upper),
            "t_mid_years": float(t_mid),
            "is_headline": _HOUSE == HEADLINE_BUCKET_FRAMEWORK,
            "citation": "자체 집계 사다리 — BCBS 표준 19버킷(bcbs_19)이 아니다",
            "evidence_status": "미확인",
        })
        lower = float(upper)
    for seq, (label, lo, hi, t_mid) in enumerate(_BCBS19_BUCKETS, start=1):
        rows.append({
            "framework_version": _TABLE2, "seq": seq, "label": label,
            "lower_years": float(lo), "upper_years": float(hi),
            "t_mid_years": float(t_mid),
            "is_headline": _TABLE2 == HEADLINE_BUCKET_FRAMEWORK,
            "citation": _BCBS19_CITATION,
            "evidence_status": "원문확인",
        })
    return pd.DataFrame(rows)


def build_time_buckets(framework_version: str | None = None) -> pd.DataFrame:
    """엔진에 들어가는 버킷 프레임 — 한 계정만 골라 준다.

    슬로팅 엔진은 사다리 한 벌을 전제로 seq 순서를 읽으므로, 두 계정이 섞인
    프레임을 넘기면 경계 배열이 단조가 아니게 되어 배정이 조용히 틀린다.
    `framework_version=None`이면 원장의 `is_headline` 행을 쓴다.
    """
    led = build_time_bucket_ledger()
    if framework_version is None:
        d = led[led["is_headline"].astype(bool)]
    else:
        d = led[led["framework_version"] == framework_version]
        if d.empty:
            raise KeyError(
                f"alm_time_bucket에 framework_version={framework_version!r} 행이 "
                f"없다 — 적재된 계정은 {list(BUCKET_FRAMEWORKS)}이다")
    return d.sort_values("seq").reset_index(drop=True)


# 합성 상품 카탈로그. 상환방식·지급주기·이자관행의 조합은 국내 은행 상품의
# 통상적 형태를 따르되 **실측이 아니다** (원천에 해당 컬럼이 없다 — §5.17).
_PRODUCTS: tuple[tuple, ...] = (
    # (code, korean, side, amort, freq, daycount, rate_type, reset, grace,
    #  balloon, behaviour_class)
    ("LN_CORP_FIX",  "기업대출(고정)", "asset", "equal_principal", 4,
     "ACT/365F", "fixed", None, 0, 0.0, "none"),
    ("LN_CORP_FLT",  "기업대출(변동)", "asset", "bullet", 4,
     "ACT/365F", "floating", 3, 0, 0.0, "none"),
    ("LN_RETAIL",    "가계신용대출", "asset", "annuity", 12,
     "ACT/365F", "floating", 6, 0, 0.0, "none"),
    ("LN_MTG_FIX",   "주택담보대출(고정)", "asset", "annuity", 12,
     "ACT/365F", "fixed", None, 12, 0.0, "prepayment"),
    ("LN_MTG_FLT",   "주택담보대출(변동)", "asset", "grace_then_annuity", 12,
     "ACT/365F", "floating", 6, 36, 0.0, "prepayment"),
    ("LN_BANK",      "은행간대출", "asset", "bullet", 4,
     "ACT/360", "floating", 3, 0, 0.0, "none"),
    ("LN_SOV",       "국공채 대출", "asset", "bullet", 2,
     "30/360", "fixed", None, 0, 0.0, "none"),
    ("SEC_HQLA_L1",  "고유동성자산 Level 1", "asset", "bullet", 2,
     "ACT/ACT_ISDA", "fixed", None, 0, 0.0, "none"),
    ("SEC_HQLA_L2A", "고유동성자산 Level 2A", "asset", "bullet", 2,
     "ACT/ACT_ISDA", "fixed", None, 0, 0.0, "none"),
    ("SEC_HQLA_L2B", "고유동성자산 Level 2B", "asset", "bullet", 2,
     "ACT/ACT_ISDA", "fixed", None, 0, 0.0, "none"),
    ("DEP_NMD_RT",   "요구불예금(소매 결제성)", "liability", "non_maturity", 12,
     "ACT/365F", "administered", None, 0, 0.0, "nmd"),
    ("DEP_NMD_RNT",  "저축예금(소매 비결제성)", "liability", "non_maturity", 12,
     "ACT/365F", "administered", None, 0, 0.0, "nmd"),
    ("DEP_NMD_WNF",  "기업 요구불예금", "liability", "non_maturity", 12,
     "ACT/365F", "administered", None, 0, 0.0, "nmd"),
    ("DEP_NMD_FI",   "금융기관 예치금", "liability", "non_maturity", 12,
     "ACT/365F", "administered", None, 0, 0.0, "nmd"),
    ("DEP_TERM_RT",  "정기예금(소매)", "liability", "bullet", 4,
     "ACT/365F", "fixed", None, 0, 0.0, "early_redemption"),
    ("DEP_TERM_CORP", "정기예금(기업)", "liability", "bullet", 4,
     "ACT/365F", "fixed", None, 0, 0.0, "early_redemption"),
    ("FUND_WS_ST",   "도매조달(단기)", "liability", "bullet", 4,
     "ACT/360", "floating", 3, 0, 0.0, "none"),
    ("FUND_WS_LT",   "도매조달(장기)", "liability", "bullet", 2,
     "30/360", "fixed", None, 0, 0.0, "none"),
    ("OWN_EQUITY",   "자기자본", "liability", "non_maturity", 1,
     "30/360", "administered", None, 0, 0.0, "none"),
)


def build_product_terms() -> pd.DataFrame:
    """상품 관행 원장."""
    return pd.DataFrame([{
        "product_code": p[0], "korean": p[1], "side": p[2], "amort_type": p[3],
        "pay_freq_per_year": p[4], "day_count": p[5], "rate_type": p[6],
        "reset_freq_months": p[7], "grace_months": p[8], "balloon_ratio": p[9],
        "behaviour_class": p[10],
        # 관행 조합 자체가 합성이다 — 원천에 없는 것을 확인이라 적지 않는다.
        "evidence_status": "미확인",
    } for p in _PRODUCTS]).astype({"reset_freq_months": "Int64"})


def build_behaviour_param(asof: str, *, param_set_id: str = "BASE") -> pd.DataFrame:
    """행동모형 기준율 원장.

    CPR₀ — PSA 100%(SIFMA 공표 표준)로 적재한다. 지어낸 값이 아니지만 **미국
    MBS 관행**이며 국내 실증근거가 없다(§5.18). base_model='psa_100'이면
    behaviour가 상품연령에서 CPR을 만든다.
    TDRR₀ — 대응하는 공표 표준이 없다. NULL로 두고 엔진이 조정을 건너뛴다.
    """
    common = {
        "asof": asof, "param_set_id": param_set_id, "ccy": "KRW",
        "estimation_window_start": None, "estimation_window_end": None,
        "backtest_mae_pp": None,          # 실측 CPR 시계열이 없어 산출 불가(§5.28)
        "entered_by": None, "approved_by": None, "approved_on": None,
    }
    return pd.DataFrame([
        {**common,
         "product_group": "mortgage", "model": "CPR",
         "base_model": "psa_100", "base_rate_annual": None,
         "estimation_method": "PSA 100% = min(0.06, 0.002·경과월)",
         "input_source": "표준벤치마크",
         "evidence_ref": "SIFMA Standard Formulas — PSA prepayment model",
         "evidence_status": "2차자료"},
        {**common,
         "product_group": "term_deposit", "model": "TDRR",
         "base_model": "미확정", "base_rate_annual": None,
         "estimation_method": None,
         "input_source": "미확정",
         "evidence_ref": "공표 표준 없음 — 은행 과거 중도해지 실적 필요. "
                         "저장소에 해지 이력 원장이 없다(§5.18)",
         "evidence_status": "미확인"},
    ]).pipe(_as_float, "base_rate_annual", "backtest_mae_pp")


def build_prepay_scurve_param(asof: str, *,
                              param_set_id: str = "BASE") -> pd.DataFrame:
    """조기상환 S-curve 계수 원장 — **전 계수 NULL, 미사용**이 초기 상태.

    Richard-Roll의 함수형(arctan 승법구조)은 공표돼 있으나 추정계수는 확인하지
    못했다(§5.20). 국내는 단조 S-curve 자체가 misspecified일 수 있다(§5.19).
    계수를 채우려면 이 원장에 승인된 값을 넣어야 하며, 그때 `enabled=True`가
    된다. 엔진은 enabled=False이면 표준방법 승수(d368 Table 3)로 간다.
    """
    return pd.DataFrame([{
        "asof": asof, "param_set_id": param_set_id, "product_group": "mortgage",
        "functional_form": "RI(x) = a + b·arctan(c·(x − d)), "
                           "x = coupon_rate − refi_rate (수수료 차감 후)",
        "coef_a": None, "coef_b": None, "coef_c": None, "coef_d": None,
        "refi_rate_ref": None, "refi_rate": None,
        "deduct_prepay_fee": True,
        "enabled": False,
        "input_source": "미확정",
        "evidence_status": "미확인",
        "note": "함수형만 확인. 계수·표본기간 미확인이므로 계수화 금지. "
                "burnout(경로의존)은 단일 시점 산출로 표현 불가 — 미구현.",
    }]).pipe(_as_float, "coef_a", "coef_b", "coef_c", "coef_d", "refi_rate")


# [별표 9-1] <표4> — 조기상환율 승수 γ(제9항 다(2))와 중도해지율 승수 u
# (제10항 다(2))를 한 표에 담는다. 원문 순서는 시나리오 1~6이며
# γ = 0.8/1.2/0.8/1.2/0.8/1.2, u = 1.2/0.8/0.8/1.2/1.2/0.8 이다.
# BCBS d368 Annex 2 Table 3·4와 값이 같다(1차자료 §B-5).
# 회전 시나리오(3 스티프너 · 4 플래트너)에서 두 승수가 **같은 값이다**.
# 평행·단기 축의 반대 방향을 회전 축까지 일반화하면 네 칸이 틀린다.
_SCENARIO_MULT: dict[str, dict[str, float]] = {
    "CPR":  {"parallel_up": 0.8, "parallel_down": 1.2, "steepener": 0.8,
             "flattener": 1.2, "short_up": 0.8, "short_down": 1.2},
    "TDRR": {"parallel_up": 1.2, "parallel_down": 0.8, "steepener": 0.8,
             "flattener": 1.2, "short_up": 1.2, "short_down": 0.8},
}

_MULT_RULE: dict[str, str] = {
    "CPR": "평행·단기 충격에서 금리 상승 시 조기상환 감소(γ=0.8) — 인센티브 "
           "역관계. 회전 시나리오는 <표4>가 스티프너 0.8 · 플래트너 1.2로 "
           "직접 정한다",
    "TDRR": "평행·단기 충격에서 금리 상승 시 중도해지 증가(u=1.2) — 재예치 유인 "
            "정관계. 회전 시나리오는 <표4>가 스티프너 0.8 · 플래트너 1.2로 "
            "직접 정하며 이 두 칸은 조기상환 승수와 값이 같다",
}


def build_behaviour_scenario_mult() -> pd.DataFrame:
    """시나리오 승수표 ([별표 9-1] <표4>) — 12행 전건 적재.

    구조식은 `CPR_{i,k} = min(1, γ_i·CPR_{0,k})`(제9항 다(2)) /
    `TDRR_i = min(1, u_i·TDRR_0)`(제10항 다(2)) 이다.
    승수 12칸은 원문확인이고, 기준율 `CPR_0`·`TDRR_0`는 규정이 주지 않는다
    (은행이 과거자료로 통화별·포트폴리오별 산출) — 그쪽은
    `alm_behaviour_param`에서 계속 비어 있다.
    """
    cite = ("[별표 9-1] <표4> 금리충격 시나리오에 따른 고정금리대출 조기상환율 "
            "및 기간부예수금 중도해지율 승수 (개정 2026.1.29) = BCBS d368 "
            "Annex 2 Table 3·4 — 1차자료 §B-5")
    return pd.DataFrame([
        {"model": model, "scenario": sc, "multiplier": _SCENARIO_MULT[model][sc],
         "direction_rule": _MULT_RULE[model], "citation": cite,
         "evidence_status": "원문확인"}
        for model in BEHAVIOUR_MODELS for sc in IRRBB_SCENARIOS])


# [별표 9-1] <표3> — 범주별 핵심예금 비율 상한 / 평균만기 상한.
# 세 줄이 전부다. BCBS d368 Annex 2 Table 2도 같은 세 줄이며 값도 같다.
# 직전 회차가 넣었던 네 번째 행(`financial`, 코어 0%)은 국내기준에도 국제기준
# 에도 없다. 제8항 가(5)가 "(2)∼(4)에 해당하지 않는 비만기성예금은 도매예금
# 으로 구분한다"고 적으므로 금융기관 예치금은 도매 범주로 귀속된다.
# (범주, 국문 표기, 코어상한, 평균만기상한, 소매 유사 간주 기준, 판정 기준)
_NMD_CAPS: tuple[tuple[str, str, float, float, float | None, str], ...] = (
    ("retail_transactional", "소매/거래", 0.90, 5.0, 1_500_000_000.0,
     "제8항 가(2)·(4) — 개인이 예치한 예금(법인·개인사업자 제외) 중 정기적 "
     "거래가 이루어지거나 이자를 지급하지 않는 예금. 가(3)에 따라 소매계정으로 "
     "관리하는 중소기업 예금 중 자금조달 총액 15억원(연결기준) 미만이면 소매와 "
     "유사한 것으로 간주한다"),
    ("retail_non_transactional", "소매/비거래", 0.70, 4.5, 1_500_000_000.0,
     "제8항 가(2)·(4) — 개인이 예치한 예금 중 거래예금에 해당하지 않는 예금. "
     "가(3)의 15억원 중소기업 간주 규정은 소매 판정에 동일하게 적용된다"),
    ("wholesale_nonfin", "도매", 0.50, 4.0, None,
     "제8항 가(5) — (2)∼(4)에 해당하지 않는 비만기성예금 전부. 금융기관이 "
     "예치한 비만기성예금도 여기 귀속된다(별도 범주가 원문에 없다)"),
)


def build_nmd_param(asof: str) -> pd.DataFrame:
    """NMD 코어 분해 파라미터 — [별표 9-1] <표3>의 세 범주.

    **초기 적재는 상한값 그대로이며 보수적이지 않다.** 코어를 늘리면 부채
    슬로팅이 길어져 ΔEVE 효과가 갭 방향에 따라 양쪽으로 간다(§5.26). 따라서
    input_source='감독상한대체'로 표시해 자체추정과 구분하고, 챌린저(코어 0%)
    대조가 필요하다는 사실을 남긴다. 제8항 나(2)는 과거 잔액 변동 관찰로
    범주별 핵심예금 규모를 산출하고 나(3)에서 <표3> 상한을 적용하라고 정하므로,
    상한을 그대로 쓰는 것은 관찰 단계를 건너뛴 자리표시다.

    범주 판정 기준(제8항 가)과 비핵심예금 배분 구간(제8항 다(2))을 컬럼으로
    둔다. 상한값만 있고 판정 기준이 없으면 어느 잔액이 어느 줄에 붙었는지
    산출물에서 재현되지 않는다.

    stable_ratio·pass_through_beta는 은행 고유 데이터로만 추정 가능하므로
    NULL이다(§5.21).
    """
    return pd.DataFrame([{
        "asof": asof, "nmd_category": cat, "korean": ko,
        "category_rule": rule, "sme_lookthrough_krw": sme, "ccy": "KRW",
        "stable_ratio": None,
        # 코어비율·평균만기는 상한을 그대로 쓴다 — 추정이 아니라 자리표시.
        "core_ratio": cap, "core_ratio_cap": cap,
        "avg_maturity_years": mat, "avg_maturity_cap_years": mat,
        "slotting_method": "linear",
        "non_core_bucket_label": OVERNIGHT_BUCKET_LABEL,
        "pass_through_beta": None,
        "input_source": "감독상한대체",
        "entered_by": None, "approved_by": None, "approved_on": None,
        "evidence_status": "원문확인",
    } for cat, ko, cap, mat, sme, rule in _NMD_CAPS]).pipe(
        _as_float, "stable_ratio", "pass_through_beta", "sme_lookthrough_krw")


def build_param_ledgers(asof: str, *, param_set_id: str = "BASE",
                        bucket_framework: str | None = None,
                        ) -> dict[str, pd.DataFrame]:
    """계수 원장 6장을 한 번에. 키는 테이블명 — 검증·실체화가 그대로 받는다.

    `bucket_framework`가 사다리 계정을 고른다. None이면 원장의 `is_headline`
    행을 쓴다. 슬로팅 엔진은 사다리 한 벌을 전제로 seq를 읽으므로 여기서
    반드시 한 계정만 내보낸다 — 두 계정을 섞어 넘기면 경계 배열이 단조가
    아니게 되어 배정이 조용히 틀린다. 표준 19버킷(`bcbs_19`)으로 갈아끼우는
    것은 이 인자 하나로 끝나며, 그 결정은 파이프라인이 한다.
    """
    return {
        "alm_time_bucket": build_time_buckets(bucket_framework),
        "alm_product_terms": build_product_terms(),
        "alm_behaviour_param": build_behaviour_param(
            asof, param_set_id=param_set_id),
        "alm_prepay_scurve_param": build_prepay_scurve_param(
            asof, param_set_id=param_set_id),
        "alm_behaviour_scenario_mult": build_behaviour_scenario_mult(),
        "alm_nmd_param": build_nmd_param(asof),
    }
