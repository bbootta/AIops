"""행동모형 추정 엔진. 관측이력에서 CPR₀ · TDRR₀ · 핵심예금 · 전가율을 만든다.

**규정이 은행에 추정을 요구한다.**

  제8항 나(2)  과거 잔액 변동을 관찰하여 비만기성예금의 각 범주별 핵심예금의
               규모를 산출하여야 한다
  제9항 다(1)  은행은 과거자료 등을 사용하여 통화별로 조기상환위험이 있는
               고정금리대출의 각 포트폴리오에 대하여 만기구간별 기본조기상환율을
               산출한다
  제10항 다(1) 은행은 과거자료 등을 사용하여 통화별로 중도해지위험이 있는
               기간부예수금의 각 포트폴리오에 대하여 기본중도해지율을 산출한다

값은 규정이 주지 않는다. 그래서 이 모듈이 만드는 것은 값이 아니라 **절차**이며,
절차의 산출물은 `alm_behaviour_model`·`alm_behaviour_backtest`·
`alm_nmd_core_method_compare` 세 원장에 남는다. <표7> 가(7)이 "조기상환율 및
중도해지율을 추정하는데 사용된 방법론과 기타 주요 가정사항"을 정성공시하라고
정하므로, 방법론이 원장에 없으면 공시할 것이 없다.

**이 모듈에는 규제표도 행동계수도 없다.** 규제 상수(<표3> 상한 90/70/50%,
5/4.5/4년)는 `alm_nmd_param`에서 인자로 들어오고, 관측치는
`alm_prepay_observation` 등에서 인자로 들어온다. 모듈 상수는 두 종류뿐이다.

  `SOLVER`   수치해법 설정(초기값 척도·허용오차·반복한도). 행동 가정이 아니다
  `INTERNAL` 규정이 정하지 않아 은행이 정해야 하는 산출 규약(관찰 백분위·
             이동창 길이·표본외 기간). 규정 미제시 사항이며 원장 컬럼과
             `params_json`으로 나가 공시·검증 대상이 된다

**추정이 안 되면 추정하지 않는다.** S-curve가 수렴하지 않으면 계수를 NULL로
두고 그 포트폴리오를 미추정으로 남긴다. 조용히 표준벤치마크(PSA 100%)로
넘어가지 않는다. PSA는 미국 MBS 관행이며 국내 실증근거가 없다.

**결정론.** 난수가 없다. 최소자승·IRLS·격자탐색 전부 결정론이며 초기값은
관측 분위수에서 만든다. `hash()`·벽시계 시각을 쓰지 않는다.

규정이 비워 둔 자리 (지어내지 않고 규약으로 적어 남긴다)
  · CPR의 연율/기간율. 제9항 라는 CPR을 구간에 바로 곱한다. <표2> 구간 폭이
    1일부터 5년까지 다르므로 연율을 그대로 곱하면 단기 과대·장기 과소가 된다.
    원장은 **연율**을 담고 적용 단계가 `SMM = 1 − (1−CPR)^τ`로 환산한다는 규약을
    `cpr_convention`에 적는다.
  · TDRR의 측정 지평. 제10항 다·라에 기간 언급이 없다. 여기서는 월 해지율을
    연율화해 담고 `horizon_convention`에 적는다. 규정 미제시이므로
    `evidence_status='재량·미규정'`이다.
  · 백테스트 임계. [별표3 203.]은 연1회 이상 사후검증을 요구하나 행동모형
    임계치를 주지 않는다. 임계가 승인되기 전에는 NULL이고 판정은 '판정보류'다.
    임계 없이 PASS를 찍지 않는다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.alm.behaviour import nmd_slotting, seasoning_ramp
from risk_lib.alm.params import EVIDENCE_STATUS, INPUT_SOURCES, NMD_CATEGORIES

__all__ = [
    "SOLVER", "INTERNAL", "MODEL_KINDS", "TDRR_MODEL_FAMILIES",
    "NMD_CORE_METHODS", "HEADLINE_CORE_METHOD", "BACKTEST_JUDGEMENTS",
    "BEHAVIOUR_MODEL", "BEHAVIOUR_BACKTEST", "NMD_CORE_METHOD_COMPARE",
    "ESTIMATION_TABLES",
    "RampFit", "ScurveFit", "PrepayFit", "TdrrFit", "NmdCoreEstimate",
    "NmdBetaFit", "EstimationResult", "EstimationCheck", "InternalStandard",
    "cpr_from_smm", "fit_seasoning_ramp", "fit_scurve",
    "estimate_prepayment", "estimate_early_redemption",
    "estimate_nmd_core", "estimate_pass_through_beta",
    "apply_table3_caps", "run_estimation",
    "build_behaviour_model_ledger", "build_behaviour_backtest_ledger",
    "build_nmd_core_method_compare", "build_estimation_ledgers",
    "apply_estimates",
    "check_estimate_moves_cashflow", "check_table3_cap_binds",
    "check_backtest_is_out_of_time", "check_unconverged_left_unestimated",
    "check_pass_through_gap_closed", "check_core_methods_differ",
    "run_estimation_checks",
]


# ---------------------------------------------------------------- 어휘

MODEL_KINDS: tuple[str, ...] = ("CPR", "TDRR", "NMD_CORE", "NMD_BETA")
TDRR_MODEL_FAMILIES: tuple[str, ...] = ("logistic", "proportional_hazard")
NMD_CORE_METHODS: tuple[str, ...] = (
    "volatility_percentile", "rolling_min", "regression_replicating")
# 헤드라인 방법. 관측 최저잔액이라는 사실만 쓰고 분포가정을 두지 않아 재현이
# 쉽다는 이유로 고른다. 규정이 방법을 정하지 않으므로 이 선택 자체가 <표7>
# 가(7) 공시 대상이며, 세 방법의 결과는 비교 원장에 나란히 남는다.
HEADLINE_CORE_METHOD: str = "rolling_min"
BACKTEST_JUDGEMENTS: tuple[str, ...] = ("적합", "부적합", "판정보류")
FIT_STATUSES: tuple[str, ...] = ("수렴", "수렴실패", "표본부족", "표본무변동")


@dataclass(frozen=True)
class SolverControl:
    """수치해법 설정. 행동 가정이 아니라 최적화기 설정이다.

    S-curve는 표준화 좌표 `u = (x − x̄)/s_x` 위에서 적합한다. 인센티브 원단위는
    0.003 근방이고 기울기 계수는 100 단위라 그대로 풀면 야코비안 조건수가 커져
    수렴 판정이 초기값에 좌우된다. 표준화 후 `c = g/s_x`, `d = x̄ + h·s_x`로
    되돌린다.
    """
    scurve_g0: float             # 표준화 좌표에서의 기울기 초기값
    scurve_ftol: float
    scurve_xtol: float
    scurve_max_nfev: int
    irls_tol: float
    irls_max_iter: int
    burnout_grid: int            # 소진계수 1차 격자 분할수
    burnout_refine: int          # 2차 국소 격자 분할수
    backfit_iters: int           # 램프 ↔ S-curve 교대적합 횟수
    ridge: float                 # 정규방정식 안정화 항


SOLVER = SolverControl(
    scurve_g0=1.0, scurve_ftol=1e-12, scurve_xtol=1e-12, scurve_max_nfev=4000,
    irls_tol=1e-10, irls_max_iter=100,
    burnout_grid=25, burnout_refine=25, backfit_iters=4, ridge=1e-12,
)


@dataclass(frozen=True)
class InternalStandard:
    """규정이 정하지 않아 은행이 정해야 하는 산출 규약.

    전부 `evidence_status='재량·미규정'`이다. 원문을 읽었고 그 원문이 값을
    정하지 않는다는 것까지 확인한 상태이며, '미확인'(원문을 못 봤다)과 다르다.
    """
    core_percentile: float       # 변동성 기준 방법의 하위 백분위
    rolling_window_months: int   # 롤링 최소 방법의 이동창
    oos_months: int              # 표본외 검증기간 길이
    min_history_months: int      # 이 아래면 추정하지 않는다
    burnout_phi_max: float       # 소진계수 탐색 상한
    burnout_min_ssr_gain: float  # 이 아래 개선이면 소진계수를 미식별로 본다
    backtest_mae_threshold_pp: float | None   # 승인 전에는 None → 판정보류
    threshold_approved_by: str | None
    threshold_approved_on: str | None


INTERNAL = InternalStandard(
    core_percentile=0.05, rolling_window_months=12, oos_months=12,
    min_history_months=36, burnout_phi_max=0.90, burnout_min_ssr_gain=0.02,
    # 임계는 승인 전이라 비어 있다. 값을 넣으면 지어낸 임계로 PASS를 찍게 된다.
    # [별표3 203.]은 연1회 이상 사후검증을 요구하지만 행동모형 임계는 주지 않는다.
    backtest_mae_threshold_pp=None,
    threshold_approved_by=None, threshold_approved_on=None,
)

CPR_CONVENTION = (
    "원장은 연율 CPR을 담고, 적용 단계가 만기구간 폭 τ로 "
    "SMM = 1 − (1 − CPR)^τ 환산한다. 제9항 라가 CPR을 구간에 바로 곱하는데 "
    "<표2> 구간 폭이 1일부터 5년까지 다르므로, 연율을 그대로 곱하면 단기 구간이 "
    "과대·장기 구간이 과소가 된다. 규정 본문이 아니라 산출 규약이다")

TDRR_HORIZON_CONVENTION = (
    "월 해지율을 TDRR = 1 − (1 − 월해지율)^12 로 연율화한다. 제10항 다·라에 "
    "측정 지평 언급이 없어 규정 미제시이며, 지평을 바꾸면 ΔEVE가 직접 바뀐다")


# ---------------------------------------------------------------- 스펙

_EVID = C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS)

BEHAVIOUR_MODEL = TableSpec(
    name="alm_behaviour_model", korean="행동모형 추정 결과", product="PRD-ALM",
    grain="기준일 × 모형 × 포트폴리오 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("model", "string", "모형종류", nullable=False, allowed=MODEL_KINDS),
        C("portfolio_id", "string", "포트폴리오", nullable=False,
          note="CPR·TDRR은 상품군, NMD는 <표3> 범주가 들어온다"),
        C("ccy", "string", "통화", nullable=False,
          citation="[별표 9-1] 제9항 다(1)·제10항 다(1). 통화별 산출"),
        C("estimation_method", "text", "추정방법", nullable=False),
        C("functional_form", "text", "함수형", nullable=False),
        C("estimation_window_start", "string", "추정구간 시작", nullable=True,
          note="YYYY-MM"),
        C("estimation_window_end", "string", "추정구간 종료", nullable=True),
        C("n_obs", "int", "관측수", nullable=False, min_value=0),
        C("params_json", "text", "적합모수", nullable=True,
          note="키 정렬 JSON. 모수 개수가 모형마다 달라 컬럼으로 펴면 스키마가 "
               "모형에 종속된다. 재현에 필요한 수치해법 설정도 같이 담는다"),
        C("r_squared", "float", "적합도", nullable=True, unit="ratio"),
        C("converged", "bool", "수렴여부", nullable=False),
        C("fit_status", "string", "적합 상태", nullable=False,
          allowed=FIT_STATUSES),
        C("burnout_included", "bool", "소진효과 반영", nullable=True,
          note="CPR에만 의미가 있다. 반영 여부가 계수 해석을 바꾸므로 원장에 "
               "남긴다. 미반영이면 경과효과 천장이 소진을 흡수한다"),
        C("horizon_convention", "text", "지평 규약", nullable=True),
        C("headline_estimate", "float", "헤드라인 추정치", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="CPR₀·TDRR₀·코어비율·전가율. 모형별로 뜻이 달라 단위만 맞춘다"),
        C("message", "text", "비고", nullable=True),
        C("input_source", "string", "입력출처", nullable=False,
          allowed=INPUT_SOURCES),
        C("entered_by", "string", "입력자", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_on", "date", "승인일", nullable=True),
        _EVID,
    ),
    primary_key=("asof", "model", "portfolio_id"),
    note="수렴하지 않은 행은 converged=False·headline_estimate=NULL로 남고 계수 "
         "원장에 값을 쓰지 않는다. 이 원장에 행이 있다는 것과 추정이 됐다는 "
         "것은 다른 사건이다.",
)

BEHAVIOUR_BACKTEST = TableSpec(
    name="alm_behaviour_backtest", korean="행동모형 사후검증", product="PRD-ALM",
    grain="기준일 × 모형 × 포트폴리오 × 검증기간 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("model", "string", "모형종류", nullable=False, allowed=MODEL_KINDS),
        C("portfolio_id", "string", "포트폴리오", nullable=False),
        C("validation_window_start", "string", "검증구간 시작", nullable=False),
        C("validation_window_end", "string", "검증구간 종료", nullable=False),
        C("is_out_of_time", "bool", "표본외 여부", nullable=False,
          note="추정구간과 겹치면 항상 통과한다. 겹침 여부를 값으로 남긴다"),
        C("n_obs", "int", "검증 관측수", nullable=False, min_value=0),
        C("mean_actual_pp", "float", "실적치 평균", nullable=False, unit="%p"),
        C("mean_predicted_pp", "float", "예측치 평균", nullable=False, unit="%p"),
        C("bias_pp", "float", "편의", nullable=False, unit="%p",
          note="예측 − 실적. 부호가 있어야 과대·과소가 구분된다"),
        C("mae_pp", "float", "MAE", nullable=False, unit="%p", min_value=0.0),
        C("rmse_pp", "float", "RMSE", nullable=False, unit="%p", min_value=0.0),
        C("in_sample_mae_pp", "float", "표본내 MAE", nullable=True, unit="%p",
          min_value=0.0,
          note="표본외가 표본내보다 좋으면 누수를 의심한다"),
        C("threshold_mae_pp", "float", "판정 임계", nullable=True, unit="%p",
          min_value=0.0,
          citation="[별표3 203.]은 연1회 이상 사후검증을 요구하나 행동모형 "
                   "임계치를 정하지 않는다. 임계는 내부기준이며 승인 전에는 "
                   "NULL이다"),
        C("threshold_basis", "text", "임계 근거", nullable=False),
        C("judgement", "string", "판정", nullable=False,
          allowed=BACKTEST_JUDGEMENTS,
          note="임계가 NULL이면 '판정보류'다. 임계 없이 '적합'을 찍지 않는다"),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_on", "date", "승인일", nullable=True),
        _EVID,
    ),
    primary_key=("asof", "model", "portfolio_id", "validation_window_start"),
    note="검증구간은 추정구간 뒤쪽을 떼어 쓴다. 추정에 쓴 기간으로 검증하면 "
         "언제나 통과하므로 is_out_of_time이 False인 행은 판정 근거가 되지 "
         "않는다.",
)

NMD_CORE_METHOD_COMPARE = TableSpec(
    name="alm_nmd_core_method_compare", korean="비만기예금 코어 산출방법 비교",
    product="PRD-ALM",
    grain="기준일 × NMD 범주 × 산출방법 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("nmd_category", "string", "NMD 범주", nullable=False,
          allowed=NMD_CATEGORIES),
        C("ccy", "string", "통화", nullable=False),
        C("method", "string", "산출방법", nullable=False,
          allowed=NMD_CORE_METHODS,
          citation="[별표 9-1] 제8항 나(2)는 과거 잔액 변동 관찰을 요구할 뿐 "
                   "산식을 주지 않는다. 2014년판의 '최근월평잔 − 기간가중 "
                   "표준편차×2.33'은 2019.11.29 개정으로 폐지됐다. 방법 선택은 "
                   "은행 재량이며 <표7> 가(7) 공시 대상이다"),
        C("method_rule", "text", "방법 정의", nullable=False),
        C("is_headline", "bool", "헤드라인", nullable=False),
        C("base_balance", "float", "기준잔액", nullable=False, unit="KRW",
          min_value=0.0),
        C("stable_ratio", "float", "안정예금 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 9-1] 제8항 나(1). 인출가능성이 낮은 안정적 예금"),
        C("rate_sensitive_share", "float", "금리민감분 비중", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="[별표 9-1] 제8항 나(2). 안정적 예금 중 금리환경 변동 시에도 "
                   "금리개정 가능성이 낮은 부분이 핵심예금이다. 그 여집합"),
        C("core_ratio_raw", "float", "코어비율(상한 전)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("core_ratio", "float", "코어비율(상한 후)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("core_ratio_cap", "float", "코어비율 상한", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="[별표 9-1] <표3>. 소매/거래 90% · 소매/비거래 70% · 도매 50%"),
        C("core_cap_binding", "bool", "코어 상한 적용", nullable=False),
        C("decay_implied_maturity_years", "float", "감쇠율 함의 평균만기",
          nullable=True, unit="years", min_value=0.0,
          note="관측 잔액의 지수감쇠율 역수. 잔액이 증가 추세면 감쇠율이 "
               "음수라 추정치가 없고 NULL이다"),
        C("avg_maturity_years", "float", "평균만기(상한 후)", nullable=False,
          unit="years", min_value=0.0),
        C("avg_maturity_cap_years", "float", "평균만기 상한", nullable=False,
          unit="years", min_value=0.0,
          citation="[별표 9-1] <표3>. 5년 · 4.5년 · 4년"),
        C("maturity_cap_binding", "bool", "평균만기 상한 적용", nullable=False),
        C("achieved_avg_maturity_years", "float", "달성 평균만기", nullable=False,
          unit="years", min_value=0.0,
          note="버킷 이산화 후 실제 달성치. 슬로팅 격자 때문에 목표와 다르다"),
        C("core_amount", "float", "핵심예금 금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("shock_bp", "float", "적용 금리충격", nullable=False, unit="bp"),
        C("delta_eve_proxy_krw", "float", "ΔEVE 영향(1차 근사)", nullable=False,
          unit="KRW",
          note="−Σ CF_k·t_k·Δr 의 부호를 뒤집은 값. 부채 PV가 줄면 EVE는 는다. "
               "듀레이션 1차 근사이며 정식 ΔEVE는 irrbb.py 산출이다"),
        C("n_obs", "int", "관측수", nullable=False, min_value=0),
        C("observation_window_start", "string", "관찰구간 시작", nullable=False),
        C("observation_window_end", "string", "관찰구간 종료", nullable=False),
        C("input_source", "string", "입력출처", nullable=False,
          allowed=INPUT_SOURCES),
        _EVID,
    ),
    primary_key=("asof", "nmd_category", "method"),
    note="세 방법의 코어비율 차이가 ΔEVE를 얼마나 움직이는지가 이 표의 목적이다. "
         "차이가 0이면 방법이 산출에 닿지 않은 것이다.",
)

ESTIMATION_TABLES: tuple[TableSpec, ...] = (
    BEHAVIOUR_MODEL, BEHAVIOUR_BACKTEST, NMD_CORE_METHOD_COMPARE,
)


# ---------------------------------------------------------------- 결과 자료형

@dataclass(frozen=True)
class RampFit:
    """경과효과 램프 min(ceiling, slope·age)."""
    ceiling: float
    slope: float
    age_star_months: float       # 천장에 닿는 경과월 = ceiling / slope
    ssr: float


@dataclass(frozen=True)
class ScurveFit:
    """차환유인 S-curve a + b·arctan(c·(x − d)). x는 ratio 단위 인센티브."""
    a: float
    b: float
    c: float
    d: float
    converged: bool
    status: str
    message: str
    n_fev: int = 0


@dataclass(frozen=True)
class PrepayFit:
    portfolio_id: str
    ccy: str
    n_obs: int
    window: tuple[str, str]
    ramp: RampFit | None
    scurve: ScurveFit | None
    burnout_included: bool
    burnout_phi: float | None
    burnout_identified: bool
    burnout_ssr_gain: float | None
    r_squared: float | None
    converged: bool
    status: str
    message: str
    current_age_months: float
    current_incentive: float
    current_refi_rate: float
    headline_cpr0: float | None


@dataclass(frozen=True)
class TdrrFit:
    portfolio_id: str
    ccy: str
    n_obs: int
    window: tuple[str, str]
    model_family: str
    coef: dict[str, float]
    r_squared: float | None
    converged: bool
    status: str
    message: str
    current_monthly_hazard: float | None
    headline_tdrr0: float | None


@dataclass(frozen=True)
class NmdCoreEstimate:
    nmd_category: str
    ccy: str
    method: str
    method_rule: str
    n_obs: int
    window: tuple[str, str]
    base_balance: float
    stable_ratio: float
    rate_sensitive_share: float
    core_ratio_raw: float
    decay_implied_maturity_years: float | None


@dataclass(frozen=True)
class NmdBetaFit:
    nmd_category: str
    ccy: str
    n_obs: int
    window: tuple[str, str]
    beta_raw: float
    beta_applied: float
    clipped: bool
    r_squared: float
    converged: bool
    status: str
    message: str


@dataclass(frozen=True)
class EstimationCheck:
    """정합성 검사 1건. `consistency.ConsistencyCheck`로 1:1 매핑된다."""
    name: str
    status: str                  # PASS · WARN · FAIL
    detail: str
    metric: float | None = None


@dataclass
class EstimationResult:
    asof: str
    prepay: list[PrepayFit] = field(default_factory=list)
    tdrr: list[TdrrFit] = field(default_factory=list)
    nmd_core: list[NmdCoreEstimate] = field(default_factory=list)
    nmd_beta: list[NmdBetaFit] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 기본 변환

def cpr_from_smm(smm: float, period_years: float) -> float:
    """SMM → 연율 CPR. `behaviour.smm_from_cpr`의 역이다.

    선형근사 SMM×12를 쓰지 않는다. SMM 0.5%에서 근사는 CPR을 약 0.16%p
    과대계상하고, 그 편의가 그대로 CPR₀로 들어간다.
    """
    if period_years <= 0.0:
        raise ValueError(f"기간은 양수. 받은 값 {period_years}")
    s = min(max(float(smm), 0.0), 1.0)
    if s >= 1.0:
        return 1.0
    return 1.0 - (1.0 - s) ** (1.0 / period_years)


def _window(months: pd.Series) -> tuple[str, str]:
    m = sorted(str(x) for x in months)
    return (m[0], m[-1]) if m else ("", "")


def _r_squared(y: np.ndarray, pred: np.ndarray) -> float:
    sst = float(((y - y.mean()) ** 2).sum())
    ssr = float(((y - pred) ** 2).sum())
    return 1.0 - ssr / sst if sst > 0 else float("nan")


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray | None:
    """정규방정식 최소자승. 특이하면 None. 조용히 유사역행렬로 넘어가지 않는다.

    유사역행렬은 식별되지 않는 계수에도 값을 돌려주므로, 설명변수가 상수인
    경우(위약금 체계가 표본 안에서 안 바뀐 경우)에도 계수가 나온 것처럼 보인다.
    """
    XtX = X.T @ X
    XtX = XtX + SOLVER.ridge * np.eye(XtX.shape[0]) * max(float(np.trace(XtX)), 1.0)
    try:
        return np.linalg.solve(XtX, X.T @ y)
    except np.linalg.LinAlgError:
        return None


# ---------------------------------------------------------------- (b) 경과효과

def fit_seasoning_ramp(age_months: np.ndarray, y: np.ndarray) -> RampFit:
    """램프 `min(ceiling, slope·age)`를 최소자승 적합한다.

    (ceiling, slope) 대신 (age*, slope)로 모수화하면 정확해가 나온다. age*를
    고정하면 `m = min(age, age*)`가 정해지고 모형이 slope에 대해 선형이므로
    `slope = Σ(y·m)/Σ(m²)`가 닫힌 해다. age*는 관측된 경과월 격자를 전수
    훑는다. 격자 밖의 age*는 m을 바꾸지 않으므로 전수탐색이 곧 전역해다.

    천장이 표본 안에서 걸리지 않으면 최적 age*가 최대 경과월이 되고 램프는
    순수 선형이 된다. 그 사실은 `age_star_months`가 표본 최대치와 같은지로
    드러난다.
    """
    age = np.asarray(age_months, dtype=float)
    yy = np.asarray(y, dtype=float)
    best: RampFit | None = None
    for a_star in np.unique(age):
        m = np.minimum(age, a_star)
        denom = float((m * m).sum())
        if denom <= 0.0:
            continue
        slope = float((yy * m).sum() / denom)
        ssr = float(((yy - slope * m) ** 2).sum())
        if best is None or ssr < best.ssr:
            best = RampFit(ceiling=slope * float(a_star), slope=slope,
                           age_star_months=float(a_star), ssr=ssr)
    if best is None:
        raise ValueError("경과월 표본이 비어 램프를 적합할 수 없다")
    return best


# ---------------------------------------------------------------- (c) S-curve

def fit_scurve(x: np.ndarray, y: np.ndarray) -> ScurveFit:
    """`a + b·arctan(c·(x − d))`를 비선형 최소자승으로 적합한다.

    표준화 좌표 `u = (x − x̄)/s_x`에서 풀고 되돌린다. 원단위(인센티브 0.003
    근방, 기울기 100 단위)로 풀면 야코비안 조건수가 커서 수렴 판정이 초기값에
    좌우된다.

    초기값은 관측 분위수에서 만든다. 상수를 박으면 그것이 곧 숨은 사전정보다.
      a₀ = median(y), b₀ = (p90(y) − p10(y))/2, g₀ = SOLVER.scurve_g0, h₀ = 0

    **수렴하지 않으면 계수를 돌려주지 않는다.** 마지막 반복값을 돌려주면
    호출부가 그것을 추정치로 쓰고, 수렴실패가 산출물에서 사라진다.
    """
    xx = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float)
    nan = float("nan")
    if xx.size < 4:
        return ScurveFit(nan, nan, nan, nan, False, "표본부족",
                         f"관측 {xx.size}건. 모수 4개를 식별할 수 없다")
    # 무변동 판정은 표준편차가 아니라 최대-최소로 한다. 동일한 값을 모아 놓아도
    # 표준편차는 부동소수 반올림 때문에 1e-16 규모로 남아 0 비교를 빠져나간다.
    s_x = float(xx.std())
    if float(np.ptp(xx)) <= 0.0 or s_x <= 0.0:
        return ScurveFit(nan, nan, nan, nan, False, "표본무변동",
                         "인센티브가 표본 안에서 변하지 않는다. c·d가 식별되지 "
                         "않는다. 상수 인센티브에서 적합한 계수를 시나리오에 "
                         "외삽하면 근거 없는 값이 된다")
    x_bar = float(xx.mean())
    u = (xx - x_bar) / s_x

    a0 = float(np.median(yy))
    b0 = float(np.percentile(yy, 90) - np.percentile(yy, 10)) / 2.0
    if b0 == 0.0:
        return ScurveFit(nan, nan, nan, nan, False, "표본무변동",
                         "잔차가 표본 안에서 변하지 않는다. 진폭 b가 식별되지 않는다")

    def resid(p: np.ndarray) -> np.ndarray:
        a, b, g, h = p
        return a + b * np.arctan(g * (u - h)) - yy

    res = least_squares(resid, np.array([a0, b0, SOLVER.scurve_g0, 0.0]),
                        method="trf", ftol=SOLVER.scurve_ftol,
                        xtol=SOLVER.scurve_xtol, gtol=SOLVER.scurve_ftol,
                        max_nfev=SOLVER.scurve_max_nfev)
    a, b, g, h = (float(v) for v in res.x)
    if not res.success or res.status <= 0 or not all(
            math.isfinite(v) for v in (a, b, g, h)):
        return ScurveFit(nan, nan, nan, nan, False, "수렴실패",
                         f"least_squares status={res.status}: {res.message}",
                         int(res.nfev))
    if g == 0.0 or b == 0.0:
        return ScurveFit(nan, nan, nan, nan, False, "수렴실패",
                         "기울기 또는 진폭이 0으로 붕괴했다. 인센티브 반응이 "
                         "식별되지 않는다", int(res.nfev))
    return ScurveFit(a=a, b=b, c=g / s_x, d=x_bar + h * s_x,
                     converged=True, status="수렴",
                     message=f"nfev={int(res.nfev)}, status={res.status}",
                     n_fev=int(res.nfev))


def _scurve_value(fit: ScurveFit, x: np.ndarray) -> np.ndarray:
    return fit.a + fit.b * np.arctan(fit.c * (np.asarray(x, dtype=float) - fit.d))


# ---------------------------------------------------------------- CPR 추정

def _prepay_predict(ramp: RampFit, scurve: ScurveFit, phi: float,
                    age: np.ndarray, inc: np.ndarray,
                    burn: np.ndarray) -> np.ndarray:
    """적합 모형의 CPR 예측. 램프 + S-curve, 소진으로 감쇠."""
    base = np.minimum(ramp.ceiling, ramp.slope * age) + _scurve_value(scurve, inc)
    return base * (1.0 - phi * burn)


def _backfit(age: np.ndarray, inc: np.ndarray, y: np.ndarray,
             ) -> tuple[RampFit, ScurveFit] | None:
    """램프와 S-curve를 교대적합한다.

    두 층을 한꺼번에 풀지 않는 이유는 규정 대응 산출물이 층별로 나뉘기
    때문이다. <표7> 가(7)이 방법론을 공시하게 하므로 경과효과와 차환유인이
    각각 무엇이었는지 남아야 한다. 경과월은 표본에서 단조증가하고 인센티브는
    평균 회귀하므로 두 축이 근사적으로 직교하며, 그래서 교대적합이 수렴한다.
    """
    s = np.zeros_like(y)
    ramp: RampFit | None = None
    sc: ScurveFit | None = None
    for _ in range(SOLVER.backfit_iters):
        ramp = fit_seasoning_ramp(age, y - s)
        resid = y - np.minimum(ramp.ceiling, ramp.slope * age)
        sc = fit_scurve(inc, resid)
        if not sc.converged:
            return None
        s = _scurve_value(sc, inc)
    if ramp is None or sc is None:
        return None
    return ramp, sc


def estimate_prepayment(obs: pd.DataFrame, *, portfolio_id: str,
                        include_burnout: bool = True,
                        oos_months: int | None = None) -> PrepayFit:
    """기본조기상환율 CPR₀ 추정. 원시율 → 경과효과 → 차환유인 → 소진.

    (a) 원시율은 관측 원장이 이미 담고 있다(`observed_cpr_annual`). 금액에서
        다시 만들지 않는 이유는 원장이 SIFMA 순서로 계산해 넣었고, 여기서
        다시 계산하면 어느 쪽이 정본인지 알 수 없어지기 때문이다. 대신 정합성
        검사가 금액과 관측률의 일치를 본다.
    (b)(c) 경과효과 램프와 차환유인 S-curve를 교대적합한다.
    (d) 소진계수 φ는 격자탐색이다. 표본에 풀이 하나뿐이면 φ는 램프 천장과
        약하게 공선이며, 이 약식별은 `params_json`에 남긴다.

    표본외 구간(`oos_months`)은 추정에서 **뺀다**. 빼지 않으면 사후검증이
    추정에 쓴 기간을 다시 보게 되어 언제나 통과한다.
    """
    oos = INTERNAL.oos_months if oos_months is None else int(oos_months)
    d = obs[obs["portfolio_id"] == portfolio_id].sort_values("obs_seq")
    ccy = str(d["ccy"].iloc[0]) if len(d) else ""
    if len(d) - oos < INTERNAL.min_history_months:
        return PrepayFit(
            portfolio_id, ccy, len(d), _window(d["obs_month"]), None, None,
            include_burnout, None, False, None, None, False, "표본부족",
            f"추정 가능 관측 {max(len(d) - oos, 0)}개월 < 내부기준 "
            f"{INTERNAL.min_history_months}개월. 추정하지 않는다",
            float("nan"), float("nan"), float("nan"), None)

    ins = d.iloc[:len(d) - oos] if oos > 0 else d
    age = ins["wa_seasoning_months"].to_numpy(dtype=float)
    inc = ins["refi_incentive_bp"].to_numpy(dtype=float) / 1e4
    burn = ins["cum_prepay_ratio"].to_numpy(dtype=float)
    y = ins["observed_cpr_annual"].to_numpy(dtype=float)

    def ssr_at(phi: float) -> tuple[float, tuple[RampFit, ScurveFit] | None]:
        deflated = y / (1.0 - phi * burn)
        fit = _backfit(age, inc, deflated)
        if fit is None:
            return float("inf"), None
        pred = _prepay_predict(fit[0], fit[1], phi, age, inc, burn)
        return float(((y - pred) ** 2).sum()), fit

    identified, gain = False, None
    if include_burnout:
        # 상한은 소진 감쇠가 음수로 뒤집히지 않는 범위로 자른다.
        phi_cap = min(INTERNAL.burnout_phi_max,
                      0.95 / max(float(burn.max()), 1e-9))
        grid = np.linspace(0.0, phi_cap, SOLVER.burnout_grid)
        scored = [(ssr_at(float(p))[0], float(p)) for p in grid]
        best_phi = min(scored)[1]
        step = phi_cap / max(SOLVER.burnout_grid - 1, 1)
        fine = np.linspace(max(best_phi - step, 0.0),
                           min(best_phi + step, phi_cap), SOLVER.burnout_refine)
        scored += [(ssr_at(float(p))[0], float(p)) for p in fine]
        best_ssr, best_phi = min(scored)
        # 식별 판정. 풀이 하나면 누적조기상환 경험이 경과월과 거의 단조 동행
        # 하므로 소진 감쇠가 램프의 천장에 그대로 흡수된다. 잔차제곱합이 φ에
        # 대해 평평하면 그 φ는 자료가 정한 값이 아니라 격자가 고른 값이므로,
        # 계수로 보고하지 않고 0으로 되돌린다. 약식별 계수를 원장에 실으면
        # 시나리오 산출이 근거 없는 감쇠를 반영하게 된다.
        ssr0 = ssr_at(0.0)[0]
        gain = (ssr0 - best_ssr) / ssr0 if ssr0 > 0 else 0.0
        identified = gain >= INTERNAL.burnout_min_ssr_gain
        if not identified:
            best_phi = 0.0
    else:
        best_phi = 0.0

    _ssr, fit = ssr_at(best_phi)
    if fit is None:
        # 실패 사유를 그대로 옮기기 위해 φ=0에서 한 번 더 진단한다. 마지막
        # 반복값을 추정치로 돌려주지 않는다. 돌려주면 수렴실패가 산출물에서
        # 사라지고 호출부는 그것을 계수로 쓴다.
        r0 = fit_seasoning_ramp(age, y)
        diag = fit_scurve(inc, y - np.minimum(r0.ceiling, r0.slope * age))
        return PrepayFit(
            portfolio_id, ccy, len(ins), _window(ins["obs_month"]), None, None,
            include_burnout, None, False, None, None, False,
            diag.status if diag.status != "수렴" else "수렴실패",
            f"차환유인 S-curve 적합 실패. {diag.message}. 이 포트폴리오는 "
            "미추정으로 남으며 표준벤치마크로 대체하지 않는다",
            float(age[-1]), float(inc[-1]),
            float(ins["market_refi_rate"].iloc[-1]), None)

    ramp, sc = fit
    pred = _prepay_predict(ramp, sc, best_phi, age, inc, burn)
    last = d.iloc[-1]
    cur_age = float(last["wa_seasoning_months"])
    cur_inc = float(last["refi_incentive_bp"]) / 1e4
    cur_burn = float(last["cum_prepay_ratio"])
    cpr0 = float(_prepay_predict(ramp, sc, best_phi,
                                 np.array([cur_age]), np.array([cur_inc]),
                                 np.array([cur_burn]))[0])
    return PrepayFit(
        portfolio_id=portfolio_id, ccy=ccy, n_obs=len(ins),
        window=_window(ins["obs_month"]), ramp=ramp, scurve=sc,
        burnout_included=include_burnout,
        burnout_phi=best_phi if include_burnout else None,
        burnout_identified=identified, burnout_ssr_gain=gain,
        r_squared=_r_squared(y, pred), converged=True, status="수렴",
        message=(f"교대적합 {SOLVER.backfit_iters}회, S-curve {sc.message}"
                 + ("" if not include_burnout else
                    (f". 소진계수 식별(SSR 개선 {gain:.1%})" if identified else
                     f". 소진계수 미식별(SSR 개선 {gain:.1%} < 내부기준 "
                     f"{INTERNAL.burnout_min_ssr_gain:.0%}). φ=0으로 되돌렸다"))),
        current_age_months=cur_age, current_incentive=cur_inc,
        current_refi_rate=float(last["market_refi_rate"]),
        headline_cpr0=float(min(max(cpr0, 0.0), 1.0)))


# ---------------------------------------------------------------- TDRR 추정

def _irls_logistic(X: np.ndarray, y: np.ndarray, w: np.ndarray,
                   ) -> tuple[np.ndarray | None, int, str]:
    """분수응답 로지스틱 IRLS. 결정론이며 난수가 없다.

    응답은 0/1이 아니라 풀 집계 비율이므로 준이항(quasi-binomial)이다. 분산함수
    μ(1−μ)를 그대로 쓰고 표본가중만 얹는다.
    """
    n, k = X.shape
    m = float(np.clip(np.average(y, weights=w), 1e-9, 1 - 1e-9))
    beta = np.zeros(k)
    beta[0] = math.log(m / (1.0 - m))
    for it in range(1, SOLVER.irls_max_iter + 1):
        eta = X @ beta
        mu = 1.0 / (1.0 + np.exp(-eta))
        v = np.clip(mu * (1.0 - mu), 1e-12, None)
        z = eta + (y - mu) / v
        sw = w * v
        XtWX = X.T @ (X * sw[:, None])
        XtWX = XtWX + SOLVER.ridge * np.eye(k) * max(float(np.trace(XtWX)), 1.0)
        try:
            new = np.linalg.solve(XtWX, X.T @ (sw * z))
        except np.linalg.LinAlgError:
            return None, it, "정규방정식이 특이하다. 설명변수가 공선이다"
        if not np.all(np.isfinite(new)):
            return None, it, "계수가 발산했다"
        if float(np.abs(new - beta).max()) < SOLVER.irls_tol:
            return new, it, f"IRLS {it}회에서 수렴"
        beta = new
    return None, SOLVER.irls_max_iter, (
        f"IRLS {SOLVER.irls_max_iter}회에서 수렴하지 않았다")


def estimate_early_redemption(obs: pd.DataFrame, *, portfolio_id: str,
                              oos_months: int | None = None) -> TdrrFit:
    """기본중도해지율 TDRR₀ 추정. 로지스틱 위험률 모형.

    `logit(월해지율) = β₀ + β₁·금리차 + β₂·잔존만기 + β₃·위약금률`

    위약금률이 설명변수로 들어가야 하는 이유는 제10항 가가 "중도해지 시 상당한
    위약금이 부과되는 경우 제외"라고 정하기 때문이다. 위약금이 해지를 억제하는
    크기를 모르면 그 제외 판정의 경계를 세울 수 없다. 위약금이 표본 안에서
    상수면 β₃는 절편과 공선이라 식별되지 않으며, 그때 IRLS가 특이 판정을 낸다.

    비례위험 모형도 같은 자리에 들어갈 수 있으나 여기서는 로지스틱만
    구현한다. 월별 풀 집계 관측이라 개별 계좌의 위험집합이 없어 부분우도를
    세울 수 없다. 선택한 모형은 `model_family`로 남긴다.

    TDRR₀의 측정 지평은 규정이 정하지 않는다. 여기서는 최근 관측 상태에서의
    월 해지율을 연율화한다(`TDRR_HORIZON_CONVENTION`).
    """
    oos = INTERNAL.oos_months if oos_months is None else int(oos_months)
    d = obs[obs["portfolio_id"] == portfolio_id].sort_values("obs_seq")
    ccy = str(d["ccy"].iloc[0]) if len(d) else ""
    nan = float("nan")
    if len(d) - oos < INTERNAL.min_history_months:
        return TdrrFit(portfolio_id, ccy, len(d), _window(d["obs_month"]),
                       "logistic", {}, None, False, "표본부족",
                       f"추정 가능 관측 {max(len(d) - oos, 0)}개월 < 내부기준 "
                       f"{INTERNAL.min_history_months}개월", None, None)

    ins = d.iloc[:len(d) - oos] if oos > 0 else d
    X, names = _tdrr_design(ins)
    y = ins["observed_tdrr_monthly"].to_numpy(dtype=float)
    w = ins["n_accounts"].to_numpy(dtype=float)
    # 무변동 판정은 최대-최소로 한다. 표준편차는 동일값 열에서도 부동소수
    # 반올림 때문에 1e-16 규모로 남아 0 비교를 빠져나가고, 그러면 공선인
    # 설계행렬이 IRLS로 넘어가 '수렴실패'로 보고된다. 원인이 가려진다.
    flat = [names[i + 1] for i in range(X.shape[1] - 1)
            if float(np.ptp(X[:, i + 1])) <= 0.0]
    if flat:
        return TdrrFit(portfolio_id, ccy, len(ins), _window(ins["obs_month"]),
                       "logistic", {}, None, False, "표본무변동",
                       f"설명변수 {', '.join(flat)}가 표본 안에서 변하지 않는다. "
                       "계수가 절편과 공선이라 식별되지 않는다", None, None)

    beta, n_it, msg = _irls_logistic(X, y, w)
    if beta is None:
        return TdrrFit(portfolio_id, ccy, len(ins), _window(ins["obs_month"]),
                       "logistic", {}, None, False, "수렴실패",
                       f"{msg}. 이 포트폴리오는 미추정으로 남는다", None, None)

    mu = 1.0 / (1.0 + np.exp(-(X @ beta)))
    last = d.iloc[-1]
    x_last, _ = _tdrr_design(last.to_frame().T)
    h = float(1.0 / (1.0 + np.exp(-(x_last @ beta)))[0])
    return TdrrFit(
        portfolio_id=portfolio_id, ccy=ccy, n_obs=len(ins),
        window=_window(ins["obs_month"]), model_family="logistic",
        coef={n: float(b) for n, b in zip(names, beta)},
        r_squared=_r_squared(y, mu), converged=True, status="수렴",
        message=msg, current_monthly_hazard=h,
        headline_tdrr0=float(min(max(1.0 - (1.0 - h) ** 12, 0.0), 1.0)))


def _tdrr_design(d: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """설계행렬. 금리차는 ratio로 되돌린다. bp로 두면 계수가 1e-4 규모가 된다."""
    n = len(d)
    X = np.column_stack([
        np.ones(n),
        d["rate_gap_bp"].to_numpy(dtype=float) / 1e4,
        d["wa_residual_maturity_years"].to_numpy(dtype=float),
        d["penalty_rate"].to_numpy(dtype=float),
    ])
    return X, ["intercept", "rate_gap", "residual_maturity", "penalty_rate"]


# ---------------------------------------------------------------- NMD 추정

def _rate_sensitive_share(d: pd.DataFrame, base_balance: float) -> float:
    """금리민감분 비중. 잔액을 시장금리와 시간추세에 회귀한다.

    `bal = α + β·policy + γ·t`. 금리민감액은 `|β| × 관측 금리 범위`이며 관측
    범위를 쓰는 이유는 표준편차 배수를 고르면 그 배수가 곧 지어낸 계수가 되기
    때문이다. 관측 범위는 자료가 준 사실이다.
    """
    bal = d["avg_balance"].to_numpy(dtype=float)
    pol = d["policy_rate"].to_numpy(dtype=float)
    t = d["obs_seq"].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(d)), pol, t])
    beta = _ols(X, bal)
    if beta is None or base_balance <= 0.0:
        return 0.0
    span = float(pol.max() - pol.min())
    return float(min(max(abs(float(beta[1])) * span / base_balance, 0.0), 1.0))


def _decay_implied_maturity(d: pd.DataFrame) -> float | None:
    """관측 잔액의 지수감쇠율 역수. 증가 추세면 감쇠율이 음수라 None.

    잔액이 늘어나는 예금에서 평균만기를 관측 감쇠로 뽑을 수 없다는 사실이
    NULL로 남아야 한다. NULL이면 <표3> 상한이 그 자리를 대체하고, 그 대체
    사실이 `maturity_cap_binding`으로 드러난다.
    """
    bal = d["avg_balance"].to_numpy(dtype=float)
    if bal.min() <= 0.0:
        return None
    t_years = d["obs_seq"].to_numpy(dtype=float) / 12.0
    X = np.column_stack([np.ones(len(d)), t_years])
    beta = _ols(X, np.log(bal))
    if beta is None:
        return None
    lam = -float(beta[1])
    return 1.0 / lam if lam > 0.0 else None


def estimate_nmd_core(history: pd.DataFrame, *, nmd_category: str,
                      methods: tuple[str, ...] = NMD_CORE_METHODS,
                      ) -> list[NmdCoreEstimate]:
    """핵심예금 비율을 세 방법으로 산출한다.

    현행 별표는 산식을 주지 않는다. 2014년판의 "최근월평잔 − 12개월 기간가중
    표준편차 × 2.33"은 2019.11.29 개정으로 폐지됐다. 따라서 방법 선택이 은행
    재량이고 <표7> 가(7) 공시 대상이며, 세 결과를 나란히 두는 것이 이 함수의
    목적이다.

    제8항 나가 2단계로 적는다: (1) 인출가능성이 낮은 **안정적 예금**, (2) 그중
    금리환경 변동 시에도 금리개정 가능성이 낮은 **핵심예금**. 그래서 세 방법을
    2단계 구조에 얹는다.

      volatility_percentile  안정분 = 하위 백분위 잔액 / 기준잔액
      rolling_min            안정분 = 이동창 최소잔액 / 기준잔액
      regression_replicating 안정분을 쓰지 않고(=1) 금리민감분만 비코어로 본다

    앞의 둘은 `코어 = 안정분 × (1 − 금리민감분)`이고 셋째는 `코어 = 1 −
    금리민감분`이다. 세 값이 다르고, 그 차이가 ΔEVE를 얼마나 움직이는지가
    비교 원장에 남는다.

    코어는 CPR·TDRR과 달리 **관찰구간 전체**를 쓴다. 제8항 나(2)가 요구하는
    것이 과거 잔액 변동의 관찰이고, 표본외로 뗄 사후검증 지표가 이 산출에는
    붙어 있지 않기 때문이다. 전가율은 예측 대상이 있어 표본외를 뗀다.
    """
    d = history[history["nmd_category"] == nmd_category].sort_values("obs_seq")
    ccy = str(d["ccy"].iloc[0]) if len(d) else ""
    if d.empty:
        return []
    bal = d["avg_balance"].to_numpy(dtype=float)
    base = float(bal[-1])
    share = _rate_sensitive_share(d, base)
    decay = _decay_implied_maturity(d)
    win = _window(d["obs_month"])
    w = min(INTERNAL.rolling_window_months, len(bal))

    out: list[NmdCoreEstimate] = []
    for m in methods:
        if m == "volatility_percentile":
            stable = float(np.percentile(bal, INTERNAL.core_percentile * 100.0)) / base
            rule = (f"과거 월중평잔의 하위 {INTERNAL.core_percentile:.0%} 분위를 "
                    "안정분으로 본다. 분위 수준은 규정 미제시 내부기준이다")
        elif m == "rolling_min":
            stable = float(bal[-w:].min()) / base
            rule = (f"최근 {w}개월 이동창의 최소 월중평잔을 안정분으로 본다. "
                    "관측된 사실만 쓰고 분포가정을 두지 않는다. 이동창 길이는 "
                    "규정 미제시 내부기준이다")
        elif m == "regression_replicating":
            stable = 1.0
            rule = ("잔액을 시장금리·시간추세에 회귀해 금리민감분만 비코어로 "
                    "본다. 잔액 변동의 관찰(안정분)을 쓰지 않는 방법이다")
        else:
            raise KeyError(f"알 수 없는 코어 산출방법: {m!r}")
        stable = float(min(max(stable, 0.0), 1.0))
        core_raw = float(min(max(stable * (1.0 - share), 0.0), 1.0))
        out.append(NmdCoreEstimate(
            nmd_category=nmd_category, ccy=ccy, method=m, method_rule=rule,
            n_obs=len(d), window=win, base_balance=base, stable_ratio=stable,
            rate_sensitive_share=share, core_ratio_raw=core_raw,
            decay_implied_maturity_years=decay))
    return out


def estimate_pass_through_beta(history: pd.DataFrame, *, nmd_category: str,
                               oos_months: int | None = None) -> NmdBetaFit:
    """전가율 β. Δ예금금리를 Δ시장금리에 회귀한 기울기.

    시장금리가 움직이지 않은 달은 관측 전가율의 분모가 0이라 표본에서 뺀다.
    0으로 채우면 β가 하방 편의를 갖고, 그 편의는 관리금리 부채의 ΔNII를
    과소계상하는 방향이다.

    β는 `alm_nmd_param.pass_through_beta`의 [0,1] 제약을 받는다. 추정치가 그
    밖으로 나가면 원값을 `beta_raw`에 남기고 잘라 쓴 사실을 `clipped`로 표시한다.
    """
    oos = INTERNAL.oos_months if oos_months is None else int(oos_months)
    d = history[history["nmd_category"] == nmd_category].sort_values("obs_seq")
    ccy = str(d["ccy"].iloc[0]) if len(d) else ""
    ins = d.iloc[:len(d) - oos] if oos > 0 else d
    use = ins[ins["policy_rate_change_bp"].notna()
              & (ins["policy_rate_change_bp"].abs() > 0)]
    nan = float("nan")
    if len(use) < 3:
        return NmdBetaFit(nmd_category, ccy, len(use), _window(ins["obs_month"]),
                          nan, nan, False, nan, False, "표본부족",
                          f"시장금리가 움직인 달이 {len(use)}개뿐이다. 전가율을 "
                          "추정하지 않는다")
    dp = use["policy_rate_change_bp"].to_numpy(dtype=float) / 1e4
    dd = (use["deposit_rate"].to_numpy(dtype=float)
          - d.set_index("obs_seq").loc[
              use["obs_seq"] - 1, "deposit_rate"].to_numpy(dtype=float))
    X = np.column_stack([np.ones(len(use)), dp])
    beta = _ols(X, dd)
    if beta is None:
        return NmdBetaFit(nmd_category, ccy, len(use), _window(ins["obs_month"]),
                          nan, nan, False, nan, False, "수렴실패",
                          "정규방정식이 특이하다")
    raw = float(beta[1])
    applied = float(min(max(raw, 0.0), 1.0))
    return NmdBetaFit(
        nmd_category=nmd_category, ccy=ccy, n_obs=len(use),
        window=_window(ins["obs_month"]), beta_raw=raw, beta_applied=applied,
        clipped=applied != raw, r_squared=_r_squared(dd, X @ beta),
        converged=True, status="수렴",
        message=f"Δ시장금리≠0 인 {len(use)}개월로 추정")


# ---------------------------------------------------------------- <표3> 상한

def apply_table3_caps(core_ratio_raw: float, maturity_raw: float | None, *,
                      core_cap: float, maturity_cap: float,
                      ) -> tuple[float, bool, float, bool]:
    """<표3> 상한 적용. `min(추정치, 상한)`.

    반환: (코어비율, 코어상한 적용여부, 평균만기, 만기상한 적용여부)

    평균만기 추정치가 없으면(감쇠율이 음수여서 NULL) 상한이 그 자리를 대체하고
    `maturity_cap_binding=True`가 된다. 대체 사실이 값에 남지 않으면 <표7>
    정량공시의 평균 금리개정만기가 추정치인지 상한인지 구분되지 않는다.
    """
    core = min(float(core_ratio_raw), float(core_cap))
    core_binding = float(core_ratio_raw) > float(core_cap) + 1e-12
    if maturity_raw is None or not math.isfinite(float(maturity_raw)):
        return core, core_binding, float(maturity_cap), True
    mat = min(float(maturity_raw), float(maturity_cap))
    return core, core_binding, mat, float(maturity_raw) > float(maturity_cap) + 1e-12


# ---------------------------------------------------------------- 진입점

def run_estimation(history: dict[str, pd.DataFrame], *, asof: str,
                   include_burnout: bool = True,
                   oos_months: int | None = None) -> EstimationResult:
    """관측이력 3장 → 추정 결과 전량. 원장 적재는 build_estimation_ledgers가 한다."""
    res = EstimationResult(asof=asof)
    prep = history.get("alm_prepay_observation")
    if prep is not None and len(prep):
        for pid in sorted(prep["portfolio_id"].astype(str).unique()):
            res.prepay.append(estimate_prepayment(
                prep, portfolio_id=pid, include_burnout=include_burnout,
                oos_months=oos_months))
    er = history.get("alm_early_redemption_observation")
    if er is not None and len(er):
        for pid in sorted(er["portfolio_id"].astype(str).unique()):
            res.tdrr.append(estimate_early_redemption(
                er, portfolio_id=pid, oos_months=oos_months))
    nmd = history.get("alm_nmd_balance_history")
    if nmd is not None and len(nmd):
        for cat in sorted(nmd["nmd_category"].astype(str).unique()):
            res.nmd_core.extend(estimate_nmd_core(nmd, nmd_category=cat))
            res.nmd_beta.append(estimate_pass_through_beta(
                nmd, nmd_category=cat, oos_months=oos_months))
    for f in res.prepay:
        if not f.converged:
            res.messages.append(f"CPR/{f.portfolio_id}: {f.status}. {f.message}")
    for t in res.tdrr:
        if not t.converged:
            res.messages.append(f"TDRR/{t.portfolio_id}: {t.status}. {t.message}")
    for b in res.nmd_beta:
        if not b.converged:
            res.messages.append(f"NMD_BETA/{b.nmd_category}: {b.status}. {b.message}")
    return res


# ---------------------------------------------------------------- 결과 원장

def _json(obj: dict) -> str:
    """키 정렬 JSON. 같은 (asof, seed)면 바이트 동일해야 한다."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _solver_note() -> dict:
    return {"scurve_g0": SOLVER.scurve_g0, "scurve_ftol": SOLVER.scurve_ftol,
            "backfit_iters": SOLVER.backfit_iters,
            "burnout_grid": SOLVER.burnout_grid,
            "irls_tol": SOLVER.irls_tol}


_CPR_FORM = ("CPR(age, x) = min(ceiling, slope·age) + a + b·arctan(c·(x − d)), "
             "소진 반영 시 ×(1 − φ·누적조기상환비율). x = 약정금리 − 재조달금리")
_TDRR_FORM = ("logit(월해지율) = β₀ + β₁·금리차 + β₂·잔존만기 + β₃·위약금률, "
              "TDRR₀ = 1 − (1 − 월해지율)^12")


def build_behaviour_model_ledger(res: EstimationResult) -> pd.DataFrame:
    """`alm_behaviour_model`. 모형 × 포트폴리오 1행."""
    rows: list[dict] = []
    common = {"entered_by": None, "approved_by": None, "approved_on": None,
              "evidence_status": "재량·미규정"}
    for f in res.prepay:
        params = {"solver": _solver_note(),
                  "burnout_included": f.burnout_included,
                  "burnout_phi": f.burnout_phi,
                  "burnout_identified": f.burnout_identified,
                  "burnout_ssr_gain": f.burnout_ssr_gain,
                  "current_age_months": f.current_age_months,
                  "current_incentive_ratio": f.current_incentive,
                  "identification_note":
                      "풀이 하나뿐인 표본에서 소진계수 φ는 램프 천장과 약하게 "
                      "공선이다. 풀을 vintage로 나눠야 강하게 식별된다"}
        if f.ramp is not None:
            params |= {"ramp_ceiling": f.ramp.ceiling, "ramp_slope": f.ramp.slope,
                       "ramp_age_star_months": f.ramp.age_star_months}
        if f.scurve is not None:
            params |= {"scurve_a": f.scurve.a, "scurve_b": f.scurve.b,
                       "scurve_c": f.scurve.c, "scurve_d": f.scurve.d}
        rows.append({
            **common, "asof": res.asof, "model": "CPR",
            "portfolio_id": f.portfolio_id, "ccy": f.ccy,
            "estimation_method": "원시 SMM 연율화 → 경과효과 램프 ↔ 차환유인 "
                                 "S-curve 교대적합 → 소진계수 격자탐색",
            "functional_form": _CPR_FORM,
            "estimation_window_start": f.window[0] or None,
            "estimation_window_end": f.window[1] or None,
            "n_obs": f.n_obs, "params_json": _json(params),
            "r_squared": f.r_squared, "converged": f.converged,
            "fit_status": f.status, "burnout_included": f.burnout_included,
            "horizon_convention": CPR_CONVENTION,
            "headline_estimate": f.headline_cpr0, "message": f.message,
            "input_source": "자체추정" if f.converged else "미확정",
        })
    for t in res.tdrr:
        rows.append({
            **common, "asof": res.asof, "model": "TDRR",
            "portfolio_id": t.portfolio_id, "ccy": t.ccy,
            "estimation_method": f"{t.model_family} 위험률 모형, 분수응답 IRLS. "
                                 "위약금률을 설명변수로 포함(제10항 가)",
            "functional_form": _TDRR_FORM,
            "estimation_window_start": t.window[0] or None,
            "estimation_window_end": t.window[1] or None,
            "n_obs": t.n_obs,
            "params_json": _json({"solver": _solver_note(),
                                  "model_family": t.model_family,
                                  "coef": t.coef,
                                  "current_monthly_hazard":
                                      t.current_monthly_hazard}),
            "r_squared": t.r_squared, "converged": t.converged,
            "fit_status": t.status, "burnout_included": None,
            "horizon_convention": TDRR_HORIZON_CONVENTION,
            "headline_estimate": t.headline_tdrr0, "message": t.message,
            "input_source": "자체추정" if t.converged else "미확정",
        })
    head = {e.nmd_category: e for e in res.nmd_core
            if e.method == HEADLINE_CORE_METHOD}
    for cat, e in sorted(head.items()):
        rows.append({
            **common, "asof": res.asof, "model": "NMD_CORE",
            "portfolio_id": cat, "ccy": e.ccy,
            "estimation_method": f"{HEADLINE_CORE_METHOD} (헤드라인). 세 방법 "
                                 "비교는 alm_nmd_core_method_compare",
            "functional_form": "코어 = 안정분 × (1 − 금리민감분)",
            "estimation_window_start": e.window[0] or None,
            "estimation_window_end": e.window[1] or None,
            "n_obs": e.n_obs,
            "params_json": _json({"method_rule": e.method_rule,
                                  "stable_ratio": e.stable_ratio,
                                  "rate_sensitive_share": e.rate_sensitive_share,
                                  "core_percentile": INTERNAL.core_percentile,
                                  "rolling_window_months":
                                      INTERNAL.rolling_window_months,
                                  "decay_implied_maturity_years":
                                      e.decay_implied_maturity_years}),
            "r_squared": None, "converged": True, "fit_status": "수렴",
            "burnout_included": None,
            "horizon_convention": "코어비율은 <표3> 상한 적용 후 값이 계수 원장에 "
                                  "들어간다",
            "headline_estimate": e.core_ratio_raw,
            "message": "상한 적용 전 추정치. 상한 후 값은 alm_nmd_param",
            "input_source": "자체추정",
        })
    for b in res.nmd_beta:
        rows.append({
            **common, "asof": res.asof, "model": "NMD_BETA",
            "portfolio_id": b.nmd_category, "ccy": b.ccy,
            "estimation_method": "Δ예금금리 = α + β·Δ시장금리 최소자승. "
                                 "Δ시장금리 = 0 인 달은 제외",
            "functional_form": "Δ예금금리 = α + β·Δ시장금리",
            "estimation_window_start": b.window[0] or None,
            "estimation_window_end": b.window[1] or None,
            "n_obs": b.n_obs,
            "params_json": _json({"beta_raw": b.beta_raw,
                                  "beta_applied": b.beta_applied,
                                  "clipped_to_unit_interval": b.clipped}),
            "r_squared": b.r_squared if b.converged else None,
            "converged": b.converged, "fit_status": b.status,
            "burnout_included": None,
            "horizon_convention": None,
            "headline_estimate": b.beta_applied if b.converged else None,
            "message": b.message,
            "input_source": "자체추정" if b.converged else "미확정",
        })
    df = pd.DataFrame(rows, columns=list(BEHAVIOUR_MODEL.column_names))
    return df.astype({"r_squared": "float64", "headline_estimate": "float64"})


def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    diff = (pred - actual) * 100.0        # %p
    return {"mean_actual_pp": float(actual.mean() * 100.0),
            "mean_predicted_pp": float(pred.mean() * 100.0),
            "bias_pp": float(diff.mean()),
            "mae_pp": float(np.abs(diff).mean()),
            "rmse_pp": float(np.sqrt((diff ** 2).mean()))}


def build_behaviour_backtest_ledger(
        res: EstimationResult, history: dict[str, pd.DataFrame], *,
        oos_months: int | None = None,
        threshold_mae_pp: float | None = None,
        approved_by: str | None = None,
        approved_on: str | None = None) -> pd.DataFrame:
    """`alm_behaviour_backtest`. 표본외(out-of-time) 검증.

    추정에 쓴 구간 **뒤쪽**을 떼어 검증한다. 추정구간으로 검증하면 언제나
    통과하므로 그 결과는 통제가 아니다. 겹침 여부는 `is_out_of_time`으로
    값에 남는다.

    임계는 규정에 없다. 인자로 승인된 임계가 들어오지 않으면 `threshold_mae_pp`
    는 NULL이고 판정은 '판정보류'다. 임계 없이 '적합'을 찍지 않는다.
    """
    oos = INTERNAL.oos_months if oos_months is None else int(oos_months)
    thr = (INTERNAL.backtest_mae_threshold_pp if threshold_mae_pp is None
           else float(threshold_mae_pp))
    appr_by = approved_by if approved_by is not None else INTERNAL.threshold_approved_by
    appr_on = approved_on if approved_on is not None else INTERNAL.threshold_approved_on
    basis = ("내부기준. [별표3 203.]은 연1회 이상 사후검증을 요구하나 행동모형 "
             "MAE 임계치를 정하지 않는다. 임계 미승인 시 NULL이며 판정보류다")
    rows: list[dict] = []

    def judge(mae: float) -> str:
        if thr is None:
            return "판정보류"
        return "적합" if mae <= thr else "부적합"

    prep = history.get("alm_prepay_observation")
    for f in res.prepay:
        if not f.converged or prep is None or f.ramp is None or f.scurve is None:
            continue
        d = prep[prep["portfolio_id"] == f.portfolio_id].sort_values("obs_seq")
        if oos <= 0 or len(d) <= oos:
            continue
        ins, out = d.iloc[:len(d) - oos], d.iloc[len(d) - oos:]
        phi = f.burnout_phi or 0.0

        def pr(x: pd.DataFrame) -> np.ndarray:
            return _prepay_predict(
                f.ramp, f.scurve, phi,
                x["wa_seasoning_months"].to_numpy(dtype=float),
                x["refi_incentive_bp"].to_numpy(dtype=float) / 1e4,
                x["cum_prepay_ratio"].to_numpy(dtype=float))

        m = _metrics(out["observed_cpr_annual"].to_numpy(dtype=float), pr(out))
        in_mae = _metrics(ins["observed_cpr_annual"].to_numpy(dtype=float),
                          pr(ins))["mae_pp"]
        vw = _window(out["obs_month"])
        rows.append({
            "asof": res.asof, "model": "CPR", "portfolio_id": f.portfolio_id,
            "validation_window_start": vw[0], "validation_window_end": vw[1],
            "is_out_of_time": vw[0] > f.window[1], "n_obs": len(out), **m,
            "in_sample_mae_pp": in_mae, "threshold_mae_pp": thr,
            "threshold_basis": basis, "judgement": judge(m["mae_pp"]),
            "approved_by": appr_by, "approved_on": appr_on,
            "evidence_status": "재량·미규정",
        })

    er = history.get("alm_early_redemption_observation")
    for t in res.tdrr:
        if not t.converged or er is None:
            continue
        d = er[er["portfolio_id"] == t.portfolio_id].sort_values("obs_seq")
        if oos <= 0 or len(d) <= oos:
            continue
        ins, out = d.iloc[:len(d) - oos], d.iloc[len(d) - oos:]
        beta = np.array([t.coef["intercept"], t.coef["rate_gap"],
                         t.coef["residual_maturity"], t.coef["penalty_rate"]])

        def hz(x: pd.DataFrame) -> np.ndarray:
            X, _ = _tdrr_design(x)
            return 1.0 / (1.0 + np.exp(-(X @ beta)))

        m = _metrics(out["observed_tdrr_monthly"].to_numpy(dtype=float), hz(out))
        in_mae = _metrics(ins["observed_tdrr_monthly"].to_numpy(dtype=float),
                          hz(ins))["mae_pp"]
        vw = _window(out["obs_month"])
        rows.append({
            "asof": res.asof, "model": "TDRR", "portfolio_id": t.portfolio_id,
            "validation_window_start": vw[0], "validation_window_end": vw[1],
            "is_out_of_time": vw[0] > t.window[1], "n_obs": len(out), **m,
            "in_sample_mae_pp": in_mae, "threshold_mae_pp": thr,
            "threshold_basis": basis, "judgement": judge(m["mae_pp"]),
            "approved_by": appr_by, "approved_on": appr_on,
            "evidence_status": "재량·미규정",
        })

    nmd = history.get("alm_nmd_balance_history")
    for b in res.nmd_beta:
        if not b.converged or nmd is None:
            continue
        d = nmd[nmd["nmd_category"] == b.nmd_category].sort_values("obs_seq")
        if oos <= 0 or len(d) <= oos:
            continue
        out = d.iloc[len(d) - oos:]
        use = out[out["policy_rate_change_bp"].notna()
                  & (out["policy_rate_change_bp"].abs() > 0)]
        if use.empty:
            continue
        prev = d.set_index("obs_seq").loc[use["obs_seq"] - 1, "deposit_rate"]
        actual = (use["deposit_rate"].to_numpy(dtype=float)
                  - prev.to_numpy(dtype=float))
        pred = b.beta_applied * use["policy_rate_change_bp"].to_numpy(
            dtype=float) / 1e4
        m = _metrics(actual, pred)
        vw = _window(use["obs_month"])
        rows.append({
            "asof": res.asof, "model": "NMD_BETA",
            "portfolio_id": b.nmd_category,
            "validation_window_start": vw[0], "validation_window_end": vw[1],
            "is_out_of_time": vw[0] > b.window[1], "n_obs": len(use), **m,
            "in_sample_mae_pp": None, "threshold_mae_pp": thr,
            "threshold_basis": basis, "judgement": judge(m["mae_pp"]),
            "approved_by": appr_by, "approved_on": appr_on,
            "evidence_status": "재량·미규정",
        })
    df = pd.DataFrame(rows, columns=list(BEHAVIOUR_BACKTEST.column_names))
    return df.astype({"in_sample_mae_pp": "float64",
                      "threshold_mae_pp": "float64"})


def build_nmd_core_method_compare(
        res: EstimationResult, nmd_param: pd.DataFrame, buckets: pd.DataFrame,
        *, shock_bp: float, balances: dict[str, float] | None = None,
        headline_method: str = HEADLINE_CORE_METHOD) -> pd.DataFrame:
    """`alm_nmd_core_method_compare`. 세 방법을 나란히 두고 ΔEVE 영향까지 낸다.

    ΔEVE 영향은 듀레이션 1차 근사 `−Σ_k CF_k · t_k · Δr`의 부호를 뒤집은 값이다.
    부채의 현재가치가 줄면 EVE는 늘기 때문이다. 정식 ΔEVE는 `irrbb.py`가 충격
    곡선으로 완전재계산하며, 여기서는 방법 간 **차이**를 보는 것이 목적이라
    같은 근사를 세 방법에 똑같이 걸어 비교 가능성을 확보한다.

    `shock_bp`는 호출부가 `alm_rate_shock_param`에서 읽어 넘긴다. 이 함수에
    충격값을 두면 규제표가 엔진에 복사된다.
    """
    caps = nmd_param.set_index("nmd_category")
    rows: list[dict] = []
    dr = float(shock_bp) / 1e4
    for e in res.nmd_core:
        if e.nmd_category not in caps.index:
            continue
        cap = caps.loc[e.nmd_category]
        core_cap = float(cap["core_ratio_cap"])
        mat_cap = float(cap["avg_maturity_cap_years"])
        core, core_bind, mat, mat_bind = apply_table3_caps(
            e.core_ratio_raw, e.decay_implied_maturity_years,
            core_cap=core_cap, maturity_cap=mat_cap)
        bal = float((balances or {}).get(e.nmd_category, e.base_balance))
        points, achieved, _ = nmd_slotting(
            bal, core_ratio=core, core_ratio_cap=core_cap,
            avg_maturity_years=mat, avg_maturity_cap_years=mat_cap,
            buckets=buckets, stable_ratio=e.stable_ratio,
            scope=f"{e.nmd_category}/{e.method}")
        pv_change = -sum(p.principal * p.t_years for p in points) * dr
        rows.append({
            "asof": res.asof,
            "nmd_category": e.nmd_category, "ccy": e.ccy, "method": e.method,
            "method_rule": e.method_rule,
            "is_headline": e.method == headline_method,
            "base_balance": bal, "stable_ratio": e.stable_ratio,
            "rate_sensitive_share": e.rate_sensitive_share,
            "core_ratio_raw": e.core_ratio_raw, "core_ratio": core,
            "core_ratio_cap": core_cap, "core_cap_binding": core_bind,
            "decay_implied_maturity_years": e.decay_implied_maturity_years,
            "avg_maturity_years": mat, "avg_maturity_cap_years": mat_cap,
            "maturity_cap_binding": mat_bind,
            "achieved_avg_maturity_years": achieved,
            "core_amount": bal * core, "shock_bp": float(shock_bp),
            "delta_eve_proxy_krw": -pv_change,
            "n_obs": e.n_obs,
            "observation_window_start": e.window[0],
            "observation_window_end": e.window[1],
            "input_source": "자체추정", "evidence_status": "재량·미규정",
        })
    df = pd.DataFrame(rows, columns=list(NMD_CORE_METHOD_COMPARE.column_names))
    return df.astype({"decay_implied_maturity_years": "float64"})


def build_estimation_ledgers(
        res: EstimationResult, history: dict[str, pd.DataFrame],
        nmd_param: pd.DataFrame, buckets: pd.DataFrame, *, shock_bp: float,
        balances: dict[str, float] | None = None,
        oos_months: int | None = None,
        threshold_mae_pp: float | None = None) -> dict[str, pd.DataFrame]:
    """추정 결과 원장 3장. 키는 테이블명."""
    return {
        "alm_behaviour_model": build_behaviour_model_ledger(res),
        "alm_behaviour_backtest": build_behaviour_backtest_ledger(
            res, history, oos_months=oos_months,
            threshold_mae_pp=threshold_mae_pp),
        "alm_nmd_core_method_compare": build_nmd_core_method_compare(
            res, nmd_param, buckets, shock_bp=shock_bp, balances=balances),
    }


# ---------------------------------------------------------------- 계수 원장 갱신

def apply_estimates(param_tables: dict[str, pd.DataFrame],
                    res: EstimationResult, *,
                    backtest: pd.DataFrame | None = None,
                    headline_core_method: str = HEADLINE_CORE_METHOD,
                    ) -> dict[str, pd.DataFrame]:
    """추정 결과를 계수 원장에 채운다. 원본을 바꾸지 않고 새 dict를 돌려준다.

    갱신 대상은 세 장이다.

      alm_behaviour_param      CPR₀·TDRR₀ · 추정구간 · 추정방법 · 백테스트 MAE
      alm_prepay_scurve_param  S-curve 계수 · 재조달금리 참조 · enabled
      alm_nmd_param            안정분 · 코어비율 · 평균만기 · 전가율

    **수렴하지 않은 모형의 자리는 건드리지 않는다.** 그 자리는 NULL로 남고
    `enabled=False`가 유지되며, 엔진은 조정을 건너뛰고 경고를 남긴다. 조용히
    표준벤치마크를 되돌려 채우지 않는다.

    `deduct_prepay_fee`를 False로 내리는 이유: 추정에 쓴 차환유인은
    `약정금리 − 재조달금리`이며 중도상환수수료를 차감하지 않은 정의다. 적용
    단계에서 수수료를 다시 빼면 모형이 본 적 없는 변수를 넣는 것이 되고,
    S-curve의 변곡점 d가 관측 분포 밖으로 밀린다.

    `coef_a`에 램프 수준을 더하는 이유: 적용 엔진(`cashflow._cpr_path`)은
    S-curve가 켜지면 기준율을 **대체**하므로, 절편이 잔차 기준이면 경과효과가
    통째로 빠진다. 현재 가중평균 경과월의 램프 수준을 절편에 실어 적용 시점의
    수준을 맞춘다. 미래 회차의 경과 진행은 반영되지 않으며, 그 한계는
    `note`에 남는다.
    """
    out = {k: v.copy() for k, v in param_tables.items()}
    mae_by = {}
    if backtest is not None and len(backtest):
        mae_by = {(str(r["model"]), str(r["portfolio_id"])): float(r["mae_pp"])
                  for _, r in backtest.iterrows()}

    bp = out.get("alm_behaviour_param")
    if bp is not None and len(bp):
        for f in res.prepay:
            if not f.converged or f.ramp is None or f.scurve is None:
                continue
            m = (bp["model"] == "CPR") & (bp["product_group"] == f.portfolio_id)
            if not m.any():
                continue
            bp.loc[m, "base_model"] = "constant"
            bp.loc[m, "base_rate_annual"] = f.headline_cpr0
            bp.loc[m, "estimation_window_start"] = _month_start(f.window[0])
            bp.loc[m, "estimation_window_end"] = _month_end(f.window[1])
            bp.loc[m, "estimation_method"] = (
                "경과효과 램프 min(ceiling, slope·경과월) ↔ 차환유인 "
                "S-curve a+b·arctan(c·(x−d)) 교대적합, 소진계수 격자탐색. "
                f"소진 반영={f.burnout_included}. {CPR_CONVENTION}")
            bp.loc[m, "backtest_mae_pp"] = mae_by.get(("CPR", f.portfolio_id))
            bp.loc[m, "input_source"] = "자체추정"
            bp.loc[m, "evidence_ref"] = (
                "[별표 9-1] 제9항 다(1) 은행 자체산출. 관측이력 "
                "alm_prepay_observation(합성) · 추정결과 alm_behaviour_model")
            bp.loc[m, "evidence_status"] = "재량·미규정"
        for t in res.tdrr:
            if not t.converged:
                continue
            m = (bp["model"] == "TDRR") & (bp["product_group"] == t.portfolio_id)
            if not m.any():
                continue
            bp.loc[m, "base_model"] = "constant"
            bp.loc[m, "base_rate_annual"] = t.headline_tdrr0
            bp.loc[m, "estimation_window_start"] = _month_start(t.window[0])
            bp.loc[m, "estimation_window_end"] = _month_end(t.window[1])
            bp.loc[m, "estimation_method"] = (
                f"{t.model_family} 위험률 모형(금리차·잔존만기·위약금률), "
                f"분수응답 IRLS. {TDRR_HORIZON_CONVENTION}")
            bp.loc[m, "backtest_mae_pp"] = mae_by.get(("TDRR", t.portfolio_id))
            bp.loc[m, "input_source"] = "자체추정"
            bp.loc[m, "evidence_ref"] = (
                "[별표 9-1] 제10항 다(1) 은행 자체산출. 관측이력 "
                "alm_early_redemption_observation(합성)")
            bp.loc[m, "evidence_status"] = "재량·미규정"
        out["alm_behaviour_param"] = bp

    sc = out.get("alm_prepay_scurve_param")
    if sc is not None and len(sc):
        for f in res.prepay:
            m = sc["product_group"] == f.portfolio_id
            if not m.any():
                continue
            if not f.converged or f.scurve is None or f.ramp is None:
                sc.loc[m, "note"] = (
                    f"S-curve 미추정({f.status}). {f.message}. 계수는 NULL로 "
                    "두고 enabled=False를 유지한다")
                continue
            applied_a = f.scurve.a + seasoning_ramp(
                f.current_age_months, ceiling=f.ramp.ceiling, slope=f.ramp.slope)
            sc.loc[m, "coef_a"] = applied_a
            sc.loc[m, "coef_b"] = f.scurve.b
            sc.loc[m, "coef_c"] = f.scurve.c
            sc.loc[m, "coef_d"] = f.scurve.d
            sc.loc[m, "refi_rate"] = f.current_refi_rate
            sc.loc[m, "refi_rate_ref"] = (
                "alm_prepay_observation.market_refi_rate 최근 관측월")
            sc.loc[m, "deduct_prepay_fee"] = False
            sc.loc[m, "enabled"] = True
            sc.loc[m, "input_source"] = "자체추정"
            sc.loc[m, "evidence_status"] = "재량·미규정"
            sc.loc[m, "note"] = (
                f"절편에 현재 가중평균 경과월 {f.current_age_months:.1f}개월의 "
                "램프 수준을 실었다. 적용 엔진이 S-curve로 기준율을 대체하므로 "
                "절편이 잔차 기준이면 경과효과가 빠진다. 미래 회차의 경과 진행은 "
                "반영되지 않으며, 반영하려면 적용부가 램프와 S-curve를 함께 "
                "평가해야 한다. 인센티브 정의는 약정금리 − 재조달금리이며 "
                "수수료를 차감하지 않는다")
        out["alm_prepay_scurve_param"] = sc

    np_ = out.get("alm_nmd_param")
    if np_ is not None and len(np_):
        core_by = {e.nmd_category: e for e in res.nmd_core
                   if e.method == headline_core_method}
        beta_by = {b.nmd_category: b for b in res.nmd_beta if b.converged}
        for i, row in np_.iterrows():
            cat = str(row["nmd_category"])
            e = core_by.get(cat)
            if e is not None:
                core, core_bind, mat, mat_bind = apply_table3_caps(
                    e.core_ratio_raw, e.decay_implied_maturity_years,
                    core_cap=float(row["core_ratio_cap"]),
                    maturity_cap=float(row["avg_maturity_cap_years"]))
                np_.at[i, "stable_ratio"] = e.stable_ratio
                np_.at[i, "core_ratio"] = core
                np_.at[i, "avg_maturity_years"] = mat
                np_.at[i, "input_source"] = (
                    "감독상한대체" if (core_bind and mat_bind) else "자체추정")
            b = beta_by.get(cat)
            if b is not None:
                np_.at[i, "pass_through_beta"] = b.beta_applied
        out["alm_nmd_param"] = np_
    return out


def _month_start(ym: str) -> str | None:
    return f"{ym}-01" if ym else None


def _month_end(ym: str) -> str | None:
    """관측월의 말일. 달력을 직접 세지 않고 다음 달 1일에서 하루 뺀다."""
    if not ym:
        return None
    y, m = int(ym[:4]), int(ym[5:7])
    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    return str(pd.Timestamp(f"{y2:04d}-{m2:02d}-01") - pd.Timedelta(days=1))[:10]


# ---------------------------------------------------------------- 정합성 검사
#
# 여섯 검사는 `consistency.ConsistencyCheck`로 1:1 매핑된다. 여기 두는 이유는
# 검사가 추정 엔진의 불변식이고, 위반 주입 테스트가 이 모듈의 테스트에 붙어야
# 하기 때문이다. consistency.py는 이 함수들을 호출해 report에 담기만 한다.

def check_estimate_moves_cashflow(before: pd.DataFrame, after: pd.DataFrame,
                                  ) -> EstimationCheck:
    """추정 모수를 채우면 행동조정 현금흐름이 실제로 바뀌는가.

    안 바뀌면 배선이 끊긴 것이다. 원장에 값이 들어갔다는 사실만으로는 산출이
    그 값을 읽었다는 근거가 되지 않는다.
    """
    name = "alm_behaviour_estimate_moves_cashflow"
    key = ["scenario", "contract_id", "bucket"]
    cols = [c for c in ("principal_cf", "interest_cf_ex_margin", "margin_cf")
            if c in before.columns and c in after.columns]
    if before.empty or after.empty or not cols:
        return EstimationCheck(name, "FAIL",
                               "비교할 행동조정 현금흐름이 없다. 추정 모수가 "
                               "산출에 닿았는지 확인할 수 없다", 0.0)
    b = before.groupby(key)[cols].sum().sum(axis=1)
    a = after.groupby(key)[cols].sum().sum(axis=1)
    joined = b.to_frame("b").join(a.to_frame("a"), how="outer").fillna(0.0)
    gap = float((joined["a"] - joined["b"]).abs().max())
    n_rows = int(len(a) - len(b))
    if gap <= 0.0 and n_rows == 0:
        return EstimationCheck(
            name, "FAIL",
            "추정 모수를 채웠는데 행동조정 현금흐름이 한 원도 움직이지 않았다. "
            "계수 원장과 산출 엔진 사이 배선이 끊겼다", gap)
    return EstimationCheck(
        name, "PASS",
        f"추정 반영으로 행동조정 현금흐름이 움직였다. 최대 {gap:,.0f}원, "
        f"행 수 변화 {n_rows:+,}", gap)


def check_table3_cap_binds(compare: pd.DataFrame) -> EstimationCheck:
    """<표3> 상한이 경계에서 무는가. `min(추정치, 상한)`이 지켜지는지 본다."""
    name = "alm_nmd_table3_cap_binds"
    if compare.empty:
        return EstimationCheck(name, "FAIL", "코어 산출방법 비교 원장이 비었다", 0.0)
    over_core = compare["core_ratio"] > compare["core_ratio_cap"] + 1e-12
    over_mat = compare["avg_maturity_years"] > compare["avg_maturity_cap_years"] + 1e-12
    raw_over = compare["core_ratio_raw"] > compare["core_ratio_cap"] + 1e-12
    flag_wrong = raw_over != compare["core_cap_binding"].astype(bool)
    n_bad = int(over_core.sum() + over_mat.sum() + flag_wrong.sum())
    if n_bad:
        return EstimationCheck(
            name, "FAIL",
            f"<표3> 상한 위반 {n_bad}건. 코어비율 초과 {int(over_core.sum())}, "
            f"평균만기 초과 {int(over_mat.sum())}, 상한적용 표시 불일치 "
            f"{int(flag_wrong.sum())}", float(n_bad))
    n_bind = int(compare["core_cap_binding"].astype(bool).sum())
    return EstimationCheck(
        name, "PASS",
        f"코어비율·평균만기 전 {len(compare)}행이 <표3> 상한 이내 "
        f"(상한이 문 행 {n_bind}건)", float(n_bind))


def check_backtest_is_out_of_time(backtest: pd.DataFrame,
                                  model_ledger: pd.DataFrame) -> EstimationCheck:
    """표본외 검증기간이 추정기간과 겹치지 않는가.

    겹치면 검증이 아니라 재적합이다. 추정에 쓴 기간으로 재면 언제나 통과한다.
    """
    name = "alm_backtest_out_of_time"
    if backtest.empty:
        return EstimationCheck(name, "FAIL", "사후검증 원장이 비었다", 0.0)
    def _s(v) -> str:
        # NaN을 `or ""`로 거르면 안 된다. NaN은 참이라 'nan' 문자열이 되고,
        # 그 문자열과의 비교는 어떤 월 라벨보다 크므로 겹침이 통과로 뒤집힌다.
        return "" if v is None or pd.isna(v) else str(v)

    win = {(str(r["model"]), str(r["portfolio_id"])):
           (_s(r["estimation_window_start"]), _s(r["estimation_window_end"]))
           for _, r in model_ledger.iterrows()}
    bad = []
    for _, r in backtest.iterrows():
        k = (str(r["model"]), str(r["portfolio_id"]))
        _, end = win.get(k, ("", ""))
        # 추정구간 종료(YYYY-MM-DD)와 검증구간 시작(YYYY-MM)을 월로 맞춰 본다.
        if not end or str(r["validation_window_start"]) <= end[:7]:
            bad.append("/".join(k))
        if not bool(r["is_out_of_time"]):
            bad.append("/".join(k) + "(표시)")
    if bad:
        return EstimationCheck(
            name, "FAIL",
            f"검증구간이 추정구간과 겹친다. {', '.join(sorted(set(bad))[:5])}. "
            "추정에 쓴 기간으로 검증하면 언제나 통과한다", float(len(bad)))
    return EstimationCheck(
        name, "PASS",
        f"사후검증 {len(backtest)}행 전건이 추정구간 밖 기간으로 측정됐다",
        float(len(backtest)))


def check_unconverged_left_unestimated(
        model_ledger: pd.DataFrame, behaviour_param: pd.DataFrame,
        scurve_param: pd.DataFrame) -> EstimationCheck:
    """수렴 실패 포트폴리오가 미추정으로 남는가.

    수렴하지 않았는데 계수 원장에 값이 들어가 있으면 어딘가에서 기본값이
    조용히 채워진 것이다.
    """
    name = "alm_unconverged_left_unestimated"
    bad: list[str] = []
    for _, r in model_ledger.iterrows():
        if bool(r["converged"]):
            continue
        model, pid = str(r["model"]), str(r["portfolio_id"])
        if model == "CPR":
            hit = behaviour_param[(behaviour_param["model"] == "CPR")
                                  & (behaviour_param["product_group"] == pid)]
            if len(hit) and hit["base_rate_annual"].notna().any():
                bad.append(f"CPR/{pid}: base_rate_annual이 채워졌다")
            s = scurve_param[scurve_param["product_group"] == pid]
            if len(s) and (s["enabled"].astype(bool).any()
                           or s[["coef_a", "coef_b", "coef_c", "coef_d"]]
                           .notna().any().any()):
                bad.append(f"CPR/{pid}: S-curve 계수 또는 enabled가 채워졌다")
        elif model == "TDRR":
            hit = behaviour_param[(behaviour_param["model"] == "TDRR")
                                  & (behaviour_param["product_group"] == pid)]
            if len(hit) and hit["base_rate_annual"].notna().any():
                bad.append(f"TDRR/{pid}: base_rate_annual이 채워졌다")
    n_unconv = int((~model_ledger["converged"].astype(bool)).sum())
    if bad:
        return EstimationCheck(
            name, "FAIL",
            "수렴 실패 모형의 계수가 원장에 들어갔다. " + " · ".join(bad[:5]),
            float(len(bad)))
    return EstimationCheck(
        name, "PASS",
        f"수렴 실패 {n_unconv}건이 전부 미추정으로 남아 있다 (계수 NULL · "
        "S-curve 미사용)", float(n_unconv))


def check_pass_through_gap_closed(nii_before: pd.DataFrame,
                                  nii_after: pd.DataFrame) -> EstimationCheck:
    """전가율을 채운 뒤 ΔNII에서 제외되는 부채 명목이 줄었는가.

    제외 명목이 그대로면 베타가 산출 경로에 닿지 않은 것이고, ΔNII는 관리금리
    부채가 빠진 채로 계속 나온다. 그 상태의 ΔNII는 덜 정확한 값이 아니라
    금리상승이 항상 이익으로 나오는 편향된 값이다.
    """
    name = "alm_nii_pass_through_gap_closed"
    col = "excluded_notional_ratio"
    if nii_before.empty or nii_after.empty or col not in nii_after.columns:
        return EstimationCheck(name, "FAIL",
                               "ΔNII 결과 원장에 제외 명목 컬럼이 없다", None)
    b = float(nii_before[col].max()) if col in nii_before.columns else 1.0
    a = float(nii_after[col].max())
    if a >= b - 1e-12:
        return EstimationCheck(
            name, "FAIL",
            f"전가율을 채웠는데 ΔNII 제외 명목 비율이 줄지 않았다. "
            f"{b:.1%} → {a:.1%}", a)
    return EstimationCheck(
        name, "PASS",
        f"ΔNII 제외 명목 비율이 {b:.1%}에서 {a:.1%}로 줄었다", a)


def check_core_methods_differ(compare: pd.DataFrame) -> EstimationCheck:
    """세 코어 산출방법의 ΔEVE 영향이 서로 다른가.

    같으면 방법이 산출에 닿지 않은 것이고, 비교 화면은 같은 숫자를 세 번
    그리게 된다.
    """
    name = "alm_nmd_core_methods_differ"
    if compare.empty:
        return EstimationCheck(name, "FAIL", "코어 산출방법 비교 원장이 비었다", 0.0)
    spread = (compare.groupby("nmd_category")["delta_eve_proxy_krw"]
              .agg(lambda s: float(s.max() - s.min())))
    worst = float(spread.max()) if len(spread) else 0.0
    flat = sorted(spread[spread <= 0.0].index.astype(str))
    if worst <= 0.0:
        return EstimationCheck(
            name, "FAIL",
            "세 코어 산출방법의 ΔEVE 영향이 전 범주에서 동일하다. 방법 선택이 "
            "산출에 닿지 않았다", worst)
    status = "PASS" if not flat else "WARN"
    detail = (f"방법 간 ΔEVE 영향 차이 최대 {worst:,.0f}원"
              + (f". 다만 {', '.join(flat)} 범주는 <표3> 상한이 세 방법을 같은 "
                 "값으로 눌러 차이가 없다" if flat else ""))
    return EstimationCheck(name, status, detail, worst)


def run_estimation_checks(
        *, compare: pd.DataFrame, backtest: pd.DataFrame,
        model_ledger: pd.DataFrame, behaviour_param: pd.DataFrame,
        scurve_param: pd.DataFrame,
        cf_before: pd.DataFrame | None = None,
        cf_after: pd.DataFrame | None = None,
        nii_before: pd.DataFrame | None = None,
        nii_after: pd.DataFrame | None = None) -> list[EstimationCheck]:
    """추정 관련 정합성 검사 전량. consistency.py가 그대로 받아 report에 담는다."""
    out = [
        check_table3_cap_binds(compare),
        check_backtest_is_out_of_time(backtest, model_ledger),
        check_unconverged_left_unestimated(
            model_ledger, behaviour_param, scurve_param),
        check_core_methods_differ(compare),
    ]
    if cf_before is not None and cf_after is not None:
        out.append(check_estimate_moves_cashflow(cf_before, cf_after))
    if nii_before is not None and nii_after is not None:
        out.append(check_pass_through_gap_closed(nii_before, nii_after))
    return out
