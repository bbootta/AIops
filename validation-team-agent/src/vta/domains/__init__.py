"""vta.domains — Basel 부문별 risk check 모듈 (Phase 3 canonical).

각 부문은 다음 패턴을 따른다.
- 임계 SSoT 는 ``harness/<bucket>_thresholds.json``
- 점검 함수는 결정론적·부작용 없는 순수 함수
- 산정 모형 자체는 트레이딩/리스크 시스템에서 수행, 본 모듈은 점검만

v1 의 ``tools.risk_checks`` 는 본 모듈을 가리키는 호환 shim 이다 (Q2 결정,
제거 목표 2026-Q4).
"""

from __future__ import annotations

from vta.domains import (  # noqa: F401
    capital,
    concentration,
    ccr,
    cva,
    irrbb,
    liquidity,
    market,
    operational,
)

__all__ = ["capital", "concentration", "ccr", "cva", "irrbb", "liquidity", "market", "operational"]
