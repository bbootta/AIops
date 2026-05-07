import numpy as np
import pandas as pd
import pytest

from middleware import schema_guard as sg


def _credit_df():
    return pd.DataFrame(
        {
            "score": [0.1, 0.2, 0.3, 0.4],
            "target": [0, 1, 0, 1],
            "set": ["dev", "dev", "oot", "oot"],
            "grade": ["A", "B", "A", "C"],
            "pd": [0.01, 0.05, 0.02, 0.20],
        }
    )


def test_credit_scoring_schema_passes_for_valid_df():
    df = _credit_df()
    schema = sg.credit_scoring_schema(
        score_col="score",
        target_col="target",
        set_col="set",
        grade_col="grade",
        pd_col="pd",
    )
    out = sg.check_schema(df, schema)
    assert out["passed"] is True
    assert out["violations"] == []


def test_missing_required_column_is_violation():
    df = _credit_df().drop(columns=["score"])
    schema = sg.credit_scoring_schema(score_col="score", target_col="target")
    out = sg.check_schema(df, schema)
    assert any(v["type"] == "missing" and v["column"] == "score" for v in out["violations"])


def test_target_must_be_binary():
    df = _credit_df()
    df["target"] = [0, 1, 2, 1]
    schema = sg.credit_scoring_schema(score_col="score", target_col="target")
    out = sg.check_schema(df, schema)
    assert any(v["type"] == "dtype" and v["column"] == "target" for v in out["violations"])


def test_pd_out_of_range_is_violation():
    df = _credit_df()
    df.loc[0, "pd"] = 1.5
    schema = sg.credit_scoring_schema(score_col="score", target_col="target", pd_col="pd")
    out = sg.check_schema(df, schema)
    types = {v["type"] for v in out["violations"]}
    assert "max_value" in types


def test_null_in_required_column_is_violation():
    df = _credit_df()
    df.loc[0, "score"] = np.nan
    schema = sg.credit_scoring_schema(score_col="score", target_col="target")
    out = sg.check_schema(df, schema)
    types = {v["type"] for v in out["violations"]}
    assert "null" in types


def test_macro_schema_validates_numeric_columns():
    df = pd.DataFrame(
        {
            "target_macro": [0.1, 0.2, 0.3],
            "gdp_growth": [0.5, 0.4, 0.3],
            "unemployment": [4.0, 4.1, 4.2],
        }
    )
    schema = sg.macro_schema(
        target_col="target_macro", feature_cols=["gdp_growth", "unemployment"]
    )
    assert sg.check_schema(df, schema)["passed"] is True


def test_check_schema_rejects_non_dataframe():
    with pytest.raises(TypeError):
        sg.check_schema([1, 2, 3], sg.credit_scoring_schema(score_col="x", target_col="y"))
