import pandas as pd
import pytest

from tools import sample_size_check as ssc


def test_min_observations():
    df = pd.DataFrame({"x": list(range(10))})
    assert ssc.check_min_observations(df, 5)["pass"] is True
    assert ssc.check_min_observations(df, 100)["pass"] is False


def test_min_defaults():
    df = pd.DataFrame({"d": [0, 0, 1, 1, 1]})
    assert ssc.check_min_defaults(df, "d", 3)["pass"] is True
    assert ssc.check_min_defaults(df, "d", 4)["pass"] is False


def test_grade_level_counts():
    df = pd.DataFrame({"grade": ["A"] * 5 + ["B"] * 2})
    out = ssc.check_grade_level_counts(df, "grade", 3)
    assert out.loc[out["grade"] == "B", "pass"].iloc[0] is False or bool(out.loc[out["grade"] == "B", "pass"].iloc[0]) is False
    assert bool(out.loc[out["grade"] == "A", "pass"].iloc[0]) is True


def test_summary_includes_keys():
    df = pd.DataFrame({"grade": ["A", "B", "A"], "default": [0, 1, 0]})
    out = ssc.summarize_sample_size_issues(df, "grade", "default")
    assert "n" in out and "n_grades" in out and "defaults" in out


def test_missing_column_raises():
    df = pd.DataFrame({"x": [1]})
    with pytest.raises(ValueError):
        ssc.check_grade_level_counts(df, "grade", 1)
