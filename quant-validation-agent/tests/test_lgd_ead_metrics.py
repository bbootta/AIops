import numpy as np
import pandas as pd
import pytest

from tools import metric_lgd_ead as m


def test_mae_rmse_bias():
    yt = [0.1, 0.2, 0.3]
    yp = [0.2, 0.2, 0.2]
    assert abs(m.calculate_mae(yt, yp) - (0.1 + 0 + 0.1) / 3) < 1e-9
    rmse = m.calculate_rmse(yt, yp)
    assert rmse > 0
    bias = m.calculate_bias(yt, yp)
    # bias = mean(pred - actual) = mean(0.1, 0.0, -0.1) = 0
    assert abs(bias - 0.0) < 1e-9


def test_lgd_range_validation_does_not_clip():
    out = m.validate_lgd_range([-0.1, 0.5, 1.2, 0.7, 1.0])
    assert out["n"] == 5
    assert out["n_negative"] == 1
    assert out["n_above_one"] == 1
    assert out["n_in_unit_range"] == 3


def test_ead_negative_detected():
    out = m.validate_ead_values([-100, 0, 200, 500])
    assert out["n_negative"] == 1
    assert out["n"] == 4


def test_summarize_error_by_segment():
    df = pd.DataFrame(
        {
            "segment": ["A", "A", "B", "B"],
            "actual": [0.1, 0.2, 0.5, 0.6],
            "pred": [0.15, 0.25, 0.4, 0.55],
        }
    )
    out = m.summarize_error_by_segment(df, "actual", "pred", "segment")
    assert set(out.columns) >= {"segment", "count", "mae", "rmse", "bias"}
    assert out.shape[0] == 2


def test_mae_length_mismatch():
    with pytest.raises(ValueError):
        m.calculate_mae([0.1, 0.2], [0.1])
