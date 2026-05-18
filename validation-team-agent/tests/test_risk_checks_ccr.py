import pytest

from tools.risk_checks import ccr


def test_supervisory_factor_known_classes():
    assert ccr.lookup_supervisory_factor("interest_rate") == pytest.approx(0.005)
    assert ccr.lookup_supervisory_factor("fx") == pytest.approx(0.04)
    assert ccr.lookup_supervisory_factor("equity_single") == pytest.approx(0.32)


def test_supervisory_factor_unknown_raises():
    with pytest.raises(KeyError):
        ccr.lookup_supervisory_factor("crypto")


def test_pfe_multiplier_in_range():
    assert ccr.check_pfe_multiplier(0.5)["passed"] is True
    assert ccr.check_pfe_multiplier(1.0)["passed"] is True
    assert ccr.check_pfe_multiplier(0.04)["passed"] is False
    assert ccr.check_pfe_multiplier(1.5)["passed"] is False


def test_ead_uses_default_alpha_1_4():
    out = ccr.compute_ead(replacement_cost=100, pfe=50)
    assert out["alpha"] == 1.4
    assert out["ead"] == pytest.approx(1.4 * 150)


def test_ead_alpha_override_blocked_below_one():
    with pytest.raises(ValueError):
        ccr.compute_ead(replacement_cost=100, pfe=50, alpha=0.9)


def test_ead_alpha_override_allowed_above_one():
    out = ccr.compute_ead(replacement_cost=100, pfe=50, alpha=1.2)
    assert out["ead"] == pytest.approx(1.2 * 150)


def test_ead_rejects_negative_inputs():
    with pytest.raises(ValueError):
        ccr.compute_ead(replacement_cost=-1, pfe=0)
    with pytest.raises(ValueError):
        ccr.compute_ead(replacement_cost=0, pfe=-1)
