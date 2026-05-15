"""LGD / EAD metric accuracy on constructed datasets."""
import numpy as np
import pandas as pd
import pytest

from tests.sectors import fixtures as fx
from tools import metric_lgd_ead as mle


def test_mae_matches_constant_error():
    realized, predicted = fx.lgd_constant_error(n=200, true_lgd=0.5,
                                                pred_lgd=0.55, seed=31)
    expected_mae = 0.05
    assert mle.calculate_mae(realized, predicted) == pytest.approx(expected_mae, abs=1e-3)


def test_rmse_matches_constant_error():
    realized, predicted = fx.lgd_constant_error(n=200, true_lgd=0.5,
                                                pred_lgd=0.55, seed=32)
    assert mle.calculate_rmse(realized, predicted) == pytest.approx(0.05, abs=1e-3)


def test_bias_sign_consistent():
    """Predicted - actual = positive when predictions are too high."""
    realized, predicted = fx.lgd_constant_error(true_lgd=0.5, pred_lgd=0.6, seed=33)
    bias = mle.calculate_bias(realized, predicted)
    assert bias == pytest.approx(0.10, abs=1e-3)


def test_segment_summary_identifies_systematic_over_prediction():
    df = fx.lgd_segmented(seed=34)
    out = mle.summarize_error_by_segment(df, "actual", "predicted", "segment")
    by = {row["segment"]: row for _, row in out.iterrows()}
    # B was constructed with a +0.1 systematic over-prediction
    assert by["B"]["bias"] == pytest.approx(0.10, abs=0.03)
    # A has near-zero bias
    assert abs(by["A"]["bias"]) < 0.05


def test_lgd_range_validation_flags_out_of_range():
    out = mle.validate_lgd_range([-0.1, 0.5, 1.2, 0.7])
    assert out["n_negative"] == 1
    assert out["n_above_one"] == 1
    assert out["n_in_unit_range"] == 2


def test_ead_validation_detects_negatives():
    out = mle.validate_ead_values([-1.0, 0.0, 100.0])
    assert out["n_negative"] == 1
    assert out["n"] == 3
