"""CCF·EAD 추정 ([별표 3] 193.~196., 하한은 표준방법 CCF의 50%).

    CCF 실측 = (부도시 인출액 − 기준시 인출액) / 기준시 미인출액

**하한은 상수 20%가 아니다.** 최종안은 자체추정 신용환산율에 "표준방법 적용
신용환산율의 50%"를 하한으로 건다. 20%는 미인출 약정 40% 버킷에 배수를 곱한
결과값이다. 20%를 상수로 박으면 취소가능 약정(표준방법 10%)에 네 배 과대한
하한이, 단기 무역관련(20%)에 두 배 과대한 하한이 걸린다. 그래서 하한은
``표준방법 CCF × 원장의 배수``로 계산하는 파생값이고, 원장에는 배수가 있다.

**분모가 0이거나 음수인 건을 조용히 잘라내지 않는다.** 기준시점에 한도가 이미
소진된 건(미인출 0)과 부도 전에 한도가 축소되어 인출액이 한도를 넘은 건(미인출
음수)은 CCF가 정의되지 않는다. 그런데 이 건들은 신용상태가 이미 나빠진 건에
몰려 있어 잘라내면 표본이 좋은 쪽으로 치우친다. 산출에서 빼되 건수와 금액을
원장에 남긴다.

**관측설계는 데이터의 성질이다.** 코호트 설계는 기준일과 부도 사이 평균 거리가
6개월 수준이라 12개월 시계보다 추가인출을 덜 관측하고, 고정시계 설계는 취급 후
12개월 안에 부도한 건을 표본에서 놓친다. 어느 설계로 뽑은 표본인지를 관측이력
원장이 들고 있고 이 모듈은 그것을 읽어 산출이력에 옮긴다.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from risk_lib.capital.crm import CCF_BUCKETS
from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.models.estimation.common import (
    cast_to_spec, min_years_param_code, run_id,
)
from risk_lib.models.estimation.moc import compute_moc, moc_component_rows
from risk_lib.models.estimation.params import (
    ParamWarning, floor_value, param_value,
)

__all__ = ["CCF_ESTIMATE", "observed_ccf", "estimate_ccf"]

_BASIS = "부도가중평균"


CCF_ESTIMATE = TableSpec(
    name="crm_ccf_estimate", korean="CCF 추정치", product="PRD-RWA",
    grain="기준일 × 세그먼트 × 신용환산 구분 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("ccf_type", "string", "신용환산 구분", nullable=False),
        C("run_id", "string", "산출 식별자", nullable=False),
        C("exposure_class", "string", "자산군", nullable=False),
        C("observation_design", "string", "관측설계", nullable=False,
          note="코호트와 고정시계는 기준시점이 달라 CCF 수준이 다르다"),
        C("estimation_basis", "string", "평균 기준", nullable=False,
          citation="[별표 3] 195.다 부도 가중평균"),
        C("observation_years", "float", "관측기간", nullable=True,
          unit="years", min_value=0.0),
        C("n_facilities", "int", "한도거래 건수", nullable=False, min_value=0),
        C("n_valid", "int", "산출 가능 건수", nullable=False, min_value=0),
        C("n_zero_denominator", "int", "분모 0 건수", nullable=False,
          min_value=0, note="기준시점 한도 소진"),
        C("n_negative_denominator", "int", "분모 음수 건수", nullable=False,
          min_value=0, note="기준시점 이후 한도 축소"),
        C("excluded_exposure_amount", "float", "제외 건의 기준시 인출액 합계",
          nullable=True, unit="KRW", min_value=0.0,
          note="제외된 표본의 크기를 인출액으로 잰다. 미인출액으로 재면 분모 0인 "
               "건이 0으로, 분모 음수인 건이 음수로 잡혀 합계가 제외 규모를 "
               "나타내지 못한다"),
        C("n_ccf_below_zero", "int", "실측 CCF 음수 건수", nullable=False,
          min_value=0, note="부도 전에 상환한 건. 절사는 내부기준이라 하지 않았다"),
        C("n_ccf_above_one", "int", "실측 CCF 1 초과 건수", nullable=False,
          min_value=0, note="한도 증액. 절사는 내부기준이라 하지 않았다"),
        C("raw_estimate", "float", "원시추정치", nullable=True, unit="ratio",
          note="부도건별 실측 CCF의 부도가중평균. 절사하지 않은 값이다"),
        C("downturn_ccf", "float", "경기침체 CCF", nullable=True, unit="ratio",
          citation="[별표 3] 193.다(4)"),
        C("downturn_applied", "bool", "침체치 적용", nullable=True,
          note="193.다(4)는 '경기순환주기에 걸쳐 변동성이 큰 익스포져'에 침체치를 "
               "쓰라고 하나 변동성 판정 기준을 주지 않는다. 미판정으로 둔다"),
        C("sa_ccf", "float", "표준방법 신용환산율", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("floor_multiplier", "float", "하한 배수", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("floor_value", "float", "하한", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="표준방법 CCF × 하한 배수. 상수가 아니라 파생값이다"),
        C("floor_status", "string", "하한 상태", nullable=False),
        C("after_floor", "float", "하한 적용 후", nullable=True, unit="ratio"),
        C("floor_binding", "bool", "하한이 물었나", nullable=True),
        C("moc_amount", "float", "MoC", nullable=True, unit="ratio",
          citation="[별표 3] 181. · 193.다(2)"),
        C("moc_status", "string", "MoC 상태", nullable=False),
        C("after_moc", "float", "MoC 적용 후", nullable=True, unit="ratio"),
        C("final_applied", "float", "최종 적용치", nullable=True, unit="ratio"),
        C("pd_ead_correlation", "float", "부도율·CCF 상관", nullable=True,
          unit="ratio", min_value=-1.0, max_value=1.0,
          citation="[별표 3] 193.다(3)"),
        C("extra_conservatism_required", "bool", "추가 보수화 필요",
          nullable=True, citation="[별표 3] 193.다(3)"),
        C("extra_conservatism_amount", "float", "추가 보수화 폭", nullable=True,
          unit="ratio",
          note="193.다(3)은 추가 보수화를 요구하되 크기를 주지 않는다. "
               "승인된 내부기준이 없으면 비워 둔다"),
        C("post_default_drawdown_treatment", "string", "부도후 추가인출 반영처",
          nullable=True, citation="[별표 3] 193.나(1)"),
        C("self_estimation_allowed", "bool", "자체추정 가능", nullable=False),
        C("status", "string", "상태", nullable=False),
    ),
    primary_key=("asof", "segment", "ccf_type"),
    note="난내항목은 현재 인출액이 하한이다(193.가). 이 원장은 난외 미인출 "
         "약정의 환산율만 담고, 인출액 하한은 EAD 산출 단계에서 건다.",
)


def observed_ccf(facility: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """한도거래별 실측 CCF와 제외 사유.

    분모가 0 이하인 건은 ``ccf_observed``가 NaN이고 ``exclusion_reason``이
    이유를 적는다. 행 자체를 빼면 제외 건수가 집계에서 사라진다.
    """
    need = {"facility_id", "segment", "ccf_type", "drawn_at_reference",
            "undrawn_at_reference", "drawn_at_default", "default_year"}
    missing = need - set(facility.columns)
    if missing:
        raise ValueError(
            f"crm_facility_drawdown_history에 없는 컬럼: {sorted(missing)}")
    f = facility[facility["asof"] == asof].copy()
    if f.empty:
        f["ccf_observed"] = pd.Series(dtype=float)
        f["exclusion_reason"] = pd.Series(dtype=object)
        return f
    denom = pd.to_numeric(f["undrawn_at_reference"], errors="coerce")
    numer = (pd.to_numeric(f["drawn_at_default"], errors="coerce")
             - pd.to_numeric(f["drawn_at_reference"], errors="coerce"))
    reason = np.where(denom == 0, "분모0(기준시 한도소진)",
                      np.where(denom < 0, "분모음수(기준시 이후 한도축소)", None))
    f["ccf_observed"] = np.where(denom > 0, numer / denom.replace(0, np.nan),
                                 np.nan)
    f["exclusion_reason"] = reason
    return f


def _multiplier(floors: pd.DataFrame, segment: str,
                framework_version: str) -> tuple[float | None, str]:
    """세그먼트별 하한 배수. 세그먼트 전용 행이 없으면 'all' 행을 쓴다."""
    for cls in (segment, "all"):
        try:
            return floor_value(floors, parameter="ccf_floor_multiplier",
                               exposure_class=cls,
                               framework_version=framework_version)
        except KeyError:
            continue
    return None, "미확인"


def estimate_ccf(facility: pd.DataFrame, default_history: pd.DataFrame, *,
                 floors: pd.DataFrame, param: pd.DataFrame, asof: str,
                 seed: int = 42, framework_version: str = "바젤3최종안",
                 downturn_years: list[int] | None = None,
                 sa_ccf: dict[str, float] | None = None,
                 representativeness_flagged: dict[str, bool] | None = None,
                 ) -> dict[str, object]:
    """세그먼트 × 신용환산 구분별 CCF를 추정한다.

    ``sa_ccf``를 주지 않으면 ``risk_lib.capital.crm.CCF_BUCKETS``를 읽는다.
    표준방법 환산율표를 이 모듈에 다시 적지 않는다. 규제표가 두 벌이 되면
    언젠가 갈라진다.
    """
    rates = dict(CCF_BUCKETS) if sa_ccf is None else dict(sa_ccf)
    obs = observed_ccf(facility, asof=asof)
    est_rows: list[dict] = []
    run_rows: list[dict] = []
    moc_rows: list[dict] = []
    notes: list[str] = []
    if obs.empty:
        return {"crm_ccf_estimate": cast_to_spec(
            pd.DataFrame(columns=[c.name for c in CCF_ESTIMATE.columns]),
            CCF_ESTIMATE), "run_rows": [], "moc_rows": [], "warnings": notes}

    # 193.다(3) 부도율·EAD 상관. 연도별 포트폴리오 부도율과 연도별 평균 실측
    # CCF의 상관을 본다. 양이면 추가 보수화 요건이 걸린다.
    dh = default_history[default_history["asof"] == asof]
    yearly_dr = dh.groupby("cohort_year")["default_flag"].mean()

    for (segment, ctype), grp in obs.groupby(["segment", "ccf_type"]):
        rid = run_id(asof=asof, parameter="CCF", segment=str(segment),
                     seed=seed)
        valid = grp[grp["ccf_observed"].notna()]
        n_valid = int(len(valid))
        n_zero = int((grp["exclusion_reason"] == "분모0(기준시 한도소진)").sum())
        n_neg = int((grp["exclusion_reason"]
                     == "분모음수(기준시 이후 한도축소)").sum())
        excl_amt = float(pd.to_numeric(
            grp.loc[grp["ccf_observed"].isna(), "drawn_at_reference"],
            errors="coerce").sum())
        years = sorted(set(pd.to_numeric(grp["default_year"])))
        obs_years = float(len(years))
        min_code = min_years_param_code("CCF", str(segment))
        min_years = param_value(param, min_code)
        meets = None if min_years is None else bool(obs_years >= min_years)

        raw = float(valid["ccf_observed"].mean()) if n_valid else None
        yearly_ccf = (valid.groupby("default_year")["ccf_observed"].mean()
                      if n_valid else pd.Series(dtype=float))
        downturn = None
        if downturn_years and n_valid:
            dsub = valid[valid["default_year"].isin(downturn_years)]
            if len(dsub):
                downturn = float(dsub["ccf_observed"].mean())

        corr = None
        if len(yearly_ccf) >= 3:
            joined = pd.concat([yearly_ccf.rename("ccf"),
                                yearly_dr.rename("dr")], axis=1).dropna()
            if len(joined) >= 3 and joined["ccf"].std() > 0 \
                    and joined["dr"].std() > 0:
                corr = float(joined["ccf"].corr(joined["dr"]))

        sa = rates.get(str(ctype))
        if sa is None:
            notes.append(f"{ctype}: 표준방법 신용환산율을 찾지 못했다")
        mult, fl_status = _multiplier(floors, str(segment), framework_version)
        fl = None if (sa is None or mult is None) else float(sa * mult)
        if fl is None:
            warnings.warn(
                f"CCF 하한을 계산할 수 없다 (segment={segment}, type={ctype}, "
                f"status={fl_status}). 하한을 적용하지 않고 그 사실을 산출 "
                "결과에 싣는다", ParamWarning, stacklevel=2)
        # 표준방법 100% 적용대상은 자체추정 대상이 아니다. 하한을 걸 것이 아니라
        # 표준방법 값을 그대로 쓴다.
        self_ok = not (sa is not None and sa >= 1.0)

        after_floor = raw
        binding = None
        if raw is not None and fl is not None:
            after_floor = float(max(raw, fl))
            binding = bool(fl > raw)

        unresolved: list[str] = []
        if fl is None:
            unresolved.append("ccf_floor_multiplier")
        moc = None
        after_moc = after_floor
        if after_floor is not None:
            flagged = (None if representativeness_flagged is None
                       else bool(representativeness_flagged.get(str(segment))))
            moc = compute_moc(param=param, point_estimate=after_floor,
                              yearly_estimates=yearly_ccf.to_numpy(),
                              representativeness_flagged=flagged)
            unresolved.extend(moc.unresolved)
            moc_rows.extend(moc_component_rows(
                moc, asof=asof, parameter="CCF", segment=str(segment),
                grade=str(ctype), point_estimate=after_floor))
            after_moc = float(after_floor + (moc.total or 0.0))
        final = None
        if not self_ok:
            final = float(sa)
        elif after_moc is not None:
            final = after_moc if fl is None else float(max(after_moc, fl))

        est_rows.append({
            "asof": asof, "segment": segment, "ccf_type": ctype,
            "run_id": rid, "exposure_class": segment,
            "observation_design": str(grp["observation_design"].iloc[0]),
            "estimation_basis": _BASIS, "observation_years": obs_years,
            "n_facilities": int(len(grp)), "n_valid": n_valid,
            "n_zero_denominator": n_zero, "n_negative_denominator": n_neg,
            "excluded_exposure_amount": excl_amt,
            "n_ccf_below_zero": int((valid["ccf_observed"] < 0).sum()),
            "n_ccf_above_one": int((valid["ccf_observed"] > 1).sum()),
            "raw_estimate": raw, "downturn_ccf": downturn,
            "downturn_applied": None,
            "sa_ccf": sa, "floor_multiplier": mult, "floor_value": fl,
            "floor_status": fl_status, "after_floor": after_floor,
            "floor_binding": binding,
            "moc_amount": (moc.total if moc else None),
            "moc_status": (moc.status if moc else "해당없음"),
            "after_moc": after_moc, "final_applied": final,
            "pd_ead_correlation": corr,
            "extra_conservatism_required": (None if corr is None
                                            else bool(corr > 0)),
            "extra_conservatism_amount": None,
            "post_default_drawdown_treatment": (
                str(grp["post_default_drawdown_treatment"].iloc[0])
                if "post_default_drawdown_treatment" in grp.columns else None),
            "self_estimation_allowed": self_ok,
            "status": ("자체추정불가(표준방법100%)" if not self_ok
                       else ("산출완료" if meets in (True, None)
                             else "산출완료(요건미충족)")),
        })

        run_rows.append({
            "asof": asof, "parameter": "CCF", "segment": f"{segment}/{ctype}",
            "run_id": f"{rid}_{ctype}", "exposure_class": segment,
            "method": ("[별표 3] 193. 실측 CCF = (부도시 인출액 − 기준시 "
                       "인출액) / 기준시 미인출액"),
            "estimation_basis": _BASIS,
            "observation_start": (f"{years[0]:04d}-01-01" if years else None),
            "observation_end": (f"{years[-1]:04d}-12-31" if years else None),
            "observation_years": obs_years,
            "min_observation_years": min_years, "meets_minimum": meets,
            "n_obligors": None, "n_defaults": int(len(grp)),
            "n_observations": n_valid, "n_censored": n_zero + n_neg,
            "estimation_window_end": (int(years[-1]) if years else None),
            "holdout_year": None,
            "moc_amount": (moc.total if moc else None),
            "moc_status": (moc.status if moc else "해당없음"),
            "moc_rationale": (moc.rationale if moc else None),
            "moc_aggregation": (moc.aggregation if moc else None),
            "floor_applied": fl is not None,
            "n_floor_binding": (1 if binding else 0),
            "amount_floor_binding": None,
            "default_definition": None,
            "definition_adjustment": None,
            "population_alignment": None,
            "last_review_date": None, "next_review_due": None,
            "review_interval_months": param_value(param,
                                                  "review_interval_months"),
            "unresolved_inputs": ("; ".join(sorted(set(unresolved)))
                                  if unresolved else None),
            "status": ("자체추정불가(표준방법100%)" if not self_ok
                       else ("산출완료" if meets in (True, None)
                             else "산출완료(요건미충족)")),
            "framework_version": framework_version, "seed": seed,
            "source_system": "synthetic",
        })

    est = cast_to_spec(pd.DataFrame(est_rows, columns=[
        c.name for c in CCF_ESTIMATE.columns]), CCF_ESTIMATE)
    return {"crm_ccf_estimate": est, "run_rows": run_rows,
            "moc_rows": moc_rows, "warnings": notes}
