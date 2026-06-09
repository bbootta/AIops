"""vta.handlers.macro — 거시 / IFRS 9 시나리오 가중치 handler alias."""

from __future__ import annotations

from tools.handlers import (  # noqa: F401
    macro_handler as stationarity,
    scenario_weights_handler as scenario_weights,
)

__all__ = ["stationarity", "scenario_weights"]
