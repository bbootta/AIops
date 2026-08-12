"""신용평가시스템 원장 일괄 빌더.

배선 담당이 파이프라인에 붙일 진입점 하나를 둔다. 이 함수 밖에서는 원장을
만들지 않으며, 여기서 규제표(요건 원장)·설계모수·합성 운영기록을 적재하고
엔진 함수에 인자로 넘긴다.

**세그먼트 범위.** 스코어카드는 기업 익스포져에만 적합한다. 재무·비재무·대표자
축은 기업평가모형의 구조이며(BNK-CRM-006·007·008), 소매 CSS는 축 구성이 다르다.
소매까지 같은 축으로 돌리면 없는 재무제표를 있는 것처럼 쓰게 된다. 소매는
개발표본·부도정의 원장(BNK-CRM-003)까지만 만든다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.credit_rating import override as ovr
from risk_lib.credit_rating import requirements as req
from risk_lib.credit_rating import sample as smp
from risk_lib.credit_rating import scorecard as sc
from risk_lib.data_gen import split_train_test

__all__ = ["CORPORATE_MODEL_ID", "MODEL_MAP", "FINANCIAL_FACTORS",
           "CreditRatingResult", "build_credit_rating"]

CORPORATE_MODEL_ID = "PD_CORP"
# 세그먼트 → 모형. crm_model에 있는 식별자여야 FK가 성립한다.
MODEL_MAP: dict[str, str] = {
    "corporate": CORPORATE_MODEL_ID,
    "retail_other": "PD_RETAIL",
    "residential_mortgage": "PD_MORTGAGE",
}

# (변수, 변수명, 예상 방향). 예상 방향은 구간 순서에 따른 부도율의 방향이며
# 재무 이론에서 온다. 관측 방향과 어긋나면 158.(1) 점검 대상이다.
FINANCIAL_FACTORS: tuple[tuple[str, str, str], ...] = (
    ("leverage", "부채비율", "증가"),
    ("current_ratio", "유동비율", "감소"),
    ("interest_coverage", "이자보상배율", "감소"),
    ("log_assets", "자산규모(로그)", "감소"),
)

# 신용평가시스템 요건은 차주등급·PD를 부여하는 모형에 걸린다. 같은 crm_model에
# 있는 LGD·ECL 모형은 [별표 3] 제4절 제5관의 추정·검증 요건(186.·195.·203.나)
# 대상이며 제1~3관의 등급체계·등급운영 요건 대상이 아니다. 그 조문들은 아직
# 요건 원장에 옮기지 않았으므로, 옮기기 전까지 LGD·ECL 모형을 판정 대상에
# 넣으면 걸리지 않는 요건으로 미이행이 잡힌다. 식별자 두문자는 crm_model의
# 기존 규약이며 materialize._domain도 같은 규약을 쓴다.
_RATING_MODEL_PREFIX = "PD_"

# 합성 운영기록의 비중. 실제 은행은 워크플로에서 받는다.
_OVERRIDE_SHARE = 0.08
_UNAPPROVED_SHARE = 0.15
# 이 저장소 합성 포트폴리오의 코호트 범위. vintage.synthesise_vintage와 같은 뜻.
_OBSERVATION_MONTHS = 24
_HOLDOUT_SHARE = 0.3
_PSI_BINS = 10


class CreditRatingResult:
    """원장 묶음과 경고. 경고는 판정하지 못한 항목을 알린다."""

    def __init__(self, tables: dict[str, pd.DataFrame], warnings: list[str]):
        self.tables = tables
        self.warnings = warnings


def build_credit_rating(portfolio: pd.DataFrame, models: pd.DataFrame, *,
                        asof: str, seed: int) -> CreditRatingResult:
    """신용평가시스템 원장 전부를 만든다.

    models는 `crm_model` 원장이다(model_id·domain·segment). 요건 적용 대상을
    거기서 결정하므로 시장·ALM 모형에 신용평가 요건이 걸리지 않는다.
    """
    warnings: list[str] = []
    requirements = req.build_rating_requirements()
    rating_models = models[
        models["model_id"].astype(str).str.startswith(_RATING_MODEL_PREFIX)]
    events = req.build_lifecycle_events(rating_models, requirements,
                                        asof=asof, seed=seed)
    compliance = req.assess_lifecycle(rating_models, requirements, events,
                                      asof=asof)

    dev_sample = smp.build_dev_sample(
        portfolio, requirements, model_map=MODEL_MAP, asof=asof,
        observation_months=_OBSERVATION_MONTHS,
        holdout_share=_HOLDOUT_SHARE, scope_map=req.SEGMENT_SCOPE)
    short = dev_sample[dev_sample["meets_minimum"] == "부적합"]
    if not short.empty:
        warnings.append(
            "최소 관측기간 요건([별표 3] 182.라·183.나)을 채우지 못한 개발표본: "
            + ", ".join(sorted(short["segment"]))
            + f" (관측 {float(short['observation_years'].iloc[0]):.1f}년). "
              "이 저장소의 합성 포트폴리오가 단일 시점이기 때문이며 PD 추정치는 "
              "규제 목적으로 쓸 수 없다")

    params = sc.build_scorecard_param(CORPORATE_MODEL_ID)
    items = sc.build_qualitative_items()

    corp = portfolio[portfolio["asset_class"] == "corporate"].copy()
    if corp.empty:
        tables = {
            "crm_rating_requirement": requirements,
            "crm_lifecycle_event": events,
            "crm_lifecycle_compliance": compliance,
            "crm_dev_sample": dev_sample,
            "crm_scorecard_param": params,
            "crm_qualitative_item": items,
        }
        return CreditRatingResult(tables, warnings)

    qual = sc.build_qualitative_assessment(corp, items, asof=asof, seed=seed)
    wide = qual.pivot(index="obligor_id", columns="item_code", values="score")
    corp = corp.merge(wide, on="obligor_id", how="left")

    factor_axis: dict[str, str] = {f: "재무" for f, _, _ in FINANCIAL_FACTORS}
    factor_korean: dict[str, str] = {f: k for f, k, _ in FINANCIAL_FACTORS}
    expected: dict[str, str] = {f: s for f, _, s in FINANCIAL_FACTORS}
    for it in items.itertuples(index=False):
        factor_axis[it.item_code] = it.axis
        factor_korean[it.item_code] = it.korean
        # 척도가 '높을수록 위험'이므로 구간이 올라가면 부도율도 오른다.
        expected[it.item_code] = "증가"

    # 검정표본은 여기서 쓰지 않는다. 변별력·안정성 검증은 crm_performance가
    # 담당하며, 여기서는 개발표본 비중을 crm_dev_sample에 기록하는 것이 목적이다.
    dev, _holdout = split_train_test(corp, test_frac=_HOLDOUT_SHARE, seed=seed)
    fit = sc.fit_scorecard(dev, factor_axis, factor_korean, expected,
                           target="default_12m", params=params,
                           model_id=CORPORATE_MODEL_ID, seed=seed)
    scores, axis_scores = sc.score_obligors(fit, corp, params=params, asof=asof)
    bad_sign = fit.factors[(fit.factors["sign_expected"] != "미정")
                           & (~fit.factors["sign_agrees"])]
    if not bad_sign.empty:
        warnings.append(
            "예상 방향과 관측 방향이 어긋난 변수: "
            + ", ".join(sorted(bad_sign["factor"]))
            + ". [별표 3] 158.(1)의 예측력·편의 점검 대상")

    repr_rows = smp.build_representativeness(
        dev, corp, list(factor_axis.keys()), model_id=CORPORATE_MODEL_ID,
        segment="corporate", asof=asof, psi_bins=_PSI_BINS)

    reasons = ovr.build_override_reasons()
    overrides = ovr.build_overrides(scores, reasons, asof=asof, seed=seed,
                                    override_share=_OVERRIDE_SHARE,
                                    unapproved_share=_UNAPPROVED_SHARE)
    overrides, ovr_warns = ovr.assess_override_range(overrides, reasons)
    warnings.extend(ovr_warns)
    performance = ovr.build_override_performance(overrides, corp, asof=asof)
    n_unapproved = int(performance["n_unapproved"].sum()) if not performance.empty else 0
    if n_unapproved:
        warnings.append(
            f"승인자가 기록되지 않은 등급변경 {n_unapproved}건. "
            "[별표 3] 165.가(3)은 등급변경의 책임자를 요구한다")

    structure = req.check_grade_structure(
        sc.non_default_grades(), ["D"], requirements)
    for s in structure:
        if s["meets"] is False:
            warnings.append(
                f"{s['label']} {s['actual']}개, 요건 {s['required']:.0f}개 "
                f"({s['citation']})")

    tables = {
        "crm_rating_requirement": requirements,
        "crm_lifecycle_event": events,
        "crm_lifecycle_compliance": compliance,
        "crm_dev_sample": dev_sample,
        "crm_sample_representativeness": repr_rows,
        "crm_scorecard_param": params,
        "crm_scorecard_bin": fit.bins,
        "crm_scorecard_factor": fit.factors,
        "crm_scorecard_axis": fit.axes,
        "crm_qualitative_item": items,
        "crm_qualitative_assessment": qual,
        "crm_obligor_axis_score": axis_scores,
        "crm_obligor_score": scores,
        "crm_override_reason": reasons,
        "crm_override": overrides,
        "crm_override_performance": performance,
    }
    return CreditRatingResult(tables, warnings)
