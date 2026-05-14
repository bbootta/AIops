import numpy as np
import pandas as pd
import pytest

from tools import binning_stability as bs


def test_check_rank_ordering_monotonic():
    df = pd.DataFrame({"grade": ["A", "B", "C"], "bad_rate": [0.01, 0.05, 0.20]})
    out = bs.check_rank_ordering(df, "grade", "bad_rate")
    assert out["monotonic_increasing"] is True
    assert out["monotonic_decreasing"] is False


def test_detect_grade_inversion_finds_violation():
    df = pd.DataFrame({"grade": ["A", "B", "C"], "bad_rate": [0.10, 0.05, 0.20]})
    rows = bs.detect_grade_inversion(df, "grade", "bad_rate", ascending=True)
    assert len(rows) == 1
    assert rows.iloc[0]["from_grade"] == "A"


def test_detect_grade_inversion_handles_pd_na():
    """pandas nullable dtypes (Int64/Float64) with pd.NA must be handled."""
    df = pd.DataFrame({
        "grade": ["A", "B", "C", "D"],
        "bad_rate": pd.array([0.01, pd.NA, 0.05, 0.20], dtype="Float64"),
    })
    rows = bs.detect_grade_inversion(df, "grade", "bad_rate", ascending=True)
    # B is dropped; remaining series A=0.01, C=0.05, D=0.20 is monotonic.
    assert len(rows) == 0


def test_detect_grade_inversion_nullable_int_metric():
    df = pd.DataFrame({
        "grade": ["A", "B", "C"],
        "rank": pd.array([1, pd.NA, 3], dtype="Int64"),
    })
    rows = bs.detect_grade_inversion(df, "grade", "rank", ascending=True)
    assert isinstance(rows, pd.DataFrame)


def test_compare_grade_distribution_basic():
    a = pd.DataFrame({"grade": ["A", "A", "B", "B", "C"]})
    b = pd.DataFrame({"grade": ["A", "B", "B", "B", "C"]})
    out = bs.compare_grade_distribution(a, b, "grade")
    assert {"grade", "base_count", "cur_count", "ratio_diff",
            "psi_contribution"}.issubset(out.columns)


def test_compare_grade_distribution_per_grade_psi_finite():
    a = pd.DataFrame({"grade": ["A"] * 70 + ["B"] * 20 + ["C"] * 10})
    b = pd.DataFrame({"grade": ["A"] * 50 + ["B"] * 30 + ["C"] * 20})
    out = bs.compare_grade_distribution(a, b, "grade")
    total = float(out["psi_contribution"].sum())
    assert total > 0 and np.isfinite(total)
