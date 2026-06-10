"""vta.core — workflow engine / logging / classification.

Phase 2 완료: 엔진 본체는 ``vta.core.workflow`` 가 canonical 이며
``tools.workflow`` 는 1분기 유지되는 호환 shim 이다 (Q2 결정).
run_logger 는 middleware 에 잔류 (Phase 3 에서 이전 검토).
"""

from __future__ import annotations

from vta.core.models import ValidationRequest  # noqa: F401
from vta.core.workflow import (  # noqa: F401
    StepResult,
    WorkflowContext,
    WorkflowEngine,
    WorkflowError,
    WorkflowRun,
)
from middleware.run_logger import (  # noqa: F401
    collect_step_ids,
    collect_step_records,
    log_step,
    run_logger,
    write_event,
)

__all__ = [
    "ValidationRequest",
    "StepResult",
    "WorkflowContext",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowRun",
    "collect_step_ids",
    "collect_step_records",
    "log_step",
    "run_logger",
    "write_event",
]
