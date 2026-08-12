"""Standardized Approach (SA) for credit RWA.

Reference: Basel III CRE20 (revised SA, 2023) and 금감원 「은행업감독업무시행세칙」 별표.
The lookup tables follow the External Credit Risk Assessment (ECRA) variant
which Korean banks generally apply for sovereigns/banks/corporates.
"""

from __future__ import annotations

import numpy as np
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


_MORTGAGE_LTV_EDGES = np.array([0.50, 0.60, 0.80, 0.90, 1.00])
_MORTGAGE_LTV_RWS = np.array([0.20, 0.25, 0.30, 0.40, 0.50, 0.70])

# Invariant: there must be exactly one risk-weight bucket per LTV edge plus one
# tail bucket for LTV above the highest edge.  Catches accidental edits that
# would silently produce IndexError or skew weights.
assert len(_MORTGAGE_LTV_RWS) == len(_MORTGAGE_LTV_EDGES) + 1, (
    "mortgage LTV RW table must have one more entry than edges"
)


def mortgage_rw(ltv: float) -> float:
    """Residential mortgage RW by LTV (Basel III CRE20.82, whole-loan approach).

    Reference (scalar) implementation; production callers can use
    :func:`mortgage_rw_vector` for a vectorised version.
    """
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


def mortgage_rw_vector(ltv: np.ndarray) -> np.ndarray:
    """Vectorised LTV → RW for residential mortgages (CRE20.82)."""
    ltv = np.asarray(ltv, dtype=float)
    idx = np.searchsorted(_MORTGAGE_LTV_EDGES, ltv, side="left")
    return _MORTGAGE_LTV_RWS[idx]


# Backwards-compatible private alias (kept for any external code that may
# have imported the old underscore name).  Prefer :func:`mortgage_rw` going forward.
_mortgage_rw = mortgage_rw


def sa_risk_weight(
    asset_class: str,
    rating: str = "UNRATED",
    *,
    ltv: float | None = None,
    past_due: bool = False,
) -> float:
    """Return the SA risk weight for one exposure (reference implementation).

    Production callers iterate large frames via :func:`sa_risk_weight_vector`;
    this scalar form remains as the documented single-exposure API and as a
    parity oracle for tests.

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
        return mortgage_rw(ltv)
    raise ValueError(f"unknown asset_class: {asset_class}")


def sa_risk_weight_vector(
    asset_class: np.ndarray,
    rating: np.ndarray | None = None,
    *,
    ltv: np.ndarray | None = None,
    past_due: np.ndarray | None = None,
) -> np.ndarray:
    """Vectorised SA risk weights — numerically identical to row-wise
    :func:`sa_risk_weight`."""
    ac = np.asarray([str(a).lower() for a in asset_class])
    n = len(ac)
    if rating is None:
        rating_arr = np.full(n, "UNRATED", dtype=object)
    else:
        rating_arr = np.where(pd.isna(rating), "UNRATED", rating).astype(object)
    past_due = (np.asarray(past_due, dtype=bool)
                if past_due is not None else np.zeros(n, dtype=bool))

    rw = np.full(n, np.nan)

    for cls, table in (("sovereign", _RW_SOVEREIGN),
                       ("bank", _RW_BANK_ECRA),
                       ("corporate", _RW_CORPORATE)):
        m = ac == cls
        if m.any():
            rw[m] = np.array(
                [table.get(r, 1.00) for r in rating_arr[m]], dtype=float)

    rw[ac == "retail_regulatory"] = _RW_RETAIL_REGULATORY
    rw[ac == "retail_other"] = _RW_RETAIL_OTHER

    m = ac == "residential_mortgage"
    if m.any():
        if ltv is None:
            raise ValueError("residential_mortgage requires ltv")
        ltv_arr = np.asarray(ltv, dtype=float)
        rw[m] = mortgage_rw_vector(ltv_arr[m])

    unknown = np.isnan(rw)
    if unknown.any():
        raise ValueError(f"unknown asset_class(es): {sorted(set(ac[unknown]))}")

    # past_due overrides all (matches scalar function: short-circuit on past_due).
    rw = np.where(past_due, _RW_PAST_DUE, rw)
    return rw


def compute_rwa_sa(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Compute SA RWA for a portfolio DataFrame (vectorised).

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
    df["rw"] = sa_risk_weight_vector(
        df["asset_class"].to_numpy(),
        df["rating"].to_numpy() if "rating" in df.columns else None,
        ltv=df["ltv"].to_numpy() if "ltv" in df.columns else None,
        past_due=df["past_due"].to_numpy(dtype=bool),
    )
    if "crm_factor" in df.columns:
        crm_raw = df["crm_factor"].to_numpy(dtype=float)
        if np.isnan(crm_raw).any():
            raise ValueError("crm_factor contains NaN")
        bad = (crm_raw < 0.0) | (crm_raw > 1.0)
        if bad.any():
            raise ValueError(
                f"crm_factor must be within [0, 1]; "
                f"{int(bad.sum())} row(s) out of range "
                f"(min={crm_raw.min():.4f}, max={crm_raw.max():.4f})"
            )
        crm = crm_raw
    else:
        crm = 1.0
    df["rwa"] = df["ead"] * df["rw"] * crm
    df["capital_8pct"] = df["rwa"] * 0.08
    return df


# Map of internal master-scale corporate grades to the SA rating bucket they
# fall into when computing the full-standardised RWA denominator of the
# output floor.  Used by :func:`standardised_rwa_total`.
def standardised_rwa_total(
    portfolio: pd.DataFrame,
    corp_bucket_by_grade: dict[str, str] | None = None,
) -> float:
    """Total RWA the book would carry under the full SA — the output-floor
    denominator (RBC30.1).

    Resolves SA risk weights per asset class with vectorised lookups:
      - sovereign/bank: rating column → SA_RISK_WEIGHTS table
      - corporate: internal grade → corp_bucket_by_grade → SA_RISK_WEIGHTS["corporate"]
      - retail_regulatory: flat 75% (CRE20.66)
      - retail_other: flat 100% (CRE20.68)
      - residential_mortgage: LTV bucket via :func:`mortgage_rw_vector`
      - others: 1.0
    """
    df = portfolio
    ac = df["asset_class"].to_numpy()
    ead = df["ead"].to_numpy(dtype=float)
    rw = np.ones(len(df))

    for cls in ("sovereign", "bank"):
        m = ac == cls
        if m.any():
            table = SA_RISK_WEIGHTS[cls]
            ratings = (df.loc[m, "rating"].fillna("UNRATED")
                       if "rating" in df.columns
                       else pd.Series(["UNRATED"] * int(m.sum())))
            rw[m] = ratings.map(lambda x: table.get(x, table["UNRATED"])).to_numpy()

    m = ac == "corporate"
    if m.any():
        table = SA_RISK_WEIGHTS["corporate"]
        if corp_bucket_by_grade is not None and "grade" in df.columns:
            buckets = df.loc[m, "grade"].map(
                lambda g: corp_bucket_by_grade.get(g, "UNRATED"))
        else:
            buckets = pd.Series(["UNRATED"] * int(m.sum()))
        rw[m] = buckets.map(lambda b: table.get(b, table["UNRATED"])).to_numpy()

    rw[ac == "retail_regulatory"] = _RW_RETAIL_REGULATORY
    rw[ac == "retail_other"] = _RW_RETAIL_OTHER

    m = ac == "residential_mortgage"
    if m.any():
        ltv = (df.loc[m, "ltv"].fillna(0.8).to_numpy(dtype=float)
               if "ltv" in df.columns
               else np.full(int(m.sum()), 0.8))
        rw[m] = mortgage_rw_vector(ltv)

    return float((ead * rw).sum())
