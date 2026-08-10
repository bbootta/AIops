"""PD 추정 ([별표 3] 182.·183., 하한 123.·131.).

**연도동일가중 단순평균이 기본이다.** 바젤Ⅲ 최종안 182.바 신설 문언은
"은행은 PD 추정시 등급별 1년 부도율의 차주수 기준 단순평균으로 산출하여야
한다"이다. 이 표현은 두 층을 동시에 지정한다. 연도 안에서는 익스포저 금액이
아니라 차주 수로 1년 부도율을 내고, 연도 사이에서는 단순평균한다.

**대조값을 함께 낸다.** 전 기간 풀링(차주수 가중평균)은 침체기에 코호트가
줄어드는 신용사이클에서 침체 효과를 희석시켜 부도율을 과소평가한다. 조문
문언만으로는 두 해석이 갈리므로 두 값을 모두 계산하고 차이를 원장에 남긴다.
적용치는 단순평균이다.

**부도가중평균은 PD에 쓰지 않는다.** 부도가중은 LGD(185.가(1))와 EAD(195.다)의
요건이다. PD에 부도가중을 쓰면 침체기 부도율로 수렴하고, 위험가중함수가 이미
조건부 부도율로 미예상손실을 계산하는 구조와 이중계상이 된다.

**표본이 작은 등급에 MoC가 더 크게 붙는다.** 통계적 MoC가 연도별 부도율의
표본평균 신뢰상한에서 나오므로 코호트가 작아 부도율이 흔들리는 등급일수록
구간이 넓어진다. 크기 모수를 손으로 등급마다 다르게 적을 필요가 없다.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.models.estimation.common import (
    EstimationWarning, PD_METHODS, cast_to_spec, min_years_param_code, run_id,
)
from risk_lib.models.estimation.moc import compute_moc, moc_component_rows
from risk_lib.models.estimation.params import (
    ParamWarning, floor_value, param_value,
)

__all__ = ["PD_YEARLY_DR", "PD_ESTIMATE", "build_pd_yearly_dr", "estimate_pd"]


PD_YEARLY_DR = TableSpec(
    name="crm_pd_yearly_dr", korean="등급별 연도 부도율", product="PRD-RWA",
    grain="기준일 × 세그먼트 × 등급 × 관측연도 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("grade", "string", "등급 또는 자산군", nullable=False),
        C("cohort_year", "int", "관측연도", nullable=False,
          min_value=1900, max_value=2200),
        C("n_obligors", "int", "코호트 차주수", nullable=False, min_value=0),
        C("n_defaults", "int", "부도 차주수", nullable=False, min_value=0),
        C("default_rate", "float", "1년 부도율", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 3] 182.바 차주수 기준"),
        C("exposure_amount", "float", "코호트 익스포저", nullable=False,
          unit="KRW", min_value=0.0),
        C("cycle_phase", "string", "경기 국면", nullable=False),
        C("in_estimation_sample", "bool", "추정 표본 포함", nullable=False,
          note="False면 사후검증용으로 유보한 연도다. 표본외 검증(203.)의 전제"),
    ),
    primary_key=("asof", "segment", "grade", "cohort_year"),
    note="장기평균 PD의 근거가 되는 연도별 값. 이 표가 없으면 평균 한 칸이 "
         "어디서 나왔는지 확인할 수 없다.",
)

PD_ESTIMATE = TableSpec(
    name="crm_pd_estimate", korean="PD 추정치", product="PRD-RWA",
    grain="기준일 × 세그먼트 × 등급 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("grade", "string", "등급 또는 자산군", nullable=False),
        C("run_id", "string", "산출 식별자", nullable=False),
        C("exposure_class", "string", "자산군", nullable=False),
        C("estimation_method", "string", "추정방법", nullable=False,
          allowed=PD_METHODS, citation="[별표 3] 182.가"),
        C("estimation_basis", "string", "평균 기준", nullable=False,
          citation="[별표 3] 182.바"),
        C("observation_years", "float", "관측기간", nullable=False,
          unit="years", min_value=0.0),
        C("n_obligors", "int", "관측 차주수(연 합계)", nullable=False,
          min_value=0),
        C("n_defaults", "int", "관측 부도수(연 합계)", nullable=False,
          min_value=0),
        C("raw_estimate", "float", "원시추정치", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="연도별 1년 부도율의 단순평균 (182.바)"),
        C("alt_obligor_weighted", "float", "차주수가중 대조값", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="전 기간 풀링. 적용치가 아니라 해석 차이를 보이는 대조값이다"),
        C("basis_gap", "float", "두 기준의 차", nullable=True, unit="ratio",
          note="단순평균 − 차주수가중. 양수면 풀링이 침체 효과를 희석했다는 뜻"),
        C("floor_value", "float", "하한", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation="[별표 3] 123.·131."),
        C("floor_status", "string", "하한 상태", nullable=False),
        C("after_floor", "float", "하한 적용 후", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("floor_binding", "bool", "하한이 물었나", nullable=True),
        C("seasoning_addon", "float", "기간경과효과 가산", nullable=True,
          unit="ratio", citation="[별표 3] 183.라"),
        C("moc_amount", "float", "MoC", nullable=True, unit="ratio",
          citation="[별표 3] 181."),
        C("moc_status", "string", "MoC 상태", nullable=False),
        C("after_moc", "float", "MoC 적용 후", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("final_applied", "float", "최종 적용치", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("exposure_amount", "float", "관측 익스포저", nullable=False,
          unit="KRW", min_value=0.0),
        C("status", "string", "상태", nullable=False),
    ),
    primary_key=("asof", "segment", "grade"),
    foreign_keys=(),
    note="원시추정 → 하한 → MoC → 최종을 각각 컬럼으로 둔다. 최종치 한 칸만 "
         "있으면 그 값이 추정에서 나왔는지 하한에서 나왔는지 알 수 없다.",
)

_BASIS = "장기평균(연도동일가중)"


def build_pd_yearly_dr(history: pd.DataFrame, *, asof: str,
                       holdout_year: int | None = None) -> pd.DataFrame:
    """등급별·연도별 1년 부도율 원장.

    부도율의 분자·분모는 차주 수다(182.바). 금액 기준으로 세면 대형 차주 한
    건의 부도가 등급 부도율을 지배한다.
    """
    need = {"asof", "cohort_year", "segment", "grade", "default_flag",
            "exposure_amount", "cycle_phase"}
    missing = need - set(history.columns)
    if missing:
        raise ValueError(f"crm_default_history에 없는 컬럼: {sorted(missing)}")
    h = history[history["asof"] == asof]
    g = h.groupby(["segment", "grade", "cohort_year"], as_index=False).agg(
        n_obligors=("default_flag", "size"),
        n_defaults=("default_flag", "sum"),
        exposure_amount=("exposure_amount", "sum"),
        cycle_phase=("cycle_phase", "first"))
    g["asof"] = asof
    g["default_rate"] = np.where(g["n_obligors"] > 0,
                                 g["n_defaults"] / g["n_obligors"], np.nan)
    g["in_estimation_sample"] = (True if holdout_year is None
                                 else g["cohort_year"] != holdout_year)
    return cast_to_spec(g[[c.name for c in PD_YEARLY_DR.columns]], PD_YEARLY_DR)


def estimate_pd(history: pd.DataFrame, *, floors: pd.DataFrame,
                param: pd.DataFrame, asof: str, seed: int = 42,
                framework_version: str = "바젤3최종안",
                method: str = "내부부도경험",
                holdout_last_year: bool = True,
                representativeness_flagged: dict[str, bool] | None = None,
                ) -> dict[str, object]:
    """등급별 장기평균 PD를 추정한다.

    ``holdout_last_year``가 참이면 마지막 관측연도를 추정 표본에서 빼고
    사후검증용으로 남긴다. 추정에 쓴 해로 사후검증을 하면 표본내 검증이 되어
    203.가의 '실제 부도율이 예상 부도율 범위 내'가 자동으로 성립한다.

    반환은 ``{'crm_pd_yearly_dr', 'crm_pd_estimate', 'run_rows',
    'moc_rows', 'warnings'}``이다. 산출이력 행은 ``run.py``가 모아 한 장으로
    만든다.
    """
    if method not in PD_METHODS:
        raise ValueError(f"method는 {PD_METHODS} 중 하나여야 한다")
    years = sorted(set(history.loc[history["asof"] == asof, "cohort_year"]))
    holdout = int(years[-1]) if (holdout_last_year and years) else None
    yearly = build_pd_yearly_dr(history, asof=asof, holdout_year=holdout)
    sample = yearly[yearly["in_estimation_sample"]]

    est_rows: list[dict] = []
    run_rows: list[dict] = []
    moc_rows: list[dict] = []
    notes: list[str] = []

    for segment, seg_df in sample.groupby("segment"):
        min_code = min_years_param_code("PD", str(segment))
        min_years = param_value(param, min_code)
        if min_years is None:
            notes.append(f"{segment}: {min_code} 미확인. 최소요건을 판정하지 않는다")
        seg_years = sorted(set(seg_df["cohort_year"]))
        obs_years = float(len(seg_years))
        meets = None if min_years is None else bool(obs_years >= min_years)
        try:
            fl, fl_status = floor_value(
                floors, parameter="pd_floor", exposure_class=str(segment),
                framework_version=framework_version)
        except KeyError:
            fl, fl_status = None, "미확인"
            notes.append(f"{segment}: crm_input_floor에 pd_floor 행이 없다")
        if fl is None:
            warnings.warn(
                f"PD 하한이 비어 있다 (segment={segment}, status={fl_status}). "
                "하한을 적용하지 않고 그 사실을 산출 결과에 싣는다",
                ParamWarning, stacklevel=2)

        seasoning = param_value(param, "pd_seasoning_addon_retail")
        seasoning_applies = segment in ("retail_other", "residential_mortgage")
        if seasoning_applies and seasoning is None:
            notes.append(
                f"{segment}: 183.라 기간경과효과 보수적 마진이 승인 전이라 "
                "가산하지 않았다")

        n_binding = 0
        amt_binding = 0.0
        moc_statuses: list[str] = []
        unresolved_all: set[str] = set()
        last_moc = None
        for grade, gdf in seg_df.groupby("grade"):
            gdf = gdf.sort_values("cohort_year")
            dr = gdf["default_rate"].to_numpy(dtype=float)
            n_obl = int(gdf["n_obligors"].sum())
            n_def = int(gdf["n_defaults"].sum())
            raw = float(np.nanmean(dr)) if len(dr) else float("nan")
            pooled = float(n_def / n_obl) if n_obl else float("nan")
            after_floor = raw if fl is None else float(max(raw, fl))
            binding = None if fl is None else bool(fl > raw)

            flagged = (None if representativeness_flagged is None
                       else bool(representativeness_flagged.get(str(segment))))
            moc = compute_moc(param=param, point_estimate=after_floor,
                              yearly_estimates=dr,
                              representativeness_flagged=flagged)
            moc_statuses.append(moc.status)
            unresolved_all.update(moc.unresolved)
            last_moc = moc
            moc_rows.extend(moc_component_rows(
                moc, asof=asof, parameter="PD", segment=str(segment),
                grade=str(grade), point_estimate=after_floor))

            add = 0.0
            if seasoning_applies and seasoning is not None:
                add = float(seasoning * after_floor)
            after_moc = after_floor + add + (moc.total or 0.0)
            final = after_moc if fl is None else float(max(after_moc, fl))
            final = float(min(final, 1.0))
            if binding:
                n_binding += 1
                amt_binding += float(gdf["exposure_amount"].sum())

            est_rows.append({
                "asof": asof, "segment": segment, "grade": grade,
                "run_id": run_id(asof=asof, parameter="PD",
                                 segment=str(segment), seed=seed),
                "exposure_class": segment,
                "estimation_method": method, "estimation_basis": _BASIS,
                "observation_years": obs_years,
                "n_obligors": n_obl, "n_defaults": n_def,
                "raw_estimate": raw, "alt_obligor_weighted": pooled,
                "basis_gap": raw - pooled,
                "floor_value": fl, "floor_status": fl_status,
                "after_floor": after_floor, "floor_binding": binding,
                "seasoning_addon": (add if seasoning_applies else None),
                "moc_amount": moc.total, "moc_status": moc.status,
                "after_moc": after_moc, "final_applied": final,
                "exposure_amount": float(gdf["exposure_amount"].sum()),
                "status": ("산출완료" if meets in (True, None)
                           else "산출완료(요건미충족)"),
            })

        unresolved = sorted(unresolved_all)
        if fl is None:
            unresolved.append("pd_floor")
        if seasoning_applies and seasoning is None:
            unresolved.append("pd_seasoning_addon_retail")
        run_rows.append({
            "asof": asof, "parameter": "PD", "segment": segment,
            "run_id": run_id(asof=asof, parameter="PD", segment=str(segment),
                             seed=seed),
            "exposure_class": segment,
            "method": f"[별표 3] 182.가 {method}",
            "estimation_basis": _BASIS,
            "observation_start": f"{seg_years[0]:04d}-01-01",
            "observation_end": f"{seg_years[-1]:04d}-12-31",
            "observation_years": obs_years,
            "min_observation_years": min_years,
            "meets_minimum": meets,
            "n_obligors": int(seg_df["n_obligors"].sum()),
            "n_defaults": int(seg_df["n_defaults"].sum()),
            "n_observations": int(seg_df["n_obligors"].sum()),
            "n_censored": None,
            "estimation_window_end": int(seg_years[-1]),
            "holdout_year": holdout,
            "moc_amount": None,
            "moc_status": ("기준미승인" if all(s == "기준미승인"
                                          for s in moc_statuses)
                           else ("산출완료" if all(s == "산출완료"
                                               for s in moc_statuses)
                                 else "부분산출")),
            "moc_rationale": last_moc.rationale if last_moc else None,
            "moc_aggregation": last_moc.aggregation if last_moc else None,
            "floor_applied": fl is not None,
            "n_floor_binding": n_binding,
            "amount_floor_binding": amt_binding,
            "default_definition": (
                history.loc[history["segment"] == segment,
                            "default_definition"].iloc[0]
                if "default_definition" in history.columns else None),
            "definition_adjustment": (
                "합성 이력이며 부도정의가 다른 외부 데이터를 결합하지 않았다. "
                "178.의 조정 대상이 없다"),
            "population_alignment": None,
            "last_review_date": None, "next_review_due": None,
            "review_interval_months": param_value(param,
                                                  "review_interval_months"),
            "unresolved_inputs": ("; ".join(sorted(set(unresolved)))
                                  if unresolved else None),
            "status": ("산출완료" if meets in (True, None)
                       else "산출완료(요건미충족)"),
            "framework_version": framework_version,
            "seed": seed, "source_system": "synthetic",
        })

    est = cast_to_spec(pd.DataFrame(est_rows, columns=[
        c.name for c in PD_ESTIMATE.columns]), PD_ESTIMATE)
    return {"crm_pd_yearly_dr": yearly, "crm_pd_estimate": est,
            "run_rows": run_rows, "moc_rows": moc_rows, "warnings": notes}
