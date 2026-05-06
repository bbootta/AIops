import math

import pandas as pd
import pytest

from tools import metric_cdr_sdr as m


def test_cdr_basic():
    assert abs(m.calculate_cdr(10, 100) - 0.10) < 1e-9


def test_cdr_zero_denominator_returns_nan():
    assert math.isnan(m.calculate_cdr(0, 0))


def test_cdr_negative_raises():
    with pytest.raises(ValueError):
        m.calculate_cdr(-1, 100)


def test_sdr_basic():
    assert abs(m.calculate_sdr(80, 100) - 0.20) < 1e-9


def test_sdr_zero_denominator_returns_nan():
    assert math.isnan(m.calculate_sdr(0, 0))


def test_sdr_survival_exceeds_exposure():
    with pytest.raises(ValueError):
        m.calculate_sdr(110, 100)


def test_summarize_cdr_by_grade():
    df = pd.DataFrame(
        {
            "grade": ["A", "A", "B", "B", "C"],
            "default": [0, 0, 1, 0, 1],
        }
    )
    out = m.summarize_cdr_by_grade(df, "grade", "default")
    assert set(out.columns) >= {"grade", "count", "defaults", "default_rate"}
    assert out.loc[out["grade"] == "C", "default_rate"].iloc[0] == 1.0


def test_compare_cdr_between_periods():
    base = pd.DataFrame({"grade": ["A", "B"], "default": [0, 1]})
    cur = pd.DataFrame({"grade": ["A", "B"], "default": [1, 1]})
    out = m.compare_cdr_between_periods(base, cur, "grade", "default")
    assert "dr_diff" in out.columns
