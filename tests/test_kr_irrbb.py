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


# -------------------------------------------------- 국내 고유 요건 도우미

def _crit(rule_code: str | None = None, **cols) -> pd.DataFrame:
    """소매 유사 간주 기준 원장. 특정 규칙의 칸을 바꿔 끼울 수 있다.

    원장을 고쳤을 때 판정이 따라 움직이는지를 보려면 검사가 원장을 손댈 수
    있어야 한다.
    """
    df = K.build_kr_retail_criteria()
    if rule_code is not None:
        m = df["rule_code"] == rule_code
        for col, val in cols.items():
            df.loc[m, col] = val
    return df


def _deposits(rows: list[dict]) -> pd.DataFrame:
    """범주 판정 입력. 기본값은 개인 예치 · 정기적 거래 있음이다."""
    base = {"asof": ASOF, "ccy": "KRW", "depositor_type": "개인",
            "balance": 1.0e8, "is_retail_managed": None,
            "funding_total_amount": None, "has_regular_transaction": True,
            "is_interest_free": False}
    out = []
    for i, r in enumerate(rows, start=1):
        d = dict(base)
        d.update(r)
        d.setdefault("account_id", f"A{i:03d}")
        out.append(d)
    return pd.DataFrame(out)


def _behaviour(rows: list[dict]) -> pd.DataFrame:
    """행동옵션 범위 판정 입력. 기본값은 개인 보유 고정금리대출이다."""
    base = {"asof": ASOF, "ccy": "KRW", "notional": 1.0e8,
            "behaviour_class": "prepayment", "customer_type": "개인",
            "rate_type": "fixed", "is_retail_managed": None,
            "exposure_amount": None, "prepay_fee_charged": False,
            "has_legal_termination_right": True, "substantial_penalty": False}
    out = []
    for i, r in enumerate(rows, start=1):
        d = dict(base)
        d.update(r)
        d.setdefault("contract_id", f"K{i:03d}")
        out.append(d)
    return pd.DataFrame(out)


def _options(rows: list[dict] | None = None) -> pd.DataFrame:
    base = {"asof": ASOF, "ccy": "KRW", "position": "매도",
            "option_type": "금리캡", "notional": 1.0e9, "strike_rate": 0.03,
            "expiry_years": 2.0, "forward_rate_base": 0.032,
            "implied_vol_base": 0.01, "discount_factor_base": 0.94}
    out = []
    for i, r in enumerate(rows if rows is not None else [{}], start=1):
        d = dict(base)
        d.update(r)
        d.setdefault("option_id", f"O{i:03d}")
        out.append(d)
    return pd.DataFrame(out)


def _shifts(*, expiry_years: float = 2.0, rate_shift: float = 0.0225,
            floor_rate: float | None = 0.0, df_shocked: float = 0.90,
            ccy: str = "KRW") -> pd.DataFrame:
    """시나리오 곡선에서 뽑은 값. 6개 시나리오에 같은 값을 준다.

    시나리오별 충격 차이를 재는 검사가 아니라 국내 고유 요건(변동성 확대·
    합산부호·하한)이 원장에서 오는지를 재는 검사이므로 곡선은 고정한다.
    """
    return pd.DataFrame([{
        "ccy": ccy, "scenario": s, "expiry_years": float(expiry_years),
        "rate_shift": rate_shift, "floor_rate": floor_rate,
        "discount_factor_shocked": df_shocked} for s in IRRBB_SCENARIOS])


def _opt_param(code: str | None = None, value: float | None = None) -> pd.DataFrame:
    df = K.build_kr_auto_option_param()
    if code is not None:
        df.loc[df["param_code"] == code, "value"] = value
    return df


def _gov_records(rows: list[dict]) -> pd.DataFrame:
    base = {"period_label": "2026 사업연도", "count_in_period": None,
            "is_annual_period": True, "last_fulfilled_date": None,
            "evidence_ref": None, "is_fulfilled": None}
    return pd.DataFrame([{**base, **r} for r in rows])


def _reasons(warns) -> str:
    return " / ".join(w.reason for w in warns)


# -------------------------------------------------- 폐지 계정 분리

def test_the_2014_framework_is_out_of_the_headline_path():
    """2014년 체계는 폐지됐다. 헤드라인으로 올라가면 안 된다.

    세 가지를 함께 본다. 계정 표에서 헤드라인이 아니고, 산출물 행마다 폐지
    사실이 실려 있고, 저장소의 다른 모듈이 그 엔진을 부르지 않는다.
    """
    assert K.KR_IS_HEADLINE[K.KR_FRAMEWORK_2014] is False
    assert K.KR_IS_HEADLINE[K.KR_FRAMEWORK_2026] is True

    b = _buckets()
    assert set(b["framework_version"]) == {K.KR_FRAMEWORK_2014}
    res = K.compute_kr_irrbb(
        _contracts([{"notional": 300.0, "maturity_date": "2027-08-08"}]),
        b, _shock(), asof=ASOF, own_capital=1000.0, core_deposit=_core())
    assert set(res.result["framework_version"]) == {K.KR_FRAMEWORK_2014}
    assert set(res.result["framework_status"]) == {"폐지"}
    assert not res.result["is_headline"].any()

    # 폐지 엔진을 부르는 모듈이 있으면 파이프라인이 그것을 헤드라인으로 쓸 수
    # 있다. 이름이 산출 코드에 등장하는지를 직접 센다.
    legacy = ("compute_kr_irrbb", "kr_ear(", "kr_var(", "build_kr_irrbb_gap",
              "build_kr_irrbb_result", "KR_FRAMEWORK_2014")
    root = Path(__file__).resolve().parents[1] / "risk_lib"
    callers = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if p.name != "kr_irrbb.py"
        and any(name in p.read_text(encoding="utf-8") for name in legacy))
    assert callers == [], f"폐지된 2014년 체계를 부르는 모듈: {callers}"


# -------------------------------------------------- 원장 품질 (국내 고유 요건)

def test_national_ledgers_validate_against_their_specs():
    specs = {s.name: s for s in K.KR_NATIONAL_TABLES}
    crit = _crit()
    nmd, _w1 = K.classify_kr_nmd_category(
        _deposits([{}, {"depositor_type": "중소기업", "is_retail_managed": True,
                        "funding_total_amount": 1.0e9}]), crit, asof=ASOF)
    scope, _w2 = K.build_kr_retail_behavioural_scope(
        _behaviour([{}, {"behaviour_class": "early_redemption"}]),
        crit, asof=ASOF)
    det, _w3 = K.build_kr_auto_option(_options(), _shifts(), _opt_param(),
                                      asof=ASOF)
    risk = K.build_kr_auto_option_risk(det, asof=ASOF)
    gov, _w4 = K.build_kr_irrbb_governance(asof=ASOF)

    assert validate(crit, specs["kr_retail_criteria"]) == []
    assert validate(nmd, specs["kr_nmd_category"]) == []
    assert validate(scope, specs["kr_retail_behavioural_scope"]) == []
    assert validate(K.build_kr_auto_option_param(),
                    specs["kr_auto_option_param"]) == []
    assert validate(det, specs["kr_auto_option"]) == []
    assert validate(risk, specs["kr_auto_option_risk"]) == []
    assert validate(gov, specs["kr_irrbb_governance"]) == []

    assert check_refs({"kr_retail_criteria": crit, "kr_nmd_category": nmd,
                       "kr_retail_behavioural_scope": scope,
                       "kr_auto_option": det,
                       "kr_auto_option_risk": risk}, specs) == []


# -------------------------------------------------- 제8항 가 범주 판정

def test_sme_deposit_is_retail_only_below_the_ledger_threshold():
    """제8항 가는 15억원 **미만**이다. 경계값 15억원은 소매가 아니다."""
    crit = _crit()
    row = crit[crit["rule_code"] == K.KR_RULE_NMD_SME].iloc[0]
    assert float(row["threshold_amount"]) == NMD_THRESHOLD
    assert row["comparison"] == "미만"
    assert row["measure"] == "자금조달총액"
    assert row["consolidation_basis"] == "연결기준"

    df, _w = K.classify_kr_nmd_category(_deposits([
        {"depositor_type": "중소기업", "is_retail_managed": True,
         "funding_total_amount": NMD_THRESHOLD - 1.0},
        {"depositor_type": "중소기업", "is_retail_managed": True,
         "funding_total_amount": NMD_THRESHOLD},
    ]), crit, asof=ASOF)
    verdict = dict(zip(df["account_id"], df["is_retail"]))
    assert verdict["A001"] is True
    assert verdict["A002"] is False
    assert list(df["category"]) == ["소매/거래", "도매"]
    assert list(df["is_retail_like"]) == [True, False]


def test_the_nmd_threshold_moves_with_the_ledger():
    """기준금액이 원장에서 온다. 원장을 낮추면 같은 계좌가 도매로 내려간다."""
    dep = _deposits([{"depositor_type": "중소기업", "is_retail_managed": True,
                      "funding_total_amount": 1.2e9}])
    a, _w1 = K.classify_kr_nmd_category(dep, _crit(), asof=ASOF)
    b, _w2 = K.classify_kr_nmd_category(
        dep, _crit(K.KR_RULE_NMD_SME, threshold_amount=1.0e9), asof=ASOF)
    assert bool(a["is_retail"].iloc[0]) is True
    assert bool(b["is_retail"].iloc[0]) is False
    assert float(b["threshold_amount"].iloc[0]) == 1.0e9


def test_only_individuals_are_retail_deposits():
    """소매예금은 개인 예치분이다. 법인·개인사업자 예치분은 제외된다."""
    df, _w = K.classify_kr_nmd_category(_deposits([
        {"depositor_type": "개인"}, {"depositor_type": "개인사업자"},
        {"depositor_type": "법인"}, {"depositor_type": "금융기관"},
    ]), _crit(), asof=ASOF)
    assert list(df["is_retail"]) == [True, False, False, False]
    assert list(df["category"]) == ["소매/거래", "도매", "도매", "도매"]


def test_sme_deposit_not_managed_as_retail_stays_wholesale():
    df, _w = K.classify_kr_nmd_category(_deposits([
        {"depositor_type": "중소기업", "is_retail_managed": False,
         "funding_total_amount": 1.0},
    ]), _crit(), asof=ASOF)
    assert bool(df["is_retail"].iloc[0]) is False
    assert "소매계정으로 관리하지 않는다" in df["rule_applied"].iloc[0]


def test_missing_funding_total_is_warned_not_assumed():
    """자금조달총액이 비면 소매로 올리지 않고 경고를 남긴다."""
    df, warns = K.classify_kr_nmd_category(_deposits([
        {"depositor_type": "중소기업", "is_retail_managed": True,
         "funding_total_amount": None},
    ]), _crit(), asof=ASOF)
    assert bool(df["is_retail"].iloc[0]) is False
    assert df["evidence_status"].iloc[0] == "미확인"
    assert "자금조달총액" in _reasons(warns)


def test_a_missing_threshold_in_the_ledger_stops_the_retail_like_rule():
    df, warns = K.classify_kr_nmd_category(_deposits([
        {"depositor_type": "중소기업", "is_retail_managed": True,
         "funding_total_amount": 1.0},
    ]), _crit(K.KR_RULE_NMD_SME, threshold_amount=None), asof=ASOF)
    assert bool(df["is_retail"].iloc[0]) is False
    assert "기준금액이 비어 있다" in _reasons(warns)


def test_transactional_deposit_needs_regular_use_or_no_interest():
    """정기적 거래가 있거나 무이자면 거래예금, 그 외 소매는 비거래예금이다."""
    df, _w = K.classify_kr_nmd_category(_deposits([
        {"has_regular_transaction": True, "is_interest_free": False},
        {"has_regular_transaction": False, "is_interest_free": True},
        {"has_regular_transaction": False, "is_interest_free": False},
    ]), _crit(), asof=ASOF)
    assert list(df["category"]) == ["소매/거래", "소매/거래", "소매/비거래"]
    assert list(df["d368_category"]) == [
        "retail_transactional", "retail_transactional",
        "retail_non_transactional"]


def test_the_deposit_category_is_left_empty_when_both_split_inputs_are_missing():
    df, warns = K.classify_kr_nmd_category(_deposits([
        {"has_regular_transaction": None, "is_interest_free": None},
    ]), _crit(), asof=ASOF)
    assert df["category"].iloc[0] is None
    assert df["d368_category"].iloc[0] is None
    assert df["evidence_status"].iloc[0] == "미확인"
    assert "거래예금 여부를 판정하지 않고" in _reasons(warns)


def test_an_unknown_depositor_type_is_refused():
    with pytest.raises(ValueError, match="예치인 구분"):
        K.classify_kr_nmd_category(
            _deposits([{"depositor_type": "협동조합"}]), _crit(), asof=ASOF)


# -------------------------------------------------- 제9·10항 행동옵션 범위

def test_sme_loan_is_retail_only_at_or_below_the_ledger_threshold():
    """제9항은 10억원 **이하**다. 경계값 10억원은 소매다."""
    crit = _crit()
    row = crit[crit["rule_code"] == K.KR_RULE_LOAN_SME].iloc[0]
    assert float(row["threshold_amount"]) == LOAN_THRESHOLD
    assert row["comparison"] == "이하"
    assert row["measure"] == "총여신"

    df, _w = K.build_kr_retail_behavioural_scope(_behaviour([
        {"customer_type": "중소기업", "is_retail_managed": True,
         "exposure_amount": LOAN_THRESHOLD},
        {"customer_type": "중소기업", "is_retail_managed": True,
         "exposure_amount": LOAN_THRESHOLD + 1.0},
    ]), crit, asof=ASOF)
    assert list(df["is_retail"]) == [True, False]
    assert list(df["in_scope"]) == [True, False]
    assert list(df["treatment"]) == ["행동옵션", "자동금리옵션"]


def test_the_two_clauses_use_different_comparison_directions():
    """제8항은 '미만', 제9항은 '이하'다. 한쪽을 복사하면 경계가 어긋난다."""
    crit = _crit()
    by_code = dict(zip(crit["rule_code"], crit["comparison"]))
    assert by_code[K.KR_RULE_NMD_SME] == "미만"
    assert by_code[K.KR_RULE_TD_SME] == "미만"
    assert by_code[K.KR_RULE_LOAN_SME] == "이하"

    amounts = dict(zip(crit["rule_code"], crit["threshold_amount"]))
    assert amounts[K.KR_RULE_TD_SME] == NMD_THRESHOLD
    assert amounts[K.KR_RULE_LOAN_SME] == LOAN_THRESHOLD


def test_the_term_deposit_rule_uses_the_funding_total_threshold():
    """제10항은 제8항의 15억원 자금조달총액 기준을 그대로 쓴다."""
    df, _w = K.build_kr_retail_behavioural_scope(_behaviour([
        {"behaviour_class": "early_redemption", "customer_type": "중소기업",
         "is_retail_managed": True, "exposure_amount": NMD_THRESHOLD - 1.0},
        {"behaviour_class": "early_redemption", "customer_type": "중소기업",
         "is_retail_managed": True, "exposure_amount": NMD_THRESHOLD},
    ]), _crit(), asof=ASOF)
    assert list(df["in_scope"]) == [True, False]
    assert list(df["exposure_measure"]) == ["자금조달총액"] * 2


def test_prepayment_applies_only_to_fixed_rate_loans():
    df, _w = K.build_kr_retail_behavioural_scope(_behaviour([
        {"rate_type": "fixed"}, {"rate_type": "floating"},
    ]), _crit(), asof=ASOF)
    assert list(df["in_scope"]) == [True, False]
    assert list(df["treatment"]) == ["행동옵션", "적합포지션"]
    assert "고정금리대출에 한한다" in df["excluded_reason"].iloc[1]


def test_a_prepayment_fee_charged_to_the_customer_leaves_the_scope():
    df, _w = K.build_kr_retail_behavioural_scope(
        _behaviour([{"prepay_fee_charged": True}]), _crit(), asof=ASOF)
    assert bool(df["in_scope"].iloc[0]) is False
    assert df["treatment"].iloc[0] == "적합포지션"


def test_early_redemption_needs_a_legal_right_and_no_substantial_penalty():
    df, _w = K.build_kr_retail_behavioural_scope(_behaviour([
        {"behaviour_class": "early_redemption",
         "has_legal_termination_right": True, "substantial_penalty": False},
        {"behaviour_class": "early_redemption",
         "has_legal_termination_right": False, "substantial_penalty": False},
        {"behaviour_class": "early_redemption",
         "has_legal_termination_right": True, "substantial_penalty": True},
    ]), _crit(), asof=ASOF)
    assert list(df["in_scope"]) == [True, False, False]
    assert list(df["treatment"]) == ["행동옵션", "적합포지션", "적합포지션"]


def test_wholesale_behavioural_options_become_automatic_options():
    """제7항 나(2) 단서. 도매고객 행동옵션은 사라지지 않고 제11항으로 간다."""
    df, _w = K.build_kr_retail_behavioural_scope(_behaviour([
        {"customer_type": "법인"},
        {"customer_type": "법인", "behaviour_class": "early_redemption"},
    ]), _crit(), asof=ASOF)
    assert list(df["in_scope"]) == [False, False]
    assert set(df["treatment"]) == {"자동금리옵션"}
    assert all("제7항 나(2) 단서" in r for r in df["excluded_reason"])


def test_a_missing_behavioural_input_leaves_the_verdict_open():
    df, warns = K.build_kr_retail_behavioural_scope(
        _behaviour([{"prepay_fee_charged": None}]), _crit(), asof=ASOF)
    assert df["in_scope"].iloc[0] is None
    assert df["evidence_status"].iloc[0] == "미확인"
    assert "고객부과 여부가 비어 있다" in _reasons(warns)


# -------------------------------------------------- 제11항 자동금리옵션

def test_volatility_expansion_comes_from_the_param_ledger():
    """확대율이 원장 모수다. 원장을 바꾸면 재평가 변동성이 따라 움직인다."""
    param = K.build_kr_auto_option_param()
    hit = param[param["param_code"] == K.KR_VOL_EXPANSION_CODE].iloc[0]
    assert float(hit["value"]) == VOL_EXPANSION

    a, _w1 = K.build_kr_auto_option(_options(), _shifts(), param, asof=ASOF)
    b, _w2 = K.build_kr_auto_option(
        _options(), _shifts(), _opt_param(K.KR_VOL_EXPANSION_CODE, 0.50),
        asof=ASOF)
    vol0 = float(a["implied_vol_base"].iloc[0])
    assert float(a["implied_vol_shocked"].iloc[0]) == pytest.approx(
        vol0 * (1.0 + VOL_EXPANSION))
    assert float(b["implied_vol_shocked"].iloc[0]) == pytest.approx(vol0 * 1.50)
    assert float(a["value_shocked"].iloc[0]) != float(b["value_shocked"].iloc[0])


def test_a_missing_volatility_expansion_skips_the_revaluation():
    det, warns = K.build_kr_auto_option(
        _options(), _shifts(), _opt_param(K.KR_VOL_EXPANSION_CODE, None),
        asof=ASOF)
    assert det["value_shocked"].isna().all()
    assert set(det["evidence_status"]) == {"미확인"}
    assert "내재변동성 확대율이 비어 있다" in _reasons(warns)
    risk = K.build_kr_auto_option_risk(det, asof=ASOF)
    assert not risk["is_complete"].any()


def test_a_missing_implied_vol_skips_that_option_and_marks_it_incomplete():
    det, warns = K.build_kr_auto_option(
        _options([{"implied_vol_base": 0.01}, {"implied_vol_base": None}]),
        _shifts(), _opt_param(), asof=ASOF)
    assert int(det["skip_reason"].notna().sum()) == len(IRRBB_SCENARIOS)
    assert "내재변동성이 비어 있다" in _reasons(warns)
    risk = K.build_kr_auto_option_risk(det, asof=ASOF)
    assert list(risk["n_skipped"]) == [1] * len(IRRBB_SCENARIOS)
    assert not risk["is_complete"].any()


def test_auto_option_risk_subtracts_bought_from_sold():
    """제11항. 매도 가치변동 합에서 매수 가치변동 합을 차감한다."""
    det, _w = K.build_kr_auto_option(_options([
        {"position": "매도", "option_type": "금리캡"},
        {"position": "매수", "option_type": "금리플로어"},
    ]), _shifts(), _opt_param(), asof=ASOF)
    risk = K.build_kr_auto_option_risk(det, asof=ASOF)
    for r in risk.itertuples():
        assert r.auto_option_risk == pytest.approx(
            r.sold_delta_sum - r.bought_delta_sum)
    assert risk["is_complete"].all()


def test_the_position_weights_come_from_the_param_ledger():
    """매도 +1 · 매수 −1이 원장 행이다. 매수 가중을 0으로 두면 차감이 사라진다."""
    opts = _options([{"position": "매도", "option_type": "금리캡"},
                     {"position": "매수", "option_type": "금리플로어"}])
    det, _w = K.build_kr_auto_option(
        opts, _shifts(), _opt_param(K.KR_OPTION_WEIGHT_CODE["매수"], 0.0),
        asof=ASOF)
    risk = K.build_kr_auto_option_risk(det, asof=ASOF)
    for r in risk.itertuples():
        assert r.auto_option_risk == pytest.approx(r.sold_delta_sum)


def test_the_post_shock_forward_rate_is_floored_by_the_curve_ledger():
    """제12항 다. 충격후 금리 하한은 0이며 하한값은 곡선 원장이 들고 온다."""
    det, _w = K.build_kr_auto_option(
        _options([{"forward_rate_base": 0.005}]),
        _shifts(rate_shift=-0.0225, floor_rate=0.0), _opt_param(), asof=ASOF)
    assert set(det["forward_rate_shocked"]) == {0.0}
    assert set(det["floor_rate"]) == {0.0}


def test_a_missing_scenario_curve_row_is_skipped_not_guessed():
    det, warns = K.build_kr_auto_option(
        _options([{"expiry_years": 3.0}]), _shifts(expiry_years=2.0),
        _opt_param(), asof=ASOF)
    assert det["value_shocked"].isna().all()
    assert "시나리오 곡선에" in _reasons(warns)


# -------------------------------------------------- 제15~20항 관리체계

def test_the_board_report_requirement_is_twice_a_year():
    """제15항 연 2회 이상. 1회는 미이행, 2회는 이행이다."""
    for count, expect in ((1, False), (2, True), (3, True)):
        gov, _w = K.build_kr_irrbb_governance(
            _gov_records([{"requirement_code": "GOV-15-02",
                           "count_in_period": count}]), asof=ASOF)
        row = gov[gov["requirement_code"] == "GOV-15-02"].iloc[0]
        assert bool(row["is_fulfilled"]) is expect, count
        assert int(row["min_count_per_year"]) == 2


def test_the_measurement_requirement_is_quarterly():
    """제16항 나 분기 1회 이상. 연 4회가 경계다."""
    for count, expect in ((3, False), (4, True)):
        gov, _w = K.build_kr_irrbb_governance(
            _gov_records([{"requirement_code": "GOV-16-01",
                           "count_in_period": count}]), asof=ASOF)
        row = gov[gov["requirement_code"] == "GOV-16-01"].iloc[0]
        assert bool(row["is_fulfilled"]) is expect, count
        assert int(row["min_count_per_year"]) == 4


def test_a_governance_requirement_without_records_is_unknown_not_failed():
    gov, warns = K.build_kr_irrbb_governance(asof=ASOF)
    assert len(gov) == len(K.KR_GOVERNANCE_REQUIREMENTS)
    assert gov["is_fulfilled"].isna().all()
    assert set(gov["evidence_status"]) == {"미확인"}
    assert len(warns) == len(K.KR_GOVERNANCE_REQUIREMENTS)


def test_a_non_annual_period_defers_the_count_verdict():
    gov, warns = K.build_kr_irrbb_governance(
        _gov_records([{"requirement_code": "GOV-15-02", "count_in_period": 2,
                       "is_annual_period": False}]), asof=ASOF)
    row = gov[gov["requirement_code"] == "GOV-15-02"].iloc[0]
    assert row["is_fulfilled"] is None
    assert "연간이 아니" in _reasons(warns)


def test_the_governance_ledger_carries_the_independent_validation_clause():
    """제16항 라가 이 저장소 3선 상시 독립검증의 규정 근거다."""
    gov, _w = K.build_kr_irrbb_governance(asof=ASOF)
    row = gov[gov["requirement_code"] == "GOV-16-02"].iloc[0]
    assert row["clause"] == "제16항 라"
    assert "적합성검증" in row["requirement"]
    assert "독립적이면서 전문성" in row["requirement"]
    # 제17항 한도 초과 시 원인분석·대응책도 추적 대상이다.
    limit = gov[gov["requirement_code"] == "GOV-17-02"].iloc[0]
    assert "원인분석" in limit["requirement"]


def test_an_unknown_governance_code_is_refused():
    with pytest.raises(ValueError, match="미지의 요구사항 코드"):
        K.build_kr_irrbb_governance(
            _gov_records([{"requirement_code": "GOV-99-99"}]), asof=ASOF)


# -------------------------------------------------- 국내 고유 요건 결정론

def test_the_national_engines_carry_no_regulatory_numbers():
    """15억·10억·25%가 함수 본문에 있으면 원장을 고쳐도 판정이 안 움직인다.

    남는 숫자 리터럴은 어휘 튜플의 색인(0~3)과 정규분포 정의(0.5·1·2)뿐이며
    규제가 정하는 값이 아니다. 그래서 금지 목록으로 좁혀 본다.
    """
    banned = {NMD_THRESHOLD, LOAN_THRESHOLD, VOL_EXPANSION, 0.15}
    for fn in (K.classify_kr_nmd_category, K.build_kr_retail_behavioural_scope,
               K.build_kr_auto_option, K.build_kr_auto_option_risk,
               K.build_kr_irrbb_governance, K._meets_threshold,
               K.bachelier_value, K._scope_row):
        found = set(_numeric_constants(fn))
        assert found & banned == set(), (fn.__name__, found & banned)

    # 연 2회·분기 1회는 요구사항 표에서 오고 판정 함수에는 어떤 숫자도 없다.
    assert _numeric_constants(K.build_kr_irrbb_governance) == []
    counts = {code: n for code, _c, _r, _b, _f, n in K.KR_GOVERNANCE_REQUIREMENTS}
    assert counts["GOV-15-02"] == 2 and counts["GOV-16-01"] == 4


def test_the_national_ledgers_are_byte_identical_for_the_same_asof():
    def _run():
        crit = _crit()
        nmd, _w1 = K.classify_kr_nmd_category(_deposits([
            {}, {"depositor_type": "중소기업", "is_retail_managed": True,
                 "funding_total_amount": 1.0e9}]), crit, asof=ASOF)
        scope, _w2 = K.build_kr_retail_behavioural_scope(_behaviour([
            {}, {"customer_type": "법인"},
            {"behaviour_class": "early_redemption"}]), crit, asof=ASOF)
        det, _w3 = K.build_kr_auto_option(
            _options([{"position": "매도"}, {"position": "매수",
                                            "option_type": "금리플로어"}]),
            _shifts(), _opt_param(), asof=ASOF)
        risk = K.build_kr_auto_option_risk(det, asof=ASOF)
        gov, _w4 = K.build_kr_irrbb_governance(
            _gov_records([{"requirement_code": "GOV-16-01",
                           "count_in_period": 4}]), asof=ASOF)
        return [d.to_csv(index=False) for d in (crit, nmd, scope, det, risk, gov)]

    assert _run() == _run()


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
