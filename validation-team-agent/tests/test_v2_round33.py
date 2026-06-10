"""Round 33 — Q5-3: 신용집중리스크 부문 (LEX + 은행법 35조 + HHI)."""

from __future__ import annotations

import pytest

from tools.risk_checks.concentration import (
    check_concentration,
    herfindahl,
    load_thresholds,
)


def _exp(cp, amount, group=None):
    return {"counterparty_id": cp, "exposure": amount, "group_id": group}


# ---------- herfindahl ----------

def test_hhi_single_exposure_is_one():
    assert herfindahl([100.0]) == 1.0


def test_hhi_uniform_portfolio():
    assert herfindahl([10.0] * 10) == pytest.approx(0.1)


def test_hhi_empty_and_nonpositive():
    assert herfindahl([]) == 0.0
    assert herfindahl([0.0, -5.0]) == 0.0


# ---------- check_concentration ----------

def test_clean_portfolio_passes():
    exposures = [_exp(f"CP{i}", 100.0) for i in range(20)]  # 각 1% of tier1
    out = check_concentration(exposures, 10_000.0)
    assert out["passed"] is True
    assert out["large_exposures"] == []
    assert out["limit_breaches"] == []
    assert out["hhi_band"] == "low"


def test_large_exposure_reported_but_not_breach():
    # 15% of Tier1 → 보고 대상 (>10%), 한도 (25%) 이내
    exposures = [_exp("BIG", 1_500.0)] + [_exp(f"CP{i}", 100.0) for i in range(10)]
    out = check_concentration(exposures, 10_000.0)
    assert len(out["large_exposures"]) == 1
    assert out["large_exposures"][0]["group"] == "BIG"
    assert out["passed"] is True


def test_single_counterparty_breach_fails():
    exposures = [_exp("HUGE", 3_000.0)]  # 30% > 25%
    out = check_concentration(exposures, 10_000.0)
    assert out["passed"] is False
    rules = {b["rule"] for b in out["limit_breaches"]}
    assert "LEX 25% Tier1" in rules


def test_group_aggregation_same_borrower():
    # 동일 group 으로 합산 시 한도 초과 (각각은 이내)
    exposures = [_exp("A1", 1_500.0, group="G1"), _exp("A2", 1_200.0, group="G1")]
    out = check_concentration(exposures, 10_000.0)
    assert out["n_groups"] == 1
    assert out["passed"] is False  # 합산 27% > 25%


def test_aggregate_large_exposure_multiple():
    # 거액 (>10%) 다수 → 합계가 자기자본 5배 초과
    exposures = [_exp(f"B{i}", 1_400.0) for i in range(40)]  # 각 14%, 합 56,000
    out = check_concentration(exposures, 10_000.0, equity=10_000.0)
    rules = {b["rule"] for b in out["limit_breaches"]}
    assert "거액신용공여 합계 ≤ 자기자본 5배" in rules


def test_invalid_tier1_raises():
    with pytest.raises(ValueError):
        check_concentration([_exp("A", 1.0)], 0.0)
    with pytest.raises(ValueError):
        check_concentration([_exp("A", 1.0)], float("nan"))


def test_thresholds_ssot_loaded():
    th = load_thresholds()
    assert th["single_counterparty_limit_pct_tier1"] == 0.25
    assert th["domestic"]["same_borrower_group_limit_pct_equity"] == 0.25
    assert th["domestic"]["large_exposure_aggregate_multiple_equity"] == 5.0


# ---------- handler / workflow 통합 ----------

def test_handler_skipped_without_inputs(tmp_path):
    from tools.handlers import concentration_handler
    from vta.core.workflow import WorkflowContext

    r = concentration_handler({}, WorkflowContext(request={}))
    assert r.status == "skipped"


def test_handler_fail_activates_escalation(tmp_path):
    from tools.handlers import register_default_handlers
    from tools.sample_generators import concentration_exposure_sample
    from vta.core.workflow import WorkflowEngine

    eng = WorkflowEngine()
    register_default_handlers(eng)
    req = concentration_exposure_sample(breach=True)
    run = eng.run(req, log_dir=tmp_path)
    assert run.context.results["3.conc"].status == "fail"
    assert "9.escalate" in run.executed_order


def test_handler_ok_on_clean_sample(tmp_path):
    from tools.handlers import register_default_handlers
    from tools.sample_generators import concentration_exposure_sample
    from vta.core.workflow import WorkflowEngine

    eng = WorkflowEngine()
    register_default_handlers(eng)
    run = eng.run(concentration_exposure_sample(breach=False), log_dir=tmp_path)
    assert run.context.results["3.conc"].status in {"ok", "warning"}
    assert "9.escalate" not in run.executed_order


def test_matrix_has_conc_step_and_taxonomy_bucket():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    m = json.loads((root / "harness/orchestration_matrix.json").read_text(encoding="utf-8"))
    step = next(s for s in m["steps"] if s["id"] == "3.conc")
    assert "9.escalate" in step["on_fail_activate"]
    report = next(s for s in m["steps"] if s["id"] == "4.report")
    assert "3.conc" in report["depends_on"]

    tax = json.loads((root / "harness/basel_risk_taxonomy.json").read_text(encoding="utf-8"))
    ids = [b["id"] for b in tax["risk_buckets"]]
    assert "concentration" in ids
