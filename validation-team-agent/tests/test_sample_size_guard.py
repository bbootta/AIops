"""sample_size_guard 임계 검증 (threshold 별 1 케이스 이상)."""

from __future__ import annotations

import pytest

from middleware import sample_size_guard as ssg


def test_min_total_violation():
    out = ssg.check_sample_size(total=500, default_count=60)
    assert out["total_ok"] is False
    assert any(v["type"] == "total" for v in out["violations"])
    assert out["passed"] is False


def test_min_defaults_violation():
    out = ssg.check_sample_size(total=2000, default_count=10)
    assert out["defaults_ok"] is False
    assert any(v["type"] == "defaults" for v in out["violations"])
    assert out["passed"] is False


def test_min_per_grade_violation():
    out = ssg.check_sample_size(
        total=2000,
        default_count=60,
        per_grade_counts={"A": 100, "B": 5},
    )
    assert out["per_grade_ok"] is False
    violations = [v for v in out["violations"] if v["type"] == "per_grade"]
    assert any(v["grade"] == "B" for v in violations)
    assert out["passed"] is False


def test_all_pass():
    out = ssg.check_sample_size(
        total=2000,
        default_count=60,
        per_grade_counts={"A": 100, "B": 100, "C": 100},
    )
    assert out["passed"] is True
    assert out["violations"] == []


def test_negative_inputs_raise():
    with pytest.raises(ValueError):
        ssg.check_sample_size(total=-1, default_count=0)
    with pytest.raises(ValueError):
        ssg.check_sample_size(total=10, default_count=-1)
    with pytest.raises(ValueError):
        ssg.check_sample_size(total=10, default_count=20)


def test_custom_thresholds_apply():
    out = ssg.check_sample_size(
        total=100,
        default_count=10,
        thresholds={"min_total": 50, "min_defaults": 5},
    )
    assert out["passed"] is True
