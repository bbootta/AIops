"""유동성 재구현 — 사다리·LCR·NSFR·생존기간의 불변식 고정.

이 파일의 규칙: **통과만으로는 통제가 아니다.** 각 검사는 결함을 되돌렸을 때
실제로 실패해야 한다. 그래서 여기 있는 검사 다섯은 전부 실제로 있었던 결함을
겨냥한다.

  · `test_ladder_moves_with_the_portfolio_maturity_mix`
      balance_sheet.py의 상수 가중 벡터(`asset_w = [0.06, 0.08, …]`). 포트폴리오
      만기를 통째로 밀어도 사다리가 미동하지 않던 자리다.
  · `test_contract_and_behavioural_ladders_differ`
      비만기예금이 계약기준에서 전액 최단 버킷, 행태기준에서 4~5년에 퍼지는
      차이. 서식 각주가 감독당국에 "행태만기로 슬로팅되어 있다"고 적고 있다.
  · `test_lcr_caps_bind_at_the_boundary`
      2B 15%·L2 40%·유입 75% 상한이 산식 한가운데 있던 자리.
  · `test_survival_days_respond_monotonically_to_runoff`
      유출률이 원장에서 오지 않으면 이 반응 자체가 성립하지 않는다.
  · `test_ladder_net_gap_ties_to_the_cashflow_ledger`
      사다리와 현금흐름 원장의 대사. 집계가 새면 여기서 잡힌다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.alm import params as P
from risk_lib.alm.balance_sheet import generate_balance_sheet
from risk_lib.alm.cashflow import build_cashflows
from risk_lib.alm.contracts import build_contract_ledger
from risk_lib.alm.lcr import (
    HQLACaps, LCR_FACTOR, LCR_FLOW, apply_hqla_caps, build_lcr_factor,
    build_lcr_flow, compute_lcr, lcr_balances_from_balance_sheet,
    lcr_balances_from_ledgers, resolve_caps,
)
from risk_lib.alm.liquidity import (
    LIQUIDITY_STRESS_PARAM, MATURITY_LADDER, STRESS_SCENARIOS, SURVIVAL_PATH,
    build_liquidity_stress_param, build_maturity_ladder, build_survival_path,
)
from risk_lib.alm.nsfr import (
    NSFR_FACTOR, NSFR_ITEM, build_nsfr_factor, build_nsfr_item, compute_nsfr,
    maturity_band_of, nsfr_balances_from_balance_sheet,
)
from risk_lib.data_gen import generate_portfolio
from risk_lib.datamodel.spec import validate

ASOF = "2026-08-08"
SEED = 42
BASE_RATE = 0.03
HORIZON = 30


@pytest.fixture(scope="module")
def portfolio():
    return generate_portfolio(seed=SEED)


@pytest.fixture(scope="module")
def bs(portfolio):
    return generate_balance_sheet(portfolio, capital_total=1.2e12, seed=SEED)


def _cashflows(portfolio, bs):
    led = P.build_param_ledgers(ASOF)
    con = build_contract_ledger(portfolio, asof=ASOF, funding=bs.funding,
                                hqla=bs.hqla, equity=bs.equity,
                                base_rate=BASE_RATE, seed=SEED)
    res = build_cashflows(
        con, asof=ASOF, product_terms=led["alm_product_terms"],
        buckets=led["alm_time_bucket"],
        behaviour_param=led["alm_behaviour_param"],
        scenario_mult=led["alm_behaviour_scenario_mult"],
        nmd_param=led["alm_nmd_param"],
        scurve_param=led["alm_prepay_scurve_param"])
    return con, led, res


@pytest.fixture(scope="module")
def engine(portfolio, bs):
    return _cashflows(portfolio, bs)


# ------------------------------------------------- 1. 상수 벡터 회귀

def test_ladder_moves_with_the_portfolio_maturity_mix(portfolio):
    """포트폴리오 만기 분포를 바꾸면 사다리가 반드시 움직인다.

    상수 가중 벡터로 만들던 사다리는 이 검사에서 **두 사다리가 완전히 같아져**
    실패한다. 잔액(EAD)은 건드리지 않고 만기만 민다 — 총액이 같은데 사다리가
    같으면 만기가 산출에 들어가지 않은 것이다.
    """
    short = portfolio.copy()
    short["maturity"] = np.clip(short["maturity"] * 0.25, 0.05, None)
    a = generate_balance_sheet(portfolio, capital_total=1.2e12, seed=SEED)
    b = generate_balance_sheet(short, capital_total=1.2e12, seed=SEED)

    assert a.loans == pytest.approx(b.loans)          # 잔액은 같다
    assert not np.allclose(a.repricing["assets"].to_numpy(),
                           b.repricing["assets"].to_numpy())
    # 만기를 당겼으면 자산의 가중평균 버킷이 앞으로 와야 한다.
    def wavg(rep):
        return float((rep["t_mid"] * rep["assets"]).sum()
                     / rep["assets"].sum())
    assert wavg(b.repricing) < wavg(a.repricing)


def test_ladder_liabilities_use_behavioural_nmd_slotting(bs):
    """비만기예금이 최단 버킷에 고이지 않고 장기 버킷으로 퍼져야 한다.

    서식 각주(`forms_fss_liquidity._LADDER_NOTE`)가 감독당국 제출문서에 "비만기성
    예금은 행태만기로 슬로팅되어 있다"고 적는다. 계약기준이면 전액 O/N이므로
    1년 초과 버킷의 부채가 0이 된다.
    """
    rep = bs.repricing
    long_liab = float(rep.loc[rep["t_mid"] > 1.0, "liabilities"].sum())
    assert long_liab > 0.0
    # 코어 상한(소매 결제성 90% · 평균만기 5년)이 있으므로 전량이 장기로 가지도
    # 않는다 — 논코어는 최단 버킷에 남는다.
    assert float(rep.loc[rep["t_mid"] < 0.1, "liabilities"].sum()) > 0.0


def test_balance_sheet_ladder_is_deterministic(portfolio):
    a = generate_balance_sheet(portfolio, 1e12, seed=SEED)
    b = generate_balance_sheet(portfolio, 1e12, seed=SEED)
    pd.testing.assert_frame_equal(a.repricing, b.repricing)


# ------------------------------------------------- 2. 계약 vs 행동조정

def test_contract_and_behavioural_ladders_differ(engine):
    """감독당국이 비교하는 바로 그 차이가 원장에서 조인되어야 한다."""
    _, _, res = engine
    lad = build_maturity_ladder(res.bucket)
    base = lad[(lad["scenario"] == "base") & (lad["ccy"] == "KRW")]
    con = base[base["basis"] == "계약"].set_index("bucket")
    beh = base[base["basis"] == "행동조정"].set_index("bucket")
    assert not con.empty and not beh.empty

    # 계약기준은 NMD 전액이 단기 유출이고, 행태기준은 그 일부가 장기로
    # 옮겨간다. 버킷 라벨을 적지 않고 원장의 경계로 1년·3년을 가른다 —
    # 사다리가 9구간에서 [별표 9-1] <표2> 19구간으로 바뀌면서 라벨을 적어 둔
    # 검사가 전건 어긋났고, NMD 계약 유출도 O/N이 아니라 그 다음 구간에 앉는다.
    bk = P.build_time_buckets()
    short_labels = set(bk.loc[bk["upper_years"] <= 1.0, "label"])
    long_labels = set(bk.loc[bk["lower_years"] >= 3.0, "label"])
    short_buckets = con.index[con.index.isin(short_labels)]
    long_buckets = con.index[con.index.isin(long_labels)]
    assert (beh.loc[short_buckets, "outflow"].sum()
            < con.loc[short_buckets, "outflow"].sum())
    assert (beh.loc[long_buckets, "outflow"].sum()
            > con.loc[long_buckets, "outflow"].sum())
    # 총 유출액 자체는 명목 보존이므로 크게 달라지지 않는다 — 바뀐 것은 시점이다.
    assert beh["outflow"].sum() == pytest.approx(con["outflow"].sum(), rel=0.05)


def test_maturity_ladder_validates_and_keys_are_unique(engine):
    _, _, res = engine
    lad = build_maturity_ladder(res.bucket, counterbalancing_capacity=1e12)
    assert validate(lad, MATURITY_LADDER) == []
    assert not lad.duplicated(list(MATURITY_LADDER.primary_key)).any()
    # 반대매매가능자산은 최단 버킷에만 놓인다 — 버킷마다 반복하면 가로합에서
    # 같은 자산이 여러 번 세어진다.
    key = ["asof", "scenario", "basis", "ccy"]
    per = lad.groupby(key)["counterbalancing_capacity"].sum()
    assert np.allclose(per.to_numpy(), 1e12)


# ------------------------------------------------- 5. 원장 대사

def test_ladder_net_gap_ties_to_the_cashflow_ledger(engine):
    """사다리 순갭 합 = 현금흐름 원장의 자산 − 부채. 집계가 새면 여기서 잡힌다."""
    _, _, res = engine
    lad = build_maturity_ladder(res.bucket)
    cf = res.bucket
    for (sc, basis), g in lad.groupby(["scenario", "basis"]):
        src = cf[(cf["scenario"] == sc) & (cf["basis"] == basis)]
        want = (float(src.loc[src["side"] == "asset", "total_cf"].sum())
                - float(src.loc[src["side"] != "asset", "total_cf"].sum()))
        assert float(g["net_gap"].sum()) == pytest.approx(want, rel=1e-12)
        # 누적갭의 마지막 값 = 순갭 합 (버킷 순서대로 쌓였는가)
        last = g.sort_values("seq")["cumulative_gap"].iloc[-1]
        assert float(last) == pytest.approx(float(g["net_gap"].sum()),
                                            rel=1e-12)


def test_cumulative_gap_does_not_leak_across_scenarios(engine):
    """시나리오·산출기준이 다르면 다른 사다리다 — 누적을 섞으면 안 된다."""
    _, _, res = engine
    lad = build_maturity_ladder(res.bucket)
    key = ["asof", "scenario", "basis", "ccy"]
    first = lad.sort_values("seq").groupby(key).first()
    assert np.allclose(first["cumulative_gap"], first["net_gap"])


# ------------------------------------------------- 3. LCR 상한

def test_lcr_factor_ledger_keeps_the_level_2b_split(portfolio):
    """단일 헤어컷 상수 0.50이 지우고 있던 RMBS 25% 버킷이 원장에 있어야 한다."""
    f = build_lcr_factor()
    assert validate(f, LCR_FACTOR) == []
    l2b = f[(f["section"] == "HQLA")
            & f["category"].str.startswith("level_2b")]
    assert set(np.round(l2b["factor"].dropna(), 2)) == {0.75, 0.50}
    rmbs = l2b[l2b["category"] == "level_2b_rmbs"].iloc[0]
    assert rmbs["factor"] == pytest.approx(0.75)
    # 보유 채권의 세부 구분 원장이 없으므로 25% 버킷은 등재되되 미산출이다.
    assert rmbs["source"] == "미산출"
    assert f[f["category"] == "level_2b_unclassified"]["source"].iloc[0] == "산출"


def test_lcr_factor_ledger_registers_what_is_not_computed():
    """분모에 아예 없던 항목을 등재하되 비워 둔다 — 부재가 보여야 한다."""
    f = build_lcr_factor()
    out = f[f["section"] == "유출"].set_index("category")
    for cat in ("derivatives_net_payable", "rating_downgrade_trigger",
                "maturing_debt_securities", "secured_funding_other"):
        assert out.loc[cat, "source"] == "미산출"
    # 국내 관할재량 항목은 계수 자체가 비어 있다.
    assert pd.isna(out.loc["trade_finance", "factor"])
    assert out.loc["trade_finance", "evidence_status"] == "미확인"
    # 1차자료를 못 읽었으므로 '원문확인'이 하나도 없어야 한다.
    assert "원문확인" not in set(f["evidence_status"])


def test_caps_come_from_the_ledger_not_the_formula():
    """'한도' 행을 비우면 산출이 멈춘다 — 코드 기본값으로 넘어가면 안 된다."""
    f = build_lcr_factor()
    caps = resolve_caps(f)
    assert (caps.l2b, caps.l2, caps.inflow) == (0.15, 0.40, 0.75)
    broken = f.copy()
    broken.loc[broken["category"] == "cap_l2b", "factor"] = np.nan
    with pytest.raises(ValueError, match="한도"):
        resolve_caps(broken)


@pytest.mark.parametrize("caps", [
    HQLACaps(0.15, 0.40, 0.75),
    HQLACaps(0.10, 0.30, 0.75),      # 상한을 바꾸면 결과가 따라 움직여야 한다
])
def test_lcr_caps_bind_at_the_boundary(caps):
    """2B 15% · L2 40% 상한이 경계에서 실제로 무는지.

    두 상한이 동시에 물면 HQLA는 L1의 1/(1−C)배로 닫힌다 (C = L2 상한).
    """
    # (a) 2B 상한만 무는 배치 — 2B가 정확히 HQLA의 15%(또는 10%)에 앉는다.
    total, l2a_inc, l2b_inc = apply_hqla_caps(3.0e12, 0.05e12, 1.5e12, caps)
    assert l2b_inc == pytest.approx(caps.l2b * total, rel=1e-9)
    assert l2a_inc + l2b_inc <= caps.l2 * total + 1.0

    # (b) 두 상한이 함께 무는 배치 — 닫힌 형태와 일치해야 한다.
    l1 = 0.2e12
    total2, l2a2, l2b2 = apply_hqla_caps(l1, 0.1e12, 2.0e12, caps)
    assert total2 == pytest.approx(l1 / (1.0 - caps.l2), rel=1e-9)
    assert l2a2 + l2b2 == pytest.approx(caps.l2 * total2, rel=1e-9)

    # (c) 상한이 물지 않는 배치는 그대로 통과한다.
    total3, l2a3, l2b3 = apply_hqla_caps(10.0e12, 0.1e12, 0.05e12, caps)
    assert total3 == pytest.approx(10.15e12, rel=1e-12)
    assert (l2a3, l2b3) == pytest.approx((0.1e12, 0.05e12))


def test_inflow_cap_binds_at_seventy_five_percent(bs):
    """유입이 유출의 75%를 넘으면 잘려야 한다 — 경계에서 확인한다."""
    f = build_lcr_factor()
    bal = lcr_balances_from_balance_sheet(bs, seed_inflow_frac=0.04)
    caps = resolve_caps(f)

    # 유입을 유출보다 크게 부풀려 상한이 반드시 물게 만든다.
    big = bal.copy()
    big.loc[big["section"] == "유입", "balance"] *= 1e3
    r = build_lcr_flow(big, f, asof=ASOF, scenario="base")
    assert r.inflow_capped == pytest.approx(caps.inflow * r.gross_outflow)
    assert r.net_outflow == pytest.approx((1 - caps.inflow) * r.gross_outflow)

    # 유입이 작으면 상한이 물지 않고 전액 인정된다.
    small = bal.copy()
    small.loc[small["section"] == "유입", "balance"] *= 1e-3
    r2 = build_lcr_flow(small, f, asof=ASOF, scenario="base")
    assert r2.inflow_capped == pytest.approx(r2.inflow_total)


def test_lcr_flow_validates_and_skips_null_factors(bs):
    f = build_lcr_factor()
    bal = lcr_balances_from_balance_sheet(bs, seed_inflow_frac=0.04)
    bal = pd.concat([bal, pd.DataFrame(
        [{"section": "유출", "category": "trade_finance",
          "balance": 5e11}])], ignore_index=True)
    r = build_lcr_flow(bal, f, asof=ASOF, scenario="base")
    assert validate(r.flow, LCR_FLOW) == []
    assert "유출/trade_finance" in r.skipped
    row = r.flow[r.flow["category"] == "trade_finance"].iloc[0]
    assert pd.isna(row["weighted"]) and row["factor_source"] == "계수 미확인·미가중"
    # 계수를 모르는 유출을 0으로 가중하면 LCR이 좋아진다 — 그렇게 하지 않는다.
    assert float(r.flow.loc[r.flow["section"] == "유출", "weighted"].sum()) \
        == pytest.approx(r.gross_outflow)


def test_compute_lcr_keeps_its_public_shape(bs):
    """서식·스트레스·보고서가 읽는 필드가 그대로 있어야 한다."""
    r = compute_lcr(bs)
    assert list(r.hqla_detail["component"]) == ["Level 1", "Level 2A",
                                                "Level 2B"]
    assert set(r.outflows.columns) == {"category", "amount", "runoff",
                                       "outflow"}
    assert set(r.inflows.columns) == {"category", "amount", "rate", "inflow"}
    assert r.lcr == pytest.approx(r.hqla_total / r.net_outflow, rel=1e-12)
    assert r.net_outflow == pytest.approx(r.gross_outflow - r.inflow_capped)
    assert float(r.outflows["outflow"].sum()) == pytest.approx(r.gross_outflow)


def test_ledger_path_applies_the_thirty_day_test(portfolio, bs, engine):
    """계약원장 경로는 30일 안에 만기가 오는 조달만 유출로 센다.

    조달 dict에는 만기가 없어 잔존 5년 조달까지 유출로 세던 자리다.
    """
    con, led, _ = engine
    from risk_lib.alm.contracts import FUNDING_PRODUCT_MAP
    funding_of = {code: cat for cat, (code, _n)
                  in FUNDING_PRODUCT_MAP.items()}
    # 조달 카테고리 이름이 곧 LCR 유출 항목은 아니다 — 계수 원장의 어휘로 옮긴다.
    lcr_cat = {"DEP_NMD_RT": "retail_stable",
               "DEP_NMD_RNT": "retail_less_stable",
               "DEP_NMD_WNF": "corporate_operational",
               "DEP_TERM_CORP": "corporate_non_operational",
               "DEP_NMD_FI": "wholesale_fi_unsecured",
               "FUND_WS_ST": "wholesale_fi_unsecured",
               "FUND_WS_LT": "wholesale_fi_unsecured"}
    assert set(lcr_cat) >= set(funding_of)
    bal = lcr_balances_from_ledgers(
        con, led["alm_product_terms"], asof=ASOF, horizon_days=HORIZON,
        funding_category_of=lcr_cat,
        hqla_category_of={"SEC_HQLA_L1": "level_1",
                          "SEC_HQLA_L2A": "level_2a",
                          "SEC_HQLA_L2B": "level_2b_unclassified"})
    out = bal.set_index("category")["balance"]
    # 만기 1년 초과 도매조달은 30일 유출에 들어오지 않는다.
    ws = float(con.loc[con["product_code"] == "FUND_WS_LT", "notional"].sum())
    assert ws > 0
    assert float(out.get("wholesale_fi_unsecured", 0.0)) < ws
    # 비만기예금은 만기가 없으므로 전액이 유출 대상이다.
    nmd = float(con.loc[con["product_code"] == "DEP_NMD_RT", "notional"].sum())
    assert float(out["retail_stable"]) == pytest.approx(nmd)


# ------------------------------------------------- 4. 생존기간

def _stress_ledger(**overrides):
    f = build_lcr_factor()
    sp = build_liquidity_stress_param(f, horizon_days=HORIZON)
    for (sc, cat), v in overrides.items():
        m = (sp["stress_scenario"] == sc) & (sp["category"] == cat)
        sp.loc[m, "cum_runoff_rate"] = v
    return sp


def test_stress_param_ledger_validates_and_leaves_market_wide_empty():
    sp = _stress_ledger()
    assert validate(sp, LIQUIDITY_STRESS_PARAM) == []
    assert set(sp["stress_scenario"]) == set(STRESS_SCENARIOS)
    # 정상 = 정의상 0, 기관고유 = LCR 준용, 시장전반 = 분해 계수 미공표 → NULL.
    assert (sp.loc[sp["stress_scenario"] == "정상",
                   "cum_runoff_rate"] == 0.0).all()
    assert sp.loc[sp["stress_scenario"] == "시장전반",
                  "cum_runoff_rate"].isna().all()
    idio = sp[sp["stress_scenario"] == "기관고유"].set_index("category")
    assert idio.loc["retail_stable", "cum_runoff_rate"] == pytest.approx(0.05)


def _survival(runoff: float, cbc: float = 1e11) -> int | None:
    """유출률 하나로 채운 원장으로 생존일수를 뽑는다."""
    sp = build_liquidity_stress_param(build_lcr_factor(),
                                      horizon_days=HORIZON)
    sp = sp[sp["stress_scenario"] == "기관고유"].copy()
    sp["cum_runoff_rate"] = runoff
    bal = pd.DataFrame([{"category": "retail_stable", "balance": 1e13}])
    r = build_survival_path(bal, sp, asof=ASOF,
                            counterbalancing_capacity=cbc)
    assert validate(r.path, SURVIVAL_PATH) == []
    return r.survival_days["기관고유"]


def test_survival_days_respond_monotonically_to_runoff():
    """유출률을 올리면 생존기간이 짧아진다 — 원장이 산출에 실제로 들어가는가."""
    days = [_survival(x) for x in (0.02, 0.05, 0.10, 0.30)]
    assert all(d is not None for d in days)
    assert days == sorted(days, reverse=True)
    assert days[0] > days[-1]
    # 유출이 반대매매가능자산을 소진하지 못하면 시계 안에서 생존한다.
    assert _survival(0.001) is None


def test_survival_path_skips_scenarios_with_missing_runoff():
    """유출률이 비면 그 시나리오를 산출하지 않고 경고를 남긴다.

    빠진 항목을 0으로 두면 비어 있음이 "오래 버틴다"로 뒤집힌다.
    """
    sp = _stress_ledger()
    bal = pd.DataFrame([{"category": "retail_stable", "balance": 1e13},
                        {"category": "retail_less_stable", "balance": 5e12}])
    r = build_survival_path(bal, sp, asof=ASOF,
                            counterbalancing_capacity=5e11)
    assert set(r.path["scenario"]) == {"정상", "기관고유"}
    assert "시장전반" not in r.survival_days
    assert any(w.scope == "시장전반" for w in r.warnings)
    # 무스트레스 기준선은 유출이 0이므로 시계 안에서 반드시 생존한다.
    assert r.survival_days["정상"] is None
    assert (r.path.loc[r.path["scenario"] == "정상",
                       "net_outflow_cum"] == 0.0).all()


def test_survival_path_is_monotone_in_time():
    """누적 순유출은 줄어들 수 없고 잔여 여력은 늘어날 수 없다."""
    sp = _stress_ledger()
    sp = sp[sp["stress_scenario"] == "기관고유"]
    bal = pd.DataFrame([{"category": "retail_stable", "balance": 1e13}])
    r = build_survival_path(bal, sp, asof=ASOF,
                            counterbalancing_capacity=2e11)
    p = r.path.sort_values("day")
    assert (p["net_outflow_cum"].diff().dropna() >= 0).all()
    assert (p["cbc_remaining"].diff().dropna() <= 0).all()
    first_false = int(p.loc[~p["survived"], "day"].iloc[0])
    assert r.survival_days["기관고유"] == first_false


# ------------------------------------------------- NSFR 만기 분할

def test_nsfr_factor_ledger_carries_the_maturity_bands():
    f = build_nsfr_factor()
    assert validate(f, NSFR_FACTOR) == []
    rsf = f[f["section"] == "RSF"].set_index("category")
    assert rsf.loc["loans_fi_lt6m", "band_upper_years"] == pytest.approx(0.5)
    assert rsf.loc["loans_fi_6to12m", "band_lower_years"] == pytest.approx(0.5)
    assert rsf.loc["loans_fi_6to12m", "factor"] == pytest.approx(0.50)
    assert rsf.loc["mortgages_ge1y", "band_lower_years"] == pytest.approx(1.0)
    assert pd.isna(rsf.loc["mortgages_ge1y", "band_upper_years"])
    # 국내 채택 미확인 항목은 계수가 비어 있다.
    assert pd.isna(rsf.loc["derivative_liabilities_addon", "factor"])


def test_bank_loans_are_split_by_actual_maturity_not_a_fixed_ratio(portfolio):
    """`fi_loans × 0.4 / × 0.6` 회귀 — 잔존 5년 여신이 6개월 소요율을 받으면 안 된다."""
    long_bank = portfolio.copy()
    long_bank.loc[long_bank["asset_class"] == "bank", "maturity"] = 5.0
    bs = generate_balance_sheet(long_bank, capital_total=1.2e12, seed=SEED)
    assert bs.asset_split["loans_fi_lt6m"] == 0.0
    assert bs.asset_split["loans_fi_6to12m"] == 0.0

    short_bank = portfolio.copy()
    short_bank.loc[short_bank["asset_class"] == "bank", "maturity"] = 0.25
    bs2 = generate_balance_sheet(short_bank, capital_total=1.2e12, seed=SEED)
    bank_ead = float(portfolio.loc[
        (portfolio["asset_class"] == "bank") & (portfolio["dpd"] < 90),
        "ead"].sum())
    assert bs2.asset_split["loans_fi_lt6m"] == pytest.approx(bank_ead)
    # 고정 비율이었다면 두 경우가 같았다.
    assert bs.asset_split["loans_fi_lt6m"] != bs2.asset_split["loans_fi_lt6m"]


def test_asset_split_is_a_partition_of_total_assets(bs):
    """Σ 분해 = 총자산. 항등식 검사가 없어 우연히 맞고 있던 자리다."""
    assert sum(bs.asset_split.values()) == pytest.approx(bs.total_assets,
                                                         rel=1e-9)


def test_maturity_band_of_never_drops_an_exposure():
    f = build_nsfr_factor()
    rsf = f[f["section"] == "RSF"]
    t = np.array([0.0, 0.49, 0.5, 0.99, 1.0, 30.0])
    got = maturity_band_of(t, rsf, ("loans_fi_lt6m", "loans_fi_6to12m",
                                    "other_loans_ge1y"))
    assert list(got) == ["loans_fi_lt6m", "loans_fi_lt6m", "loans_fi_6to12m",
                         "loans_fi_6to12m", "other_loans_ge1y",
                         "other_loans_ge1y"]


def test_nsfr_item_validates_and_ties_to_the_totals(bs):
    f = build_nsfr_factor()
    res = build_nsfr_item(nsfr_balances_from_balance_sheet(bs), f, asof=ASOF)
    assert validate(res.item, NSFR_ITEM) == []
    it = res.item
    assert float(it.loc[it["section"] == "ASF", "weighted"].sum()) \
        == pytest.approx(res.asf_total)
    assert res.nsfr == pytest.approx(res.asf_total / res.rsf_total, rel=1e-12)


def test_compute_nsfr_keeps_its_public_shape(bs):
    n = compute_nsfr(bs)
    for tbl in (n.asf, n.rsf):
        assert list(tbl.columns) == ["category", "amount", "factor", "weighted"]
    assert n.nsfr == pytest.approx(n.asf_total / n.rsf_total, rel=1e-12)
    assert float(n.rsf["weighted"].sum()) == pytest.approx(n.rsf_total)


# ------------------------------------------------- 6. 버킷 경계 규약 회귀
#
# 두 사다리가 같은 익스포저를 다른 버킷에 놓던 자리다. `_slot`이 `side="right"`
# ([lower, upper))였고 입력에는 경계값이 실제로 들어왔다 — 재설정 주기 3·6개월은
# 0.25·0.5년, 조달 만기 구간 끝은 1.0·5.0년이다. 그래서 3개월 재설정 대출이
# `3-6m`에 앉았고, 같은 계약을 날짜 차이로 슬로팅하는 계약원장 경로
# (91/365.25 = 0.2491)는 `1-3m`에 놓았다.

def test_slotting_uses_the_supervisory_upper_inclusive_convention():
    """경계 규약 (하한, 상한]. 라벨을 적지 않고 원장의 경계로 확인한다.

    직전에는 자체 집계 9구간의 라벨을 문자열로 적어 두었고, 헤드라인 사다리가
    [별표 9-1] <표2> 19구간으로 옮기면서 전건 어긋났다. 검사가 확인해야 하는
    것은 라벨이 아니라 **경계 포함 방향**이므로 원장의 경계로 본다.
    """
    from risk_lib.alm.liquidity import _slot
    b = P.build_time_buckets().sort_values("seq").reset_index(drop=True)
    for t in (0.0, 0.25, 0.5, 1.0, 3.0, 5.0, 20.0, 25.0):
        i = int(_slot([t], b)[0])
        lo, hi = float(b["lower_years"][i]), float(b["upper_years"][i])
        if i == len(b) - 1:
            assert t > lo or t == 0.0    # 마지막은 개방구간
        elif i == 0:
            assert lo <= t <= hi         # 첫 버킷은 하한 0을 포함한다
        else:
            assert lo < t <= hi, f"{t}가 ({lo}, {hi}] 밖이다"
    # 상한에 정확히 걸리는 값은 그 구간에 들어간다 — 다음 구간이 아니다.
    edge = float(b["upper_years"][2])
    assert int(_slot([edge], b)[0]) == 2


def test_ladder_and_contract_paths_agree_on_a_boundary_repricing_date():
    """사다리 경로의 명목 재설정 시점과 계약원장 경로의 실제 날짜가 같은 버킷."""
    from datetime import date, timedelta
    from risk_lib.alm.liquidity import _slot
    b = P.build_time_buckets()
    nominal = 3 / 12.0
    asof_d = date.fromisoformat(ASOF)
    actual = ((asof_d + timedelta(days=91)) - asof_d).days / 365.25
    assert int(_slot([nominal], b)[0]) == int(_slot([actual], b)[0])


def test_floating_assets_reach_the_shortest_buckets(bs):
    """변동금리 자산을 재설정 주기 끝 한 점에 몰면 최단 버킷이 구조적으로 빈다.

    그 상태에서 외화유동성비율(제63조) 분자가 항상 0이 되어 감독 제출 서식에
    '비율 0% · 충족여부 0'으로 나갔다.
    """
    # 최단 버킷 라벨은 사다리가 바뀌면 함께 바뀐다. 원장 순서로 집는다.
    # 1년 이내 구간에 자산이 실제로 앉는지를 본다 — 한 점에 몰리면 최단 몇
    # 구간이 통째로 0이 되고 외화유동성비율 분자가 항상 0이 된다.
    rep = bs.repricing.reset_index(drop=True)
    assert float(rep.loc[0, "assets"]) > 0.0
    bk = P.build_time_buckets().sort_values("seq").reset_index(drop=True)
    within_1y = rep.loc[bk["upper_years"] <= 1.0, "assets"]
    assert (within_1y > 0.0).sum() >= 3, "1년 이내 구간 대부분이 비었다"


def test_repricing_ladder_conserves_the_portfolio_amount(portfolio, bs):
    """구간 분산은 금액을 재배치할 뿐 만들거나 없애지 않는다."""
    expected = float(portfolio["ead"].sum()) + float(sum(bs.hqla.values()))
    assert float(bs.repricing["assets"].sum()) == pytest.approx(expected,
                                                               rel=1e-12)


# ------------------------------------------------- 7. 잔존만기 축 분리
#
# `alm_maturity_ladder`는 시간축이 리프라이싱이다(입력인 alm_cashflow_bucket이
# 변동금리 명목 전액을 차기 재설정일에 놓는다). 잔존만기 축이 필요한 소비처는
# 계약원장에서 따로 접는다.

def test_contractual_balance_ladder_is_a_different_axis(portfolio, bs, engine):
    from risk_lib.alm.liquidity import build_contractual_balance_ladder
    contracts = build_contract_ledger(
        portfolio, asof=ASOF, funding=bs.funding, hqla=bs.hqla,
        equity=bs.equity, base_rate=BASE_RATE, seed=SEED)
    buckets = P.build_time_buckets()
    mat = build_contractual_balance_ladder(contracts, buckets, asof=ASOF)

    # 잔액 보존 — 자기자본만 빠진다.
    total = float(contracts.loc[~contracts["is_own_equity"].astype(bool),
                                "notional"].sum())
    assert float(mat["assets"].sum() + mat["liabilities"].sum()) \
        == pytest.approx(total, rel=1e-12)

    # 비만기예금은 계약기준에서 최단 버킷이다(최조기 지급가능일).
    nmd = float(contracts.loc[
        contracts["maturity_date"].isna()
        & ~contracts["is_own_equity"].astype(bool), "notional"].sum())
    assert float(mat.loc[mat["seq"] == 1, "liabilities"].iloc[0]) >= nmd

    # 리프라이싱 축과 같은 사다리가 아니다 — 같아지면 축 혼용이 재발한 것이다.
    rep = bs.repricing.set_index("bucket")["assets"]
    got = mat.set_index("bucket")["assets"]
    assert not np.allclose(rep.reindex(got.index).to_numpy(),
                           got.to_numpy())
