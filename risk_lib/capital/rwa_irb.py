"""Internal Ratings-Based (IRB) approach for credit RWA.

Implements the Basel III risk weight function for corporate / sovereign /
bank exposures (CRE31).  Retail uses a different correlation; supported via
asset_class="retail_other"/"retail_revolving"/"residential_mortgage".

Formulas (corporate):
    R   = 0.12 * (1 - exp(-50*PD)) / (1 - exp(-50))
        + 0.24 * (1 - (1 - exp(-50*PD)) / (1 - exp(-50)))
    b   = (0.11852 - 0.05478 * ln(PD))**2
    K   = LGD * [N(sqrt(1/(1-R))*G(PD) + sqrt(R/(1-R))*G(0.999)) - PD]
              * (1 + (M-2.5)*b) / (1 - 1.5*b)
    RWA = K * 12.5 * EAD
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import norm


AssetClass = Literal[
    "corporate", "sovereign", "bank",
    "retail_other", "retail_revolving", "residential_mortgage",
]

# Floors per Basel III (CRE32).
PD_FLOOR_CORPORATE = 0.0003   # 3 bp
PD_FLOOR_RETAIL = 0.0003
LGD_FLOOR_UNSECURED_CORP = 0.25  # FIRB unsecured senior; AIRB has different floors
LGD_FLOOR_MORTGAGE = 0.05


def _correlation(pd_value: float, asset_class: str) -> float:
    """Asset correlation R per Basel III CRE31."""
    pd_value = max(pd_value, 1e-10)
    ac = asset_class.lower()
    if ac in ("corporate", "sovereign", "bank"):
        w = (1 - math.exp(-50 * pd_value)) / (1 - math.exp(-50))
        return 0.12 * w + 0.24 * (1 - w)
    if ac == "residential_mortgage":
        return 0.15
    if ac == "retail_revolving":
        return 0.04
    if ac == "retail_other":
        w = (1 - math.exp(-35 * pd_value)) / (1 - math.exp(-35))
        return 0.03 * w + 0.16 * (1 - w)
    raise ValueError(f"unknown asset_class: {asset_class}")


def _maturity_adjustment(pd_value: float, maturity: float) -> float:
    """Maturity adjustment factor (corporate/sovereign/bank only).

    Returns (1 + (M-2.5)*b) / (1 - 1.5*b).
    """
    pd_value = max(pd_value, 1e-10)
    b = (0.11852 - 0.05478 * math.log(pd_value)) ** 2
    m = max(1.0, min(maturity, 5.0))  # M floored at 1y, capped at 5y
    return (1 + (m - 2.5) * b) / (1 - 1.5 * b)


def irb_capital_requirement(
    pd_value: float,
    lgd: float,
    asset_class: str = "corporate",
    maturity: float = 2.5,
    *,
    apply_floor: bool = True,
) -> float:
    """Capital requirement K per unit of EAD."""
    if apply_floor:
        floor = PD_FLOOR_RETAIL if "retail" in asset_class else PD_FLOOR_CORPORATE
        pd_value = max(pd_value, floor)
    pd_value = min(pd_value, 1.0)
    lgd = max(0.0, min(lgd, 1.0))

    r = _correlation(pd_value, asset_class)
    # UL capital (Vasicek): N(sqrt(1/(1-R))*G(PD) + sqrt(R/(1-R))*G(0.999)) - PD
    g_pd = norm.ppf(pd_value)
    g_999 = norm.ppf(0.999)
    cond_pd = norm.cdf(math.sqrt(1.0 / (1.0 - r)) * g_pd
                       + math.sqrt(r / (1.0 - r)) * g_999)
    k = lgd * (cond_pd - pd_value)

    if asset_class.lower() in ("corporate", "sovereign", "bank"):
        k *= _maturity_adjustment(pd_value, maturity)

    return max(k, 0.0)


def compute_rwa_irb(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Compute IRB RWA for a portfolio.

    Required columns: exposure_id, asset_class, ead, pd, lgd
    Optional: maturity (defaults 2.5y for wholesale, ignored for retail)
    """
    required = {"exposure_id", "asset_class", "ead", "pd", "lgd"}
    missing = required - set(portfolio.columns)
    if missing:
        raise ValueError(f"portfolio missing columns: {missing}")

    df = portfolio.copy()
    if "maturity" not in df.columns:
        df["maturity"] = 2.5

    df["k"] = df.apply(
        lambda r: irb_capital_requirement(
            r["pd"], r["lgd"], r["asset_class"], r.get("maturity", 2.5),
        ),
        axis=1,
    )
    df["rwa"] = df["k"] * 12.5 * df["ead"]
    df["capital_8pct"] = df["rwa"] * 0.08
    df["el"] = df["pd"] * df["lgd"] * df["ead"]  # Expected Loss
    return df
