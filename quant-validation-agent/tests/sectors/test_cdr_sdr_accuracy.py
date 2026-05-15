"""CDR / SDR arithmetic accuracy."""
import pandas as pd
import pytest

from tools import metric_cdr_sdr as cs


def test_cdr_simple_arithmetic():
    assert cs.calculate_cdr(50, 1000) == pytest.approx(0.05, abs=1e-9)
    assert cs.calculate_cdr(0, 1000) == pytest.approx(0.0, abs=1e-9)


def test_sdr_complements_survivors():
    # 980 survivors out of 1000 → default count 20 → SDR = 0.02
    assert cs.calculate_sdr(980, 1000) == pytest.approx(0.02, abs=1e-9)


def test_summarize_cdr_by_grade_matches_arithmetic():
    df = pd.DataFrame({
        "grade": ["A"] * 5 + ["B"] * 5,
        "default": [0, 0, 1, 0, 0, 1, 1, 1, 0, 0],
    })
    out = cs.summarize_cdr_by_grade(df, "grade", "default")
    rate_a = out.loc[out["grade"] == "A", "default_rate"].iloc[0]
    rate_b = out.loc[out["grade"] == "B", "default_rate"].iloc[0]
    assert rate_a == pytest.approx(1 / 5, abs=1e-9)
    assert rate_b == pytest.approx(3 / 5, abs=1e-9)


def test_compare_cdr_between_periods_records_diff():
    # base: grade=[A,A,B], default=[0,0,1] → A: 0/2=0.0, B: 1/1=1.0
    # cur:  grade=[A,B,B], default=[1,1,1] → A: 1/1=1.0, B: 2/2=1.0
    base = pd.DataFrame({"grade": ["A", "A", "B"], "default": [0, 0, 1]})
    cur = pd.DataFrame({"grade": ["A", "B", "B"], "default": [1, 1, 1]})
    out = cs.compare_cdr_between_periods(base, cur, "grade", "default")
    row_a = out[out["grade"] == "A"].iloc[0]
    row_b = out[out["grade"] == "B"].iloc[0]
    assert row_a["base_dr"] == pytest.approx(0.0)
    assert row_a["cur_dr"] == pytest.approx(1.0)
    assert row_a["dr_diff"] == pytest.approx(1.0)
    # B was 1/1 in base and 2/2 in current → both 1.0 → diff exactly 0
    assert row_b["base_dr"] == pytest.approx(1.0)
    assert row_b["cur_dr"] == pytest.approx(1.0)
    assert row_b["dr_diff"] == pytest.approx(0.0)
