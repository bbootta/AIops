import pandas as pd
import pytest

from tools import binomial_calibration as bc


def test_wilson_interval_ranges():
    lo, hi = bc.wilson_interval(50, 1000, alpha=0.05)
    assert 0.0 <= lo <= 0.05 <= hi <= 1.0
    assert hi > lo


def test_wilson_interval_zero_default_count():
    lo, hi = bc.wilson_interval(0, 100)
    assert lo == 0.0
    assert hi > 0.0


def test_wilson_interval_rejects_invalid():
    with pytest.raises(ValueError):
        bc.wilson_interval(10, 0)
    with pytest.raises(ValueError):
        bc.wilson_interval(-1, 100)
    with pytest.raises(ValueError):
        bc.wilson_interval(101, 100)


def test_calibration_table_shape_and_keys():
    grades = [
        {"grade": "A", "pd_estimated": 0.01, "default_count": 10, "exposure_count": 1000},
        {"grade": "B", "pd_estimated": 0.05, "default_count": 200, "exposure_count": 1000},
        {"grade": "C", "pd_estimated": 0.10, "default_count": 110, "exposure_count": 1000},
    ]
    out = bc.calibration_test_per_grade(grades, alpha=0.05, multitest="holm")
    assert isinstance(out, pd.DataFrame)
    assert {
        "grade",
        "pd_estimated",
        "observed_rate",
        "default_count",
        "exposure_count",
        "ci_lower",
        "ci_upper",
        "p_value",
        "p_value_adj",
        "reject",
    } <= set(out.columns)
    # B 등급은 명백히 캘리브레이션 어긋남(예측 5% vs 실측 20%)
    row_b = out.set_index("grade").loc["B"]
    assert row_b["reject"] is True or bool(row_b["reject"]) is True


def test_calibration_holm_more_conservative_than_none():
    grades = [
        {"grade": "A", "pd_estimated": 0.01, "default_count": 11, "exposure_count": 1000},
        {"grade": "B", "pd_estimated": 0.05, "default_count": 60, "exposure_count": 1000},
    ]
    holm = bc.calibration_test_per_grade(grades, multitest="holm")
    none = bc.calibration_test_per_grade(grades, multitest="none")
    assert (holm["p_value_adj"] >= none["p_value_adj"] - 1e-12).all()


def test_calibration_rejects_missing_keys():
    with pytest.raises(KeyError):
        bc.calibration_test_per_grade([{"grade": "A", "pd_estimated": 0.01}])
