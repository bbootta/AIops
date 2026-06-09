"""vta.handlers.credit — 신용 부문 handler alias (v1 동일 객체)."""

from __future__ import annotations

from tools.handlers import (  # noqa: F401
    credit_calibration_handler as calibration,
    credit_discrimination_handler as discrimination,
    credit_psi_handler as psi,
    sample_size_handler as sample_size,
)

__all__ = ["discrimination", "psi", "calibration", "sample_size"]
