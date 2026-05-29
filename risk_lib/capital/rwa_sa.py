"""Standardized Approach (SA) for credit RWA.

Reference: Basel III CRE20 (revised SA, 2023) and 금감원 「은행업감독업무시행세칙」 별표.
The lookup tables follow the External Credit Risk Assessment (ECRA) variant
which Korean banks generally apply for sovereigns/banks/corporates.
"""

from __future__ import annotations

import pandas as pd


# External rating buckets used throughout (S&P style).
_RATING_BUCKETS = ["AAA-AA", "A", "BBB", "BB", "B", "CCC-", "UNRATED"]


# Risk weight tables (decimal, not %).  Source: Basel III CRE20.
_RW_SOVEREIGN = {
    "AAA-AA": 0.00,
    "A": 0.20,
    "BBB": 0.50,
    "BB": 1.00,
    "B": 1.00,
    "CCC-": 1.50,
    "UNRATED": 1.00,
}

_RW_BANK_ECRA = {
    "AAA-AA": 0.20,
    "A": 0.30,
    "BBB": 0.50,
    "BB": 1.00,
    "B": 1.00,
    "CCC-": 1.50,
    "UNRATED": 1.00,
}

_RW_CORPORATE = {
    "AAA-AA": 0.20,
    "A": 0.50,
    "BBB": 0.75,
    "BB": 1.00,
    "B": 1.00,
    "CCC-": 1.50,
    "UNRATED": 1.00,
}

# Retail regulatory (qualifying retail / SME retail): flat 75%.
_RW_RETAIL_REGULATORY = 0.75
# Other retail (non-qualifying): 100%.
_RW_RETAIL_OTHER = 1.00

# Past-due exposures (>90일 연체): 150% if specific provisions <20% of unsecured,
# 100% otherwise.  Simplified to 150%.
_RW_PAST_DUE = 1.50


# Public per-asset-class rating→RW tables (for vectorised lookups).
SA_RISK_WEIGHTS = {
    "sovereign": _RW_SOVEREIGN,
    "bank": _RW_BANK_ECRA,
    "corporate": _RW_CORPORATE,
}


def _mortgage_rw(ltv: float) -> float:
    """Residential mortgage RW by LTV (Basel III CRE20.82, whole-loan approach)."""
    if ltv <= 0.50:
        return 0.20
    if ltv <= 0.60:
        return 0.25
    if ltv <= 0.80:
        return 0.30
    if ltv <= 0.90:
        return 0.40
    if ltv <= 1.00:
        return 0.50
    return 0.70  # LTV > 100%


def sa_risk_weight(
    asset_class: str,
    rating: str = "UNRATED",
    *,
    ltv: float | None = None,
    past_due: bool = False,
) -> float:
    """Return the SA risk weight for one exposure.

    asset_class: one of {"sovereign", "bank", "corporate",
                          "retail_regulatory", "retail_other",
                          "residential_mortgage"}.
    """
    if past_due:
        return _RW_PAST_DUE

    ac = asset_class.lower()
    if ac == "sovereign":
        return _RW_SOVEREIGN.get(rating, 1.00)
    if ac == "bank":
        return _RW_BANK_ECRA.get(rating, 1.00)
    if ac == "corporate":
        return _RW_CORPORATE.get(rating, 1.00)
    if ac == "retail_regulatory":
        return _RW_RETAIL_REGULATORY
    if ac == "retail_other":
        return _RW_RETAIL_OTHER
    if ac == "residential_mortgage":
        if ltv is None:
            raise ValueError("residential_mortgage requires ltv")
        return _mortgage_rw(ltv)
    raise ValueError(f"unknown asset_class: {asset_class}")


def compute_rwa_sa(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Compute SA RWA for a portfolio DataFrame.

    Required columns:
      exposure_id, asset_class, ead, rating, ltv (nullable), past_due (bool),
      crm_factor (optional, 0..1 multiplier for collateral; 1.0 = no CRM)
    Returns the input frame with added columns: rw, rwa, capital_8pct.
    """
    required = {"exposure_id", "asset_class", "ead", "rating", "past_due"}
    missing = required - set(portfolio.columns)
    if missing:
        raise ValueError(f"portfolio missing columns: {missing}")

    df = portfolio.copy()
    df["rw"] = df.apply(
        lambda r: sa_risk_weight(
            r["asset_class"],
            r.get("rating", "UNRATED"),
            ltv=r.get("ltv"),
            past_due=bool(r["past_due"]),
        ),
        axis=1,
    )
    crm = df["crm_factor"] if "crm_factor" in df.columns else 1.0
    df["rwa"] = df["ead"] * df["rw"] * crm
    df["capital_8pct"] = df["rwa"] * 0.08
    return df
