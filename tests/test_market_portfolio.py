"""트레이딩 포트폴리오 축과 포지션 원장 일원화 (risk_lib/market_portfolio.py).

이 축이 지키는 약속은 세 가지다.

1. 분해는 보존한다. 포트폴리오 포지션·자본을 위험군으로 합치면 규제 표
   (rwa_market_component)와 같고, VaR·ES 배분의 측정치별 합은 전사 값과 같다.
   가중치 합 1.0·전부 양수가 그 전제이고, 전제가 깨지면 import 가 죽는다.
2. 일원화는 계보에 보인다. rwa_market_component 의 상류가 mkt_position 이다.
   숫자만 맞고 선이 없으면 다음 사람이 다시 두 벌로 가른다.
3. headline 은 변하지 않는다. RWA 총액은 분해와 무관하게 위험군 총계에서
   나온다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import risk_lib.market_portfolio as mp
from risk_lib.capital.market_risk import compute_market_risk_rwa

ASOF = "2026-06-30"


def _class_positions() -> pd.DataFrame:
    return pd.DataFrame({
        "risk_class": ["fx", "equity", "interest_rate"],
        "net_position": [2.0e11, 1.0e11, 5.0e11],
    })


# ---------------------------------------------------------------- 적재 표

def test_weights_sum_to_one_per_class_and_are_positive():
    classes = {c for *_, w, _l in mp._PORTFOLIOS for c in w}
    assert classes, "배분이 비면 검사가 무의미하다"
    for cls in classes:
        s = sum(w.get(cls, 0.0) for *_, w, _l in mp._PORTFOLIOS)
        assert abs(s - 1.0) < 1e-9, f"{cls} 배분 합 {s}"
        assert all(w.get(cls, 0.0) >= 0.0 for *_, w, _l in mp._PORTFOLIOS)


def test_a_broken_loading_table_dies_at_import():
    """합이 1.0 이 아니면 조용히 새는 대신 시작 전에 죽는다."""
    good = mp._PORTFOLIOS
    try:
        mp._PORTFOLIOS = (("PF-A", "가", "전략", {"fx": 0.6}, 1.0),)
        with pytest.raises(ValueError, match="배분 합"):
            mp._check_loading_table()
        mp._PORTFOLIOS = (("PF-A", "가", "전략", {"fx": 1.3}, 0.5),
                          ("PF-B", "나", "전략", {"fx": -0.3}, 0.5))
        with pytest.raises(ValueError):
            mp._check_loading_table()
    finally:
        mp._PORTFOLIOS = good


def test_every_trade_kind_is_assigned_a_portfolio():
    """배정 없는 상품 유형은 포트폴리오 집계에서 조용히 빠진다."""
    from risk_lib.sensitivities import synthesise_trading_book
    ids = {p[0] for p in mp._PORTFOLIOS}
    assert set(mp.KIND_TO_PORTFOLIO.values()) <= ids
    # 트레이딩북 생성기가 만드는 유형 전부가 배정표에 있다
    import inspect
    src = inspect.getsource(synthesise_trading_book)
    for kind in ("option", "swap", "cds"):
        assert kind in src and kind in mp.KIND_TO_PORTFOLIO


# ---------------------------------------------------------------- 보존

def test_split_preserves_class_positions():
    cls = _class_positions()
    split = mp.split_positions(cls, asof=ASOF)
    agg = split.groupby("risk_class")["net_position"].sum()
    for _, r in cls.iterrows():
        assert agg[r["risk_class"]] == pytest.approx(r["net_position"],
                                                     rel=1e-12)


def test_portfolio_capital_reaggregates_to_the_engine_rwa():
    """포트폴리오 자본 합 = 엔진 시장 RWA. 산식이 두 벌이 아니라는 증명이다."""
    cls = _class_positions()
    engine = compute_market_risk_rwa(cls)
    split = mp.split_positions(cls, asof=ASOF)
    cap = mp.capital_frame(split)
    assert float(cap["rwa"].sum()) == pytest.approx(engine.rwa, rel=1e-9)
    by_cls = cap.groupby("risk_class")["capital"].sum()
    for cls_name, capital in engine.by_class.items():
        assert by_cls[cls_name] == pytest.approx(capital, rel=1e-9)


def test_var_es_allocation_sums_to_the_totals():
    cls = _class_positions()
    cap = mp.capital_frame(mp.split_positions(cls, asof=ASOF))
    var_es = pd.DataFrame([
        {"asof": ASOF, "measure": "VaR_99", "horizon_days": 1,
         "confidence": 0.99, "value": 2.3e9, "method": "historical"},
        {"asof": ASOF, "measure": "ES_97_5", "horizon_days": 10,
         "confidence": 0.975, "value": 5.0e9, "method": "historical"},
    ])
    out = mp.allocate_var_es(var_es, cap)
    for _, m in var_es.iterrows():
        got = float(out[out["measure"] == m["measure"]]["value"].sum())
        assert got == pytest.approx(float(m["value"]), rel=1e-12)
    # 배분 비중도 측정치마다 합 1
    for _, g in out.groupby("measure"):
        assert float(g["alloc_share"].sum()) == pytest.approx(1.0, rel=1e-12)


def test_allocation_basis_is_capital_share_not_equal_split():
    """배분 비중이 자본비중이다. 합만 보면 균등 배분도 통과하므로 기준
    자체를 고정한다. 스펙 note 가 '자본비중 비례배분' 이라고 말하고 있고,
    말과 산식이 갈라지면 화면의 설명이 거짓이 된다."""
    cls = _class_positions()
    cap = mp.capital_frame(mp.split_positions(cls, asof=ASOF))
    by_pf = cap.groupby("portfolio_id")["capital"].sum()
    want = by_pf / by_pf.sum()
    var_es = pd.DataFrame([
        {"asof": ASOF, "measure": "VaR_99", "horizon_days": 1,
         "confidence": 0.99, "value": 2.3e9, "method": "historical"}])
    out = mp.allocate_var_es(var_es, cap).set_index("portfolio_id")
    assert len(set(round(x, 12) for x in want)) > 1, (
        "포트폴리오 자본이 전부 같으면 균등 배분과 구별할 수 없다")
    for pid, share in want.items():
        assert float(out.loc[pid, "alloc_share"]) == pytest.approx(
            float(share), rel=1e-12)


def test_negative_positions_would_break_abs_conservation():
    """가중치가 전부 양수라 |Σ| = Σ|·| 가 성립함을 음수 사례로 확인한다.

    포트폴리오 간 부호가 갈리면 자본 합이 위험군 자본을 넘어선다. 지금
    설정에는 그 경우가 없고, 이 검사는 그 전제가 담보하는 성질 자체를
    문서화한다.
    """
    cls = pd.DataFrame({"risk_class": ["fx"], "net_position": [-3.0e11]})
    split = mp.split_positions(cls, asof=ASOF)
    # 원 포지션이 음수면 조각도 전부 음수다 — 부호가 섞이지 않는다
    assert (split["net_position"] < 0).all()
    cap = mp.capital_frame(split)
    engine = compute_market_risk_rwa(cls)
    assert float(cap["rwa"].sum()) == pytest.approx(engine.rwa, rel=1e-9)


# ---------------------------------------------------------------- 원장 빌더

def _base(cls: pd.DataFrame) -> dict:
    split = mp.split_positions(cls, asof=ASOF)
    return {"mkt_position": split}


def test_component_position_comes_from_the_ledger_not_a_back_solve():
    """position 열이 원장 집계다. capital/0.08 역산은 어떤 포지션도 아니다."""
    cls = _class_positions()
    engine = compute_market_risk_rwa(cls)
    out = mp.build_component_tables(engine.by_class, _base(cls), asof=ASOF)
    rc = out["rwa_market_component"].set_index("risk_class")
    for _, r in cls.iterrows():
        got = float(rc.loc[r["risk_class"], "position"])
        assert got == pytest.approx(float(r["net_position"]), rel=1e-9)
        # 옛 역산값과는 확실히 다르다 (동치가 되는 우연을 배제)
        back = float(rc.loc[r["risk_class"], "capital"]) / 0.08
        assert abs(got - back) > abs(got) * 0.01


def test_component_without_a_ledger_leaves_nan_not_an_invention():
    cls = _class_positions()
    engine = compute_market_risk_rwa(cls)
    out = mp.build_component_tables(engine.by_class, {}, asof=ASOF)
    rc = out["rwa_market_component"]
    assert rc["position"].isna().all()
    assert (rc["capital"] > 0).all()          # 자본은 엔진 값 그대로 남는다


def test_var_allocation_without_inputs_returns_an_empty_ledger():
    out = mp.build_var_es_allocation({})
    assert out["mkt_var_es_portfolio"].empty


# ---------------------------------------------------------------- 계보·결정론

def test_unification_is_visible_in_lineage():
    """일원화의 정의: rwa_market_component 의 상류가 mkt_position 이다."""
    from risk_lib.datamodel import lineage as L
    lin = L.build_lineage()
    up = {e.src for e in lin.edges
          if e.kind in ("feeds", "fk") and e.dst == "rwa_market_component"}
    assert "mkt_position" in up
    up2 = {e.src for e in lin.edges
           if e.kind in ("feeds", "fk") and e.dst == "mkt_var_es_portfolio"}
    assert {"mkt_var_es", "mkt_portfolio_capital"} <= up2


def test_specs_validate_and_measures_match_catalog():
    from risk_lib.datamodel import catalog as cat
    from risk_lib.datamodel.spec import validate
    assert set(mp.MEASURES) == set(cat.RISK_MEASURES)
    assert set(mp.RISK_CLASSES) == set(cat.MARKET_RISK_CLASSES)
    assert validate(mp.portfolio_frame(), mp.PORTFOLIO) == []
    cls = _class_positions()
    split = mp.split_positions(cls, asof=ASOF)
    assert validate(split, mp.POSITION) == []
    assert validate(mp.capital_frame(split), mp.PORTFOLIO_CAPITAL) == []


def test_split_is_deterministic():
    cls = _class_positions()
    a = mp.split_positions(cls, asof=ASOF)
    b = mp.split_positions(cls, asof=ASOF)
    pd.testing.assert_frame_equal(a, b)
