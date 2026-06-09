"""vta.reports — 보고서 템플릿 / 점검 (v1 re-export)."""

from __future__ import annotations

from tools.report_template import (  # noqa: F401
    build_validation_report,
    build_issue_summary,
    render_html,
)
from middleware.output_completeness_guard import (  # noqa: F401
    check_numeric_citations,
    check_report,
)
from middleware.draft_watermark_guard import check_watermarks  # noqa: F401

__all__ = [
    "build_validation_report",
    "build_issue_summary",
    "render_html",
    "check_numeric_citations",
    "check_report",
    "check_watermarks",
]
