"""Economic capital by risk type and ICAAP adequacy assessment.

  - credit:        IRB unexpected-loss capital (99.9%) over the whole book
                   + a Pillar 2 concentration add-on (simplified granularity
                   adjustment off sector/country HHI, Gordy 2003)
  - market:        market RWA × 8%
  - operational:   op RWA × 8%
  - irrbb:         worst ΔEVE decline across the six standard shocks

Aggregation: variance-covariance with the supervisory-style inter-risk
correlation matrix (references.ICAAP_CORRELATION).  Adequacy compares the
aggregate EC to available financial resources (총자본) and grades utilisation
green / amber / red.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.references import (
    ICAAP_RISK_TYPES, ICAAP_CORRELATION,
    ICAAP_GREEN_UTILISATION, ICAAP_AMBER_UTILISATION,
)


@dataclass
class ICAAPResult:
    ec_by_type: pd.DataFrame      # risk_type, ec (standalone)
    ec_standalone_sum: float
    ec_diversified: float
    diversification_benefit: float
    concentration_addon: float
    available_capital: float      # AFR = 총자본
    utilisation: float            # ec_diversified / AFR
    buffer: float                 # AFR - ec_diversified
    grade: str                    # GREEN | AMBER | RED

    def passes(self) -> bool:
        return self.grade != "RED"


def concentration_addon_rate(hhi_sector: float, hhi_country: float) -> float:
    """Pillar 2 concentration add-on as a fraction of credit EC.

    Simplified granularity adjustment: linear in the sector/country HHIs,
    capped at 15% of credit EC.
    """
    return float(min(0.15, 0.5 * hhi_sector + 0.3 * hhi_country))


def compute_icaap(
    *,
    credit_ec: float,
    market_ec: float,
    op_ec: float,
    irrbb_ec: float,
    hhi_sector: float,
    hhi_country: float,
    available_capital: float,
) -> ICAAPResult:
    addon = credit_ec * concentration_addon_rate(hhi_sector, hhi_country)
    ec = {
        "credit": credit_ec + addon,
        "market": market_ec,
        "operational": op_ec,
        "irrbb": irrbb_ec,
    }
    e = np.array([ec[t] for t in ICAAP_RISK_TYPES], dtype=float)
    rho = np.array(ICAAP_CORRELATION, dtype=float)
    ec_div = float(np.sqrt(e @ rho @ e))
    standalone = float(e.sum())

    util = ec_div / available_capital if available_capital > 0 else float("inf")
    if util <= ICAAP_GREEN_UTILISATION:
        grade = "GREEN"
    elif util <= ICAAP_AMBER_UTILISATION:
        grade = "AMBER"
    else:
        grade = "RED"

    return ICAAPResult(
        ec_by_type=pd.DataFrame(
            [{"risk_type": t, "ec": ec[t]} for t in ICAAP_RISK_TYPES]),
        ec_standalone_sum=standalone,
        ec_diversified=ec_div,
        diversification_benefit=standalone - ec_div,
        concentration_addon=addon,
        available_capital=available_capital,
        utilisation=util,
        buffer=available_capital - ec_div,
        grade=grade,
    )
