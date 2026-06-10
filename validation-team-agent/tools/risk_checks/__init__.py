"""v1 호환 shim — 본체는 ``vta.domains`` 로 이전 (Phase 3).

``import tools.risk_checks.capital`` / ``from tools.risk_checks import capital``
모두 canonical 모듈 (``vta.domains.capital``) 과 동일 객체를 반환한다
(sys.modules 등록 방식). 제거 목표 2026-Q4 — docs/v2_refactor_plan.md 4절.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from vta.domains import (  # noqa: F401
        capital, ccr, concentration, cva, irrbb, liquidity, market, operational,
    )
except ModuleNotFoundError:
    # pip install -e . 없이 repo 루트에서 직접 실행하는 경우 src/ 를 경로에 추가
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from vta.domains import (  # noqa: F401
        capital, ccr, concentration, cva, irrbb, liquidity, market, operational,
    )

# `import tools.risk_checks.<name>` 이 canonical 모듈을 반환하도록 등록
for _name, _mod in [
    ("capital", capital), ("concentration", concentration), ("ccr", ccr), ("cva", cva), ("irrbb", irrbb),
    ("liquidity", liquidity), ("market", market), ("operational", operational),
]:
    sys.modules[f"{__name__}.{_name}"] = _mod

__all__ = ["capital", "concentration", "ccr", "cva", "irrbb", "liquidity", "market", "operational"]
