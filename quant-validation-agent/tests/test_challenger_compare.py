import numpy as np
import pandas as pd
import pytest

from tools import challenger_compare as cc


def _make_paired(seed=3):
    rng = np.random.default_rng(seed)
    n = 400
    y = rng.binomial(1, 0.25, size=n)
    sc_champ = rng.normal(0, 1, size=n) + y * 0.8
    sc_chal = rng.normal(0, 1, size=n) + y * 1.2  # better separation
    return y, sc_champ, sc_chal


def test_check_same_sample_identical():
    a = pd.DataFrame({"id": [1, 2, 3]})
    b = pd.DataFrame({"id": [1, 2, 3]})
    out = cc.check_same_sample(a, b, "id")
    assert out["same_sample"] is True
    assert out["n_intersection"] == 3


def test_check_same_sample_different():
    a = pd.DataFrame({"id": [1, 2, 3]})
    b = pd.DataFrame({"id": [1, 2, 4]})
    out = cc.check_same_sample(a, b, "id")
    assert out["same_sample"] is False
    assert out["n_only_a"] == 1
    assert out["n_only_b"] == 1


def test_check_same_sample_missing_key_raises():
    a = pd.DataFrame({"id": [1]})
    b = pd.DataFrame({"x": [1]})
    with pytest.raises(ValueError):
        cc.check_same_sample(a, b, "id")


def test_compare_discrimination_returns_delta_row():
    y, sc_a, sc_b = _make_paired()
    df = cc.compare_discrimination(y, sc_a, sc_b, higher_is_worse=True)
    assert df.shape[0] == 3  # champion, challenger, delta
    assert "delta_challenger_minus_champion" in df["model"].values
    chal = df[df["model"] == "challenger"].iloc[0]
    champ = df[df["model"] == "champion"].iloc[0]
    # challenger has stronger signal in the synthetic setup
    assert chal["auroc"] > champ["auroc"]


def test_compare_discrimination_length_mismatch():
    with pytest.raises(ValueError):
        cc.compare_discrimination([0, 1], [0.1, 0.2], [0.1])


def test_compare_calibration_basic():
    rng = np.random.default_rng(0)
    n = 300
    pd_true = np.clip(rng.beta(2, 8, size=n), 1e-3, 1 - 1e-3)
    y = (rng.uniform(0, 1, size=n) < pd_true).astype(int)
    pd_champ = np.clip(pd_true + rng.normal(0, 0.02, size=n), 1e-4, 1 - 1e-4)
    pd_chal = np.clip(pd_true + rng.normal(0, 0.05, size=n), 1e-4, 1 - 1e-4)
    df = cc.compare_calibration(y, pd_champ, pd_chal)
    assert df.shape[0] == 3
    assert {"brier", "abs_bias"}.issubset(df.columns)
