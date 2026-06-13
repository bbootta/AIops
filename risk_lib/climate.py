"""Climate risk overlay — physical + transition scenario translation.

Two stylised NGFS-style scenarios mapped to portfolio exposure:
  - Physical (acute):    coastal real_estate + shipping + manufacturing
                          take an LGD uplift driven by climate hazard intensity
  - Transition (orderly/disorderly): high-emission sectors (energy / shipping
                          / manufacturing / transport) take a PD uplift via
                          carbon-price pass-through to debt service capacity

Output is a Climate report that summarises:
  - exposure-at-risk (EAR) per sector × scenario
  - ECL uplift vs base ECL (point estimate)
  - 2030 / 2050 horizon decomposition (path lite)

This is an MVP designed to satisfy ECB / BoE / FSS climate stress test
templates at the level a CRO would inspect quarterly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


# ---------------------------------------------------------------- scenario specs

# NGFS-aligned narratives, intensity calibrated by harness defaults.
TRANSITION_SCENARIOS = {
    "orderly":     {"co2_price_2030": 100, "co2_price_2050": 250, "narrative": "Net Zero 2050"},
    "disorderly":  {"co2_price_2030": 50,  "co2_price_2050": 400, "narrative": "Delayed transition"},
    "hot_house":   {"co2_price_2030": 10,  "co2_price_2050": 30,  "narrative": "Current policies"},
}

# Per-sector PD uplift coefficient (per $100/t CO2 price), industry-typical:
TRANSITION_PD_BETA = {
    "energy": 0.020,          # 2pp PD per $100 carbon price
    "manufacturing": 0.010,
    "shipping": 0.015,
    "construction": 0.008,
    "real_estate": 0.005,
    "tech": 0.001,
    "retail_trade": 0.002,
    "financial": 0.001,
    "government": 0.000,
    "household": 0.000,
}

# Physical LGD uplift (acute event severity 0..1 → LGD shift) per sector.
PHYSICAL_LGD_BETA = {
    "real_estate": 0.20,      # +20pp LGD on flood / typhoon damage
    "shipping": 0.18,
    "construction": 0.12,
    "manufacturing": 0.08,
    "energy": 0.10,
    "household": 0.06,        # mortgage collateral exposure
    "retail_trade": 0.04,
    "tech": 0.02,
    "financial": 0.01,
    "government": 0.00,
}

PHYSICAL_SCENARIOS = {
    "current":         {"hazard_intensity": 0.20, "narrative": "1.5°C path"},
    "moderate":        {"hazard_intensity": 0.45, "narrative": "2.0°C path"},
    "severe":          {"hazard_intensity": 0.75, "narrative": "3.0°C path"},
}


@dataclass
class ClimateLeg:
    """Per-scenario climate impact summary."""
    scenario: str
    narrative: str
    by_sector: pd.DataFrame
    total_ear: float             # exposure-at-risk
    base_ecl: float
    climate_ecl: float
    uplift: float


@dataclass
class ClimateReport:
    transition: list[ClimateLeg] = field(default_factory=list)
    physical: list[ClimateLeg] = field(default_factory=list)
    worst_transition: str = ""
    worst_physical: str = ""


def _ead_by_sector(portfolio: pd.DataFrame) -> pd.Series:
    return portfolio.groupby("sector")["ead"].sum()


def transition_leg(portfolio: pd.DataFrame, base_ecl: float,
                   scenario: str, horizon: str = "2030") -> ClimateLeg:
    """Translate carbon price to a PD uplift → ECL uplift per sector."""
    spec = TRANSITION_SCENARIOS[scenario]
    co2_price = spec[f"co2_price_{horizon}"]
    base_ead = _ead_by_sector(portfolio)

    rows = []
    total_uplift = 0.0
    total_ear = 0.0
    for sec, ead in base_ead.items():
        beta = TRANSITION_PD_BETA.get(sec, 0.0)
        d_pd = beta * (co2_price / 100.0)
        # rough ECL: PD × LGD(~0.45) × EAD; uplift = ΔPD · 0.45 · EAD
        uplift = d_pd * 0.45 * float(ead)
        rows.append({"sector": sec, "ead": float(ead), "delta_pd": d_pd,
                     "uplift_ecl": uplift,
                     "share": float(ead) / base_ead.sum()})
        total_uplift += uplift
        if d_pd > 0:
            total_ear += float(ead)

    by_sector = pd.DataFrame(rows).sort_values("uplift_ecl", ascending=False)
    return ClimateLeg(
        scenario=f"transition_{scenario}_{horizon}",
        narrative=f"{spec['narrative']} @ {horizon} (CO2 ${co2_price}/t)",
        by_sector=by_sector,
        total_ear=total_ear, base_ecl=base_ecl,
        climate_ecl=base_ecl + total_uplift, uplift=total_uplift,
    )


def physical_leg(portfolio: pd.DataFrame, base_ecl: float,
                 scenario: str) -> ClimateLeg:
    """Acute-event severity → LGD uplift per sector → ECL uplift."""
    spec = PHYSICAL_SCENARIOS[scenario]
    intensity = spec["hazard_intensity"]
    base_ead = _ead_by_sector(portfolio)

    rows = []
    total_uplift = 0.0
    total_ear = 0.0
    for sec, ead in base_ead.items():
        beta = PHYSICAL_LGD_BETA.get(sec, 0.0)
        d_lgd = beta * intensity
        # uplift ≈ avg PD(~0.02) × ΔLGD × EAD on the at-risk sectors
        uplift = 0.02 * d_lgd * float(ead)
        rows.append({"sector": sec, "ead": float(ead),
                     "delta_lgd": d_lgd, "uplift_ecl": uplift,
                     "share": float(ead) / base_ead.sum()})
        total_uplift += uplift
        if d_lgd > 0:
            total_ear += float(ead)

    by_sector = pd.DataFrame(rows).sort_values("uplift_ecl", ascending=False)
    return ClimateLeg(
        scenario=f"physical_{scenario}",
        narrative=f"{spec['narrative']} hazard intensity {intensity:.0%}",
        by_sector=by_sector,
        total_ear=total_ear, base_ecl=base_ecl,
        climate_ecl=base_ecl + total_uplift, uplift=total_uplift,
    )


def run_climate(portfolio: pd.DataFrame, base_ecl: float) -> ClimateReport:
    transition = [transition_leg(portfolio, base_ecl, s, "2030")
                  for s in TRANSITION_SCENARIOS]
    transition += [transition_leg(portfolio, base_ecl, s, "2050")
                   for s in TRANSITION_SCENARIOS]
    physical = [physical_leg(portfolio, base_ecl, s)
                for s in PHYSICAL_SCENARIOS]
    rep = ClimateReport(transition=transition, physical=physical)
    rep.worst_transition = max(transition, key=lambda x: x.uplift).scenario
    rep.worst_physical = max(physical, key=lambda x: x.uplift).scenario
    return rep
