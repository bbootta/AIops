import os

import pytest

from tools import threshold_loader as tl


def test_load_default_policy():
    policy = tl.load_threshold_policy()
    assert "metrics" in policy
    assert "policy_version" in policy


def test_get_metric_threshold_known():
    policy = tl.load_threshold_policy()
    out = tl.get_metric_threshold(policy, "ks")
    assert out["direction"] == "higher_is_better"
    assert out["green_threshold"] == 0.40
    assert out["yellow_threshold"] == 0.30


def test_get_metric_threshold_pd_bias_uses_abs():
    policy = tl.load_threshold_policy()
    out = tl.get_metric_threshold(policy, "pd_bias")
    assert out["direction"] == "abs_lower_is_better"


def test_get_metric_threshold_unknown_raises():
    policy = tl.load_threshold_policy()
    with pytest.raises(KeyError):
        tl.get_metric_threshold(policy, "definitely_not_a_metric")


def test_list_metrics_for_model_scoring():
    policy = tl.load_threshold_policy()
    metrics = tl.list_metrics_for_model(policy, "scoring")
    assert {"ks", "auroc", "ar", "psi"}.issubset(set(metrics))


def test_list_metrics_for_model_lgd():
    policy = tl.load_threshold_policy()
    metrics = tl.list_metrics_for_model(policy, "lgd")
    assert "mae_lgd" in metrics


def test_load_missing_file_raises(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        tl.load_threshold_policy(str(missing))
