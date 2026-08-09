"""IRRBB(ΔEVE) · ΔNII — 불변식 고정.

이 파일의 규칙: **통과만으로는 통제가 아니다.** 각 검사는 결함을 되돌렸을 때
실제로 실패해야 한다. 특히 세 검사가 현행 결함을 직접 겨냥한다.

  · `test_delta_eve_moves_with_the_portfolio_maturity_profile`
    현행 사다리는 `balance_sheet.py:93-98`의 상수 가중 벡터에서 나오므로
    포트폴리오 만기를 바꿔도 ΔEVE가 미동하지 않는다. 만기를 3배로 늘리고
    ΔEVE가 움직이는지 본다.
  · `test_contract_and_behavioural_bases_differ_by_orders_of_magnitude`
    계약기준이면 비만기예금이 전액 최단 버킷, 행동기준이면 4~5년에 퍼진다.
    두 값이 같으면 행동모형이 ΔEVE에 닿지 않고 있다는 뜻이다.
  · `test_bucket_delta_pv_sums_to_delta_eve`
    화면이 그리는 버킷별 효과와 헤드라인이 같은 산출에서 나왔는지 대사한다.
    현행은 버킷별 효과가 원장에 아예 없었다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.alm import nii as N
from risk_lib.alm import params as P
from risk_lib.alm.balance_sheet import generate_balance_sheet
from risk_lib.alm.cashflow import build_cashflows
from risk_lib.alm.contracts import build_contract_ledger
from risk_lib.alm.curves import base_curve, build_curve_ledgers
from risk_lib.alm.irrbb import (
    IRRBB_TABLES, SCENARIOS, build_bucket_pv, build_irrbb_result,
    build_shocked_curves, by_scenario, compute_irrbb,
    compute_irrbb_from_cashflows, shock_curve, worst_eve, worst_row,
)
from risk_lib.data_gen import generate_portfolio
from risk_lib.datamodel.spec import validate
from risk_lib.market_data import demo_market_data
from risk_lib.references import (
    IRRBB_OUTLIER_EVE_PCT_TIER1, irrbb_shock_bp,
)

# 충격폭은 원장(alm_rate_shock_param)에서 읽는다. 시험이 숫자를 다시 적으면
# 원장과 시험이 두 벌이 되어, 원장이 틀려도 시험이 같이 틀린 채로 통과한다.
SHOCK_PARALLEL_BP = irrbb_shock_bp("parallel")
SHOCK_SHORT_BP = irrbb_shock_bp("short")
SHOCK_LONG_BP = irrbb_shock_bp("long")

ASOF = "2026-08-08"
SEED = 42
FW = "d368_2016"
TIER1 = 1.0e11


# ---------------------------------------------------------------- 도우미

def _small_portfolio(seed: int = SEED) -> pd.DataFrame:
    """검사용 소형 포트폴리오 — 엔진 경로는 같고 실행시간만 줄인다."""
    return generate_portfolio(n_corporate=60, n_retail=100, n_mortgage=40,
                              n_sovereign=5, n_bank=5, seed=seed)


def _risk_factor(asof: str = ASOF, seed: int = SEED) -> pd.DataFrame:
    snaps, _c, _v = demo_market_data(asof=asof, seed=seed)
    snap = next(s for s in snaps if s.data_type == "ir_curve")
    return pd.DataFrame([{
        "factor_id": f"ir_curve:{snap.name}:{float(r['tenor']):g}Y",
        "asof": asof, "risk_class": "interest_rate", "curve": snap.name,
        "tenor": float(r["tenor"]), "value": float(r["quote"]),
        "source": snap.source, "staleness_days": 0, "modellable": True,
    } for _, r in snap.quotes.iterrows()])


def _build(portfolio: pd.DataFrame, *, asof: str = ASOF, seed: int = SEED):
    """계약 → 현금흐름 → 커브까지. 엔진 입력을 한 자리에서 만든다.

    자본은 포트폴리오에 비례시킨다 — 고정 금액을 쓰면 소형 포트폴리오에서
    자기자본이 총자산을 넘어 조달 잔액이 음수가 되고, 그 상태의 ΔEVE는 아무
    것도 고정하지 못한다.
    """
    bs = generate_balance_sheet(
        portfolio, capital_total=float(portfolio["ead"].sum()) * 0.14,
        seed=seed)
    led = P.build_param_ledgers(asof)
    con = build_contract_ledger(portfolio, asof=asof, funding=bs.funding,
                                hqla=bs.hqla, equity=bs.equity,
                                base_rate=0.03, seed=seed)
    cf = build_cashflows(
        con, asof=asof, product_terms=led["alm_product_terms"],
        buckets=led["alm_time_bucket"],
        behaviour_param=led["alm_behaviour_param"],
        scenario_mult=led["alm_behaviour_scenario_mult"],
        nmd_param=led["alm_nmd_param"],
        scurve_param=led["alm_prepay_scurve_param"])
    curves = {"KRW": base_curve(_risk_factor(asof, seed), asof=asof)}
    return con, led, build_curve_ledgers(), cf, curves


def _irrbb(bundle, *, basis: str = "행동조정", tier1: float = TIER1,
           delta_nii: pd.DataFrame | None = None, asof: str = ASOF):
    _con, _led, cl, cf, curves = bundle
    return compute_irrbb_from_cashflows(
        cf.bucket, asof=asof, tier1=tier1, curves=curves,
        shock_param=cl["alm_rate_shock_param"],
        scenario_def=cl["alm_scenario_def"],
        floor=cl["alm_post_shock_floor"], framework_version=FW,
        headline_basis=basis, delta_nii=delta_nii)


@pytest.fixture(scope="module")
def bundle():
    return _build(_small_portfolio())


@pytest.fixture(scope="module")
def irrbb(bundle):
    return _irrbb(bundle)


@pytest.fixture(scope="module")
def nii(bundle):
    con, led, cl, _cf, curves = bundle
    shocked, _w = build_shocked_curves(
        curves, scenarios=SCENARIOS, shock_param=cl["alm_rate_shock_param"],
        scenario_def=cl["alm_scenario_def"], floor=cl["alm_post_shock_floor"],
        framework_version=FW)
    return N.compute_delta_nii(
        con, led["alm_product_terms"], asof=ASOF, horizon_years=1.0,
        curves=curves, shocked=shocked,
        scenario_def=cl["alm_scenario_def"], nmd_param=led["alm_nmd_param"])


# ---------------------------------------------------------------- 원장 품질

def test_irrbb_ledgers_validate(irrbb):
    specs = {s.name: s for s in IRRBB_TABLES}
    assert validate(irrbb.bucket_pv, specs["alm_irrbb_bucket_pv"]) == []
    assert validate(irrbb.result, specs["alm_irrbb_result"]) == []


def test_nii_ledger_validates(nii):
    assert validate(nii.result, N.NII_RESULT) == []


def test_result_grain_is_basis_times_scenario(irrbb):
    """두 산출기준 × 6시나리오 = 12행. 부분집합 검사로는 1행짜리 결함이 통과한다
    — `test_datamodel_domains.py:294`가 그 상태였다."""
    assert len(irrbb.result) == 2 * len(SCENARIOS)
    assert not irrbb.result.duplicated(
        subset=["asof", "basis", "scenario"]).any()
    assert set(irrbb.result["scenario"]) == set(SCENARIOS)


def test_engine_is_deterministic():
    """(asof, seed)가 같으면 같은 산출이다."""
    a = _irrbb(_build(_small_portfolio()))
    b = _irrbb(_build(_small_portfolio()))
    assert a.result.equals(b.result)
    assert a.bucket_pv.equals(b.bucket_pv)


# ---------------------------------------------------------------- ΔEVE 대사

def test_bucket_delta_pv_sums_to_delta_eve(irrbb):
    """버킷별 효과와 헤드라인이 같은 산출에서 나와야 화면과 원장이 갈라지지 않는다."""
    got = (irrbb.bucket_pv.groupby(["basis", "scenario"])["delta_pv"].sum()
           .rename("delta_pv").reset_index())
    want = irrbb.result[["basis", "scenario", "delta_eve"]]
    m = want.merge(got, on=["basis", "scenario"])
    assert len(m) == len(want)
    assert (m["delta_eve"] - m["delta_pv"]).abs().max() < 1e-3


def test_bucket_pv_reproduces_from_cashflow_and_discount_factor(irrbb):
    """PV = CF × DF가 원장 안에서 재현돼야 한다 — 재현되지 않으면 감사에서
    분해가 불가능하다."""
    d = irrbb.bucket_pv
    assert (d["pv_base"] - d["cf_base"] * d["df_base"]).abs().max() < 1e-6
    assert (d["pv_shocked"] - d["cf"] * d["df_shocked"]).abs().max() < 1e-6
    assert (d["delta_pv"] - (d["pv_shocked"] - d["pv_base"])).abs().max() < 1e-6


def test_worst_scenario_is_the_minimum_delta_eve(irrbb):
    """`worst_eve()`가 6개 중 최악을 고르고 원장 플래그와 일치하는지."""
    for basis in ("계약", "행동조정"):
        d = irrbb.result[irrbb.result["basis"] == basis]
        assert int(d["is_worst"].sum()) == 1
        assert worst_eve(irrbb.result, basis=basis) == pytest.approx(
            float(d["delta_eve"].min()))
        assert worst_row(irrbb.result, basis=basis)["scenario"] in SCENARIOS
    # 헤드라인 스칼라도 같은 행에서 나온다
    hb = irrbb.headline_basis
    assert irrbb.worst_eve == pytest.approx(worst_eve(irrbb.result, basis=hb))
    assert irrbb.worst_eve_decline == pytest.approx(
        max(-irrbb.worst_eve, 0.0))


def test_by_scenario_preserves_the_form_line_order(irrbb):
    """서식 라인번호(20xx)가 이 순서를 쓴다 — 순서가 바뀌면 제출서식이 바뀐다."""
    v = by_scenario(irrbb.result, basis="계약")
    assert list(v["scenario"]) == SCENARIOS
    assert list(v.columns) == ["scenario", "delta_eve", "pct_tier1"]


def test_ambiguous_basis_is_refused_not_guessed(irrbb):
    """산출기준을 명시하지 않으면 어느 기준의 수치인지가 남지 않는다."""
    with pytest.raises(ValueError, match="산출기준이 여럿"):
        by_scenario(irrbb.result)


# ---------------------------------------------------------------- 두 산출기준

def test_contract_and_behavioural_bases_differ_by_orders_of_magnitude(irrbb):
    """계약기준은 NMD가 전액 O/N(듀레이션 ≈ 0), 행동기준은 4~5년에 퍼진다."""
    d = irrbb.result.set_index(["basis", "scenario"])["delta_eve"]
    for sc in SCENARIOS:
        assert d[("계약", sc)] != pytest.approx(d[("행동조정", sc)], rel=1e-6)
    # parallel_up은 방향까지 갈린다 — 부채 슬로팅이 길어지면 갭 부호가 뒤집힌다.
    assert np.sign(d[("계약", "parallel_up")]) != np.sign(
        d[("행동조정", "parallel_up")])


def test_delta_eve_moves_with_the_portfolio_maturity_profile():
    """상수 가중 벡터 결함의 회귀 검사.

    현행 사다리는 포트폴리오의 함수가 아니어서 만기를 바꿔도 IRRBB가 미동하지
    않는다. 계약원장 → 현금흐름 경로에서는 반드시 움직여야 한다.
    """
    base = _small_portfolio()
    longer = base.copy()
    longer["maturity"] = longer["maturity"] * 3.0
    a = _irrbb(_build(base), basis="계약")
    b = _irrbb(_build(longer), basis="계약")
    ea = float(a.result.set_index(["basis", "scenario"])
               .loc[("계약", "parallel_up"), "delta_eve"])
    eb = float(b.result.set_index(["basis", "scenario"])
               .loc[("계약", "parallel_up"), "delta_eve"])
    # 자산 듀레이션이 길어지면 금리상승 손실이 커진다 — 부호까지 확인한다.
    assert eb < ea
    assert abs(eb - ea) > abs(ea) * 0.05


# ---------------------------------------------------------------- 마진 취급

def test_margin_is_excluded_from_eve_and_included_in_nii(irrbb, nii, bundle):
    """두 지표가 마진을 반대로 쓴다는 사실을 **금액으로** 확인한다."""
    _con, _led, _cl, cf, _curves = bundle
    b = cf.bucket
    b = b[(b["scenario"] == "base") & (b["basis"] == "행동조정")]
    margin_total = float(b["margin_cf"].sum())
    assert margin_total != 0.0        # 마진이 0이면 이 검사가 무의미해진다

    # EVE: 버킷 CF에 margin_cf가 들어가지 않았다.
    sign = {"asset": 1.0, "liability": -1.0}
    cf_with_margin = float((b["total_cf"] * b["side"].map(sign)).sum())
    cf_in_ledger = float(
        irrbb.bucket_pv[(irrbb.bucket_pv["basis"] == "행동조정")
                        & (irrbb.bucket_pv["scenario"] == "parallel_up")]
        ["cf_base"].sum())
    signed_margin = float((b["margin_cf"] * b["side"].map(sign)).sum())
    assert cf_in_ledger == pytest.approx(cf_with_margin - signed_margin,
                                         rel=1e-9)

    # NII: 마진이 수준에 들어가 있고 그 금액이 원장에 남는다.
    r = nii.result.iloc[0]
    assert float(r["margin_included"]) == pytest.approx(
        float(r["nii_base"]) - float(r["nii_base_ex_margin"]), rel=1e-12)
    assert float(r["margin_included"]) != 0.0
    assert r["margin_treatment"] == "포함"
    assert (irrbb.bucket_pv["margin_treatment"] == "제외").all()


# ---------------------------------------------------------------- ΔNII

def test_delta_nii_covers_only_the_two_parallel_scenarios(nii):
    """ΔNII는 6개가 아니라 평행충격 2개다 — 규칙은 원장(applies_to_nii)에서 온다."""
    assert list(nii.result["scenario"]) == ["parallel_up", "parallel_down"]
    assert len(nii.result) == 2


def test_delta_nii_is_symmetric_and_signed_for_parallel_shocks(nii):
    """평행 ±충격은 크기가 같고 부호가 반대다(선형 전가). 부호가 같으면
    시나리오 곡선이 ΔNII에 닿지 않고 있다는 뜻이다."""
    up, dn = (float(nii.result.set_index("scenario")
                    .loc[s, "delta_nii"]) for s in
              ("parallel_up", "parallel_down"))
    assert up == pytest.approx(-dn, rel=1e-6)
    assert up != 0.0


def test_missing_deposit_beta_skips_the_adjustment_and_warns(nii):
    """예금베타가 비어 있으면 지어내지 않고 건너뛴 사실을 남긴다."""
    w = nii.warning_frame()
    assert (w["param"] == "pass_through_beta").any()


def test_delta_nii_joins_into_the_result_ledger(bundle, nii):
    """`catalog.ALM_METRICS`의 IRRBB_NII 자리를 채운다 — 결과 원장에서 조인된다."""
    res = _irrbb(bundle, delta_nii=nii.delta_nii)
    d = res.result[res.result["basis"] == "행동조정"].set_index("scenario")
    assert d.loc["parallel_up", "delta_nii"] == pytest.approx(
        float(nii.result.set_index("scenario").loc["parallel_up", "delta_nii"]))
    assert pd.isna(d.loc["steepener", "delta_nii"])
    # 마진 취급이 반대라는 사실이 컬럼으로 보인다.
    assert d.loc["parallel_up", "margin_treatment"] == "ΔEVE 마진제외 · ΔNII 마진포함"
    assert d.loc["steepener", "margin_treatment"] == "ΔEVE 마진제외"


# ---------------------------------------------------------------- 근거·모수

def test_outlier_verdict_is_made_against_the_tier1_threshold(irrbb):
    """BCBS d368 §88 원문확인 — 최대 ΔEVE 대 기본자본의 15%(1차자료 §A-5).

    앞선 회차는 기준의 1차자료를 못 봐서 판정을 보류(NULL)했다. 원문을 확보한
    지금은 판정한다. 분모는 기본자본이며 총자기자본이 아니다.
    """
    assert irrbb.result["outlier_test_pass"].notna().all()
    assert (irrbb.result["evidence_status"] == "원문확인").all()
    r = irrbb.result
    want = -r["delta_eve_to_tier1"] <= IRRBB_OUTLIER_EVE_PCT_TIER1
    assert list(r["outlier_test_pass"].astype(bool)) == list(want)


def test_contract_basis_actually_fails_the_outlier_test(irrbb):
    """판정이 나는 것이 정상이다 — 계약기준 ΔEVE는 기본자본의 15%를 넘는다.

    이 검사가 실패하면 둘 중 하나다. 산출이 바뀌었거나, 판정을 숨기고 있거나.
    """
    worst = worst_row(irrbb.result, basis="계약")
    assert -float(worst["delta_eve_to_tier1"]) > IRRBB_OUTLIER_EVE_PCT_TIER1
    assert bool(worst["outlier_test_pass"]) is False


def test_outlier_verdict_is_withheld_when_the_caller_says_so(irrbb):
    """다른 기준을 써야 하는데 그 산출체계가 없으면 판정하지 않고 NULL을 남긴다."""
    r = build_irrbb_result(
        irrbb.bucket_pv, asof=ASOF, tier1=TIER1, framework_version=FW,
        shock_source={sc: "직접" for sc in SCENARIOS},
        outlier_threshold=None, outlier_evidence="미확인")
    assert r["outlier_test_pass"].isna().all()


def test_shock_source_is_direct_not_a_proxy(irrbb):
    """KRW 실값이 원장에 있으므로 다른 통화를 빌리지 않는다."""
    assert (irrbb.result["shock_source"] == "직접").all()
    assert (irrbb.result["framework_version"] == FW).all()


def test_missing_shock_parameters_refuse_to_produce_a_zero_result(bundle):
    """모수가 비어 있는데 0을 돌려주면 화면에 'ΔEVE 0'으로 읽힌다."""
    _con, _led, cl, cf, curves = bundle
    empty = cl["alm_rate_shock_param"].copy()
    empty.loc[empty["ccy"] == "KRW", "shock_bp"] = pd.NA
    with pytest.raises(ValueError, match="충격 모수가 전부 비어 있다"):
        compute_irrbb_from_cashflows(
            cf.bucket, asof=ASOF, tier1=TIER1, curves=curves,
            shock_param=empty,
            scenario_def=cl["alm_scenario_def"],
            floor=cl["alm_post_shock_floor"], framework_version=FW,
            headline_basis="계약")


def test_zero_tier1_is_refused_not_divided_by(irrbb):
    """자본이 소진된 경로에서 현행은 0나눗셈이 난다."""
    with pytest.raises(ValueError, match="기본자본"):
        build_irrbb_result(irrbb.bucket_pv, asof=ASOF, tier1=0.0,
                           framework_version=FW,
                           shock_source={sc: "직접" for sc in SCENARIOS})


def test_off_balance_cashflows_are_refused_until_they_carry_a_sign(bundle):
    """부호 규약이 없는 측에 임의로 +1을 붙이면 ΔEVE 부호가 조용히 틀린다."""
    _con, _led, _cl, cf, curves = bundle
    bad = cf.bucket.copy()
    bad.loc[bad.index[0], "side"] = "off_balance"
    with pytest.raises(ValueError, match="부호 규약이 없는 측"):
        build_bucket_pv(bad, asof=ASOF, curves=curves, shocked={})


# ---------------------------------------------------------------- 계승 경로

@pytest.fixture(scope="module")
def legacy():
    p = _small_portfolio()
    bs = generate_balance_sheet(p, capital_total=float(p["ead"].sum()) * 0.14,
                                seed=SEED)
    return bs, compute_irrbb(bs.repricing, tier1=bs.equity * 0.9)


def test_legacy_shock_curve_reads_the_ledger_calibration():
    """Δr은 원장 값에서 나온다. 1차자료 반영으로 KRW가 200/300/150(USD 프록시)
    에서 300/400/200(d368 Annex 2 Table 1)으로 올라갔고, 이 검사는 상수를
    다시 적지 않고 원장을 읽으므로 원장이 정본이라는 사실이 유지된다."""
    t = np.array([0.05, 0.5, 1.0, 3.0, 5.0, 10.0, 20.0])
    assert np.allclose(shock_curve("parallel_up", t),
                       SHOCK_PARALLEL_BP / 1e4)
    assert np.allclose(shock_curve("parallel_down", t),
                       -SHOCK_PARALLEL_BP / 1e4)
    s = shock_curve("short_up", t)
    assert s[0] > 0 and (np.diff(s) < 0).all()
    steep = shock_curve("steepener", t)
    assert steep[0] < 0 and steep[-1] > 0
    flat = shock_curve("flattener", t)
    assert flat[0] > 0 and flat[-1] < 0
    # 장·단기 계수가 둘 다 살아 있는지는 합성식으로만 확인된다
    assert steep[-1] == pytest.approx(
        -0.65 * SHOCK_SHORT_BP / 1e4 * np.exp(-20 / 4)
        + 0.9 * SHOCK_LONG_BP / 1e4 * (1 - np.exp(-20 / 4)), rel=1e-12)
    assert shock_curve("short_up", np.array([0.0]))[0] == pytest.approx(
        SHOCK_SHORT_BP / 1e4)


def test_legacy_gap_path_reproduces_the_current_numbers(legacy):
    """계승 경로는 산출값이 아니라 산출물의 **모양**만 바꾼다."""
    bs, r = legacy
    t = bs.repricing["t_mid"].to_numpy(dtype=float)
    gap = bs.repricing["gap"].to_numpy(dtype=float)
    pv_base = float(np.sum(gap * np.exp(-0.03 * t)))
    want = {sc: float(np.sum(gap * np.exp(-(0.03 + shock_curve(sc, t)) * t)))
            - pv_base for sc in SCENARIOS}
    got = r.delta_eve.set_index("scenario")["delta_eve"]
    for sc in SCENARIOS:
        assert got[sc] == pytest.approx(want[sc], rel=1e-12)


def test_legacy_result_exposes_the_attributes_materialisation_looks_for(legacy):
    """`materialize.py:327,342`가 `getattr`로 찾다 실패해 `alm_irrbb_shock`을
    1행 · delta_eve=0.0으로 만들던 폴백 결함의 회귀 검사."""
    _bs, r = legacy
    assert hasattr(r, "by_scenario") and hasattr(r, "worst_eve")
    assert len(r.by_scenario) == len(SCENARIOS)
    assert set(r.by_scenario.columns) == {"scenario", "delta_eve", "pct_tier1"}
    assert r.worst_eve == pytest.approx(float(r.delta_eve["delta_eve"].min()))
    assert r.worst_eve != 0.0


def test_legacy_path_records_that_the_curve_is_flat(legacy):
    """평면 곡선은 산출 가정이지 시장이 아니다 — 그 사실이 산출물에 실려야 한다."""
    _bs, r = legacy
    assert (r.warning_frame()["param"] == "base_curve").any()
    assert r.base_rate == 0.03


def test_legacy_bucket_effect_ties_to_the_ladder(legacy):
    """화면이 그리던 pv_effect_worst가 이제 원장(alm_irrbb_bucket_pv)에서 나온다."""
    _bs, r = legacy
    assert "pv_effect_worst" in r.repricing.columns
    assert float(r.repricing["pv_effect_worst"].sum()) == pytest.approx(
        r.worst_eve, rel=1e-9)
