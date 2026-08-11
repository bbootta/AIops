import numpy as np
import pandas as pd
import pytest

from tools import data_profile as dp


def _make_df():
    return pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 3, 4],
            "obs_date": ["2024-01-15", "2024-02-15", "2024-04-15", "2024-04-15", None],
            "score": [0.1, 0.2, np.nan, 0.4, 0.5],
            "target": [0, 1, 0, 1, 0],
        }
    )


def test_profile_dataframe_shapes_and_keys():
    df = _make_df()
    out = dp.profile_dataframe(df)
    assert out["n_rows"] == 5
    assert out["n_cols"] == 4
    assert "customer_id" in out["dtypes"]
    assert 0.0 <= out["missing_ratio"]["score"] <= 1.0


def test_check_missing_returns_per_column():
    df = _make_df()
    out = dp.check_missing(df)
    assert set(out.columns) == {"column", "missing_count", "missing_ratio"}
    score_row = out.loc[out["column"] == "score"].iloc[0]
    assert score_row["missing_count"] == 1


def test_check_duplicates_finds_repeated_keys():
    df = _make_df()
    out = dp.check_duplicates(df, ["customer_id"])
    assert out["duplicate_count"] == 2
    assert out["duplicate_keys"] == [{"customer_id": 3}]


def test_check_duplicates_requires_existing_columns():
    df = _make_df()
    with pytest.raises(KeyError):
        dp.check_duplicates(df, ["nope"])


def test_check_date_coverage_detects_missing_months():
    df = _make_df()
    out = dp.check_date_coverage(df, "obs_date")
    assert out["min_date"] == "2024-01-15"
    assert out["max_date"] == "2024-04-15"
    assert "2024-03" in out["missing_months"]
    assert out["missing_count"] == 1
