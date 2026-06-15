"""leakage_guard 의 name-pattern detector 기본 검증."""

from __future__ import annotations

from middleware import leakage_guard as lg


def test_target_name_as_feature_blocked():
    out = lg.check_leakage(["x", "y", "target"], target_name="target")
    assert out["passed"] is False
    assert any(item["feature"] == "target" for item in out["leaked"])


def test_default_pattern_caught():
    out = lg.check_leakage(["x", "default_flag"], target_name="target")
    assert out["passed"] is False
    assert any(item["feature"] == "default_flag" for item in out["leaked"])


def test_clean_features_pass():
    out = lg.check_leakage(["age", "income", "score"], target_name="target")
    assert out["passed"] is True
    assert out["leaked"] == []


def test_post_suffix_caught():
    out = lg.check_leakage(["balance_after"], target_name="target")
    assert out["passed"] is False
    assert any("after" in item["reason"] for item in out["leaked"])


def test_extra_forbidden_used():
    out = lg.check_leakage(
        ["recovery_amount"],
        target_name="target",
        extra_forbidden=[r"^recovery_"],
    )
    assert out["passed"] is False
    assert any(item["feature"] == "recovery_amount" for item in out["leaked"])
