"""분기별 다기간 스트레스 경로 (multi-period quarterly stress projection).

`run_stress` applies one point-in-time shock and reads the capital impact.  This
module projects a *trajectory*: a sequence of quarterly stress severities from
the forecast-start quarter to a horizon (e.g. 2026Q3 .. 2028Q4), maps each
quarter's severity to a Scenario via `StressAxis`, and revalues RWA / ECL / BIS
at every quarter.

Each scenario follows a hump-shaped severity profile — stress ramps linearly to
a peak, then mean-reverts geometrically — per EBA/CCAR multi-period design.  The
per-quarter capital impact is the same point-in-time revaluation used by
`evaluate_scenario` (CET1 reduced by ECL above the unstressed base); a full
cumulative pre-provision-earnings projection is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from risk_lib.capital.bis import CapitalStack
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.stress.scenario import StressAxis, evaluate_scenario


def _q_index(year: int, q: int) -> int:
    return year * 4 + (q - 1)


def _q_label(idx: int) -> str:
    y, m = divmod(idx, 4)
    return f"{y}Q{m + 1}"


def forecast_quarter_labels(asof: date, years_ahead: int = 2) -> list[str]:
    """Quarters from the one *after* `asof`'s quarter through Q4 of `asof.year
    + years_ahead` (i.e. "내후년말까지" when years_ahead=2)."""
    cur_q = (asof.month - 1) // 3 + 1
    start = _q_index(asof.year, cur_q) + 1
    end = _q_index(asof.year + years_ahead, 4)
    return [_q_label(i) for i in range(start, end + 1)]


@dataclass
class StressPath:
    """A named quarterly severity trajectory (hump-shaped).

    Severity ramps linearly to `peak_severity` at `peak_index`, then decays by
    `decay` each subsequent quarter.  peak_index <= 0 gives a flat path.
    """
    name: str
    peak_severity: float
    peak_index: int = 4
    decay: float = 0.8

    def severities(self, n: int) -> list[float]:
        out: list[float] = []
        for i in range(n):
            if self.peak_index <= 0:
                s = self.peak_severity
            elif i <= self.peak_index:
                s = self.peak_severity * (i + 1) / (self.peak_index + 1)
            else:
                s = self.peak_severity * self.decay ** (i - self.peak_index)
            out.append(float(s))
        return out


# Default supervisory narratives.  Severe shock is front-loaded and deeper;
# adverse is milder and peaks a little later — typical EBA/CCAR shaping.
DEFAULT_STRESS_PATHS: list[StressPath] = [
    StressPath("baseline", peak_severity=0.0, peak_index=0),
    StressPath("adverse", peak_severity=1.0, peak_index=4),
    StressPath("severely_adverse", peak_severity=2.2, peak_index=3),
]


def run_stress_path(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    *,
    quarters: list[str] | None = None,
    asof: date | None = None,
    years_ahead: int = 2,
    paths: list[StressPath] | None = None,
    axis: StressAxis | None = None,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
) -> pd.DataFrame:
    """Project RWA / ECL / BIS quarter-by-quarter for each stress path.

    Returns a long DataFrame: scenario, quarter, q_index, severity, gdp_shock,
    lgd_addon, rwa_total, ecl, cet1_ratio, cet1_surplus, passes.
    """
    if paths is None:
        paths = DEFAULT_STRESS_PATHS
    if axis is None:
        axis = StressAxis()
    if quarters is None:
        quarters = forecast_quarter_labels(asof or date.today(), years_ahead)

    base_ecl = compute_ecl(irb_portfolio, eir=eir)["ecl"].sum()
    n = len(quarters)
    rows = []
    for path in paths:
        for i, (qlabel, s) in enumerate(zip(quarters, path.severities(n))):
            sc = axis.scenario_at(s)
            ev = evaluate_scenario(irb_portfolio, capital, rwa_other, sc,
                                   base_ecl=base_ecl, buffers=buffers, eir=eir)
            rows.append({
                "scenario": path.name,
                "quarter": qlabel,
                "q_index": i,
                "severity": s,
                "gdp_shock": sc.gdp_shock,
                "lgd_addon": sc.lgd_addon,
                "rwa_total": ev["rwa_total"],
                "ecl": ev["ecl"],
                "cet1_ratio": ev["cet1_ratio"],
                "cet1_surplus": ev["cet1_surplus"],
                "passes": ev["passes"],
            })
    return pd.DataFrame(rows)


def path_trough_summary(path_df: pd.DataFrame) -> pd.DataFrame:
    """Per-scenario worst quarter: trough CET1, its quarter, horizon-end CET1,
    and the first breach quarter (if any)."""
    rows = []
    for name, g in path_df.groupby("scenario", sort=False):
        trough = g.loc[g["cet1_ratio"].idxmin()]
        end = g.loc[g["q_index"].idxmax()]
        breaches = g[~g["passes"]]
        first_breach = breaches.loc[breaches["q_index"].idxmin(), "quarter"] \
            if len(breaches) else None
        rows.append({
            "scenario": name,
            "trough_cet1": float(trough["cet1_ratio"]),
            "trough_quarter": trough["quarter"],
            "end_cet1": float(end["cet1_ratio"]),
            "first_breach": first_breach,
            "passes_all": bool(g["passes"].all()),
        })
    return pd.DataFrame(rows)
