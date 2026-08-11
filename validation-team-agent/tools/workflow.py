"""v1 호환 shim — 엔진 본체는 ``vta.core.workflow`` 로 이전 (Phase 2).

기존 ``from tools.workflow import WorkflowEngine, StepResult`` 호출은 그대로
동작한다. 신규 코드는 ``vta.core.workflow`` 를 직접 import 할 것.

Deprecation: Q2 결정(1개 분기 유지)에 따라 본 shim 은 2026-Q4 에 제거 예정.
제거 일정은 docs/v2_refactor_plan.md 참조.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from vta.core.workflow import (  # noqa: F401
        Handler,
        Status,
        StepResult,
        WorkflowContext,
        WorkflowEngine,
        WorkflowError,
        WorkflowRun,
        _classify,
        _topological_order,
    )
except ModuleNotFoundError:
    # pip install -e . 없이 repo 루트에서 직접 실행하는 경우 src/ 를 경로에 추가
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from vta.core.workflow import (  # noqa: F401
        Handler,
        Status,
        StepResult,
        WorkflowContext,
        WorkflowEngine,
        WorkflowError,
        WorkflowRun,
        _classify,
        _topological_order,
    )

__all__ = [
    "Handler",
    "Status",
    "StepResult",
    "WorkflowContext",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowRun",
]
