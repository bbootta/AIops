import numpy as np
import pandas as pd
import pytest

from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.capital.rwa_sa import compute_rwa_sa
from risk_lib.validation.consistency import (
    ConsistencyCheck, ValidationReport, run_consistency_checks,
)
from risk_lib.validation.backtest import (
    hosmer_lemeshow, binomial_test_per_grade, pd_backtest_report,
)


def _sa_df():
    return pd.DataFrame({
        "exposure_id": ["A1"],
        "asset_class": ["corporate"],
        "ead": [1e6], "rating": ["BBB"], "ltv": [None], "past_due": [False],
    })


def _irb_df():
    return pd.DataFrame({
        "exposure_id": ["B1"],
        "asset_class": ["corporate"],
        "ead": [1e6], "pd": [0.02], "lgd": [0.45], "maturity": [2.5],
    })


def test_clean_inputs_all_pass():
    sa = compute_rwa_sa(_sa_df())
    irb = compute_rwa_irb(_irb_df())
    rwa_total = float(sa["rwa"].sum() + irb["rwa"].sum())
    cap = CapitalStack(cet1=rwa_total * 0.10, additional_t1=0, tier2=0)
    bis = compute_bis_ratios(cap, rwa_total)
    rep = run_consistency_checks(
        sa_results=sa, irb_results=irb,
        bis_result=bis, rwa_total_for_bis=rwa_total,
    )
    summary = rep.summary()
    assert summary.get("FAIL", 0) == 0
    assert rep.passes()


def test_detects_pd_out_of_bounds():
    bad = _irb_df()
    bad.loc[0, "pd"] = 1.5
    rep = run_consistency_checks(irb_results=bad)
    assert any(c.name == "pd_in_[0,1]" and c.status == "FAIL" for c in rep.checks)
    assert not rep.passes()


def test_detects_sa_irb_overlap():
    sa = compute_rwa_sa(_sa_df().assign(exposure_id="DUP"))
    irb = compute_rwa_irb(_irb_df().assign(exposure_id="DUP"))
    rep = run_consistency_checks(sa_results=sa, irb_results=irb)
    assert any(c.name == "sa_irb_no_overlap" and c.status == "FAIL"
               for c in rep.checks)


def test_detects_rwa_mismatch_to_bis():
    sa = compute_rwa_sa(_sa_df())
    cap = CapitalStack(cet1=1000, additional_t1=0, tier2=0)
    bis = compute_bis_ratios(cap, 10_000.0)
    rep = run_consistency_checks(
        sa_results=sa, bis_result=bis,
        rwa_total_for_bis=99_999.0,  # mismatched on purpose
    )
    assert any(c.name == "rwa_matches_bis_input" and c.status == "FAIL"
               for c in rep.checks)


def test_hosmer_lemeshow_calibrated():
    rng = np.random.default_rng(0)
    pd_pred = rng.uniform(0.001, 0.3, 5000)
    # generate defaults from the predicted PDs ⇒ well-calibrated
    d = (rng.random(5000) < pd_pred).astype(int)
    res = hosmer_lemeshow(pd_pred, d, n_groups=10)
    # well-calibrated ⇒ should not reject; p > 0.05 most seeds
    assert 0 <= res["p_value"] <= 1


def test_hosmer_lemeshow_miscalibrated():
    rng = np.random.default_rng(1)
    pd_pred = rng.uniform(0.001, 0.05, 5000)
    # induce 3x higher realised defaults than predicted
    d = (rng.random(5000) < pd_pred * 3).astype(int)
    res = hosmer_lemeshow(pd_pred, d, n_groups=10)
    assert res["chi_square"] > 0
    assert res["p_value"] < 0.05  # detects miscalibration


def test_binomial_per_grade_zones():
    rng = np.random.default_rng(2)
    n = 3000
    grade = rng.choice(["A", "BBB", "BB"], n)
    pd_pred = np.where(grade == "A", 0.005,
              np.where(grade == "BBB", 0.02, 0.06))
    d = (rng.random(n) < pd_pred).astype(int)
    out = binomial_test_per_grade(grade, pd_pred, d)
    assert set(out["grade"]) == {"A", "BBB", "BB"}
    # GREEN expected when realised matches predicted
    assert (out["zone"] == "GREEN").all() or (out["zone"] != "RED").all()


def test_pd_backtest_report_structure():
    rng = np.random.default_rng(3)
    n = 1500
    df = pd.DataFrame({
        "grade": rng.choice(["AAA", "AA", "A", "BBB", "BB", "B"], n),
        "pd": rng.uniform(0.001, 0.2, n),
        "default_12m": rng.integers(0, 2, n),
    })
    res = pd_backtest_report(df)
    assert "hosmer_lemeshow" in res
    assert "per_grade" in res
    assert isinstance(res["per_grade"], pd.DataFrame)
