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
