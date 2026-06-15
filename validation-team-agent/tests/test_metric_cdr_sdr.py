"""CDR / SDR(Survival Rate) edge case sanity tests."""

from __future__ import annotations

import pytest

from tools import metric_cdr_sdr as m


def test_all_survival():
    # 100 명 중 0 명 부도.
    assert m.calculate_cdr(0, 100) == 0.0
    assert m.calculate_survival_rate(100, 100) == 1.0
    # alias 도 동일.
    assert m.calculate_sdr(100, 100) == 1.0


def test_all_default():
    assert m.calculate_cdr(100, 100) == 1.0
    assert m.calculate_survival_rate(0, 100) == 0.0
    assert m.calculate_sdr(0, 100) == 0.0


def test_mixed():
    assert m.calculate_cdr(25, 100) == pytest.approx(0.25)
    assert m.calculate_survival_rate(75, 100) == pytest.approx(0.75)


def test_compare_returns_consistent_sdr():
    base = {"default_count": 10, "exposure_count": 100}
    current = {"default_count": 20, "exposure_count": 100}
    out = m.compare_cdr_sdr(base, current)
    assert out["base_cdr"] == pytest.approx(0.10)
    assert out["current_cdr"] == pytest.approx(0.20)
    assert out["delta_cdr"] == pytest.approx(0.10)
    # base_sdr 는 survival rate = 1 - CDR.
    assert out["base_sdr"] == pytest.approx(0.90)
    assert out["current_sdr"] == pytest.approx(0.80)
    assert out["delta_sdr"] == pytest.approx(-0.10)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        m.calculate_cdr(0, 0)
    with pytest.raises(ValueError):
        m.calculate_cdr(-1, 10)
    with pytest.raises(ValueError):
        m.calculate_cdr(11, 10)
    with pytest.raises(ValueError):
        m.calculate_survival_rate(11, 10)
    with pytest.raises(KeyError):
        m.compare_cdr_sdr({"default_count": 0}, {"default_count": 0, "exposure_count": 10})
