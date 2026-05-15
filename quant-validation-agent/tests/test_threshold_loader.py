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
    assert out["source"] == "global"


def test_segment_override_replaces_values_only():
    policy = tl.load_threshold_policy()
    out = tl.get_metric_threshold(policy, "ks", segment="ldp_corporate")
    assert out["direction"] == "higher_is_better"
    assert out["green_threshold"] == 0.25
    assert out["yellow_threshold"] == 0.15
    assert out["source"] == "segment:ldp_corporate"


def test_segment_without_override_falls_back_to_global():
    policy = tl.load_threshold_policy()
    # 'retail' segment exists but does not override 'psi'
    out = tl.get_metric_threshold(policy, "psi", segment="retail")
    assert out["green_threshold"] == 0.10
    assert out["source"] == "global"


def test_unknown_segment_falls_back_to_global():
    policy = tl.load_threshold_policy()
    out = tl.get_metric_threshold(policy, "ks", segment="not_a_real_segment")
    assert out["green_threshold"] == 0.40
    assert out["source"] == "global"


def test_list_segments_includes_known_segments():
    policy = tl.load_threshold_policy()
    segs = tl.list_segments(policy)
    assert {"retail", "sme", "ldp_corporate"}.issubset(set(segs))


def test_get_ead_metric_settings_consistent():
    policy = tl.load_threshold_policy()
    out = tl.get_ead_metric_settings(policy)
    assert out["normalizer"] in out["allowed_normalizers"]


def test_get_ead_metric_settings_invalid_rejected():
    bad_policy = {
        "ead_metric_settings": {
            "normalizer": "definitely_not_allowed",
            "allowed_normalizers": ["mean_realized"],
        }
    }
    with pytest.raises(ValueError):
        tl.get_ead_metric_settings(bad_policy)


def test_validate_policy_accepts_real_repo_policy():
    policy = tl.load_threshold_policy()
    tl.validate_policy(policy)


def test_validate_policy_rejects_bad_direction():
    bad = {
        "metrics": {
            "ks": {
                "direction": "diagonal",
                "green_threshold": 0.4,
                "yellow_threshold": 0.3,
            }
        }
    }
    with pytest.raises(ValueError):
        tl.validate_policy(bad)


def test_validate_policy_rejects_missing_threshold():
    bad = {
        "metrics": {
            "ks": {
                "direction": "higher_is_better",
                "green_threshold": 0.4
            }
        }
    }
    with pytest.raises(ValueError):
        tl.validate_policy(bad)


def test_validate_policy_rejects_unknown_top_level_key():
    bad = {
        "metrics": {},
        "totally_unrelated_block": {"x": 1},
    }
    with pytest.raises(ValueError):
        tl.validate_policy(bad)


def test_get_metric_threshold_returns_regulatory_basis():
    policy = tl.load_threshold_policy()
    out = tl.get_metric_threshold(policy, "ks")
    assert isinstance(out.get("regulatory_basis"), list)
    assert "basel_irb_pd" in out["regulatory_basis"]


def test_validate_policy_rejects_unknown_model_type():
    bad = {
        "metrics": {
            "ks": {
                "model_types": ["fictional_model_type"],
                "direction": "higher_is_better",
                "green_threshold": 0.4,
                "yellow_threshold": 0.3,
            }
        }
    }
    with pytest.raises(ValueError):
        tl.validate_policy(bad)


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
