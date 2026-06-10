"""vta.handlers — workflow step handler registry (Phase 3 canonical).

본체는 ``vta.handlers.registry``. 도메인별 alias 는 ``vta.handlers.credit``,
``.basel``, ``.report``, ``.data``, ``.macro``. v1 의 ``tools.handlers`` 는
호환 shim 이다 (제거 목표 2026-Q4).
"""

from __future__ import annotations

from vta.handlers.registry import (  # noqa: F401
    register_default_handlers,
)
from vta.handlers import registry as _registry

# registry 의 step_id → handler dict (rename 의 사용자 결정 영역 침범 안 함).
DEFAULT = _registry._DEFAULT  # noqa: SLF001

__all__ = ["DEFAULT", "register_default_handlers"]
