"""Shared session-scoped fixtures for the risk_lib test suite.

Previously 8 test modules each ran their own module-scoped
`run_pipeline(generate_portfolio(seed=42), seed=42)` fixture, so the full
suite executed the pipeline 8 times (~5m41s wall). One session-scoped run
is shared by every module instead.

`asof` is pinned so the forecast quarter axis (2026Q3..2028Q4) is
reproducible independent of wall-clock time.
"""

from __future__ import annotations

import pytest

from risk_lib.data_gen import generate_portfolio
from risk_lib.pipeline import run_pipeline

PINNED_ASOF = "2026-06-11"


@pytest.fixture(scope="session")
def portfolio():
    return generate_portfolio(seed=42)


@pytest.fixture(scope="session")
def result(portfolio):
    return run_pipeline(portfolio, seed=42, asof=PINNED_ASOF)
