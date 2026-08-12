"""내부등급법 추정 원장 묶음 산출 (IRB-R001).

한 번의 호출로 모수 원장 넉 장, 관측이력 석 장, 추정 결과 다섯 장, 검증·거버넌스
석 장을 만든다. 화면은 이 dict의 프레임만 읽는다.

**결정론.** ``(asof, seed)``가 같으면 결과가 같다. 관측이력은 전용 난수 스트림을
쓰고, 추정은 난수를 쓰지 않는다.

**승인 전 상태가 기본이다.** 내부기준 모수(할인율·MoC 크기·침체기 정의·판정
임계)는 비어 있는 채로 나온다. 그래서 기본 산출물에서 LGD는 ``산출불가``,
MoC는 ``기준미승인``, 사후검증은 미판정이다. 승인된 모수를 넣으려면
``param``·``rates`` 인자로 승인 기록이 들어간 원장을 넘긴다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.models.estimation.ccf_est import estimate_ccf, observed_ccf
from risk_lib.models.estimation.common import ESTIMATION_RUN, MOC_COMPONENT, cast_to_spec
from risk_lib.models.estimation.discount_capm import build_capm_discount_ledgers
from risk_lib.models.estimation.history import build_history_ledgers
from risk_lib.models.estimation.plgd import build_plgd_ledgers
from risk_lib.models.estimation.lgd_est import (
    build_defaulted_lgd, estimate_lgd, identify_downturn_years, realised_lgd,
)
from risk_lib.models.estimation.params import (
    build_estimation_param_ledgers, discount_rate_for,
)
from risk_lib.models.estimation.pd_est import estimate_pd
from risk_lib.models.estimation.validation import (
    build_backtest_result, build_model_governance, build_representativeness,
)

__all__ = ["ESTIMATION_TABLES", "build_irb_estimation_ledgers"]

# 화면·검증이 참조할 테이블 이름 목록. 스펙은 각 모듈이 들고 있다.
ESTIMATION_TABLES: tuple[str, ...] = (
    "crm_input_floor", "crm_irb_scope", "crm_estimation_param",
    "crm_lgd_discount_rate",
    "crm_default_history", "crm_recovery_history",
    "crm_facility_drawdown_history",
    "crm_capm_observation", "crm_capm_estimate",
    "crm_pd_yearly_dr", "crm_pd_estimate", "crm_lgd_estimate",
    "crm_ccf_estimate", "crm_defaulted_lgd",
    "crm_beel_curve", "crm_plgd", "crm_plgd_sensitivity",
    "crm_estimation_run", "crm_moc_component",
    "crm_backtest_result", "crm_representativeness", "crm_model_governance",
)


def build_irb_estimation_ledgers(*, asof: str, seed: int = 42,
                                 years: int = 8,
                                 param: pd.DataFrame | None = None,
                                 rates: pd.DataFrame | None = None,
                                 floors: pd.DataFrame | None = None,
                                 scope: pd.DataFrame | None = None,
                                 history: dict[str, pd.DataFrame] | None = None,
                                 current_portfolio: pd.DataFrame | None = None,
                                 provisions: pd.DataFrame | None = None,
                                 framework_version: str = "바젤3최종안",
                                 pd_method: str = "내부부도경험",
                                 confidence_q: float | None = None,
                                 q_approved_by: str | None = None,
                                 q_approval_date: str | None = None,
                                 ) -> dict[str, pd.DataFrame]:
    """추정 원장 묶음을 만든다.

    ``current_portfolio``를 주지 않으면 가장 최근 코호트를 현재 분포의 대용으로
    쓰고, 대용이라는 사실을 대표성 원장의 근거 문구에 남긴다. 대용을 실제
    포트폴리오라고 적으면 180.의 대표성 입증이 근거 없는 문장이 된다.
    """
    params = build_estimation_param_ledgers(asof)
    if param is not None:
        params["crm_estimation_param"] = param
    if rates is not None:
        params["crm_lgd_discount_rate"] = rates
    if floors is not None:
        params["crm_input_floor"] = floors
    if scope is not None:
        params["crm_irb_scope"] = scope
    p = params["crm_estimation_param"]

    # ---- 회수 할인율 (CAPM) ----
    # 관측 → 추정 → 승인이 한 묶음이다. R_M(capm_market_return)이 승인돼 있으면
    # 자기자본비용이 나오고 '전체' 회수유형 할인율이 그 값으로 채워진다.
    #
    # 승인 전이면 관측 프리미엄이 음수라 0 하한이 걸리고 k_e = R_f 가 두 회수유형
    # 모두에 채워진다 (내부기준). 그래서 승인 전에도 LGD 는 산출된다. 다만 그
    # 할인율에는 체계적 위험분이 없고 하한이 걸렸다는 사실이 ke_status 와
    # ParamWarning 으로 남는다. 할인율이 낮으면 회수 현재가치가 커져 LGD 가
    # 작아지므로 보수적인 방향이 아니다.
    capm = build_capm_discount_ledgers(asof=asof, seed=seed, param=p,
                                       rates=params["crm_lgd_discount_rate"])
    params["crm_lgd_discount_rate"] = capm["crm_lgd_discount_rate"]

    hist = history or build_history_ledgers(asof=asof, seed=seed, years=years)
    dh = hist["crm_default_history"]
    rh = hist["crm_recovery_history"]
    fh = hist["crm_facility_drawdown_history"]

    # ---- 대표성 (180.) ----
    est_years = sorted(set(dh["cohort_year"]))
    latest = est_years[-1] if est_years else None
    current = (current_portfolio if current_portfolio is not None
               else dh[dh["cohort_year"] == latest])
    label = ("현재 포트폴리오" if current_portfolio is not None
             else f"최근 코호트({latest}년, 현재 분포의 대용)")
    rep = build_representativeness(dh, current, asof=asof, param=p,
                                   parameter="PD", axes=("grade",),
                                   current_label=label)
    flagged = {r["segment"]: (r["judgment"] in ("경고", "불합격"))
               for _, r in rep.iterrows() if r["judgment_status"] == "판정완료"}
    flagged = flagged or None

    # ---- PD ----
    pd_out = estimate_pd(dh, floors=params["crm_input_floor"], param=p,
                         asof=asof, seed=seed,
                         framework_version=framework_version,
                         method=pd_method,
                         representativeness_flagged=flagged)
    # ---- LGD ----
    lgd_out = estimate_lgd(rh, dh, floors=params["crm_input_floor"], param=p,
                           rates=params["crm_lgd_discount_rate"], asof=asof,
                           seed=seed, framework_version=framework_version,
                           representativeness_flagged=flagged)
    # ---- CCF ----
    dt_years, _, _ = identify_downturn_years(dh, param=p, asof=asof)
    ccf_out = estimate_ccf(fh, dh, floors=params["crm_input_floor"], param=p,
                           asof=asof, seed=seed,
                           framework_version=framework_version,
                           downturn_years=dt_years,
                           representativeness_flagged=flagged)

    run = cast_to_spec(pd.DataFrame(
        pd_out["run_rows"] + lgd_out["run_rows"] + ccf_out["run_rows"],
        columns=[c.name for c in ESTIMATION_RUN.columns]), ESTIMATION_RUN)
    moc = cast_to_spec(pd.DataFrame(
        pd_out["moc_rows"] + lgd_out["moc_rows"] + ccf_out["moc_rows"],
        columns=[c.name for c in MOC_COMPONENT.columns]), MOC_COMPONENT)

    # ---- 사후검증 (203.) ----
    # 실적은 유보연도에서만 뽑는다. LGD 실적은 승인된 할인율이 있는 세그먼트만
    # 산출되며, 없으면 그 세그먼트는 사후검증 표에서도 빠진다.
    lgd_real = []
    for seg in sorted(set(rh["segment"])) if not rh.empty else []:
        try:
            rate = discount_rate_for(params["crm_lgd_discount_rate"],
                                     asof=asof, segment=seg)
        except KeyError:
            rate = None
        if rate is None:
            continue
        seg_rec = rh[(rh["asof"] == asof) & (rh["segment"] == seg)]
        lgd_real.append(realised_lgd(seg_rec, discount_rate=rate, asof=asof))
    lgd_real_df = (pd.concat(lgd_real, ignore_index=True) if lgd_real
                   else None)
    ccf_obs = observed_ccf(fh, asof=asof) if not fh.empty else None
    if ccf_obs is not None:
        ccf_obs = ccf_obs[ccf_obs["ccf_observed"].notna()]

    backtest = build_backtest_result(
        asof=asof, param=p, yearly_dr=pd_out["crm_pd_yearly_dr"],
        pd_estimate=pd_out["crm_pd_estimate"],
        lgd_realised=lgd_real_df, lgd_estimate=lgd_out["crm_lgd_estimate"],
        ccf_observed=ccf_obs, ccf_estimate=ccf_out["crm_ccf_estimate"])

    # ---- BEEL 곡선 · PLGD (185.바) ----
    # 분모구분은 관측이 판정한다. 할인율이 없으면 곡선이 산출불가 자리행만
    # 남고 PLGD 원장은 빈다. 신뢰수준 q는 승인 없이 들어가지 않는다.
    plgd_led = build_plgd_ledgers(rh, asof=asof,
                                  rates=params["crm_lgd_discount_rate"],
                                  confidence_q=confidence_q,
                                  approved_by=q_approved_by,
                                  approval_date=q_approval_date,
                                  provisions=provisions)
    defaulted = build_defaulted_lgd(rh, lgd_out["crm_lgd_estimate"],
                                    asof=asof, provisions=provisions,
                                    plgd=plgd_led["crm_plgd"])
    governance = build_model_governance(run, asof=asof, param=p)

    out: dict[str, pd.DataFrame] = {}
    out.update(params)
    out.update(hist)
    out["crm_capm_observation"] = capm["crm_capm_observation"]
    out["crm_capm_estimate"] = capm["crm_capm_estimate"]
    out.update(plgd_led)
    out["crm_pd_yearly_dr"] = pd_out["crm_pd_yearly_dr"]
    out["crm_pd_estimate"] = pd_out["crm_pd_estimate"]
    out["crm_lgd_estimate"] = lgd_out["crm_lgd_estimate"]
    out["crm_ccf_estimate"] = ccf_out["crm_ccf_estimate"]
    out["crm_defaulted_lgd"] = defaulted
    out["crm_estimation_run"] = run
    out["crm_moc_component"] = moc
    out["crm_backtest_result"] = backtest
    out["crm_representativeness"] = rep
    out["crm_model_governance"] = governance
    return out
