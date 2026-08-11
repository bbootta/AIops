"""CAPM 회수 할인율 추정 시험.

시험의 축은 다섯이다.

1. **되찾기.** 합성 은행주 계열의 생성 베타를 회귀 추정기가 허용오차 안에서
   되찾는가. 생성 베타는 ``discount_capm``의 생성 모수 구역에만 있고 추정기는
   그것을 읽지 않는다.
2. **경계.** 시장위험프리미엄이 0 이하이면 k_e를 내지 않는가. 승인된 시장수익률이
   들어오면 그때 비로소 나오는가.
3. **승인.** 승인을 거치지 않고 할인율이 원장에 들어가는 경로가 없는가.
4. **음성 대조.** 자체검사에 위반을 주입하면 실제로 FAIL이 뜨는가.
5. **결정론.** 같은 (asof, seed)면 별도 프로세스에서도 결과가 같은가.

그리고 이 작업의 목적, **LGD가 실제로 산출되기 시작하는지**를 확인한다.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
import pytest

from risk_lib.datamodel.spec import validate
from risk_lib.models.estimation import (
    ParamWarning, approve_estimation_param, build_estimation_param_ledgers,
    build_irb_estimation_ledgers, unapproved_internal_params,
)
from risk_lib.models.estimation import discount_capm as D
from risk_lib.models.estimation.discount_capm import (
    CAPM_APPROVER, CAPM_ESTIMATE, CAPM_EVIDENCE, CAPM_OBSERVATION,
    apply_capm_discount_rates, build_capm_discount_ledgers,
    build_crm_capm_estimate, build_crm_capm_observation,
    check_capm_evidence_disclosed, check_capm_recalculation,
    check_discount_rate_approved, check_lgd_increases_with_discount_rate,
    check_riskfree_scope_below_total, estimate_capm_discount_rate,
    run_capm_checks,
)
from risk_lib.models.estimation.params import build_crm_lgd_discount_rate
from risk_lib.validation.consistency import ValidationReport

ASOF = "2026-06-30"
SEED = 42
# 시험용 승인 기록이다. 규정 수치가 아니고 저장소 산출물의 기본값도 아니다.
# 관측 원장의 KOSPI에 표류항이 없어 실현 프리미엄이 음수이므로, 이 값이 없으면
# k_e가 나오지 않는다는 사실 자체가 아래 시험의 대상이다.
_APPROVED_MARKET_RETURN = 0.09


def _param_with_market_return(value: float | None = _APPROVED_MARKET_RETURN):
    p = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    if value is None:
        return p
    return approve_estimation_param(
        p, code="capm_market_return", value=value, approved_by="시험",
        approval_date="2026-01-01", approval_body="모형위원회")


@pytest.fixture(scope="module")
def obs() -> pd.DataFrame:
    return build_crm_capm_observation(asof=ASOF, seed=SEED)


@pytest.fixture(scope="module")
def approved() -> dict[str, pd.DataFrame]:
    """시장수익률이 승인된 상태의 CAPM 원장 묶음."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_capm_discount_ledgers(asof=ASOF, seed=SEED,
                                           param=_param_with_market_return())


# ---------------------------------------------------------------- 원장 스펙

def test_observation_and_estimate_pass_spec(obs, approved):
    """두 원장이 자기 스펙을 통과하고 기본키가 유일하다."""
    assert not validate(obs, CAPM_OBSERVATION), [
        str(v) for v in validate(obs, CAPM_OBSERVATION)]
    assert not obs.duplicated(subset=["asof", "period"]).any()
    assert len(obs) == D.N_PERIODS_DEFAULT
    est = approved["crm_capm_estimate"]
    assert not validate(est, CAPM_ESTIMATE), [
        str(v) for v in validate(est, CAPM_ESTIMATE)]
    assert len(est) == 1


def test_observation_declares_that_it_is_synthetic(obs):
    """합성 계열이라는 사실이 원장 칸에 있다. 실측과 섞이면 안 된다."""
    assert (obs["bank_return_source"] == "합성관측").all()
    assert (obs["source_system"] == "synthetic").all()
    assert (obs["evidence_status"] == CAPM_EVIDENCE).all()
    assert (obs["market_indicator"] == "KOSPI").all()
    assert (obs["riskfree_indicator"] == "KTB3Y").all()


def test_excess_returns_are_returns_minus_riskfree(obs):
    """초과수익률 두 칸이 정의대로다. 회귀 입력이 원장에서 재현된다."""
    assert np.allclose(obs["excess_market_return"],
                       obs["market_return"] - obs["riskfree_return"])
    assert np.allclose(obs["excess_bank_return"],
                       obs["bank_equity_return"] - obs["riskfree_return"])


# ---------------------------------------------------------------- 되찾기

def test_estimator_recovers_generation_beta(obs):
    """회귀 추정기가 합성 생성 베타를 되찾는다.

    생성 베타는 ``discount_capm._TRUE_BETA``이고 추정기는 그 값을 읽지 않는다.
    표준오차의 3배 안에 들어와야 한다.
    """
    est = estimate_capm_discount_rate(obs)
    assert est.beta is not None and est.beta_stderr is not None
    assert abs(est.beta - D._TRUE_BETA) < 3 * est.beta_stderr, (
        f"베타 {est.beta:.4f}, 생성값 {D._TRUE_BETA}, 표준오차 {est.beta_stderr:.4f}")
    assert abs(est.beta - D._TRUE_BETA) < 0.15
    # 절편은 0과 구분되지 않아야 한다. 생성이 CAPM을 정확히 따르게 만들어져
    # 있다(생성 알파 0). 절편의 표준오차를 잔차에서 직접 내 비교한다.
    x = obs["excess_market_return"].to_numpy(dtype=float)
    y = obs["excess_bank_return"].to_numpy(dtype=float)
    resid = y - (est.alpha + est.beta * x)
    se_alpha = float(resid.std(ddof=2)) / np.sqrt(len(x))
    assert abs(est.alpha) < 3 * se_alpha
    assert 0.5 < est.beta_r2 < 1.0


def test_beta_recovery_fails_when_the_pairing_is_broken(obs):
    """음성 대조. 은행주 수익률을 시장과 무관하게 섞으면 베타를 되찾지 못한다.

    되찾기 시험이 언제나 통과하는 시험이 아니라는 것을 보인다.
    """
    broken = obs.copy()
    perm = np.random.default_rng(0).permutation(len(broken))
    broken["excess_bank_return"] = broken["excess_bank_return"].to_numpy()[perm]
    est = estimate_capm_discount_rate(broken)
    assert abs(est.beta - D._TRUE_BETA) > 0.15
    assert est.beta_r2 < 0.5


def test_riskfree_is_the_ktb3y_average(obs):
    """R_f가 국고채 3년 관측 만기수익률의 산출대상기간 평균이다."""
    est = estimate_capm_discount_rate(obs)
    assert est.riskfree_annual == pytest.approx(
        float(obs["riskfree_yield"].mean()) / 100.0, rel=1e-12)
    assert est.n_observations == len(obs)
    assert est.period_start == obs["period"].min()
    assert est.period_end == obs["period"].max()


# ---------------------------------------------------------------- 프리미엄

def test_observed_market_premium_is_nonpositive_and_blocks_ke(obs):
    """관측 원장으로는 k_e를 낼 수 없다. 그 사실이 상태로 남는다.

    지표 마스터의 KOSPI는 표류항 없는 평균회귀 계열이라 어느 구간을 잡아도
    로그수익률 평균이 0 부근이고 R_M − R_f 가 음수가 된다. 이때 산식값을 그대로
    할인율로 쓰면 무위험회수보다 낮은 값이 LGD로 흘러간다. 내지 않는다.
    """
    est = estimate_capm_discount_rate(obs)
    assert est.market_return_source == "관측실현"
    assert est.market_premium < 0
    assert est.cost_of_equity is None
    assert est.ke_status == "추정불가(위험프리미엄비양수)"
    # 산식값 자체는 숨기지 않는다. 화면이 왜 비었는지 볼 수 있어야 한다.
    assert est.cost_of_equity_raw is not None


def test_ke_follows_the_capm_formula_when_market_return_is_approved(obs):
    """승인된 R_M이 들어오면 k_e = R_f + beta·(R_M − R_f)로 나온다."""
    est = estimate_capm_discount_rate(obs,
                                      market_return=_APPROVED_MARKET_RETURN)
    assert est.market_return_source == "승인모수"
    expected = est.riskfree_annual + est.beta * (
        _APPROVED_MARKET_RETURN - est.riskfree_annual)
    assert est.cost_of_equity == pytest.approx(expected, rel=1e-12)
    assert est.ke_status == "산출완료"
    # 무위험회수(R_f)보다 크다. beta > 0이고 프리미엄이 양수이기 때문이다.
    assert est.cost_of_equity > est.riskfree_annual
    # 타행 실측(예적금 外 11.22%)을 베끼지 않았다는 것을 값으로 확인한다.
    assert est.cost_of_equity != pytest.approx(0.1122, abs=1e-6)


def test_ke_is_blank_when_the_rate_falls_outside_the_ledger_range(obs):
    """산식값이 할인율 정의역(0, 1]을 벗어나면 채우지 않는다."""
    est = estimate_capm_discount_rate(obs, market_return=1.5)
    assert est.cost_of_equity is None
    assert est.ke_status == "추정불가(할인율범위밖)"
    assert est.cost_of_equity_raw > 1.0


def test_short_sample_returns_no_estimate():
    """표본이 3개월 미만이면 회귀를 돌리지 않는다."""
    obs = build_crm_capm_observation(asof=ASOF, seed=SEED, n_periods=3)
    est = estimate_capm_discount_rate(obs.head(2))
    assert est.beta is None and est.ke_status == "추정불가(표본부족)"
    with pytest.raises(ValueError):
        build_crm_capm_observation(asof=ASOF, seed=SEED, n_periods=2)


# ---------------------------------------------------------------- 승인 경로

def test_discount_rate_ledger_ships_null_even_with_estimation_sources():
    """출처를 적어도 값은 비어 있다. 값은 승인을 거쳐야 들어간다."""
    plain = build_crm_lgd_discount_rate(ASOF)
    assert plain["discount_rate"].isna().all()
    annotated = build_crm_lgd_discount_rate(
        ASOF, rf_source="KTB3Y 평균", beta_source="합성 관측 회귀",
        estimation_period="2014-07~2026-06")
    assert annotated["discount_rate"].isna().all()
    assert annotated["approved_by"].isna().all()
    assert (annotated["basis"] == "미정").all()
    assert (annotated["evidence_status"] == "재량·미규정").all()
    assert (annotated["beta_source"] == "합성 관측 회귀").all()


def test_capm_market_return_ships_unapproved():
    """시장수익률 모수는 값도 승인자도 비어 있는 채로 나간다."""
    p = build_estimation_param_ledgers(ASOF)["crm_estimation_param"]
    blank = unapproved_internal_params(p)
    assert "capm_market_return" in set(blank["param_code"])
    row = p[p["param_code"] == "capm_market_return"].iloc[0]
    assert pd.isna(row["param_value"]) and pd.isna(row["approved_by"])
    assert row["input_source"] == "내부기준"
    # 참고치 칸도 비어 있다. 타행 서식이 베타를 공시하지 않아 R_M을 역산할 수 없다.
    assert pd.isna(row["reference_value"])
    assert "역산" in str(row["reference_citation"])


def test_only_the_riskfree_scope_is_filled_without_an_approved_market_return():
    """R_M 승인 전에는 무위험회수만 채워지고 전체는 빈다."""
    with pytest.warns(ParamWarning):
        led = build_capm_discount_ledgers(asof=ASOF, seed=SEED)
    r = led["crm_lgd_discount_rate"]
    rf_rows = r[r["recovery_scope"] == "무위험회수"]
    all_rows = r[r["recovery_scope"] == "전체"]
    assert rf_rows["discount_rate"].notna().all()
    assert (rf_rows["basis"] == "무위험이자율").all()
    assert (rf_rows["approved_by"] == CAPM_APPROVER).all()
    assert (rf_rows["approval_date"] == ASOF).all()      # 벽시계가 아니라 기준일
    assert all_rows["discount_rate"].isna().all()
    assert all_rows["approved_by"].isna().all()


def test_approved_market_return_fills_both_scopes(approved):
    r = approved["crm_lgd_discount_rate"]
    assert r["discount_rate"].notna().all()
    assert (r["approved_by"] == CAPM_APPROVER).all()
    assert (r["evidence_status"] == CAPM_EVIDENCE).all()
    assert set(r.loc[r["recovery_scope"] == "전체", "basis"]) == {"자기자본비용"}
    assert set(r.loc[r["recovery_scope"] == "무위험회수", "basis"]) == {"무위험이자율"}


def test_approval_writes_value_and_record_together(obs):
    """승인 함수를 거치지 않고 값만 들어가는 경로가 없다."""
    est = estimate_capm_discount_rate(obs,
                                      market_return=_APPROVED_MARKET_RETURN)
    rates = build_crm_lgd_discount_rate(ASOF)
    out = apply_capm_discount_rates(rates, est, asof=ASOF)
    filled = out[out["discount_rate"].notna()]
    assert len(filled) == len(out)
    assert filled["approved_by"].notna().all()
    assert filled["approval_date"].notna().all()
    # 원본은 그대로다. 승인은 사본을 돌려준다.
    assert rates["discount_rate"].isna().all()


# ---------------------------------------------------------------- 자체검사

def test_check_suite_passes_on_the_approved_ledgers(approved, hist_recovery):
    led = dict(approved)
    led["crm_recovery_history"] = hist_recovery
    rep = run_capm_checks(led, asof=ASOF)
    fails = [c for c in rep.checks if c.status == "FAIL"]
    assert not fails, [str(c) for c in fails]
    assert len(rep.checks) == 5


def test_check_suite_has_no_failures_before_the_market_return_is_approved(
        hist_recovery):
    """승인 전 상태에서도 FAIL은 없다. 비어 있음은 위반이 아니라 산출물이다."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        led = build_capm_discount_ledgers(asof=ASOF, seed=SEED)
    led["crm_recovery_history"] = hist_recovery
    rep = run_capm_checks(led, asof=ASOF)
    assert not [c for c in rep.checks if c.status == "FAIL"]
    warned = {c.name for c in rep.checks if c.status == "WARN"}
    # 전체 회수유형에 값이 없으므로 서열 비교와 LGD 민감도는 판정하지 않는다.
    assert warned == {"CAPM 회수유형 할인율 서열", "CAPM 할인율 LGD 민감도"}


@pytest.fixture(scope="module")
def hist_recovery() -> pd.DataFrame:
    from risk_lib.models.estimation import build_history_ledgers
    return build_history_ledgers(asof=ASOF, seed=SEED)["crm_recovery_history"]


def test_check_recalculation_fails_when_the_ledger_is_tampered(approved):
    """음성 대조. 추정 원장의 베타를 손대면 재계산 검사가 FAIL한다."""
    ok = ValidationReport()
    check_capm_recalculation(approved["crm_capm_observation"],
                             approved["crm_capm_estimate"], ok)
    assert ok.checks[-1].status == "PASS"

    bad_est = approved["crm_capm_estimate"].copy()
    bad_est.loc[0, "beta"] = float(bad_est.loc[0, "beta"]) + 0.5
    rep = ValidationReport()
    check_capm_recalculation(approved["crm_capm_observation"], bad_est, rep)
    assert rep.checks[-1].status == "FAIL"

    # 표본을 잘라도 잡힌다. 추정을 돌린 표본과 원장의 표본이 달라지는 사건이다.
    rep2 = ValidationReport()
    check_capm_recalculation(approved["crm_capm_observation"].head(40),
                             approved["crm_capm_estimate"], rep2)
    assert rep2.checks[-1].status == "FAIL"


def test_check_scope_order_fails_when_the_two_rates_are_swapped(approved):
    """음성 대조. 무위험회수와 전체 할인율을 맞바꾸면 서열 검사가 FAIL한다."""
    r = approved["crm_lgd_discount_rate"]
    ok = ValidationReport()
    check_riskfree_scope_below_total(r, ok)
    assert ok.checks[-1].status == "PASS"

    swapped = r.copy()
    ke = float(r.loc[r["recovery_scope"] == "전체", "discount_rate"].iloc[0])
    rf = float(r.loc[r["recovery_scope"] == "무위험회수",
                     "discount_rate"].iloc[0])
    swapped.loc[swapped["recovery_scope"] == "전체", "discount_rate"] = rf
    swapped.loc[swapped["recovery_scope"] == "무위험회수", "discount_rate"] = ke
    rep = ValidationReport()
    check_riskfree_scope_below_total(swapped, rep)
    assert rep.checks[-1].status == "FAIL"


def test_check_approval_fails_when_a_value_is_written_without_approval(approved):
    """음성 대조. 승인 기록 없이 값만 넣으면 승인기록 검사가 FAIL한다."""
    ok = ValidationReport()
    check_discount_rate_approved(approved["crm_lgd_discount_rate"], ok)
    assert ok.checks[-1].status == "PASS"

    sneaked = build_crm_lgd_discount_rate(ASOF)
    sneaked.loc[0, "discount_rate"] = 0.11        # 승인 절차 우회
    rep = ValidationReport()
    check_discount_rate_approved(sneaked, rep)
    assert rep.checks[-1].status == "FAIL"


def test_check_evidence_fails_when_synthetic_is_labelled_as_measured(approved):
    """음성 대조. 합성 기반 값을 '2차자료'로 표시하면 근거 검사가 FAIL한다."""
    ok = ValidationReport()
    check_capm_evidence_disclosed(approved["crm_lgd_discount_rate"], ok)
    assert ok.checks[-1].status == "PASS"

    mislabelled = approved["crm_lgd_discount_rate"].copy()
    mislabelled["evidence_status"] = "2차자료"
    rep = ValidationReport()
    check_capm_evidence_disclosed(mislabelled, rep)
    assert rep.checks[-1].status == "FAIL"


def test_check_lgd_sensitivity_fails_when_the_discount_effect_disappears(
        approved, hist_recovery):
    """음성 대조. 경과연수를 0으로 뭉개면 할인효과가 사라져 FAIL한다."""
    r = approved["crm_lgd_discount_rate"]
    ok = ValidationReport()
    check_lgd_increases_with_discount_rate(hist_recovery, r, ok, asof=ASOF)
    assert ok.checks[-1].status == "PASS"

    flattened = hist_recovery.copy()
    flattened["recovery_years"] = 0.0
    rep = ValidationReport()
    check_lgd_increases_with_discount_rate(flattened, r, rep, asof=ASOF)
    assert rep.checks[-1].status == "FAIL"


# ---------------------------------------------------------------- LGD 산출

def test_lgd_stays_blocked_without_an_approved_cost_of_equity():
    """R_M 승인 전에는 LGD가 지금과 같이 전건 산출불가로 남는다."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cap = build_capm_discount_ledgers(asof=ASOF, seed=SEED)
        led = build_irb_estimation_ledgers(
            asof=ASOF, seed=SEED, rates=cap["crm_lgd_discount_rate"])
    est = led["crm_lgd_estimate"]
    assert (est["status"] == "산출불가").all()
    assert est["final_applied"].isna().all()


def test_lgd_is_produced_once_the_cost_of_equity_is_approved(approved):
    """승인된 k_e가 들어가면 LGD가 실제로 산출된다.

    이 작업 전에는 전 세그먼트가 '산출불가'였다.
    """
    p = _param_with_market_return()
    for code, val in (("downturn_year_quantile", 0.75),
                      ("moc_confidence_level", 0.75),
                      ("moc_data_quality_addon", 0.05)):
        p = approve_estimation_param(p, code=code, value=val,
                                     approved_by="시험",
                                     approval_date="2026-01-01",
                                     approval_body="모형위원회")
    for code, txt in (("moc_aggregation", "단순합"),
                      ("lgd_censoring_treatment", "보수적포함")):
        p = approve_estimation_param(p, code=code, text=txt,
                                     approved_by="시험",
                                     approval_date="2026-01-01",
                                     approval_body="모형위원회")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        led = build_irb_estimation_ledgers(
            asof=ASOF, seed=SEED, param=p,
            rates=approved["crm_lgd_discount_rate"])
    est = led["crm_lgd_estimate"]
    assert len(est) == 3
    assert not (est["status"] == "산출불가").any()
    assert est["final_applied"].notna().all()
    assert (est["discount_rate_status"] == "승인").all()
    ke = float(approved["crm_capm_estimate"]["cost_of_equity"].iloc[0])
    assert est["discount_rate"].to_numpy() == pytest.approx(ke)
    run = led["crm_estimation_run"]
    lgd_run = run[run["parameter"] == "LGD"]
    assert not lgd_run["unresolved_inputs"].fillna("").str.contains(
        "lgd_discount_rate").any()


def test_higher_discount_rate_gives_higher_lgd(approved, hist_recovery):
    """할인율을 올리면 LGD가 올라간다. 회수 현가가 줄기 때문이다."""
    from risk_lib.models.estimation import realised_lgd
    ke = float(approved["crm_capm_estimate"]["cost_of_equity"].iloc[0])
    low = realised_lgd(hist_recovery, discount_rate=ke, asof=ASOF)
    high = realised_lgd(hist_recovery, discount_rate=ke + 0.05, asof=ASOF)
    assert high["lgd_realised"].mean() > low["lgd_realised"].mean()


# ---------------------------------------------------------------- 결정론

def _fingerprint(frames: dict[str, pd.DataFrame]) -> str:
    h = hashlib.sha256()
    for name in sorted(frames):
        df = frames[name]
        h.update(name.encode())
        h.update(",".join(map(str, df.columns)).encode())
        h.update(pd.util.hash_pandas_object(df.astype(str),
                                            index=True).values.tobytes())
    return h.hexdigest()


def test_deterministic_same_process():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = build_capm_discount_ledgers(asof=ASOF, seed=SEED)
        b = build_capm_discount_ledgers(asof=ASOF, seed=SEED)
        c = build_capm_discount_ledgers(asof=ASOF, seed=SEED + 1)
    assert _fingerprint(a) == _fingerprint(b)
    assert _fingerprint(a) != _fingerprint(c)


def test_deterministic_across_processes():
    """별도 프로세스에서도 지문이 같다. 내장 hash()·벽시계를 쓰지 않는다."""
    code = (
        "import warnings, hashlib, pandas as pd;"
        "warnings.simplefilter('ignore');"
        "from risk_lib.models.estimation.discount_capm import "
        "build_capm_discount_ledgers as B;"
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
        local = _fingerprint(build_capm_discount_ledgers(asof=ASOF, seed=SEED))
    assert outs[0] == outs[1] == local


def test_estimate_frame_is_a_faithful_copy_of_the_estimate(obs):
    """추정 객체와 원장 1행이 같은 값을 든다."""
    est = estimate_capm_discount_rate(obs,
                                      market_return=_APPROVED_MARKET_RETURN)
    row = build_crm_capm_estimate(est).iloc[0]
    assert float(row["beta"]) == pytest.approx(est.beta, rel=1e-12)
    assert float(row["beta_stderr"]) == pytest.approx(est.beta_stderr, rel=1e-12)
    assert float(row["beta_r2"]) == pytest.approx(est.beta_r2, rel=1e-12)
    assert float(row["cost_of_equity"]) == pytest.approx(est.cost_of_equity,
                                                         rel=1e-12)
    assert row["ke_status"] == est.ke_status
    assert "합성" in row["beta_source"]
    assert "11.22%" in row["reference_note"]
