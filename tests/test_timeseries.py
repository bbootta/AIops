"""Tests for the time-series accumulation ledger."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from risk_lib import generate_portfolio, run_pipeline
from risk_lib.repro import build_manifest, now_utc
from risk_lib.timeseries_ledger import (
    TimeSeriesLedger, PeriodSnapshot, HEADLINE_SPEC,
    build_timeseries_report,
)


def _mk_ledger(n=5, start_seed=42):
    led = TimeSeriesLedger()
    periods = ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1"][:n]
    for i, per in enumerate(periods):
        p = generate_portfolio(seed=start_seed + i)
        res = run_pipeline(p, seed=start_seed + i)
        mf = build_manifest(portfolio=p, parameters={"seed": start_seed + i},
                            result=res, start_utc=now_utc(), end_utc=now_utc())
        led.add_from_manifest(per, mf)
    return led


@pytest.fixture(scope="module")
def ledger():
    return _mk_ledger()


def test_ledger_accumulates(ledger):
    assert len(ledger.snapshots) == 5
    assert [s.period for s in ledger.snapshots] == sorted(
        s.period for s in ledger.snapshots)


def test_ledger_idempotent_period(ledger):
    """Re-adding the same period replaces, does not duplicate."""
    before = len(ledger.snapshots)
    snap = ledger.snapshots[-1]
    ledger.add(PeriodSnapshot(period=snap.period, asof=snap.asof,
                              headline=snap.headline))
    assert len(ledger.snapshots) == before


def test_frame_has_all_headline_metrics(ledger):
    df = ledger.to_frame()
    for mid in HEADLINE_SPEC:
        assert mid in df.columns
    assert len(df) == len(ledger.snapshots)


def test_qoq_yoy_shapes(ledger):
    q = ledger.qoq_yoy("bis.cet1")
    assert "qoq" in q.columns and "yoy" in q.columns
    assert len(q) == len(ledger.snapshots)
    # first QoQ is NaN
    assert np.isnan(q["qoq"].iloc[0])


def test_trend_flags_present(ledger):
    flags = ledger.trend_flags()
    assert not flags.empty
    assert {"metric", "label", "latest", "trend",
            "consecutive_breaches"} <= set(flags.columns)
    # all trend values are known labels
    assert set(flags["trend"]) <= {"개선", "악화", "보합", "증가", "감소"}


def test_trend_direction_awareness():
    """A rising CET1 (min-direction) is 개선; a rising IRRBB (max) is 악화."""
    led = TimeSeriesLedger()
    led.add(PeriodSnapshot("2025Q1", "2025-03-31",
                           {"bis.cet1": 0.10, "irrbb.worst_pct_tier1": 0.05}))
    led.add(PeriodSnapshot("2025Q2", "2025-06-30",
                           {"bis.cet1": 0.11, "irrbb.worst_pct_tier1": 0.08}))
    flags = led.trend_flags().set_index("metric")
    assert flags.loc["bis.cet1", "trend"] == "개선"       # rose, min-metric
    assert flags.loc["irrbb.worst_pct_tier1", "trend"] == "악화"  # rose, max-metric


def test_consecutive_breach_counter():
    """Consecutive sub-floor periods are counted from the latest backwards."""
    led = TimeSeriesLedger()
    # CET1 floor is 0.08; three sub-floor periods at the end
    for per, v in [("2025Q1", 0.10), ("2025Q2", 0.075),
                   ("2025Q3", 0.07), ("2025Q4", 0.065)]:
        led.add(PeriodSnapshot(per, per, {"bis.cet1": v}))
    flags = led.trend_flags().set_index("metric")
    assert flags.loc["bis.cet1", "consecutive_breaches"] == 3


def test_json_roundtrip(tmp_path, ledger):
    p = ledger.save(tmp_path / "ts.json")
    assert Path(p).exists()
    reloaded = TimeSeriesLedger.load(p)
    assert len(reloaded.snapshots) == len(ledger.snapshots)
    assert reloaded.snapshots[0].period == ledger.snapshots[0].period


def test_load_missing_file_returns_empty(tmp_path):
    led = TimeSeriesLedger.load(tmp_path / "does_not_exist.json")
    assert len(led.snapshots) == 0


def test_build_report_writes_html(tmp_path, ledger):
    p = build_timeseries_report(ledger, tmp_path / "trend.html")
    body = Path(p).read_text(encoding="utf-8")
    assert "시계열" in body
    assert "자본비율 추이" in body
    assert "약어 사전" in body
    assert body.count("<svg") >= 4
