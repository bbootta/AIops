"""Round 27 — v2 Phase 2: 엔진 이전 + Pydantic 데이터 계약 + 정책 로더."""

from __future__ import annotations

import pandas as pd
import pytest


# ---------- 엔진 canonical 위치 / shim 동일성 ----------

def test_canonical_engine_in_vta_core_workflow():
    import tools.workflow as shim
    import vta.core.workflow as canon

    assert shim.WorkflowEngine is canon.WorkflowEngine
    assert shim.StepResult is canon.StepResult
    assert shim.WorkflowContext is canon.WorkflowContext
    assert shim.WorkflowRun is canon.WorkflowRun
    assert shim.WorkflowError is canon.WorkflowError


def test_import_tools_workflow_first_no_cycle():
    """tools.workflow 를 먼저 import 해도 순환 import 가 없다 (vta lazy __init__)."""
    import subprocess
    import sys

    code = (
        "from tools.workflow import StepResult; "
        "print(StepResult('1.x', 'ok').status)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=True,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
    )
    assert out.stdout.strip() == "ok"


def test_vta_lazy_core_workflow_attr():
    import vta
    import vta.core.workflow as canon

    assert vta.core_workflow is canon
    with pytest.raises(AttributeError):
        vta.no_such_attr  # noqa: B018


# ---------- StepResult — Pydantic 검증 ----------

def test_step_result_invalid_status_raises_value_error():
    from vta.core.workflow import StepResult

    with pytest.raises(ValueError):
        StepResult("1.x", "weird")


def test_step_result_positional_and_defaults():
    from vta.core.workflow import StepResult

    r = StepResult("3.disc", "warning", {"ks": 0.2}, "KS below")
    assert (r.step_id, r.status, r.outputs, r.detail) == (
        "3.disc", "warning", {"ks": 0.2}, "KS below")
    r2 = StepResult("1.req", "ok")
    assert r2.outputs == {} and r2.detail == ""


def test_step_result_rejects_non_string_step_id():
    from vta.core.workflow import StepResult

    with pytest.raises(ValueError):
        StepResult(123, "ok")


# ---------- ValidationRequest ----------

def test_validation_request_defaults_and_extra():
    from vta.core.models import ValidationRequest

    req = ValidationRequest(title="t", capital_cet1=0.13)
    d = req.to_request()
    assert d["title"] == "t"
    assert d["capital_cet1"] == 0.13  # extra 필드 통과
    assert d["df"] is None
    assert d["key_cols"] == []


def test_validation_request_rejects_non_dataframe_df():
    from vta.core.models import ValidationRequest

    with pytest.raises(ValueError):
        ValidationRequest(df=[1, 2, 3])


def test_validation_request_df_reference_preserved():
    from vta.core.models import ValidationRequest

    df = pd.DataFrame({"a": [1, 2]})
    req = ValidationRequest(df=df)
    assert req.to_request()["df"] is df


def test_validation_request_runs_through_engine(tmp_path):
    from tools.handlers import register_default_handlers
    from vta.core.models import ValidationRequest
    from vta.core.workflow import WorkflowEngine

    eng = WorkflowEngine()
    register_default_handlers(eng)
    req = ValidationRequest(title="pydantic 경유", capital_cet1=0.13)
    run = eng.run(req.to_request(), log_dir=tmp_path)
    assert len(run.executed_order) >= 1
    assert "3.capital" in run.executed_order


# ---------- 정책 로더 (Q3=a) ----------

def test_load_validated_with_schema():
    from vta.policies.models import load_validated

    pol = load_validated("orchestration_matrix")
    assert pol.name == "orchestration_matrix"
    assert pol.schema_validated is True
    assert pol.schema_path is not None
    assert isinstance(pol.data["steps"], list)
    assert pol.version is not None


def test_load_validated_without_schema_still_loads():
    from vta.policies import list_policies, list_schemas
    from vta.policies.models import load_validated

    schema_names = {n for n, _ in list_schemas()}
    no_schema = [n for n, _ in list_policies() if n not in schema_names]
    if not no_schema:
        pytest.skip("모든 정책에 schema 존재")
    pol = load_validated(no_schema[0])
    assert pol.schema_validated is False
    assert pol.schema_path is None


def test_policy_envelope_is_frozen():
    from vta.policies.models import load_validated

    pol = load_validated("orchestration_matrix")
    with pytest.raises(Exception):
        pol.name = "x"


def test_load_validated_missing_policy_raises():
    from vta.policies.models import load_validated

    with pytest.raises(FileNotFoundError):
        load_validated("no_such_policy")
