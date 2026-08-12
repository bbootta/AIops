"""내부등급법 PD·LGD·CCF 추정 ([별표 3] 제5관 제2목~제7목, 202.·203.).

기존 ``risk_lib/models``에는 모형 적합(로지스틱 PD, 릿지 LGD)과 변별력 지표가
있었으나 내부등급법 최소요건을 만족하는 **추정 절차**가 없었다. 이 패키지가
그 절차를 원장 위에 올린다.

  ``params``      하한·적용범위·관측기간·할인율 원장. 규제표는 여기에만 있다
  ``history``     다년 관측이력 원장 (합성, 결정론)
  ``pd_est``      182.·183. 장기평균 PD
  ``lgd_est``     184.~187. 워크아웃 LGD, 경기침체 LGD, 부도자산 LGD
  ``ccf_est``     193.~196. CCF 실측
  ``moc``         181. 보수적 조정을 세 원천으로 나눠 산출
  ``validation``  203. 사후검증, 180. 대표성, 179.나 거버넌스
  ``checks``      자체 정합성 검사 (2선)
  ``run``         원장 묶음 산출

**엔진 함수 본문과 기본값에 규제 수치가 없다.** 하한·관측기간·환산율은 전부
원장에서 읽고, 원장에 값이 없으면 조용히 기본값을 쓰지 않고 경고를 남기며 그
조정을 건너뛴다.
"""

from risk_lib.models.estimation.params import (
    INPUT_FLOOR, IRB_SCOPE, ESTIMATION_PARAM, LGD_DISCOUNT_RATE, PARAM_TABLES,
    ParamWarning,
    build_crm_input_floor, build_crm_irb_scope, build_crm_estimation_param,
    build_crm_lgd_discount_rate, build_estimation_param_ledgers,
    floor_value, param_value, param_text, discount_rate_for,
    approve_estimation_param, approve_discount_rate,
    unapproved_internal_params, assign_irb_method,
)
from risk_lib.models.estimation.history import (
    DEFAULT_HISTORY, RECOVERY_HISTORY, FACILITY_DRAWDOWN_HISTORY,
    HISTORY_TABLES,
    build_crm_default_history, build_crm_recovery_history,
    build_crm_facility_drawdown_history, build_history_ledgers,
)
from risk_lib.models.estimation.common import (
    ESTIMATION_RUN, MOC_COMPONENT, EstimationWarning, PARAMETERS,
    ESTIMATION_BASES, PD_METHODS, RUN_STATUS, run_id,
)
from risk_lib.models.estimation.moc import MocResult, compute_moc
from risk_lib.models.estimation.pd_est import (
    PD_ESTIMATE, PD_YEARLY_DR, build_pd_yearly_dr, estimate_pd,
)
from risk_lib.models.estimation.lgd_est import (
    LGD_ESTIMATE, DEFAULTED_LGD, realised_lgd, identify_downturn_years,
    estimate_lgd, build_defaulted_lgd,
)
from risk_lib.models.estimation.ccf_est import (
    CCF_ESTIMATE, observed_ccf, estimate_ccf,
)
from risk_lib.models.estimation.discount_capm import (
    CAPM_ESTIMATE, CAPM_OBSERVATION, CAPM_TABLES, CapmEstimate,
    build_capm_discount_ledgers, build_crm_capm_estimate,
    build_crm_capm_observation, estimate_capm_discount_rate, run_capm_checks,
)
from risk_lib.models.estimation.plgd import (
    BEEL_CURVE, PLGD, PLGD_SENSITIVITY, PLGD_TABLES,
    build_crm_beel_curve, build_crm_plgd, build_crm_plgd_sensitivity,
    build_plgd_ledgers, decide_beel_denominator, decide_dsf_form,
    run_plgd_checks,
)
from risk_lib.models.estimation.validation import (
    BACKTEST_RESULT, REPRESENTATIVENESS, MODEL_GOVERNANCE,
    build_backtest_result, build_representativeness, build_model_governance,
    record_governance_review, population_psi,
)
from risk_lib.models.estimation.checks import run_irb_estimation_checks
from risk_lib.models.estimation.run import (
    ESTIMATION_TABLES, build_irb_estimation_ledgers,
)

#: 이 패키지가 정의하는 모든 TableSpec. 배선 담당이 카탈로그에 등록할 때 쓴다.
ALL_TABLES = {
    **PARAM_TABLES,
    **HISTORY_TABLES,
    **CAPM_TABLES,
    **PLGD_TABLES,
    PD_YEARLY_DR.name: PD_YEARLY_DR,
    PD_ESTIMATE.name: PD_ESTIMATE,
    LGD_ESTIMATE.name: LGD_ESTIMATE,
    DEFAULTED_LGD.name: DEFAULTED_LGD,
    CCF_ESTIMATE.name: CCF_ESTIMATE,
    ESTIMATION_RUN.name: ESTIMATION_RUN,
    MOC_COMPONENT.name: MOC_COMPONENT,
    BACKTEST_RESULT.name: BACKTEST_RESULT,
    REPRESENTATIVENESS.name: REPRESENTATIVENESS,
    MODEL_GOVERNANCE.name: MODEL_GOVERNANCE,
}

__all__ = [
    "ALL_TABLES", "ESTIMATION_TABLES",
    "INPUT_FLOOR", "IRB_SCOPE", "ESTIMATION_PARAM", "LGD_DISCOUNT_RATE",
    "PARAM_TABLES", "ParamWarning",
    "build_crm_input_floor", "build_crm_irb_scope",
    "build_crm_estimation_param", "build_crm_lgd_discount_rate",
    "build_estimation_param_ledgers",
    "floor_value", "param_value", "param_text", "discount_rate_for",
    "approve_estimation_param", "approve_discount_rate",
    "unapproved_internal_params", "assign_irb_method",
    "DEFAULT_HISTORY", "RECOVERY_HISTORY", "FACILITY_DRAWDOWN_HISTORY",
    "HISTORY_TABLES", "build_crm_default_history",
    "build_crm_recovery_history", "build_crm_facility_drawdown_history",
    "build_history_ledgers",
    "ESTIMATION_RUN", "MOC_COMPONENT", "EstimationWarning", "PARAMETERS",
    "ESTIMATION_BASES", "PD_METHODS", "RUN_STATUS", "run_id",
    "MocResult", "compute_moc",
    "PD_ESTIMATE", "PD_YEARLY_DR", "build_pd_yearly_dr", "estimate_pd",
    "LGD_ESTIMATE", "DEFAULTED_LGD", "realised_lgd",
    "identify_downturn_years", "estimate_lgd", "build_defaulted_lgd",
    "CCF_ESTIMATE", "observed_ccf", "estimate_ccf",
    "CAPM_OBSERVATION", "CAPM_ESTIMATE", "CAPM_TABLES", "CapmEstimate",
    "build_crm_capm_observation", "estimate_capm_discount_rate",
    "build_crm_capm_estimate", "build_capm_discount_ledgers",
    "run_capm_checks",
    "BEEL_CURVE", "PLGD", "PLGD_SENSITIVITY", "PLGD_TABLES",
    "build_crm_beel_curve", "build_crm_plgd", "build_crm_plgd_sensitivity",
    "build_plgd_ledgers", "decide_beel_denominator", "decide_dsf_form",
    "run_plgd_checks",
    "BACKTEST_RESULT", "REPRESENTATIVENESS", "MODEL_GOVERNANCE",
    "build_backtest_result", "build_representativeness",
    "build_model_governance", "record_governance_review", "population_psi",
    "run_irb_estimation_checks", "build_irb_estimation_ledgers",
]
