"""Downturn LGD accuracy."""
import pandas as pd
import pytest

from tools import downturn_lgd as dl


def test_downturn_periods_with_elevated_lgd_show_positive_diff():
    flags = pd.DataFrame({
        "period": ["2020Q1", "2020Q2", "2020Q3", "2020Q4", "2021Q1", "2021Q2"],
        "indicator": [0.02, 0.06, 0.07, 0.04, 0.025, 0.022],
    })
    flagged = dl.identify_downturn_periods(flags, "period", "indicator",
                                           threshold=0.05)
    obs = pd.DataFrame({
        "period": ["2020Q1", "2020Q2", "2020Q3", "2020Q4", "2021Q1", "2021Q2"],
        "realized_lgd": [0.30, 0.55, 0.50, 0.32, 0.28, 0.31],
    })
    out = dl.compute_downturn_lgd(obs, "period", "realized_lgd",
                                  flagged, period_col_flags="period")
    assert out["n_downturn"] == 2
    assert out["mean_lgd_downturn"] == pytest.approx((0.55 + 0.50) / 2, abs=1e-9)
    assert out["mean_lgd_non_downturn"] == pytest.approx(
        (0.30 + 0.32 + 0.28 + 0.31) / 4, abs=1e-9
    )
    assert out["downturn_minus_non_downturn"] > 0.15


def test_compute_downturn_lgd_diff_zero_when_means_equal():
    flags = pd.DataFrame({
        "period": ["P1", "P2", "P3", "P4"],
        "is_downturn": [True, True, False, False],
    })
    obs = pd.DataFrame({
        "period": ["P1", "P2", "P3", "P4"],
        "realized_lgd": [0.3, 0.5, 0.3, 0.5],
    })
    out = dl.compute_downturn_lgd(obs, "period", "realized_lgd", flags)
    assert abs(out["downturn_minus_non_downturn"]) < 1e-9


def test_downturn_lower_is_worse_direction():
    flags = pd.DataFrame({"period": ["A", "B"], "gdp": [-0.02, 0.03]})
    out = dl.identify_downturn_periods(flags, "period", "gdp", threshold=0.0,
                                       direction="lower_is_worse")
    by = dict(zip(out["period"], out["is_downturn"]))
    assert by["A"] is True
    assert by["B"] is False
