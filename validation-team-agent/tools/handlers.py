"""v1 호환 shim — 본체는 ``vta.handlers.registry`` 로 이전 (Phase 3).

기존 ``from tools.handlers import register_default_handlers`` 등은 그대로
동작한다. 신규 코드는 ``vta.handlers.registry`` 를 직접 import 할 것.

Deprecation: Q2 결정(1개 분기 유지)에 따라 2026-Q4 제거 예정 —
docs/v2_refactor_plan.md 4절.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from vta.handlers.registry import *  # noqa: F401,F403
    from vta.handlers.registry import _DEFAULT, _bad_scalar, _has  # noqa: F401
except ModuleNotFoundError:
    # pip install -e . 없이 repo 루트에서 직접 실행하는 경우 src/ 를 경로에 추가
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from vta.handlers.registry import *  # noqa: F401,F403
    from vta.handlers.registry import _DEFAULT, _bad_scalar, _has  # noqa: F401
