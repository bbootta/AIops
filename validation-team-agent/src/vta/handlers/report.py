"""vta.handlers.report — 보고서 산출 / 점검 / escalation handler alias."""

from __future__ import annotations

from tools.handlers import (  # noqa: F401
    citation_handler as citation,
    completeness_handler as completeness,
    escalation_handler as escalation,
    report_handler as report,
    watermark_handler as watermark,
)

__all__ = [
    "report", "completeness", "citation", "watermark", "escalation"
]
