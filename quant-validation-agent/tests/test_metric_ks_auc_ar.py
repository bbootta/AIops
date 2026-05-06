import numpy as np
import pytest

from tools import metric_ks_auc_ar as m


def _make_data():
    rng = np.random.default_rng(42)
    n = 500
    y = rng.binomial(1, 0.3, size=n)
    score = rng.normal(0, 1, size=n) + y * 1.2  # higher score => higher default
    return y, score


def test_ks_in_range():
    y, s = _make_data()
    ks = m.calculate_ks(y, s, higher_is_worse=True)
    assert 0.0 <= ks <= 1.0
    assert ks > 0.2  # non-trivial separation


def test_auc_in_range():
    y, s = _make_data()
    auc = m.calculate_auc(y, s, higher_is_worse=True)
    assert 0.5 <= auc <= 1.0
    assert auc > 0.6


def test_gini_equals_two_auc_minus_one():
    y, s = _make_data()
    auc = m.calculate_auc(y, s, higher_is_worse=True)
    gini = m.calculate_gini(y, s, higher_is_worse=True)
    assert abs(gini - (2 * auc - 1)) < 1e-9


def test_direction_consistency_via_negation():
    y, s = _make_data()
    auc_high = m.calculate_auc(y, s, higher_is_worse=True)
    auc_low = m.calculate_auc(y, [-x for x in s], higher_is_worse=True)
    # Flipping sign should flip AUC around 0.5
    assert abs((auc_high - 0.5) + (auc_low - 0.5)) < 1e-6


def test_direction_flag_changes_result():
    y, s = _make_data()
    auc_a = m.calculate_auc(y, s, higher_is_worse=True)
    auc_b = m.calculate_auc(y, s, higher_is_worse=False)
    assert abs(auc_a + auc_b - 1.0) < 1e-9


def test_decile_table_shape():
    y, s = _make_data()
    tbl = m.build_decile_table(y, s, n_bins=10, higher_is_worse=True)
    assert len(tbl) <= 10
    assert {"count", "defaults", "default_rate"}.issubset(tbl.columns)
    # Worst bin should have higher default rate than best bin
    assert tbl["default_rate"].iloc[-1] >= tbl["default_rate"].iloc[0]


def test_auc_requires_two_classes():
    with pytest.raises(ValueError):
        m.calculate_auc([1, 1, 1], [0.1, 0.2, 0.3])
