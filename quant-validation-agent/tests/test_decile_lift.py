import numpy as np
import pytest

from tools import decile_lift as dl
from tools.metric_ks_auc_ar import calculate_ks


def _separable(seed=0, n=600):
    rng = np.random.default_rng(seed)
    y = rng.binomial(1, 0.3, size=n)
    s = rng.normal(0, 1, size=n) + y * 1.5  # higher score => higher risk
    return y, s


def test_lift_table_structure():
    y, s = _separable()
    out = dl.build_lift_table(y, s, n_bins=10, higher_is_worse=True)
    assert {"count", "defaults", "lift", "cum_default_share", "cum_pop_share"}.issubset(out.columns)
    assert out.shape[0] <= 10


def test_lift_table_first_bucket_has_higher_lift():
    y, s = _separable()
    out = dl.build_lift_table(y, s, n_bins=10, higher_is_worse=True)
    assert out["lift"].iloc[0] > 1.0
    assert out["bucket_default_rate"].iloc[0] >= out["bucket_default_rate"].iloc[-1]


def test_lift_table_total_shares_close_to_one():
    y, s = _separable()
    out = dl.build_lift_table(y, s, n_bins=10, higher_is_worse=True)
    assert abs(float(out["cum_pop_share"].iloc[-1]) - 1.0) < 1e-9
    assert abs(float(out["cum_default_share"].iloc[-1]) - 1.0) < 1e-9


def test_ks_plot_coordinates_match_ks_value():
    y, s = _separable()
    coords = dl.ks_plot_coordinates(y, s, higher_is_worse=True)
    ks_from_plot = float(coords["ks_distance"].max())
    ks_from_metric = calculate_ks(y, s, higher_is_worse=True)
    assert abs(ks_from_plot - ks_from_metric) < 1e-9


def test_ks_plot_endpoints():
    y, s = _separable()
    coords = dl.ks_plot_coordinates(y, s, higher_is_worse=True)
    assert abs(float(coords["cum_bad"].iloc[-1]) - 1.0) < 1e-9
    assert abs(float(coords["cum_good"].iloc[-1]) - 1.0) < 1e-9


def test_invalid_bins_rejected():
    with pytest.raises(ValueError):
        dl.build_lift_table([0, 1], [0.1, 0.2], n_bins=1)


def test_format_lift_markdown_basic():
    y, s = _separable()
    lift = dl.build_lift_table(y, s, n_bins=5, higher_is_worse=True)
    md = dl.format_lift_markdown(lift, decimals=3)
    # Must include header with all columns and correct number of data rows
    assert "| bin | count | defaults" in md
    data_rows = [ln for ln in md.strip().splitlines()[2:]]
    assert len(data_rows) == lift.shape[0]


def test_format_lift_markdown_empty_returns_placeholder():
    import pandas as pd

    md = dl.format_lift_markdown(pd.DataFrame())
    assert "(empty)" in md


def test_format_lift_markdown_missing_columns_raises():
    import pandas as pd

    bad = pd.DataFrame({"bin": [0, 1], "count": [10, 20]})
    with pytest.raises(ValueError):
        dl.format_lift_markdown(bad)
