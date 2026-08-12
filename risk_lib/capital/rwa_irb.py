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

from risk_lib.references import (
    PD_FLOOR_BPS, LGD_FLOOR_UNSECURED_CORP, LGD_FLOOR_MORTGAGE,
    MATURITY_FLOOR_YEARS, MATURITY_CAP_YEARS, CONFIDENCE_LEVEL,
)


# Floors per Basel III CRE32.
PD_FLOOR_CORPORATE = PD_FLOOR_BPS / 10_000   # 3 bp
PD_FLOOR_RETAIL = PD_FLOOR_BPS / 10_000
# LGD floors retained for documentation; the harness does not auto-floor LGD
# (callers can do so explicitly per CRE32.42 if they want FIRB-style behaviour).
_LGD_FLOOR_UNSECURED_CORP = LGD_FLOOR_UNSECURED_CORP
_LGD_FLOOR_MORTGAGE = LGD_FLOOR_MORTGAGE


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
    m = max(MATURITY_FLOOR_YEARS, min(maturity, MATURITY_CAP_YEARS))  # CRE31.6
    return (1 + (m - 2.5) * b) / (1 - 1.5 * b)


def irb_capital_requirement(
    pd_value: float,
    lgd: float,
    asset_class: str = "corporate",
    maturity: float = 2.5,
    *,
    apply_floor: bool = True,
) -> float:
    """Capital requirement K per unit of EAD (reference implementation).

    Production callers operate on whole portfolios via :func:`irb_k_vector`
    (numerically identical to ≤1e-9; parity is enforced in
    tests/test_vector_parity.py).
    """
    if apply_floor:
        floor = PD_FLOOR_RETAIL if "retail" in asset_class else PD_FLOOR_CORPORATE
        pd_value = max(pd_value, floor)
    pd_value = min(pd_value, 1.0)
    lgd = max(0.0, min(lgd, 1.0))

    r = _correlation(pd_value, asset_class)
    # UL capital (Vasicek): N(sqrt(1/(1-R))*G(PD) + sqrt(R/(1-R))*G(0.999)) - PD
    g_pd = norm.ppf(pd_value)
    g_999 = norm.ppf(CONFIDENCE_LEVEL)
    cond_pd = norm.cdf(math.sqrt(1.0 / (1.0 - r)) * g_pd
                       + math.sqrt(r / (1.0 - r)) * g_999)
    k = lgd * (cond_pd - pd_value)

    if asset_class.lower() in ("corporate", "sovereign", "bank"):
        k *= _maturity_adjustment(pd_value, maturity)

    return max(k, 0.0)


def compute_rwa_irb(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Compute IRB RWA for a portfolio (vectorised).

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

    df["k"] = irb_k_vector(
        df["pd"].to_numpy(dtype=float),
        df["lgd"].to_numpy(dtype=float),
        df["asset_class"].to_numpy(),
        df["maturity"].to_numpy(dtype=float),
    )
    df["rwa"] = df["k"] * 12.5 * df["ead"]
    df["capital_8pct"] = df["rwa"] * 0.08
    df["el"] = df["pd"] * df["lgd"] * df["ead"]  # Expected Loss
    return df


def irb_k_vector(
    pd_value: np.ndarray,
    lgd: np.ndarray,
    asset_class: np.ndarray,
    maturity: np.ndarray,
    *,
    apply_floor: bool = True,
) -> np.ndarray:
    """Vectorised capital requirement K per unit EAD.

    Numerically identical to `irb_capital_requirement` applied row-wise, but
    computed with array ops + vectorised scipy norm so it scales to large books.
    """
    pd_value = np.asarray(pd_value, dtype=float)
    lgd = np.clip(np.asarray(lgd, dtype=float), 0.0, 1.0)
    ac = np.asarray([str(a).lower() for a in asset_class])
    maturity = np.asarray(maturity, dtype=float)

    if apply_floor:
        floor = np.where(np.char.find(ac, "retail") >= 0,
                         PD_FLOOR_RETAIL, PD_FLOOR_CORPORATE)
        pd_value = np.maximum(pd_value, floor)
    pd_value = np.clip(pd_value, 1e-10, 1.0)

    wholesale = np.isin(ac, ("corporate", "sovereign", "bank"))
    # Asset correlation R per CRE31, per asset class.
    w50 = (1 - np.exp(-50 * pd_value)) / (1 - math.exp(-50))
    r_wholesale = 0.12 * w50 + 0.24 * (1 - w50)
    w35 = (1 - np.exp(-35 * pd_value)) / (1 - math.exp(-35))
    r_retail_other = 0.03 * w35 + 0.16 * (1 - w35)
    r = np.select(
        [wholesale, ac == "residential_mortgage",
         ac == "retail_revolving", ac == "retail_other"],
        [r_wholesale, np.full_like(pd_value, 0.15),
         np.full_like(pd_value, 0.04), r_retail_other],
        default=np.nan,
    )
    if np.isnan(r).any():
        bad = sorted(set(ac[np.isnan(r)]))
        raise ValueError(f"unknown asset_class: {bad}")

    g_pd = norm.ppf(pd_value)
    g_999 = norm.ppf(CONFIDENCE_LEVEL)
    cond_pd = norm.cdf(np.sqrt(1.0 / (1.0 - r)) * g_pd
                       + np.sqrt(r / (1.0 - r)) * g_999)
    k = lgd * (cond_pd - pd_value)

    # Maturity adjustment (wholesale only).
    b = (0.11852 - 0.05478 * np.log(pd_value)) ** 2
    m = np.clip(maturity, MATURITY_FLOOR_YEARS, MATURITY_CAP_YEARS)
    mat_adj = (1 + (m - 2.5) * b) / (1 - 1.5 * b)
    k = np.where(wholesale, k * mat_adj, k)

    return np.maximum(k, 0.0)
