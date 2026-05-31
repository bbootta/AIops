import pytest

from tools import handlers as h
from tools.sample_generators import credit_scoring_sample
from tools.workflow import WorkflowContext, WorkflowEngine


def _req(df, **extra):
    base = {
        "df": df,
        "score_col": "score",
        "target_col": "target",
        "set_col": "set",
        "grade_col": "grade",
        "pd_col": "pd",
    }
    base.update(extra)
    return base


def test_credit_discrimination_handler_returns_metrics():
    df = credit_scoring_sample(n=2000, seed=1)
    ctx = WorkflowContext(request={})
    res = h.credit_discrimination_handler(_req(df), ctx)
    assert res.status in {"ok", "warning"}
    assert "ks" in res.outputs and "auc" in res.outputs


def test_credit_psi_handler_detects_drift():
    df_calm = credit_scoring_sample(n=2000, seed=2, psi_shift=0.0)
    df_drift = credit_scoring_sample(n=2000, seed=2, psi_shift=1.0)
    ctx = WorkflowContext(request={})
    calm = h.credit_psi_handler(_req(df_calm), ctx)
    drift = h.credit_psi_handler(_req(df_drift), ctx)
    assert drift.outputs["psi"] > calm.outputs["psi"]


def test_psi_handler_skipped_without_set_col():
    df = credit_scoring_sample(n=500, seed=3)
    ctx = WorkflowContext(request={})
    res = h.credit_psi_handler(_req(df, set_col=None), ctx)
    assert res.status == "skipped"


def test_calibration_handler_runs_on_synthetic():
    df = credit_scoring_sample(n=3000, seed=4)
    ctx = WorkflowContext(request={})
    res = h.credit_calibration_handler(_req(df), ctx)
    assert res.status in {"ok", "warning"}
    assert "n_grades" in res.outputs


def test_sample_size_handler_passes_for_10k_sample():
    df = credit_scoring_sample(n=10_000, seed=5)
    ctx = WorkflowContext(request={})
    res = h.sample_size_handler(_req(df), ctx)
    assert res.outputs["passed"] is True


def test_capital_handler_passes_for_healthy_input():
    ctx = WorkflowContext(request={})
    res = h.capital_handler(
        {"capital_cet1": 0.13, "capital_tier1": 0.135, "capital_total": 0.143,
         "capital_leverage": 0.06}, ctx,
    )
    assert res.status == "ok"


def test_capital_handler_fails_for_stress_input():
    ctx = WorkflowContext(request={})
    res = h.capital_handler(
        {"capital_cet1": 0.03, "capital_tier1": 0.04, "capital_total": 0.05,
         "capital_leverage": 0.02}, ctx,
    )
    assert res.status == "fail"


def test_liquidity_handler_below_min():
    ctx = WorkflowContext(request={})
    res = h.liquidity_handler(
        {"liquidity_hqla": 80, "liquidity_outflow": 100}, ctx,
    )
    assert res.outputs["lcr"]["status"] == "below_min"
    assert res.status == "fail"


def test_market_handler_red_zone():
    ctx = WorkflowContext(request={})
    res = h.market_handler({"market_var_exceptions": 12}, ctx)
    assert res.outputs["zone"] == "red"
    assert res.status == "fail"


def test_irrbb_handler_outlier_detected():
    ctx = WorkflowContext(request={})
    res = h.irrbb_handler(
        {
            "irrbb_delta_eve_by_scenario": {"parallel_up": -3_000_000,
                                            "parallel_down": 0},
            "irrbb_tier1": 10_000_000,
        },
        ctx,
    )
    assert res.outputs["outlier"] is True
    assert res.status == "fail"


def test_register_default_handlers_attaches_to_known_ids():
    eng = WorkflowEngine()
    registered = h.register_default_handlers(eng)
    # 매트릭스에 존재하는 step 들만 등록되었는지
    assert "3.disc" in registered and "9.escalate" in registered
    # 모두 매트릭스 step 이어야
    for sid in registered:
        assert sid in eng.steps_by_id
