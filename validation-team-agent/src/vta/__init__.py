"""vta — validation team agent (v2).

Phase 2 부터 엔진 본체는 ``vta.core.workflow`` 가 canonical 이며, v1
(`tools.workflow`) 은 1분기 유지되는 호환 shim 이다 (Q2 결정).

호환성 보장:
- v1 모든 API 는 변경 없이 동작 (`import tools.workflow`, `import middleware.run_logger` 등).
- v1 과 v2 는 동일 객체를 가리킨다 (단일 진실 소스).
- v1 shim 제거 목표: 2026-Q4 (`docs/v2_refactor_plan.md` 4절).

주의: 본 __init__ 은 순환 import 방지를 위해 v1 모듈을 lazy 로 노출한다
(PEP 562). ``vta.core_workflow`` 등 속성 접근 시점에 import 된다.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0a1"

# 속성명 → import 경로 (PEP 562 lazy export — tools ↔ vta 순환 방지)
_LAZY = {
    "core_workflow": "vta.core.workflow",
}

__all__ = [
    "__version__",
    "core_workflow",
]


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name])
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'vta' has no attribute {name!r}")
