"""Intraday risk engine — tick-by-tick VaR / Greeks / limit-utilisation refresh.

Top-IB trading floors do not wait for the overnight batch: they re-price the
book and re-check limits on every market tick. This module provides a
deterministic, seeded simulation of an intraday session:

  - `simulate_market_ticks`: a seeded random-walk path for the risk factors
    (equity index, rates, FX, credit spread, vol) over N intraday snapshots.
  - `IntradayEngine`: on each tick, re-values the trading book Greeks, marks
    VaR, and re-computes limit utilisation. Emits alert events when a limit
    or VaR band is breached.
  - `intraday_var_path`: linear VaR marked at each tick.
  - `AlertEvent`: a structured intraday alert (severity / metric / value /
    threshold / tick) ready to be fed to risk_lib.notifications.

Everything is reproducible: the same seed → identical tick path → identical
alerts, so an intraday session can be replayed for audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Market tick simulation
# ---------------------------------------------------------------------------

RISK_FACTORS = ["equity_idx", "rate_10y", "fx_usdkrw", "credit_spread", "vol"]

# daily vol of each factor (used to scale intraday steps)
_FACTOR_DAILY_VOL = {
    "equity_idx":    0.012,     # 1.2% daily
    "rate_10y":      0.0008,    # 8bp daily
    "fx_usdkrw":     0.006,
    "credit_spread": 0.0006,
    "vol":           0.03,
}


def simulate_market_ticks(n_ticks: int = 78, *, seed: int = 42,
                          stress_tick: int | None = None,
                          stress_mult: float = 6.0) -> pd.DataFrame:
    """Seeded intraday risk-factor path (78 ticks = 5-min bars over 6.5h).

    Returns a frame with one column per risk factor plus 'tick' and 'time'.
    Values are *cumulative shocks* from the open (0.0 at tick 0).
    An optional `stress_tick` injects a large jump to test alerting.
    """
    rng = np.random.default_rng(seed + 5150)
    steps_per_tick_vol = {f: v / np.sqrt(n_ticks)
                          for f, v in _FACTOR_DAILY_VOL.items()}
    data = {f: np.zeros(n_ticks) for f in RISK_FACTORS}
    for f in RISK_FACTORS:
        steps = rng.normal(0, steps_per_tick_vol[f], n_ticks)
        if stress_tick is not None and 0 <= stress_tick < n_ticks:
            steps[stress_tick] += steps_per_tick_vol[f] * stress_mult * (
                -1 if f in ("equity_idx",) else 1)
        data[f] = np.cumsum(steps)
    df = pd.DataFrame(data)
    df.insert(0, "tick", np.arange(n_ticks))
    # 09:00 open, 5-min bars
    df.insert(1, "time", [f"{9 + (5*t)//60:02d}:{(5*t)%60:02d}"
                          for t in range(n_ticks)])
    return df


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@dataclass
class AlertEvent:
    tick: int
    time: str
    severity: str                 # RED / AMBER / WATCH
    metric: str
    value: float
    threshold: float
    message: str


# ---------------------------------------------------------------------------
# Intraday engine
# ---------------------------------------------------------------------------

@dataclass
class IntradayResult:
    ticks: pd.DataFrame           # per-tick VaR / pnl / greeks / util
    alerts: list[AlertEvent]
    peak_var: float
    peak_var_tick: int
    max_util: float
    n_alerts: int


@dataclass
class IntradayEngine:
    """Re-values a book on every tick and checks limits."""
    base_var: float               # start-of-day VaR (KRW)
    base_delta: float             # net delta exposure
    base_dv01: float              # IR sensitivity (KRW / bp)
    base_cs01: float              # credit sensitivity (KRW / bp)
    var_limit: float              # intraday VaR limit
    util_limit: float = 1.0       # limit utilisation ceiling
    watch_frac: float = 0.75      # WATCH at 75% of limit
    amber_frac: float = 0.90      # AMBER at 90%

    def run(self, ticks: pd.DataFrame) -> IntradayResult:
        rows = []
        alerts: list[AlertEvent] = []
        for _, t in ticks.iterrows():
            # mark-to-market P&L from factor moves
            pnl = (- self.base_delta * t["equity_idx"] * 100
                   - self.base_dv01 * t["rate_10y"] * 1e4
                   - self.base_cs01 * t["credit_spread"] * 1e4)
            # VaR scales with realised vol (vol factor) + position drift
            var_now = self.base_var * (1 + 12.0 * abs(t["vol"])
                                       + 25.0 * abs(t["equity_idx"]))
            util = var_now / self.var_limit if self.var_limit else 0.0

            # alerting
            if util >= self.util_limit:
                sev = "RED"
            elif util >= self.amber_frac:
                sev = "AMBER"
            elif util >= self.watch_frac:
                sev = "WATCH"
            else:
                sev = None
            if sev:
                alerts.append(AlertEvent(
                    tick=int(t["tick"]), time=str(t["time"]),
                    severity=sev, metric="VaR 사용률",
                    value=util, threshold=self.util_limit,
                    message=(f"VaR 사용률 {util*100:.0f}% "
                             f"(VaR {var_now/1e9:.1f}bn / 한도 {self.var_limit/1e9:.1f}bn)"),
                ))
            rows.append({
                "tick": int(t["tick"]), "time": str(t["time"]),
                "pnl": pnl, "var": var_now, "util": util,
                "delta_pnl": - self.base_delta * t["equity_idx"] * 100,
                "ir_pnl": - self.base_dv01 * t["rate_10y"] * 1e4,
                "credit_pnl": - self.base_cs01 * t["credit_spread"] * 1e4,
                "severity": sev or "OK",
            })
        df = pd.DataFrame(rows)
        peak_i = int(df["var"].idxmax())
        return IntradayResult(
            ticks=df, alerts=alerts,
            peak_var=float(df["var"].max()),
            peak_var_tick=int(df.loc[peak_i, "tick"]),
            max_util=float(df["util"].max()),
            n_alerts=len(alerts),
        )


def run_intraday_session(result, *, seed: int = 42,
                         stress_tick: int | None = None) -> IntradayResult:
    """Wire a pipeline result into an intraday session.

    Uses the trading book Greeks (from risk_lib.sensitivities) to seed the
    engine, and market RWA-derived VaR as the base VaR / limit.
    """
    from risk_lib.sensitivities import synthesise_trading_book, desk_aggregate

    base_var = result.rwa["market"] * 0.02   # ~2% of market RWA as 1d VaR
    var_limit = base_var * 2.0                # limit = 2x SOD VaR

    if result.ccr is not None and not result.ccr.by_counterparty.empty:
        bank = result.ccr.by_counterparty.rename(
            columns={"counterparty": "obligor_id"}).copy()
        bank["ead"] = bank.get("ead", 1e9)
        book = synthesise_trading_book(bank, seed=seed)
        ds = desk_aggregate(book)
        base_delta, base_dv01, base_cs01 = ds.total_delta, ds.total_dv01, ds.total_cs01
    else:
        base_delta, base_dv01, base_cs01 = 10.0, 1e8, 5e7

    engine = IntradayEngine(
        base_var=base_var, base_delta=base_delta,
        base_dv01=base_dv01, base_cs01=base_cs01,
        var_limit=var_limit,
    )
    ticks = simulate_market_ticks(seed=seed, stress_tick=stress_tick)
    return engine.run(ticks)
