import pandas as pd
import pytest

from tools import downturn_lgd as dl


def _flags():
    return pd.DataFrame({
        "period": ["2020Q1", "2020Q2", "2020Q3", "2020Q4", "2021Q1"],
        "indicator": [0.02, 0.06, 0.07, 0.04, 0.025],
    })


def test_identify_downturn_higher_is_worse():
    out = dl.identify_downturn_periods(_flags(), "period", "indicator", threshold=0.05)
    by = dict(zip(out["period"], out["is_downturn"]))
    assert by["2020Q2"] is True
    assert by["2020Q3"] is True
    assert by["2020Q1"] is False
    assert by["2021Q1"] is False


def test_identify_downturn_lower_is_worse():
    df = pd.DataFrame({"period": ["a", "b", "c"], "gdp": [0.03, -0.01, 0.02]})
    out = dl.identify_downturn_periods(df, "period", "gdp", threshold=0.0,
                                       direction="lower_is_worse")
    by = dict(zip(out["period"], out["is_downturn"]))
    assert by["b"] is True
    assert by["a"] is False


def test_identify_downturn_rejects_bad_direction():
    df = pd.DataFrame({"p": ["a"], "v": [0.0]})
    with pytest.raises(ValueError):
        dl.identify_downturn_periods(df, "p", "v", threshold=0.0, direction="zigzag")


def test_compute_downturn_lgd_basic():
    obs = pd.DataFrame({
        "period": ["2020Q1", "2020Q2", "2020Q3", "2020Q4", "2021Q1"],
        "realized_lgd": [0.30, 0.55, 0.50, 0.32, 0.28],
    })
    flags = dl.identify_downturn_periods(_flags(), "period", "indicator",
                                         threshold=0.05)
    out = dl.compute_downturn_lgd(obs, "period", "realized_lgd",
                                  flags, period_col_flags="period")
    # 2020Q2, 2020Q3 are downturn
    assert out["n_downturn"] == 2
    assert out["n_non_downturn"] == 3
    assert out["mean_lgd_downturn"] == pytest.approx((0.55 + 0.50) / 2)
    assert out["mean_lgd_non_downturn"] == pytest.approx((0.30 + 0.32 + 0.28) / 3)
    assert out["downturn_minus_non_downturn"] > 0


def test_compute_downturn_lgd_missing_columns():
    obs = pd.DataFrame({"p": ["a"], "lgd": [0.3]})
    flags = pd.DataFrame({"period": ["a"], "is_downturn": [True]})
    with pytest.raises(ValueError):
        dl.compute_downturn_lgd(obs, "period", "lgd", flags)


def test_compute_downturn_lgd_unmatched_periods_counted():
    obs = pd.DataFrame({"period": ["x", "y"], "realized_lgd": [0.3, 0.5]})
    flags = pd.DataFrame({"period": ["x"], "is_downturn": [True]})
    out = dl.compute_downturn_lgd(obs, "period", "realized_lgd", flags)
    assert out["n_unmatched_periods"] == 1
