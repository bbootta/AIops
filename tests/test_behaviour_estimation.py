"""행동모형 추정 엔진. 불변식 고정.

이 파일의 규칙: **통과만으로는 통제가 아니다.** 각 검사는 결함을 되돌렸을 때
실제로 실패해야 하고, 정합성 검사 6종은 위반을 직접 주입해 FAIL을 확인한다.

특히 두 가지를 겨냥한다.

  · **자기 정답 보기.** 합성 생성 모수(`behaviour_history._GEN_*`)는 추정기에
    넘어가지 않는다. 테스트만 그 상수를 읽어 대조한다. 생성기와 추정기가 모수를
    공유하면 회복 테스트는 아무것도 검증하지 않는다.
  · **누수.** 표본외 구간의 관측치를 흔들어도 적합계수가 바뀌지 않아야 한다.
    바뀌면 검증기간이 추정에 들어간 것이고, 그때 사후검증은 언제나 통과한다.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from risk_lib.alm import behaviour_estimation as BE
from risk_lib.alm import behaviour_history as BH
from risk_lib.alm.behaviour import psa_cpr, seasoning_ramp, smm_from_cpr
from risk_lib.alm.params import build_param_ledgers
from risk_lib.datamodel.spec import validate

ASOF = "2026-08-08"
SEED = 42
BASE_RATE = 0.0315
REPO = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- 픽스처

@pytest.fixture(scope="module")
def history() -> dict[str, pd.DataFrame]:
    return BH.build_behaviour_history(ASOF, seed=SEED, base_rate=BASE_RATE)


@pytest.fixture(scope="module")
def params() -> dict[str, pd.DataFrame]:
    return build_param_ledgers(ASOF)


@pytest.fixture(scope="module")
def estimates(history) -> BE.EstimationResult:
    return BE.run_estimation(history, asof=ASOF)


@pytest.fixture(scope="module")
def shock_bp() -> float:
    """KRW 평행충격은 원장에서 읽는다. 테스트에도 규제값을 박지 않는다."""
    from risk_lib.alm import curves as ac
    sp = ac.build_curve_ledgers()["alm_rate_shock_param"]
    hit = sp[(sp["framework_version"] == "별표9의1_2026")
             & (sp["ccy"] == "KRW") & (sp["shock_type"] == "parallel")]
    return float(hit["shock_bp"].iloc[0])


@pytest.fixture(scope="module")
def ledgers(estimates, history, params, shock_bp) -> dict[str, pd.DataFrame]:
    return BE.build_estimation_ledgers(
        estimates, history, params["alm_nmd_param"], params["alm_time_bucket"],
        shock_bp=shock_bp)


@pytest.fixture(scope="module")
def contracts() -> pd.DataFrame:
    from risk_lib.alm.balance_sheet import generate_balance_sheet
    from risk_lib.alm.contracts import build_contract_ledger
    from risk_lib.data_gen import generate_portfolio
    pf = generate_portfolio(seed=SEED)
    bs = generate_balance_sheet(pf, 1.0e13, seed=SEED, asof=ASOF)
    return build_contract_ledger(pf, asof=ASOF, funding=bs.funding, hqla=bs.hqla,
                                 equity=bs.equity, base_rate=BASE_RATE, seed=SEED)


def _cashflows(p: dict[str, pd.DataFrame], contracts: pd.DataFrame):
    from risk_lib.alm.cashflow import build_cashflows
    return build_cashflows(
        contracts, asof=ASOF, product_terms=p["alm_product_terms"],
        buckets=p["alm_time_bucket"], behaviour_param=p["alm_behaviour_param"],
        scenario_mult=p["alm_behaviour_scenario_mult"],
        nmd_param=p["alm_nmd_param"], scurve_param=p["alm_prepay_scurve_param"])


# ---------------------------------------------------------------- 관측이력 원장

def test_history_ledgers_satisfy_their_specs(history):
    for spec in BH.HISTORY_TABLES:
        v = validate(history[spec.name], spec)
        assert not v, f"{spec.name}: {[str(x) for x in v]}"


def test_observed_smm_reproduces_from_amounts(history):
    """관측 SMM이 금액에서 재현되는가. SIFMA 분모 순서가 지켜졌는지 본다.

    분모에서 약정상환액을 빼기 전에 SMM을 걸면 조기상환액이 과대계상되고 그
    오차가 만기까지 복리된다. 금액과 비율이 서로 재현되지 않으면 추정기가 어느
    쪽을 읽었는지에 따라 CPR₀가 갈린다.
    """
    d = history["alm_prepay_observation"]
    recomputed = d["excess_principal"] / (d["opening_balance"]
                                          - d["scheduled_principal"])
    assert np.allclose(recomputed, d["observed_smm"], atol=1e-12)
    annual = 1.0 - (1.0 - d["observed_smm"]) ** 12
    assert np.allclose(annual, d["observed_cpr_annual"], atol=1e-12)
    # 잘못된 순서(약정분을 빼지 않은 분모)는 다른 값을 준다. 검사가 무의미하지
    # 않다는 음성 대조.
    wrong = d["excess_principal"] / d["opening_balance"]
    assert not np.allclose(wrong, d["observed_smm"], atol=1e-6)


def test_nmd_history_leaves_pass_through_null_when_rate_did_not_move(history):
    d = history["alm_nmd_balance_history"]
    flat = d[d["policy_rate_change_bp"].fillna(0.0).abs() < 1e-12]
    assert len(flat) > 0, "시장금리가 멈춘 달이 없으면 결측 처리가 시험되지 않는다"
    assert flat["observed_pass_through"].isna().all()


def test_history_is_deterministic_and_seed_sensitive():
    a = BH.build_behaviour_history(ASOF, seed=SEED, base_rate=BASE_RATE)
    b = BH.build_behaviour_history(ASOF, seed=SEED, base_rate=BASE_RATE)
    c = BH.build_behaviour_history(ASOF, seed=SEED + 1, base_rate=BASE_RATE)
    for k in a:
        pd.testing.assert_frame_equal(a[k], b[k])
        assert not a[k].equals(c[k]), f"{k}: 시드를 바꿔도 같다. 난수를 안 쓴다"


def test_month_labels_exclude_the_partial_asof_month():
    m = BH.month_labels("2026-08-08", 3)
    assert m == ["2026-05", "2026-06", "2026-07"]


# ---------------------------------------------------------------- 회복 검증

def test_prepayment_recovers_generator_parameters(estimates):
    """생성 모수를 추정기에 넘기지 않고 되찾는가.

    S-curve의 b와 c는 개별로는 약하게 식별된다. 인센티브 관측범위 안에서
    `b·arctan(c·x) ≈ b·c·x` 이므로 곱이 식별되는 조합이다. 그래서 곱에 좁은
    허용오차를, 개별 계수에 넓은 허용오차를 건다. 곱까지 느슨하게 두면 검사가
    아무것도 잡지 못한다.
    """
    g = BH._GEN_PREPAY
    f = estimates.prepay[0]
    assert f.converged and f.status == "수렴"
    assert f.ramp.ceiling == pytest.approx(g.ramp_ceiling, rel=0.12)
    assert f.ramp.slope == pytest.approx(g.ramp_slope, rel=0.12)
    assert (f.scurve.b * f.scurve.c) == pytest.approx(
        g.scurve_b * g.scurve_c, rel=0.10)
    assert f.scurve.b == pytest.approx(g.scurve_b, rel=0.30)
    assert f.scurve.c == pytest.approx(g.scurve_c, rel=0.35)
    assert f.scurve.d == pytest.approx(g.scurve_d, abs=0.001)
    assert f.r_squared > 0.9
    assert 0.0 < f.headline_cpr0 < 1.0


def test_early_redemption_recovers_penalty_and_gap_coefficients(estimates):
    """위약금이 해지를 억제하고 금리차가 촉진하는가. 부호와 크기 둘 다 본다."""
    g = BH._GEN_TDRR
    t = estimates.tdrr[0]
    assert t.converged and t.model_family == "logistic"
    assert t.coef["penalty_rate"] < 0.0, "위약금 계수가 음수가 아니면 제10항 가의 전제와 어긋난다"
    assert t.coef["rate_gap"] > 0.0
    assert t.coef["rate_gap"] == pytest.approx(g.beta_gap, rel=0.15)
    assert t.coef["penalty_rate"] == pytest.approx(g.beta_penalty, rel=0.20)
    assert t.coef["residual_maturity"] == pytest.approx(g.beta_maturity, rel=0.40)
    assert 0.0 < t.headline_tdrr0 < 1.0


def test_pass_through_beta_recovers_per_category(estimates):
    for b in estimates.nmd_beta:
        true = BH._GEN_NMD[b.nmd_category].pass_through_beta
        assert b.converged, b.message
        assert b.beta_applied == pytest.approx(true, rel=0.10)
        assert not b.clipped
    betas = sorted(b.beta_applied for b in estimates.nmd_beta)
    assert betas[0] < betas[-1], "범주별 전가율이 같으면 범주 구분이 산출에 닿지 않는다"


# ---------------------------------------------------------------- 소진(burnout)

def test_burnout_option_is_recorded_and_weak_identification_is_reported(
        history, ledgers):
    """소진 반영 여부가 원장에 남고, 약식별이면 계수를 0으로 되돌리는가.

    풀이 하나면 누적 조기상환 경험이 경과월과 거의 단조 동행하므로 소진 감쇠가
    램프 천장에 흡수된다. 그때 격자가 고른 φ는 자료가 정한 값이 아니다.
    """
    obs = history["alm_prepay_observation"]
    on = BE.estimate_prepayment(obs, portfolio_id="mortgage", include_burnout=True)
    off = BE.estimate_prepayment(obs, portfolio_id="mortgage", include_burnout=False)
    assert on.burnout_included and not off.burnout_included
    assert off.burnout_phi is None
    assert on.burnout_ssr_gain is not None
    if not on.burnout_identified:
        assert on.burnout_phi == 0.0
        assert on.burnout_ssr_gain < BE.INTERNAL.burnout_min_ssr_gain
        assert "미식별" in on.message

    row = ledgers["alm_behaviour_model"].query("model == 'CPR'").iloc[0]
    assert bool(row["burnout_included"]) is True
    assert "burnout_identified" in str(row["params_json"])


# ---------------------------------------------------------------- 수렴 실패

def _degenerate_prepay(history: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """인센티브가 표본 안에서 상수인 관측. c·d가 식별되지 않는다."""
    d = history["alm_prepay_observation"].copy()
    d["refi_incentive_bp"] = float(d["refi_incentive_bp"].iloc[0])
    return d


def test_scurve_failure_leaves_portfolio_unestimated(history):
    d = _degenerate_prepay(history)
    f = BE.estimate_prepayment(d, portfolio_id="mortgage")
    assert not f.converged
    assert f.status in ("수렴실패", "표본무변동")
    assert f.headline_cpr0 is None and f.ramp is None and f.scurve is None
    assert "미추정" in f.message


def test_fit_scurve_reports_failure_instead_of_last_iterate():
    x = np.full(40, 0.003)
    y = np.linspace(0.02, 0.06, 40)
    fit = BE.fit_scurve(x, y)
    assert not fit.converged and fit.status == "표본무변동"
    assert all(np.isnan(v) for v in (fit.a, fit.b, fit.c, fit.d))


def test_unconverged_model_does_not_reach_the_param_ledgers(history, params):
    """수렴 실패면 계수 원장이 그대로여야 한다. 조용히 기본값을 쓰면 안 된다."""
    res = BE.run_estimation({"alm_prepay_observation": _degenerate_prepay(history)},
                            asof=ASOF)
    out = BE.apply_estimates(params, res)
    cpr = out["alm_behaviour_param"].query("model == 'CPR'")
    assert cpr["base_rate_annual"].isna().all()
    assert cpr["input_source"].iloc[0] == "표준벤치마크"
    sc = out["alm_prepay_scurve_param"]
    assert not sc["enabled"].astype(bool).any()
    assert sc[["coef_a", "coef_b", "coef_c", "coef_d"]].isna().all().all()
    assert "미추정" in str(sc["note"].iloc[0])

    ck = BE.check_unconverged_left_unestimated(
        BE.build_behaviour_model_ledger(res), out["alm_behaviour_param"], sc)
    assert ck.status == "PASS"


def test_unconverged_check_fails_when_a_value_is_injected(history, params):
    """음성 대조. 수렴 실패 모형의 계수가 채워지면 검사가 FAIL해야 한다."""
    res = BE.run_estimation({"alm_prepay_observation": _degenerate_prepay(history)},
                            asof=ASOF)
    bad_sc = params["alm_prepay_scurve_param"].copy()
    bad_sc.loc[:, "enabled"] = True
    bad_sc.loc[:, "coef_a"] = 0.05
    ck = BE.check_unconverged_left_unestimated(
        BE.build_behaviour_model_ledger(res), params["alm_behaviour_param"], bad_sc)
    assert ck.status == "FAIL" and "채워졌다" in ck.detail


def test_tdrr_reports_failure_when_penalty_never_changes(history):
    d = history["alm_early_redemption_observation"].copy()
    d["penalty_rate"] = float(d["penalty_rate"].iloc[0])
    t = BE.estimate_early_redemption(d, portfolio_id="term_deposit")
    assert not t.converged and t.status == "표본무변동"
    assert t.coef == {} and t.headline_tdrr0 is None


def test_sample_shorter_than_internal_minimum_is_not_estimated(history):
    d = history["alm_prepay_observation"].head(20)
    f = BE.estimate_prepayment(d, portfolio_id="mortgage")
    assert not f.converged and f.status == "표본부족"


# ---------------------------------------------------------------- <표3> 상한

def test_table3_cap_binds_at_the_boundary():
    """경계에서 무는가. 상한과 같은 값은 '적용'이 아니고, 넘으면 잘린다."""
    core, bind, mat, mbind = BE.apply_table3_caps(
        0.90, 5.0, core_cap=0.90, maturity_cap=5.0)
    assert (core, bind, mat, mbind) == (0.90, False, 5.0, False)

    core, bind, mat, mbind = BE.apply_table3_caps(
        0.9000001, 5.0000001, core_cap=0.90, maturity_cap=5.0)
    assert core == 0.90 and bind is True
    assert mat == 5.0 and mbind is True

    # 평균만기 추정치가 없으면(감쇠율 음수) 상한이 그 자리를 대체하고, 대체
    # 사실이 값에 남는다.
    core, bind, mat, mbind = BE.apply_table3_caps(
        0.40, None, core_cap=0.50, maturity_cap=4.0)
    assert (core, bind, mat, mbind) == (0.40, False, 4.0, True)


def test_cap_check_fails_when_a_violation_is_injected(ledgers):
    good = BE.check_table3_cap_binds(ledgers["alm_nmd_core_method_compare"])
    assert good.status == "PASS"
    bad = ledgers["alm_nmd_core_method_compare"].copy()
    bad.loc[bad.index[0], "core_ratio"] = 0.99
    assert BE.check_table3_cap_binds(bad).status == "FAIL"


def test_estimated_core_never_exceeds_the_stable_share(estimates):
    """코어 ⊆ 안정예금. 제8항 나(1)(2)의 2단계 분해가 뒤집히면 안 된다."""
    for e in estimates.nmd_core:
        assert e.core_ratio_raw <= e.stable_ratio + 1e-12


# ---------------------------------------------------------------- 표본외 검증

def test_backtest_window_does_not_overlap_the_estimation_window(ledgers):
    bt, ml = ledgers["alm_behaviour_backtest"], ledgers["alm_behaviour_model"]
    assert len(bt) > 0
    assert bt["is_out_of_time"].astype(bool).all()
    assert BE.check_backtest_is_out_of_time(bt, ml).status == "PASS"


def test_out_of_time_check_fails_on_an_overlapping_window(ledgers):
    bt = ledgers["alm_behaviour_backtest"].copy()
    ml = ledgers["alm_behaviour_model"]
    bt.loc[bt.index[0], "validation_window_start"] = str(
        ml.query("model == 'CPR'")["estimation_window_start"].iloc[0])[:7]
    assert BE.check_backtest_is_out_of_time(bt, ml).status == "FAIL"


def test_out_of_time_error_exceeds_in_sample_error_for_cpr(ledgers):
    """표본외가 표본내보다 나쁘게 나오는가. 같으면 누수다.

    합성자료의 표본 뒤쪽에는 국면전환이 들어 있다. 국내 실증에서 조기상환
    회귀계수가 국면에 따라 달라진다는 보고를 반영한 것이며, 표본외 검증이
    드러내야 하는 것이 정확히 그 편의다.
    """
    row = ledgers["alm_behaviour_backtest"].query("model == 'CPR'").iloc[0]
    assert row["mae_pp"] > row["in_sample_mae_pp"]


def test_perturbing_the_holdout_does_not_move_the_fitted_parameters(history):
    """누수 직접 검사. 검증구간 관측치를 흔들어도 계수가 바뀌면 안 된다."""
    obs = history["alm_prepay_observation"]
    base = BE.estimate_prepayment(obs, portfolio_id="mortgage")
    tampered = obs.copy()
    tail = tampered.index[-BE.INTERNAL.oos_months:]
    tampered.loc[tail, "observed_cpr_annual"] *= 3.0
    moved = BE.estimate_prepayment(tampered, portfolio_id="mortgage")
    assert moved.ramp.ceiling == base.ramp.ceiling
    assert moved.ramp.slope == base.ramp.slope
    assert moved.scurve.b == base.scurve.b and moved.scurve.c == base.scurve.c


def test_backtest_judgement_is_withheld_until_a_threshold_is_approved(
        estimates, history):
    """임계가 없으면 '판정보류'다. 지어낸 임계로 PASS를 찍지 않는다."""
    held = BE.build_behaviour_backtest_ledger(estimates, history)
    assert (held["judgement"] == "판정보류").all()
    assert held["threshold_mae_pp"].isna().all()

    approved = BE.build_behaviour_backtest_ledger(
        estimates, history, threshold_mae_pp=0.5,
        approved_by="ALM위원회", approved_on="2026-08-08")
    assert set(approved["judgement"]) <= {"적합", "부적합"}
    assert (approved["approved_by"] == "ALM위원회").all()
    strict = BE.build_behaviour_backtest_ledger(
        estimates, history, threshold_mae_pp=0.0, approved_by="ALM위원회",
        approved_on="2026-08-08")
    assert (strict["judgement"] == "부적합").all()


# ---------------------------------------------------------------- 코어 3방법

def test_three_core_methods_move_delta_eve(ledgers):
    c = ledgers["alm_nmd_core_method_compare"]
    assert set(c["method"]) == set(BE.NMD_CORE_METHODS)
    spread = (c.groupby("nmd_category")["delta_eve_proxy_krw"]
               .agg(lambda s: float(s.max() - s.min())))
    assert float(spread.max()) > 0.0
    assert BE.check_core_methods_differ(c).status in ("PASS", "WARN")


def test_core_method_check_fails_when_all_methods_collapse(ledgers):
    c = ledgers["alm_nmd_core_method_compare"].copy()
    c["delta_eve_proxy_krw"] = 1.0
    ck = BE.check_core_methods_differ(c)
    assert ck.status == "FAIL" and "닿지 않았다" in ck.detail


def test_headline_core_method_is_flagged_exactly_once_per_category(ledgers):
    c = ledgers["alm_nmd_core_method_compare"]
    counts = c.groupby("nmd_category")["is_headline"].sum()
    assert (counts == 1).all()


# ---------------------------------------------------------------- 결과 원장

def test_estimation_ledgers_satisfy_their_specs(ledgers):
    for spec in BE.ESTIMATION_TABLES:
        v = validate(ledgers[spec.name], spec)
        assert not v, f"{spec.name}: {[str(x) for x in v]}"


def test_model_ledger_carries_the_conventions_the_regulation_left_open(ledgers):
    ml = ledgers["alm_behaviour_model"]
    cpr = ml.query("model == 'CPR'").iloc[0]
    tdrr = ml.query("model == 'TDRR'").iloc[0]
    assert "연율" in str(cpr["horizon_convention"])
    assert "제10항" in str(tdrr["horizon_convention"])
    assert set(ml["evidence_status"]) == {"재량·미규정"}
    assert ml["approved_by"].isna().all(), "승인 전인데 승인자가 채워져 있다"


# ---------------------------------------------------------------- 계수 원장 갱신

def test_apply_estimates_does_not_mutate_the_input_ledgers(params, estimates):
    before = {k: v.copy() for k, v in params.items()}
    BE.apply_estimates(params, estimates)
    for k, v in before.items():
        pd.testing.assert_frame_equal(params[k], v)


def test_apply_estimates_fills_the_gaps_that_blocked_the_engines(
        params, estimates, ledgers):
    out = BE.apply_estimates(params, estimates,
                             backtest=ledgers["alm_behaviour_backtest"])
    bp = out["alm_behaviour_param"]
    assert bp["base_rate_annual"].notna().all()
    assert set(bp["input_source"]) == {"자체추정"}
    assert bp["estimation_window_start"].notna().all()
    assert bp["backtest_mae_pp"].notna().all()

    sc = out["alm_prepay_scurve_param"]
    assert sc["enabled"].astype(bool).all()
    assert sc[["coef_a", "coef_b", "coef_c", "coef_d"]].notna().all().all()
    # 추정에 쓴 인센티브 정의에 수수료가 없으므로 적용 단계에서도 빼지 않는다.
    assert not sc["deduct_prepay_fee"].astype(bool).any()

    nmd = out["alm_nmd_param"]
    assert nmd["pass_through_beta"].notna().all()
    assert nmd["stable_ratio"].notna().all()
    assert (nmd["core_ratio"] <= nmd["core_ratio_cap"] + 1e-12).all()
    assert (nmd["avg_maturity_years"] <= nmd["avg_maturity_cap_years"] + 1e-12).all()


def test_updated_param_ledgers_still_satisfy_their_specs(params, estimates,
                                                         ledgers):
    """추정값을 채운 뒤에도 계수 원장이 스펙을 지키는가.

    값을 써 넣으면서 dtype이나 허용값을 깨면 원장은 채워졌는데 검증에서
    되돌아온다.
    """
    from risk_lib.alm.params import PARAM_TABLES
    out = BE.apply_estimates(params, estimates,
                             backtest=ledgers["alm_behaviour_backtest"])
    for spec in PARAM_TABLES:
        if spec.name not in out:
            continue
        v = validate(out[spec.name], spec)
        assert not v, f"{spec.name}: {[str(x) for x in v]}"


def test_estimates_move_the_behavioural_cashflows(params, estimates, contracts):
    """배선 검사. 계수 원장에 값이 들어갔다는 사실은 산출이 그것을 읽었다는
    근거가 아니다."""
    out = BE.apply_estimates(params, estimates)
    before = _cashflows(params, contracts)
    after = _cashflows(out, contracts)
    ck = BE.check_estimate_moves_cashflow(before.behavioural, after.behavioural)
    assert ck.status == "PASS", ck.detail
    # 음성 대조. 같은 모수로 두 번 돌리면 검사가 FAIL해야 한다.
    same = BE.check_estimate_moves_cashflow(before.behavioural,
                                            before.behavioural)
    assert same.status == "FAIL"


def test_estimates_close_the_tdrr_and_nmd_param_warnings(params, estimates,
                                                         contracts):
    before = _cashflows(params, contracts)
    after = _cashflows(BE.apply_estimates(params, estimates), contracts)
    params_before = {w.param for w in before.warnings}
    assert "base_rate_annual" in params_before, "TDRR 결손이 처음부터 없으면 검사가 무의미하다"
    assert len(after.warnings) < len(before.warnings)


def test_pass_through_gap_closes_in_delta_nii(params, estimates, contracts):
    from risk_lib.alm import curves as ac, irrbb as ai, nii as an
    from risk_lib.pipeline import (ALM_CCY, ALM_FRAMEWORK_VERSION,
                                   ALM_NII_HORIZON_YEARS, _alm_risk_factor)
    cl = ac.build_curve_ledgers()
    base = ac.base_curve(_alm_risk_factor(ASOF, SEED), asof=ASOF)
    curves = {ALM_CCY: base}
    shocked, _ = ai.build_shocked_curves(
        curves, scenarios=ai.SCENARIOS, shock_param=cl["alm_rate_shock_param"],
        scenario_def=cl["alm_scenario_def"], floor=cl["alm_post_shock_floor"],
        framework_version=ALM_FRAMEWORK_VERSION, allow_proxy=True)

    def nii(p):
        return an.compute_delta_nii(
            contracts, p["alm_product_terms"], asof=ASOF,
            horizon_years=ALM_NII_HORIZON_YEARS, curves=curves, shocked=shocked,
            scenario_def=cl["alm_scenario_def"], nmd_param=p["alm_nmd_param"])

    b = nii(params).result
    a = nii(BE.apply_estimates(params, estimates)).result
    assert float(b["excluded_notional_ratio"].max()) > 0.0
    ck = BE.check_pass_through_gap_closed(b, a)
    assert ck.status == "PASS" and float(a["excluded_notional_ratio"].max()) == 0.0
    assert BE.check_pass_through_gap_closed(b, b).status == "FAIL"


# ---------------------------------------------------------------- 변환·결정론

def test_cpr_smm_round_trip():
    for cpr in (0.01, 0.06, 0.25):
        smm = smm_from_cpr(cpr, 1.0 / 12.0)
        assert BE.cpr_from_smm(smm, 1.0 / 12.0) == pytest.approx(cpr, rel=1e-12)
    # 선형근사와 다르다는 것을 고정한다. 같으면 근사를 쓰고 있는 것이다.
    assert BE.cpr_from_smm(0.005, 1.0 / 12.0) != pytest.approx(0.06, rel=1e-6)


def test_seasoning_ramp_reproduces_psa_at_the_sifma_coefficients():
    for age in (0.0, 12.0, 30.0, 60.0):
        assert seasoning_ramp(age, ceiling=0.06, slope=0.002) == psa_cpr(age)
    # 계수를 바꾸면 값이 바뀐다. 함수형이 계수를 실제로 읽는다.
    assert seasoning_ramp(20.0, ceiling=0.09, slope=0.003) != psa_cpr(20.0)


def _ledger_digest(asof: str, seed: int, base_rate: float) -> str:
    h = BH.build_behaviour_history(asof, seed=seed, base_rate=base_rate)
    res = BE.run_estimation(h, asof=asof)
    p = build_param_ledgers(asof)
    from risk_lib.alm import curves as ac
    sp = ac.build_curve_ledgers()["alm_rate_shock_param"]
    hit = sp[(sp["framework_version"] == "별표9의1_2026")
             & (sp["ccy"] == "KRW") & (sp["shock_type"] == "parallel")]
    led = BE.build_estimation_ledgers(
        res, h, p["alm_nmd_param"], p["alm_time_bucket"],
        shock_bp=float(hit["shock_bp"].iloc[0]))
    m = hashlib.sha256()
    for k in sorted(led):
        m.update(k.encode())
        m.update(led[k].to_csv(index=False).encode())
    return m.hexdigest()


def test_estimation_is_byte_identical_within_the_process():
    assert _ledger_digest(ASOF, SEED, BASE_RATE) == _ledger_digest(
        ASOF, SEED, BASE_RATE)


def test_estimation_is_byte_identical_in_a_separate_process():
    """별도 프로세스에서도 같은가. 솔트된 hash()나 벽시계가 섞이면 갈린다."""
    mine = _ledger_digest(ASOF, SEED, BASE_RATE)
    code = (
        "import sys; sys.path.insert(0, r'%s');\n"
        "from tests.test_behaviour_estimation import _ledger_digest, ASOF, SEED, BASE_RATE\n"
        "print(_ledger_digest(ASOF, SEED, BASE_RATE))" % REPO)
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                         capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == mine


def test_run_estimation_checks_returns_every_designed_check(
        ledgers, params, estimates, contracts):
    out = BE.apply_estimates(params, estimates)
    before = _cashflows(params, contracts).behavioural
    after = _cashflows(out, contracts).behavioural
    checks = BE.run_estimation_checks(
        compare=ledgers["alm_nmd_core_method_compare"],
        backtest=ledgers["alm_behaviour_backtest"],
        model_ledger=ledgers["alm_behaviour_model"],
        behaviour_param=out["alm_behaviour_param"],
        scurve_param=out["alm_prepay_scurve_param"],
        cf_before=before, cf_after=after)
    assert {c.name for c in checks} == {
        "alm_nmd_table3_cap_binds", "alm_backtest_out_of_time",
        "alm_unconverged_left_unestimated", "alm_nmd_core_methods_differ",
        "alm_behaviour_estimate_moves_cashflow"}
    assert all(c.status in ("PASS", "WARN") for c in checks), [
        (c.name, c.status, c.detail) for c in checks if c.status == "FAIL"]
