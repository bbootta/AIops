"""FRTB IMA framework — Top-IB grade trading book regulation.

BCBS MAR (Fundamental Review of the Trading Book, 2019) requires desks
seeking Internal Models Approach (IMA) approval to pass three tests:

1. **PLAT** (P&L Attribution Test): the hypothetical P&L (HPL) generated
   by the front-office pricing model must align with the risk-theoretical
   P&L (RTPL) from the risk model.
   Two metrics:
     - Spearman correlation: HPL ranks vs RTPL ranks, ≥ 0.80 (green),
       0.70–0.80 (amber), < 0.70 (red → desk fails)
     - KS test: distance between HPL and RTPL distributions,
       ≤ 0.09 (green), 0.09–0.12 (amber), > 0.12 (red)
     A desk falling into the red zone for either metric automatically
     loses IMA status.

2. **RFET** (Risk Factor Eligibility Test): each risk factor used in the
   IMA must have at least 24 observable price quotes in the past year and
   no gap > 1 month. Risk factors failing RFET are called NMRFs
   (Non-Modellable Risk Factors).

3. **NMRF capital add-on**: For each NMRF, a stressed expected shortfall
   (SES) is computed and added to the IMA capital charge.

4. **Backtesting traffic light** (BCBS MAR99): 12-month 1-day 99% VaR
   backtest:
     - green:  ≤ 4 exceptions (no add-on)
     - yellow: 5–9 exceptions (multiplier 1.85–2.00)
     - red:    ≥ 10 exceptions (forced SA fallback)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ----- PLAT ---------------------------------------------------------------

@dataclass
class PLATResult:
    desk: str
    spearman: float                  # rank correlation HPL vs RTPL
    spearman_zone: str               # green / amber / red
    ks_stat: float                   # KS distance between HPL and RTPL
    ks_zone: str
    overall_zone: str                # worst of the two
    n_days: int


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Spearman rank correlation without scipy."""
    a = pd.Series(a).rank().to_numpy()
    b = pd.Series(b).rank().to_numpy()
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a ** 2).sum() * (b ** 2).sum()))
    if denom < 1e-12:
        return 0.0
    return float((a * b).sum() / denom)


def _ks(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sample Kolmogorov-Smirnov statistic, no scipy."""
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    if a.size == 0 or b.size == 0:
        return 1.0
    all_vals = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, all_vals, side="right") / a.size
    cdf_b = np.searchsorted(b, all_vals, side="right") / b.size
    return float(np.abs(cdf_a - cdf_b).max())


def _zone_spearman(rho: float) -> str:
    if rho >= 0.80: return "green"
    if rho >= 0.70: return "amber"
    return "red"


def _zone_ks(ks: float) -> str:
    if ks <= 0.09: return "green"
    if ks <= 0.12: return "amber"
    return "red"


def plat_test(hpl: np.ndarray, rtpl: np.ndarray,
              *, desk: str = "trading") -> PLATResult:
    rho = _spearman(hpl, rtpl)
    ks = _ks(hpl, rtpl)
    rho_z = _zone_spearman(rho)
    ks_z = _zone_ks(ks)
    worst = max(rho_z, ks_z, key=lambda z: {"green": 0, "amber": 1, "red": 2}[z])
    return PLATResult(
        desk=desk, spearman=rho, spearman_zone=rho_z,
        ks_stat=ks, ks_zone=ks_z, overall_zone=worst,
        n_days=int(min(len(hpl), len(rtpl))),
    )


# ----- RFET / NMRF --------------------------------------------------------

@dataclass
class RFETResult:
    n_factors: int
    n_modellable: int
    n_nmrf: int
    nmrf_capital_addon: float        # stressed ES on NMRF (KRW)
    factors: pd.DataFrame            # per-factor detail


def rfet_test(price_history: pd.DataFrame, *,
              min_obs_per_year: int = 24,
              max_gap_days: int = 30) -> RFETResult:
    """For each risk factor (column), count observations and max gap.

    Eligible (modellable) if obs ≥ 24/yr and max_gap ≤ 30 days.
    """
    rows = []
    for col in price_history.columns:
        s = price_history[col].dropna()
        n_obs = len(s)
        if "date" in price_history.columns and len(s) > 1:
            dates = pd.to_datetime(price_history.loc[s.index, "date"])
            gaps = dates.diff().dt.days.dropna()
            max_gap = float(gaps.max()) if len(gaps) else 0.0
        else:
            max_gap = 0.0
        eligible = (n_obs >= min_obs_per_year) and (max_gap <= max_gap_days)
        rows.append({
            "risk_factor": col, "n_obs": n_obs, "max_gap_days": max_gap,
            "modellable": eligible,
        })
    df = pd.DataFrame(rows)

    n_mod = int(df["modellable"].sum())
    n_nmrf = len(df) - n_mod
    # Simplified NMRF add-on: 10% capital adder per NMRF factor
    addon = float(n_nmrf * 1e9)
    return RFETResult(
        n_factors=len(df), n_modellable=n_mod, n_nmrf=n_nmrf,
        nmrf_capital_addon=addon, factors=df,
    )


# ----- Backtesting traffic light ------------------------------------------

@dataclass
class BacktestResult:
    n_days: int
    n_exceptions: int
    zone: str                        # green / yellow / red
    multiplier: float                # 1.5, 1.7, 1.85, ..., 2.0
    failed: bool


def _backtest_zone(n_exc: int) -> tuple[str, float, bool]:
    """BCBS MAR99 traffic light at 250 days."""
    if n_exc <= 4:
        return "green", 1.50, False
    elif n_exc <= 9:
        # graduated multiplier per yellow zone exceptions
        mult = {5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92}[n_exc]
        return "yellow", mult, False
    else:
        return "red", 2.00, True


def backtest_var(pnl: np.ndarray, var_99_1d: np.ndarray) -> BacktestResult:
    """Count days where PnL < -VaR_99 (i.e. loss exceeded VaR)."""
    pnl = np.asarray(pnl, dtype=float)
    var_99_1d = np.asarray(var_99_1d, dtype=float)
    n = min(len(pnl), len(var_99_1d))
    pnl = pnl[:n]
    var = var_99_1d[:n]
    n_exc = int((pnl < -var).sum())
    zone, mult, failed = _backtest_zone(n_exc)
    return BacktestResult(
        n_days=n, n_exceptions=n_exc, zone=zone,
        multiplier=mult, failed=failed,
    )


# ----- IMA capital computation --------------------------------------------

@dataclass
class IMACapital:
    es_97_5: float                   # 99% 1d → 97.5% 10d Expected Shortfall
    multiplier: float                # backtest-driven scalar
    nmrf_addon: float
    ima_capital: float               # final IMA capital charge
    pla_zone: str
    pla_status: str                  # active / under_review / forced_SA
    sa_capital_fallback: float = 0.0


def compute_ima_capital(
    es_97_5: float,
    plat: PLATResult,
    rfet: RFETResult,
    backtest: BacktestResult,
    *, sa_charge: float = 0.0,
) -> IMACapital:
    """Final IMA charge = max(ES_today, multiplier · ES_avg_60d) + NMRF SES.

    PLAT red OR backtest red → desk forced onto SA (with surcharge).
    """
    if plat.overall_zone == "red" or backtest.failed:
        # Desk loses IMA, falls back to SA with surcharge
        return IMACapital(
            es_97_5=es_97_5, multiplier=backtest.multiplier,
            nmrf_addon=rfet.nmrf_capital_addon,
            ima_capital=0.0,
            pla_zone=plat.overall_zone,
            pla_status="forced_SA",
            sa_capital_fallback=sa_charge * 1.30,
        )
    cap = es_97_5 * backtest.multiplier + rfet.nmrf_capital_addon
    status = "active" if plat.overall_zone == "green" else "under_review"
    return IMACapital(
        es_97_5=es_97_5, multiplier=backtest.multiplier,
        nmrf_addon=rfet.nmrf_capital_addon,
        ima_capital=cap, pla_zone=plat.overall_zone,
        pla_status=status,
    )
