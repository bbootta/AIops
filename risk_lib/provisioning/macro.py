"""IFRS 9 거시연계(PIT) ECL — point-in-time PD term structure + 시나리오 확률가중.

The base `ecl.py` runs ECL off a single through-the-cycle (TTC) 12-month PD under
a constant-hazard assumption.  IFRS 9 5.5 instead requires an *unbiased,
probability-weighted, forward-looking* estimate.  This module supplies that:

1.  TTC → PIT.  A Vasicek/ASRF one-factor transform shifts the TTC PD in probit
    space by a systematic factor `z` (deviation of the economy from its long-run
    trend):

        PD_PIT(z) = Φ( Φ⁻¹(PD_TTC) + √(ρ/(1-ρ)) · z )

    Convention here: z > 0 is a downturn (raises PD); z = 0 (the long-run /
    baseline state) reproduces the TTC PD exactly; z < 0 (upside) lowers it.
    ρ is the asset correlation governing macro sensitivity.

2.  Macro → z path.  A `MacroScenario` carries a GDP-growth deviation path over
    an explicit forecast horizon.  GDP maps to z via an elasticity, and beyond
    the forecast horizon z reverts geometrically toward the TTC level (z→0) —
    the standard "reasonable and supportable forecast then revert" mechanic.

3.  PIT term structure.  Year-by-year conditional 1y PIT PDs build a
    non-constant-hazard survival curve; lifetime ECL discounts the marginal
    defaults at the effective interest rate.

4.  Probability weighting.  The reported ECL is Σ_s p_s · ECL_s across multiple
    macro scenarios (upside/baseline/downside/severe), per IFRS 9 B5.5.42.

References: IFRS 9 5.5 / B5.5; Vasicek (2002) one-factor model; 금감원
「대손충당금 적립기준」.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import norm

from risk_lib.provisioning.ecl import (
    Stage, classify_stage_vector, _discounted_loss, _vector_lifetime_const,
)


DEFAULT_RHO = 0.15  # asset correlation for the PIT transform (IFRS9 modelling choice)


@dataclass
class MacroScenario:
    """A forward-looking macro path and its probability weight.

    gdp_path: annual GDP-growth *deviation from long-run trend* over the explicit
              forecast horizon (year 1..H).  Negative = downturn.
    gdp_z_beta: GDP deviation → systematic factor sensitivity (z = -beta·gdp).
    reversion: geometric decay of z toward TTC (z→0) for years beyond H.
    """
    name: str
    probability: float
    gdp_path: tuple[float, ...]
    gdp_z_beta: float = 30.0
    reversion: float = 0.5

    def z_path(self, n_years: int) -> np.ndarray:
        """Systematic factor for years 1..n_years (downturn ⇒ positive z)."""
        base = np.array([-self.gdp_z_beta * g for g in self.gdp_path], dtype=float)
        if n_years <= len(base):
            return base[:n_years]
        last = base[-1] if len(base) else 0.0
        tail = np.array([last * self.reversion ** k
                         for k in range(1, n_years - len(base) + 1)])
        return np.concatenate([base, tail])

    def z_quarterly(self, n_quarters: int) -> np.ndarray:
        """Quarterly systematic factor by ramping from today (z=0) and linearly
        interpolating the annual z-path.  Quarter i (1..n) maps to fractional
        year i/4; the anchor point (year 0, z=0) gives a smooth ramp-in."""
        n_years = max(int(np.ceil(n_quarters / 4)), 1)
        annual = self.z_path(n_years)
        xp = np.arange(0, n_years + 1)                  # 0..n_years
        fp = np.concatenate([[0.0], annual])            # z(0)=0 anchor
        q_years = np.arange(1, n_quarters + 1) / 4.0
        return np.interp(q_years, xp, fp)


# Default IFRS 9 scenario set (probabilities sum to 1).  3-year explicit horizon.
DEFAULT_MACRO_SCENARIOS: list[MacroScenario] = [
    MacroScenario("baseline", 0.50, gdp_path=(0.0, 0.0, 0.0)),
    MacroScenario("downside", 0.30, gdp_path=(-0.020, -0.015, -0.005)),
    MacroScenario("severe",   0.20, gdp_path=(-0.050, -0.030, -0.010)),
]


def _shift_coef(rho: float) -> float:
    """√(ρ/(1-ρ)) with ρ clipped to [0, 1) to avoid div-by-zero / NaN."""
    rho = float(np.clip(rho, 0.0, 1 - 1e-9))
    return float(np.sqrt(rho / (1 - rho)))


def pit_pd(pd_ttc: float, z: float, rho: float = DEFAULT_RHO) -> float:
    """Anchor-preserving PIT PD: probit-shift of the TTC PD by factor z.

    z = 0 returns the TTC PD; z > 0 (downturn) raises it, z < 0 lowers it.
    """
    pd_ttc = float(np.clip(pd_ttc, 1e-6, 1 - 1e-6))
    return float(norm.cdf(norm.ppf(pd_ttc) + _shift_coef(rho) * z))


def pit_term_structure(
    pd_ttc: float, z_path: np.ndarray, rho: float = DEFAULT_RHO,
) -> np.ndarray:
    """Conditional 1-year PIT PD for each year in z_path (vectorised)."""
    pd_ttc = float(np.clip(pd_ttc, 1e-6, 1 - 1e-6))
    k = norm.ppf(pd_ttc)
    return norm.cdf(k + _shift_coef(rho) * np.asarray(z_path, dtype=float))


def _scenario_ecl(
    pd_ttc: float,
    lgd: float,
    ead: float,
    maturity: float,
    stage: Stage,
    z_path: np.ndarray,
    *,
    rho: float,
    eir: float,
    amortising: bool = True,
) -> float:
    """ECL for one exposure under one scenario's z path.

    Stage 1 → 12-month (year-1 PIT) ECL; Stage 2 → lifetime PIT ECL;
    Stage 3 → LGD·EAD (already defaulted, PD = 1).
    """
    lgd = float(np.clip(lgd, 0.0, 1.0))
    ead = max(ead, 0.0)
    if stage == Stage.STAGE_3:
        return lgd * ead
    if stage == Stage.STAGE_1:
        return pit_pd(pd_ttc, z_path[0], rho) * lgd * ead

    n = max(int(np.ceil(maturity)), 1)
    pits = pit_term_structure(pd_ttc, z_path[:n], rho)
    return _discounted_loss(pits, lgd, ead, eir=eir, amortising=amortising)


def _book_scenario_ecl(
    k_vec: np.ndarray, lgd: np.ndarray, ead: np.ndarray, n_vec: np.ndarray,
    stage: np.ndarray, z_path: np.ndarray, coef: float,
    *, eir: float, amortising: bool = True,
) -> np.ndarray:
    """Vectorised per-exposure ECL under one scenario's time-varying z path.

    k_vec = Φ⁻¹(PD_TTC).  Equivalent to `_scenario_ecl` row-wise: Stage 1 uses
    the year-1 PIT PD, Stage 2 the full PIT term structure, Stage 3 LGD·EAD.
    """
    e = len(k_vec)
    if e == 0:
        return np.zeros(0)
    n_max = max(int(n_vec.max()), 1)
    z = np.asarray(z_path, dtype=float)[:n_max]
    if len(z) < n_max:                       # pad with last z if path too short
        z = np.concatenate([z, np.full(n_max - len(z), z[-1] if len(z) else 0.0)])
    pit = norm.cdf(k_vec[:, None] + coef * z[None, :])      # (E, n_max)

    # lifetime via non-constant-hazard survival
    one_minus = 1 - pit
    surv_prev = np.concatenate(
        [np.ones((e, 1)), np.cumprod(one_minus, axis=1)[:, :-1]], axis=1)
    marginal = surv_prev * pit
    t = np.arange(1, n_max + 1)
    n_col = n_vec[:, None]
    ead_t = ead[:, None] * (1 - (t - 1) / n_col) if amortising else \
        np.broadcast_to(ead[:, None], (e, n_max))
    df = (1.0 + eir) ** (-t)
    mask = t <= n_col
    life = (marginal * lgd[:, None] * ead_t * df * mask).sum(axis=1)

    ecl_12m = pit[:, 0] * lgd * ead
    ecl_def = lgd * ead
    return np.select([stage == 1, stage == 2, stage == 3],
                     [ecl_12m, life, ecl_def])


def _book_flat_z_ecl(
    k_vec: np.ndarray, lgd: np.ndarray, ead: np.ndarray, n_vec: np.ndarray,
    stage: np.ndarray, z: float, coef: float, *, eir: float,
) -> np.ndarray:
    """Book ECL under a single (flat) macro state z — the 'current conditions'
    allowance used for the quarterly trajectory.  Stage 2 uses a constant PIT
    hazard PD = Φ(k + coef·z) over remaining maturity."""
    if len(k_vec) == 0:
        return np.zeros(0)
    pit = norm.cdf(k_vec + coef * z)
    life = _vector_lifetime_const(pit, lgd, ead, n_vec, eir=eir)
    ecl_12m = pit * lgd * ead
    ecl_def = lgd * ead
    return np.select([stage == 1, stage == 2, stage == 3],
                     [ecl_12m, life, ecl_def])


@dataclass
class MacroECLResult:
    per_exposure: pd.DataFrame          # exposure_id, stage, ecl_<scenario>..., ecl
    by_scenario: pd.DataFrame           # scenario, probability, ecl
    weighted_total: float
    scenarios: list[MacroScenario] = field(default_factory=list)


def _prepare_book(portfolio: pd.DataFrame, sicr_pd_multiple: float):
    """Shared frame prep + staging for the macro ECL functions."""
    required = {"exposure_id", "ead", "pd", "lgd"}
    missing = required - set(portfolio.columns)
    if missing:
        raise ValueError(f"portfolio missing columns: {missing}")
    df = portfolio.copy()
    if "dpd" not in df.columns:
        df["dpd"] = 0
    if "maturity" not in df.columns:
        df["maturity"] = 1.0

    pd_arr = np.clip(df["pd"].to_numpy(dtype=float), 1e-6, 1 - 1e-6)
    lgd = np.clip(df["lgd"].to_numpy(dtype=float), 0.0, 1.0)
    ead = np.maximum(df["ead"].to_numpy(dtype=float), 0.0)
    n_vec = np.maximum(np.ceil(df["maturity"].to_numpy(dtype=float)).astype(int), 1)
    stage = classify_stage_vector(
        df["dpd"].to_numpy(dtype=float), df["pd"].to_numpy(dtype=float),
        df["pd_origination"].to_numpy(dtype=float) if "pd_origination" in df.columns else None,
        watchlist=df["watchlist"].to_numpy(dtype=bool) if "watchlist" in df.columns else None,
        sicr_pd_multiple=sicr_pd_multiple,
    )
    return df, pd_arr, lgd, ead, n_vec, stage


def macro_ecl(
    portfolio: pd.DataFrame,
    scenarios: list[MacroScenario] | None = None,
    *,
    rho: float = DEFAULT_RHO,
    eir: float = 0.05,
    sicr_pd_multiple: float = 2.0,
) -> MacroECLResult:
    """Probability-weighted, forward-looking (PIT) IFRS 9 ECL (vectorised).

    Required columns: exposure_id, ead, pd, lgd
    Optional: dpd, maturity, pd_origination, watchlist
    `pd` is treated as the TTC anchor that the PIT transform conditions on.
    """
    if scenarios is None:
        scenarios = DEFAULT_MACRO_SCENARIOS
    prob_sum = sum(s.probability for s in scenarios)
    if prob_sum <= 0:
        raise ValueError("scenario probabilities must be positive")

    df, pd_arr, lgd, ead, n_vec, stage = _prepare_book(portfolio, sicr_pd_multiple)
    k_vec = norm.ppf(pd_arr)
    coef = _shift_coef(rho)
    max_n = int(n_vec.max())

    out = df[["exposure_id", "ead"]].copy()
    out["stage"] = stage
    weighted = np.zeros(len(df))
    scen_totals = {}
    for s in scenarios:
        ecl_s = _book_scenario_ecl(k_vec, lgd, ead, n_vec, stage,
                                   s.z_path(max_n), coef, eir=eir)
        out[f"ecl_{s.name}"] = ecl_s
        weighted += s.probability * ecl_s
        scen_totals[s.name] = float(ecl_s.sum())
    weighted /= prob_sum
    out["ecl"] = weighted
    out["coverage_ratio"] = out["ecl"] / out["ead"].replace(0, np.nan)

    by_scen = pd.DataFrame({
        "scenario": [s.name for s in scenarios],
        "probability": [s.probability / prob_sum for s in scenarios],
        "ecl": [scen_totals[s.name] for s in scenarios],
    })
    return MacroECLResult(
        per_exposure=out,
        by_scenario=by_scen,
        weighted_total=float(weighted.sum()),
        scenarios=list(scenarios),
    )


def macro_ecl_path(
    portfolio: pd.DataFrame,
    quarters: list[str],
    scenarios: list[MacroScenario] | None = None,
    *,
    rho: float = DEFAULT_RHO,
    eir: float = 0.05,
    sicr_pd_multiple: float = 2.0,
) -> pd.DataFrame:
    """Quarterly IFRS 9 ECL allowance trajectory aligned to `quarters`.

    For each quarter the book is revalued under that quarter's macro state
    (`MacroScenario.z_quarterly`), respecting staging.  Returns a long frame:
    scenario, quarter, q_index, z, ecl — plus a probability-weighted 'weighted'
    pseudo-scenario per quarter (the headline IFRS 9 allowance path).
    """
    if scenarios is None:
        scenarios = DEFAULT_MACRO_SCENARIOS
    prob_sum = sum(s.probability for s in scenarios)
    if prob_sum <= 0:
        raise ValueError("scenario probabilities must be positive")

    _, pd_arr, lgd, ead, n_vec, stage = _prepare_book(portfolio, sicr_pd_multiple)
    k_vec = norm.ppf(pd_arr)
    coef = _shift_coef(rho)
    nq = len(quarters)

    rows = []
    weighted = np.zeros(nq)
    for s in scenarios:
        zq = s.z_quarterly(nq)
        for i, (q, z) in enumerate(zip(quarters, zq)):
            ecl = float(_book_flat_z_ecl(k_vec, lgd, ead, n_vec, stage,
                                         z, coef, eir=eir).sum())
            rows.append({"scenario": s.name, "quarter": q, "q_index": i,
                         "z": float(z), "ecl": ecl})
            weighted[i] += s.probability * ecl
    weighted /= prob_sum
    for i, q in enumerate(quarters):
        rows.append({"scenario": "weighted", "quarter": q, "q_index": i,
                     "z": float("nan"), "ecl": float(weighted[i])})
    return pd.DataFrame(rows)
