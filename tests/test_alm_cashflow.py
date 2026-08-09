"""ALM 현금흐름 산출 엔진 — 불변식 고정.

이 파일의 규칙: **통과만으로는 통제가 아니다.** 각 검사는 결함을 되돌렸을 때
실제로 실패해야 하고, 그렇지 않은 검사는 그 사실을 주석에 남긴다.

특히 `test_prepayment_shortens_wal_not_just_total`은 명목 대사만으로는 잡히지
않는 결함(SIFMA 순서 위반)을 겨냥한다 — 조기상환은 원금 **금액**이 아니라
**시점**을 바꾸므로 합계 검사는 순서를 바꿔도 통과한다.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from risk_lib.alm import params as P
from risk_lib.alm.behaviour import (
    apply_prepayment, nmd_slotting, psa_cpr, scenario_multiplier,
    scurve_ri, smm_from_cpr,
)
from risk_lib.alm.cashflow import CASHFLOW_TABLES, CF_SCENARIOS, build_cashflows
from risk_lib.alm.contracts import CONTRACT, build_contract_ledger
from risk_lib.alm.daycount import year_fraction
from risk_lib.alm.schedule import (
    SCHEDULED_AMORT_TYPES, annuity_payment, balance_forward, build_schedule,
    payment_dates,
)
from risk_lib.datamodel.spec import validate

ASOF = "2026-08-08"
SEED = 42


# ---------------------------------------------------------------- 이자관행

def test_thirty_360_month_end_correction():
    """30/360은 D1 보정 뒤에 D2를 자른다 — 순서가 틀리면 월말 계약이 하루 어긋난다."""
    # 1/31 → 2/28: D1=31→30, D2=28 (D1이 30이 됐지만 D2가 31이 아니므로 그대로)
    assert year_fraction(date(2026, 1, 31), date(2026, 2, 28), "30/360") == \
        pytest.approx((30 * 1 + (28 - 30)) / 360)
    # 1/30 → 3/31: D2=31이고 D1=30이므로 D2→30
    assert year_fraction(date(2026, 1, 30), date(2026, 3, 31), "30/360") == \
        pytest.approx(60 / 360)


def test_act_act_isda_splits_at_the_year_boundary():
    """윤년을 걸치는 구간을 한 분모로 나누면 이자가 틀린다."""
    f = year_fraction(date(2023, 12, 1), date(2024, 2, 1), "ACT/ACT_ISDA")
    assert f == pytest.approx(31 / 365 + 31 / 366)
    # 단일 분모(365)로 계산하면 다른 값이 나온다 — 검사가 분기를 실제로 요구한다.
    assert f != pytest.approx(62 / 365)


def test_unknown_day_count_is_rejected():
    with pytest.raises(ValueError, match="미지원 이자계산 관행"):
        year_fraction(date(2026, 1, 1), date(2026, 2, 1), "ACT/365L")


# ---------------------------------------------------------------- 상환스케줄

def test_payment_dates_anchor_on_maturity_without_month_end_drift():
    """말일 절사가 누적되면 3/31 → 2/28 → 1/28로 원래 일자를 잃는다."""
    ds = payment_dates(date(2025, 12, 1), date(2026, 3, 31), 12)
    assert ds == [date(2025, 12, 31), date(2026, 1, 31),
                  date(2026, 2, 28), date(2026, 3, 31)]


@pytest.mark.parametrize("amort", SCHEDULED_AMORT_TYPES)
def test_principal_ties_to_opening_balance(amort):
    """설계의 alm_cf_contract_ties_to_notional — 원금 합계 = 기초잔액."""
    s = build_schedule(asof=date(2026, 1, 31), maturity=date(2031, 1, 31),
                       opening_balance=1e9, annual_rate=0.05, amort_type=amort,
                       pay_freq_per_year=12, day_count="ACT/365F",
                       grace_months=12)
    assert sum(i.principal for i in s) == pytest.approx(1e9, abs=1e-6)
    assert s[-1].closing_balance == 0.0


def test_backward_balance_matches_forward_recursion():
    """후진식(산출 경로)과 전진식(대조용)이 1원 이내로 맞아야 한다."""
    b0, rate, freq = 1e9, 0.05, 12
    s = build_schedule(asof=date(2026, 1, 31), maturity=date(2031, 1, 31),
                       opening_balance=b0, annual_rate=rate,
                       amort_type="annuity", pay_freq_per_year=freq,
                       day_count="30/360")
    i = rate / freq
    pmt = annuity_payment(b0, i, len(s))
    for k in range(1, len(s)):
        assert balance_forward(b0, i, pmt, k) == \
            pytest.approx(s[k - 1].closing_balance, abs=1.0)


def test_zero_rate_annuity_does_not_divide_by_zero():
    assert annuity_payment(1e9, 0.0, 10) == pytest.approx(1e8)


def test_balloon_is_repaid_at_maturity_on_top_of_the_final_instalment():
    """부분상각: 만기 직전 잔액은 (마지막 회차 지급액 + balloon)의 현재가치다.

    balloon 자체(β·P₀)가 만기 직전 잔액인 것이 **아니다** — 그 시점에는 마지막
    정규 회차분도 아직 남아 있다. B_{n−1}(1+i) = PMT + B_n 이 성립해야
    annuity 산식이 balloon을 목표로 잡은 것이 맞다.
    """
    b0, rate, freq, ratio = 1e9, 0.05, 4, 0.3
    s = build_schedule(asof=date(2026, 1, 31), maturity=date(2031, 1, 31),
                       opening_balance=b0, annual_rate=rate,
                       amort_type="annuity", pay_freq_per_year=freq,
                       day_count="ACT/365F", balloon_ratio=ratio)
    i, bn = rate / freq, b0 * ratio
    pmt = annuity_payment(b0, i, len(s), bn)
    assert s[-2].closing_balance == pytest.approx((pmt + bn) / (1 + i), rel=1e-12)
    # 최종 회차가 balloon을 흡수하므로 정규 회차보다 압도적으로 크다.
    assert s[-1].principal > bn
    assert s[-1].principal > 5 * s[0].principal
    assert sum(x.principal for x in s) == pytest.approx(b0, abs=1e-6)


def test_non_maturity_products_have_no_contractual_schedule():
    with pytest.raises(ValueError, match="계약 상환일정이 없다"):
        build_schedule(asof=date(2026, 1, 1), maturity=date(2031, 1, 1),
                       opening_balance=1e9, annual_rate=0.02,
                       amort_type="non_maturity", pay_freq_per_year=12,
                       day_count="ACT/365F")


# ---------------------------------------------------------------- 행동모형

def test_smm_uses_the_exact_conversion_not_the_linear_approximation():
    """SMM = 1 − (1−CPR)^τ. 선형근사 CPR/12를 쓰면 이 검사가 깨진다."""
    exact = 1.0 - (1.0 - 0.06) ** (1 / 12)
    assert smm_from_cpr(0.06, 1 / 12) == pytest.approx(exact, rel=1e-12)
    assert smm_from_cpr(0.06, 1 / 12) != pytest.approx(0.06 / 12, rel=1e-3)


def test_psa_100_ramps_to_six_percent_at_thirty_months():
    assert psa_cpr(0) == 0.0
    assert psa_cpr(15) == pytest.approx(0.03)
    assert psa_cpr(30) == pytest.approx(0.06)
    assert psa_cpr(360) == pytest.approx(0.06)      # 램프 후 평탄


def test_prepayment_preserves_principal_across_cpr_levels():
    """조기상환은 금액이 아니라 시점을 바꾼다."""
    s = _mortgage_schedule()
    for cpr in (0.0, 0.06, 0.30):
        cf = apply_prepayment(s, annual_rate=0.045, cpr_path=[cpr] * len(s))
        assert sum(p.principal for p in cf) == pytest.approx(1e9, abs=1e-3)


def test_prepayment_shortens_wal_not_just_total():
    """**합계 검사가 못 잡는 결함을 겨냥한다.**

    SIFMA 순서 `PP = SMM·(B − SP)`를 `PP = SMM·B`로 바꾸면 조기상환이
    과대계상되지만 원금 합계는 그대로 보존된다 — 명목 대사는 통과한다.
    가중평균만기(WAL)가 그 차이를 드러내는 유일한 축이다.
    """
    s = _mortgage_schedule()
    cf0 = apply_prepayment(s, annual_rate=0.045, cpr_path=[0.0] * len(s))
    cf6 = apply_prepayment(s, annual_rate=0.045, cpr_path=[0.06] * len(s))
    assert _wal(cf6) < _wal(cf0) - 0.5           # 조기상환이 만기를 앞당긴다

    # 순서를 위반한 재구현 — 합계는 같지만 WAL이 더 짧다.
    bad_wal = _wal_with_broken_sifma_order(s, 0.06)
    assert bad_wal < _wal(cf6), (
        "SP 차감 전에 SMM을 걸면 조기상환이 과대계상되어야 한다 — "
        "이 검사가 통과하지 않으면 순서 결함을 잡을 수 없다")


def test_scenario_multiplier_table_is_complete_from_the_source():
    """BCBS d368 Annex 2 Table 3·4 12칸 전건이 원문확인이다(1차자료 §A-7·§A-8).

    **바뀐 것.** 앞선 회차는 steepener·flattener 네 칸을 NULL로 두고 엔진이
    승수 1.0으로 건너뛰게 했다. 1차자료 발췌로 그 네 칸이 확인돼(CPR 0.8/1.2,
    TDRR 0.8/1.2) 원장이 채워졌으므로, 이제 그 시나리오도 조정이 걸린다.
    """
    mt = P.build_behaviour_scenario_mult()
    assert mt["multiplier"].notna().all()
    assert (mt["evidence_status"] == "원문확인").all()
    for model in ("CPR", "TDRR"):
        mult, warn = scenario_multiplier(mt, model, "steepener")
        assert mult == pytest.approx(0.8) and warn is None
        mult, warn = scenario_multiplier(mt, model, "flattener")
        assert mult == pytest.approx(1.2) and warn is None


def test_blank_scenario_multiplier_still_falls_back_to_one_and_warns():
    """원장이 비면 조용히 메우지 않는다 — 폴백 경로 자체는 살아 있어야 한다."""
    mt = P.build_behaviour_scenario_mult()
    mt.loc[(mt["model"] == "CPR") & (mt["scenario"] == "steepener"),
           ["multiplier", "evidence_status"]] = [None, "미확인"]
    mult, warn = scenario_multiplier(mt, "CPR", "steepener")
    assert mult == 1.0 and warn is not None and "미확인" in warn.reason


def test_cpr_and_tdrr_are_opposite_only_on_the_parallel_and_short_axes():
    """평행·단기 축은 방향이 반대이고 회전 축은 두 표가 **같은 값**이다.

    "TDRR은 CPR의 역방향"이라고 일반화하면 steepener·flattener 네 칸이
    틀린다(1차자료 §A-8). Table 3과 Table 4를 각각 읽어야 한다.
    """
    mt = P.build_behaviour_scenario_mult()

    def m(model, sc):
        return scenario_multiplier(mt, model, sc)[0]

    for sc in ("parallel_up", "short_up"):
        assert m("CPR", sc) < 1.0 < m("TDRR", sc)
    for sc in ("parallel_down", "short_down"):
        assert m("TDRR", sc) < 1.0 < m("CPR", sc)
    for sc in ("steepener", "flattener"):
        assert m("CPR", sc) == pytest.approx(m("TDRR", sc))


def test_nmd_caps_are_enforced_by_the_engine_not_trusted_from_the_ledger():
    """원장에 상한 초과값이 들어와도 산출은 상한을 넘지 않아야 한다."""
    bk = P.build_time_buckets()

    def slot(core_ratio, avg_maturity):
        return nmd_slotting(
            1e12, core_ratio=core_ratio, core_ratio_cap=0.50,
            avg_maturity_years=avg_maturity, avg_maturity_cap_years=4.0,
            buckets=bk, stable_ratio=None, scope="test")

    over, achieved_over, warns_over = slot(0.99, 99.0)   # 원장이 상한 초과값 제공
    at_cap, achieved_cap, _ = slot(0.50, 4.0)            # 상한 그대로
    # 절사가 엔진에서 일어나면 두 산출은 완전히 같아야 한다.
    assert [(p.t_years, p.principal) for p in over] == \
           [(p.t_years, p.principal) for p in at_cap]
    assert achieved_over == pytest.approx(achieved_cap)
    assert sum(p.principal for p in over) == pytest.approx(1e12, rel=1e-12)
    # 코어 비율 절사는 정확하다 — 논코어(최단 버킷)가 절반이어야 한다.
    assert over[0].principal == pytest.approx(0.50e12, rel=1e-12)


def test_bucket_discretisation_breaching_the_cap_is_reported_not_hidden():
    """house 9버킷에서는 상한 4년 NMD가 4.375년으로 슬로팅된다.

    H = 2×4 = 8년이 "5-10y" 버킷 안에 떨어져 [5,8]의 질량이 t_mid 7.5년에
    놓이기 때문이다. 감독상한 초과를 조용히 두면 산출물에 남지 않으므로
    경고로 드러나야 한다. 근본 해결은 표준 19버킷 적재다.
    """
    bk = P.build_time_buckets()
    _, achieved, warns = nmd_slotting(
        1e12, core_ratio=0.50, core_ratio_cap=0.50,
        avg_maturity_years=4.0, avg_maturity_cap_years=4.0,
        buckets=bk, stable_ratio=None, scope="wholesale_nonfin")
    assert achieved > 4.0
    assert any(w.param == "avg_maturity_cap_years" and "이산화" in w.reason
               for w in warns)

    # 상한이 버킷 경계에 떨어지면(5년 → H=10년) 오차가 사라지고 경고도 없다.
    _, exact, clean = nmd_slotting(
        1e12, core_ratio=1.0, core_ratio_cap=1.0,
        avg_maturity_years=5.0, avg_maturity_cap_years=5.0,
        buckets=bk, stable_ratio=None, scope="retail_transactional")
    assert exact == pytest.approx(5.0, rel=1e-12)
    assert not any(w.param == "avg_maturity_cap_years" for w in clean)


def test_financial_nmd_gets_no_core_and_lands_overnight():
    """금융기관 NMD는 코어 인정 불가 — 전액 최단 버킷 (BCBS d368 Annex 2)."""
    bk = P.build_time_buckets()
    nm = P.build_nmd_param(ASOF).set_index("nmd_category").loc["financial"]
    assert nm["core_ratio_cap"] == 0.0
    pts, achieved, _ = nmd_slotting(
        1e12, core_ratio=nm["core_ratio"], core_ratio_cap=nm["core_ratio_cap"],
        avg_maturity_years=nm["avg_maturity_years"],
        avg_maturity_cap_years=nm["avg_maturity_cap_years"],
        buckets=bk, stable_ratio=None, scope="financial")
    assert len(pts) == 1
    assert pts[0].t_years == pytest.approx(bk["t_mid_years"].iloc[0])
    assert achieved == 0.0


def test_core_exceeding_stable_is_a_contradiction():
    bk = P.build_time_buckets()
    with pytest.raises(ValueError, match="코어는 안정예금의 부분집합"):
        nmd_slotting(1e12, core_ratio=0.9, core_ratio_cap=0.9,
                     avg_maturity_years=5.0, avg_maturity_cap_years=5.0,
                     buckets=bk, stable_ratio=0.5, scope="t")


def test_scurve_is_monotone_in_the_refinancing_incentive():
    """계수는 원장에서 온다 — 여기 값은 함수형 확인용 가설값이다."""
    vals = [scurve_ri(x, 0.05, 0.12, 30.0, 0.0)
            for x in (-0.04, -0.01, 0.0, 0.01, 0.04)]
    assert vals == sorted(vals)
    assert all(0.0 <= v < 1.0 for v in vals)


# ---------------------------------------------------------------- 계수 원장

def test_every_parameter_ledger_validates_against_its_spec():
    led = P.build_param_ledgers(ASOF)
    specs = {s.name: s for s in P.PARAM_TABLES}
    for name, df in led.items():
        assert validate(df, specs[name]) == [], name


def test_unverified_coefficients_are_null_not_invented():
    """규약: 모르면 비워 둔다. 이 검사가 '나중에 채워 넣기'를 막는다.

    **바뀐 것.** 시나리오 승수 steepener·flattener는 여기서 빠졌다. 1차자료
    발췌(§A-7·§A-8)로 네 칸이 확인돼 더 이상 미확인이 아니다. 확인된 값을
    계속 비워 두는 것도 규약 위반이다. 아래 세 가지는 여전히 규정이 값을 주지
    않는 자리다 — TDRR 기준율, S-curve 계수, NMD financial 범주.
    """
    led = P.build_param_ledgers(ASOF)
    nmd = led["alm_nmd_param"].set_index("nmd_category")
    # d368 Annex 2 Table 2는 소매결제성·소매비결제성·도매 세 줄뿐이고
    # 금융기관 범주가 없다 — 코어 0%는 설계의 가정이지 원문값이 아니다.
    assert nmd.loc["financial", "evidence_status"] == "미확인"
    assert (nmd.loc[["retail_transactional", "retail_non_transactional",
                     "wholesale_nonfin"], "evidence_status"] == "원문확인").all()

    tdrr = led["alm_behaviour_param"].query("model == 'TDRR'")
    assert tdrr["base_rate_annual"].isna().all()

    sc = led["alm_prepay_scurve_param"]
    assert not sc["enabled"].any()
    assert sc[["coef_a", "coef_b", "coef_c", "coef_d"]].isna().all().all()


def test_house_bucket_ladder_does_not_claim_the_standard_citation():
    """9개 자체집계에 'SRP31.94 표준 만기 구간'을 다는 것은 허위 표기다."""
    bk = P.build_time_buckets()
    assert (bk["framework_version"] == "house_9").all()
    assert not bk["citation"].str.contains("SRP31").any()
    assert (bk["evidence_status"] == "미확인").all()
    # 표준 19버킷은 경계를 모르므로 적재하지 않는다.
    assert "bcbs_19" not in set(bk["framework_version"])


def test_bucket_ledger_boundaries_are_contiguous():
    bk = P.build_time_buckets().sort_values("seq")
    assert bk["lower_years"].iloc[0] == 0.0
    assert (bk["lower_years"].to_numpy()[1:]
            == bk["upper_years"].to_numpy()[:-1]).all()
    assert ((bk["t_mid_years"] >= bk["lower_years"])
            & (bk["t_mid_years"] <= bk["upper_years"])).all()


# ---------------------------------------------------------------- 엔진

@pytest.fixture(scope="module")
def engine(portfolio):
    from risk_lib.alm.balance_sheet import generate_balance_sheet
    bs = generate_balance_sheet(portfolio, capital_total=1.2e12, seed=SEED)
    led = P.build_param_ledgers(ASOF)
    con = build_contract_ledger(portfolio, asof=ASOF, funding=bs.funding,
                                hqla=bs.hqla, equity=bs.equity,
                                base_rate=0.03, seed=SEED)
    res = build_cashflows(
        con, asof=ASOF, product_terms=led["alm_product_terms"],
        buckets=led["alm_time_bucket"],
        behaviour_param=led["alm_behaviour_param"],
        scenario_mult=led["alm_behaviour_scenario_mult"],
        nmd_param=led["alm_nmd_param"],
        scurve_param=led["alm_prepay_scurve_param"])
    return con, led, res


def test_contract_ledger_validates(engine):
    con, _, _ = engine
    assert validate(con, CONTRACT) == []


def test_cashflow_ledgers_validate(engine):
    _, _, res = engine
    specs = {s.name: s for s in CASHFLOW_TABLES}
    for name, df in (("alm_cashflow_contract", res.contract),
                     ("alm_cashflow_behavioural", res.behavioural),
                     ("alm_cashflow_bucket", res.bucket)):
        assert validate(df, specs[name]) == [], name


def test_contract_cashflow_principal_ties_to_notional(engine):
    """설계의 alm_cf_contract_ties_to_notional. 계약 한 건도 새지 않아야 한다."""
    con, _, res = engine
    got = res.contract.groupby("contract_id")["principal_cf"].sum()
    want = con.set_index("contract_id")["notional"].reindex(got.index)
    assert (got - want).abs().max() < 1e-3
    assert len(got) == len(con)          # 현금흐름이 없는 계약이 있으면 안 된다


def test_behavioural_principal_also_ties_to_notional(engine):
    _, _, res = engine
    con, _, _ = engine
    beh = res.behavioural.query("scenario == 'base'")
    got = beh.groupby("contract_id")["principal_cf"].sum()
    want = con.set_index("contract_id")["notional"].reindex(got.index)
    assert (got - want).abs().max() < 1e-3


def test_adjustment_cf_reconciles_behaviour_minus_contract(engine):
    """설계의 alm_behavioural_delta_attributable."""
    _, _, res = engine
    for sc in CF_SCENARIOS:
        beh = res.behavioural.query("scenario == @sc")
        lhs = float((beh["principal_cf"] + beh["interest_cf_ex_margin"]
                     + beh["margin_cf"]).sum())
        con_side = res.contract[
            res.contract["contract_id"].isin(set(beh["contract_id"]))]
        rhs = float((con_side["principal_cf"]
                     + con_side["interest_cf_ex_margin"]
                     + con_side["margin_cf"]).sum())
        # 상대오차 — 1.5e10 규모 합산의 float64 누적 순서 차이(≈1e-13)까지
        # 절대 1e-3으로 묶으면 결함이 아니라 부동소수점을 잡는 검사가 된다.
        assert float(beh["adjustment_cf"].sum()) == pytest.approx(lhs - rhs,
                                                                  rel=1e-9)


def test_nmd_behaviour_materially_lengthens_liability_slotting(engine):
    """계약기준 vs 행동기준 — 감독당국이 비교하는 바로 그 차이가 나와야 한다."""
    _, _, res = engine
    b = res.bucket.query("scenario == 'base' and side == 'liability'")
    wal = {}
    for basis in ("계약", "행동조정"):
        s = b.query("basis == @basis")
        wal[basis] = float((s["principal_cf"] * s["t_mid"]).sum()
                           / s["principal_cf"].sum())
        # 부채 원금 총액은 기준을 바꿔도 같다 — 슬로팅만 달라진다.
    assert wal["행동조정"] > wal["계약"] * 2.0


def test_prepayment_scenario_direction_shows_in_the_ladder(engine):
    """γ<1(금리상승)이면 조기상환이 느려져 만기가 길어진다."""
    _, _, res = engine
    m = res.behavioural.query("behaviour_model == 'CPR'")
    wal = {sc: float((g["principal_cf"] * g["t_mid"]).sum()
                     / g["principal_cf"].sum())
           for sc, g in m.groupby("scenario")}
    assert wal["parallel_up"] > wal["base"] > wal["parallel_down"]
    # **바뀐 것.** steepener는 승수가 NULL이라 base와 같았다. 1차자료 §A-7로
    # γ=0.8이 확인돼 parallel_up과 같은 승수를 쓰므로 이제 그쪽과 같아야 한다.
    assert wal["steepener"] == pytest.approx(wal["parallel_up"], rel=1e-12)
    assert wal["flattener"] == pytest.approx(wal["parallel_down"], rel=1e-12)


def test_missing_parameters_surface_as_warnings(engine):
    """비어 있음이 산출물에 실려 나가야 한다 — 조용한 폴백은 통제가 아니다."""
    _, _, res = engine
    wf = res.warning_frame()
    assert not wf.empty
    # **바뀐 것.** CPR은 승수 12칸이 전부 채워져 더 이상 경고를 내지 않는다.
    # 남는 공백은 TDRR 기준율(규정 미제시)과 NMD 안정예금 비율(자체추정)이다.
    assert {"TDRR", "NMD"} <= set(wf["model"])
    assert "CPR" not in set(wf["model"])
    assert (wf["param"] == "base_rate_annual").any()


def test_own_equity_is_excluded_from_the_bucket_ledger(engine):
    """BCBS d368 §132 — 자기자본 미투자 가정. 제외액은 보고되어야 한다."""
    con, _, res = engine
    equity = float(con.query("is_own_equity")["notional"].sum())
    assert res.own_equity_excluded == pytest.approx(equity, rel=1e-12)
    assert res.contract["is_own_equity"].any()      # 대조를 위해 원장에는 남는다
    liab = res.bucket.query("scenario == 'base' and basis == '계약' "
                            "and side == 'liability'")["principal_cf"].sum()
    con_liab = float(con.query("side == 'liability'")["notional"].sum())
    assert float(liab) == pytest.approx(con_liab - equity, rel=1e-9)


def test_floating_contracts_slot_the_notional_at_the_reset_date(engine):
    """BCBS d368 Annex 2 — 변동금리는 명목 전액을 차기 리프라이싱일에 슬로팅."""
    _, _, res = engine
    flt = res.contract.query("repricing_flag")
    assert not flt.empty
    # 리프라이싱 슬로팅은 계약당 버킷 1개다 — 여러 개면 스케줄이 섞인 것이다.
    assert flt.groupby("contract_id").size().max() == 1
    assert (flt["t_mid"] <= 0.5).all()


def test_engine_reads_bucket_count_from_the_ledger(portfolio):
    """K를 소스에서 뺐는지 확인 — 버킷 수를 바꿔도 엔진이 동작해야 한다."""
    from risk_lib.alm.balance_sheet import generate_balance_sheet
    bs = generate_balance_sheet(portfolio, capital_total=1.2e12, seed=SEED)
    led = P.build_param_ledgers(ASOF)
    coarse = pd.DataFrame([
        {"framework_version": "house_9", "seq": 1, "label": "0-1y",
         "lower_years": 0.0, "upper_years": 1.0, "t_mid_years": 0.5,
         "citation": "test", "evidence_status": "미확인"},
        {"framework_version": "house_9", "seq": 2, "label": "1y+",
         "lower_years": 1.0, "upper_years": 30.0, "t_mid_years": 5.0,
         "citation": "test", "evidence_status": "미확인"},
    ])
    con = build_contract_ledger(portfolio, asof=ASOF, funding=bs.funding,
                                hqla=bs.hqla, equity=bs.equity,
                                base_rate=0.03, seed=SEED)
    res = build_cashflows(
        con, asof=ASOF, product_terms=led["alm_product_terms"],
        buckets=coarse, behaviour_param=led["alm_behaviour_param"],
        scenario_mult=led["alm_behaviour_scenario_mult"],
        nmd_param=led["alm_nmd_param"],
        scurve_param=led["alm_prepay_scurve_param"])
    assert set(res.contract["bucket"]) <= {"0-1y", "1y+"}
    got = res.contract.groupby("contract_id")["principal_cf"].sum()
    want = con.set_index("contract_id")["notional"].reindex(got.index)
    assert (got - want).abs().max() < 1e-3


def test_engine_is_deterministic(portfolio):
    """(asof, seed)가 같으면 비트 단위로 같다."""
    from risk_lib.alm.balance_sheet import generate_balance_sheet
    bs = generate_balance_sheet(portfolio, capital_total=1.2e12, seed=SEED)

    def once():
        led = P.build_param_ledgers(ASOF)
        con = build_contract_ledger(portfolio, asof=ASOF, funding=bs.funding,
                                    hqla=bs.hqla, equity=bs.equity,
                                    base_rate=0.03, seed=SEED)
        return build_cashflows(
            con, asof=ASOF, product_terms=led["alm_product_terms"],
            buckets=led["alm_time_bucket"],
            behaviour_param=led["alm_behaviour_param"],
            scenario_mult=led["alm_behaviour_scenario_mult"],
            nmd_param=led["alm_nmd_param"],
            scurve_param=led["alm_prepay_scurve_param"])

    a, b = once(), once()
    assert a.contract.equals(b.contract)
    assert a.behavioural.equals(b.behavioural)
    assert a.bucket.equals(b.bucket)


def test_unmapped_funding_category_is_refused_not_dropped(portfolio):
    """매핑 없는 조달 잔액이 조용히 사라지면 대차가 깨진다."""
    from risk_lib.alm.balance_sheet import generate_balance_sheet
    bs = generate_balance_sheet(portfolio, capital_total=1.2e12, seed=SEED)
    funding = dict(bs.funding)
    funding["retail_crypto_deposits"] = 1e11
    with pytest.raises(KeyError, match="대응하는 ALM 상품이 없다"):
        build_contract_ledger(portfolio, asof=ASOF, funding=funding,
                              hqla=bs.hqla, equity=bs.equity,
                              base_rate=0.03, seed=SEED)


# ---------------------------------------------------------------- 보조

def _mortgage_schedule():
    return build_schedule(asof=date(2026, 1, 31), maturity=date(2036, 1, 31),
                          opening_balance=1e9, annual_rate=0.045,
                          amort_type="annuity", pay_freq_per_year=12,
                          day_count="ACT/365F")


def _wal(points) -> float:
    tot = sum(p.principal for p in points)
    return sum(p.principal * p.t_years for p in points) / tot


def _wal_with_broken_sifma_order(sched, cpr: float) -> float:
    """PP = SMM·B (SP 미차감) — 순서를 위반한 재구현. 검사가 잡아야 할 결함."""
    bal, prev, num, den = sched[0].opening_balance, 0.0, 0.0, 0.0
    for k, ins in enumerate(sched, start=1):
        tau = ins.t_years - prev
        if k == len(sched):
            sp, pp = bal, 0.0
        else:
            ratio = bal / ins.opening_balance if ins.opening_balance else 0.0
            sp = ratio * ins.principal
            pp = smm_from_cpr(cpr, tau) * bal
        num += (sp + pp) * ins.t_years
        den += sp + pp
        bal = max(bal - sp - pp, 0.0)
        prev = ins.t_years
    return num / den
