import math

import pandas as pd
import pytest

from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.rwa_irb import irb_capital_requirement, compute_rwa_irb
from risk_lib.capital.rwa_sa import sa_risk_weight, compute_rwa_sa


# ---------- SA -----------------------------------------------------------

def test_sa_risk_weight_lookups():
    assert sa_risk_weight("sovereign", "AAA-AA") == 0.0
    assert sa_risk_weight("corporate", "AAA-AA") == 0.20
    assert sa_risk_weight("corporate", "UNRATED") == 1.00
    assert sa_risk_weight("retail_regulatory") == 0.75
    assert sa_risk_weight("residential_mortgage", ltv=0.45) == 0.20
    assert sa_risk_weight("residential_mortgage", ltv=0.85) == 0.40
    assert sa_risk_weight("corporate", "AAA-AA", past_due=True) == 1.50


def test_sa_risk_weight_unknown_asset_class():
    with pytest.raises(ValueError):
        sa_risk_weight("unknown")


def test_compute_rwa_sa_rejects_crm_factor_out_of_range():
    """crm_factor outside [0,1] must raise rather than silently propagate."""
    portfolio = pd.DataFrame({
        "exposure_id": ["E1", "E2"],
        "asset_class": ["corporate", "corporate"],
        "ead": [1_000_000.0, 1_000_000.0],
        "rating": ["BBB", "BBB"],
        "ltv": [None, None],
        "past_due": [False, False],
        "crm_factor": [0.5, 1.5],   # 1.5 is out of range
    })
    with pytest.raises(ValueError, match="crm_factor"):
        compute_rwa_sa(portfolio)


def test_compute_rwa_sa_accepts_valid_crm_factor():
    portfolio = pd.DataFrame({
        "exposure_id": ["E1"],
        "asset_class": ["corporate"],
        "ead": [1_000_000.0],
        "rating": ["BBB"],
        "ltv": [None],
        "past_due": [False],
        "crm_factor": [0.5],
    })
    res = compute_rwa_sa(portfolio)
    assert res.loc[0, "rwa"] == pytest.approx(1_000_000.0 * 0.75 * 0.5)


def test_mortgage_ltv_rw_table_invariant():
    """RW table must have one more entry than edges (one tail bucket)."""
    from risk_lib.capital.rwa_sa import _MORTGAGE_LTV_EDGES, _MORTGAGE_LTV_RWS
    assert len(_MORTGAGE_LTV_RWS) == len(_MORTGAGE_LTV_EDGES) + 1


def test_compute_rwa_sa_basic():
    portfolio = pd.DataFrame({
        "exposure_id": ["E1", "E2"],
        "asset_class": ["corporate", "sovereign"],
        "ead": [1_000_000, 5_000_000],
        "rating": ["BBB", "AAA-AA"],
        "ltv": [None, None],
        "past_due": [False, False],
    })
    res = compute_rwa_sa(portfolio)
    assert res.loc[0, "rw"] == 0.75
    assert res.loc[1, "rw"] == 0.0
    assert res.loc[0, "rwa"] == pytest.approx(1_000_000 * 0.75)
    assert res.loc[0, "capital_8pct"] == pytest.approx(60_000.0)


# ---------- IRB ----------------------------------------------------------

def test_irb_k_known_anchor():
    """Sanity: known anchor PD=1%, LGD=45%, M=2.5, corporate ⇒ K≈8.4%."""
    k = irb_capital_requirement(0.01, 0.45, "corporate", 2.5)
    assert 0.07 < k < 0.10, f"K={k}"


def test_irb_k_monotone_in_pd():
    ks = [irb_capital_requirement(p, 0.45, "corporate") for p in
          [0.005, 0.01, 0.03, 0.10]]
    assert ks == sorted(ks)


def test_irb_k_monotone_in_lgd():
    ks = [irb_capital_requirement(0.02, l, "corporate") for l in
          [0.20, 0.45, 0.75]]
    assert ks == sorted(ks)


def test_irb_retail_lower_corr_lower_k():
    # retail revolving correlation is 4% vs corporate ~12-24% ⇒ lower K
    k_rev = irb_capital_requirement(0.02, 0.45, "retail_revolving")
    k_corp = irb_capital_requirement(0.02, 0.45, "corporate", 2.5)
    assert k_rev < k_corp


def test_compute_rwa_irb_shape():
    portfolio = pd.DataFrame({
        "exposure_id": ["E1"],
        "asset_class": ["corporate"],
        "ead": [1_000_000.0],
        "pd": [0.02],
        "lgd": [0.45],
        "maturity": [2.5],
    })
    res = compute_rwa_irb(portfolio)
    assert {"k", "rwa", "capital_8pct", "el"}.issubset(res.columns)
    assert res.loc[0, "el"] == pytest.approx(0.02 * 0.45 * 1_000_000.0)
    assert res.loc[0, "rwa"] == pytest.approx(res.loc[0, "k"] * 12.5 * 1_000_000.0)


# ---------- BIS ----------------------------------------------------------

def test_bis_basic_ratios():
    cap = CapitalStack(cet1=100, additional_t1=20, tier2=30)
    bis = compute_bis_ratios(cap, 1000.0, buffers={
        "capital_conservation": 0.025, "countercyclical": 0, "dsib": 0,
    })
    assert bis.cet1_ratio == pytest.approx(0.10)
    assert bis.tier1_ratio == pytest.approx(0.12)
    assert bis.total_ratio == pytest.approx(0.15)
    # CET1 10% > 4.5+2.5=7%, Tier1 12% > 8.5%, Total 15% > 10.5%
    assert bis.passes()


def test_bis_fails_when_undercapitalised():
    cap = CapitalStack(cet1=30, additional_t1=5, tier2=5)
    bis = compute_bis_ratios(cap, 1000.0)
    assert not bis.passes()


def test_bis_rejects_zero_rwa():
    cap = CapitalStack(cet1=100, additional_t1=0, tier2=0)
    with pytest.raises(ValueError):
        compute_bis_ratios(cap, 0.0)


def test_ec_covers_every_credit_rwa_component(result):
    """분모(RWA)에 든 신용형 갈래가 내부자본(EC)에서 빠지지 않는다.

    구조화 4.13조가 RWA에는 들어가고 EC에는 빠져 있었고, 그 시정 뒤에도 CCR이
    같은 상태로 남아 있었다 — 둘 다 "산출해놓고 합계에 넣지 않기"다.

    금액이 아니라 **구성요소 이름**으로 본다. CCR 경제자본 기여는 15.6억으로
    Pillar 1 소요자본 1,078조의 0.001%라, 총량 비교로는 빠져도 절대 걸리지
    않는다 — 통제가 있어 보이는데 동작하지 않는 상태가 된다.
    """
    from risk_lib.validation.cross_domain import (
        _CREDIT_RWA_KEYS, _check_ec_covers_rwa,
    )

    present = {k for k in _CREDIT_RWA_KEYS
               if float(result.rwa.get(k, 0.0) or 0.0) > 0}
    assert present, "신용형 RWA 갈래가 하나도 없다 — 검사가 아무것도 지키지 않는다"
    assert present <= set(result.icaap.credit_ec_components), (
        f"RWA에 있는데 EC에 없는 갈래: "
        f"{sorted(present - set(result.icaap.credit_ec_components))}")

    check = [c for c in result.validation.checks
             if c.name == "xd_ec_covers_rwa_components"]
    assert check and check[0].status == "PASS", check

    # 결함을 되돌리면 잡히는가 — 잡지 못하는 검사는 통제가 아니다.
    import dataclasses
    broken = dataclasses.replace(result.icaap, credit_ec_components=tuple(
        k for k in result.icaap.credit_ec_components if k != "ccr"))
    out = _check_ec_covers_rwa(dict(result.rwa), broken)
    assert out and out[0].status == "FAIL", "CCR을 빼도 검사가 통과한다"
