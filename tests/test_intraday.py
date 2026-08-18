"""Tests for the intraday risk engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib import generate_portfolio
from risk_lib.intraday import (
    simulate_market_ticks, IntradayEngine, run_intraday_session,
    RISK_FACTORS, AlertEvent,
)

# `result` fixture: session-scoped shared — see conftest.py.


def test_tick_path_shape():
    df = simulate_market_ticks(n_ticks=78, seed=42)
    assert len(df) == 78
    for f in RISK_FACTORS:
        assert f in df.columns
    # opens near zero (first cumulative step is small)
    assert abs(df["equity_idx"].iloc[0]) < 0.01


def test_tick_path_reproducible():
    a = simulate_market_ticks(seed=7)
    b = simulate_market_ticks(seed=7)
    assert np.allclose(a["equity_idx"], b["equity_idx"])
    assert np.allclose(a["vol"], b["vol"])


def test_tick_path_seed_varies():
    a = simulate_market_ticks(seed=1)
    b = simulate_market_ticks(seed=2)
    assert not np.allclose(a["equity_idx"], b["equity_idx"])


def test_stress_tick_injects_jump():
    normal = simulate_market_ticks(seed=42)
    stressed = simulate_market_ticks(seed=42, stress_tick=40, stress_mult=8)
    # after the stress tick the paths diverge
    assert not np.allclose(normal["equity_idx"].iloc[40:],
                           stressed["equity_idx"].iloc[40:])
    # before it they match
    assert np.allclose(normal["equity_idx"].iloc[:40],
                       stressed["equity_idx"].iloc[:40])


def test_engine_var_nonneg_and_util():
    ticks = simulate_market_ticks(seed=42)
    eng = IntradayEngine(base_var=10e9, base_delta=100, base_dv01=1e8,
                         base_cs01=5e7, var_limit=20e9)
    res = eng.run(ticks)
    assert (res.ticks["var"] >= 0).all()
    assert res.peak_var >= res.ticks["var"].iloc[0]
    assert 0 <= res.max_util


def test_engine_alerts_fire_above_watch():
    """A tight limit produces alerts."""
    ticks = simulate_market_ticks(seed=42, stress_tick=20, stress_mult=10)
    eng = IntradayEngine(base_var=10e9, base_delta=100, base_dv01=1e8,
                         base_cs01=5e7, var_limit=11e9)  # tight
    res = eng.run(ticks)
    assert res.n_alerts > 0
    for a in res.alerts:
        assert a.severity in ("WATCH", "AMBER", "RED")
        assert a.value >= eng.watch_frac


def test_engine_no_alerts_with_loose_limit():
    ticks = simulate_market_ticks(seed=42)
    eng = IntradayEngine(base_var=1e9, base_delta=10, base_dv01=1e7,
                         base_cs01=1e6, var_limit=1e12)  # huge limit
    res = eng.run(ticks)
    assert res.n_alerts == 0


def test_session_deterministic(result):
    a = run_intraday_session(result, seed=42, stress_tick=40)
    b = run_intraday_session(result, seed=42, stress_tick=40)
    assert np.allclose(a.ticks["var"], b.ticks["var"])
    assert a.n_alerts == b.n_alerts


def test_session_produces_78_ticks(result):
    r = run_intraday_session(result, seed=42)
    assert len(r.ticks) == 78
    assert {"pnl", "var", "util", "severity"} <= set(r.ticks.columns)


def test_alert_event_fields():
    ev = AlertEvent(tick=10, time="09:50", severity="RED",
                    metric="VaR", value=1.05, threshold=1.0, message="x")
    assert ev.severity == "RED" and ev.value > ev.threshold


def test_intraday_page_registered(tmp_path, result):
    from risk_lib.html_report import build_full_report_package
    p = generate_portfolio(seed=42)
    written = build_full_report_package(result, tmp_path, portfolio=p)
    assert "ops/61_intraday.html" in written
    import os
    assert os.path.getsize(written["ops/61_intraday.html"]) > 5000
