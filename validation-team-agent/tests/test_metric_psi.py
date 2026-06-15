import numpy as np
import pytest

from tools import metric_psi as psi


def test_psi_zero_for_same_distribution():
    rng = np.random.default_rng(1)
    x = rng.normal(size=2000)
    out = psi.calculate_psi(x, x, bins=10)
    assert out["psi"] < 1e-6
    assert out["n_expected"] == 2000
    assert out["n_actual"] == 2000


def test_psi_increases_with_drift():
    rng = np.random.default_rng(2)
    expected = rng.normal(loc=0, scale=1, size=2000)
    drifted = rng.normal(loc=1.5, scale=1, size=2000)
    out = psi.calculate_psi(expected, drifted, bins=10)
    assert out["psi"] > 0.25


def test_psi_no_zero_division_with_empty_bin():
    rng = np.random.default_rng(3)
    expected = rng.uniform(0, 1, size=1000)
    actual = rng.uniform(2, 3, size=1000)
    out = psi.calculate_psi(expected, actual, bins=10)
    assert np.isfinite(out["psi"])


def test_psi_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        psi.calculate_psi([], [1.0, 2.0])
    with pytest.raises(ValueError):
        psi.calculate_psi([1.0, 2.0], [1.0, 2.0], bins=1)
    with pytest.raises(ValueError):
        psi.calculate_psi([1.0, np.nan], [1.0, 2.0])


def test_psi_by_bucket_basic():
    expected = ["A", "A", "B", "B", "C"]
    actual = ["A", "B", "B", "C", "C"]
    out = psi.calculate_psi_by_bucket(expected, actual)
    assert out["categories"] == ["A", "B", "C"]
    assert out["n_expected"] == 5
    assert out["n_actual"] == 5
    assert np.isfinite(out["psi"])


def test_eps_floor_is_industry_standard():
    # 빈 bin floor 는 0.01% (=1e-4) — 더 작은 값은 단일 빈 bin 만으로 PSI > 1
    # false alarm 을 만든다 (모듈 docstring 참조).
    assert psi._EPS == 1e-4


def test_empty_bin_does_not_inflate_psi_above_one():
    # 시나리오: 두 bucket 분포에서 한 bucket 이 10% expected → 0% actual.
    # 이전 epsilon=1e-6 floor 에서는 단일 bin 만으로 PSI ≈ 1.15 false alarm.
    # 새 epsilon=1e-4 floor 에서는 PSI 가 1.0 미만으로 묶여야 한다.
    expected = ["A"] * 10 + ["B"] * 90  # 10% / 90%
    actual = ["B"] * 100  # 0% / 100%
    out = psi.calculate_psi_by_bucket(expected, actual)
    assert np.isfinite(out["psi"])
    # 핵심 조건: 빈 bin 한 개의 epsilon-기여만으로 PSI 가 1 을 넘어선 안 된다.
    assert out["psi"] < 1.0
    # 동시에, 분명한 drift 이므로 0.25 (보편적 high-drift 임계) 이상은 유지.
    assert out["psi"] > 0.25
