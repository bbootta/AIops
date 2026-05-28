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

from risk_lib.provisioning.ecl import Stage, classify_stage


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


# Default IFRS 9 scenario set (probabilities sum to 1).  3-year explicit horizon.
DEFAULT_MACRO_SCENARIOS: list[MacroScenario] = [
    MacroScenario("baseline", 0.50, gdp_path=(0.0, 0.0, 0.0)),
    MacroScenario("downside", 0.30, gdp_path=(-0.020, -0.015, -0.005)),
    MacroScenario("severe",   0.20, gdp_path=(-0.050, -0.030, -0.010)),
]


def pit_pd(pd_ttc: float, z: float, rho: float = DEFAULT_RHO) -> float:
    """Anchor-preserving PIT PD: probit-shift of the TTC PD by factor z.

    z = 0 returns the TTC PD; z > 0 (downturn) raises it, z < 0 lowers it.
    """
    pd_ttc = float(np.clip(pd_ttc, 1e-6, 1 - 1e-6))
    k = norm.ppf(pd_ttc)
    x = k + np.sqrt(rho / (1 - rho)) * z
    return float(norm.cdf(x))


def pit_term_structure(
    pd_ttc: float, z_path: np.ndarray, rho: float = DEFAULT_RHO,
) -> np.ndarray:
    """Conditional 1-year PIT PD for each year in z_path."""
    return np.array([pit_pd(pd_ttc, z, rho) for z in z_path])


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
    surv_prev = 1.0
    ecl = 0.0
    for t in range(1, n + 1):
        p_t = pits[t - 1]
        marginal_pd = surv_prev * p_t
        ead_t = ead * (1 - (t - 1) / n) if amortising else ead
        df = 1.0 / ((1 + eir) ** t)
        ecl += marginal_pd * lgd * ead_t * df
        surv_prev *= (1 - p_t)
    return ecl


@dataclass
class MacroECLResult:
    per_exposure: pd.DataFrame          # exposure_id, stage, ecl_<scenario>..., ecl
    by_scenario: pd.DataFrame           # scenario, probability, ecl
    weighted_total: float
    scenarios: list[MacroScenario] = field(default_factory=list)


def macro_ecl(
    portfolio: pd.DataFrame,
    scenarios: list[MacroScenario] | None = None,
    *,
    rho: float = DEFAULT_RHO,
    rho_by_class: dict[str, float] | None = None,
    eir: float = 0.05,
    sicr_pd_multiple: float = 2.0,
) -> MacroECLResult:
    """Probability-weighted, forward-looking (PIT) IFRS 9 ECL.

    Required columns: exposure_id, ead, pd, lgd
    Optional: dpd, maturity, pd_origination, watchlist, asset_class
    `pd` is treated as the TTC anchor that the PIT transform conditions on.
    """
    required = {"exposure_id", "ead", "pd", "lgd"}
    missing = required - set(portfolio.columns)
    if missing:
        raise ValueError(f"portfolio missing columns: {missing}")
    if scenarios is None:
        scenarios = DEFAULT_MACRO_SCENARIOS

    prob_sum = sum(s.probability for s in scenarios)
    if prob_sum <= 0:
        raise ValueError("scenario probabilities must be positive")

    df = portfolio.copy()
    if "dpd" not in df.columns:
        df["dpd"] = 0
    if "maturity" not in df.columns:
        df["maturity"] = 1.0

    max_n = max(int(np.ceil(df["maturity"].max())), 1)
    z_paths = {s.name: s.z_path(max_n) for s in scenarios}

    stages: list[int] = []
    scen_cols: dict[str, list[float]] = {s.name: [] for s in scenarios}
    weighted: list[float] = []

    for _, r in df.iterrows():
        stage = classify_stage(
            int(r["dpd"]), float(r["pd"]), r.get("pd_origination"),
            sicr_pd_multiple=sicr_pd_multiple,
            watchlist=bool(r.get("watchlist", False)),
        )
        rho_i = rho
        if rho_by_class is not None:
            rho_i = rho_by_class.get(r.get("asset_class"), rho)

        w_ecl = 0.0
        for s in scenarios:
            ecl_s = _scenario_ecl(
                float(r["pd"]), float(r["lgd"]), float(r["ead"]),
                float(r["maturity"]), stage, z_paths[s.name],
                rho=rho_i, eir=eir,
            )
            scen_cols[s.name].append(ecl_s)
            w_ecl += s.probability * ecl_s
        stages.append(int(stage))
        weighted.append(w_ecl / prob_sum)

    out = df[["exposure_id", "ead"]].copy()
    out["stage"] = stages
    for name, vals in scen_cols.items():
        out[f"ecl_{name}"] = vals
    out["ecl"] = weighted
    out["coverage_ratio"] = out["ecl"] / out["ead"].replace(0, np.nan)

    by_scen = pd.DataFrame({
        "scenario": [s.name for s in scenarios],
        "probability": [s.probability / prob_sum for s in scenarios],
        "ecl": [float(np.sum(scen_cols[s.name])) for s in scenarios],
    })
    return MacroECLResult(
        per_exposure=out,
        by_scenario=by_scen,
        weighted_total=float(np.sum(weighted)),
        scenarios=list(scenarios),
    )
