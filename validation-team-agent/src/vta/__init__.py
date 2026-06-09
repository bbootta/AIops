"""vta — validation team agent (v2 shell).

본 패키지는 v1 (`tools/`, `middleware/`, `harness/`) 의 동작을 그대로 보존한
**re-export shim** 이다. Round 20 시점 (Phase 1) 에서는 import 호환만 제공하며,
실제 모듈 이전은 Phase 2 (R21~R22) 이후 진행된다.

v2 의 결정 항목 (Q1~Q5) 은 `docs/v2_refactor_plan.md` 참조.

호환성 보장:
- v1 모든 API 는 변경 없이 동작 (`import tools.workflow`, `import middleware.run_logger` 등).
- v2 `import vta` 는 v1 의 동일 객체를 가리킨다 (단일 진실 소스).
- v2 의 어떤 함수도 새로 정의되지 않는다 — 모두 v1 의 re-export.
- 향후 모듈 이전 시 v1 은 deprecation warning 후 1개 분기 유지.
"""

from __future__ import annotations

__version__ = "0.1.0a1"

# v1 module surfaces — direct re-export 로 동일 객체 보장.
from tools import workflow as core_workflow
from tools import handlers as _handlers
from tools import manifest as _manifest
from tools import dry_run as _dry_run

__all__ = [
    "__version__",
    "core_workflow",
]
