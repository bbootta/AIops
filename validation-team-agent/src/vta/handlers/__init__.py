"""vta.handlers — workflow step handler registry (v1 re-export)."""

from __future__ import annotations

from tools.handlers import (  # noqa: F401
    register_default_handlers,
)
from tools import handlers as _v1_handlers

# v1 _DEFAULT dict 를 그대로 노출 (rename 의 사용자 결정 영역 침범 안 함).
DEFAULT = _v1_handlers._DEFAULT  # noqa: SLF001

__all__ = ["DEFAULT", "register_default_handlers"]
