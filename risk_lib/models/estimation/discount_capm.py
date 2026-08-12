"""CAPM 회수 할인율 추정 (IRB-D001).

[별표 3] 184.(1)은 경제적 손실에 "회수기간에 따른 할인효과"를 고려하라고만 하고
할인율의 수준·산식·세그먼트 구분을 주지 않는다. 그래서 ``crm_lgd_discount_rate``의
``discount_rate``가 전건 NULL이고 LGD가 전 세그먼트 '산출불가'로 남아 있다.
이 모듈은 그 빈칸을 **자기자본비용(CAPM)** 으로 추정하는 경로를 만든다.

    k_e = R_f + beta · (R_M − R_f)

    R_f    국고채 3년(KTB3Y) 관측 계열의 산출대상기간 평균 (연율)
    R_M    KOSPI 로그수익률의 연율화 평균
    beta   초과수익률 회귀의 기울기. 표준오차·결정계수를 함께 원장에 남긴다

**회수유형을 나눈다.** 예적금 상계처럼 회수 불확실성이 없는 회수(``무위험회수``)는
R_f를, 나머지(``전체``)는 k_e를 쓴다. 교안이 무위험이자율을 "현금담보에 의한 회수
등 회수의 불확실성이 존재하지 않는 경우를 제외하고는 적절하지 않음"으로 적은 것과
같은 구분이다(``docs/primary_sources/BEEL_PLGD_조사결과.md`` §할인율). 우리금융지주
실측에서 예적금담보 4.01%가 무위험이자율 수준이고 예적금 外 11.22%가 자기자본비용
수준인 것도 이 구분과 부합한다. **타행 실측은 참고치일 뿐 여기서 베끼지 않는다.**

## 베타를 어떻게 얻었나

관측 가능한 은행 주가 계열이 이 저장소에 없다. 세 가지 길 중 **(a) 은행주 수익률
관측 원장을 결정론 합성으로 신설하고 초과수익률 회귀로 추정**하는 길을 골랐다.
생성 베타(``_TRUE_BETA``)는 이 모듈의 빌더 구역에만 있고 추정기에 넘기지 않는다.
추정기가 그 값을 허용오차 안에서 되찾는지가 ``tests/test_discount_capm.py``의
시험이다.

**합성 베타로 낸 할인율은 실측이 아니다.** 그 사실이 원장에서 읽혀야 하므로
관측·추정 원장과 승인된 할인율 행 전부에 ``evidence_status='내부추정(합성관측)'``이
붙고, 화면의 회수 할인율 카드가 그 칸을 그대로 싣는다.

## 이 원장으로 시장수익률을 추정할 수 없다

``rdm_macro_indicator_master``의 KOSPI는 **표류항이 없는 평균회귀 계열**이다
(level 2600으로 되돌아가고 drift 칸이 마스터에 없다). 그래서 어느 구간을 잡아도
로그수익률의 평균이 0 부근이고, R_M − R_f 가 구조적으로 −R_f 근처의 음수가 된다.
seed·기간을 바꿔도 부호가 바뀌지 않는다.

이것을 조용히 넘기면 k_e = R_f + beta·(음수) 가 되어 무위험회수보다 낮은, beta가
1을 넘으면 음수인 할인율이 나온다. 그래서 **위험프리미엄에 0 하한을 둔다**
(내부기준, 사용자 지시). 프리미엄이 0 이하이면 0으로 막아 ``k_e = R_f`` 를 쓰고
``ke_status='산출완료(프리미엄0하한)'`` 로 그 사실을 남긴다. 체계적 위험분이
빠진 값이며 beta 는 결과에 들어가지 않는다.

이 하한은 할인율을 **낮추는** 쪽이다. 할인율이 낮으면 회수액의 현재가치가 커져
LGD 가 작아지므로 보수적인 방향이 아니다. 그래서 상태값을 산출물과 화면까지
따라붙게 두고, 승인된 R_M 이 들어오면 그 값이 하한보다 우선한다.

R_M은 ``crm_estimation_param``의 ``capm_market_return``으로 승인받는 내부기준
모수다. 승인되면 관측 실현 대신 그 값으로 프리미엄을 내고, 그때 프리미엄이
양수이면 하한이 걸리지 않는다.

**결정론.** 은행주 계열은 전용 스트림 ``default_rng(seed + 90_404)``를 쓴다.
전역 ``np.random``·내장 ``hash()``·벽시계 시각을 쓰지 않으며 승인일은 ``asof``다.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.macro_monitor import observations
from risk_lib.models.estimation.common import cast_to_spec
from risk_lib.models.estimation.lgd_est import realised_lgd
from risk_lib.models.estimation.params import (
    IRB_EVIDENCE_STATUS, ParamWarning, approve_discount_rate,
    build_crm_lgd_discount_rate, param_value,
)
from risk_lib.validation.consistency import ConsistencyCheck, ValidationReport

__all__ = [
    "MARKET_INDICATOR", "RISKFREE_INDICATOR", "N_PERIODS_DEFAULT",
    "CAPM_APPROVER", "CAPM_EVIDENCE", "KE_STATUS", "MARKET_RETURN_SOURCES",
    "CAPM_OBSERVATION", "CAPM_ESTIMATE", "CAPM_TABLES",
    "CapmEstimate", "CapmWarning",
    "build_crm_capm_observation", "estimate_capm_discount_rate",
    "build_crm_capm_estimate", "capm_rate_by_scope",
    "apply_capm_discount_rates", "build_capm_discount_ledgers",
    "check_capm_recalculation", "check_riskfree_scope_below_total",
    "check_discount_rate_approved", "check_capm_evidence_disclosed",
    "check_lgd_increases_with_discount_rate", "run_capm_checks",
]


class CapmWarning(UserWarning):
    """CAPM 추정을 건너뛰었거나 할인율을 채우지 못했다는 경고."""


# ---------------------------------------------------------------- 어휘

#: 초과수익률 회귀가 읽는 지표. 두 값 모두 ``rdm_macro_indicator_master``의 행이다.
MARKET_INDICATOR = "KOSPI"
RISKFREE_INDICATOR = "KTB3Y"
#: 산출대상기간의 기본 길이(월). 우리금융 실측의 2003~2014와 같은 12년이다.
N_PERIODS_DEFAULT = 144
#: 승인자 자리에 적는 식별자. 사람도 승인기구도 아니라는 사실이 이름에 드러난다.
CAPM_APPROVER = "내부추정(CAPM)"
#: 합성 관측으로 낸 값이라는 표시. 실측·원문확인과 섞이면 안 된다.
CAPM_EVIDENCE = "내부추정(합성관측)"
KE_STATUS: tuple[str, ...] = (
    "산출완료", "산출완료(프리미엄0하한)", "추정불가(위험프리미엄비양수)",
    "추정불가(할인율범위밖)", "추정불가(표본부족)")
MARKET_RETURN_SOURCES: tuple[str, ...] = ("관측실현", "승인모수")

_MARKET_RETURN_BASES: tuple[str, ...] = ("로그수익률",)
_RISKFREE_CONVERSIONS: tuple[str, ...] = ("연율→월 복리환산",)
_BANK_RETURN_SOURCES: tuple[str, ...] = ("합성관측",)

_OBS_CITE = (
    "은행주 관측 계열이 저장소에 없어 결정론 합성으로 만들었다. 시장·무위험 "
    "계열은 rdm_macro_indicator_master의 KOSPI·KTB3Y 관측치이며 그 마스터 역시 "
    "합성 기준점(evidence_status='미확인')이다. 실측이 아니다")
_EST_CITE = (
    "[별표 3] 184.(1)은 '회수기간에 따른 할인효과'만 정하고 할인율의 수준·산식·"
    "세그먼트 구분을 주지 않는다. CAPM 채택과 산출대상기간은 내부기준이며 "
    "승인기구 의결이 효력 요건이다. 방법론은 우리금융지주 적합성 검증 서식을 "
    "참고했고 값은 본 은행 원장으로 다시 추정했다")

# ---------------------------------------------------------------- 생성 모수
# 아래 셋은 규제표도 추정 결과도 아니다. 은행주 관측 계열을 합성하는 생성
# 모수이며 추정기(`estimate_capm_discount_rate`)는 이 값을 읽지 않는다.
# 추정기가 `_TRUE_BETA`를 되찾는지가 시험이다.

_SEED_OFF_CAPM = 90_404
_TRUE_BETA = 1.15        # 은행주 베타
_TRUE_ALPHA = 0.0        # CAPM이 정확히 성립하도록 절편을 0으로 둔다
_IDIO_SD = 0.025         # 월별 고유위험 표준편차


# ---------------------------------------------------------------- 스펙

CAPM_OBSERVATION = TableSpec(
    name="crm_capm_observation", korean="CAPM 관측 계열", product="PRD-RWA",
    grain="기준일 × 관측월 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("period", "string", "관측월", nullable=False,
          note="YYYY-MM. 지표 관측 원장의 period 표기를 그대로 쓴다"),
        C("market_indicator", "string", "시장지표", nullable=False,
          note="rdm_macro_indicator_master의 indicator_id. 산출 묶음이 달라 "
               "외래키를 걸지 않는다. 마스터가 함께 실리는 화면에서 조인한다"),
        C("riskfree_indicator", "string", "무위험지표", nullable=False),
        C("market_index", "float", "시장지수", nullable=False, unit="지수",
          min_value=0.0),
        C("riskfree_yield", "float", "무위험 만기수익률", nullable=False,
          unit="%(연율)"),
        C("market_return", "float", "시장 수익률", nullable=False,
          unit="ratio(월)", note="ln(지수_t / 지수_{t-1})"),
        C("riskfree_return", "float", "무위험 수익률", nullable=False,
          unit="ratio(월)", note="(1+연율)^(1/12) − 1"),
        C("bank_equity_return", "float", "은행주 수익률", nullable=False,
          unit="ratio(월)"),
        C("excess_market_return", "float", "시장 초과수익률", nullable=False,
          unit="ratio(월)", note="시장 수익률 − 무위험 수익률. 회귀의 설명변수"),
        C("excess_bank_return", "float", "은행주 초과수익률", nullable=False,
          unit="ratio(월)", note="회귀의 피설명변수"),
        C("market_return_basis", "string", "시장 수익률 산식", nullable=False,
          allowed=_MARKET_RETURN_BASES),
        C("riskfree_conversion", "string", "무위험 수익률 환산", nullable=False,
          allowed=_RISKFREE_CONVERSIONS),
        C("bank_return_source", "string", "은행주 계열 출처", nullable=False,
          allowed=_BANK_RETURN_SOURCES,
          note="관측 가능한 은행 주가 계열이 없어 결정론 합성으로 만들었다"),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
        C("source_system", "string", "원천", nullable=False,
          allowed=("market_data", "synthetic")),
    ),
    primary_key=("asof", "period"),
    note="회귀의 입력을 월별로 남긴다. 베타만 원장에 두면 어느 표본으로 낸 "
         "값인지 재현할 수 없다.",
)

CAPM_ESTIMATE = TableSpec(
    name="crm_capm_estimate", korean="CAPM 할인율 추정", product="PRD-RWA",
    grain="기준일 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("n_observations", "int", "관측 개월수", nullable=False, min_value=0),
        C("period_start", "string", "산출대상기간 시작", nullable=True),
        C("period_end", "string", "산출대상기간 종료", nullable=True),
        C("riskfree_annual", "float", "무위험이자율", nullable=True,
          unit="ratio(연율)",
          note="KTB3Y 관측 만기수익률의 산출대상기간 평균. 무위험회수 할인율이 "
               "곧 이 값이다"),
        C("market_return_observed", "float", "시장수익률(관측)", nullable=True,
          unit="ratio(연율)", note="월별 로그수익률 평균 × 12"),
        C("market_return_applied", "float", "시장수익률(적용)", nullable=True,
          unit="ratio(연율)"),
        C("market_return_source", "string", "시장수익률 출처", nullable=False,
          allowed=MARKET_RETURN_SOURCES),
        C("market_premium", "float", "시장위험프리미엄", nullable=True,
          unit="ratio(연율)", note="R_M − R_f. 0 이하이면 k_e를 내지 않는다"),
        C("beta", "float", "베타", nullable=True, unit="배",
          note="초과수익률 회귀의 기울기"),
        C("beta_stderr", "float", "베타 표준오차", nullable=True, unit="배"),
        C("beta_tstat", "float", "베타 t값", nullable=True, unit="배"),
        C("beta_r2", "float", "결정계수", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("alpha", "float", "절편", nullable=True, unit="ratio(월)",
          note="CAPM이 성립하면 0이다. 회귀 결과를 그대로 남긴다"),
        C("cost_of_equity", "float", "자기자본비용", nullable=True,
          unit="ratio(연율)", min_value=0.0, max_value=1.0,
          note="k_e. 산출할 수 없으면 NULL이고 ke_status가 사유를 든다"),
        C("cost_of_equity_raw", "float", "자기자본비용(산식값)", nullable=True,
          unit="ratio(연율)",
          note="R_f + beta·(R_M − R_f)를 그대로 적은 값. 음수여도 숨기지 "
               "않는다. 할인율로 쓰이는 값은 cost_of_equity 쪽이다"),
        C("ke_status", "string", "자기자본비용 상태", nullable=False,
          allowed=KE_STATUS),
        C("rf_source", "text", "무위험이자율 출처", nullable=False),
        C("beta_source", "text", "베타 출처", nullable=False),
        C("estimation_period", "text", "산출대상기간", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
        C("reference_note", "text", "참고치", nullable=True,
          note="타행 실측. 승인 판단의 참고자료이며 엔진은 읽지 않는다"),
    ),
    primary_key=("asof",),
    note="베타의 표준오차·결정계수까지 원장에 둔다. 점추정만 남기면 "
         "추정 불확실성이 화면에서 사라진다.",
)

CAPM_TABLES: dict[str, TableSpec] = {
    CAPM_OBSERVATION.name: CAPM_OBSERVATION,
    CAPM_ESTIMATE.name: CAPM_ESTIMATE,
}

_REFERENCE_NOTE = (
    "우리금융지주 「V. 리스크 측정요소의 계량화 2. LGD」 적합성 검증 서식은 같은 "
    "방법(R_f 국고채 3년, R_M KOSPI 로그수익률, 베타 Bloomberg)으로 2003~2014 "
    "산술평균 예적금담보 4.01% · 예적금 外 11.22%를 냈다. 타행 실측이며 본 "
    "은행의 내부기준이 아니다. 베타를 공시하지 않아 그 서식에서 R_M을 역산할 수 "
    "없다")


# ---------------------------------------------------------------- 관측 원장

def build_crm_capm_observation(*, asof: str | date, seed: int = 42,
                               n_periods: int = N_PERIODS_DEFAULT,
                               master: pd.DataFrame | None = None
                               ) -> pd.DataFrame:
    """CAPM 관측 계열을 만든다. 기준일 × 관측월 1행.

    시장·무위험 계열은 ``macro_monitor.observations``에서 읽는다. 수익률 1개를
    만들려면 지수 2개가 필요하므로 지표 관측은 ``n_periods + 1``개월을 받아
    첫 달을 기준으로만 쓴다.

    은행주 수익률은 ``r_bank = R_f + beta·(R_M − R_f) + eps``로 합성한다.
    생성 베타는 이 모듈의 생성 모수 구역에만 있고 추정기에 넘기지 않는다.
    """
    if n_periods < 3:
        raise ValueError("n_periods는 3 이상이어야 한다. 회귀 표본이 없다")
    asof_s = asof.isoformat() if isinstance(asof, date) else str(asof)

    obs = observations(asof_s, seed=seed, n_periods=n_periods + 1,
                       master=master)
    cols = [c.name for c in CAPM_OBSERVATION.columns]
    mkt = obs[obs["indicator_id"] == MARKET_INDICATOR].sort_values("period")
    rfr = obs[obs["indicator_id"] == RISKFREE_INDICATOR].sort_values("period")
    if mkt.empty or rfr.empty:
        warnings.warn(
            f"지표 관측 원장에 {MARKET_INDICATOR} 또는 {RISKFREE_INDICATOR}가 "
            "없어 CAPM 관측 계열을 만들지 않는다. 마스터의 계열 생성 칸이 비어 "
            "있는지 본다", CapmWarning, stacklevel=2)
        return cast_to_spec(pd.DataFrame(columns=cols), CAPM_OBSERVATION)

    periods = list(mkt["period"])[1:]
    index = mkt["value"].to_numpy(dtype=float)
    yield_pct = rfr["value"].to_numpy(dtype=float)[1:]
    r_market = np.diff(np.log(index))
    r_free = (1.0 + yield_pct / 100.0) ** (1.0 / 12.0) - 1.0
    excess_market = r_market - r_free

    g = np.random.default_rng(seed + _SEED_OFF_CAPM)
    eps = g.normal(0.0, _IDIO_SD, len(periods))
    r_bank = r_free + _TRUE_ALPHA + _TRUE_BETA * excess_market + eps

    out = pd.DataFrame({
        "asof": asof_s, "period": periods,
        "market_indicator": MARKET_INDICATOR,
        "riskfree_indicator": RISKFREE_INDICATOR,
        "market_index": index[1:], "riskfree_yield": yield_pct,
        "market_return": r_market, "riskfree_return": r_free,
        "bank_equity_return": r_bank,
        "excess_market_return": excess_market,
        "excess_bank_return": r_bank - r_free,
        "market_return_basis": "로그수익률",
        "riskfree_conversion": "연율→월 복리환산",
        "bank_return_source": "합성관측",
        "citation": _OBS_CITE, "evidence_status": CAPM_EVIDENCE,
        "source_system": "synthetic",
    })
    return cast_to_spec(out[cols], CAPM_OBSERVATION)


# ---------------------------------------------------------------- 추정

@dataclass(frozen=True)
class CapmEstimate:
    """CAPM 추정 결과. 원장 1행과 같은 사실을 담는다."""
    asof: str
    n_observations: int
    period_start: str | None
    period_end: str | None
    riskfree_annual: float | None
    market_return_observed: float | None
    market_return_applied: float | None
    market_return_source: str
    market_premium: float | None
    beta: float | None
    beta_stderr: float | None
    beta_tstat: float | None
    beta_r2: float | None
    alpha: float | None
    cost_of_equity: float | None
    cost_of_equity_raw: float | None
    ke_status: str

    @property
    def rf_source(self) -> str:
        return (f"rdm_macro_indicator_master {RISKFREE_INDICATOR}(국고채 3년) "
                f"관측 계열 {self.n_observations}개월 만기수익률 평균. 마스터는 "
                "합성 기준점이며 공표통계가 아니다")

    @property
    def beta_source(self) -> str:
        if self.beta is None:
            return "합성 관측 회귀 (표본 부족으로 미산출)"
        return (f"합성 관측 회귀. crm_capm_observation의 초과수익률 "
                f"{self.n_observations}개월 OLS 기울기 {self.beta:.4f} "
                f"(표준오차 {self.beta_stderr:.4f}, R² {self.beta_r2:.4f}). "
                "관측 가능한 은행 주가 계열이 없어 결정론 합성으로 만든 표본이며 "
                "실측 베타가 아니다")

    @property
    def estimation_period(self) -> str:
        return (f"{self.period_start}~{self.period_end} 월별 "
                f"{self.n_observations}개월")

    def ledger_annotation(self) -> dict[str, str]:
        """할인율 원장 빌더가 받는 출처 칸.

        값(할인율)도 근거 상태도 여기 없다. 둘은 승인 단계에서 함께 들어간다.
        """
        return {"rf_source": self.rf_source, "beta_source": self.beta_source,
                "estimation_period": self.estimation_period}


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """단순회귀 기울기·표준오차·결정계수·절편.

    numpy.polyfit은 표준오차를 주지 않는다. 잔차분산에서 직접 낸다.
    """
    n = len(x)
    xbar, ybar = float(x.mean()), float(y.mean())
    sxx = float(((x - xbar) ** 2).sum())
    sxy = float(((x - xbar) * (y - ybar)).sum())
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    resid = y - (intercept + slope * x)
    sse = float((resid ** 2).sum())
    sst = float(((y - ybar) ** 2).sum())
    s2 = sse / (n - 2)
    stderr = float(np.sqrt(s2 / sxx))
    r2 = float(1.0 - sse / sst) if sst > 0 else float("nan")
    return slope, stderr, r2, intercept


def estimate_capm_discount_rate(obs: pd.DataFrame, *,
                                market_return: float | None = None
                                ) -> CapmEstimate:
    """관측 원장에서 R_f·R_M·beta·k_e를 낸다.

    ``market_return``은 승인된 내부기준 시장수익률(연율)이다. 주지 않으면 관측
    계열의 실현 평균을 쓰는데, 지표 마스터의 KOSPI가 표류항 없는 평균회귀
    계열이라 실현 프리미엄이 구조적으로 0 이하다.

    프리미엄이 0 이하이면 0으로 막아 ``k_e = R_f`` 를 쓰고 ``ke_status`` 를
    ``'산출완료(프리미엄0하한)'`` 로 둔다 (내부기준). 그 값에는 체계적 위험분이
    없고 beta 가 들어가지 않는다. ``cost_of_equity_raw`` 는 하한 전 산식값을
    그대로 들고 있으므로 둘을 대조하면 하한이 얼마나 걸렸는지 읽힌다.
    """
    asof = (str(obs["asof"].iloc[0]) if len(obs) else "")
    if len(obs) < 3:
        return CapmEstimate(
            asof=asof, n_observations=int(len(obs)), period_start=None,
            period_end=None, riskfree_annual=None,
            market_return_observed=None, market_return_applied=None,
            market_return_source=("승인모수" if market_return is not None
                                  else "관측실현"),
            market_premium=None, beta=None, beta_stderr=None, beta_tstat=None,
            beta_r2=None, alpha=None, cost_of_equity=None,
            cost_of_equity_raw=None, ke_status="추정불가(표본부족)")

    d = obs.sort_values("period")
    rf_annual = float(pd.to_numeric(d["riskfree_yield"]).mean()) / 100.0
    rm_observed = float(pd.to_numeric(d["market_return"]).mean()) * 12.0
    slope, stderr, r2, intercept = _ols(
        d["excess_market_return"].to_numpy(dtype=float),
        d["excess_bank_return"].to_numpy(dtype=float))

    applied = rm_observed if market_return is None else float(market_return)
    source = "관측실현" if market_return is None else "승인모수"
    premium = applied - rf_annual
    ke_raw = rf_annual + slope * premium

    if premium <= 0.0:
        # 위험프리미엄에 0 하한을 둔다 (내부기준). 프리미엄이 음수면 체계적
        # 위험의 대가가 음수라는 뜻이 되어 beta 가 클수록 할인율이 낮아지는,
        # 방향이 뒤집힌 값이 나온다. 0 으로 막으면 k_e = R_f 이며 체계적
        # 위험분이 빠진 값이다. 그 사실은 상태값이 든다.
        #
        # 주의. 이 하한은 할인율을 낮추는 쪽이고, 할인율이 낮으면 회수액의
        # 현재가치가 커져 LGD 가 작아진다. 보수적인 방향이 아니다.
        ke, status = float(rf_annual), "산출완료(프리미엄0하한)"
    elif not (0.0 < ke_raw <= 1.0):
        ke, status = None, "추정불가(할인율범위밖)"
    else:
        ke, status = float(ke_raw), "산출완료"

    return CapmEstimate(
        asof=asof, n_observations=int(len(d)),
        period_start=str(d["period"].iloc[0]),
        period_end=str(d["period"].iloc[-1]),
        riskfree_annual=rf_annual, market_return_observed=rm_observed,
        market_return_applied=applied, market_return_source=source,
        market_premium=float(premium), beta=float(slope),
        beta_stderr=float(stderr),
        beta_tstat=(float(slope / stderr) if stderr > 0 else None),
        beta_r2=float(r2), alpha=float(intercept), cost_of_equity=ke,
        cost_of_equity_raw=float(ke_raw), ke_status=status)


def build_crm_capm_estimate(est: CapmEstimate) -> pd.DataFrame:
    """추정 결과를 원장 1행으로 옮긴다."""
    row = {
        "asof": est.asof, "n_observations": est.n_observations,
        "period_start": est.period_start, "period_end": est.period_end,
        "riskfree_annual": est.riskfree_annual,
        "market_return_observed": est.market_return_observed,
        "market_return_applied": est.market_return_applied,
        "market_return_source": est.market_return_source,
        "market_premium": est.market_premium, "beta": est.beta,
        "beta_stderr": est.beta_stderr, "beta_tstat": est.beta_tstat,
        "beta_r2": est.beta_r2, "alpha": est.alpha,
        "cost_of_equity": est.cost_of_equity,
        "cost_of_equity_raw": est.cost_of_equity_raw,
        "ke_status": est.ke_status, "rf_source": est.rf_source,
        "beta_source": est.beta_source,
        "estimation_period": est.estimation_period,
        "citation": _EST_CITE, "evidence_status": CAPM_EVIDENCE,
        "reference_note": _REFERENCE_NOTE,
    }
    cols = [c.name for c in CAPM_ESTIMATE.columns]
    return cast_to_spec(pd.DataFrame([row])[cols], CAPM_ESTIMATE)


# ---------------------------------------------------------------- 승인 경로

def capm_rate_by_scope(est: CapmEstimate) -> dict[str, tuple[float | None, str]]:
    """회수유형별 (할인율, 산출근거). 낼 수 없는 값은 None이다.

    무위험회수는 R_f만 쓰므로 시장수익률 승인 없이도 산출된다. 전체는 k_e이며
    ``ke_status``가 '산출완료'가 아니면 비어 있다.
    """
    return {
        "무위험회수": (est.riskfree_annual, "무위험이자율"),
        "전체": (est.cost_of_equity, "자기자본비용"),
    }


def apply_capm_discount_rates(rates: pd.DataFrame, est: CapmEstimate, *,
                              asof: str, approved_by: str = CAPM_APPROVER,
                              approval_date: str | None = None
                              ) -> pd.DataFrame:
    """추정 결과를 ``approve_discount_rate``로 원장에 넣은 사본을 돌려준다.

    **승인 절차를 우회하지 않는다.** 값이 원장에 들어가는 경로는 이 함수가 부르는
    ``approve_discount_rate`` 하나뿐이고, 그 함수는 승인자·승인일을 같은 행에
    함께 적는다. 승인일은 ``asof``다. 벽시계 시각을 읽으면 같은 기준일 산출이
    돌릴 때마다 달라진다.

    산출되지 않은 회수유형(k_e가 비어 있는 경우)은 건드리지 않는다. NULL로
    남는 것이 산출물이다.
    """
    out = rates
    approval_date = approval_date or asof
    skipped: list[str] = []
    for scope, (rate, basis) in capm_rate_by_scope(est).items():
        if rate is None:
            skipped.append(scope)
            continue
        segs = sorted(set(out.loc[(out["asof"] == asof)
                                  & (out["recovery_scope"] == scope),
                                  "segment"]))
        for seg in segs:
            out = approve_discount_rate(
                out, asof=asof, segment=seg, recovery_scope=scope,
                rate=float(rate), basis=basis, approved_by=approved_by,
                approval_date=approval_date, rf_source=est.rf_source,
                beta_source=est.beta_source,
                estimation_period=est.estimation_period,
                evidence_status=CAPM_EVIDENCE)
    if skipped:
        warnings.warn(
            f"회수유형 {skipped}의 할인율을 채우지 않았다 "
            f"(ke_status={est.ke_status}). crm_estimation_param의 "
            "capm_market_return이 승인되면 채워진다. 그때까지 해당 세그먼트 "
            "LGD는 산출불가로 남는다", ParamWarning, stacklevel=2)
    if est.ke_status == "산출완료(프리미엄0하한)":
        # 하한이 걸렸다는 것은 승인된 R_M 없이 대체값을 썼다는 뜻이다. 값이
        # 채워졌다는 이유로 조용히 넘어가면 그 사실이 산출물에만 남고 부르는
        # 쪽에는 남지 않는다.
        warnings.warn(
            f"위험프리미엄이 0 이하({est.market_premium:.4%})라 0 하한을 걸어 "
            f"k_e = R_f = {est.cost_of_equity:.4%}로 할인율을 채웠다. 체계적 "
            f"위험분이 빠진 값이며 beta({est.beta:.4f})가 들어가지 않았다. "
            "할인율이 낮으면 회수 현재가치가 커져 LGD가 작아지므로 보수적인 "
            "방향이 아니다. crm_estimation_param의 capm_market_return이 "
            "승인되면 그 값이 하한보다 우선한다", ParamWarning, stacklevel=2)
    return out


def build_capm_discount_ledgers(*, asof: str, seed: int = 42,
                                n_periods: int = N_PERIODS_DEFAULT,
                                segments: tuple[str, ...] | None = None,
                                param: pd.DataFrame | None = None,
                                rates: pd.DataFrame | None = None,
                                master: pd.DataFrame | None = None,
                                approved_by: str = CAPM_APPROVER
                                ) -> dict[str, pd.DataFrame]:
    """관측 → 추정 → 승인 → 할인율 원장까지 한 번에 만든다.

    ``param``에 ``capm_market_return``이 승인돼 있으면 그 값을 R_M으로 쓰고,
    없으면 관측 실현치를 쓴다. 관측 실현 프리미엄이 0 이하라 '전체' 할인율은
    승인 전까지 비어 있고, 그 상태에서 LGD는 지금과 같이 산출불가로 남는다.

    ``rates``를 주면 그 원장에 승인을 얹는다. 주지 않으면 빌더가 만든 원장
    (전건 NULL)에 얹는다.
    """
    obs = build_crm_capm_observation(asof=asof, seed=seed,
                                     n_periods=n_periods, master=master)
    market_return = (None if param is None
                     else param_value(param, "capm_market_return"))
    est = estimate_capm_discount_rate(obs, market_return=market_return)
    if rates is None:
        kwargs = {} if segments is None else {"segments": segments}
        rates = build_crm_lgd_discount_rate(asof, **kwargs,
                                            **est.ledger_annotation())
    rates = apply_capm_discount_rates(rates, est, asof=asof,
                                      approved_by=approved_by)
    return {"crm_capm_observation": obs,
            "crm_capm_estimate": build_crm_capm_estimate(est),
            "crm_lgd_discount_rate": rates}


# ---------------------------------------------------------------- 자체검사
# 검사는 위반을 만들면 실제로 FAIL해야 통제다. 각 함수의 docstring에 "이 검사를
# FAIL시키려면 무엇이 깨져야 하는가"를 적었고 tests/test_discount_capm.py가
# 검사마다 위반을 주입해 확인한다.

_ATOL = 1e-9


def _pass(report, name, detail, metric=0.0):
    report.add(ConsistencyCheck(name, "PASS", detail, metric=float(metric)))


def _fail(report, name, detail, metric):
    report.add(ConsistencyCheck(name, "FAIL", detail, metric=float(metric)))


def _warn(report, name, detail, metric=0.0):
    report.add(ConsistencyCheck(name, "WARN", detail, metric=float(metric)))


def check_capm_recalculation(observation: pd.DataFrame,
                             estimate: pd.DataFrame,
                             report: ValidationReport) -> None:
    """추정 원장의 R_f·beta·k_e를 관측 원장에서 다시 계산해 대조한다 (2선 재계산).

    FAIL 조건: 관측 원장으로 다시 낸 값이 추정 원장의 값과 다를 때. 추정을 돌린
    뒤 관측 원장이 바뀌었거나, 승인 화면이 다른 표본으로 낸 값을 실었거나,
    연율화 배수를 바꾸면 즉시 뜬다. 항등식을 다시 쓴 검사가 아니라 원장 두 장을
    서로 대조하는 검사다.
    """
    if observation.empty or estimate.empty:
        _warn(report, "CAPM 재계산", "관측 또는 추정 원장이 비어 있다")
        return
    row = estimate.iloc[0]
    applied = (None if pd.isna(row["market_return_applied"])
               else float(row["market_return_applied"]))
    redo = estimate_capm_discount_rate(observation, market_return=applied)
    diffs = []
    for col, got in (("riskfree_annual", redo.riskfree_annual),
                     ("market_return_observed", redo.market_return_observed),
                     ("beta", redo.beta), ("beta_stderr", redo.beta_stderr),
                     ("beta_r2", redo.beta_r2),
                     ("cost_of_equity_raw", redo.cost_of_equity_raw)):
        have = row[col]
        if pd.isna(have) and got is None:
            continue
        if pd.isna(have) or got is None or abs(float(have) - got) > _ATOL:
            diffs.append(f"{col}: 원장 {have} 대 재계산 {got}")
    if int(row["n_observations"]) != redo.n_observations:
        diffs.append(f"n_observations: 원장 {row['n_observations']} 대 "
                     f"재계산 {redo.n_observations}")
    if diffs:
        _fail(report, "CAPM 재계산",
              f"관측 원장 재계산과 추정 원장이 다르다: {diffs[:3]}", len(diffs))
        return
    _pass(report, "CAPM 재계산",
          f"관측 {redo.n_observations}개월 재계산으로 R_f·베타·k_e가 원장과 "
          f"일치 (beta {redo.beta:.4f}, R² {redo.beta_r2:.4f})",
          redo.n_observations)


def check_riskfree_scope_below_total(rates: pd.DataFrame,
                                     report: ValidationReport) -> None:
    """무위험회수 할인율이 전체 할인율보다 크지 않은지.

    FAIL 조건: 같은 (기준일, 세그먼트)에서 무위험회수 할인율이 전체 할인율보다
    클 때. k_e = R_f + beta·(R_M − R_f)이므로 beta > 0이고 프리미엄이 양수이면
    항상 성립한다. 프리미엄이 음수인 채로 k_e를 채우거나 두 회수유형에 값을
    바꿔 넣으면 뒤집힌다.
    """
    if rates.empty:
        return
    both = (rates.pivot_table(index=["asof", "segment"],
                              columns="recovery_scope", values="discount_rate")
            .reindex(columns=["무위험회수", "전체"]).dropna())
    if both.empty:
        _warn(report, "CAPM 회수유형 할인율 서열",
              f"두 회수유형에 값이 모두 있는 (기준일, 세그먼트)가 없다. 승인된 "
              f"할인율 {int(rates['discount_rate'].notna().sum())}건")
        return
    bad = both[both["무위험회수"] > both["전체"] + _ATOL]
    if len(bad):
        _fail(report, "CAPM 회수유형 할인율 서열",
              f"무위험회수 할인율이 전체보다 크다 {len(bad)}건: "
              f"{sorted({str(i[1]) for i in bad.index})}", len(bad))
        return
    _pass(report, "CAPM 회수유형 할인율 서열",
          f"{len(both)}건 전건에서 무위험회수 ≤ 전체", len(both))


def check_discount_rate_approved(rates: pd.DataFrame,
                                 report: ValidationReport) -> None:
    """값이 들어간 할인율 행에 승인 기록이 있는지.

    FAIL 조건: ``discount_rate``가 채워졌는데 승인자·승인일이 비었거나 산출근거가
    '미정'일 때. 원장에 값을 직접 대입하는 경로가 생기면 이 검사가 잡는다.
    승인 절차를 우회한 값은 화면에서 승인된 값과 구분되지 않는다.
    """
    if rates.empty:
        return
    filled = rates[rates["discount_rate"].notna()]
    if filled.empty:
        _warn(report, "CAPM 할인율 승인기록",
              "승인된 할인율이 한 건도 없다. LGD는 산출불가로 남는다")
        return
    bad = filled[filled["approved_by"].isna() | filled["approval_date"].isna()
                 | (filled["basis"] == "미정")]
    if len(bad):
        _fail(report, "CAPM 할인율 승인기록",
              f"승인 기록 없이 값이 들어간 행 {len(bad)}건: "
              f"{sorted(set(bad['segment'] + '/' + bad['recovery_scope']))[:5]}",
              len(bad))
        return
    _pass(report, "CAPM 할인율 승인기록",
          f"값이 있는 {len(filled)}건 전건에 승인자·승인일·산출근거가 있다",
          len(filled))


def check_capm_evidence_disclosed(rates: pd.DataFrame,
                                  report: ValidationReport) -> None:
    """합성 관측으로 낸 할인율이 그 사실을 달고 있는지.

    FAIL 조건: 베타 출처에 '합성'이 적힌 행의 ``evidence_status``가
    ``'내부추정(합성관측)'``이 아닐 때. 합성 표본으로 낸 값이 '원문확인'이나
    '2차자료'로 표시되면 화면에서 실측과 구분되지 않는다.
    """
    if rates.empty:
        return
    d = rates[rates["discount_rate"].notna()
              & rates["beta_source"].fillna("").str.contains("합성")]
    if d.empty:
        _warn(report, "CAPM 근거 표시",
              "합성 관측으로 낸 할인율 행이 없다")
        return
    bad = d[d["evidence_status"] != CAPM_EVIDENCE]
    if len(bad):
        _fail(report, "CAPM 근거 표시",
              f"합성 관측 기반인데 근거 상태가 {sorted(set(bad['evidence_status']))}"
              f"로 적힌 행 {len(bad)}건", len(bad))
        return
    _pass(report, "CAPM 근거 표시",
          f"{len(d)}건 전건이 evidence_status='{CAPM_EVIDENCE}'", len(d))


def check_lgd_increases_with_discount_rate(recovery: pd.DataFrame,
                                           rates: pd.DataFrame,
                                           report: ValidationReport, *,
                                           asof: str, bump: float = 0.01
                                           ) -> None:
    """할인율을 올리면 실현 LGD가 올라가는지.

    회수 현가가 줄어들므로 손실률은 커져야 한다. FAIL 조건: 승인된 할인율과
    그보다 ``bump``만큼 높은 할인율의 평균 실현 LGD가 같거나 오히려 낮을 때.
    할인지수의 지수 부호를 뒤집거나(``(1+d)^{+t}``) 경과연수를 0으로 뭉개면
    할인효과가 사라져 이 검사가 잡는다.
    """
    if recovery.empty or rates.empty:
        return
    filled = rates[(rates["asof"] == asof) & rates["discount_rate"].notna()
                   & (rates["recovery_scope"] == "전체")]
    if filled.empty:
        _warn(report, "CAPM 할인율 LGD 민감도",
              "'전체' 회수유형에 승인된 할인율이 없어 민감도를 보지 못했다")
        return
    rate = float(filled["discount_rate"].iloc[0])
    low = realised_lgd(recovery, discount_rate=rate, asof=asof)
    high = realised_lgd(recovery, discount_rate=rate + bump, asof=asof)
    if low.empty or high.empty:
        _warn(report, "CAPM 할인율 LGD 민감도", "회수 관측이 없다")
        return
    a = float(low["lgd_realised"].mean())
    b = float(high["lgd_realised"].mean())
    if b <= a:
        _fail(report, "CAPM 할인율 LGD 민감도",
              f"할인율을 {bump:.2%}p 올렸는데 평균 LGD가 {a:.6f}에서 {b:.6f}로 "
              "커지지 않았다", b - a)
        return
    _pass(report, "CAPM 할인율 LGD 민감도",
          f"할인율 {rate:.4f}→{rate + bump:.4f}에서 평균 LGD "
          f"{a:.6f}→{b:.6f}", b - a)


def run_capm_checks(ledgers: dict[str, pd.DataFrame], *,
                    asof: str | None = None,
                    report: ValidationReport | None = None) -> ValidationReport:
    """CAPM 할인율 원장 묶음에 대한 자체 정합성 검사 일괄 실행."""
    rep = report or ValidationReport()
    obs = ledgers.get("crm_capm_observation", pd.DataFrame())
    est = ledgers.get("crm_capm_estimate", pd.DataFrame())
    rates = ledgers.get("crm_lgd_discount_rate", pd.DataFrame())
    recovery = ledgers.get("crm_recovery_history", pd.DataFrame())
    if asof is None and not rates.empty:
        asof = str(rates["asof"].iloc[0])
    check_capm_recalculation(obs, est, rep)
    check_riskfree_scope_below_total(rates, rep)
    check_discount_rate_approved(rates, rep)
    check_capm_evidence_disclosed(rates, rep)
    if asof is not None:
        check_lgd_increases_with_discount_rate(recovery, rates, rep, asof=asof)
    return rep
