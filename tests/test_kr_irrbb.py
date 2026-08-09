"""[별표 9-1] 국내 고유 요건과 폐지된 2014년 체계. 불변식 고정.

이 파일의 규칙: 통과만으로는 통제가 아니다. 각 검사는 결함을 되돌렸을 때 실제로
실패해야 한다. 규정을 직접 겨냥하는 검사는 아래와 같다.

  · `test_the_2014_framework_is_out_of_the_headline_path`
    2014년 체계는 2019.11.29 개정으로 폐지됐다. 파이프라인이 이 모듈을 부르면
    폐지된 수치가 헤드라인으로 올라간다.
  · `test_sme_deposit_is_retail_only_below_the_ledger_threshold`
    제8항 가는 15억원 **미만**이다. 경계값 15억원은 소매가 아니다.
  · `test_sme_loan_is_retail_only_at_or_below_the_ledger_threshold`
    제9항은 10억원 **이하**다. 경계값 10억원은 소매다. 두 조항의 비교 방향이
    다르므로 한쪽을 복사하면 경계에서 한 건씩 어긋난다.
  · `test_wholesale_behavioural_options_become_automatic_options`
    제7항 나(2) 단서. 도매고객 행동옵션은 사라지지 않고 제11항으로 넘어간다.
  · `test_volatility_expansion_comes_from_the_param_ledger`
    확대율이 소스에 박혀 있으면 원장을 고쳐도 재평가가 움직이지 않는다.
  · `test_ear_ignores_buckets_beyond_one_year`
    금리 EaR은 만기구간 1년 이하만 쓴다(2014년 체계 제7항).
  · `test_engine_functions_carry_no_numeric_constants`
    중간시점·수정듀레이션이 원장에서 와야 버킷을 바꿨을 때 산출이 따라 움직인다.
"""

from __future__ import annotations

import ast
import inspect
import math
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from risk_lib.alm import kr_irrbb as K
from risk_lib.alm.contracts import build_contract_ledger
from risk_lib.alm.params import IRRBB_SCENARIOS
from risk_lib.data_gen import generate_portfolio
from risk_lib.datamodel.spec import check_refs, validate

ASOF = "2026-08-08"
SEED = 42
FW = K.KR_FRAMEWORK_2014

# 제8항 가 15억원(미만) · 제9항 10억원(이하). 검사가 원장 값을 직접 대조한다.
NMD_THRESHOLD = 1_500_000_000.0
LOAN_THRESHOLD = 1_000_000_000.0
VOL_EXPANSION = 0.25

# <표 2> 원문값. 원장이 이 값을 담고 있는지를 검사가 직접 대조한다.
T_MID = [0.042, 0.167, 0.375, 0.75, 1.5, 2.5, 3.5, 4.5, 6.0, 8.5, 12.5,
         17.5, 22.5]
MOD_DUR = [0.04, 0.16, 0.36, 0.71, 1.38, 2.25, 3.07, 3.85, 5.08, 6.63, 8.92,
           11.21, 13.01]


# ---------------------------------------------------------------- 도우미

def _buckets() -> pd.DataFrame:
    return K.build_kr_irrbb_bucket()


def _shock(measured: dict[str, float] | None = None) -> pd.DataFrame:
    """원화는 총자산 5% 이상 · G-10 이외, 미달러는 5% 미만."""
    return K.build_kr_irrbb_shock_param(
        {"KRW": 0.94, "USD": 0.03}, g10_ccys=("USD",),
        measured_shock_bp=measured)


def _contracts(rows: list[dict], *, asof: str = ASOF) -> pd.DataFrame:
    """검사용 최소 계약원장. 갭 산출이 읽는 컬럼만 담는다."""
    base = {"asof": asof, "product_code": "X", "side": "asset", "ccy": "KRW",
            "notional": 0.0, "maturity_date": None, "next_reset_date": None,
            "is_own_equity": False}
    out = []
    for i, r in enumerate(rows, start=1):
        d = dict(base)
        d.update(r)
        d.setdefault("contract_id", f"C{i:04d}")
        out.append(d)
    return pd.DataFrame(out)


def _monthly(balances: list[float], ccy: str = "KRW") -> pd.DataFrame:
    """lag 0 = t월. 리스트 순서를 그대로 시차로 읽는다."""
    return pd.DataFrame([{"ccy": ccy, "lag_months": i, "avg_balance": float(b)}
                         for i, b in enumerate(balances)])


def _flat_gap(amounts: list[float], *, ccy: str = "KRW") -> pd.DataFrame:
    """13구간 갭 사다리를 직접 만든다. 엔진 산식만 떼어 보기 위한 입력."""
    b = _buckets()
    return pd.DataFrame([{
        "asof": ASOF, "framework_version": FW, "ccy": ccy,
        "seq": int(r.seq), "label": r.label,
        "rate_sensitive_asset": max(a, 0.0),
        "rate_sensitive_liability": max(-a, 0.0),
        "gap_amount": float(a), "citation": None,
        "evidence_status": "원문확인",
    } for r, a in zip(b.itertuples(), amounts)])


def _core(ratio: float = 1.0, ccy: str = "KRW") -> pd.DataFrame:
    """핵심예금 원장을 비율만 지정해 만든다."""
    bal = 1.0e12
    return pd.DataFrame([{
        "asof": ASOF, "ccy": ccy, "scope": "검사용", "n_months": 12,
        "latest_month_avg_balance": bal, "weighted_mean": bal,
        "weighted_std": 0.0, "multiplier": 2.33,
        "core_amount": bal * ratio, "non_core_amount": bal * (1 - ratio),
        "core_ratio": ratio, "is_floored": False, "std_formula": "검사용",
        "citation": None, "evidence_status": "원문확인",
    }])


def _numeric_constants(fn) -> list[float]:
    """함수 본문(독스트링 제외)의 숫자 리터럴."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    node = tree.body[0]
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    found = []
    for stmt in body:
        for n in ast.walk(stmt):
            if (isinstance(n, ast.Constant) and not isinstance(n.value, bool)
                    and isinstance(n.value, (int, float))):
                found.append(n.value)
    return found


# ---------------------------------------------------------------- 원장 품질

def test_all_kr_ledgers_validate_against_their_specs():
    specs = {s.name: s for s in K.KR_IRRBB_TABLES}
    b = _buckets()
    core, _w = K.build_kr_core_deposit(
        _monthly([100.0] * 12), K.build_kr_core_deposit_weight(), asof=ASOF)
    con = _contracts([
        {"notional": 300.0, "maturity_date": "2027-08-08"},
        {"side": "liability", "notional": 200.0, "product_code": "D"},
        {"side": "liability", "notional": 50.0, "is_own_equity": True},
    ])
    res = K.compute_kr_irrbb(
        con, b, _shock(), asof=ASOF, own_capital=1000.0, core_deposit=core)

    assert validate(b, specs["kr_irrbb_bucket"]) == []
    assert validate(_shock(), specs["kr_irrbb_shock_param"]) == []
    assert validate(K.build_kr_core_deposit_weight(),
                    specs["kr_core_deposit_weight"]) == []
    assert validate(core, specs["kr_core_deposit"]) == []
    assert validate(res.gap, specs["kr_irrbb_gap"]) == []
    assert validate(res.result, specs["kr_irrbb_result"]) == []


def test_gap_references_an_existing_bucket_row():
    b = _buckets()
    core, _w = K.build_kr_core_deposit(
        _monthly([100.0] * 12), K.build_kr_core_deposit_weight(), asof=ASOF)
    gap, _e, _w2 = K.build_kr_irrbb_gap(
        _contracts([{"notional": 10.0, "maturity_date": "2030-01-01"}]),
        b, asof=ASOF, core_deposit=core)
    specs = {s.name: s for s in K.KR_IRRBB_TABLES}
    assert check_refs({"kr_irrbb_gap": gap, "kr_irrbb_bucket": b}, specs) == []


# ---------------------------------------------------------------- <표 2> 버킷

def test_bucket_ladder_is_the_thirteen_domestic_buckets():
    b = _buckets()
    assert len(b) == 13
    assert list(b["t_mid_years"]) == T_MID
    assert list(b["modified_duration_years"]) == MOD_DUR
    assert set(b["evidence_status"]) == {"원문확인"}


def test_ear_target_is_the_four_buckets_within_one_year():
    b = _buckets()
    tgt = b[b["is_ear_target"].astype(bool)]
    assert list(tgt["label"]) == ["0~1월", "1~3월", "3~6월", "6~12월"]
    assert K.ear_horizon_years(b) == 1.0


def test_core_deposit_slots_are_the_eight_buckets_within_five_years():
    b = _buckets()
    slots = b[b["is_core_deposit_slot"].astype(bool)]
    assert len(slots) == 8
    assert float(slots["upper_years"].max()) == 5.0


# ---------------------------------------------------------------- 엔진 산식

def test_engine_functions_carry_no_numeric_constants():
    """중간시점·수정듀레이션·대상구간은 전부 원장에서 온다."""
    for fn in (K.kr_ear, K.kr_var, K._join, K.ear_horizon_years):
        assert _numeric_constants(fn) == [], fn.__name__
    # 버킷 원장 빌더도 <표 2> 값을 직접 적지 않고 규제표 상수 하나를 읽는다.
    # 남는 숫자는 enumerate의 시작 인덱스뿐이다.
    lits = set(_numeric_constants(K.build_kr_irrbb_bucket))
    assert lits & (set(T_MID) | set(MOD_DUR)) == set()
    assert lits == {1}


def test_var_moves_with_the_duration_in_the_ledger():
    b = _buckets()
    gap = _flat_gap([1.0e9] * 13)
    base = K.kr_var(gap, b, shock_bp=200.0)
    doubled = b.copy()
    doubled["modified_duration_years"] = doubled["modified_duration_years"] * 2
    assert K.kr_var(gap, doubled, shock_bp=200.0) == pytest.approx(base * 2)


def test_ear_ignores_buckets_beyond_one_year():
    """제7항. 금리 EaR은 만기구간 1년 이하만 대상이다."""
    b = _buckets()
    amounts = [1.0e9] * 13
    gap = _flat_gap(amounts)
    ear0 = K.kr_ear(gap, b, shock_bp=200.0, horizon_years=1.0)
    var0 = K.kr_var(gap, b, shock_bp=200.0)

    bumped = list(amounts)
    bumped[8] += 5.0e11          # 5~7년 구간을 크게 키운다
    gap2 = _flat_gap(bumped)
    assert K.kr_ear(gap2, b, shock_bp=200.0, horizon_years=1.0) == ear0
    assert K.kr_var(gap2, b, shock_bp=200.0) != var0


def test_var_uses_every_bucket():
    b = _buckets()
    for i in range(13):
        amounts = [0.0] * 13
        amounts[i] = 1.0e9
        v = K.kr_var(_flat_gap(amounts), b, shock_bp=200.0)
        assert v == pytest.approx(1.0e9 * MOD_DUR[i] * 0.02)


def test_ear_reproduces_the_formula_bucket_by_bucket():
    b = _buckets()
    amounts = [1.0e9, -2.0e9, 3.0e9, 4.0e9] + [7.0e9] * 9
    expect = sum(amounts[i] * (1.0 - T_MID[i]) * 0.02 for i in range(4))
    got = K.kr_ear(_flat_gap(amounts), b, shock_bp=200.0, horizon_years=1.0)
    assert got == pytest.approx(expect)


def test_gap_of_more_than_one_currency_is_refused():
    b = _buckets()
    two = pd.concat([_flat_gap([1.0] * 13), _flat_gap([1.0] * 13, ccy="USD")])
    with pytest.raises(ValueError, match="통화 하나"):
        K.kr_var(two, b, shock_bp=200.0)


# ---------------------------------------------------------------- <표 5> 핵심예금

def test_core_deposit_weights_sum_to_one():
    w = K.build_kr_core_deposit_weight()
    assert len(w) == 12
    assert float(w["weight"].sum()) == pytest.approx(1.0, abs=1e-15)
    assert float(w.loc[w["lag_months"] == 0, "weight"].iloc[0]) == 12 / 78
    assert float(w.loc[w["lag_months"] == 11, "weight"].iloc[0]) == 1 / 78


def test_core_deposit_matches_a_hand_calculation():
    bal = [1000.0, 900.0, 1100.0, 1000.0, 900.0, 1100.0,
           1000.0, 900.0, 1100.0, 1000.0, 900.0, 1100.0]
    w = [(12 - i) / 78 for i in range(12)]
    mean = sum(w[i] * bal[i] for i in range(12))
    std = math.sqrt(sum(w[i] * (bal[i] - mean) ** 2 for i in range(12)))
    expect = bal[0] - std * 2.33

    core, warns = K.build_kr_core_deposit(
        _monthly(bal), K.build_kr_core_deposit_weight(), asof=ASOF)
    row = core.iloc[0]
    assert warns == []
    assert float(row["weighted_mean"]) == pytest.approx(mean)
    assert float(row["weighted_std"]) == pytest.approx(std)
    assert float(row["core_amount"]) == pytest.approx(expect)
    assert float(row["non_core_amount"]) == pytest.approx(bal[0] - expect)


def test_constant_balances_make_the_whole_deposit_core():
    core, _w = K.build_kr_core_deposit(
        _monthly([500.0] * 12), K.build_kr_core_deposit_weight(), asof=ASOF)
    row = core.iloc[0]
    assert float(row["weighted_std"]) == pytest.approx(0.0, abs=1e-9)
    assert float(row["core_amount"]) == pytest.approx(500.0)
    assert float(row["core_ratio"]) == pytest.approx(1.0)


def test_short_history_is_skipped_not_extrapolated():
    core, warns = K.build_kr_core_deposit(
        _monthly([500.0] * 9), K.build_kr_core_deposit_weight(), asof=ASOF)
    assert core.empty
    assert any(w.param == "monthly_balance" for w in warns)


def test_negative_core_is_floored_and_disclosed():
    bal = [100.0] + [900.0, 100.0] * 5 + [900.0]
    core, warns = K.build_kr_core_deposit(
        _monthly(bal), K.build_kr_core_deposit_weight(), asof=ASOF)
    row = core.iloc[0]
    assert bool(row["is_floored"])
    assert float(row["core_amount"]) == 0.0
    assert any(w.param == "core_amount" for w in warns)


def test_core_deposit_is_spread_over_eight_buckets_at_one_eighth():
    """<표 1>. 핵심예금은 5년 이내 8개 구간에 12.5%씩, 비핵심은 0~1월."""
    b = _buckets()
    con = _contracts([{"side": "liability", "notional": 800.0,
                       "product_code": "DEP_NMD"}])
    gap, _e, _w = K.build_kr_irrbb_gap(
        con, b, asof=ASOF, core_deposit=_core(ratio=1.0))
    liab = gap.set_index("seq")["rate_sensitive_liability"]
    assert [float(liab[s]) for s in range(1, 9)] == [100.0] * 8
    assert [float(liab[s]) for s in range(9, 14)] == [0.0] * 5
    assert float(liab.sum()) == pytest.approx(800.0)


def test_non_core_deposit_goes_to_the_shortest_bucket():
    b = _buckets()
    con = _contracts([{"side": "liability", "notional": 800.0}])
    gap, _e, _w = K.build_kr_irrbb_gap(
        con, b, asof=ASOF, core_deposit=_core(ratio=0.25))
    liab = gap.set_index("seq")["rate_sensitive_liability"]
    # 핵심 200을 8구간에 25씩, 비핵심 600은 최단구간에 얹힌다.
    assert float(liab[1]) == pytest.approx(625.0)
    assert [float(liab[s]) for s in range(2, 9)] == [25.0] * 7


def test_missing_core_deposit_row_warns_and_treats_the_deposit_as_non_core():
    b = _buckets()
    con = _contracts([{"side": "liability", "notional": 800.0}])
    gap, _e, warns = K.build_kr_irrbb_gap(
        con, b, asof=ASOF, core_deposit=_core(ratio=1.0, ccy="USD"))
    liab = gap.set_index("seq")["rate_sensitive_liability"]
    assert float(liab[1]) == pytest.approx(800.0)
    assert any(w.param == "core_ratio" for w in warns)


# ---------------------------------------------------------------- <표 3> 충격폭

def test_krw_is_the_second_row_of_the_table_and_has_no_fixed_bp():
    sp = _shock()
    krw = sp[sp["ccy"] == "KRW"].iloc[0]
    assert krw["asset_share_band"] == "5%이상"
    assert not bool(krw["is_g10"])
    assert krw["method"] == "5년실측 1%·99%"
    assert pd.isna(krw["shock_bp"])
    assert krw["evidence_status"] == "미확인"


def test_currency_below_five_percent_of_assets_gets_the_regulated_200bp():
    sp = _shock()
    usd = sp[sp["ccy"] == "USD"].iloc[0]
    assert usd["asset_share_band"] == "5%미만"
    assert usd["method"] == "고정200bp"
    assert float(usd["shock_bp"]) == 200.0
    assert usd["evidence_status"] == "원문확인"


def test_krw_without_a_measured_shock_stays_empty():
    """200bp가 조용히 대입되면 규정이 아니라 다른 줄의 값이 들어간 것이다."""
    b = _buckets()
    gap = pd.concat([_flat_gap([1.0e9] * 13),
                     _flat_gap([1.0e9] * 13, ccy="USD")], ignore_index=True)
    res, warns = K.build_kr_irrbb_result(
        gap, b, _shock(), asof=ASOF, own_capital=1.0e12)
    krw = res[res["ccy"] == "KRW"].iloc[0]
    assert pd.isna(krw["shock_bp"])
    assert pd.isna(krw["ear_amount"])
    assert pd.isna(krw["var_amount"])
    assert pd.isna(krw["total_ir_risk"])
    assert krw["evidence_status"] == "미확인"
    assert any(w.scope == "KRW" and w.param == "shock_bp" for w in warns)
    # 합계는 산출된 통화(USD)만 담는다.
    usd = res[res["ccy"] == "USD"].iloc[0]
    tot = res[res["is_total"].astype(bool)].iloc[0]
    assert float(tot["var_amount"]) == pytest.approx(float(usd["var_amount"]))


def test_a_measured_shock_fills_the_krw_row():
    b = _buckets()
    gap = _flat_gap([1.0e9] * 13)
    res, warns = K.build_kr_irrbb_result(
        gap, b, _shock({"KRW": 315.0}), asof=ASOF, own_capital=1.0e12)
    krw = res[res["ccy"] == "KRW"].iloc[0]
    assert float(krw["shock_bp"]) == 315.0
    assert krw["shock_method"] == "5년실측 1%·99%"
    assert not any(w.param == "shock_bp" for w in warns)


def test_no_priced_currency_leaves_the_verdict_open_not_false():
    b = _buckets()
    res, _w = K.build_kr_irrbb_result(
        _flat_gap([1.0e9] * 13), b, _shock(), asof=ASOF, own_capital=1.0e12)
    tot = res[res["is_total"].astype(bool)].iloc[0]
    assert pd.isna(tot["is_outlier"])
    assert pd.isna(tot["total_ir_risk"])


# ---------------------------------------------------------------- 제27항 판정

def _result_at(ratio: float) -> pd.Series:
    """총 금리리스크가 자기자본의 `ratio`가 되도록 갭을 역산한다."""
    b = _buckets()
    own = 1.0e12
    md = MOD_DUR[0]
    gap_amt = own * ratio / (md * 0.02)
    amounts = [gap_amt] + [0.0] * 12
    res, _w = K.build_kr_irrbb_result(
        _flat_gap(amounts, ccy="USD"), b, _shock(), asof=ASOF,
        own_capital=own)
    return res[res["is_total"].astype(bool)].iloc[0]


def test_outlier_uses_own_capital_at_twenty_percent():
    """제27항. 자기자본의 20%를 **초과**하는 은행이 outlier다."""
    at = _result_at(0.20)
    assert float(at["risk_to_own_capital"]) == pytest.approx(0.20)
    assert bool(at["is_outlier"]) is False

    over = _result_at(0.2001)
    assert bool(over["is_outlier"]) is True

    under = _result_at(0.1999)
    assert bool(under["is_outlier"]) is False


def test_the_denominator_is_own_capital_not_tier1():
    row = _result_at(0.10)
    assert float(row["outlier_threshold"]) == 0.20
    assert "자기자본" in str(row["denominator_basis"])
    assert "Tier" not in str(row["denominator_basis"])
    assert float(row["own_capital"]) == 1.0e12


def test_zero_own_capital_is_refused_not_divided_by():
    with pytest.raises(ValueError, match="자기자본"):
        K.build_kr_irrbb_result(_flat_gap([1.0] * 13), _buckets(), _shock(),
                                asof=ASOF, own_capital=0.0)


# ---------------------------------------------------------------- 제외항목

def test_excluded_items_are_reported_not_dropped():
    b = _buckets()
    con = _contracts([
        {"notional": 1000.0, "maturity_date": "2027-08-08"},
        {"side": "liability", "notional": 400.0, "is_own_equity": True},
        {"notional": 250.0, "product_code": "CASH", "maturity_date": None},
    ])
    gap, excl, _w = K.build_kr_irrbb_gap(
        con, b, asof=ASOF, core_deposit=_core(),
        exclude_product_codes={"CASH": "현금"})
    items = dict(zip(excl["item"], excl["amount"]))
    assert items == {"자본총계": 400.0, "현금": 250.0}
    assert float(gap["rate_sensitive_asset"].sum()) == pytest.approx(1000.0)
    assert float(gap["rate_sensitive_liability"].sum()) == 0.0


def test_excluded_amount_reaches_the_result_ledger():
    b = _buckets()
    con = _contracts([
        {"notional": 1000.0, "maturity_date": "2027-08-08", "ccy": "USD"},
        {"side": "liability", "notional": 400.0, "is_own_equity": True,
         "ccy": "USD"},
    ])
    res = K.compute_kr_irrbb(con, b, _shock(), asof=ASOF,
                             own_capital=1.0e6, core_deposit=_core())
    tot = res.result[res.result["is_total"].astype(bool)].iloc[0]
    assert float(tot["excluded_amount"]) == 400.0


def test_an_unknown_exclusion_item_is_refused():
    with pytest.raises(ValueError, match="제외 가능 항목"):
        K.build_kr_irrbb_gap(
            _contracts([{"notional": 1.0, "product_code": "Z"}]),
            _buckets(), asof=ASOF, core_deposit=_core(),
            exclude_product_codes={"Z": "영업권"})


def test_off_balance_contracts_are_refused_until_decomposed():
    with pytest.raises(ValueError, match="부외"):
        K.build_kr_irrbb_gap(
            _contracts([{"notional": 1.0, "side": "off_balance"}]),
            _buckets(), asof=ASOF, core_deposit=_core())


# ---------------------------------------------------------------- 슬로팅

def test_repricing_date_wins_over_maturity_date():
    b = _buckets()
    con = _contracts([{"notional": 100.0, "maturity_date": "2036-08-08",
                       "next_reset_date": "2026-09-08"}])
    gap, _e, _w = K.build_kr_irrbb_gap(con, b, asof=ASOF,
                                       core_deposit=_core())
    hit = gap[gap["rate_sensitive_asset"] > 0]
    assert list(hit["label"]) == ["1~3월"]


def test_beyond_the_last_boundary_lands_in_the_open_bucket():
    b = _buckets()
    con = _contracts([{"notional": 100.0, "maturity_date": "2060-08-08"}])
    gap, _e, _w = K.build_kr_irrbb_gap(con, b, asof=ASOF,
                                       core_deposit=_core())
    hit = gap[gap["rate_sensitive_asset"] > 0]
    assert list(hit["label"]) == ["20년초과"]


def test_every_currency_gets_the_full_thirteen_bucket_ladder():
    b = _buckets()
    con = _contracts([
        {"notional": 100.0, "maturity_date": "2027-08-08"},
        {"notional": 100.0, "maturity_date": "2029-08-08", "ccy": "USD"},
    ])
    gap, _e, _w = K.build_kr_irrbb_gap(con, b, asof=ASOF,
                                       core_deposit=_core())
    assert len(gap) == 26
    assert dict(gap.groupby("ccy").size()) == {"KRW": 13, "USD": 13}


# ---------------------------------------------------------------- 결정론

def test_same_inputs_give_byte_identical_ledgers():
    b = _buckets()
    con = _contracts([
        {"notional": 500.0, "maturity_date": "2028-01-01"},
        {"side": "liability", "notional": 300.0},
    ])
    a = K.compute_kr_irrbb(con, b, _shock({"KRW": 250.0}), asof=ASOF,
                           own_capital=1.0e6, core_deposit=_core(0.6))
    c = K.compute_kr_irrbb(con, b, _shock({"KRW": 250.0}), asof=ASOF,
                           own_capital=1.0e6, core_deposit=_core(0.6))
    assert a.gap.to_csv(index=False) == c.gap.to_csv(index=False)
    assert a.result.to_csv(index=False) == c.result.to_csv(index=False)


def test_contract_ledger_path_is_deterministic_for_the_same_asof_and_seed():
    """(asof, seed) 고정이면 계약원장부터 결과까지 바이트 동일하다."""
    b = _buckets()
    core, _w = K.build_kr_core_deposit(
        _monthly([9.0e11, 8.9e11, 9.1e11, 9.0e11, 8.8e11, 9.2e11,
                  9.0e11, 8.9e11, 9.1e11, 9.0e11, 8.8e11, 9.2e11]),
        K.build_kr_core_deposit_weight(), asof=ASOF)

    # 조달·HQLA·자기자본은 값을 직접 준다. 대차대조표 합성기를 거치면 이 검사가
    # 결정론이 아니라 그 모듈의 상태를 재는 검사가 된다.
    funding = {"retail_stable": 4.0e11, "retail_less_stable": 2.0e11,
               "corporate_operational": 1.5e11,
               "corporate_non_operational": 1.0e11,
               "wholesale_fi_lt6m": 5.0e10, "wholesale_fi_6to12m": 3.0e10,
               "funding_gt1y": 7.0e10}
    hqla = {"level_1": 2.0e11, "level_2a": 5.0e10, "level_2b": 2.0e10}
    equity = 9.0e10

    def _run() -> K.KrIrrbbResult:
        pf = generate_portfolio(n_corporate=40, n_retail=60, n_mortgage=20,
                                n_sovereign=3, n_bank=3, seed=SEED)
        con = build_contract_ledger(pf, asof=ASOF, funding=funding, hqla=hqla,
                                    equity=equity, base_rate=0.03, seed=SEED)
        return K.compute_kr_irrbb(
            con, b, _shock({"KRW": 250.0}), asof=ASOF,
            own_capital=equity, core_deposit=core)

    r1, r2 = _run(), _run()
    assert r1.gap.to_csv(index=False) == r2.gap.to_csv(index=False)
    assert r1.result.to_csv(index=False) == r2.result.to_csv(index=False)

    specs = {s.name: s for s in K.KR_IRRBB_TABLES}
    assert validate(r1.gap, specs["kr_irrbb_gap"]) == []
    assert validate(r1.result, specs["kr_irrbb_result"]) == []
    # 자기자본은 제외항목(자본총계)이므로 갭에 들어가지 않고 제외액에 남는다.
    assert float(r1.excluded["amount"].sum()) == pytest.approx(equity)
    assert r1.outlier() is not None
