"""Round 20 / v2 Phase 1: 패키지 셸 import 호환성 + v1 객체 동일성.

본 테스트는 v2 namespace 가 v1 의 **동일 객체**를 가리키는지 확인한다.
v2 셸은 새 정의를 만들지 않으며 모두 v1 의 re-export 이다.
"""

import pytest


def test_top_level_import():
    import vta
    assert vta.__version__.startswith("0.")


def test_core_workflow_engine_identity():
    import vta.core
    import tools.workflow as v1

    assert vta.core.WorkflowEngine is v1.WorkflowEngine
    assert vta.core.StepResult is v1.StepResult
    assert vta.core.WorkflowContext is v1.WorkflowContext
    assert vta.core.WorkflowRun is v1.WorkflowRun


def test_core_logger_identity():
    import vta.core
    import middleware.run_logger as v1

    assert vta.core.log_step is v1.log_step
    assert vta.core.collect_step_ids is v1.collect_step_ids
    assert vta.core.run_logger is v1.run_logger


def test_domains_namespace_identity():
    import vta.domains
    from tools.risk_checks import (
        capital, ccr, cva, irrbb, liquidity, market, operational,
    )

    assert vta.domains.capital is capital
    assert vta.domains.ccr is ccr
    assert vta.domains.cva is cva
    assert vta.domains.irrbb is irrbb
    assert vta.domains.liquidity is liquidity
    assert vta.domains.market is market
    assert vta.domains.operational is operational


def test_handlers_registry_identity():
    import vta.handlers
    import tools.handlers as v1

    assert vta.handlers.register_default_handlers is v1.register_default_handlers
    assert vta.handlers.DEFAULT is v1._DEFAULT


def test_policies_loader_works():
    import vta.policies

    matrix = vta.policies.load("orchestration_matrix")
    assert "steps" in matrix
    assert len(matrix["steps"]) >= 25
    # 정책 파일 부재 시 명확한 오류
    with pytest.raises(FileNotFoundError):
        vta.policies.load("__does_not_exist__")


def test_reports_namespace_identity():
    import vta.reports
    from tools.report_template import build_validation_report
    from middleware.output_completeness_guard import check_report
    from middleware.draft_watermark_guard import check_watermarks

    assert vta.reports.build_validation_report is build_validation_report
    assert vta.reports.check_report is check_report
    assert vta.reports.check_watermarks is check_watermarks


def test_cli_module_catalog_lists_v1_entries():
    import vta.cli

    assert "tools.run_workflow_demo" in vta.cli.V1_CLI_MODULES
    assert "tools.manifest" in vta.cli.V1_CLI_MODULES
    assert len(vta.cli.V1_CLI_MODULES) >= 15


def test_v2_does_not_change_v1_behaviour():
    """v2 import 후에도 v1 단독 실행이 동일해야 한다."""
    import vta  # noqa: F401  (트리거)
    from tools.workflow import WorkflowEngine
    from tools.handlers import register_default_handlers

    eng = WorkflowEngine()
    registered = register_default_handlers(eng)
    # v1 단독 실행 결과: 전 step 등록 (R19: 25, R33: 3.conc 추가로 26)
    assert len(registered) == 28
