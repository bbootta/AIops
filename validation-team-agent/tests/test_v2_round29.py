"""Round 29 — v2 Phase 3 완결: risk_checks/handlers 본체의 vta 이전."""

from __future__ import annotations



# ---------- risk_checks → vta.domains (sys.modules shim) ----------

def test_risk_modules_canonical_in_vta_domains():
    """tools.risk_checks.<name> 은 vta.domains.<name> 과 동일 모듈 객체다."""
    import vta.domains

    for name in vta.domains.__all__:
        import importlib

        v1 = importlib.import_module(f"tools.risk_checks.{name}")
        canon = getattr(vta.domains, name)
        assert v1 is canon, name
        assert canon.__name__ == f"vta.domains.{name}"


def test_risk_module_thresholds_resolve_from_new_location():
    """이전 후에도 _THRESHOLDS_PATH 가 harness/ SSoT 를 가리킨다."""
    import vta.domains

    for name in vta.domains.__all__:
        mod = getattr(vta.domains, name)
        th = mod.load_thresholds()
        assert isinstance(th, dict) and th, name


def test_risk_check_functions_still_work():
    from tools.risk_checks.capital import check_ratios

    out = check_ratios(0.13, 0.14, 0.16)
    assert out["passed"] is True


# ---------- handlers → vta.handlers.registry ----------

def test_handlers_canonical_in_registry():
    import tools.handlers as shim
    import vta.handlers.registry as reg

    assert shim.register_default_handlers is reg.register_default_handlers
    assert shim._DEFAULT is reg._DEFAULT
    assert shim.capital_handler is reg.capital_handler
    assert shim.report_handler is reg.report_handler


def test_registry_module_origin():
    import vta.handlers.registry as reg

    assert reg.capital_handler.__module__ == "vta.handlers.registry"


def test_registry_imports_core_workflow_directly():
    """registry 는 shim(tools.workflow)이 아닌 vta.core.workflow 를 쓴다."""
    import inspect

    import vta.handlers.registry as reg

    src = inspect.getsource(reg)
    assert "from vta.core.workflow import" in src
    assert "from tools.workflow import" not in src


def test_v1_shim_chain_no_cycle_when_imported_first():
    """tools.handlers 를 최초 import 해도 순환 없이 동작한다."""
    import subprocess
    import sys
    from pathlib import Path

    code = (
        "from tools.handlers import register_default_handlers; "
        "from vta.core.workflow import WorkflowEngine; "
        "eng = WorkflowEngine(); print(len(register_default_handlers(eng)))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert int(out.stdout.strip()) >= 25


def test_workflow_runs_with_registry_handlers(tmp_path):
    from vta.core.workflow import WorkflowEngine
    from vta.handlers.registry import register_default_handlers

    eng = WorkflowEngine()
    register_default_handlers(eng)
    run = eng.run({"capital_cet1": 0.13}, log_dir=tmp_path)
    assert "3.capital" in run.executed_order
