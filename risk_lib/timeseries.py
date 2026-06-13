"""Synthetic KRI time series for trend / early-warning visualisation.

The harness produces a point-in-time snapshot.  For the CRO dashboard we also
need a *plausible* time series so trend charts make sense — otherwise every
KRI looks like a single dot.  This module generates a 12-month back-history
that:
  - lands on the realised KRI at the current month (so it reconciles)
  - drifts with auto-correlation typical of monthly bank metrics
  - is reproducible from `seed`
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class KRITimeSeries:
    """One KRI's 12-month history ending at the current observation."""
    name: str
    months: list[str]              # ISO month labels (oldest first)
    values: list[float]            # length == months
    threshold_min: float | None    # board limit (min direction) or None
    threshold_max: float | None
    direction: str                 # "min" or "max"

    def trend(self) -> str:
        """Simple trend descriptor for the report."""
        if len(self.values) < 3: return "—"
        recent = np.mean(self.values[-3:])
        older = np.mean(self.values[:3])
        d = recent - older
        if abs(d) < 1e-6: return "보합"
        if self.direction == "min":
            return "악화" if d < 0 else "개선"
        else:
            return "악화" if d > 0 else "개선"


def _ar1(target: float, months: int, *, sigma: float, phi: float = 0.6,
         rng) -> np.ndarray:
    """AR(1) path that lands exactly at `target` in the last step."""
    eps = rng.normal(0, sigma, months)
    x = np.zeros(months)
    x[0] = target + rng.normal(0, sigma * 1.5)
    for t in range(1, months):
        x[t] = phi * x[t - 1] + (1 - phi) * target + eps[t]
    # rescale to land exactly at target
    x = x + (target - x[-1])
    return x


def synth_history(raf, months: int = 12, *, seed: int = 42) -> list[KRITimeSeries]:
    """Generate plausible 12-month history for each KRI in a RAFReport."""
    rng = np.random.default_rng(seed + 313)
    today = pd.Timestamp.now().normalize().to_period("M")
    month_labels = [str((today - (months - 1 - i))) for i in range(months)]
    out = []
    for k in raf.kris:
        # pick sigma proportional to either ratio scale or magnitude
        if k.fmt == "pct":
            sigma = 0.0035       # 35bp monthly noise on ratios
        elif k.fmt == "ratio":
            sigma = 0.012
        else:
            sigma = abs(k.actual) * 0.05
        vals = _ar1(k.actual, months, sigma=sigma, rng=rng)
        if k.threshold.direction == "min":
            tmin = k.threshold.board; tmax = None
        else:
            tmin = None; tmax = k.threshold.board
        out.append(KRITimeSeries(
            name=k.name, months=month_labels, values=vals.tolist(),
            threshold_min=tmin, threshold_max=tmax,
            direction=k.threshold.direction,
        ))
    return out
