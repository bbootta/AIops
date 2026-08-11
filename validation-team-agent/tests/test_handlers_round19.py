"""Round 19: 마지막 7개 simulated step (1.req / 2.schema / 2.safety /
2.leakage / 2.date / 2.dup / 6.audit) handler 등록 확인."""

from tools import handlers as h
from tools.sample_generators import credit_scoring_sample
from tools.workflow import StepResult, WorkflowContext, WorkflowEngine


def _ctx():
    return WorkflowContext(request={})


# ---------- 1.req ----------

def test_request_reconstruction_basic():
    r = h.request_reconstruction_handler({"title": "T"}, _ctx())
    assert r.status == "ok"
    assert r.outputs["title"] == "T"
    assert r.outputs["domains"] == []


def test_request_reconstruction_detects_domains():
    df = credit_scoring_sample(n=200, seed=1)
    req = {
        "df": df, "score_col": "score", "target_col": "target",
        "capital_cet1": 0.13, "scenario_weight_panel": "X",
        "market_var_exceptions": 4,
    }
    domains = set(h.request_reconstruction_handler(req, _ctx()).outputs["domains"])
    assert {"credit", "capital", "ifrs9_weights", "market"} <= domains


# ---------- 2.schema ----------

def test_schema_handler_passes_for_valid_df():
    df = credit_scoring_sample(n=500, seed=2)
    r = h.schema_check_handler(
        {"df": df, "score_col": "score", "target_col": "target",
         "set_col": "set", "grade_col": "grade", "pd_col": "pd"},
        _ctx(),
    )
    assert r.status == "ok" and r.outputs["passed"] is True


def test_schema_handler_skip_without_df():
    assert h.schema_check_handler({}, _ctx()).status == "ok"


# ---------- 2.safety ----------

def test_safety_handler_clean_for_synthetic_data():
    df = credit_scoring_sample(n=500, seed=4)
    r = h.safety_check_handler({"df": df}, _ctx())
    assert r.status == "ok"
    assert r.outputs["clean"] is True


# ---------- 2.leakage ----------

def test_leakage_handler_passes_for_safe_features():
    r = h.leakage_check_handler(
        {"feature_names": ["score", "grade", "pd"], "target_col": "target"}, _ctx(),
    )
    assert r.status == "ok"


def test_leakage_handler_detects_target_in_features():
    r = h.leakage_check_handler(
        {"feature_names": ["score", "target", "grade"], "target_col": "target"}, _ctx(),
    )
    assert r.status == "fail"


# ---------- 2.date ----------

def test_date_handler_runs_for_continuous_panel():
    df = credit_scoring_sample(n=500, seed=5)
    r = h.date_coverage_handler({"df": df, "date_col": "obs_date"}, _ctx())
    assert r.status in {"ok", "warning"}
    assert "min_date" in r.outputs


# ---------- 2.dup ----------

def test_duplicates_handler_skipped_without_keys():
    df = credit_scoring_sample(n=200, seed=6)
    r = h.duplicates_check_handler({"df": df}, _ctx())
    assert r.status == "ok"
    assert "skip" in r.detail


def test_duplicates_handler_runs_with_keys():
    df = credit_scoring_sample(n=200, seed=6)
    r = h.duplicates_check_handler(
        {"df": df, "key_cols": ["customer_id"]}, _ctx(),
    )
    assert r.status == "ok"
    assert r.outputs["duplicate_count"] == 0


# ---------- 6.audit ----------

def test_audit_handler_ok_when_no_fails():
    ctx = _ctx()
    ctx.results["3.disc"] = StepResult("3.disc", "ok", {}, "passed")
    assert h.audit_handler({}, ctx).status == "ok"


def test_audit_handler_warns_on_fails():
    ctx = _ctx()
    ctx.results["3.capital"] = StepResult("3.capital", "fail", {}, "v")
    r = h.audit_handler({}, ctx)
    assert r.status == "warning"
    assert r.outputs["fails"] == 1


# ---------- registry coverage ----------

def test_all_matrix_steps_have_handlers():
    eng = WorkflowEngine()
    registered = set(h.register_default_handlers(eng))
    expected = set(eng.steps_by_id.keys())
    missing = expected - registered
    assert not missing, f"매트릭스 step 중 미등록: {missing}"
