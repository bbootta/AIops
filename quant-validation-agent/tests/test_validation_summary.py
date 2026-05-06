import pandas as pd
import pytest

from tools import validation_summary as vs


def test_higher_is_better():
    assert vs.assign_rag_status(0.8, 0.7, 0.5, "higher_is_better") == "Green"
    assert vs.assign_rag_status(0.6, 0.7, 0.5, "higher_is_better") == "Yellow"
    assert vs.assign_rag_status(0.3, 0.7, 0.5, "higher_is_better") == "Red"


def test_lower_is_better():
    assert vs.assign_rag_status(0.05, 0.10, 0.25, "lower_is_better") == "Green"
    assert vs.assign_rag_status(0.20, 0.10, 0.25, "lower_is_better") == "Yellow"
    assert vs.assign_rag_status(0.30, 0.10, 0.25, "lower_is_better") == "Red"


def test_abs_lower_is_better_positive_and_negative():
    # PD bias style — both over- and under-prediction count
    assert vs.assign_rag_status(0.005, 0.01, 0.03, "abs_lower_is_better") == "Green"
    assert vs.assign_rag_status(-0.005, 0.01, 0.03, "abs_lower_is_better") == "Green"
    assert vs.assign_rag_status(0.02, 0.01, 0.03, "abs_lower_is_better") == "Yellow"
    assert vs.assign_rag_status(-0.02, 0.01, 0.03, "abs_lower_is_better") == "Yellow"
    assert vs.assign_rag_status(0.05, 0.01, 0.03, "abs_lower_is_better") == "Red"
    assert vs.assign_rag_status(-0.05, 0.01, 0.03, "abs_lower_is_better") == "Red"


def test_abs_lower_is_better_negative_threshold_rejected():
    with pytest.raises(ValueError):
        vs.assign_rag_status(0.0, -0.01, 0.03, "abs_lower_is_better")


def test_invalid_direction_raises():
    with pytest.raises(ValueError):
        vs.assign_rag_status(0.5, 0.5, 0.3, "diagonal")


def test_gray_when_thresholds_missing():
    assert vs.assign_rag_status(0.5, None, None, "higher_is_better") == "Gray"
    assert vs.assign_rag_status(None, 0.5, 0.3, "higher_is_better") == "Gray"


def test_build_metric_summary_and_issue_table_and_commentary():
    summary = vs.build_metric_summary({"KS": 0.42, "AUROC": 0.78})
    issues = vs.build_issue_table(
        [
            {"issue": "표본 부족", "severity": "Yellow", "evidence": "n=300"},
        ]
    )
    text = vs.build_validation_commentary(summary, issues)
    assert "단정 금지" in text
    assert "Yellow 1" in text or "Yellow" in text