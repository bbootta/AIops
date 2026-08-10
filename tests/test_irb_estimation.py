"""내부등급법 PD·LGD·CCF 추정 시험.

시험의 축은 넷이다.

1. **되찾기.** 합성 생성 모수를 추정기가 허용오차 안에서 되찾는가. 생성 모수는
   ``history`` 모듈에만 있고 추정 모듈은 그것을 읽지 않는다.
2. **경계.** 최소 관측기간·하한이 경계에서 판정을 바꾸는가.
3. **음성 대조.** 정합성 검사에 위반을 주입하면 실제로 FAIL이 뜨는가. 언제나
   통과하는 검사는 아무것도 지키지 못한다.
4. **결정론.** 같은 (asof, seed)면 별도 프로세스에서도 결과가 같은가.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
import pytest

from risk_lib.datamodel.spec import check_refs, validate
from risk_lib.models.estimation import (
    ALL_TABLES, ParamWarning, approve_discount_rate, approve_estimation_param,
    assign_irb_method, build_crm_default_history, build_crm_input_floor,
    build_crm_irb_scope, build_estimation_param_ledgers, build_history_ledgers,
    build_irb_estimation_ledgers, compute_moc, estimate_lgd, estimate_pd,
    floor_value, identify_downturn_years, observed_ccf, param_value,
    realised_lgd, run_irb_estimation_checks, unapproved_internal_params,
)
from risk_lib.models.estimation import history as H
from risk_lib.models.estimation.checks import (
    check_backtest_inside_range, check_backtest_out_of_sample,
    check_basis_domain, check_ccf_denominator_accounting,
    check_ccf_floor_is_derived, check_censoring_disclosure,
    check_downturn_floor, check_elbe_provision_justification, check_lgd_floor,
    check_moc_direction, check_observation_minimum, check_pd_estimate_wired,
    check_pd_floor,
)
from risk_lib.validation.consistency import ValidationReport

ASOF = "2026-06-30"
SEED = 42

# 승인 전에는 내부기준 모수가 비어 있어 MoC·침체·판정이 모두 멈춘다. 시험은
# 승인된 상태를 만들어 엔진 경로를 끝까지 태운다. 아래 값은 규정 수치가 아니라
# 시험용 승인 기록이며 저장소 산출물의 기본값이 아니다.
_APPROVED_NUM = {
    "downturn_year_quantile": 0.75,
    "moc_confidence_level": 0.75,
    "moc_data_quality_addon": 0.05,
    "moc_representativeness_addon": 0.05,
    "backtest_ci_level": 0.99,
    "backtest_significance_level": 0.05,
    "psi_threshold_warn": 0.10,
    "psi_threshold_fail": 0.25,
    "pd_seasoning_addon_retail": 0.02,
}
_APPROVED_TXT = {"moc_aggregation": "단순합",
                 "lgd_censoring_treatment": "보수적포함"}
_TEST_DISCOUNT_RATE = 0.11


def _approved_param() -> pd.DataFrame:
    p = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    for code, val in _APPROVED_NUM.items():
        p = approve_estimation_param(p, code=code, value=val,
                                     approved_by="시험", approval_date="2026-01-01",
                                     approval_body="모형위원회")
    for code, txt in _APPROVED_TXT.items():
        p = approve_estimation_param(p, code=code, text=txt,
                                     approved_by="시험", approval_date="2026-01-01",
                                     approval_body="모형위원회")
    return p


def _approved_rates(rate: float = _TEST_DISCOUNT_RATE) -> pd.DataFrame:
    r = build_estimation_param_ledgers(ASOF)["crm_lgd_discount_rate"]
    for seg in ("corporate", "retail_other", "residential_mortgage"):
        r = approve_discount_rate(r, asof=ASOF, segment=seg,
                                  recovery_scope="전체", rate=rate,
                                  basis="자기자본비용", approved_by="시험",
                                  approval_date="2026-01-01")
    return r


@pytest.fixture(scope="module")
def hist() -> dict[str, pd.DataFrame]:
    return build_history_ledgers(asof=ASOF, seed=SEED, years=8)


@pytest.fixture(scope="module")
def ledgers_default() -> dict[str, pd.DataFrame]:
    """승인 전 기본 산출물. 내부기준 모수가 비어 있는 상태."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_irb_estimation_ledgers(asof=ASOF, seed=SEED)


@pytest.fixture(scope="module")
def ledgers_approved() -> dict[str, pd.DataFrame]:
    """내부기준이 승인된 상태의 산출물."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_irb_estimation_ledgers(
            asof=ASOF, seed=SEED, param=_approved_param(),
            rates=_approved_rates())


# ---------------------------------------------------------------- 원장 스펙

def test_all_tables_pass_spec(ledgers_default):
    """모든 원장이 자기 스펙을 통과한다. FK 대상도 존재한다."""
    for name, spec in ALL_TABLES.items():
        assert name in ledgers_default, f"{name} 산출 누락"
        violations = validate(ledgers_default[name], spec)
        assert not violations, f"{name}: {[str(v) for v in violations]}"
    assert not check_refs(ledgers_default, ALL_TABLES)


def test_unconfirmed_values_stay_null():
    """자료가 비었거나 어긋나는 항목은 값을 채우지 않는다."""
    floors = build_crm_input_floor()
    # 주거용주택담보 무담보 LGD 하한. 감독당국 자료가 칸을 '-'로 비웠다.
    val, status = floor_value(floors, parameter="lgd_floor_unsecured",
                              exposure_class="residential_mortgage")
    assert val is None and status == "미확인"
    # 대기업 AIRB 제외 매출 기준액. 6천억(2018 워크숍)과 7천억(2023 요건정의서)이
    # 어긋난다. 한쪽을 고르지 않는다.
    param = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    assert param_value(param, "airb_exclusion_revenue_krw") is None
    row = param[param["param_code"] == "airb_exclusion_revenue_krw"].iloc[0]
    assert row["evidence_status"] == "미확인"
    assert "6천억" in row["citation"] and "7천억" in row["citation"]


def test_internal_params_ship_unapproved():
    """규정이 수치를 주지 않는 항목은 값과 승인자가 모두 비어 있다."""
    param = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    blank = unapproved_internal_params(param)
    codes = set(blank["param_code"])
    for code in ("moc_confidence_level", "downturn_year_quantile",
                 "backtest_ci_level", "psi_threshold_fail",
                 "lgd_censoring_treatment"):
        assert code in codes, f"{code}가 승인 전 목록에 없다"
    assert blank["param_value"].isna().all() or blank["approved_by"].isna().all()
    # 규정 수치는 승인 대상이 아니다.
    with pytest.raises(ValueError):
        approve_estimation_param(param, code="obs_years_min_pd_corporate",
                                 value=3.0, approved_by="x",
                                 approval_date="2026-01-01",
                                 approval_body="모형위원회")


def test_pd_floor_differs_by_framework_version():
    """PD 하한이 판본별로 다르고 적격회전거래 세분이 갈라져 있다."""
    floors = build_crm_input_floor()
    old, _ = floor_value(floors, parameter="pd_floor",
                         exposure_class="corporate",
                         framework_version="별표3_2018-06-30")
    new, _ = floor_value(floors, parameter="pd_floor",
                         exposure_class="corporate")
    assert old == pytest.approx(0.0003)
    assert new == pytest.approx(0.0005)
    assert floor_value(floors, parameter="pd_floor",
                       exposure_class="sovereign")[0] == pytest.approx(0.0003)
    assert floor_value(floors, parameter="pd_floor",
                       exposure_class="qrre_revolver")[0] == pytest.approx(0.001)
    assert floor_value(floors, parameter="pd_floor",
                       exposure_class="qrre_transactor")[0] == pytest.approx(0.0005)
    # 주거용주택담보 담보 LGD 하한은 10%에서 5%로 내려갔다.
    assert floor_value(floors, parameter="lgd_floor_secured",
                       exposure_class="residential_mortgage",
                       collateral_type="real_estate",
                       framework_version="별표3_2018-06-30")[0] == pytest.approx(0.10)
    assert floor_value(floors, parameter="lgd_floor_secured",
                       exposure_class="residential_mortgage",
                       collateral_type="real_estate")[0] == pytest.approx(0.05)


def test_ccf_floor_is_multiplier_not_constant(ledgers_default):
    """CCF 하한은 상수 20%가 아니라 표준방법 환산율 × 배수다."""
    floors = build_crm_input_floor()
    mult, _ = floor_value(floors, parameter="ccf_floor_multiplier",
                          exposure_class="all")
    assert mult == pytest.approx(0.5)
    # 정부 익스포저는 값이 NULL이되 사유가 '미확인'이 아니라 '적용제외'다.
    val, status = floor_value(floors, parameter="ccf_floor_multiplier",
                              exposure_class="sovereign")
    assert val is None and status == "적용제외"
    est = ledgers_default["crm_ccf_estimate"]
    got = est.set_index("ccf_type")["floor_value"].to_dict()
    assert got["unconditionally_cancellable"] == pytest.approx(0.05)
    assert got["commitment_gt_1y"] == pytest.approx(0.20)
    assert got["short_term_trade"] == pytest.approx(0.10)


def test_irb_scope_blocks_equity_and_bank_airb():
    """주식 IRB 금지와 은행 AIRB 금지를 원장이 강제한다."""
    scope = build_crm_irb_scope()
    param = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    obligors = pd.DataFrame({
        "obligor_id": ["O1", "O2", "O3"],
        "exposure_class": ["equity", "bank", "corporate"],
        "annual_revenue": [1e11, 1e11, 1e12]})
    with pytest.warns(ParamWarning):
        out = assign_irb_method(obligors, scope, param)
    row = out.set_index("obligor_id")
    assert row.loc["O1", "firb_allowed"] is np.False_ or not row.loc["O1", "firb_allowed"]
    assert not row.loc["O1", "airb_allowed"]
    assert not row.loc["O2", "airb_allowed"]
    # 매출 기준액이 미확인이라 대기업 판정은 나지 않는다. 판정불가를 허용으로
    # 바꾸지 않는다.
    assert row.loc["O3", "scope_status"] == "기준액미확인"
    assert row.loc["O3", "airb_allowed"] is None
    assert not row.loc["O3", "airb_allowed_conservative"]
    # 기준액은 내부기준이 아니라 규정 수치이므로 승인 대상이 아니다. 확정
    # 시행세칙을 확인해 원장 값을 채우는 것이 유일한 경로다.
    with pytest.raises(ValueError):
        approve_estimation_param(param, code="airb_exclusion_revenue_krw",
                                 value=7.0e11, approved_by="시험",
                                 approval_date="2026-01-01",
                                 approval_body="리스크관리위원회")
    confirmed = param.copy()
    confirmed.loc[confirmed["param_code"] == "airb_exclusion_revenue_krw",
                  "param_value"] = 7.0e11
    out2 = assign_irb_method(obligors, scope, confirmed).set_index("obligor_id")
    assert out2.loc["O3", "scope_status"] == "판정완료"
    assert not out2.loc["O3", "airb_allowed"]     # 1조원 > 7천억원


# ---------------------------------------------------------------- 되찾기

def test_pd_estimator_recovers_generation_parameters(hist):
    """생성 모수를 추정기가 되찾는다.

    생성 모수는 ``history._TRUE_PD``와 ``history._CYCLE_MULT``에 있고, 추정
    모듈은 이 상수를 읽지 않는다. 추정 표본(유보연도 제외 7년)의 경기배수 평균이
    1.0이므로 연도동일가중 단순평균은 기저 부도율로 수렴한다.

    허용오차는 상대 30%다. 코호트가 1,000명 안팎이라 저부도 자산군(0.8%)의
    연도별 부도율이 크게 흔들린다. 이 흔들림 자체가 181.의 통계적 MoC가 필요한
    이유다.
    """
    out = estimate_pd(hist["crm_default_history"],
                      floors=build_crm_input_floor(),
                      param=_approved_param(), asof=ASOF, seed=SEED)
    est = out["crm_pd_estimate"].set_index(["segment", "grade"])
    n_years = len(H._CYCLE_MULT) - 1                      # 유보연도 1년 제외
    scale = float(np.mean(H._CYCLE_MULT[:n_years]))
    for (segment, grade), (base, _n) in H._TRUE_PD.items():
        expected = base * scale
        got = float(est.loc[(segment, grade), "raw_estimate"])
        assert abs(got - expected) <= 0.30 * expected, (
            f"{segment}/{grade}: 기대 {expected:.5f} 실제 {got:.5f}")


def test_pd_pooled_average_differs_from_simple_average(hist):
    """차주수 가중 풀링평균이 단순평균보다 낮다 (침체 효과 희석).

    침체기에 코호트가 줄면 그 해의 높은 부도율이 풀링에서 작은 가중치를 받는다.
    두 해석의 차이를 ``basis_gap``으로 남기고 적용치는 단순평균(182.바)이다.
    """
    out = estimate_pd(hist["crm_default_history"],
                      floors=build_crm_input_floor(),
                      param=_approved_param(), asof=ASOF, seed=SEED)
    est = out["crm_pd_estimate"]
    assert (est["basis_gap"] > 0).all(), "풀링평균이 단순평균보다 낮지 않다"
    assert est["estimation_basis"].eq("장기평균(연도동일가중)").all()


def test_lgd_estimator_recovers_generation_parameters(hist):
    """LGD 추정기가 생성 목표 LGD를 되찾는다.

    할인율은 되찾을 대상이 아니라 은행이 정하는 입력이다(184.는 값을 주지
    않는다). 생성에 쓴 할인율과 같은 값을 원장에 승인해 넣고, 세그먼트 기저
    LGD를 되찾는지 본다. 침체 연도 부도건에 가산이 붙어 있으므로 회수종료 건
    평균은 기저보다 높다.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = estimate_lgd(hist["crm_recovery_history"],
                           hist["crm_default_history"],
                           floors=build_crm_input_floor(),
                           param=_approved_param(),
                           rates=_approved_rates(H._GEN_DISCOUNT_RATE),
                           asof=ASOF, seed=SEED)
    est = out["crm_lgd_estimate"].set_index("segment")
    for segment, base in H._TRUE_LGD.items():
        got = float(est.loc[segment, "lgd_excl_censored"])
        assert base <= got <= base + H._LGD_DOWNTURN_UPLIFT + 0.06, (
            f"{segment}: 기저 {base} 대비 {got}")


def test_lgd_rises_with_discount_rate(hist):
    """할인율이 높으면 LGD가 커진다. 할인율 하나가 LGD 전체를 움직인다."""
    per_low = realised_lgd(hist["crm_recovery_history"], discount_rate=0.02,
                           asof=ASOF)
    per_high = realised_lgd(hist["crm_recovery_history"], discount_rate=0.20,
                            asof=ASOF)
    assert per_high["lgd_realised"].mean() > per_low["lgd_realised"].mean()


def test_ccf_estimator_recovers_generation_parameters(ledgers_approved):
    """CCF 추정기가 생성 CCF를 되찾는다.

    부도가 침체 연도에 몰려 있고 침체 연도에는 생성 CCF에 가산이 붙으므로,
    부도가중평균은 기저와 기저+가산 사이에 놓인다.
    """
    est = ledgers_approved["crm_ccf_estimate"]
    est = est[est["segment"] == "corporate"].set_index("ccf_type")
    for ctype, base in H._TRUE_CCF.items():
        if ctype not in est.index:
            continue
        got = float(est.loc[ctype, "raw_estimate"])
        assert base - 0.05 <= got <= base + H._CCF_DOWNTURN_UPLIFT + 0.05, (
            f"{ctype}: 기저 {base} 대비 {got}")


# ---------------------------------------------------------------- 경계

@pytest.mark.parametrize("years,expect_corporate_lgd", [(6, False), (7, True)])
def test_minimum_observation_period_boundary(years, expect_corporate_lgd):
    """기업 LGD·EAD 최소 관측기간 7년(186.·195.) 경계에서 판정이 바뀐다."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        led = build_irb_estimation_ledgers(
            asof=ASOF, seed=SEED, years=years, param=_approved_param(),
            rates=_approved_rates())
    run = led["crm_estimation_run"]
    row = run[(run["parameter"] == "LGD")
              & (run["segment"] == "corporate")].iloc[0]
    assert bool(row["meets_minimum"]) is expect_corporate_lgd
    assert row["min_observation_years"] == pytest.approx(7.0)
    # 소매는 5년이므로 6년에서도 충족이다. 한 값으로 판정하면 이 차이가 사라진다.
    retail = run[(run["parameter"] == "LGD")
                 & (run["segment"] == "retail_other")].iloc[0]
    assert retail["min_observation_years"] == pytest.approx(5.0)
    assert bool(retail["meets_minimum"]) is True


def test_pd_floor_binds_at_boundary(hist):
    """PD 하한이 경계에서 문다. 하한을 올리면 최종치가 하한으로 올라간다."""
    floors = build_crm_input_floor()
    high = floors.copy()
    m = ((high["framework_version"] == "바젤3최종안")
         & (high["parameter"] == "pd_floor"))
    high.loc[m, "floor_value"] = 0.50
    out = estimate_pd(hist["crm_default_history"], floors=high,
                      param=_approved_param(), asof=ASOF, seed=SEED)
    est = out["crm_pd_estimate"]
    assert (est["final_applied"] >= 0.50 - 1e-12).all()
    assert est["floor_binding"].all()
    assert est["after_floor"].eq(0.50).all()


def test_missing_floor_warns_and_is_reported(hist):
    """하한이 NULL이면 조용히 넘어가지 않고 경고와 산출 결과에 남는다."""
    floors = build_crm_input_floor()
    blank = floors.copy()
    m = ((blank["framework_version"] == "바젤3최종안")
         & (blank["parameter"] == "pd_floor"))
    blank.loc[m, "floor_value"] = np.nan
    blank.loc[m, "floor_status"] = "미확인"
    with pytest.warns(ParamWarning):
        out = estimate_pd(hist["crm_default_history"], floors=blank,
                          param=_approved_param(), asof=ASOF, seed=SEED)
    assert out["crm_pd_estimate"]["floor_value"].isna().all()
    run = pd.DataFrame(out["run_rows"])
    assert (~run["floor_applied"]).all()
    assert run["unresolved_inputs"].str.contains("pd_floor").all()


def test_lgd_blocked_without_discount_rate(ledgers_default):
    """할인율이 없으면 LGD 산출을 건너뛰고 그 사실을 원장에 남긴다."""
    est = ledgers_default["crm_lgd_estimate"]
    assert (est["status"] == "산출불가").all()
    assert est["final_applied"].isna().all()
    assert est["discount_rate"].isna().all()
    assert (est["discount_rate_status"] == "미승인").all()
    # 할인 전 손실률은 관측 사실이라 남는다. 이것은 LGD가 아니다.
    assert est["undiscounted_loss_rate"].notna().all()
    run = ledgers_default["crm_estimation_run"]
    lgd_run = run[run["parameter"] == "LGD"]
    assert lgd_run["unresolved_inputs"].str.contains(
        "lgd_discount_rate").all()


def test_downturn_needs_approved_definition(hist):
    """침체기 정의가 승인 전이면 침체 연도를 식별하지 않는다."""
    plain = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    years, _, status = identify_downturn_years(hist["crm_default_history"],
                                               param=plain, asof=ASOF)
    assert years == [] and status == "기준미승인"
    years2, definition, status2 = identify_downturn_years(
        hist["crm_default_history"], param=_approved_param(), asof=ASOF)
    assert status2 == "산출완료" and len(years2) >= 1
    assert "185" in definition


def test_downturn_lgd_at_least_longrun(ledgers_approved):
    """185.가(1). 장기 부도가중평균이 하한이므로 원시추정치가 둘 중 크다."""
    est = ledgers_approved["crm_lgd_estimate"]
    assert (est["downturn_lgd"] >= est["longrun_default_weighted_lgd"]).all()
    assert (est["raw_estimate"]
            >= est["longrun_default_weighted_lgd"] - 1e-12).all()
    assert (est["raw_estimate"] >= est["downturn_lgd"] - 1e-12).all()


def test_ignoring_censored_workouts_is_optimistic(ledgers_approved):
    """관측중단 건을 빼면 LGD가 낙관적으로 나온다."""
    est = ledgers_approved["crm_lgd_estimate"]
    assert (est["n_censored"] > 0).all()
    assert (est["lgd_excl_censored"] < est["lgd_incl_censored"]).all()
    assert (est["censoring_impact"] > 0).all()


def test_ccf_zero_and_negative_denominators(hist):
    """분모가 0·음수인 건이 실제로 있고 집계에서 사라지지 않는다."""
    obs = observed_ccf(hist["crm_facility_drawdown_history"], asof=ASOF)
    assert (obs["exclusion_reason"] == "분모0(기준시 한도소진)").sum() > 0
    assert (obs["exclusion_reason"]
            == "분모음수(기준시 이후 한도축소)").sum() > 0
    assert obs.loc[obs["exclusion_reason"].notna(), "ccf_observed"].isna().all()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        led = build_irb_estimation_ledgers(asof=ASOF, seed=SEED, param=_approved_param(),
                                           rates=_approved_rates())
    ccf = led["crm_ccf_estimate"]
    total = (ccf["n_valid"] + ccf["n_zero_denominator"]
             + ccf["n_negative_denominator"])
    assert (total == ccf["n_facilities"]).all()
    assert (ccf["excluded_exposure_amount"] > 0).all()


def test_pd_ead_correlation_detected(ledgers_approved):
    """193.다(3). 부도율과 CCF의 정(+) 상관이 잡히고 추가 보수화가 표시된다."""
    ccf = ledgers_approved["crm_ccf_estimate"]
    assert ccf["pd_ead_correlation"].notna().any()
    positive = ccf[ccf["pd_ead_correlation"] > 0]
    assert len(positive) > 0
    assert positive["extra_conservatism_required"].all()
    # 추가 보수화의 크기는 규정이 주지 않으므로 비어 있다.
    assert positive["extra_conservatism_amount"].isna().all()


# ---------------------------------------------------------------- MoC

def test_moc_moves_conservatively_only(ledgers_approved):
    """MoC는 상향으로만 움직인다 (PD·LGD·CCF)."""
    for name in ("crm_pd_estimate", "crm_lgd_estimate", "crm_ccf_estimate"):
        df = ledgers_approved[name].dropna(subset=["after_floor", "after_moc"])
        assert len(df) > 0
        assert (df["after_moc"] >= df["after_floor"] - 1e-12).all(), name
        assert (df["moc_amount"].fillna(0.0) >= 0).all(), name


def test_moc_larger_for_small_samples():
    """표본이 작을수록 통계적 MoC가 커진다 (181. 조정폭 확대)."""
    param = _approved_param()
    stable = compute_moc(param=param, point_estimate=0.05,
                         yearly_estimates=[0.05, 0.051, 0.049, 0.05, 0.05],
                         representativeness_flagged=False)
    noisy = compute_moc(param=param, point_estimate=0.05,
                        yearly_estimates=[0.01, 0.09, 0.02, 0.08, 0.05],
                        representativeness_flagged=False)
    assert noisy.components["모형품질"] > stable.components["모형품질"]
    assert noisy.total > stable.total


def test_moc_unapproved_is_not_silently_zero():
    """크기 모수가 승인 전이면 MoC를 0으로 두지 않고 상태로 남긴다."""
    plain = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    res = compute_moc(param=plain, point_estimate=0.05,
                      yearly_estimates=[0.04, 0.06], representativeness_flagged=None)
    assert res.total is None
    assert res.status == "기준미승인"
    assert all(v is None for v in res.components.values())
    assert "moc_aggregation" in res.unresolved


# ---------------------------------------------------------------- 사후검증

def test_backtest_is_out_of_sample(ledgers_approved):
    """추정 표본에서 뺀 해로 검증한다 (203.라(1))."""
    bt = ledgers_approved["crm_backtest_result"]
    assert len(bt) > 0
    assert bt["out_of_sample"].all()
    pd_rows = bt[bt["parameter"] == "PD"]
    assert (pd_rows["backtest_year"]
            > pd_rows["estimation_window_end"]).all()
    yearly = ledgers_approved["crm_pd_yearly_dr"]
    assert (~yearly["in_estimation_sample"]).sum() > 0


def test_backtest_unjudged_without_thresholds(ledgers_default):
    """판정 임계가 승인 전이면 판정하지 않는다."""
    bt = ledgers_default["crm_backtest_result"]
    assert (bt["judgment_status"] == "기준미승인").all()
    assert bt["inside_range"].isna().all()
    assert bt["ci_level"].isna().all()


# ---------------------------------------------------------------- 음성 대조

def _report_status(fn, *args) -> str:
    rep = ValidationReport()
    fn(*args, rep)
    return rep.checks[-1].status if rep.checks else "없음"


def test_check_observation_minimum_fails_on_violation(ledgers_approved):
    run = ledgers_approved["crm_estimation_run"]
    assert _report_status(check_observation_minimum, run) == "PASS"
    bad = run.copy()
    bad.loc[bad.index[0], "observation_years"] = 1.0
    bad.loc[bad.index[0], "meets_minimum"] = True
    assert _report_status(check_observation_minimum, bad) == "FAIL"


def test_check_pd_floor_fails_on_violation(ledgers_approved):
    est = ledgers_approved["crm_pd_estimate"]
    assert _report_status(check_pd_floor, est) == "PASS"
    bad = est.copy()
    bad.loc[bad.index[0], "final_applied"] = 0.0
    bad.loc[bad.index[0], "floor_value"] = 0.0005
    assert _report_status(check_pd_floor, bad) == "FAIL"


def test_check_lgd_floor_fails_on_violation(ledgers_approved):
    est = ledgers_approved["crm_lgd_estimate"]
    assert _report_status(check_lgd_floor, est) == "PASS"
    bad = est.copy()
    m = bad["segment"] == "residential_mortgage"
    bad.loc[m, "final_applied"] = 0.01          # 주거용주택담보 하한 5% 미만
    assert _report_status(check_lgd_floor, bad) == "FAIL"


def test_check_downturn_floor_fails_on_violation(ledgers_approved):
    est = ledgers_approved["crm_lgd_estimate"]
    assert _report_status(check_downturn_floor, est) == "PASS"
    bad = est.copy()
    # max를 min으로 잘못 쓴 상태를 흉내낸다.
    bad["raw_estimate"] = bad[["longrun_default_weighted_lgd",
                               "downturn_lgd"]].min(axis=1) - 0.01
    assert _report_status(check_downturn_floor, bad) == "FAIL"


def test_check_moc_direction_fails_on_violation(ledgers_approved):
    ests = {k: ledgers_approved[k] for k in
            ("crm_pd_estimate", "crm_lgd_estimate", "crm_ccf_estimate")}
    assert _report_status(check_moc_direction, ests) == "PASS"
    bad = dict(ests)
    b = bad["crm_pd_estimate"].copy()
    b.loc[b.index[0], "after_moc"] = b.loc[b.index[0], "after_floor"] - 0.01
    bad["crm_pd_estimate"] = b
    assert _report_status(check_moc_direction, bad) == "FAIL"


def test_check_basis_domain_fails_on_violation(ledgers_approved):
    run = ledgers_approved["crm_estimation_run"]
    assert _report_status(check_basis_domain, run) == "PASS"
    bad = run.copy()
    bad.loc[bad["parameter"] == "PD", "estimation_basis"] = "부도가중평균"
    assert _report_status(check_basis_domain, bad) == "FAIL"


def test_check_backtest_out_of_sample_fails_on_violation(ledgers_approved):
    bt = ledgers_approved["crm_backtest_result"]
    assert _report_status(check_backtest_out_of_sample, bt) == "PASS"
    bad = bt.copy()
    bad.loc[bad.index[0], "out_of_sample"] = False
    assert _report_status(check_backtest_out_of_sample, bad) == "FAIL"


def test_check_backtest_range_fails_only_on_upper_breach(ledgers_approved):
    """실적이 범위를 상회하면 FAIL, 하회하면 WARN이다."""
    bt = ledgers_approved["crm_backtest_result"]
    over = bt.copy()
    over.loc[over.index[0], "judgment_status"] = "판정완료"
    over.loc[over.index[0], "inside_range"] = False
    over.loc[over.index[0], "breach_direction"] = "상회"
    assert _report_status(check_backtest_inside_range, over) == "FAIL"
    under = bt.copy()
    under["breach_direction"] = under["breach_direction"].where(
        under["breach_direction"] != "상회", "하회")
    assert _report_status(check_backtest_inside_range, under) in ("PASS", "WARN")


def test_check_censoring_disclosure_fails_on_violation(ledgers_approved):
    est = ledgers_approved["crm_lgd_estimate"]
    assert _report_status(check_censoring_disclosure, est) == "PASS"
    bad = est.copy()
    bad["censoring_impact"] = np.nan
    assert _report_status(check_censoring_disclosure, bad) == "FAIL"


def test_check_ccf_denominator_fails_on_violation(ledgers_approved):
    est = ledgers_approved["crm_ccf_estimate"]
    assert _report_status(check_ccf_denominator_accounting, est) == "PASS"
    bad = est.copy()
    bad.loc[bad.index[0], "n_zero_denominator"] = 0    # 제외 건을 지운 상태
    assert _report_status(check_ccf_denominator_accounting, bad) == "FAIL"


def test_check_ccf_floor_derivation_fails_on_constant(ledgers_approved):
    """하한을 20% 상수로 박으면 검사가 잡는다."""
    est = ledgers_approved["crm_ccf_estimate"]
    assert _report_status(check_ccf_floor_is_derived, est) == "PASS"
    bad = est.copy()
    bad["floor_value"] = 0.20
    assert _report_status(check_ccf_floor_is_derived, bad) == "FAIL"


def test_check_elbe_provision_justification(ledgers_approved):
    """ELBE가 개별충당금+부분상각보다 작으면 입증 문서를 요구한다."""
    dl = ledgers_approved["crm_defaulted_lgd"]
    assert _report_status(check_elbe_provision_justification, dl) == "PASS"
    bad = dl.copy()
    bad.loc[bad.index[0], "justification_required"] = True
    bad.loc[bad.index[0], "justification_ref"] = None
    assert _report_status(check_elbe_provision_justification, bad) == "FAIL"
    ok = bad.copy()
    ok.loc[ok.index[0], "justification_ref"] = "모형위원회 2026-03 의결"
    assert _report_status(check_elbe_provision_justification, ok) == "PASS"


def test_defaulted_lgd_provision_comparison(hist, ledgers_approved):
    """충당금 자료가 있으면 185.바의 비대칭 비교가 실제로 판정된다."""
    from risk_lib.models.estimation import build_defaulted_lgd
    small = pd.DataFrame({"segment": ["corporate"],
                          "specific_provision": [1e13],
                          "partial_writeoff": [0.0]})
    out = build_defaulted_lgd(hist["crm_recovery_history"],
                              ledgers_approved["crm_lgd_estimate"],
                              asof=ASOF, provisions=small)
    row = out[out["segment"] == "corporate"].iloc[0]
    assert row["shortfall"] > 0
    assert bool(row["justification_required"]) is True
    # 예상외손실 추가분은 근거 미확인이라 산출하지 않는다.
    assert pd.isna(row["unexpected_loss_addon"])
    assert row["addon_status"] == "미산출(근거미확인)"


def test_check_pd_estimate_wired(ledgers_approved):
    """추정 PD 최종치가 RWA 산출에 쓰이지 않으면 배선 단절로 FAIL."""
    est = ledgers_approved["crm_pd_estimate"]
    disconnected = pd.DataFrame({"pd": [0.0123456789, 0.02]})
    rep = ValidationReport()
    check_pd_estimate_wired(est, disconnected, rep)
    assert rep.checks[-1].status == "FAIL"
    connected = pd.DataFrame({"pd": est["final_applied"].head(3).to_numpy()})
    rep2 = ValidationReport()
    check_pd_estimate_wired(est, connected, rep2)
    assert rep2.checks[-1].status == "PASS"


def test_full_check_suite_has_no_failures(ledgers_default, ledgers_approved):
    """기본 산출물과 승인 산출물 모두 자체검증에서 FAIL이 없다."""
    for led in (ledgers_default, ledgers_approved):
        rep = run_irb_estimation_checks(led)
        fails = [c for c in rep.checks if c.status == "FAIL"]
        assert not fails, [str(c) for c in fails]
        assert len(rep.checks) >= 12


# ---------------------------------------------------------------- 결정론

def _fingerprint(ledgers: dict[str, pd.DataFrame]) -> str:
    h = hashlib.sha256()
    for name in sorted(ledgers):
        df = ledgers[name]
        h.update(name.encode())
        h.update(",".join(map(str, df.columns)).encode())
        h.update(pd.util.hash_pandas_object(df.astype(str),
                                            index=True).values.tobytes())
    return h.hexdigest()


def test_deterministic_same_process():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = build_irb_estimation_ledgers(asof=ASOF, seed=SEED)
        b = build_irb_estimation_ledgers(asof=ASOF, seed=SEED)
        c = build_irb_estimation_ledgers(asof=ASOF, seed=SEED + 1)
    assert _fingerprint(a) == _fingerprint(b)
    assert _fingerprint(a) != _fingerprint(c)


def test_deterministic_across_processes():
    """별도 프로세스에서도 지문이 같다.

    파이썬 내장 ``hash()``는 프로세스마다 솔트가 달라 식별자 생성에 쓰면 이
    시험이 깨진다. 산출 식별자는 sha256으로 만든다.
    """
    code = (
        "import warnings, hashlib, pandas as pd;"
        "warnings.simplefilter('ignore');"
        "from risk_lib.models.estimation import build_irb_estimation_ledgers as B;"
        f"L=B(asof='{ASOF}', seed={SEED});"
        "h=hashlib.sha256();"
        "[ (h.update(k.encode()), h.update(','.join(map(str,L[k].columns)).encode()),"
        "   h.update(pd.util.hash_pandas_object(L[k].astype(str), index=True).values.tobytes()))"
        "  for k in sorted(L)];"
        "print(h.hexdigest())")
    outs = []
    for _ in range(2):
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=600)
        assert r.returncode == 0, r.stderr[-2000:]
        outs.append(r.stdout.strip())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        local = _fingerprint(build_irb_estimation_ledgers(asof=ASOF, seed=SEED))
    assert outs[0] == outs[1] == local


def test_history_is_deterministic_and_labelled():
    """관측이력이 결정론이고 합성 표시를 달고 있다."""
    a = build_crm_default_history(asof=ASOF, seed=SEED)
    b = build_crm_default_history(asof=ASOF, seed=SEED)
    pd.testing.assert_frame_equal(a, b)
    assert (a["source_system"] == "synthetic").all()
    assert a["default_date"].notna().sum() == int(a["default_flag"].sum())
    # 등급부여일이 코호트 구성일보다 앞선다. 뒤면 생존편의다.
    assert (a["rating_assigned_date"] < a["cohort_start_date"]).all()
    assert set(a["cycle_phase"]) == {"정상", "침체"}
