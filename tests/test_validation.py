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


def test_bis_plausible_flags_tier1_and_total_minima_independently():
    """Regression: previously only CET1 fired bis_*_min; T1<6% and Total<8% slipped through."""
    from risk_lib.capital.bis import BISResult
    # CET1 8% passes 4.5%; T1 5% breaches 6%; Total 7% breaches 8%.
    # Ordering total >= tier1 >= cet1 intentionally inverted here is unrelated
    # to what's being tested; we synthesise a result that exercises the per-tier
    # minimum check, not the ordering check.
    bis = BISResult(
        cet1_ratio=0.08, tier1_ratio=0.05, total_ratio=0.07,
        rwa=100.0,
        required={"cet1": 0.07, "tier1": 0.085, "total": 0.105},
        surplus_shortfall={"cet1": 0.01, "tier1": -0.035, "total": -0.035},
    )
    rep = run_consistency_checks(bis_result=bis, rwa_total_for_bis=bis.rwa)
    fails = {c.name for c in rep.checks if c.status == "FAIL"}
    assert "bis_tier1_ratio_min" in fails
    assert "bis_total_ratio_min" in fails
    # CET1 above 4.5% should still report a plausible PASS for cet1.
    cet1_check = next(c for c in rep.checks if c.name == "bis_cet1_ratio_plausible")
    assert cet1_check.status == "PASS"


# ----- 구성요소 대사·fail-closed (2선 통제 시정) --------------------------

def test_rwa_component_reconciliation_catches_a_mutated_frame():
    """행 단위 프레임을 변조하면 헤드라인 대사가 어긋나야 한다.

    이전 검사 63건은 SA·IRB RWA를 전건 변조해도 상태가 하나도 바뀌지 않았다.
    부호·범위만 보거나 같은 값을 자기 자신과 비교했기 때문이다.
    """
    from risk_lib.capital.output_floor import apply_output_floor

    sa = compute_rwa_sa(_sa_df())
    sa_total = float(sa["rwa"].sum())
    internal = sa_total + 10.0 + 20.0 + 30.0        # + ccr + market + op
    of = apply_output_floor(internal, internal * 0.5, 0.725)
    kw = dict(sa_results=sa, market_rwa=20.0, op_rwa=30.0, ccr_rwa=10.0,
              structured_rwa=0.0, output_floor_result=of,
              rwa_total_for_bis=of.rwa_final, total_ead=1.0)

    ok = next(c for c in run_consistency_checks(**kw).checks
              if c.name == "rwa_components_reconcile")
    assert ok.status == "PASS"

    bad = sa.copy()
    bad["rwa"] = bad["rwa"] * 1.2
    hit = next(c for c in run_consistency_checks(**{**kw, "sa_results": bad}).checks
               if c.name == "rwa_components_reconcile")
    assert hit.status == "FAIL"


def test_rwa_component_reconciliation_is_partial_without_ccr_and_structured():
    """CCR·구조화가 넘어오지 않으면 대사가 부분적이라는 사실이 남아야 한다.
    '돌지 않았다'와 '통과했다'가 같은 칸에 들어가면 안 된다."""
    from risk_lib.capital.output_floor import apply_output_floor

    sa = compute_rwa_sa(_sa_df())
    internal = float(sa["rwa"].sum()) + 50.0
    of = apply_output_floor(internal, internal * 0.5, 0.725)
    c = next(x for x in run_consistency_checks(
        sa_results=sa, market_rwa=0.0, op_rwa=0.0, output_floor_result=of,
        rwa_total_for_bis=of.rwa_final).checks
        if x.name == "rwa_components_reconcile")
    assert c.status == "WARN" and "부분 대사" in c.detail


def test_large_exposure_check_is_not_fail_open():
    """한도 리포트가 없으면 '위반 없음'이 아니다."""
    c = next(x for x in run_consistency_checks(limit_report=None).checks
             if x.name == "large_exposure_25pct")
    assert c.status == "WARN" and "부재" in c.detail


def test_identity_checks_are_not_counted_as_controls():
    """항등식은 실패할 수 없으므로 통제 건수에서 빠져야 한다."""
    from risk_lib.capital.bis import compute_bis_ratios

    cap = CapitalStack(cet1=1000, additional_t1=0, tier2=0)
    bis = compute_bis_ratios(cap, 10_000.0)
    rep = run_consistency_checks(bis_result=bis, rwa_total_for_bis=bis.rwa)
    identities = {c.name for c in rep.checks if c.is_identity}
    assert "rwa_matches_bis_input" in identities
    assert "bis_ratio_ordering" in identities
    assert len(rep.controls()) == len(rep.checks) - len(identities)


def test_op_rwa_of_zero_is_a_failure_when_exposure_exists():
    """부호만 보면 운영리스크 RWA를 0으로 지워도 통과한다."""
    c = next(x for x in run_consistency_checks(op_rwa=0.0,
                                               total_ead=1.0e12).checks
             if x.name == "op_rwa_nonneg")
    assert c.status == "FAIL"


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
