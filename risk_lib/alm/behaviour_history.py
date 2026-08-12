"""행동모형 관측이력 원장. 추정의 **입력 경계**.

**왜 이 원장이 있어야 하는가.** [별표 9-1]은 기본조기상환율·기본중도해지율·
핵심예금 규모를 은행이 **과거자료로 산출**하라고 정한다(제8항 나(2), 제9항
다(1), 제10항 다(1)). 저장소에는 그 과거자료가 없었다. 없으면 추정 절차를
만들 수 없고, 추정이 없으면 `alm_behaviour_param.base_rate_annual`과
`alm_nmd_param.pass_through_beta`가 계속 NULL로 남아 산출이 결손 상태로 나온다.
이 모듈은 그 입력 자리를 원장으로 만든다.

**합성이지 실측이 아니다.** 계좌계·수신계 원천이 이 저장소에 없으므로 세 원장은
전부 합성이며 모든 행에 `source='synthetic'`, `evidence_status='미확인'`이 붙는다.
실측 적재가 들어오면 `source`만 바뀌고 추정 엔진은 그대로 돈다. 그것이 원장을
경계로 두는 이유다.

**생성 모수를 추정기에 넘기지 않는다.** 아래 `_GEN_*` 상수가 합성의 참값이고,
`behaviour_estimation`은 이 상수를 임포트하지 않는다. 추정기가 참값을 얼마나
되찾는지가 테스트이며, 생성기와 추정기가 모수를 공유하면 그 테스트는 자기
정답을 보는 것이 된다.

**결정론.** 난수는 `np.random.default_rng(seed + 전용오프셋)`에서만 나온다.
전역 `np.random`·`hash()`·벽시계 시각을 쓰지 않는다. 오프셋 1201~1203은 신규
전용이며 기존 스트림(balance_sheet 101 · contracts 1101)과 겹치지 않는다.

관측 단위와 규정 문구의 대응
  조기상환   SMM = 초과상환액 / (기초잔액 − 약정상환예정액)  ← 분모에서 약정분을
             먼저 뺀다(SIFMA 순서). 순서를 바꾸면 조기상환액이 과대계상되고 그
             오차가 만기까지 복리된다. `behaviour.apply_prepayment`와 같은 순서다.
  중도해지   월별 해지율 = 해지액 / 기초잔액. 규정은 측정 지평을 정하지 않는다
             (제10항 다·라에 기간 언급이 없다). 지평 규약은 추정 엔진이
             `horizon_convention` 컬럼으로 남긴다.
  비만기예금 월중평잔과 월말잔액을 함께 둔다. 제8항 나(2)가 관찰하라고 적은 것은
             '잔액 변동'이며, 평잔만 보면 월중 인출 폭이 평활되어 사라진다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.alm.params import EVIDENCE_STATUS, NMD_CATEGORIES

__all__ = [
    "OBS_SOURCES", "PREPAY_OBSERVATION", "EARLY_REDEMPTION_OBSERVATION",
    "NMD_BALANCE_HISTORY", "HISTORY_TABLES",
    "PREPAY_PORTFOLIOS", "TERM_DEPOSIT_PORTFOLIOS",
    "month_labels", "build_prepay_observation",
    "build_early_redemption_observation", "build_nmd_balance_history",
    "build_behaviour_history",
]

# 신규 전용 오프셋. 기존 스트림을 밀면 무관한 산출이 바뀐다.
_RNG_PREPAY, _RNG_TDRR, _RNG_NMD = 1201, 1202, 1203

OBS_SOURCES: tuple[str, ...] = ("synthetic", "core_banking", "deposit_system")

# 관측 포트폴리오. `alm_behaviour_param.product_group` 어휘와 같은 문자열을 쓴다.
# 다르면 추정 결과를 계수 원장에 붙일 때 조인이 끊긴다.
PREPAY_PORTFOLIOS: tuple[str, ...] = ("mortgage",)
TERM_DEPOSIT_PORTFOLIOS: tuple[str, ...] = ("term_deposit",)


# ---------------------------------------------------------------- 스펙

_ASOF = C("asof", "date", "기준일", nullable=False)
_OBS_MONTH = C("obs_month", "string", "관측월", nullable=False,
               note="YYYY-MM. 완결된 월만 담는다. asof가 속한 월은 부분월이라 "
                    "상환·해지 실적이 절단되어 관측률이 하방 편의를 갖는다")
_OBS_SEQ = C("obs_seq", "int", "관측 순번", nullable=False, min_value=1,
             note="오래된 월이 1. 정렬을 문자열 비교에 맡기지 않는다")
_SOURCE = C("source", "string", "원천", nullable=False, allowed=OBS_SOURCES)
_EVID = C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS)

PREPAY_OBSERVATION = TableSpec(
    name="alm_prepay_observation", korean="조기상환 관측이력", product="PRD-ALM",
    grain="기준일 × 포트폴리오 × 관측월 1행",
    columns=(
        _ASOF,
        C("portfolio_id", "string", "포트폴리오", nullable=False,
          citation="[별표 9-1] 제9항 다(1). 통화별로 조기상환위험이 있는 "
                   "고정금리대출의 각 포트폴리오에 대하여 만기구간별 "
                   "기본조기상환율을 산출한다. 포트폴리오가 산출 단위다"),
        C("ccy", "string", "통화", nullable=False,
          citation="[별표 9-1] 제9항 다(1). 통화별 산출"),
        _OBS_MONTH, _OBS_SEQ,
        C("opening_balance", "float", "기초 원금잔액", nullable=False, unit="KRW",
          min_value=0.0),
        C("scheduled_principal", "float", "약정 원금상환예정액", nullable=False,
          unit="KRW", min_value=0.0,
          citation="[별표 9-1] 제9항 라. 현금흐름은 약정 원리금 상환예정액에 "
                   "조기상환액을 더해 산출한다. 약정분과 초과분을 나눠 두지 "
                   "않으면 SMM 분모를 만들 수 없다"),
        C("excess_principal", "float", "초과상환액(조기상환)", nullable=False,
          unit="KRW", min_value=0.0),
        C("actual_principal", "float", "실제 원금상환액", nullable=False,
          unit="KRW", min_value=0.0,
          note="약정분 + 초과분. 계정계는 이 합계만 주는 경우가 많고, 그때는 "
               "계약별 상환스케줄을 재구성해야 초과분이 분리된다"),
        C("wa_coupon_rate", "float", "가중평균 약정금리", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("market_refi_rate", "float", "시장 재조달금리", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("refi_incentive_bp", "float", "차환유인", nullable=False, unit="bp",
          note="약정금리 − 재조달금리. 중도상환수수료는 차감하지 않은 정의이며, "
               "적용 단계에서 수수료를 다시 빼면 추정에 쓰지 않은 변수를 "
               "적용하는 것이 된다"),
        C("wa_seasoning_months", "float", "가중평균 경과월수", nullable=False,
          unit="months", min_value=0.0),
        C("cum_prepay_ratio", "float", "누적 조기상환 비율", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="소진(burnout) 설명변수. 누적 초과상환액 / 최초 잔액"),
        C("observed_smm", "float", "관측 SMM", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="SMM = 초과상환액 / (기초잔액 − 약정상환예정액). 분모에서 "
                   "약정분을 먼저 빼는 SIFMA 순서"),
        C("observed_cpr_annual", "float", "관측 CPR(연율)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="CPR = 1 − (1 − SMM)^12. 선형근사 SMM×12를 쓰지 않는다"),
        C("n_accounts", "int", "관측 계좌수", nullable=False, min_value=0),
        _SOURCE, _EVID,
    ),
    primary_key=("asof", "portfolio_id", "obs_month"),
    note="이 원장이 비면 CPR₀는 추정되지 않고 NULL로 남는다. 추정 엔진은 "
         "표본이 없을 때 조용히 표준벤치마크로 넘어가지 않는다.",
)

EARLY_REDEMPTION_OBSERVATION = TableSpec(
    name="alm_early_redemption_observation", korean="중도해지 관측이력",
    product="PRD-ALM",
    grain="기준일 × 포트폴리오 × 관측월 1행",
    columns=(
        _ASOF,
        C("portfolio_id", "string", "포트폴리오", nullable=False,
          citation="[별표 9-1] 제10항 다(1). 통화별로 중도해지위험이 있는 "
                   "기간부예수금의 각 포트폴리오에 대하여 기본중도해지율을 산출"),
        C("ccy", "string", "통화", nullable=False),
        _OBS_MONTH, _OBS_SEQ,
        C("opening_balance", "float", "기초 예수금 잔액", nullable=False,
          unit="KRW", min_value=0.0),
        C("early_redemption_amount", "float", "중도해지액", nullable=False,
          unit="KRW", min_value=0.0),
        C("wa_contract_rate", "float", "가중평균 약정금리", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("market_rate", "float", "시장금리", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("rate_gap_bp", "float", "금리차", nullable=False, unit="bp",
          note="시장금리 − 약정금리. 양수면 재예치 유인이 있다"),
        C("wa_residual_maturity_years", "float", "가중평균 잔존만기",
          nullable=False, unit="years", min_value=0.0),
        C("penalty_rate", "float", "위약금률", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 9-1] 제10항 가. 중도해지 시 상당한 위약금이 부과되면 "
                   "산출 대상에서 제외한다. '상당한'의 정량 기준은 별표가 주지 "
                   "않으므로 위약금률은 제외 판정 기준이자 해지율 설명변수다"),
        C("observed_tdrr_monthly", "float", "관측 월 해지율", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("observed_tdrr_annual", "float", "관측 해지율(연율)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="1 − (1 − 월해지율)^12"),
        C("n_accounts", "int", "관측 계좌수", nullable=False, min_value=0),
        _SOURCE, _EVID,
    ),
    primary_key=("asof", "portfolio_id", "obs_month"),
    note="위약금률이 표본 안에서 변하지 않으면 그 계수는 식별되지 않는다. "
         "위약금 체계 개정 시점이 표본에 들어가야 한다.",
)

NMD_BALANCE_HISTORY = TableSpec(
    name="alm_nmd_balance_history", korean="비만기예금 잔액이력",
    product="PRD-ALM",
    grain="기준일 × NMD 범주 × 관측월 1행",
    columns=(
        _ASOF,
        C("nmd_category", "string", "NMD 범주", nullable=False,
          allowed=NMD_CATEGORIES,
          citation="[별표 9-1] <표3>의 세 범주. 제8항 나(2)는 범주별로 과거 잔액 "
                   "변동을 관찰해 핵심예금 규모를 산출하라고 정한다"),
        C("ccy", "string", "통화", nullable=False),
        _OBS_MONTH, _OBS_SEQ,
        C("avg_balance", "float", "월중평잔", nullable=False, unit="KRW",
          min_value=0.0),
        C("month_end_balance", "float", "월말잔액", nullable=False, unit="KRW",
          min_value=0.0,
          note="평잔만 보면 월중 인출 폭이 평활되어 사라진다. 관찰 대상은 "
               "'잔액 변동'이므로 두 계열을 함께 둔다"),
        C("deposit_rate", "float", "예금금리", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("policy_rate", "float", "시장금리(정책금리)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("policy_rate_change_bp", "float", "시장금리 변동", nullable=True,
          unit="bp", note="첫 관측월은 직전월이 없어 NULL"),
        C("observed_pass_through", "float", "전가율 관측치", nullable=True,
          unit="ratio",
          note="Δ예금금리 / Δ시장금리. 시장금리가 움직이지 않은 달은 분모가 0이라 "
               "NULL이다. 0으로 채우면 전가율 추정이 하방 편의를 갖는다"),
        C("n_accounts", "int", "관측 계좌수", nullable=False, min_value=0),
        _SOURCE, _EVID,
    ),
    primary_key=("asof", "nmd_category", "obs_month"),
    note="핵심예금 산출에는 최소 36개월 이상이 필요하다는 것이 이 원장의 사용 "
         "전제다. BCBS d368 §112는 'past 10 years'를 적지만 국내 별표에는 관찰 "
         "기간 규정이 없다. 두 자료가 어긋나며, 실제 사용 기간은 추정 결과 "
         "원장의 추정구간 컬럼으로 드러난다.",
)

HISTORY_TABLES: tuple[TableSpec, ...] = (
    PREPAY_OBSERVATION, EARLY_REDEMPTION_OBSERVATION, NMD_BALANCE_HISTORY,
)


# ---------------------------------------------------------------- 생성 모수
#
# 아래 세 dataclass가 합성의 **참값**이다. `behaviour_estimation`은 이 모듈에서
# 아무것도 임포트하지 않으며, 추정기가 이 값을 얼마나 되찾는지가 테스트다.

@dataclass(frozen=True)
class _PrepayGen:
    n_months: int
    age_start_months: float
    ramp_ceiling: float          # 연율 CPR 천장
    ramp_slope: float            # 연율 CPR / 경과월
    scurve_b: float              # 진폭
    scurve_c: float              # 1/ratio 기울기
    scurve_d: float              # 변곡 인센티브(ratio)
    burnout_phi: float           # 누적조기상환 1단위당 반응 둔화
    coupon_spread: float         # 기저금리 대비 약정금리 가산
    refi_spread: float           # 기저금리 대비 재조달금리 가산
    refi_ar1_rho: float
    refi_ar1_sd: float
    cpr_noise_sd: float
    sched_amort_monthly: float   # 월 약정상환률(기초잔액 대비)
    opening_balance: float
    n_accounts: int
    late_regime_months: int      # 표본 후반 국면전환 구간 길이
    late_regime_uplift: float    # 그 구간의 조기상환 수준 상승폭


# 국면전환을 넣는 이유: 국내 실증에서 주택가격 상승기·하락기, 위기 전후로
# 조기상환 회귀계수가 동일하지 않음이 보고된다. 단일 표본기간 추정치를 전
# 기간에 쓰면 국면 편의가 생기며, 표본외 검증은 바로 그 편의를 드러내는 장치다.
# 국면전환을 표본 뒤쪽에만 넣으면 표본내 적합도와 표본외 적합도가 갈린다.
_GEN_PREPAY = _PrepayGen(
    n_months=60, age_start_months=8.0,
    ramp_ceiling=0.072, ramp_slope=0.0021,
    scurve_b=0.0180, scurve_c=170.0, scurve_d=0.0030,
    burnout_phi=0.30,
    coupon_spread=0.0165, refi_spread=0.0135,
    refi_ar1_rho=0.80, refi_ar1_sd=0.0021,
    cpr_noise_sd=0.0022,
    sched_amort_monthly=0.0034,
    opening_balance=8.4e12, n_accounts=41_000,
    late_regime_months=12, late_regime_uplift=0.20,
)


@dataclass(frozen=True)
class _TdrrGen:
    n_months: int
    beta0: float                 # 로짓 절편
    beta_gap: float              # 금리차(ratio) 계수
    beta_maturity: float         # 잔존만기(년) 계수
    beta_penalty: float          # 위약금률(ratio) 계수. 음수여야 억제다
    contract_spread: float
    market_ar1_rho: float
    market_ar1_sd: float
    maturity_center: float
    maturity_amp: float
    penalty_before: float
    penalty_after: float
    penalty_switch_month: int    # 위약금 체계 개정 시점. 없으면 계수 미식별
    hazard_noise_sd: float
    opening_balance: float
    n_accounts: int


_GEN_TDRR = _TdrrGen(
    n_months=60,
    beta0=-4.30, beta_gap=48.0, beta_maturity=-0.55, beta_penalty=-2.20,
    contract_spread=0.0045,
    market_ar1_rho=0.83, market_ar1_sd=0.0024,
    maturity_center=1.05, maturity_amp=0.32,
    penalty_before=0.30, penalty_after=0.55, penalty_switch_month=33,
    hazard_noise_sd=0.07,
    opening_balance=21.5e12, n_accounts=186_000,
)


@dataclass(frozen=True)
class _NmdGen:
    level: float                 # 최초 잔액 수준
    growth_annual: float         # 연 성장률
    rate_sensitivity: float      # 잔액/기준잔액이 금리 1.0 상승에 반응하는 폭
    noise_sd: float              # 잔액 잡음(기준잔액 대비)
    intramonth_gap: float        # 월말잔액이 평잔 대비 벌어지는 폭
    pass_through_beta: float     # 예금금리 전가율(참값)
    deposit_rate_base: float
    n_accounts: int


# 범주별 전가율을 다르게 둔다. 결제성 예금은 금리를 거의 따라가지 않고 도매는
# 시장금리에 붙는다는 것이 통상의 방향이며, 이 차이가 ΔNII 부호를 만든다.
_GEN_NMD: dict[str, _NmdGen] = {
    "retail_transactional": _NmdGen(
        level=31.0e12, growth_annual=0.028, rate_sensitivity=6.2,
        noise_sd=0.016, intramonth_gap=0.011, pass_through_beta=0.22,
        deposit_rate_base=0.0015, n_accounts=7_420_000),
    "retail_non_transactional": _NmdGen(
        level=18.5e12, growth_annual=0.019, rate_sensitivity=9.8,
        noise_sd=0.021, intramonth_gap=0.014, pass_through_beta=0.48,
        deposit_rate_base=0.0090, n_accounts=2_180_000),
    "wholesale_nonfin": _NmdGen(
        level=12.8e12, growth_annual=0.011, rate_sensitivity=15.5,
        noise_sd=0.033, intramonth_gap=0.022, pass_through_beta=0.79,
        deposit_rate_base=0.0125, n_accounts=64_000),
}

_GEN_NMD_MONTHS = 72
_GEN_NMD_POLICY_RHO = 0.94
_GEN_NMD_POLICY_SD = 0.0016
# 정책금리는 25bp 격자로만 움직인다. 격자를 넣지 않으면 Δ정책금리가 0인 달이
# 없어 전가율 관측치의 결측 처리가 시험되지 않는다.
_GEN_NMD_POLICY_STEP = 0.0025


# ---------------------------------------------------------------- 공통

def month_labels(asof: str, n_months: int) -> list[str]:
    """asof 직전월부터 과거로 n개월, 오래된 순. 벽시계 시각을 쓰지 않는다.

    asof가 속한 달을 넣지 않는 이유는 부분월이기 때문이다. 부분월의 상환·해지
    실적을 한 달치로 세면 관측률이 하방 편의를 갖고, 그 편의가 그대로 CPR₀·
    TDRR₀로 들어간다.
    """
    if n_months <= 0:
        raise ValueError(f"관측 개월수는 1 이상. 받은 값 {n_months}")
    y, m = int(asof[:4]), int(asof[5:7])
    out: list[str] = []
    for _ in range(n_months):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y:04d}-{m:02d}")
    return list(reversed(out))


def _ar1(rng: np.random.Generator, n: int, rho: float, sd: float) -> np.ndarray:
    """평균 0 AR(1) 경로. 초기값을 정상분포에서 뽑아 앞부분 편의를 없앤다."""
    x = np.empty(n, dtype=float)
    x[0] = rng.normal(0.0, sd / np.sqrt(max(1.0 - rho * rho, 1e-9)))
    for t in range(1, n):
        x[t] = rho * x[t - 1] + rng.normal(0.0, sd)
    return x


# ---------------------------------------------------------------- 빌더

def build_prepay_observation(asof: str, *, seed: int, base_rate: float,
                             portfolio_id: str = PREPAY_PORTFOLIOS[0],
                             ccy: str = "KRW") -> pd.DataFrame:
    """조기상환 관측이력. 폐쇄형 풀(신규 유입 없음)의 월별 상환 실적.

    폐쇄형으로 두는 이유는 신규 유입이 있으면 가중평균 경과월수가 표본 안에서
    되돌아가고, 경과효과와 차환유인의 공선성이 관측 설계 단계에서 생기기
    때문이다. 실측 풀이 들어오면 vintage로 잘라 같은 성질을 만든다.
    """
    g = _GEN_PREPAY
    rng = np.random.default_rng(seed + _RNG_PREPAY)
    months = month_labels(asof, g.n_months)
    n = len(months)

    dev = _ar1(rng, n, g.refi_ar1_rho, g.refi_ar1_sd)
    coupon = np.full(n, base_rate + g.coupon_spread)
    refi = base_rate + g.refi_spread + dev
    incentive = coupon - refi                      # ratio
    age = g.age_start_months + np.arange(n, dtype=float)
    noise = rng.normal(0.0, g.cpr_noise_sd, n)

    # 국면전환은 표본 뒤쪽 구간에만 건다.
    regime = np.zeros(n)
    if g.late_regime_months > 0:
        regime[-g.late_regime_months:] = g.late_regime_uplift

    rows = []
    bal = g.opening_balance
    initial = g.opening_balance
    cum_excess = 0.0
    for t in range(n):
        cum_ratio = min(cum_excess / initial, 1.0)
        level = (min(g.ramp_ceiling, g.ramp_slope * age[t])
                 + g.scurve_b * np.arctan(g.scurve_c * (incentive[t] - g.scurve_d)))
        cpr = level * (1.0 - g.burnout_phi * cum_ratio) * (1.0 + regime[t]) + noise[t]
        cpr = float(np.clip(cpr, 1e-4, 0.95))
        smm = 1.0 - (1.0 - cpr) ** (1.0 / 12.0)

        sched = bal * g.sched_amort_monthly
        excess = smm * max(bal - sched, 0.0)
        rows.append({
            "asof": asof, "portfolio_id": portfolio_id, "ccy": ccy,
            "obs_month": months[t], "obs_seq": t + 1,
            "opening_balance": bal, "scheduled_principal": sched,
            "excess_principal": excess, "actual_principal": sched + excess,
            "wa_coupon_rate": float(coupon[t]),
            "market_refi_rate": float(refi[t]),
            "refi_incentive_bp": float(incentive[t] * 1e4),
            "wa_seasoning_months": float(age[t]),
            "cum_prepay_ratio": cum_ratio,
            # 금액에서 되돌려 적는다. 관측치와 금액이 서로 재현되지 않으면
            # 추정기가 어느 쪽을 읽었는지에 따라 결과가 갈린다.
            "observed_smm": excess / max(bal - sched, 1e-9),
            "observed_cpr_annual": 1.0 - (1.0 - smm) ** 12,
            "n_accounts": int(round(g.n_accounts * bal / initial)),
            "source": "synthetic", "evidence_status": "미확인",
        })
        cum_excess += excess
        bal = max(bal - sched - excess, 0.0)
    return pd.DataFrame(rows, columns=list(PREPAY_OBSERVATION.column_names))


def build_early_redemption_observation(
        asof: str, *, seed: int, base_rate: float,
        portfolio_id: str = TERM_DEPOSIT_PORTFOLIOS[0],
        ccy: str = "KRW") -> pd.DataFrame:
    """중도해지 관측이력. 회전형 정기예금 포트폴리오.

    위약금률에 표본 중간의 개정 시점을 넣는다. 위약금이 표본 안에서 상수면
    그 계수는 절편과 완전공선이라 식별되지 않으며, 그때 추정기는 "위약금이
    해지를 억제한다"는 규정의 전제(제10항 가)를 검증할 수 없다.
    """
    g = _GEN_TDRR
    rng = np.random.default_rng(seed + _RNG_TDRR)
    months = month_labels(asof, g.n_months)
    n = len(months)

    dev = _ar1(rng, n, g.market_ar1_rho, g.market_ar1_sd)
    contract = np.full(n, base_rate + g.contract_spread)
    market = base_rate + dev
    gap = market - contract                        # ratio
    resid_mat = g.maturity_center + g.maturity_amp * np.sin(
        2.0 * np.pi * np.arange(n) / 12.0)
    penalty = np.where(np.arange(n) < g.penalty_switch_month,
                       g.penalty_before, g.penalty_after)
    eta_noise = rng.normal(0.0, g.hazard_noise_sd, n)

    eta = (g.beta0 + g.beta_gap * gap + g.beta_maturity * resid_mat
           + g.beta_penalty * penalty + eta_noise)
    hazard = 1.0 / (1.0 + np.exp(-eta))

    rows = []
    bal = g.opening_balance
    for t in range(n):
        amount = bal * float(hazard[t])
        rows.append({
            "asof": asof, "portfolio_id": portfolio_id, "ccy": ccy,
            "obs_month": months[t], "obs_seq": t + 1,
            "opening_balance": bal, "early_redemption_amount": amount,
            "wa_contract_rate": float(contract[t]),
            "market_rate": float(market[t]),
            "rate_gap_bp": float(gap[t] * 1e4),
            "wa_residual_maturity_years": float(resid_mat[t]),
            "penalty_rate": float(penalty[t]),
            "observed_tdrr_monthly": amount / bal,
            "observed_tdrr_annual": 1.0 - (1.0 - amount / bal) ** 12,
            "n_accounts": g.n_accounts,
            "source": "synthetic", "evidence_status": "미확인",
        })
        # 회전형이라 해지분은 재예치로 대체된다. 잔액은 유지된다.
        bal = g.opening_balance
    return pd.DataFrame(
        rows, columns=list(EARLY_REDEMPTION_OBSERVATION.column_names))


def build_nmd_balance_history(asof: str, *, seed: int, base_rate: float,
                              ccy: str = "KRW") -> pd.DataFrame:
    """비만기예금 잔액이력. 범주별 월중평잔·월말잔액·예금금리·정책금리.

    정책금리를 25bp 격자로 움직인다. 격자가 없으면 모든 달에 Δ정책금리가 0이
    아니게 되어 전가율 관측치의 결측(분모 0) 처리가 한 번도 시험되지 않는다.
    """
    rng = np.random.default_rng(seed + _RNG_NMD)
    months = month_labels(asof, _GEN_NMD_MONTHS)
    n = len(months)

    raw = base_rate + _ar1(rng, n, _GEN_NMD_POLICY_RHO, _GEN_NMD_POLICY_SD)
    policy = np.maximum(np.round(raw / _GEN_NMD_POLICY_STEP)
                        * _GEN_NMD_POLICY_STEP, 0.0)
    policy_mean = float(policy.mean())

    rows = []
    for cat in NMD_CATEGORIES:
        g = _GEN_NMD[cat]
        bal_noise = rng.normal(0.0, g.noise_sd, n)
        rate_noise = rng.normal(0.0, 1e-4, n)
        dep = np.empty(n, dtype=float)
        dep[0] = g.deposit_rate_base + g.pass_through_beta * (
            float(policy[0]) - policy_mean)
        for t in range(1, n):
            dep[t] = (dep[t - 1]
                      + g.pass_through_beta * float(policy[t] - policy[t - 1])
                      + rate_noise[t])
        dep = np.maximum(dep, 0.0)

        trend = 1.0 + g.growth_annual * np.arange(n) / 12.0
        shape = trend - g.rate_sensitivity * (policy - policy_mean) + bal_noise
        avg_bal = g.level * np.maximum(shape, 0.05)
        eom_gap = rng.normal(0.0, g.intramonth_gap, n)
        eom_bal = avg_bal * np.maximum(1.0 + eom_gap, 0.05)

        for t in range(n):
            d_policy = None if t == 0 else float(policy[t] - policy[t - 1])
            pt = None
            if d_policy is not None and abs(d_policy) > 1e-12:
                pt = float((dep[t] - dep[t - 1]) / d_policy)
            rows.append({
                "asof": asof, "nmd_category": cat, "ccy": ccy,
                "obs_month": months[t], "obs_seq": t + 1,
                "avg_balance": float(avg_bal[t]),
                "month_end_balance": float(eom_bal[t]),
                "deposit_rate": float(dep[t]),
                "policy_rate": float(policy[t]),
                "policy_rate_change_bp": (None if d_policy is None
                                          else d_policy * 1e4),
                "observed_pass_through": pt,
                "n_accounts": g.n_accounts,
                "source": "synthetic", "evidence_status": "미확인",
            })
    return pd.DataFrame(rows, columns=list(NMD_BALANCE_HISTORY.column_names))


def build_behaviour_history(asof: str, *, seed: int, base_rate: float,
                            ccy: str = "KRW") -> dict[str, pd.DataFrame]:
    """관측이력 원장 3장. 키는 테이블명. 검증·실체화가 그대로 받는다."""
    return {
        "alm_prepay_observation": build_prepay_observation(
            asof, seed=seed, base_rate=base_rate, ccy=ccy),
        "alm_early_redemption_observation": build_early_redemption_observation(
            asof, seed=seed, base_rate=base_rate, ccy=ccy),
        "alm_nmd_balance_history": build_nmd_balance_history(
            asof, seed=seed, base_rate=base_rate, ccy=ccy),
    }
