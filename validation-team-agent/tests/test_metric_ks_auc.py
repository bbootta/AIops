import numpy as np
import pytest

from tools import metric_ks_auc as m


def _well_separated():
    rng = np.random.default_rng(0)
    good = rng.normal(loc=0.0, scale=1.0, size=500)
    bad = rng.normal(loc=2.0, scale=1.0, size=500)
    score = np.concatenate([good, bad])
    y = np.concatenate([np.zeros(500), np.ones(500)]).astype(int)
    return y, score


def test_ks_in_unit_range_for_separable_data():
    y, s = _well_separated()
    out = m.calculate_ks(y, s)
    assert 0.0 <= out["ks"] <= 1.0
    assert out["ks"] > 0.4
    assert out["n"] == 1000
    assert out["n_bad"] == 500
    assert out["n_good"] == 500


def test_auc_gini_consistency():
    y, s = _well_separated()
    out = m.calculate_auc_gini(y, s)
    assert 0.5 < out["auc"] <= 1.0
    assert out["gini"] == pytest.approx(2 * out["auc"] - 1, rel=1e-9)


def test_validate_binary_target_rejects_nonbinary():
    with pytest.raises(ValueError):
        m.validate_binary_target([0, 1, 2])


def test_validate_binary_target_rejects_single_class():
    with pytest.raises(ValueError):
        m.validate_binary_target([0, 0, 0])


def test_ks_rejects_length_mismatch():
    with pytest.raises(ValueError):
        m.calculate_ks([0, 1, 0], [0.1, 0.2])


def test_ks_rejects_nan_score():
    with pytest.raises(ValueError):
        m.calculate_ks([0, 1, 0, 1], [0.1, np.nan, 0.3, 0.4])
