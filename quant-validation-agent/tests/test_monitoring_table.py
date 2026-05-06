import pandas as pd
import pytest

from tools import monitoring_table as mt


def _row_level_df():
    return pd.DataFrame(
        {
            "obs_date": [
                "2025-01", "2025-01", "2025-01", "2025-01", "2025-01",
                "2025-02", "2025-02", "2025-02", "2025-02", "2025-02",
            ],
            "grade": ["A", "A", "B", "B", "C", "A", "B", "B", "C", "C"],
            "default": [0, 0, 1, 0, 1, 0, 1, 0, 1, 1],
        }
    )


def _aggregated_df():
    return pd.DataFrame(
        {
            "obs_date": ["2025-01"] * 3 + ["2025-02"] * 3,
            "grade": ["A", "B", "C"] * 2,
            "count": [100, 50, 20, 110, 55, 25],
            "defaults": [1, 5, 6, 2, 6, 9],
        }
    )


def test_build_time_grade_matrix_row_level():
    df = _row_level_df()
    out = mt.build_time_grade_matrix(df, "obs_date", "grade", "default")
    assert {"obs_date", "grade", "count", "defaults", "default_rate"}.issubset(out.columns)
    a_jan = out[(out["obs_date"] == "2025-01") & (out["grade"] == "A")].iloc[0]
    assert a_jan["count"] == 2 and a_jan["defaults"] == 0 and a_jan["default_rate"] == 0.0


def test_build_time_grade_matrix_with_count_col():
    df = _aggregated_df()
    out = mt.build_time_grade_matrix(df, "obs_date", "grade", "defaults", count_col="count")
    feb_c = out[(out["obs_date"] == "2025-02") & (out["grade"] == "C")].iloc[0]
    assert feb_c["count"] == 25 and feb_c["defaults"] == 9
    assert abs(feb_c["default_rate"] - 9 / 25) < 1e-9


def test_compute_period_psi_vs_baseline_row_level():
    df = _row_level_df()
    out = mt.compute_period_psi_vs_baseline(df, "obs_date", "grade", baseline_period="2025-01")
    assert out.shape[0] == 1
    assert out.iloc[0]["period"] == "2025-02"
    assert out.iloc[0]["psi"] >= 0.0


def test_compute_period_psi_with_count_col():
    df = _aggregated_df()
    out = mt.compute_period_psi_vs_baseline(
        df, "obs_date", "grade", baseline_period="2025-01", count_col="count"
    )
    assert out.shape[0] == 1


def test_compute_period_psi_missing_baseline_raises():
    df = _row_level_df()
    with pytest.raises(ValueError):
        mt.compute_period_psi_vs_baseline(df, "obs_date", "grade", baseline_period="2024-01")


def test_summarize_default_rate_trend():
    df = _row_level_df()
    out = mt.summarize_default_rate_trend(df, "obs_date", "default")
    assert out.shape[0] == 2
    jan = out[out["obs_date"] == "2025-01"].iloc[0]
    assert jan["count"] == 5 and jan["defaults"] == 2
