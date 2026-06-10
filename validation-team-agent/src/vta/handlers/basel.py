"""vta.handlers.basel — Basel 부문 handler alias (v1 동일 객체)."""

from __future__ import annotations

from tools.handlers import (  # noqa: F401
    capital_handler as capital,
    ccr_handler as ccr,
    concentration_handler as concentration,
    cva_handler as cva,
    irrbb_handler as irrbb,
    liquidity_handler as liquidity,
    market_handler as market,
    operational_handler as operational,
)

__all__ = [
    "capital", "ccr", "concentration", "cva", "irrbb", "liquidity", "market",
    "operational"
]
