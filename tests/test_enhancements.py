import numpy as np
import pandas as pd
import pytest

from risk_lib.capital.crm import (
    ccf_ead, crm_adjusted_ead, guarantee_substitution, apply_crm,
)
from risk_lib.capital.op_risk import (
    BusinessIndicator, business_indicator_component, compute_op_risk_rwa,
)
from risk_lib.capital.market_risk import compute_market_risk_rwa
from risk_lib.capital.output_floor import apply_output_floor
from risk_lib.capital.leverage import compute_leverage_ratio, exposure_measure
from risk_lib.capital.bis import CapitalStack
from risk_lib.provisioning.ecl import (
    Stage, classify_stage, twelve_month_ecl, lifetime_ecl, compute_ecl,
)
from risk_lib.stress.scenario import (
    BASELINE, ADVERSE, SEVERELY_ADVERSE, apply_scenario, run_stress, Scenario,
)
from risk_lib.limits.concentration import hhi, normalised_hhi, concentration_report
from risk_lib.validation.consistency import run_consistency_checks


# ---------- CRM / CCF ----------------------------------------------------

def test_ccf_ead():
    assert ccf_ead(100, 200, "direct_credit_substitute") == 300
    assert ccf_ead(100, 200, "commitment_le_1y") == pytest.approx(180.0)


def test_ccf_unknown_type():
    with pytest.raises(ValueError):
        ccf_ead(1, 1, "nope")


def test_crm_adjusted_ead_cash_full_cover():
    # cash collateral (0 haircut) fully covering exposure ⇒ E* = 0
    assert crm_adjusted_ead(100, 100, "cash") == pytest.approx(0.0)


def test_crm_adjusted_ead_with_haircut_and_fx():
    e = crm_adjusted_ead(100, 50, "equity_main_index", fx_mismatch=True)
    # C*(1 - 0.20 - 0.08) = 50*0.72 = 36 ⇒ 100 - 36 = 64
    assert e == pytest.approx(64.0)


def test_guarantee_substitution_blends_rw():
    res = guarantee_substitution(100, 60, obligor_rw=1.0, guarantor_rw=0.2)
    assert res["rwa"] == pytest.approx(60 * 0.2 + 40 * 1.0)
    assert res["blended_rw"] == pytest.approx(0.52)


def test_apply_crm_reduces_ead():
    port = pd.DataFrame({
        "exposure_id": ["E1"],
        "ead": [100.0],
        "collateral_value": [40.0],
        "collateral_type": ["cash"],
    })
    out = apply_crm(port)
    assert out.loc[0, "ead_gross"] == 100.0
    assert out.loc[0, "ead"] == pytest.approx(60.0)


# ---------- Operational risk --------------------------------------------

def test_bic_marginal_buckets():
    # BI = 2bn ⇒ 1bn*0.12 + 1bn*0.15 = 0.27bn
    assert business_indicator_component(2_000_000_000) == pytest.approx(270_000_000)


def test_op_risk_ilm_one_when_no_losses_disabled():
    bi = BusinessIndicator(ildc=5e8, sc=3e8, fc=2e8)  # BI = 1bn
    res = compute_op_risk_rwa(bi, avg_annual_losses_10y=0.0, use_ilm=False)
    assert res.ilm == 1.0
    assert res.rwa == pytest.approx(res.orc * 12.5)
    assert res.bic == pytest.approx(1_000_000_000 * 0.12)


def test_op_risk_ilm_increases_with_losses():
    bi = BusinessIndicator(ildc=2e9, sc=0, fc=0)  # BI = 2bn
    low = compute_op_risk_rwa(bi, avg_annual_losses_10y=1e7)
    high = compute_op_risk_rwa(bi, avg_annual_losses_10y=1e9)
    assert high.ilm > low.ilm


# ---------- Market risk --------------------------------------------------

def test_market_risk_rwa_basic():
    pos = pd.DataFrame({
        "risk_class": ["fx", "equity"],
        "net_position": [1_000_000, -500_000],
    })
    res = compute_market_risk_rwa(pos)
    # fx: 1e6*0.08*1.20 = 96000 ; equity: 5e5*0.08*3.50 = 140000
    assert res.by_class["fx"] == pytest.approx(96_000)
    assert res.by_class["equity"] == pytest.approx(140_000)
    assert res.rwa == pytest.approx((96_000 + 140_000) * 12.5)


def test_market_risk_unknown_class():
    pos = pd.DataFrame({"risk_class": ["weather"], "net_position": [1]})
    with pytest.raises(ValueError):
        compute_market_risk_rwa(pos)


# ---------- Output floor -------------------------------------------------

def test_output_floor_binding():
    res = apply_output_floor(rwa_internal=70, rwa_standardised=100, floor=0.725)
    assert res.is_binding
    assert res.rwa_final == pytest.approx(72.5)
    assert res.add_on == pytest.approx(2.5)


def test_output_floor_not_binding():
    res = apply_output_floor(rwa_internal=80, rwa_standardised=100, floor=0.725)
    assert not res.is_binding
    assert res.rwa_final == pytest.approx(80)
    assert res.add_on == pytest.approx(0.0)


# ---------- Leverage -----------------------------------------------------

def test_leverage_ratio_pass_fail():
    ok = compute_leverage_ratio(40, 1000)
    assert ok.leverage_ratio == pytest.approx(0.04)
    assert ok.passes()
    bad = compute_leverage_ratio(20, 1000)
    assert not bad.passes()


def test_exposure_measure_ccf_floor():
    # off-balance CCF floored at 10%
    em = exposure_measure(1000, off_balance_notional=500, off_balance_ccf=0.0)
    assert em == pytest.approx(1000 + 500 * 0.10)


# ---------- IFRS 9 ECL ---------------------------------------------------

def test_stage_classification():
    assert classify_stage(0, 0.01) == Stage.STAGE_1
    assert classify_stage(45, 0.01) == Stage.STAGE_2          # dpd>=30
    assert classify_stage(120, 0.01) == Stage.STAGE_3         # dpd>=90
    assert classify_stage(0, 0.05, pd_origination=0.01) == Stage.STAGE_2  # PD 5x


def test_lifetime_ecl_ge_12m():
    ecl12 = twelve_month_ecl(0.05, 0.45, 1_000_000)
    ecl_life = lifetime_ecl(0.05, 0.45, 1_000_000, maturity_years=5, amortising=False)
    assert ecl_life > ecl12


def test_compute_ecl_columns_and_stage3_max():
    port = pd.DataFrame({
        "exposure_id": ["A", "B", "C"],
        "ead": [1e6, 1e6, 1e6],
        "pd": [0.01, 0.02, 0.5],
        "lgd": [0.4, 0.4, 0.4],
        "dpd": [0, 45, 120],
        "maturity": [1.0, 5.0, 3.0],
    })
    out = compute_ecl(port)
    assert list(out["stage"]) == [1, 2, 3]
    # stage 3 ECL = lgd*ead
    assert out.loc[2, "ecl"] == pytest.approx(0.4 * 1e6)


# ---------- Stress -------------------------------------------------------

def _irb_port():
    return pd.DataFrame({
        "exposure_id": [f"E{i}" for i in range(50)],
        "asset_class": ["corporate"] * 50,
        "ead": [1e6] * 50,
        "pd": [0.02] * 50,
        "lgd": [0.45] * 50,
        "maturity": [2.5] * 50,
        "dpd": [0] * 50,
    })


def test_apply_scenario_increases_pd():
    port = _irb_port()
    stressed = apply_scenario(port, SEVERELY_ADVERSE)
    assert (stressed["pd"] >= port["pd"]).all()
    assert (stressed["lgd"] >= port["lgd"]).all()


def test_run_stress_monotone():
    port = _irb_port()
    cap = CapitalStack(cet1=2e6, additional_t1=0, tier2=0)
    df = run_stress(port, cap, rwa_other=1e6,
                    scenarios=[BASELINE, ADVERSE, SEVERELY_ADVERSE])
    base = df[df["scenario"] == "baseline"].iloc[0]
    sev = df[df["scenario"] == "severely_adverse"].iloc[0]
    assert sev["rwa_total"] >= base["rwa_total"]
    assert sev["cet1_ratio"] <= base["cet1_ratio"]


# ---------- Concentration ------------------------------------------------

def test_hhi_bounds():
    assert hhi([1, 1, 1, 1]) == pytest.approx(0.25)
    assert hhi([100, 0, 0]) == pytest.approx(1.0)
    assert normalised_hhi([1, 1, 1, 1]) == pytest.approx(0.0)


def test_concentration_report():
    port = pd.DataFrame({
        "sector": ["a", "a", "b"],
        "ead": [50, 50, 100],
    })
    rep = concentration_report(port, ["sector"])
    assert rep.loc[0, "hhi"] == pytest.approx(0.5)
    assert rep.loc[0, "top1_share"] == pytest.approx(0.5)


# ---------- New validation checks ---------------------------------------

def test_validation_catches_leverage_breach():
    lev = compute_leverage_ratio(20, 1000)  # 2% < 3%
    rep = run_consistency_checks(leverage_result=lev)
    assert any(c.name == "leverage_min_3pct" and c.status == "FAIL"
               for c in rep.checks)
    assert not rep.passes()


def test_validation_output_floor_binding_warns():
    of = apply_output_floor(70, 100, 0.725)
    rep = run_consistency_checks(output_floor_result=of)
    c = next(c for c in rep.checks if c.name == "output_floor_applied")
    assert c.status == "WARN"
    assert rep.passes()  # WARN does not fail


def test_validation_stress_monotone_pass():
    port = _irb_port()
    cap = CapitalStack(cet1=2e6, additional_t1=0, tier2=0)
    stress_df = run_stress(port, cap, rwa_other=1e6)
    rep = run_consistency_checks(stress_results=stress_df)
    assert any(c.name == "stress_monotone" and c.status == "PASS"
               for c in rep.checks)


def test_validation_ecl_nonneg():
    port = pd.DataFrame({
        "exposure_id": ["A"], "ead": [1e6], "pd": [0.02], "lgd": [0.4],
        "dpd": [0], "maturity": [1.0],
    })
    ecl = compute_ecl(port)
    rep = run_consistency_checks(ecl_results=ecl)
    assert any(c.name == "ecl_nonneg" and c.status == "PASS" for c in rep.checks)
