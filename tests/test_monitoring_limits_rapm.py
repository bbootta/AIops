import pandas as pd
import pytest

from risk_lib.monitoring.delinquency import (
    delinquency_summary, default_rate, transition_matrix,
)
from risk_lib.monitoring.recovery import (
    recovery_curve, cumulative_recovery_rate,
)
from risk_lib.limits.limit_engine import LimitDefinition, LimitEngine
from risk_lib.performance.rapm import raroc, economic_capital, rapm_report


# ---------- monitoring ---------------------------------------------------

def test_default_rate_count_and_weighted():
    df = pd.DataFrame({"dpd": [0, 30, 95, 200], "ead": [10, 20, 30, 40]})
    assert default_rate(df) == pytest.approx(0.5)
    assert default_rate(df, weight_col="ead") == pytest.approx(70 / 100)


def test_delinquency_summary_segments_sum_to_total():
    df = pd.DataFrame({
        "asset_class": ["A", "A", "B", "B"],
        "dpd": [0, 100, 30, 0],
        "balance": [100, 200, 50, 150],
    })
    summary = delinquency_summary(df, segment_col="asset_class")
    for ac, sub in summary.groupby("asset_class"):
        assert abs(sub["balance_share"].sum() - 1.0) < 1e-9


def test_transition_matrix_rows_sum_to_one():
    t0 = pd.DataFrame({"exposure_id": [1, 2, 3, 4],
                       "rating": ["A", "BBB", "BB", "B"]})
    t1 = pd.DataFrame({"exposure_id": [1, 2, 3, 4],
                       "rating": ["A", "BB", "BB", "DEFAULT"]})
    m = transition_matrix(t0, t1, grades=["A", "BBB", "BB", "B", "DEFAULT"])
    for _, row in m.iterrows():
        assert abs(row.sum() - 1.0) < 1e-9


def test_recovery_curve_monotone():
    workouts = pd.DataFrame({
        "default_id": ["D1", "D1", "D1", "D2", "D2"],
        "months_since_default": [3, 12, 24, 6, 24],
        "recovery_amount": [10, 20, 30, 40, 10],
        "ead_at_default": [100, 100, 100, 100, 100],
    })
    curve = recovery_curve(workouts, horizon_months=24)
    rates = curve["cum_recovery_rate"].tolist()
    assert rates == sorted(rates)
    assert curve["cum_recovery_rate"].iloc[-1] == pytest.approx((60 + 50) / 200)


def test_cumulative_recovery_rate_bounds():
    workouts = pd.DataFrame({
        "default_id": ["D1", "D1"],
        "months_since_default": [3, 6],
        "recovery_amount": [40, 30],
        "ead_at_default": [100, 100],
    })
    r = cumulative_recovery_rate(workouts)
    assert r == pytest.approx(0.7)


# ---------- limits -------------------------------------------------------

def test_limit_engine_absolute_breach():
    port = pd.DataFrame({
        "obligor_id": ["A", "A", "B"],
        "ead": [80, 30, 10],
    })
    eng = LimitEngine([LimitDefinition("test", "obligor_id", None, 100.0)])
    rep = eng.report(port)
    a_row = rep[rep["bucket"] == "A"].iloc[0]
    assert a_row["utilisation"] == pytest.approx(1.10)
    assert a_row["severity"] == "BREACH"


def test_limit_engine_pct_tier1():
    port = pd.DataFrame({"obligor_id": ["X"], "ead": [25.0]})
    eng = LimitEngine(
        [LimitDefinition("동일차주", "obligor_id", None, 0.25, basis="pct_tier1")],
        tier1_capital=100.0,
    )
    rep = eng.report(port)
    assert rep.iloc[0]["utilisation"] == pytest.approx(1.0)
    assert rep.iloc[0]["severity"] == "BREACH"


def test_limit_engine_warn_and_ok():
    port = pd.DataFrame({"obligor_id": ["A", "B"], "ead": [91.0, 50.0]})
    eng = LimitEngine([LimitDefinition("test", "obligor_id", None, 100.0)])
    rep = eng.report(port)
    # B (50% util) is OK ⇒ not in report; A (91%) is WARN
    assert set(rep["bucket"]) == {"A"}
    assert rep.iloc[0]["severity"] == "WARN"


def test_limit_engine_requires_tier1_for_pct():
    port = pd.DataFrame({"obligor_id": ["X"], "ead": [10.0]})
    eng = LimitEngine(
        [LimitDefinition("동일차주", "obligor_id", None, 0.25, basis="pct_tier1")],
    )
    with pytest.raises(ValueError):
        eng.evaluate(port)


# ---------- RAPM ---------------------------------------------------------

def test_economic_capital_positive():
    ec = economic_capital(0.02, 0.45, 1_000_000.0, "corporate", 2.5)
    assert ec > 0


def test_raroc_positive_when_profitable():
    res = raroc(revenue=50_000, operating_cost=10_000,
                pd_value=0.01, lgd=0.40, ead=1_000_000.0,
                asset_class="corporate", maturity=2.5)
    assert res["raroc"] > 0
    assert res["expected_loss"] == pytest.approx(0.01 * 0.40 * 1_000_000)


def test_rapm_report_columns():
    port = pd.DataFrame({
        "exposure_id": ["E1", "E2"],
        "asset_class": ["corporate", "corporate"],
        "ead": [1e6, 2e6],
        "pd": [0.02, 0.03],
        "lgd": [0.45, 0.40],
        "maturity": [2.5, 3.0],
        "revenue": [40_000, 80_000],
        "operating_cost": [5_000, 9_000],
    })
    rep = rapm_report(port, hurdle_rate=0.10)
    assert {"raroc", "value_added", "pass_hurdle"}.issubset(rep.columns)
    assert len(rep) == 2
