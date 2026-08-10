"""LGD 추정 ([별표 3] 184.~187., 하한 132.가).

**손실은 회계손실이 아니라 경제적 손실이다**(184.). 세 구성요소가 조문에 그대로
대응한다. 회수기간에 따른 할인효과, 회수 관련 직·간접 비용, 부도시 익스포저.

    LGD = 1 − [ Σ R_t·DF(t) − Σ C_t·DF(t) ] / EAD,   DF(t) = (1+d)^(-t)

**할인율은 코드 상수가 아니라 원장 행이다.** 184.는 "할인효과를 고려할 것"까지만
정하고 수준·산식·세그먼트 구분을 주지 않는다. 원장의 할인율이 비어 있으면 이
모듈은 조용히 기본값을 쓰지 않고 그 세그먼트 산출을 건너뛰며, 산출불가 사유를
원장에 남긴다. 할인율 하나가 LGD 전체를 움직이므로 근거 없는 값이 들어가면
그 값이 RWA로 흘러간다.

**경기침체 LGD의 하한은 장기 부도가중평균이다**(185.가(1)). 침체기의 정의는
규정이 주지 않으므로 원장 모수(연도별 포트폴리오 부도율 분위)로 두고, 침체
연도는 **관측 데이터에서 식별**한다. 합성 이력의 ``cycle_phase`` 컬럼을 그대로
읽으면 생성 모수를 추정기에 넘기는 것이 되어 시험이 성립하지 않는다.

**관측중단을 무시하면 LGD가 낙관적으로 나온다.** 회수가 끝나지 않은 건은 회수가
어려운 건이 남은 것이므로, 빼고 추정하면 회수가 잘 된 건만 남는다. 두 처리의
값을 모두 계산해 차이를 원장에 남기고, 어느 쪽을 적용할지는 원장 모수가 정한다.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.models.estimation.common import (
    CENSORING_TREATMENTS, cast_to_spec, min_years_param_code, run_id,
)
from risk_lib.models.estimation.moc import compute_moc, moc_component_rows
from risk_lib.models.estimation.params import (
    ParamWarning, discount_rate_for, floor_value, param_text, param_value,
)

__all__ = [
    "LGD_ESTIMATE", "DEFAULTED_LGD",
    "realised_lgd", "identify_downturn_years", "estimate_lgd",
    "build_defaulted_lgd",
]

_BASIS = "부도가중평균"
# 담보유형별 하한을 고르는 규칙. 세그먼트가 곧 담보유형이 아니므로 매핑을
# 원장 조회 키로 옮긴다. 주거용주택담보만 담보 하한이 조문에 따로 있다.
_FLOOR_LOOKUP: dict[str, tuple[str, str]] = {
    "residential_mortgage": ("lgd_floor_secured", "real_estate"),
    "corporate": ("lgd_floor_unsecured", "해당없음"),
    "retail_other": ("lgd_floor_unsecured", "해당없음"),
}


LGD_ESTIMATE = TableSpec(
    name="crm_lgd_estimate", korean="LGD 추정치", product="PRD-RWA",
    grain="기준일 × 세그먼트 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("run_id", "string", "산출 식별자", nullable=False),
        C("exposure_class", "string", "자산군", nullable=False),
        C("estimation_basis", "string", "평균 기준", nullable=False,
          citation="[별표 3] 185.가(1) 장기 부도가중평균"),
        C("discount_rate", "float", "할인율", nullable=True, unit="ratio",
          citation="[별표 3] 184.(1) 할인효과"),
        C("discount_rate_status", "string", "할인율 상태", nullable=False),
        C("observation_years", "float", "관측기간", nullable=True,
          unit="years", min_value=0.0),
        C("n_defaults", "int", "부도건수", nullable=False, min_value=0),
        C("n_closed", "int", "회수종료 건수", nullable=False, min_value=0),
        C("n_censored", "int", "관측중단 건수", nullable=False, min_value=0),
        C("censoring_treatment", "string", "관측중단 처리", nullable=True,
          allowed=CENSORING_TREATMENTS),
        C("censoring_treatment_status", "string", "관측중단 처리 상태",
          nullable=False),
        C("lgd_excl_censored", "float", "관측중단 제외 LGD", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("lgd_incl_censored", "float", "관측중단 포함 LGD", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("censoring_impact", "float", "관측중단 처리 차이", nullable=True,
          unit="ratio",
          note="포함 − 제외. 양수면 제외 처리가 낙관적이라는 뜻"),
        C("longrun_default_weighted_lgd", "float", "장기 부도가중평균",
          nullable=True, unit="ratio", min_value=0.0, max_value=1.0,
          citation="[별표 3] 185.가(1)"),
        C("downturn_lgd", "float", "경기침체 LGD", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation="[별표 3] 185.가·나"),
        C("downturn_years", "text", "침체 연도", nullable=True),
        C("downturn_definition", "text", "침체기 정의", nullable=True),
        C("downturn_status", "string", "침체 산출 상태", nullable=False),
        C("raw_estimate", "float", "원시추정치", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="max(경기침체, 장기 부도가중평균). 185.가(1)의 하한 규칙"),
        C("floor_value", "float", "규제 하한", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation="[별표 3] 132.가"),
        C("floor_status", "string", "하한 상태", nullable=False),
        C("after_floor", "float", "하한 적용 후", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("floor_binding", "bool", "하한이 물었나", nullable=True),
        C("moc_amount", "float", "MoC", nullable=True, unit="ratio",
          citation="[별표 3] 181."),
        C("moc_status", "string", "MoC 상태", nullable=False),
        C("after_moc", "float", "MoC 적용 후", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("final_applied", "float", "최종 적용치", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("wrong_way_adjustment", "float", "차주·담보 상관 조정", nullable=True,
          unit="ratio", citation="[별표 3] 185.다"),
        C("currency_mismatch_adjustment", "float", "통화불일치 조정",
          nullable=True, unit="ratio", citation="[별표 3] 185.다"),
        C("adjustment_note", "text", "조정 비고", nullable=True),
        C("undiscounted_loss_rate", "float", "할인 전 손실률", nullable=True,
          unit="ratio",
          note="할인하지 않은 참고값이며 184.의 경제적 손실이 아니다. 할인율 "
               "승인 전에 화면이 빈 칸만 보이는 것을 막기 위한 관측 사실"),
        C("ead_at_default_total", "float", "부도시 익스포저 합계",
          nullable=True, unit="KRW", min_value=0.0),
        C("status", "string", "상태", nullable=False),
    ),
    primary_key=("asof", "segment"),
    note="원시추정 → 하한 → MoC → 최종을 각각 컬럼으로 둔다. 관측중단 두 처리의 "
         "값을 나란히 두어 선택의 영향이 화면에 보이게 한다.",
)

DEFAULTED_LGD = TableSpec(
    name="crm_defaulted_lgd", korean="부도자산 LGD", product="PRD-RWA",
    grain="기준일 × 세그먼트 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("n_defaulted_open", "int", "부도상태 건수", nullable=False,
          min_value=0),
        C("elbe", "float", "예상손실 최적추정치", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 3] 185.바 예상손실의 최적추정치"),
        C("elbe_method", "text", "산출방법", nullable=False),
        C("unexpected_loss_addon", "float", "예상외손실 추가분", nullable=True,
          unit="ratio", citation="[별표 3] 185.바 두 번째 문장"),
        C("lgd_in_default", "float", "부도자산 적용 LGD", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("addon_status", "string", "추가분 상태", nullable=False),
        C("elbe_amount", "float", "ELBE 금액", nullable=True, unit="KRW",
          min_value=0.0),
        C("specific_provision", "float", "개별충당금", nullable=True,
          unit="KRW", min_value=0.0),
        C("partial_writeoff", "float", "부분상각", nullable=True, unit="KRW",
          min_value=0.0),
        C("shortfall", "float", "충당금+상각 − ELBE", nullable=True,
          unit="KRW",
          note="양수면 ELBE가 작다는 뜻이고 185.바의 입증책임이 붙는다. "
               "반대 방향에는 입증책임이 없다. 비대칭 규칙이다"),
        C("justification_required", "bool", "정당성 입증 필요", nullable=True,
          citation="[별표 3] 185.바"),
        C("justification_ref", "text", "입증 문서", nullable=True),
        C("status", "string", "상태", nullable=False),
    ),
    primary_key=("asof", "segment"),
    note="185.바는 최적추정치가 개별충당금+부분상각보다 작을 때만 입증을 "
         "요구한다. 충당금 자료가 없으면 판정하지 않고 미판정으로 둔다.",
)


# ---------------------------------------------------------------- 실현 LGD

def realised_lgd(recovery: pd.DataFrame, *, discount_rate: float,
                 asof: str | None = None) -> pd.DataFrame:
    """부도건별 실현 LGD.

    회수·비용을 각각 회수시점으로 할인한 뒤 부도시 익스포저로 나눈다. 추가인출·
    역거래는 ``recovery_amount``의 음수로 이미 들어와 있어 별도 처리를 하지
    않는다. 부호를 컬럼으로 나누면 어느 쪽이 빠졌는지 합계에서 드러나지 않는다.
    """
    if discount_rate is None or not np.isfinite(discount_rate):
        raise ValueError("discount_rate는 유한한 값이어야 한다")
    need = {"default_id", "segment", "default_year", "ead_at_default",
            "recovery_years", "recovery_amount", "direct_cost",
            "indirect_cost", "workout_open"}
    missing = need - set(recovery.columns)
    if missing:
        raise ValueError(f"crm_recovery_history에 없는 컬럼: {sorted(missing)}")
    r = recovery if asof is None else recovery[recovery["asof"] == asof]
    if r.empty:
        return pd.DataFrame(columns=[
            "default_id", "segment", "default_year", "ead_at_default",
            "pv_recovery", "pv_cost", "lgd_realised", "workout_open",
            "nominal_loss_rate"])
    df_factor = (1.0 + float(discount_rate)) ** (
        -pd.to_numeric(r["recovery_years"], errors="coerce").astype(float))
    work = pd.DataFrame({
        "default_id": r["default_id"].to_numpy(),
        "segment": r["segment"].to_numpy(),
        "default_year": pd.to_numeric(r["default_year"]).to_numpy(),
        "ead_at_default": pd.to_numeric(r["ead_at_default"]).to_numpy(),
        "workout_open": r["workout_open"].to_numpy(),
        "pv_recovery": (pd.to_numeric(r["recovery_amount"]).to_numpy()
                        * df_factor.to_numpy()),
        "pv_cost": ((pd.to_numeric(r["direct_cost"]).to_numpy()
                     + pd.to_numeric(r["indirect_cost"]).to_numpy())
                    * df_factor.to_numpy()),
        "nominal_recovery": pd.to_numeric(r["recovery_amount"]).to_numpy(),
        "nominal_cost": (pd.to_numeric(r["direct_cost"]).to_numpy()
                         + pd.to_numeric(r["indirect_cost"]).to_numpy()),
    })
    g = work.groupby("default_id", as_index=False).agg(
        segment=("segment", "first"), default_year=("default_year", "first"),
        ead_at_default=("ead_at_default", "first"),
        workout_open=("workout_open", "max"),
        pv_recovery=("pv_recovery", "sum"), pv_cost=("pv_cost", "sum"),
        nominal_recovery=("nominal_recovery", "sum"),
        nominal_cost=("nominal_cost", "sum"))
    g["lgd_realised"] = np.clip(
        1.0 - (g["pv_recovery"] - g["pv_cost"]) / g["ead_at_default"], 0.0, 1.0)
    g["nominal_loss_rate"] = np.clip(
        1.0 - (g["nominal_recovery"] - g["nominal_cost"]) / g["ead_at_default"],
        0.0, 1.0)
    return g


def identify_downturn_years(default_history: pd.DataFrame, *,
                            param: pd.DataFrame, asof: str
                            ) -> tuple[list[int], str, str]:
    """관측 데이터에서 침체 연도를 식별한다.

    연도별 포트폴리오 부도율이 원장 분위 이상인 해를 침체로 본다. 분위가 승인
    전이면 빈 목록과 상태 ``'기준미승인'``을 돌려준다. 침체기 정의는 규정이
    주지 않으므로 임의로 정하면 그 정의가 규정처럼 보인다.

    합성 이력의 ``cycle_phase``를 읽지 않는다. 생성 라벨을 그대로 쓰면 침체
    식별 로직이 시험되지 않는다.
    """
    q = param_value(param, "downturn_year_quantile")
    if q is None:
        return [], "침체기 정의 모수가 승인 전이다", "기준미승인"
    h = default_history[default_history["asof"] == asof]
    yearly = h.groupby("cohort_year")["default_flag"].mean()
    if yearly.empty:
        return [], "관측연도가 없다", "표본부족"
    cut = float(yearly.quantile(q))
    years = [int(y) for y, v in yearly.items() if float(v) >= cut]
    definition = (
        f"연도별 포트폴리오 부도율이 상위 분위 {q:.4g}(임계 {cut:.6g}) 이상인 "
        f"해를 침체로 본다. [별표 3] 185.가·나는 '평균보다 상당히 높은 "
        f"손실발생기간'이라고만 적고 정의를 주지 않는다")
    return years, definition, "산출완료"


# ---------------------------------------------------------------- 추정

def estimate_lgd(recovery: pd.DataFrame, default_history: pd.DataFrame, *,
                 floors: pd.DataFrame, param: pd.DataFrame,
                 rates: pd.DataFrame, asof: str, seed: int = 42,
                 framework_version: str = "바젤3최종안",
                 representativeness_flagged: dict[str, bool] | None = None,
                 ) -> dict[str, object]:
    """세그먼트별 LGD를 추정한다.

    할인율이 원장에 없으면 그 세그먼트는 ``status='산출불가(할인율미승인)'``로
    남고 수치 컬럼은 비어 있다. 비어 있음이 화면에 드러나는 것이 산출물이다.
    """
    segments = sorted(set(recovery.loc[recovery["asof"] == asof, "segment"]))
    est_rows: list[dict] = []
    run_rows: list[dict] = []
    moc_rows: list[dict] = []
    notes: list[str] = []

    dt_years, dt_definition, dt_status = identify_downturn_years(
        default_history, param=param, asof=asof)
    treatment = param_text(param, "lgd_censoring_treatment")
    if treatment is not None and treatment not in CENSORING_TREATMENTS:
        raise ValueError(
            f"lgd_censoring_treatment는 {CENSORING_TREATMENTS} 중 하나여야 한다")
    if treatment is None:
        notes.append("lgd_censoring_treatment가 승인 전이다. 두 처리의 값을 "
                     "모두 내고 최종 적용치는 정하지 않는다")

    for segment in segments:
        rid = run_id(asof=asof, parameter="LGD", segment=segment, seed=seed)
        seg_rec = recovery[(recovery["asof"] == asof)
                           & (recovery["segment"] == segment)]
        n_def = int(seg_rec["default_id"].nunique())
        years = sorted(set(pd.to_numeric(seg_rec["default_year"])))
        obs_years = float(len(years))
        min_code = min_years_param_code("LGD", segment)
        min_years = param_value(param, min_code)
        meets = None if min_years is None else bool(obs_years >= min_years)

        try:
            rate = discount_rate_for(rates, asof=asof, segment=segment)
            rate_status = "승인" if rate is not None else "미승인"
        except KeyError:
            rate, rate_status = None, "원장행없음"
            notes.append(f"{segment}: crm_lgd_discount_rate에 행이 없다")

        param_key, coll = _FLOOR_LOOKUP.get(
            segment, ("lgd_floor_unsecured", "해당없음"))
        try:
            fl, fl_status = floor_value(
                floors, parameter=param_key, exposure_class=segment,
                collateral_type=coll, framework_version=framework_version)
        except KeyError:
            fl, fl_status = None, "미확인"
            notes.append(f"{segment}: crm_input_floor에 {param_key} 행이 없다")

        base = {
            "asof": asof, "segment": segment, "run_id": rid,
            "exposure_class": segment, "estimation_basis": _BASIS,
            "discount_rate": rate, "discount_rate_status": rate_status,
            "observation_years": obs_years, "n_defaults": n_def,
            "n_closed": 0, "n_censored": 0,
            "censoring_treatment": treatment,
            "censoring_treatment_status": ("승인" if treatment is not None
                                           else "기준미승인"),
            "lgd_excl_censored": None, "lgd_incl_censored": None,
            "censoring_impact": None,
            "longrun_default_weighted_lgd": None,
            "downturn_lgd": None,
            "downturn_years": (", ".join(map(str, dt_years)) if dt_years
                               else None),
            "downturn_definition": dt_definition,
            "downturn_status": dt_status,
            "raw_estimate": None, "floor_value": fl,
            "floor_status": fl_status, "after_floor": None,
            "floor_binding": None, "moc_amount": None,
            "moc_status": "해당없음", "after_moc": None,
            "final_applied": None,
            "wrong_way_adjustment": None,
            "currency_mismatch_adjustment": None,
            "adjustment_note": (
                "185.다의 차주·담보 상관과 통화불일치 조정은 담보 소재통화와 "
                "차주·담보제공자 상관 자료가 없어 산출하지 않았다. 0으로 두지 "
                "않는다"),
            "undiscounted_loss_rate": None,
            "ead_at_default_total": None,
            "status": "산출완료",
        }
        unresolved: list[str] = []

        if rate is None:
            warnings.warn(
                f"회수 할인율이 없다 (segment={segment}). [별표 3] 184.는 값을 "
                "주지 않고 내부기준은 승인 전이다. 이 세그먼트 LGD 산출을 "
                "건너뛴다", ParamWarning, stacklevel=2)
            base["status"] = "산출불가"
            unresolved.append("lgd_discount_rate")
            # 할인 전 손실률은 관측 사실이므로 남긴다. 이것은 LGD가 아니다.
            if not seg_rec.empty:
                nominal = realised_lgd(seg_rec, discount_rate=0.0, asof=asof)
                base["undiscounted_loss_rate"] = float(
                    nominal["lgd_realised"].mean())
                base["ead_at_default_total"] = float(
                    nominal["ead_at_default"].sum())
                base["n_censored"] = int(nominal["workout_open"].sum())
                base["n_closed"] = int((~nominal["workout_open"]).sum())
            est_rows.append(base)
            run_rows.append(_run_row(
                base, min_years=min_years, meets=meets, years=years,
                param=param, framework_version=framework_version, seed=seed,
                unresolved=unresolved, moc=None,
                n_obs=n_def, n_censored=base["n_censored"]))
            continue

        per_default = realised_lgd(seg_rec, discount_rate=rate, asof=asof)
        closed = per_default[~per_default["workout_open"].astype(bool)]
        n_closed = int(len(closed))
        n_cens = int(len(per_default) - n_closed)
        # 185.가(1)·195.다의 부도가중평균. 부도 1건이 관측 1건이므로 건별
        # 산술평균이 곧 부도가중평균이다. 금액가중으로 바꾸면 대형 부도 한 건이
        # 세그먼트 LGD를 지배한다.
        lgd_excl = float(closed["lgd_realised"].mean()) if n_closed else None
        lgd_incl = (float(per_default["lgd_realised"].mean())
                    if len(per_default) else None)
        longrun = (lgd_incl if treatment == "보수적포함" else lgd_excl)
        if treatment is None:
            # 처리 선택이 승인 전이면 장기평균 자체를 확정하지 않는다.
            longrun = lgd_excl
            unresolved.append("lgd_censoring_treatment")

        yearly_mean = (closed.groupby("default_year")["lgd_realised"].mean()
                       if n_closed else pd.Series(dtype=float))
        downturn = None
        if dt_years and n_closed:
            dsub = closed[closed["default_year"].isin(dt_years)]
            if len(dsub):
                downturn = float(dsub["lgd_realised"].mean())
        if dt_status == "기준미승인":
            unresolved.append("downturn_year_quantile")

        raw = None
        if longrun is not None:
            # 185.가(1) 장기 부도가중평균을 하한으로 한다.
            raw = float(max(longrun, downturn)) if downturn is not None \
                else float(longrun)
        after_floor = raw if (fl is None or raw is None) else float(max(raw, fl))
        binding = None if (fl is None or raw is None) else bool(fl > raw)
        if fl is None:
            unresolved.append(param_key)
            warnings.warn(
                f"LGD 하한이 비어 있다 (segment={segment}, status={fl_status}). "
                "하한을 적용하지 않고 그 사실을 산출 결과에 싣는다",
                ParamWarning, stacklevel=2)

        moc = None
        after_moc = after_floor
        if after_floor is not None:
            flagged = (None if representativeness_flagged is None
                       else bool(representativeness_flagged.get(segment)))
            moc = compute_moc(param=param, point_estimate=after_floor,
                              yearly_estimates=yearly_mean.to_numpy(),
                              representativeness_flagged=flagged)
            unresolved.extend(moc.unresolved)
            moc_rows.extend(moc_component_rows(
                moc, asof=asof, parameter="LGD", segment=segment,
                grade=segment, point_estimate=after_floor))
            after_moc = float(after_floor + (moc.total or 0.0))
        final = (None if after_moc is None
                 else float(min(1.0, after_moc if fl is None
                                else max(after_moc, fl))))
        if treatment is None:
            final = None   # 적용치는 처리 선택이 승인돼야 확정된다

        base.update({
            "n_closed": n_closed, "n_censored": n_cens,
            "lgd_excl_censored": lgd_excl, "lgd_incl_censored": lgd_incl,
            "censoring_impact": (None if (lgd_excl is None or lgd_incl is None)
                                 else float(lgd_incl - lgd_excl)),
            "longrun_default_weighted_lgd": longrun,
            "downturn_lgd": downturn,
            "raw_estimate": raw, "after_floor": after_floor,
            "floor_binding": binding,
            "moc_amount": (moc.total if moc else None),
            "moc_status": (moc.status if moc else "해당없음"),
            "after_moc": after_moc, "final_applied": final,
            "undiscounted_loss_rate": float(
                per_default["nominal_loss_rate"].mean()),
            "ead_at_default_total": float(per_default["ead_at_default"].sum()),
            "status": ("산출완료" if meets in (True, None)
                       else "산출완료(요건미충족)"),
        })
        est_rows.append(base)
        run_rows.append(_run_row(
            base, min_years=min_years, meets=meets, years=years, param=param,
            framework_version=framework_version, seed=seed,
            unresolved=unresolved, moc=moc, n_obs=n_def, n_censored=n_cens))

    est = cast_to_spec(pd.DataFrame(est_rows, columns=[
        c.name for c in LGD_ESTIMATE.columns]), LGD_ESTIMATE)
    return {"crm_lgd_estimate": est, "run_rows": run_rows,
            "moc_rows": moc_rows, "warnings": notes}


def _run_row(base: dict, *, min_years, meets, years, param,
             framework_version, seed, unresolved, moc, n_obs,
             n_censored) -> dict:
    """산출이력 한 줄. 추정 원장과 같은 사실을 요약해 담는다."""
    return {
        "asof": base["asof"], "parameter": "LGD", "segment": base["segment"],
        "run_id": base["run_id"], "exposure_class": base["exposure_class"],
        "method": ("[별표 3] 184. 워크아웃 방식. 회수·비용을 회수시점으로 "
                   "할인해 부도시 익스포저로 나눈다"),
        "estimation_basis": _BASIS,
        "observation_start": (f"{years[0]:04d}-01-01" if years else None),
        "observation_end": (f"{years[-1]:04d}-12-31" if years else None),
        "observation_years": base["observation_years"],
        "min_observation_years": min_years, "meets_minimum": meets,
        "n_obligors": None, "n_defaults": base["n_defaults"],
        "n_observations": n_obs, "n_censored": n_censored,
        "estimation_window_end": (int(years[-1]) if years else None),
        "holdout_year": None,
        "moc_amount": (moc.total if moc else None),
        "moc_status": (moc.status if moc else "해당없음"),
        "moc_rationale": (moc.rationale if moc else None),
        "moc_aggregation": (moc.aggregation if moc else None),
        "floor_applied": base["floor_value"] is not None,
        "n_floor_binding": (1 if base["floor_binding"] else 0),
        "amount_floor_binding": (base["ead_at_default_total"]
                                 if base["floor_binding"] else 0.0),
        "default_definition": None,
        "definition_adjustment": None,
        "population_alignment": None,
        "last_review_date": None, "next_review_due": None,
        "review_interval_months": param_value(param, "review_interval_months"),
        "unresolved_inputs": ("; ".join(sorted(set(unresolved)))
                              if unresolved else None),
        "status": base["status"],
        "framework_version": framework_version, "seed": seed,
        "source_system": "synthetic",
    }


# ---------------------------------------------------------------- 부도자산

_ELBE_METHOD = (
    "부도상태 건에 해당 세그먼트의 회수종료 부도건 실현 LGD 부도가중평균을 "
    "적용했다. 경과월별 BEEL 곡선은 만들지 않았다. 교안이 제시하는 경과월 축 "
    "산식의 분모(경과시점 잔여 익스포저인지 부도시 익스포저인지)를 자료에서 "
    "확정하지 못했고, 분모 선택 하나로 값이 크게 달라진다")
_ADDON_NOTE = (
    "185.바 두 번째 문장의 예상외손실 추가분을 산출하지 않았다. 교안은 "
    "PLGD(Potential LGD)를 BEEL에 Downturn Scaling Factor를 반영하거나 BEEL "
    "분포에서 직접 추정한다고 적을 뿐, 반영이 승산인지 가산인지와 분위 신뢰수준을 "
    "적지 않는다. 두 값 모두 자료에서 확정하지 못했으므로 지어내지 않는다")


def build_defaulted_lgd(recovery: pd.DataFrame, lgd_estimate: pd.DataFrame, *,
                        asof: str,
                        provisions: pd.DataFrame | None = None
                        ) -> pd.DataFrame:
    """부도자산 LGD 원장 (185.바).

    ``provisions``는 ``segment``·``specific_provision``·``partial_writeoff``를
    갖는 프레임이다. 없으면 충당금 비교를 하지 않고 ``justification_required``를
    NULL로 둔다. 비교 대상이 없는데 False로 두면 '입증이 필요 없음을 확인했다'가
    되어 판정하지 않은 것과 구분되지 않는다.

    **예상외손실 추가분(PLGD)은 구현하지 않았다.** 사유는 ``addon_status``와
    이 모듈의 ``_ADDON_NOTE``에 있다.
    """
    r = recovery[recovery["asof"] == asof]
    rows: list[dict] = []
    prov = (provisions.set_index("segment") if provisions is not None
            and not provisions.empty else None)
    for _, est in lgd_estimate.iterrows():
        seg = est["segment"]
        open_ids = r[(r["segment"] == seg) & (r["workout_open"].astype(bool))]
        n_open = int(open_ids["default_id"].nunique())
        ead_open = float(open_ids.drop_duplicates("default_id")
                         ["ead_at_default"].sum())
        elbe = est["longrun_default_weighted_lgd"]
        elbe = None if pd.isna(elbe) else float(elbe)
        elbe_amount = None if elbe is None else float(elbe * ead_open)
        sp = wo = shortfall = None
        required = None
        if prov is not None and seg in prov.index:
            sp = float(prov.loc[seg, "specific_provision"])
            wo = float(prov.loc[seg, "partial_writeoff"])
            if elbe_amount is not None:
                shortfall = float(sp + wo - elbe_amount)
                required = bool(shortfall > 0)
        rows.append({
            "asof": asof, "segment": seg, "n_defaulted_open": n_open,
            "elbe": elbe, "elbe_method": _ELBE_METHOD,
            "unexpected_loss_addon": None, "lgd_in_default": None,
            "addon_status": "미산출(근거미확인)",
            "elbe_amount": elbe_amount, "specific_provision": sp,
            "partial_writeoff": wo, "shortfall": shortfall,
            "justification_required": required,
            "justification_ref": None,
            "status": ("산출완료" if elbe is not None else "산출불가"),
        })
    return cast_to_spec(pd.DataFrame(rows, columns=[
        c.name for c in DEFAULTED_LGD.columns]), DEFAULTED_LGD)
