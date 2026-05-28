"""Credit Risk Mitigation (CRM) and Credit Conversion Factors (CCF).

  - CCF: off-balance-sheet → EAD (Basel III CRE20.94 SA buckets)
  - CRM comprehensive approach with supervisory haircuts (CRE22):
        E* = max(0, E*(1+He) - C*(1-Hc-Hfx))
  - Guarantee/credit-derivative substitution of risk weight on covered portion.
"""

from __future__ import annotations

import pandas as pd


# Basel III SA credit conversion factors (CRE20.94).
CCF_BUCKETS = {
    "unconditionally_cancellable": 0.10,   # was 0% pre-finalisation; 10% in CRE20
    "short_term_trade": 0.20,              # <=1y self-liquidating trade L/C
    "transaction_related": 0.50,           # performance bonds, NIFs, RUFs
    "commitment_le_1y": 0.40,
    "commitment_gt_1y": 0.40,
    "direct_credit_substitute": 1.00,      # guarantees, acceptances
}


def ccf_ead(drawn: float, undrawn: float, ccf_type: str) -> float:
    """EAD for an exposure with an undrawn commitment portion."""
    if ccf_type not in CCF_BUCKETS:
        raise ValueError(f"unknown ccf_type: {ccf_type}")
    return drawn + undrawn * CCF_BUCKETS[ccf_type]


# Standard supervisory haircuts (CRE22.49), 10-business-day, daily remargining.
# Keyed by (collateral_type, residual_maturity_bucket).
_SUPERVISORY_HAIRCUTS = {
    "cash": 0.00,
    "gold": 0.15,
    "sovereign_aaa_le1y": 0.005,
    "sovereign_aaa_1to5y": 0.02,
    "sovereign_aaa_gt5y": 0.04,
    "corp_bond_invest_le1y": 0.01,
    "corp_bond_invest_1to5y": 0.04,
    "corp_bond_invest_gt5y": 0.08,
    "equity_main_index": 0.20,
    "equity_other_listed": 0.30,
}

FX_MISMATCH_HAIRCUT = 0.08  # 8% when exposure and collateral in different currencies


def collateral_haircut(collateral_type: str) -> float:
    if collateral_type not in _SUPERVISORY_HAIRCUTS:
        raise ValueError(f"unknown collateral_type: {collateral_type}")
    return _SUPERVISORY_HAIRCUTS[collateral_type]


def crm_adjusted_ead(
    exposure: float,
    collateral_value: float = 0.0,
    collateral_type: str = "cash",
    *,
    fx_mismatch: bool = False,
    exposure_haircut: float = 0.0,
) -> float:
    """Comprehensive-approach adjusted exposure E*.

    E* = max(0, E*(1+He) - C*(1-Hc-Hfx))
    """
    if exposure < 0:
        raise ValueError("exposure must be >= 0")
    hc = collateral_haircut(collateral_type) if collateral_value > 0 else 0.0
    hfx = FX_MISMATCH_HAIRCUT if (fx_mismatch and collateral_value > 0) else 0.0
    adjusted = exposure * (1 + exposure_haircut) - collateral_value * (1 - hc - hfx)
    return max(0.0, adjusted)


def guarantee_substitution(
    exposure: float,
    covered_amount: float,
    obligor_rw: float,
    guarantor_rw: float,
) -> dict[str, float]:
    """Split RWA between covered (guarantor RW) and uncovered (obligor RW).

    Returns the blended risk weight and component RWAs.
    """
    covered = min(max(covered_amount, 0.0), exposure)
    uncovered = exposure - covered
    rwa = covered * guarantor_rw + uncovered * obligor_rw
    blended_rw = rwa / exposure if exposure > 0 else 0.0
    return {
        "covered": covered,
        "uncovered": uncovered,
        "rwa": rwa,
        "blended_rw": blended_rw,
    }


def apply_crm(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Vectorised CRM/CCF over a portfolio.

    Optional columns (defaults assume no CRM/off-balance):
      drawn, undrawn, ccf_type, collateral_value, collateral_type,
      fx_mismatch, exposure_haircut
    Produces:
      ead_gross   - drawn + CCF*undrawn (or existing 'ead' if no off-balance cols)
      ead         - CRM-adjusted EAD (overwrites the EAD used downstream)
    """
    df = portfolio.copy()

    if {"drawn", "undrawn", "ccf_type"}.issubset(df.columns):
        df["ead_gross"] = df.apply(
            lambda r: ccf_ead(r["drawn"], r["undrawn"], r["ccf_type"]), axis=1
        )
    elif "ead" in df.columns:
        df["ead_gross"] = df["ead"]
    else:
        raise ValueError("need either ('drawn','undrawn','ccf_type') or 'ead'")

    has_collateral = "collateral_value" in df.columns
    df["ead"] = df.apply(
        lambda r: crm_adjusted_ead(
            r["ead_gross"],
            r.get("collateral_value", 0.0) if has_collateral else 0.0,
            r.get("collateral_type", "cash"),
            fx_mismatch=bool(r.get("fx_mismatch", False)),
            exposure_haircut=float(r.get("exposure_haircut", 0.0)),
        ),
        axis=1,
    )
    return df
