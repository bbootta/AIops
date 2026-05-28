import numpy as np
import pandas as pd
import pytest

from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.provisioning.macro import (
    MacroScenario, DEFAULT_MACRO_SCENARIOS, pit_pd, macro_ecl,
)
from risk_lib.stress.scenario import (
    ADVERSE, run_stress, evaluate_scenario,
)
from risk_lib.stress.reverse import reverse_stress, StressAxis
from risk_lib.validation.consistency import run_consistency_checks


# ---------- fixtures -----------------------------------------------------

def _book(n=60, pd_=0.03, lgd=0.45, maturity=3.0):
    return pd.DataFrame({
        "exposure_id": [f"E{i}" for i in range(n)],
        "asset_class": ["corporate"] * n,
        "ead": [1e7] * n,
        "pd": [pd_] * n,
        "lgd": [lgd] * n,
        "maturity": [maturity] * n,
        "dpd": [0] * n,
    })


def _capital_for(book, rwa_other, cet1_pct):
    rwa_irb = float(compute_rwa_irb(book)["rwa"].sum())
    total = rwa_irb + rwa_other
    return CapitalStack(cet1=total * cet1_pct, additional_t1=0.0, tier2=0.0)


# ---------- PIT transform ------------------------------------------------

def test_pit_pd_zero_z_equals_ttc():
    assert pit_pd(0.02, 0.0) == pytest.approx(0.02, abs=1e-6)


def test_pit_pd_monotone_in_z():
    assert pit_pd(0.05, -1.0) < 0.05 < pit_pd(0.05, 1.0)
    assert pit_pd(0.05, 1.0) < pit_pd(0.05, 2.0)


def test_pit_pd_higher_rho_more_sensitive():
    # under a downturn (z>0), higher asset correlation amplifies the PD lift
    assert pit_pd(0.03, 1.5, rho=0.25) > pit_pd(0.03, 1.5, rho=0.10)


def test_z_path_reversion():
    sev = MacroScenario("severe", 0.2, gdp_path=(-0.05, -0.03, -0.01))
    z = sev.z_path(6)
    assert len(z) == 6
    assert z[0] == pytest.approx(1.5)          # -30 * -0.05
    # tail reverts geometrically toward 0
    assert z[3] == pytest.approx(0.3 * 0.5)
    assert z[5] < z[4] < z[3]
    assert (z >= 0).all()


# ---------- macro (PIT, probability-weighted) ECL ------------------------

def _mixed_book():
    return pd.DataFrame({
        "exposure_id": ["S1", "S2", "S3"],
        "asset_class": ["corporate"] * 3,
        "ead": [1e7, 1e7, 1e7],
        "pd": [0.03, 0.03, 0.5],
        "lgd": [0.45, 0.45, 0.45],
        "maturity": [3.0, 3.0, 3.0],
        "dpd": [0, 45, 120],   # stage 1 / 2 / 3
    })


def test_macro_ecl_columns_and_stages():
    res = macro_ecl(_mixed_book(), DEFAULT_MACRO_SCENARIOS)
    cols = res.per_exposure.columns
    assert "ecl" in cols and "stage" in cols
    for s in DEFAULT_MACRO_SCENARIOS:
        assert f"ecl_{s.name}" in cols
    assert list(res.per_exposure["stage"]) == [1, 2, 3]


def test_macro_ecl_severe_ge_baseline():
    res = macro_ecl(_mixed_book(), DEFAULT_MACRO_SCENARIOS)
    by = res.by_scenario.set_index("scenario")["ecl"]
    assert by["severe"] >= by["downside"] >= by["baseline"]


def test_macro_weighted_in_scenario_range():
    res = macro_ecl(_mixed_book(), DEFAULT_MACRO_SCENARIOS)
    ecls = res.by_scenario["ecl"].values
    assert ecls.min() - 1e-6 <= res.weighted_total <= ecls.max() + 1e-6


def test_macro_stage3_invariant_to_scenario():
    # defaulted (stage 3) ECL = LGD*EAD regardless of macro path
    res = macro_ecl(_mixed_book(), DEFAULT_MACRO_SCENARIOS)
    s3 = res.per_exposure.iloc[2]
    assert s3["ecl"] == pytest.approx(0.45 * 1e7)
    for s in DEFAULT_MACRO_SCENARIOS:
        assert s3[f"ecl_{s.name}"] == pytest.approx(0.45 * 1e7)


def test_macro_ecl_probabilities_renormalised():
    scen = [
        MacroScenario("a", 2.0, gdp_path=(0.0,)),
        MacroScenario("b", 2.0, gdp_path=(-0.05,)),
    ]
    res = macro_ecl(_book(n=5), scen)
    assert res.by_scenario["probability"].sum() == pytest.approx(1.0)


# ---------- evaluate_scenario shared logic -------------------------------

def test_evaluate_scenario_matches_run_stress():
    book = _book()
    rwa_other = 5e8
    cap = _capital_for(book, rwa_other, 0.12)
    base_ecl = compute_ecl(book)["ecl"].sum()

    ev = evaluate_scenario(book, cap, rwa_other, ADVERSE, base_ecl=base_ecl)
    row = run_stress(book, cap, rwa_other, scenarios=[ADVERSE]).iloc[0]

    assert ev["cet1_ratio"] == pytest.approx(row["cet1_ratio"])
    assert ev["rwa_total"] == pytest.approx(row["rwa_total"])
    assert ev["ecl"] == pytest.approx(row["ecl"])


# ---------- reverse stress -----------------------------------------------

def test_reverse_stress_hits_target():
    book = _book()
    rwa_other = float(compute_rwa_irb(book)["rwa"].sum())  # ~50% of total
    cap = _capital_for(book, rwa_other, 0.09)              # base CET1 = 9%
    res = reverse_stress(book, cap, rwa_other, metric="cet1",
                         target_ratio=0.07)
    assert not res.resilient
    assert res.base_ratio == pytest.approx(0.09, abs=1e-3)
    assert res.critical_severity > 0
    assert res.ratio_at_break == pytest.approx(0.07, abs=1e-3)
    assert res.implied_gdp_shock < 0          # a downturn
    assert res.implied_lgd_addon > 0


def test_reverse_stress_higher_target_lower_severity():
    book = _book()
    rwa_other = float(compute_rwa_irb(book)["rwa"].sum())
    cap = _capital_for(book, rwa_other, 0.09)
    easy = reverse_stress(book, cap, rwa_other, target_ratio=0.085)
    hard = reverse_stress(book, cap, rwa_other, target_ratio=0.070)
    # a higher break threshold is reached with less stress
    assert easy.critical_severity < hard.critical_severity


def test_reverse_stress_resilient_when_well_capitalised():
    book = _book()
    rwa_other = float(compute_rwa_irb(book)["rwa"].sum())
    cap = _capital_for(book, rwa_other, 0.50)   # huge buffer
    res = reverse_stress(book, cap, rwa_other, target_ratio=0.07,
                         max_severity=10.0)
    assert res.resilient
    assert res.ratio_at_break > res.target_ratio


def test_reverse_stress_already_breached():
    book = _book()
    rwa_other = float(compute_rwa_irb(book)["rwa"].sum())
    cap = _capital_for(book, rwa_other, 0.05)   # base CET1 5% < 7% target
    res = reverse_stress(book, cap, rwa_other, target_ratio=0.07)
    assert not res.resilient
    assert res.critical_severity == 0.0


# ---------- validation hooks ---------------------------------------------

def test_validation_macro_and_reverse():
    book = _book()
    rwa_other = float(compute_rwa_irb(book)["rwa"].sum())
    cap = _capital_for(book, rwa_other, 0.09)
    macro = macro_ecl(book, DEFAULT_MACRO_SCENARIOS)
    rev = reverse_stress(book, cap, rwa_other, target_ratio=0.07)
    rep = run_consistency_checks(macro_ecl_result=macro,
                                 reverse_stress_result=rev)
    names = {c.name: c.status for c in rep.checks}
    assert names["macro_scenario_prob_sum"] == "PASS"
    assert names["macro_weighted_in_range"] == "PASS"
    assert names["macro_ecl_gdp_monotone"] == "PASS"
    assert names["reverse_stress_solved"] == "PASS"
    assert rep.passes()
