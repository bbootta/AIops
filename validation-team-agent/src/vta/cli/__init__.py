"""vta CLI — 단일 entry point (Phase 4 에서 본격 통합).

현재는 v1 의 17개 `python -m tools.*` CLI 를 그대로 사용한다. 본 모듈은
Phase 4 에서 단일 `vta` subcommand 구조로 통합될 예정이며, 그 시점까지는
사용 가능한 v1 CLI 목록만 노출한다.
"""

from __future__ import annotations

V1_CLI_MODULES = [
    "tools.run_validation",
    "tools.run_macro_validation",
    "tools.run_ifrs9_validation",
    "tools.run_workflow_demo",
    "tools.run_audit",
    "tools.dry_run",
    "tools.dry_run_diff",
    "tools.manifest",
    "tools.findings",
    "tools.model_notes",
    "tools.limitations",
    "tools.policy_lint",
    "tools.classify_error",
    "tools.feedback_retention",
    "tools.audit_retention",
    "tools.runner_result",
    "tools.cli_index",
]

__all__ = ["V1_CLI_MODULES"]
