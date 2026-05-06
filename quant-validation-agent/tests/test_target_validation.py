import pytest

from tools import target_validation as tv


def test_binary_target_accepts_zero_one():
    arr = tv.validate_binary_target([0, 1, 1, 0])
    assert arr.tolist() == [0, 1, 1, 0]


def test_binary_target_rejects_non_binary():
    with pytest.raises(ValueError):
        tv.validate_binary_target([0, 1, 2])


def test_binary_target_rejects_nan():
    with pytest.raises(ValueError):
        tv.validate_binary_target([0, 1, float("nan")])


def test_probability_values_in_range():
    arr = tv.validate_probability_values([0.0, 0.5, 1.0])
    assert arr.tolist() == [0.0, 0.5, 1.0]


def test_probability_values_rejects_out_of_range():
    with pytest.raises(ValueError):
        tv.validate_probability_values([0.0, 1.2])
    with pytest.raises(ValueError):
        tv.validate_probability_values([-0.1, 0.5])


def test_infer_score_direction_higher_is_worse():
    y = [0, 0, 0, 1, 1, 1]
    s = [10, 20, 30, 80, 90, 95]
    out = tv.infer_score_direction(y, s)
    assert out["higher_is_worse"] is True


def test_check_default_rate():
    out = tv.check_default_rate([0, 0, 1, 1, 1])
    assert out["n"] == 5
    assert out["defaults"] == 3
    assert abs(out["default_rate"] - 0.6) < 1e-9
