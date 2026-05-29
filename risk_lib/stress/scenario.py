"""Macro stress testing.

A scenario shifts PD (multiplicatively) and LGD (additively, in pp), then the
harness recomputes IRB RWA, total capital ratio, and IFRS 9 ECL.  PD stress can
be expressed directly (pd_multiplier) or derived from a GDP shock via a simple
satellite elasticity.

References: 금감원 스트레스테스트 가이드라인, EBA/Fed CCAR severity design.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.provisioning.ecl import compute_ecl


@dataclass
class Scenario:
    name: str
    pd_multiplier: float = 1.0     # applied to PD (capped at 1.0)
    lgd_addon: float = 0.0         # additive pp to LGD (capped at 1.0)
    gdp_shock: float = 0.0         # GDP growth delta (informational / satellite)
    pd_gdp_elasticity: float = -8.0  # %PD change per 1.0 GDP change (logit space)

    def stress_pd(self, pd_base: np.ndarray) -> np.ndarray:
        pd_base = np.asarray(pd_base, dtype=float)
        mult = self.pd_multiplier
        if self.gdp_shock != 0.0:
            # satellite: logit(PD) shifts by elasticity * gdp_shock
            logit = np.log(np.clip(pd_base, 1e-6, 1 - 1e-6) /
                           (1 - np.clip(pd_base, 1e-6, 1 - 1e-6)))
            logit = logit + self.pd_gdp_elasticity * self.gdp_shock
            pd_sat = 1 / (1 + np.exp(-logit))
            pd_base = np.maximum(pd_base, pd_sat)
        return np.clip(pd_base * mult, 0.0, 1.0)

    def stress_lgd(self, lgd_base: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(lgd_base, dtype=float) + self.lgd_addon, 0.0, 1.0)


BASELINE = Scenario("baseline", pd_multiplier=1.0, lgd_addon=0.0, gdp_shock=0.0)
ADVERSE = Scenario("adverse", pd_multiplier=1.8, lgd_addon=0.07, gdp_shock=-0.03)
SEVERELY_ADVERSE = Scenario("severely_adverse", pd_multiplier=3.0,
                            lgd_addon=0.15, gdp_shock=-0.06)


@dataclass
class StressAxis:
    """Maps a scalar severity s >= 0 to a Scenario along one stress direction.

    GDP shock = -s * gdp_per_unit (drives PD via the satellite elasticity);
    LGD add-on = s * lgd_addon_per_unit.  Shared by reverse stress (solve for s)
    and the quarterly stress path (s varies over the horizon).
    """
    gdp_per_unit: float = 0.03          # GDP drop per unit severity
    lgd_addon_per_unit: float = 0.05    # LGD add-on (pp) per unit severity
    pd_gdp_elasticity: float = -8.0     # logit-space PD sensitivity to GDP

    def scenario_at(self, severity: float) -> Scenario:
        return Scenario(
            name=f"s={severity:.4f}",
            pd_multiplier=1.0,
            lgd_addon=severity * self.lgd_addon_per_unit,
            gdp_shock=-severity * self.gdp_per_unit,
            pd_gdp_elasticity=self.pd_gdp_elasticity,
        )


def apply_scenario(portfolio: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    """Return a copy with stressed pd/lgd columns."""
    df = portfolio.copy()
    df["pd"] = scenario.stress_pd(df["pd"].values)
    df["lgd"] = scenario.stress_lgd(df["lgd"].values)
    return df


def evaluate_scenario(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    scenario: Scenario,
    *,
    base_ecl: float,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
) -> dict:
    """Recompute RWA / ECL / BIS under a single scenario.

    CET1 is reduced by the *incremental* ECL above `base_ecl` (P&L impact).
    Returns a dict including every BIS ratio plus the BISResult, so callers can
    pick the metric they need (forward stress vs reverse stress).
    """
    stressed = apply_scenario(irb_portfolio, scenario)
    rwa_irb = compute_rwa_irb(stressed)["rwa"].sum()
    ecl = compute_ecl(stressed, eir=eir)["ecl"].sum()
    rwa_total = rwa_irb + rwa_other

    incremental_ecl = max(ecl - base_ecl, 0.0)
    stressed_cap = CapitalStack(
        cet1=capital.cet1 - incremental_ecl,
        additional_t1=capital.additional_t1,
        tier2=capital.tier2,
    )
    bis = compute_bis_ratios(stressed_cap, rwa_total, buffers=buffers)
    return {
        "scenario": scenario.name,
        "rwa_irb": rwa_irb,
        "rwa_total": rwa_total,
        "ecl": ecl,
        "incremental_ecl": incremental_ecl,
        "cet1_ratio": bis.cet1_ratio,
        "tier1_ratio": bis.tier1_ratio,
        "total_ratio": bis.total_ratio,
        "cet1_surplus": bis.surplus_shortfall["cet1"],
        "passes": bis.passes(),
        "bis": bis,
    }


_STRESS_COLUMNS = [
    "scenario", "rwa_irb", "rwa_total", "ecl", "incremental_ecl",
    "cet1_ratio", "total_ratio", "cet1_surplus", "passes",
]


def run_stress(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    scenarios: list[Scenario] | None = None,
    *,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
) -> pd.DataFrame:
    """Recompute RWA, total capital ratio, and ECL under each scenario.

    irb_portfolio: needs exposure_id, asset_class, ead, pd, lgd (+ maturity, dpd).
    rwa_other: non-IRB RWA held fixed under stress (SA credit + market + op).
    """
    if scenarios is None:
        scenarios = [BASELINE, ADVERSE, SEVERELY_ADVERSE]

    base_ecl = compute_ecl(irb_portfolio, eir=eir)["ecl"].sum()
    rows = [
        evaluate_scenario(irb_portfolio, capital, rwa_other, sc,
                          base_ecl=base_ecl, buffers=buffers, eir=eir)
        for sc in scenarios
    ]
    return pd.DataFrame(rows)[_STRESS_COLUMNS]
