"""Helpers shared by the ops deep-dive page modules."""

from risk_lib.html_report import (
    _page, _esc,
)


# ============================================================================
# v0.7.0 — RWA deep-dive pages (CRO-grade)
# ============================================================================


def _placeholder_page(title: str, msg: str, active: str) -> str:
    body = f'<h1 class="title">{_esc(title)}</h1><p class="section-lead">{_esc(msg)}</p>'
    return _page(title, body, active)
