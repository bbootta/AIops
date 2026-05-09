import pandas as pd
import pytest

from tools import markdown_renderers as mr


def test_render_dataframe_markdown_basic():
    df = pd.DataFrame({"a": [1, 2], "b": [3.14159, 2.71828]})
    out = mr.render_dataframe_markdown(df, decimals=2, aligns={"b": "right"})
    assert "| a | b |" in out
    assert "---:" in out
    assert "3.14" in out


def test_render_dataframe_markdown_empty():
    out = mr.render_dataframe_markdown(pd.DataFrame())
    assert "(empty)" in out


def test_render_dataframe_markdown_missing_columns():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError):
        mr.render_dataframe_markdown(df, columns=["a", "b"])


def test_render_metrics_table_with_thresholds():
    metrics = {
        "ks": {"value": 0.42, "rag": "Green", "green_threshold": 0.4, "yellow_threshold": 0.3, "source": "global"},
        "psi": {"value": None, "rag": "Gray"},
    }
    out = mr.render_metrics_table(metrics, decimals=3)
    assert "ks" in out and "0.420" in out
    assert "Green" in out
    assert "Gray" in out


def test_render_metrics_table_empty():
    out = mr.render_metrics_table({})
    assert "(없음)" in out


def test_render_issue_table_with_and_without():
    out_empty = mr.render_issue_table([])
    assert "(없음)" in out_empty
    out = mr.render_issue_table([{"issue": "A", "severity": "Yellow", "evidence": "n=10"}])
    assert "Yellow" in out and "n=10" in out


def test_render_regression_summary_combines_blocks():
    summary = {"n": 100, "k": 3, "r_squared": 0.91, "adj_r_squared": 0.90, "f_pvalue": 0.0001}
    pvals = [{"variable": "x1", "pvalue": 0.01, "significant_at_threshold": True, "threshold": 0.05}]
    vif = [{"variable": "x1", "vif": 1.5}]
    out = mr.render_regression_summary(summary, pvals, vif)
    assert "R²" in out
    assert "p-values" in out and "0.0100" in out
    assert "VIF" in out and "1.5000" in out


def test_render_calibration_table_rejects_missing_columns():
    bad = pd.DataFrame({"count": [10], "mean_pred": [0.1]})
    with pytest.raises(ValueError):
        mr.render_calibration_table(bad)
